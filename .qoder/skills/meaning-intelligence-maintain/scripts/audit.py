#!/usr/bin/env python3
"""Run the repository's deterministic audit, optionally rebuilding the white paper."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def configure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def find_repo_root() -> Path:
    root = Path(__file__).resolve().parents[4]
    required = ("tools", "msi", "whitepaper", "docs")
    missing = [name for name in required if not (root / name).is_dir()]
    if missing:
        print(f"错误：无法从脚本路径定位完整仓库根：{root}（缺少 {', '.join(missing)}）")
        raise SystemExit(2)
    return root


def command(args: list[str], cwd: Path, label: str) -> int:
    print(f"\n[{label}] python {' '.join(args)}", flush=True)
    env = os.environ.copy()
    env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    try:
        result = subprocess.run(
            [sys.executable, *args],
            cwd=cwd,
            env=env,
            shell=False,
            check=False,
        )
    except OSError as exc:
        print(f"失败：{label} 无法启动：{exc}")
        return 127
    if result.returncode:
        print(f"失败：{label}（退出码 {result.returncode}）", file=sys.stderr)
    return result.returncode


def main() -> int:
    configure_utf8()
    parser = argparse.ArgumentParser(
        description="按固定顺序审计仓库；默认不构建白皮书。"
    )
    parser.add_argument(
        "--build-whitepaper",
        action="store_true",
        help="在 MSI 构建后重建白皮书插图和 DOCX（不转换 PDF、不部署）",
    )
    args = parser.parse_args()
    root = find_repo_root()
    print(f"仓库根：{root}")
    print(f"模式：{'审计并重建白皮书' if args.build_whitepaper else '仅审计（不重建白皮书）'}")
    print("MSI 构建会重写 msi/meaning_intelligence.html 与 meaning_intelligence_diagram.md。")

    base_steps = [
        (["tools/verify_issue_forms.py"], root, "1/6 Issue 表单"),
        (["tools/verify_consistency.py"], root, "2/6 一致性"),
        (["tools/verify_html.py", "msi/meaning_intelligence.html"], root, "3/6 现有 HTML"),
        (["tools/verify_planned_fallback.py"], root, "4/6 planned 回退"),
        (["build.py"], root / "msi", "5/6 构建 MSI"),
        (["tools/verify_html.py", "msi/meaning_intelligence.html"], root, "6/6 构建后 HTML"),
    ]
    steps = base_steps.copy()
    if args.build_whitepaper:
        print("白皮书构建会重写 whitepaper/figures/ 与 whitepaper/dist/ 中的 DOCX。")
        steps.extend([
            (["make_figures.py"], root / "whitepaper", "白皮书插图"),
            (["build_whitepaper.py"], root / "whitepaper", "白皮书 DOCX"),
        ])

    for command_args, cwd, label in steps:
        status = command(command_args, cwd, label)
        if status:
            return status
    print("\n审计通过。未 commit、push、部署或读取凭据。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
