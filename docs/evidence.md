# 证据体系 / The Evidence System

> 这份文档回答一个问题：**说某一层是「E1」到底意味着什么，以及这个标注为什么不能当作质量评分来读？**
> This document answers one question: **what does it actually mean to label a layer "E1", and why must that label not be read as a quality score?**

**当前判据以 V7.0 正典表 I.2 为准。** 本项目早期文档曾把 E3 写成“在新数据上预测正确”、把 E6 写成“框架外领域独立确认”；这两条不是 V7.0 定义，已废止，不作为现行评级依据。

**The current criteria follow V7.0 Canon Table I.2.** Earlier project documents described E3 as correct prediction on new data and E6 as confirmation outside the framework. Those were not the V7.0 definitions and are retired.

---

## 一、E0–E6：七级定义 / E0–E6: Seven Levels

证据等级回答的不是「这个想法好不好」，而是**「关于它，我们目前知道了什么」**。级别描述检验状态，不是可信度百分比。

| 等级 | 名称 / Name | V7.0 正典含义 / Canon meaning |
|---|---|---|
| **E0** | 概念 / Conceptual | 理论构念已定义。 / The theoretical construct is defined. |
| **E1** | 形式化 / Formalized | 已建立数学模型。 / A mathematical model has been established. |
| **E2** | 操作化 / Operationalized | 已有测量工具，信效度验证中。 / A measurement instrument exists; reliability and validity are under validation. |
| **E3** | 预测性 / Predictive | 有预注册假设，数据收集中。 / A preregistered hypothesis exists and data collection is under way. |
| **E4** | 复制 / Replicated | 独立实验室复现结果。 / Results have been replicated by an independent laboratory. |
| **E5** | 证伪或存活 / Falsified or Survived | 预注册证伪标准已检验。 / The preregistered falsification criterion has been tested. |
| **E6** | 外部验证 / Externally Validated | 跨情境、跨文化、跨时间泛化。 / Generalization across contexts, cultures, and time. |

两个容易读错的地方：

- **E3 不等于已经做出成功预测。** 在 V7.0 中，它表示预注册假设已进入数据收集阶段；不能把它当作“预测已验证”的缩写。
  **E3 does not mean a successful prediction has already been made.** In V7.0 it marks preregistration plus active data collection.
- **E5 是双出口。** 它既包括「被证伪」，也包括「通过预注册检验而存活」。被标为 E5 且已证伪是一项成果，不是丑闻。
  **E5 has two exits:** falsified, or survived a preregistered test. A falsified E5 claim is a result, not a scandal.

---

## 二、六层证据等级 / Evidence Levels of the Engineering Layers

六层栈本身是**本项目提出的工程扩展，E0**，不是 V7.0 正典的固定层次。下表区分“本框架操作化”与“所关联的正典假设或外部机制”。

| 层 Layer | 本框架内的操作化 / Engineering operationalization | 正典关联或机制 / Canon link or mechanism | 当前状态 / Current state |
|---|---|---|---|
| **L1 减负** / Cognitive Load Reduction | E1 | 外部机制待按 V7.0 逐条核验 | 本框架 E1；机制待核验 |
| **L2 可体验** / Experiential Rendering | E1 | 外部机制待按 V7.0 逐条核验 | 本框架 E1；机制待核验 |
| **L3 意义生成** / Meaning Generation | E0–E1 | H2（E0）；3.2 三维度、8.1 光谱带 | 本框架 E0–E1；机制 E0 |
| **L4 价值评估** / Value Assessment | E2（工具）/ E1（模型） | H10（E2）；E0–E6 标注规程 | 本框架 E2（工具）/ E1（模型） |
| **L5 方向选择** / Direction Selection | E1 | H7 / H8（均 E1） | 本框架 E1；关联 H7/H8（E1） |
| **L6 反思与审视递归** / Recursive Reflection and Review | E2 | H12 / H13（E2）；H14（E1） | 本框架 E2；关联 H12/H13（E2）、H14（E1） |
| **六层栈本身** / The stack itself | **E0** | 非正典结构 | 工程整合结构，未经独立检验 |

### 为什么 L1 / L2 的机制不再标 E3–E4

早期文档引用“认知负荷、受控语言、多媒体学习”的外部研究后直接标注 E3–E4，但没有逐条记录预注册状态、独立实验室复现或跨情境/跨文化/跨时间泛化证据。本次迭代**没有找到足以支持该等级的项目内证据链**，因此降为“待核验”，而不是继续沿用无法复核的标签。

这不是断言外部机制无效，而是承认：**机制文献的成熟度不能自动转移给本项目的六层操作化，也不能在缺少项目内审计记录时直接授予 V7.0 等级。**

---

## 三、为什么必须区分两个对象 / Why Two Objects Must Be Kept Apart

| 问题 Question | 应检查什么 What to inspect |
|---|---|
| 「结构化压缩能降低认知负荷吗？」<br>"Can structured compression reduce cognitive load?" | 外部机制研究；需逐条核验预注册、复现与泛化条件。 |
| 「L1 这套组合能否提升本项目任务中的决策质量？」<br>"Does the L1 package improve decision quality in this project's tasks?" | 本框架操作化；当前 E1，需预注册对照检验。 |
| 「方向、价值、边界能否被独立测量？」<br>"Can direction, value, and boundary be measured independently?" | 正典 H2；其证伪条件与 L3 工程界面不是同一回事。 |
| 「递归审视能否提高纠错率？」<br>"Does recursive review improve error correction?" | L6 的工程草案；须先预注册，不能替代 H13 的元认知 RCT。 |

**机制成熟不能转移给工程层。** 把外部研究、正典假设和工程操作化混为一个等级，会让“有文献”看起来像“本栈已证实”。

**Mechanism maturity cannot be transferred to an engineering layer.** Conflating external literature, canonical hypotheses, and engineering operationalizations makes "has literature" look like "this stack is confirmed."

---

## 四、六层栈本身是 E0 / The Stack Itself Is E0

- `config.json` 把它数据化、动画把它可视化、页面让它可操作——**这些都不提高它的证据等级**。
  工程实现改变的是它**可被体验**的程度，不是它**已被检验**的程度。
- 它的分层方式**可能不是最优切分**。若出现更简洁且解释力更强的切分，应当**替换**它，而不是为它辩护。
- 正典的三层次已在第 8 章重释为连续光谱带；六层栈不得被描述为正典层次体系。

---

## 五、证据等级不是质量评价 / An Evidence Level Is Not a Quality Judgment

| 常见误读 Misreading | 实际含义 What it actually means |
|---|---|
| 「E0 等于没用。」 | E0 表示构念已定义；定义清楚是进展，但不是预测证据。 |
| 「E3 表示预测已经成功。」 | V7.0 的 E3 是预注册假设 + 数据收集中，不是成功预测。 |
| 「E2 比 E1 好，所以应该尽快升级。」 | 等级描述知识状态，不是进度条；不得为升级而放宽标准。 |
| 「机制是 E4，所以这一层是 E4。」 | 机制与工程操作化是不同主张，必须分别评级。 |
| 「E5 说明很可靠。」 | E5 包含“已证伪”出口，衡量检验严肃程度而非正确程度。 |

一句话概括：**证据等级是知识状态的标注，不是主张的质量评分。**

---

后续阅读：[理论失败矩阵](failure-matrix.md) · [术语对照](glossary.md) · [系统架构](architecture.md)
