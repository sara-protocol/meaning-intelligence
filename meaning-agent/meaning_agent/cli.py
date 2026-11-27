"""Bilingual command-line interface for analysis, review, demo, web, and MCP."""

import argparse
import json
import sys

from . import __version__, analyze, demo, review
from .constants import DEFAULT_MCP_PORT, DEFAULT_WEB_PORT
from .engine import APPROVAL_STATES
from .mcp_public import serve_core
from .mcp_server import serve_stdio
from .safety import strict_json_loads
from .web import serve


def load_json_argument(value, label):
    try:
        result = strict_json_loads(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError(f"{label} 必须是有效 JSON 对象 / {label} must be a valid JSON object.")
    if not isinstance(result, dict):
        raise argparse.ArgumentTypeError(f"{label} 必须是 JSON 对象 / {label} must be a JSON object.")
    return result


def port(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("port 必须是整数 / port must be an integer.")
    if not 1 <= number <= 65535:
        raise argparse.ArgumentTypeError("port 必须在 1–65535 之间 / port must be between 1 and 65535.")
    return number


def _llm_options(parser):
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--llm", action="store_true", help="显式尝试环境配置的 LLM / Explicitly try the configured LLM")
    mode.add_argument("--offline", action="store_true", help="强制离线 / Force offline mode")


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m meaning_agent", description="离线优先的意义智能体；人类最终批准。 / Offline-first Meaning Intelligence; human approval required.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    analyze_parser = commands.add_parser("analyze", help="分析文本并输出双语 Markdown 或 JSON / Analyze text")
    analyze_parser.add_argument("--text", required=True)
    analyze_parser.add_argument("--context", type=lambda value: load_json_argument(value, "context"), default={})
    analyze_parser.add_argument("--scales", nargs="*", default=None)
    analyze_parser.add_argument("--json", action="store_true")
    _llm_options(analyze_parser)

    demo_parser = commands.add_parser("demo", help="运行合成示例 / Run a synthetic demo")
    demo_parser.add_argument("--json", action="store_true")
    _llm_options(demo_parser)

    review_parser = commands.add_parser("review", help="文本递归复核或反馈修订 / Review text or revise previous analysis")
    source = review_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="需要复核的文本 / Text to review")
    source.add_argument("--previous", type=lambda value: load_json_argument(value, "previous"), help="上一轮分析 JSON / Previous analysis JSON")
    source.add_argument("--previous-stdin", action="store_true")
    review_parser.add_argument("--feedback", help="人工反馈 / Human feedback")
    review_parser.add_argument("--approval", choices=list(APPROVAL_STATES), default="pending")
    review_parser.add_argument("--json", action="store_true")
    _llm_options(review_parser)

    serve_parser = commands.add_parser("serve", help="启动仅绑定 127.0.0.1 的本地 Web / Start loopback-only Web UI")
    serve_parser.add_argument("--port", type=port, default=DEFAULT_WEB_PORT)

    mcp_parser = commands.add_parser("mcp", help="通过 HTTP 或 stdio 启动只读 MCP / Start read-only MCP over HTTP or stdio")
    mcp_parser.add_argument("--transport", choices=("http", "stdio"), default="stdio")
    mcp_parser.add_argument("--port", type=port, default=DEFAULT_MCP_PORT)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            use_llm = False if args.offline else True if args.llm else None
            result = analyze(args.text, args.context, args.scales, use_llm=use_llm)
            output = result if args.json else result["markdown"]
        elif args.command == "demo":
            use_llm = False if args.offline else True if args.llm else None
            output = demo(use_llm=use_llm, as_json=args.json)
        elif args.command == "review":
            use_llm = False if args.offline else True if args.llm else None
            if args.text is not None:
                result = review(args.text, approval=args.approval, use_llm=use_llm)
            else:
                if not args.feedback:
                    parser.error("使用 --previous 时需要 --feedback / --feedback is required with --previous")
                previous = args.previous
                if args.previous_stdin:
                    previous = load_json_argument(sys.stdin.read(), "previous")
                result = review(previous, args.feedback)
            output = result if args.json else result["markdown"]
        elif args.command == "serve":
            serve(port=args.port)
            return 0
        elif args.command == "mcp":
            if args.transport == "stdio":
                serve_stdio()
            else:
                serve_core(port=args.port)
            return 0
        else:
            parser.error("未知命令 / unknown command")
        if isinstance(output, str):
            print(output)
        else:
            print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except BrokenPipeError:
        return 0
    except Exception:
        print("meaning-agent: 输入无效或操作失败；未输出敏感详情。 / Invalid input or operation failed; sensitive details were not returned.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
