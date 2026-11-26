---
name: grade-evidence-falsification
description: Assess evidence against E0–E6 and create falsification conditions without automatically assigning an empirical level. Use for research claims, hypothesis review, evidence audits, preregistration design, and canon-to-engineering traceability.
---

# Grade Evidence and Falsification / 证据与证伪

## Overview
Separate canon records, user-supplied metadata, and current empirical status. / 区分正典记录、用户材料与当前实证状态。

## Workflow
1. Read claims from L1 and sanitized evidence metadata. / 读取 L1 断言与已净化证据元数据。
2. Accept only explicit E0–E6 levels tied to a claim or source. / 只接受明确关联断言或来源的 E0–E6 等级。
3. Preserve user level claims as unverified; leave every accepted level null. / 保留用户等级声明为未核实；已接受等级一律为空。
4. Never claim independent verification. / 绝不声称独立验证。
5. Write a testable prediction, opposite result, threshold, and evidence requirements. / 写明可检验预测、相反结果、阈值与证据要求。
6. Mark engineering falsifiers as unpreregistered drafts; never claim they were tested. / 工程证伪条件标为未预注册草案；绝不声称已检验。
7. Label canon hypothesis levels as records, not current assessments. / 正典假设等级仅标为记录，而非当前评估。

## API Mapping
- Runner: `meaning_agent.skills.l4_evidence.run`
- Registry key: `grade-evidence-falsification` or `L4`
- Output: `evidence_items`, `reference_scale`, `linked_hypotheses`, `falsification_conditions`

## Limits
The tool performs no experiments, literature search, or external fact-checking. / 工具不做实验、文献检索或外部事实核查。
