# 路线图 / Roadmap

> 这份文档回答一个问题：**本项目在整个正典路线图中处于什么位置，当前版本交付了什么，下一步做什么？**
> This document answers one question: **where does this repository sit in the canon's roadmap, what does the current release deliver, and what comes next?**

---

## 一、本仓库的定位 / Where This Repository Sits

**本仓库定位在正典路线图的「第一阶段：认知普及与工具孵化」。**

白皮书与 MSI 演示系统都属于第一阶段的产品形态：一本专著与一批**个人版工具**。
本仓库不主张自己已经进入第二至第五阶段，也不把面向组织的、面向城市的、面向文明的部署
写成已经发生的事实。下面第三节的「近期待办」全部在第一阶段的范围内。

**This repository sits in the canon roadmap's first phase: cognitive popularization and tool
incubation.** The white paper and the MSI demonstration system are both first-phase product forms —
a monograph and a set of **individual-scale tools**. This repository does not claim to have entered
phases two through five, and it does not describe organizational, urban, or civilizational deployment
as though it had already happened. Every item in the near-term list below stays inside phase one.

---

## 二、五阶段路线图 / The Five Phases

| 阶段 Phase | 时间 Time | 主题 Theme | 主要产出 Main outputs | 六层的主要形态 Primary forms of the six layers |
|---|---|---|---|---|
| 第一阶段 / Phase 1 | 当下–2030<br>now–2030 | 认知普及与工具孵化<br>Cognitive popularization and tool incubation | 专著；个人版工具<br>Monograph; individual-scale tools | 个人阅读降维、可丢弃微应用（L1–L2）；意义自检、证据标注（L3–L4）；年度归零、螺旋追踪（L5–L6） |
| 第二阶段 / Phase 2 | 2030–2045 | 组织应用与制度嵌入<br>Organizational application and institutional embedding | 组织级评估与治理流程<br>Organizational assessment and governance processes | 汇报与文档受控化、仪表盘；使命合法性评估；使命压力测试、方向重置 |
| 第三阶段 / Phase 3 | 2045–2060 | 城市与区域意义治理<br>Urban and regional meaning governance | 城市尺度公共界面与集体记忆评估<br>Urban-scale public interfaces and collective-memory assessment | 公共信息可读化、参与式界面；地方感与集体记忆评估；城市归零工作坊 |
| 第四阶段 / Phase 4 | 2060–2080 | 国家与文明级 MI 架构<br>National and civilizational MI architecture | 跨尺度政策与制度一致性框架<br>Cross-scale policy and institutional consistency frameworks | 政策文本可读化；制度意义一致性评估；跨尺度方向校准（正典工具 A.9 跨尺度） |
| 第五阶段 / Phase 5 | 2080+ | 人类级意义智能与文明自觉<br>Humanity-scale meaning intelligence and civilizational self-awareness | 文明级方向治理与归零-螺旋机制<br>Civilization-scale direction governance and zeroing-spiral mechanisms | 文明叙事降维；物种责任与文明方向评估；文明级归零-螺旋治理 |

**读表须知：** 阶段二至阶段五的主题来自正典路线图；表中“六层主要形态”来自本项目的白皮书表 4，是工程扩展的应用设想，不是正典既成事实。它们的作用是**标明第一阶段不是终点**，而不是承诺时间表必然兑现。
六层在五个尺度上形态不同，是因为正典公理三指出：多尺度意义不可通约，协调不是加权求和。

**How to read the table:** phase themes come from the canon roadmap; the “forms of the six layers” column comes from this project's white paper Table 4 and is an engineering-extension scenario, not a canonical fact. It shows that **phase one is not the endpoint**, not that the schedule will be met. The layers take different forms at different scales because Canon Axiom Three holds that multi-scale meanings are incommensurable and coordination is not weighted summation.

---

## 三、当前版本 0.2.0 / Current Release 0.2.0

**已完成 / Delivered:**

1. **六层应用栈首次公开**：L1 减负 / L2 可体验 / L3 意义生成 / L4 价值评估 / L5 方向选择 /
   L6 反思与审视递归，并给出三带划分（界面带 L1–L2、加工带 L3–L4、元带 L5–L6）。
   The six-layer stack published for the first time, together with the three-band partition.
2. **中英双语白皮书 v1.1**：正文、排版、插图均由脚本生成（[`whitepaper/build_whitepaper.py`](../whitepaper/build_whitepaper.py)、
   [`whitepaper/docx_style.py`](../whitepaper/docx_style.py)、[`whitepaper/make_figures.py`](../whitepaper/make_figures.py)），
   发布产物在 [`whitepaper/dist/`](../whitepaper/dist)。
   Bilingual white paper v1.1, generated end to end by scripts.
3. **MSI 六层演示系统**：Manim **八幕、43 秒**动画（[`msi/scenes/`](../msi/scenes)；实测时间轴末点 43.433 秒）＋ 单文件交互页
   [`msi/meaning_intelligence.html`](../msi/meaning_intelligence.html)，含时间轴联动、六层导航与实测/预算时间轴的分支处理（见
   [architecture.md](architecture.md)）。
   The MSI eight-act, 43-second demonstration system: Manim scenes plus a single-file interactive page with
   timeline linking, six-layer navigation, and explicit measured/planned timeline branching (measured end: 43.433 s).
4. **V7.0 E0–E6 定义、正典五模块失败矩阵、H1–H18 与六层工程证伪草案分层归档**：正典阈值与工程草案不再混用（见 [failure-matrix.md](failure-matrix.md)），并配套
   [`falsification_report.yml`](../.github/ISSUE_TEMPLATE/falsification_report.yml) 证伪报告模板。
   V7.0 evidence definitions, the canon's five-module matrix, H1–H18, and engineering drafts are stored separately, with a falsification report template.
5. **本目录（`docs/`）**：架构、证据体系、失败矩阵、路线图、术语五份说明性文档。
   This documentation layer.

**明确未主张 / Explicitly not claimed:**

- 本版本**不主张任何模块达到 E4 及以上**；各模块当前等级见 [evidence.md](evidence.md)。
  No module is claimed at E4 or above.
- **六层栈本身是 E0（概念）**，未经独立检验。把它数据化、动画化、可操作化，
  **都不提高**它的证据等级。
  The stack itself is E0 and untested; implementing it does not raise its level.
- 18 张假设卡片 H1–H18 及其预注册证伪标准随正典发布；本仓库承载**引用与报告流程**，
  不复述全部标准，也不改写其中任何一条。
  The 18 hypothesis cards and their preregistered criteria ship with the canon; this repository
  carries references and the reporting workflow, not restatements or revisions.

---

## 四、0.3.0 未发布工程增补（2026-11-27）/ Unreleased 0.3.0 Engineering Addendum (2026-11-27)

本节是 **2026-10-08 发布的 v0.2.0 之后**的工程增补，不回写 v0.2.0 的原始交付范围。
研究系统仍是 **v0.2.0**；Canon V7.0、操作栈 2.0/E0 与白皮书 v1.1（22 页 / 9 表 / 3 图）不变。

- **SDK 0.3.0（未发布工程版本）**：[`pr_sdk_v2/`](../pr_sdk_v2) 提供配置读取、六层启发式与假说判定；草稿、缺数据、条件不足或未实现判定返回 `INCONCLUSIVE`。仅已实现的 L3-H1 名义 alpha 阈值可返回 `FALSIFIED` / `NOT_FALSIFIED`，二者均不授予实证等级，后者也不等于已证实。
- **工程假说与门槛**：[`hypotheses.yaml`](../hypotheses.yaml)、[`tools/verify_final.py`](../tools/verify_final.py)（含 `--negative`）与 SDK 检查进入 CI。
- **浏览器本地审计/助手**：[`audit/index.html`](../audit/index.html) 支持用户手动填写方向/价值/边界并生成启发式报告，以 `localStorage` 保存历史，并可选用 GitHub Models / 本地 Ollama 双引擎拆解；[`audit/qr.html`](../audit/qr.html) 是二维码入口。
- **Windows token 诊断**：[`check-token.bat`](../check-token.bat) 只检查桌面 token 文件格式，不输出完整 token，也不证明鉴权或模型可用。
- **本地智能体与公共只读 Web MCP**：[`meaning-agent/`](../meaning-agent) 与 [`web-mcp/`](../web-mcp) 属于 0.2.0 之后的本地工具增补；后者需要 Bearer 鉴权，本仓库不提供生产端点或凭据。

`registered` 只表示预注册元数据存在，`evidence_ceiling` 是设计上限，**不是已取得证据**。
SDK、审计/助手、Meaning Agent、Web MCP 及代码检查**都不是实证验证**；后续仍需按预注册设计收集独立数据。
自定义域主页 <https://msi.gojj.ccwu.cc/> 与上游 GitHub Pages 入口
<https://sara-protocol.github.io/meaning-intelligence/> 只是发布角色，本文不声称已完成部署、可访问或已产生下载。

This section records engineering additions **after the v0.2.0 release of 2026-10-08** without rewriting that
release's original scope. The research system remains **v0.2.0**; Canon V7.0, operational stack 2.0/E0, and
white paper v1.1 (22 pages / 9 tables / 3 figures) are unchanged.

- **SDK 0.3.0 (unreleased engineering):** [`pr_sdk_v2/`](../pr_sdk_v2) adds config loading, six-layer heuristics,
  and hypothesis verdicts. Drafts, missing data, unmet conditions, and unimplemented rules return `INCONCLUSIVE`;
  only the implemented L3-H1 nominal-alpha threshold returns `FALSIFIED` / `NOT_FALSIFIED`. Neither grants an
  empirical evidence level, and the latter is not confirmation.
- **Engineering registry and gates:** [`hypotheses.yaml`](../hypotheses.yaml),
  [`tools/verify_final.py`](../tools/verify_final.py) (including `--negative`), and SDK checks run in CI.
- **Browser-local audit/assistant:** [`audit/index.html`](../audit/index.html) lets users enter direction/value/boundary,
  generates heuristic reports, saves history in `localStorage`, and offers optional GitHub Models / local Ollama decomposition;
  [`audit/qr.html`](../audit/qr.html) is the QR entry.
- **Windows token diagnostic:** [`check-token.bat`](../check-token.bat) checks only the desktop token-file format,
  without printing the full token or proving authentication/model availability.
- **Local agent and public read-only Web MCP:** [`meaning-agent/`](../meaning-agent) and
  [`web-mcp/`](../web-mcp) are local-tooling additions after 0.2.0. The latter requires Bearer authentication;
  this repository provides no production endpoint or credentials.

`registered` means only that preregistration metadata exists; `evidence_ceiling` is a design ceiling,
**not achieved evidence**. The SDK, audit/assistant, Meaning Agent, Web MCP, and code checks are **not empirical
validation**; independent data still require preregistered study designs. The custom-domain homepage
<https://msi.gojj.ccwu.cc/> and upstream GitHub Pages entry
<https://sara-protocol.github.io/meaning-intelligence/> are publication roles, not claims here of completed
deployment, availability, or downloads.

---

## 五、近期待办 / Near-Term Work

分三类。这个分类不是进度管理，而是**承诺管理**：正典假设按已发布阈值处置；工程草案必须先预注册；设计产物本身不是可证伪命题。

Three categories distinguish commitment: canonical hypotheses use published thresholds; engineering drafts require preregistration; design outputs are not themselves falsifiable claims.

| # | 工作 Work | 类别 Category | 完成判据 / 证伪条件 Criterion |
|---|---|---|---|
| 1 | L1 操作化的对照检验：降维前后的决策质量是否出现可察觉差异<br>Controlled test of L1 | **工程草案**<br>**Engineering draft** | 先预注册样本、检验与处置；若 d&lt;0.3，重设压缩比或放弃字数硬限 |
| 2 | L2 交互组与静态组的对照：结构回忆是否有显著差异<br>Interactive vs. static groups | **工程草案**<br>**Engineering draft** | 先预注册迁移任务；若无显著差异，L2 降为可选增强 |
| 3 | L3 三维度的独立可评分性：方向/价值/边界能否被独立评分<br>Can direction, value, and boundary be scored independently? | **正典 H2**<br>**Canon H2** | 若单一维度解释意义判断方差 &gt;90%，接受 H2 被证伪并重构结构模型 |
| 4 | L4 测量工具的信效度验证<br>Reliability and validity of L4 instruments | **正典 H10 + 工程草案**<br>**Canon H10 + draft** | H10 按 2031 年信度 &gt;0.7 阈值；L4 标注一致性另作工程预注册 |
| 5 | L6 的元认知 RCT<br>L6 metacognitive RCT | **正典 H13**<br>**Canon H13** | 若 RCT 无显著差异（d&lt;0.3，p&gt;0.05），按 H13 处置；不自动推翻 H12/H14 |
| 6 | L5 跨尺度一致性与生存期的观测设计<br>Cross-scale consistency and survival | **正典 H7/H8**<br>**Canon H7/H8** | 若出现「长期背离却无危机」，标记 H8 被证伪并重估五尺度模型 |
| 7 | 六层切分本身的替代方案比较<br>Comparing alternative partitions | **待检验设计**<br>**Design** | 若出现更简洁且解释力更强的切分，**替换**六层栈，而不是为它辩护 |
| 8 | 各层操作化指标的边界条件与混淆清单<br>Boundary conditions and confounds | **待检验设计**<br>**Design** | 按 [CONTRIBUTING.md](../CONTRIBUTING.md) 第 3 节提交：目标构念、测量程序、混淆、最小可判别效应 |
| 9 | 页面与白皮书之间的一致性自动检查<br>Automated consistency checking | **已实现**<br>**Implemented** | 层名、证据等级、来源边界与阈值在 `msi/config.json`、白皮书脚本和 `docs/` 间一致；由 `tools/verify_consistency.py` 检查 |

**A note on categories:** canonical hypotheses already have published thresholds. Engineering drafts do not become deletion criteria until their sample, statistical rule, and disposition are preregistered. Items 7–9 produce designs or verification tooling, not empirical claims.

---

## 六、版本号的含义 / What the Version Number Means

`0.x` 表示六层工程栈与操作化**仍在演进**；V7.0 的 E0–E6 定义与 H1–H18 阈值不随工程版本静默改写。任何工程模块因预注册检验被标记或删除时，会在 [`CHANGELOG.md`](../CHANGELOG.md) 中**显式说明**。

`0.x` means the six-layer engineering stack and its operationalizations are **still evolving**. V7.0 evidence definitions and H1–H18 thresholds are not silently rewritten with engineering releases. Marking or removing an engineering module after a preregistered test is recorded **explicitly** in the changelog.

---

后续阅读：[系统架构](architecture.md) · [证据体系](evidence.md) · [理论失败矩阵](failure-matrix.md)

Further reading: [System Architecture](architecture.md) · [Evidence System](evidence.md) ·
[Theory Failure Matrix](failure-matrix.md)
