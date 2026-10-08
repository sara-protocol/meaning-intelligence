# 工具9 · 螺旋回环状态跟踪表
## Tool 9 — Spiral Loop Tracker

**出处 / Source**：正典附录 A · A.4 通用工具 · 工具9
*Canon Appendix A · A.4 General Tools · Tool 9*

> **编号提示 / Identifier note**：本工具的编号 `A.9` 与上方的章节名 `A.4` 不同源。正文中请写
> 「**工具9（螺旋回环状态跟踪表）**」，并同时标注 **附录 A.4 通用工具**这一章节。 / Always write
> **Tool 9 (Spiral Loop Tracker)**, together with the section name **Appendix A.4 General Tools**.

---

## 用途 / Purpose

**中文**　这是全尺度通用的**回环台账**：记录六层栈每完成一轮之后，落点相对上一轮移动了多少。
它不评价某一轮做得好不好，只回答两个可观测的问题——**这一轮的落点与上一轮同角度吗？半径变大了吗？**
以及**回环之间的间隔是否已经过快或过慢？** 正典把后一个问题写成 H6：螺旋速率过快或过慢均致危机。

**English**　This is the cross-scale **loop ledger**: it records how far the entry point moved relative to the
last cycle each time the six-layer stack closes a loop. It does not grade a cycle; it answers two observable
questions — **is this cycle's entry point at the same angle as the last, and is the radius larger?** — plus
**has the interval between loops become too fast or too slow?** The canon states the latter as H6: a spiral
rate that is too fast or too slow both lead to crisis.

---

## 适用尺度与频率 / Scale and Cadence

- **尺度 / Scale**：全尺度（个人／组织／城市／国家／人类）/ All scales
- **频率 / Cadence**：持续登记；每次回环闭合即追加一行，不补记、不回填
  / Continuous: append one row each time a loop closes; never backfill
- **单一数据源 / Single source of truth**：同一主体只维护**一张**跟踪表；多表并行会使回环编号失效
  / Keep **one** tracker per subject; parallel trackers invalidate loop numbering

---

## 关联六层 / Layers Served

| 层 Layer | 本表做什么 What this tracker does here |
|---|---|
| **L6 反思与审视递归** Recursive Reflection and Review | 主层：SA 螺旋上升（正典 7B.3）的回环台账；AZ 主动归零（7B.4）的落点记录 |
| **L5 方向选择** Direction Selection | 上溯：每轮的方向声明与偏离阈值触发情况，作为回环触发条件的依据 |
| **L1–L4** | 记录回环的**起点**（L1 的输入标准是否被改写）；不评价各层内部质量 |

**为什么以 L6 为主**：回环不是返工，而是**前提被改写后的重新进入**。若 L1 的输入标准没变，
这一轮即使产出很多，也不构成螺旋。 / **Why L6 leads**: a loop is not rework but **re-entry after premises
were rewritten**. If L1's input criteria did not change, a busy cycle is still not a spiral.

---

## 填写区 / Form

**主体 Subject**：`____________________`　**尺度 Scale**：`个人 / 组织 / 城市 / 国家 / 人类`

### 1. 回环台账 / Loop ledger（每次回环闭合追加一行 / append one row per closed loop）

| 回环 # Loop | 起止 Start–End | 本轮的核心问题 Core question | 角度：与上一轮是否同一问题 Same angle as last? | 半径：增大 / 不变 / 缩小 Radius | 螺旋深度 SD（增量）SD increment | 距上一轮的间隔 Interval since last | 归零方式 Zeroing used |
|---|---|---|---|---|---|---|---|
| `____` | `________` | `________________` | 是 / 否 Yes / No | 增大 / 不变 / 缩小 | `______` | `______` | 工具2 / 工具5 / 工具8 / 未归零 |
| `____` | `________` | `________________` | 是 / 否 | 增大 / 不变 / 缩小 | `______` | `______` | 工具2 / 工具5 / 工具8 / 未归零 |
| `____` | `________` | `________________` | 是 / 否 | 增大 / 不变 / 缩小 | `______` | `______` | 工具2 / 工具5 / 工具8 / 未归零 |
| `____` | `________` | `________________` | 是 / 否 | 增大 / 不变 / 缩小 | `______` | `______` | 工具2 / 工具5 / 工具8 / 未归零 |
| `____` | `________` | `________________` | 是 / 否 | 增大 / 不变 / 缩小 | `______` | `______` | 工具2 / 工具5 / 工具8 / 未归零 |

> **几何约定（正典给出）**：归零后的落点 L1′ 与原点 L1 处于**同一角度、更大半径**。
> **完全重合**＝该轮未产生意义增量；**角度改变**＝这不是回环，而是换了问题，应新开一行并注明。

### 2. 回环速率记录 / Loop rate record（对应 H6：过快或过慢均致危机）

| 项 Item | 填写 Fill in |
|---|---|
| 相邻两次回环的最短间隔 Shortest interval between loops | `______` |
| 相邻两次回环的最长间隔 Longest interval between loops | `______` |
| 是否存在「同一问题在极短时间内被反复归零」Does one question get re-zeroed very often | 是 / 否 |
| 是否存在「长期未发生任何回环」Are there long stretches with no loop at all | 是 / 否 |
| 上述两种情形的具体条目编号 Rows involved | `____________________` |

> 正典未给出「过快」「过慢」的数值分界；本表**只做记录**，请勿自行填入分数线。
> / The canon gives no numerical cut for "too fast" or "too slow"; **record only**.

### 3. 落点质量检查 / Entry-point quality check（每轮填一次 / once per loop）

- **本轮是否改写了 L1 的输入标准？** / Did this loop rewrite L1's input criteria？`是 / 否`
- 若「是」，改写内容 / If yes, what changed：`____________________________________`
- 若「否」，本轮是否为**返工**而非螺旋 / If no, was this rework rather than a spiral：`是 / 否`
- **本轮依赖的假设及其证伪条件** / Assumptions and falsification conditions：`____________________________`

### 4. 未归零追踪 / No-zeroing tracking（对应 H14）

| 项 Item | 填写 Fill in |
|---|---|
| 距上一次归零已过去多久 Time since last zeroing | `______` |
| 期间是否出现僵化迹象（决策重复、拒绝新证据）Signs of ossification | 是 / 否 / 无法判断 |
| 若判断为「是」，具体证据 If yes, the evidence | `____________________________` |

### 5. 本表自检 / Tracker-level check
- [ ] 每一行都是在回环**闭合时**登记的，没有事后补记 / Every row was logged at loop closure, not backfilled
- [ ] 未归零的轮次被如实标为「未归零」，没有被美化 / Cycles without zeroing are labelled honestly
- [ ] 落点与上一轮完全重合的轮次已写明原因 / Any exactly coinciding cycle carries a written reason
- [ ] 回环编号未被重排 / Loop numbers were never rearranged

---

## 判读标准 / How to read the result

**中文**
- **正典给出几何判读**：同角度、更大半径＝螺旋；**完全重合**＝未产生意义增量。
- **正典给出速率判读**：**H6——螺旋速率过快或过慢均致危机**（倒 U 型）。两端都不是好状态。
- **偏离阈值（正典给出，用于 L5 上溯）**：一级修正 <10%、二级修正 10–30%、三级修正 >30%。
- **L6 失败阈值（正典给出）**：若出现 **RCT 无显著差异（d<0.3）**，归零类动作**放弃有效性主张，
  仅保留为操作规程**。
- **正典未给出阈值**：回环间隔的数值分界、SD 的健康区间、多少次未归零即构成僵化——**正典全部未给出**。
  **本表不设判读线，只做记录与纵向比对。**

**English**
- **Canon geometry**: same angle with a larger radius is a spiral; **exact coincidence** means no increment.
- **Canon rate reading**: **H6 — a rate too fast or too slow both lead to crisis** (inverted-U).
- **Deviation thresholds (canon, for the L5 look-back)**: level-one <10%, level-two 10–30%, level-three >30%.
- **L6 failure threshold (canon)**: on **no significant difference in the RCT (d<0.3)**, zeroing-type
  actions **drop the efficacy claim and remain procedural only**.
- **No threshold in the canon** for interval cuts, a healthy SD range, or how many unzeroed cycles constitute
  ossification. **Record and compare; read no line.**

---

## 失败即删的提示 / If Falsified, Revise or Withdraw

1. **H12（归零防僵化）被证伪** ⇒ 「归零后的半径应增大」这一读法失效，第 3 节应删除。
   / **H12 falsified** ⇒ the "radius should grow after zeroing" reading fails; delete §3.
2. **H14（无归零-僵化）被证伪** ⇒ 第 4 节失去预测意义，应降级为描述性备注。
   / **H14 falsified** ⇒ §4 loses predictive meaning; demote it to a descriptive note.
3. **H6（螺旋速率倒 U 型）被证伪** ⇒ 第 2 节整节删除，本表只保留几何与台账功能。
   / **H6 falsified** ⇒ delete §2 entirely; the tracker keeps only the ledger and geometry.
4. **H13（元认知-判断质量）被证伪** ⇒ 第 3 节的「改写 L1 输入标准」不再被读作判断质量改善的依据。
   / **H13 falsified** ⇒ §3's L1 rewrite is no longer read as evidence of better judgment.
5. 若 L6 触及阈值（RCT，d<0.3），本表按
   [`../docs/failure-matrix.md`](../docs/failure-matrix.md) 保留为规程，不再主张有效性。

---

## 边界 / Boundaries

- **不能替代专业判断**：不替代项目管理、审计、统计或其他专业判断；它不判定一轮工作是否合格。
  **Does not replace professional judgment** — project management, audit, statistics; it does not certify a cycle.
- **不承诺正确答案**：本表不告诉你「应该多久回环一次」，也不承诺回环必然带来改进。
  **Promises no correct answer**; it does not say how often to loop, nor that looping improves anything.
- **不适用于无主体系统**：纯物理系统不适用。
  **Not applicable to subject-less systems.**
- **文化敏感性**：「一轮」的边界在不同文化中不同（学年、财年、任期、节庆），须就地定义并写明。
  **Cultural sensitivity**: what counts as a "cycle" varies (school year, fiscal year, term, festival);
  define it locally and write it down.
- **过度元认知可致决策瘫痪**：当登记回环本身开始取代推进工作，即已达此边界——应暂停登记一个周期。
  **Excessive metacognition can cause decision paralysis**: when logging loops displaces the work, pause
  logging for one cycle.

---

相关 / Related：[工具3 生命叙事螺旋图](03-life-narrative-spiral.md) ·
[工具2 个人意义归零协议](02-personal-zeroing-protocol.md) ·
[工具5 组织意义归零协议（战略版）](05-organizational-zeroing-protocol.md) ·
[工具10 归零安全检查清单](10-zeroing-safety-checklist.md) ·
[术语对照](../docs/glossary.md)
