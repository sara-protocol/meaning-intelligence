# 理论失败矩阵（六层版）/ Theory Failure Matrix, Six-Layer Edition

> 这份文档回答一个问题：**每一层在什么观察下会作废，作废之后怎么处理？**
> This document answers one question: **under what observation does each layer become void, and what happens to it then?**

本表沿用正典「理论失败矩阵」的体例，逐层给出**支持证据 / 部分支持 / 失败阈值 / 失败后操作**。
它是本仓库最应该被先读的一页：如果一项主张没有写清什么观察会让它作废，它就不是本项目的成员。

This table follows the canon's Theory Failure Matrix, giving each layer its **supporting evidence /
partial support / failure threshold / post-failure action**. It is the page to read first: a claim with
no stated refuting observation is not a member of this project.

---

## 一、六层失败矩阵 / The Six-Layer Failure Matrix

| 层 Layer | 支持证据 Supporting evidence | 部分支持 Partial support | 失败阈值 Failure threshold | 失败后操作 Post-failure action |
|---|---|---|---|---|
| **L1 减负**<br>Cognitive Load Reduction | 受控语言降低误读率<br>Controlled language reduces misreading | 特定文本类型有效<br>Effective for certain text types | 降维后决策质量无提升（d&lt;0.3）<br>No improvement in decision quality after reduction (d&lt;0.3) | 重设压缩比或放弃字数硬限<br>Reset the compression ratio or drop the hard word limit |
| **L2 可体验**<br>Experiential Rendering | 交互提升结构回忆<br>Interaction improves recall of structure | 特定概念类型有效<br>Effective for certain concept types | 交互组与静态组无显著差异<br>No significant difference between interactive and static groups | 降为可选增强，不作必需层<br>Demote to optional enhancement, not a required layer |
| **L3 意义生成**<br>Meaning Generation | 三维度可被独立评分<br>The three dimensions can be scored independently | 特定文化背景下成立<br>Holds in certain cultural contexts | 意义判断方差被单一维度解释&gt;90%<br>A single dimension explains &gt;90% of the variance in meaning judgment | 接受 H2 被证伪，重构结构模型<br>Accept that H2 is falsified and rebuild the structural model |
| **L4 价值评估**<br>Value Assessment | 证据标注提升判断一致性<br>Evidence labelling improves judgment consistency | 领域专家群体内有效<br>Effective within groups of domain experts | 标注与判断质量无相关<br>No correlation between labelling and judgment quality | 退回定性评估<br>Revert to qualitative assessment |
| **L5 方向选择**<br>Direction Selection | 跨尺度一致者生存更久<br>Cross-scale consistency survives longer | 特定尺度组合成立<br>Holds for certain scale combinations | 长期背离却无危机（H8 反例）<br>Long-term divergence without crisis (a counterexample to H8) | 标记 H8 被证伪，重估五尺度模型<br>Mark H8 as falsified and reassess the five-scale model |
| **L6 反思与审视递归**<br>Recursive Reflection and Review | 归零缓解僵化<br>Zeroing relieves ossification | 案例层面成立<br>Holds at the case level | RCT 无显著差异（d&lt;0.3）<br>No significant difference in the RCT (d&lt;0.3) | 放弃有效性主张，仅保留为操作规程<br>Drop the efficacy claim; keep it only as a procedural rule |

**几点必须连带读出的信息 / What must be read alongside the table:**

- **「支持证据」一列不是该层的证据等级。** 它是该层所依赖的机制或现象，
  其证据等级见 [evidence.md](evidence.md) 第二节的「底层机制」列。这两列不可互换。
  The "supporting evidence" column is **not** the layer's evidence level. It names the mechanism or
  phenomenon the layer leans on; its level is the "underlying mechanism" column in
  [evidence.md](evidence.md). The two are not interchangeable.
- **阈值是预注册的。** 它们在此处被写出，目的正是让任何人都能在看到数据之前知道
  「什么结果算失败」。事后放宽或改写阈值属于 HARKing，见 [CONTRIBUTING.md](../CONTRIBUTING.md)。
  The thresholds are preregistered, so that anyone can know **before** seeing the data what would
  count as failure. Relaxing or rewriting a threshold afterwards is HARKing; see CONTRIBUTING.md.
- **阈值指向的是可观测的量。** 「d&lt;0.3」是对效应量的判定；「&gt;90% 方差」是对结构模型的判定；
  「无相关」「无显著差异」是对关联强度的判定。它们都可以被一次设计良好的观测判定为满足或不满足。
  Each threshold names an observable quantity — an effect size, a share of variance, a correlation, a
  group difference — so a well-designed observation can settle whether it is met.

---

## 二、使用规则 / How the Matrix Is Used

1. **任何一层触及失败阈值，该层将在后续版本中被标记或删除，而不是被辩护。**
   这是本项目的学术诚信承诺，适用于我们自己提出的模块，包括 L1 与 L2 这两层机制基础最强的层。
   **If any layer reaches its failure threshold, that layer will be marked or removed in a later
   version — not defended.** This commitment applies to modules we proposed ourselves, including L1
   and L2, the two layers with the strongest mechanistic basis.
2. **处置方式只有两种：标记或删除。** 二者都不等于「保留但降低声量」。
   - *标记*：该层仍可作为规程或经验做法存在，但**不再主张有效性**（L6 的失败后操作即此）。
   - *删除*：该层从六层栈中移除，并触发对相邻层关系的重新表述。
   Only two outcomes exist: **marked** or **removed**. Neither means "kept but discussed less".
   *Marked*: the layer may remain as a procedure or heuristic, but with **no efficacy claim** (this is
   L6's post-failure action). *Removed*: the layer leaves the stack, which forces the neighbouring
   layers' relations to be restated.
3. **处置必须留痕。** 变更记录在 [`CHANGELOG.md`](../CHANGELOG.md) 的
   「移除或标记 / Removed or Flagged」段落，并注明依据（证据等级、样本、失败判据）。
   Disposition leaves a trace: under "Removed or Flagged" in the changelog, together with its basis
   (evidence level, sample, failure criterion).
4. **不因「整体说得通」而免检。** 「内部一致」与「符合直觉」都不是提升证据等级的正当理由。
   No layer is exempt because the whole "makes sense". Internal consistency and intuitive appeal are
   not valid grounds for raising an evidence level.
5. **一次失败只推翻被检验的那一条主张。** 例如 d&lt;0.3 的失败推翻的是「这一层的操作化产生了
   可察觉的决策质量提升」，而不自动推翻它所依赖的底层机制——后者由独立文献支撑。
   One failure refutes only the claim that was tested. An effect-size failure refutes "this layer's
   operationalization produces a detectable improvement in decision quality"; it does not
   automatically refute the underlying mechanism, which rests on independent literature.
6. **六层栈整体是 E0。** 即使六层全部未触及阈值，也只说明这个表征未被推翻，不说明整合结构已被证实。
   The stack as a whole is E0. Even if no layer reaches its threshold, that means the representation
   has not been refuted — not that the integrative structure is confirmed.

---

## 三、如何提交一份能触发处置的报告 / Filing a Report That Can Trigger Disposition

最有价值的贡献**不是**加功能，而是提交证伪报告。一份足以触发上表处置的报告需要：

The most valuable contribution is **not** a feature; it is a falsification report. A report strong
enough to trigger disposition needs:

1. **指明对象**：哪一层（L1–L6）或哪条假设（H1–H18）。
   **Name the target**: which layer, or which hypothesis.
2. **对准预注册标准**：引用上表阈值的具体条款，并说明结果**如何**满足它。
   **Match the preregistered criterion**: quote the specific threshold and explain **how** the result
   satisfies it.
3. **给出可复核的数字**：效应量、p 值、统计功效、样本量与抽样方式。
   **Give checkable numbers**: effect size, p value, statistical power, sample size, sampling.
4. **交代数据可得性**与限制。
   **State data availability** and its restrictions.
5. **自评不确定性**：你本人最担心这份报告的哪一点。
   **Self-assess uncertainty**: what worries you most about your own report.

模板：[`.github/ISSUE_TEMPLATE/falsification_report.yml`](../.github/ISSUE_TEMPLATE/falsification_report.yml)。
报告不满足阈值时我们仍然会读，但按定义它不构成证伪——如实说明这一点比把它写成证伪更有用。

Template: `.github/ISSUE_TEMPLATE/falsification_report.yml`. Reports that do not meet the threshold are
still read, but by definition they are not falsifications — saying so plainly is more useful than
presenting them as such.

**核心行为期待：可以攻击理论，不可以攻击人。**

**Core behavioural expectation: attack the theory, not the person.**

---

后续阅读：[证据体系](evidence.md) · [路线图](roadmap.md) · [术语对照](glossary.md)

Further reading: [Evidence System](evidence.md) · [Roadmap](roadmap.md) · [Glossary](glossary.md)
