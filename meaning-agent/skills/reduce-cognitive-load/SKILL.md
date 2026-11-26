---
name: reduce-cognitive-load
description: Reduce analytical load by separating assertions from open questions, extracting lexical structure and constraints, and preserving uncertainty. Use for dense decisions, research summaries, policy notes, or mixed fact/question text in Chinese or English.
---

# Reduce Cognitive Load / 减负

## Overview
Run L1 without converting input assertions into verified facts. / 运行 L1，不得把输入断言变成已核实事实。

## Workflow
1. Validate non-empty text; redact secrets and enforce the length limit. / 校验非空文本，遮盖密钥并限制长度。
2. Split statements from explicit questions. / 分离陈述与显式问题。
3. Mark every statement `unverified` and empirical status `unknown`. / 所有陈述标记为未核实，经验状态为未知。
4. Extract lexical nodes and co-occurrence edges; never infer causality. / 抽取词法节点与共现关系，绝不推断因果。
5. Retain hard constraints, source text, and omission counts. / 保留硬约束、原文与省略计数。
6. Return bilingual labels and request clarification only when required input is missing. / 返回双语标签，仅在必需输入缺失时请求澄清。

## API Mapping
- Runner: `meaning_agent.skills.l1_load_reduction.run`
- Registry key: `reduce-cognitive-load` or `L1`
- Output: `fact_question_separation`, `key_structure`, `critical_constraints`, `compression`

## Limits
Lexical heuristics are not fact-checking, psychometrics, or professional judgment. / 词法启发式不是事实核查、心理测量或专业判断。
