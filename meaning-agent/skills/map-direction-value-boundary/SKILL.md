---
name: map-direction-value-boundary
description: Extract direction, value, and boundary candidates and represent meaning on a continuous spectrum. Use for values clarification, strategic direction, trade-offs, temporal or relational boundaries, and decisions that must remain human-selected.
---

# Map Direction, Value, Boundary / 方向价值边界

## Overview
Expose candidates without choosing a final direction. / 展示候选，不替人选择最终方向。

## Workflow
1. Extract directional statements, value terms, and hard/soft boundaries. / 抽取方向陈述、价值词与硬/软边界。
2. Keep source text and candidate status. / 保留来源文本与候选状态。
3. Represent the spectrum continuously from 0 to 100. / 用 0–100 连续表示光谱。
4. Label heuristic positions as non-measurements. / 明确启发式位置不是测量。
5. Leave selected direction and spectrum position null pending a human. / 在人工选择前，所选方向与位置保持 null。
6. Never treat textual boundaries as legal, ethical, or safety permission. / 文本边界不是法律、伦理或安全许可。

## API Mapping
- Runner: `meaning_agent.skills.l3_meaning_generation.run`
- Registry key: `map-direction-value-boundary` or `L3`
- Output: `dimensions`, `spectrum`, `candidate_not_commitment`

## Limits
Absent signals mean unknown, not neutrality or agreement. / 无信号意味着未知，而非中立或一致。
