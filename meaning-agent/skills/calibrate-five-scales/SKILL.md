---
name: calibrate-five-scales
description: Calibrate individual, organization, city, national, and humanity impacts through conflicts, priorities, costs, and triggers. Use for cross-scale decisions and trade-offs; never use weighted summation or compensatory totals.
---

# Calibrate Five Scales / 五尺度校准

## Overview
Preserve incommensurability across all five scales. / 保留五尺度的不可通约性。

## Workflow
1. Inspect individual, organization, city, national, and humanity rows. / 检查个人、组织、城市、国家、人类五行。
2. Record only explicit scale signals; silence is not neutrality. / 只记录显式信号，沉默不是中立。
3. Surface conflicts, stated priorities, costs, and triggers. / 呈现冲突、既定优先级、成本与触发条件。
4. Check hard boundaries and irreversible harm before stated priorities. / 先检查硬边界与不可逆伤害，再检查既定优先级。
5. Leave final priority null pending human calibration. / 人工校准前最终优先级为空。
6. Forbid weights, numeric totals, and compensation across scales. / 禁止权重、数值总和与跨尺度补偿。

## API Mapping
- Runner: `meaning_agent.skills.l5_direction.run`
- Registry key: `calibrate-five-scales` or `L5`
- Output: `scale_positions`, `conflicts`, `priority_order`, `costs`, `trigger_conditions`, `provisional_direction`

## Limits
Do not infer missing scale positions or convert unlike harms into a common score. / 不得推断缺失尺度立场或把异质伤害换成共同分数。
