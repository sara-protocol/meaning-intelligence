---
name: model-experiential-interface
description: Produce an offline interactive HTML prototype and adjustable interaction parameters for meaning analysis. Use when a decision needs inspectable structure, open questions, pacing, agency, or feedback controls; scripts may only change local display and must never access the network.
---

# Model Experiential Interface / 可体验界面

## Overview
Turn experience into discussable parameters rather than decoration or evidence. / 把体验变成可讨论参数，而非装饰或证据。

## Workflow
1. Read sanitized text and optional L1 structure. / 读取已净化文本与可选 L1 结构。
2. Suggest cognitive load, agency, feedback timing, pace, and reversibility. / 建议认知负荷、行动主体、反馈时机、节奏与可逆性。
3. Produce a standalone HTML fragment whose optional script only changes local node visibility; no network, submission, or command execution. / 生成独立 HTML；可选脚本只改变本地节点显示，不联网、不提交、不执行命令。
4. Escape all source-derived labels and questions. / 转义所有来源标签与问题。
5. Mark parameters as suggestions requiring human approval. / 参数均为建议，需人工批准。
6. Keep interaction separate from evidence strength. / 交互不得改变证据强度。

## API Mapping
- Runner: `meaning_agent.skills.l2_experiential.run`
- Registry key: `model-experiential-interface` or `L2`
- Output: `parameters`, `parameter_suggestions`, `interactive_html`, `html_safety`

## Limits
Treat generated HTML as an untrusted download, not as trusted application code. / 生成 HTML 仅作为不可信下载，不得当作可信应用代码渲染。
