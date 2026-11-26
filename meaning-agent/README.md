# Meaning Agent / 意义智能体

离线优先、仅使用 Python 标准库的意义智能体。它把文本整理为可审问的结构，生成方向、价值与边界候选，评估证据边界，校准五个不可通约尺度，并保留人类最终批准。

> L1–L6 是本项目的 E0 工程扩展，不是正典固定层次，也未经过本项目独立检验。正典 H1–H18、附录 D.7 与 E0–E6 定义优先；工程证伪条件只是未预注册草案。

## Quick start / 快速开始

需要 Python 3.10+，无需第三方依赖。

```bash
cd meaning-agent
python -m meaning_agent analyze --text "研究显示效率提升，但来源缺失。是否应该保留自主？" --json
python -m meaning_agent demo
python -m meaning_agent serve --port 8766
```

打开 <http://127.0.0.1:8766>。页面支持文本输入、五尺度选择、可选上下文 JSON、运行、证据与证伪条件、人工批准门、待澄清信息及中英切换。无 LLM 密钥时结果明确为 `mode=offline`。

## Python API

```python
from meaning_agent import analyze, review, demo, to_markdown

result = analyze(
    "组织希望提升效率，但个人担心自主。预算超过100万元时必须暂停。",
    context={
        "direction": "提升协作效率",
        "scale_positions": {
            "individual": {"direction": "保留自主", "alignment": "conflict", "costs": ["选择成本"]},
            "organization": {"direction": "提升效率", "costs": ["预算"]},
        },
        "scale_priorities": ["individual", "organization"],
        "expires_on": "2027-01-01",
    },
    scales=["individual", "organization"],
)
print(result["mode"])          # offline
print(result["approval_gate"]) # status=pending
print(to_markdown(result))

revised = review(result, {"action": "replace_text", "text": "组织提升效率，同时保留个人自主。"})
print(revised["revision_required"])
print(demo(as_json=False))
```

- `analyze(text, context=None, scales=None, *, use_llm=None)` 返回结构化字典并附带 `markdown`。
- `review(text, context=None, approval="pending", use_llm=None)` 或 `review(previous, feedback)` 支持文本复核与反馈修订；修订不会执行。
- `demo(*, as_json=False)` 默认返回 Markdown。

## CLI

```bash
python -m meaning_agent analyze --text "是否应该扩大试点？" --scales individual organization --json
python -m meaning_agent analyze --text "必须设置边界" \
  --context '{"direction":"受控试点","boundaries":{"temporal":"三个月"},"expires_on":"2027-03-01"}'
python -m meaning_agent demo --json
python -m meaning_agent review --text "请复核证据来源。" --json
python -m meaning_agent review --previous-stdin --feedback "请复核证据来源" --json < analysis.json
python -m meaning_agent serve --port 8766
```

JSON 与 Markdown 均为双语输出；`--offline` 强制离线，`--llm` 显式尝试已配置模型。

## Optional LLM / 可选 LLM

只使用 `urllib`，只读取三个环境变量：

- `MI_LLM_BASE_URL`：OpenAI 兼容基地址；远程地址必须 HTTPS。
- `MI_LLM_API_KEY`：仅放入 `Authorization` 头。
- `MI_LLM_MODEL`：模型名。

```bash
export MI_LLM_BASE_URL="https://provider.example/v1"
export MI_LLM_API_KEY="..."
export MI_LLM_MODEL="your-model"
python -m meaning_agent analyze --text "..." --llm --json
```

超时固定 15 秒，响应上限 1 MiB，禁止重定向与环境代理，要求严格 JSON 和字段白名单。LLM 只能提供未核验的双语写作建议，不能改变确定性技能、证据等级、尺度聚合或批准。成功为 `mode=llm`，失败为 `mode=offline_fallback`，无密钥为 `mode=offline`。no keys in logs/files.

## Architecture / 架构与六技能

`meaning_agent/engine.py` 编排 L1–L6，`meaning_agent/skills/registry.py` 是唯一注册入口。技能信封包含 `name`、`description`、`description_en`、`layer`、`input`、`output`、`status`、`needs_clarification`、`data`。

| 层 | 注册名 | 实现 | 职责 |
|---|---|---|---|
| L1 | `reduce-cognitive-load` | `skills/l1_load_reduction.py` | 事实/问题分离、结构、约束；陈述均未核实 |
| L2 | `model-experiential-interface` | `skills/l2_experiential.py` | 参数建议、无脚本安全片段与可选固定本地交互 HTML |
| L3 | `map-direction-value-boundary` | `skills/l3_meaning_generation.py` | 方向、价值、边界与连续光谱 |
| L4 | `grade-evidence-falsification` | `skills/l4_evidence.py` | E0–E6、正典记录、证伪计划；不自动授予实证等级 |
| L5 | `calibrate-five-scales` | `skills/l5_direction.py` | 五尺度冲突、优先级、代价、触发；禁止加权求和 |
| L6 | `recursive-review-zeroing` | `skills/l6_recursive.py` | 三轮有界审视、反馈复核、可逆归零、批准重置 |

六份可复用定义位于 `skills/<name>/SKILL.md`，含规范 frontmatter、使用时机、输入输出、边界与实现映射。

常用上下文字段：`direction`、`value_types`、`boundaries`、`spectrum_position`、`time_horizon`、`frequency`、`scale_positions`、`scale_priorities`、`costs`、`conflicts`、`triggers`、`expires_on`、`evidence`、`sources`、`evidence_claims`。缺失信息返回 `needs_clarification`，不用默认值编造。

## White-paper mapping / 正典与白皮书映射

- 六层是白皮书 E0 工程操作化，不是正典固定层次。
- 方向、价值、边界来自正典 §3.2；连续光谱来自 §8.1，不是三个固定抽屉，也不是 C/V/E/A 四维系缚模型。
- 五尺度遵循正典公理三与 §4.3：个人、组织、城市、国家、人类不可通约，只能递归校准；weighted summation forbidden。
- H1–H18 的等级是正典记录，不是本工具对新分析的独立认定。
- 附录 D.7 保留 SG、Spectrum Spiral、Witness→Leap、MI-AI、Weaving Sovereignty 的失败阈值。
- 工程证伪条件标为 `requires_preregistration=true`、`formal_disposition_allowed=false`。
- 未提供证据时，新主张的实证等级保持 `null` / unknown；E0 仅可作为明确的保守占位说明，不能伪装为真实世界状态。

## MCP server

MCP 使用 JSON-RPC 2.0 与协议 `2024-11-05`，提供 10 个只读 `meaning://` 资源及 `meaning_analyze`、`meaning_review` 两个工具。

```bash
# HTTP, loopback only
python -m meaning_agent mcp --transport http --port 8767

# stdio, one JSON-RPC message per line
python -m meaning_agent mcp --transport stdio
```

HTTP 端点为 `http://127.0.0.1:8767/mcp`。资源包括目录、证据、五尺度、安全边界和六技能；内容为双语。工具标注 `readOnlyHint=true`，不执行分析文本或反馈中的代码。

## Limits and safety / 安全边界与局限

> Human approval defaults pending; localhost-only web UI 127.0.0.1, no arbitrary file/command.
>
> do not execute arbitrary code, do not allow traversal, no network egress beyond configured LLM, no key leakage.

- Web 强制绑定 `127.0.0.1`，校验 Host/Origin。
- 静态资源固定白名单；无任意文件读取、路径参数、shell 或命令执行 API。
- JSON 请求体大小受限，错误脱敏，不记录访问日志；CSP、nosniff、禁框与禁外链资源。
- 输入与上下文遮盖常见密钥；不保存分析、不部署、不提交。
- 批准默认 `pending`；修订触发会使失效批准回到待定；高风险领域提示专业复核。
- L2 的 `safe_html_suggestion` 无脚本；`interactive_html` 是单独、固定的本地显示脚本，不含网络请求，Web UI 只以文本展示、不注入执行。
- 词法与规则启发式不是事实核查、心理测量、实证验证或安全认证；共现不等于因果，光谱位置不是测量；不独立核验证据，不执行实验或外部事实核查；沉默不等于中立，异质伤害不能换算为共同分数；递归审视不能证明无偏、真实或安全，也不替代专业判断。

## Tests / 测试

```bash
python -m compileall -q meaning_agent
python -m unittest discover -s tests -v
node --check meaning_agent/static/app.js
```
