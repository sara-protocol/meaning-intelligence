---
name: recursive-review-zeroing
description: Perform bounded recursive review over evidence, scales, and assumptions, then propose reversible controlled zeroing. Use before human approval, after conflicting feedback, or when direction deviation and boundary uncertainty require a reset.
---

# Recursive Review and Zeroing / 递归审视与归零

## Overview
Review structure without claiming unbiasedness, truth, or safety. / 审视结构，不声称无偏、真实或安全。

## Workflow
1. Inspect feedback, upstream clarification, scale conflict, expiry, and professional-domain triggers. / 检查反馈、上游澄清、尺度冲突、失效日期与专业领域触发。
2. Generate metacognition questions and map each trigger to affected skills. / 生成元认知问题并映射受影响技能。
3. Preserve unverified claims and unknown status. / 保留未核实断言与未知状态。
4. Propose controlled zeroing for requested reset or major review triggers. / 对主动重置或重大复核触发建议受控归零。
5. Pause conclusions, retain source material, list assumptions, seek counterexamples, and rebuild minimally. / 暂停结论、保留材料、列出假设、寻找反例、最小重建。
6. Keep zeroing reversible; delete no data and execute no action. / 归零可逆，不删除数据、不执行操作。
7. Reset invalidated approval to pending. / 已失效批准重置为待定。

## API Mapping
- Runner: `meaning_agent.skills.l6_recursive.run`
- Registry key: `recursive-review-zeroing` or `L6`
- Output: `metacognition_questions`, `review_triggers`, `zeroing_plan`, `revision_suggestions`, `approval_gate`

## Limits
A clean automatic review is not proof of correctness. / 自动审视无问题不等于正确。
