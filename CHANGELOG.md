# 更新日志 / Changelog

本文件记录本仓库的对外可见变更。

本文件遵循 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/)；版本号遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/spec/v2.0.0.html)。

This file records externally visible changes to this repository.

It follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

关于版本号的一点说明：本项目的版本号同时标记**文档与工程模块**的状态。`0.x` 阶段的含义是：六层工程栈与操作化仍在演进；V7.0 的 E0–E6 定义与 H1–H18 阈值不随工程版本静默改写。工程模块只有经过预注册检验才可正式标记或删除，这类变更会在下面的“变更”段落中显式说明。

A note on version numbers: releases mark the state of both documents and engineering modules. `0.x` means the six-layer engineering stack and its operationalizations are still evolving. V7.0 evidence definitions and H1–H18 thresholds are not silently rewritten with engineering releases. An engineering module is marked or removed only after a preregistered test, and such changes are stated explicitly below.

---

## [Unreleased]

### 新增 / Added

- **SDK 0.3.0 工程集成（2026-11-27，未发布）。** [`pr_sdk_v2/`](pr_sdk_v2/) 增加 `meaning_intelligence` Python 包与 `mi` CLI，覆盖配置读取、六层启发式函数和假说判定；草稿、缺数据、条件不足或尚未实现的评估返回 `INCONCLUSIVE`，已实现的 L3-H1 名义 alpha 阈值可返回 `FALSIFIED` / `NOT_FALSIFIED`，后者不等于已证实。
- **SDK 0.3.0 engineering integration (2026-11-27, unreleased).** [`pr_sdk_v2/`](pr_sdk_v2/) adds the `meaning_intelligence` package and `mi` CLI for config loading, six-layer heuristics, and hypothesis verdicts. Drafts, missing data, unmet conditions, and unevaluated rules return `INCONCLUSIVE`; the implemented L3-H1 nominal-alpha threshold can return `FALSIFIED` / `NOT_FALSIFIED`, and the latter does not mean confirmed.
- **v0.3.0 配置、假说注册与语义门槛。** 接入 [`hypotheses.yaml`](hypotheses.yaml)、[`tools/verify_final.py`](tools/verify_final.py) 及其 `--negative` 用例；CI 增加最终门槛、负向用例和 `PYTHONPATH=pr_sdk_v2 python pr_sdk_v2/test_pr.py`。
- **v0.3.0 configuration, hypothesis registry, and semantic gates.** Integrates [`hypotheses.yaml`](hypotheses.yaml), [`tools/verify_final.py`](tools/verify_final.py), and its `--negative` cases; CI adds the final gates, negative cases, and `PYTHONPATH=pr_sdk_v2 python pr_sdk_v2/test_pr.py`.
- **浏览器本地审计/助手。** [`audit/index.html`](audit/index.html) 提供手动启发式自检、`localStorage` 历史，以及 GitHub Models / 本地 Ollama 双引擎可选拆解；[`audit/qr.html`](audit/qr.html) 提供二维码入口，[`check-token.bat`](check-token.bat) 只诊断桌面 token 文件格式，不输出完整 token。
- **Browser-local audit/assistant.** [`audit/index.html`](audit/index.html) adds manual heuristic review, `localStorage` history, and optional GitHub Models / local Ollama decomposition; [`audit/qr.html`](audit/qr.html) is the QR entry, and [`check-token.bat`](check-token.bat) diagnoses only the desktop token-file format without printing the full token.
- **AI 访问者提示。** 中英文 README 在开头保留同一提示：AI 评估者可先回答 `agent-network/protocol/ai-visitor-questions.json` 的三个问题。
- **AI-visitor notice.** Both READMEs retain the opening notice inviting AI evaluators to answer the three questions in `agent-network/protocol/ai-visitor-questions.json` first.

- **正典来源审计 `docs/canon-audit.md`。** 登记 KDP 定稿02 V7 主正典与英文母本的 SHA-256、权威顺序、重复副本、上游截断/冲突和缺失插图占位；正典原件未修改。
- **Canon source audit `docs/canon-audit.md`.** Records SHA-256 hashes, authority order, duplicate copies, upstream truncation/conflicts, and missing-figure placeholders for the KDP V7 primary canon and English mother; canon originals were not modified.
- **语义一致性门槛。** `tools/verify_consistency.py` 现在检查工程扩展来源、六层证据、正典假设映射、证伪范围、V7 E3/E6 判据、来源哈希，并从任意工作目录运行。
- **Semantic consistency gates.** `tools/verify_consistency.py` now checks engineering-extension provenance, layer evidence, canon-hypothesis mappings, falsifier scope, V7 E3/E6 criteria, and source hashes, and runs from any working directory.

- **Issue 分诊与定时维护自动化。** 两个工作流，权限被刻意收窄，治理规则见 [docs/automation.md](docs/automation.md)：
  - `triage.yml`：issue 打开时检查证伪报告的必备字段是否齐全（**缺失不等于不成立**，只是提示补充）、依据固定字段名机械打标签；若配置了 `LLM_API_KEY`，额外生成一份自标为「机器草稿」的归类说明。
  - `maintenance.yml`：每周一汇总仓库状态；把超过 14 天无人回复的证伪报告**升级**给维护者（加 `needs-maintainer-review` 标签），而不是清理它们。
  - **本仓库不自动关闭任何 issue**（`days-before-issue-close: -1`）。对一个以可失败性为承诺的仓库，静默关闭一条未回复的批评是最坏的自动化。
- **Issue triage and scheduled maintenance automation.** Two workflows with deliberately narrow permissions; governance rules in [docs/automation.md](docs/automation.md). The repository **never auto-closes issues** — silently closing an unanswered criticism would be the worst possible automation for a repository whose commitment is falsifiability.
- **公开发布落地页 `index.html`。** 单文件、**零外部资源**——没有 CDN、没有字体外链、没有统计脚本，离线打开亦完整可用。含六层栈、证据等级与失败矩阵、六层截图、参与方式。配套 `.nojekyll`，可直接用 GitHub Pages（Source 设为 `main` / `(root)`）发布。
- **Landing page `index.html`.** A single file with **zero external resources** — no CDN, no web fonts, no analytics; it works fully offline.
- **`toolkit/`：十份可填写的实践工具模板**，对应正典附录 A 的工具 1–10（意义自检卡、个人/组织归零协议、生命叙事螺旋图、使命压力测试、组织监测仪表盘、城市普查问卷、城市归零工作坊、螺旋回环跟踪表、归零安全检查清单）。每份含出处、用途、适用尺度与频率、关联层级、可填写区、判读标准、失败即删提示与边界。
- **`toolkit/`: ten fillable practice templates** corresponding to canon Appendix A tools 1–10, each with provenance, purpose, scale and cadence, the layer it serves, a fillable form, reading criteria, its falsification trigger, and boundaries.
- `tools/verify_issue_forms.py`：按 GitHub 官方 schema 校验 issue 表单结构，已接入 CI 作为独立步骤。它守的是 YAML 解析管不到的约束（`type` 取值、`id` 唯一性、markdown 元素不得带 `id`、dropdown 必须有 `options` 等）——**违反这些时 GitHub 不报错，只会让表单静默失效**。
- `tools/verify_issue_forms.py`: validates issue form structure against GitHub's official schema, wired into CI as its own step. It catches constraints YAML parsing cannot — which GitHub enforces silently by dropping the form rather than erroring.
- `tools/publish.py` 新增标签自动创建（`ensure_labels()`）。GitHub 对不存在的标签是静默丢弃的，不建会让分诊无声失效。
- `tools/publish.py` now creates the labels the workflows depend on. GitHub drops unknown labels silently, which would make triage fail without any error.

### 证据与版本边界 / Evidence and Version Boundaries

- **以上 SDK、审计/助手、Meaning Agent 与 Web MCP 增补均不是实证验证。** `registered` 仅表示预注册元数据存在，`evidence_ceiling` 是设计上限，不是已取得证据；代码检查通过也不提升证据等级。
- **None of the SDK, audit/assistant, Meaning Agent, or Web MCP additions is empirical validation.** `registered` means preregistration metadata exists; `evidence_ceiling` is a design ceiling, not achieved evidence. Passing code checks does not raise evidence levels.
- **研究系统仍为 v0.2.0（2026-10-08）**，Canon V7.0、操作栈 2.0/E0 与白皮书 v1.1（22 页 / 9 表 / 3 图）的范围不变；0.3.0 只是未发布工程组件版本。
- **The research system remains v0.2.0 (2026-10-08).** Canon V7.0, operational stack 2.0/E0, and white paper v1.1 (22 pages / 9 tables / 3 figures) are unchanged; 0.3.0 is an unreleased engineering-component version only.

### 变更 / Changed

- **MSI 时长口径补齐。** 当前演示明确为八幕、43 秒；`msi/timeline.json` 的实测末点为 43.433 秒，版本元数据按 43 秒记载。
- **MSI runtime clarified.** The current demo is documented as eight acts and 43 seconds; the measured timeline ends at 43.433 seconds, while version metadata records 43 seconds.

- **来源边界纠正。** 六层栈与三带明确为本项目 E0 工程扩展，不是正典固定层次；`anchor` 改为“正典概念关联”。正典 H1–H18、附录 D.7 与工程 MI-C / L1–L6 草案分开引用。
- **Provenance corrected.** The six-layer stack and three bands are now explicitly an E0 engineering extension, not a fixed canon hierarchy; `anchor` is a canon concept link. Canon H1–H18 and Appendix D.7 are cited separately from engineering MI-C / L1–L6 drafts.
- **V7 证据与失败规则对齐。** E3 恢复为“有预注册假设，数据收集中”，E4 恢复为“独立实验室复现”，E6 恢复为“跨情境、跨文化、跨时间泛化”；L1/L2 外部机制改标待核验；工程草案无预注册时间戳、样本量与统计方案不得正式触发标记或删除。
- **V7 evidence and failure rules aligned.** E3, E4, and E6 now use the V7 definitions; unverified L1/L2 mechanisms are marked pending audit; engineering drafts cannot trigger formal disposition without a preregistration timestamp, sample size, and statistical plan.
- **MSI 实现计数纠正。** 文档按实际实现写为 45 条随机文本收敛为 3 条核心语句，再转为 2 个结构节点；删除未经实现的 120 粒子与 12 节点描述。
- **MSI counts corrected.** Documentation now matches the implementation: 45 random text fragments converge to 3 core statements, then 2 structure nodes; unsupported 120-particle and 12-node descriptions were removed.

- **版本与产物元数据对齐。** 白皮书当前版本统一为 v1.1；根据实际 PDF 与生成脚本将页数修正为 22 页、插图修正为 3 图；CITATION 发布日期与 `VERSION.yaml` 统一为 2026-10-08。
- **Release metadata aligned.** The current white paper is v1.1; page and figure counts now match the actual PDF and generator (22 pages, 3 figures); the citation release date matches `VERSION.yaml` (2026-10-08).
- **校验器可移植性与误报修复。** Windows 默认 GBK 控制台不再导致校验脚本崩溃；HTML 证据色阶改为解析真实 `CFG.evidence_scale` 与评级索引；一致性检查新增白皮书版本、页数、幕数、时长、toolkit 数量与引用日期门槛，并接入 CI。
- **Verifier portability and false-positive fixes.** Validation scripts now run under the default Windows GBK console; HTML evidence checks parse the real configuration; CI now checks white-paper metadata, demo acts/runtime, toolkit count, and citation date.
- **文档渲染修复。** 重写中文 README 的损坏转义，恢复图片、链接、分隔线和命令；中英文 README、首页、路线图与架构文档的六幕描述统一为八幕。
- **Documentation rendering repaired.** The Chinese README was rewritten to restore images, links, separators, and commands; current Chinese and English docs now describe the eight-act demo consistently.
- **正典引用勘误。** 术语表中三特性 MCA / SA / AZ 的出处原写作「第 12 章 / 第 13 章」，经逐条比对正典原文，正确出处为**第 7 章的 7B.2 / 7B.3 / 7B.4 节**。
- **Canon citation correction.** The three properties MCA / SA / AZ were cited as Chapters 12 and 13; verification against the canon text shows they are defined in **Chapter 7, §7B.2 / §7B.3 / §7B.4**.
- **L3 锚点修正。** 原写「归位到元意义／中介意义／情境意义三个层次」，而 V7 正典**第 8 章 8.1「光谱带模型取代固定层次」**已把离散三层次重释为连续光谱带。L3 的定义与操作已相应改写，并区分了「三维度＝方向·价值·边界（3.2）」与「四维度＝认知C·价值V·存在E·行动A（8.2）」这两组不可混用的概念。
- **L3 anchor corrected.** The original wording placed material into three discrete levels; V7 canon **§8.1 ("the spectral band model replaces fixed levels")** reinterprets them as one continuous band. L3's definition and practice were rewritten accordingly, and the two non-interchangeable dimension sets are now distinguished.

### 移除或标记 / Removed or Flagged

- 暂无。若某个模块达到其预注册的失败阈值，其实情将记录在此段，并注明依据（证据等级、样本、失败标准）。
- None yet. If a module reaches its preregistered failure threshold, the fact is recorded here together with its basis (evidence level, sample, failure criterion).

---

## [0.2.0] - 2026-10-08

### Added
- **`VERSION.yaml`** — 单一版本源,所有版本号以此为唯一真相
- **`README.en.md`** — 英文版 README
- **`ROADMAP.md`** — 工程路线图 v0.2.0
- **`tools/audit_versions.py`** — 版本信号一致性扫描
- **`tools/fix_versions.py`** — 一致性缺陷批量修复
- **`tools/fix_versions_v2.py`** — badge / citation / changelog 收尾修复

### Changed
- 统一白皮书页数:`20` → `19`(与实际一致)
- 统一 Copyright:`2025` → `2026`
- `README.md` badge:`0.1.0` → `0.2.0`
- `CITATION.cff`:`0.1.0` → `0.2.0`

### Fixed
- 版本信号在 README / index.html / config.json / whitepaper 之间漂移的问题

---

## [0.1.0] - 2026-10-07

首次公开发布。

First public release.

### 新增 / Added

- **六层应用栈首次公开**：L1 减负 / Cognitive Load Reduction、L2 可体验 / Experiential Rendering、L3 意义生成 / Meaning Generation、L4 价值评估 / Value Assessment、L5 方向选择 / Direction Selection、L6 反思与审视递归 / Recursive Reflection and Review；并给出三带划分——界面带（L1–L2）、加工带（L3–L4）、元带（L5–L6）。
- **Six-layer application stack made public** for the first time: L1 Cognitive Load Reduction, L2 Experiential Rendering, L3 Meaning Generation, L4 Value Assessment, L5 Direction Selection, L6 Recursive Reflection and Review, together with the three bands — interface band (L1–L2), processing band (L3–L4), and meta band (L5–L6).
- **中英双语白皮书 v1.0**：`whitepaper/` 下的《意义智能 · 元智能理论与分层应用》公开发布白皮书，中英并列排版，由 Python 脚本生成 DOCX 并导出 PDF；发布产物存放于 `whitepaper/dist/`。
- **Bilingual white paper v1.0**: the public release white paper *Meaning Intelligence: Meta-Intelligence Theory and Layered Applications* under `whitepaper/`, laid out with Chinese and English in parallel, generated as DOCX by Python scripts and exported to PDF; release artifacts live in `whitepaper/dist/`.
- **MSI 六层演示系统**：`msi/` 下的 Meaning Intelligence 演示系统，由 Manim 场景（`msi/scenes/`）渲染动画，并构建为单文件交互页 `msi/meaning_intelligence.html`（时间轴联动、Canvas 粒子、六层导航）。
- **MSI six-layer demonstration system**: the Meaning Intelligence demo under `msi/`, with animation rendered from Manim scenes (`msi/scenes/`) and built into the single-file interactive page `msi/meaning_intelligence.html` (timeline linking, canvas particles, six-layer navigation).
- **E0–E6 证据等级与理论失败矩阵纳入仓库**：E0 概念 / E1 形式化 / E2 操作化 / E3 预测性 / E4 复制 / E5 证伪或存活 / E6 外部验证；每个核心模块写明支持证据、部分支持、失败阈值与失败后操作。仓库配套提供证伪报告模板（`.github/ISSUE_TEMPLATE/falsification_report.yml`），并承诺：若证伪成立，对应模块将被标记或删除。
- **E0–E6 evidence levels and the theory failure matrix brought into the repository**: E0 conceptual, E1 formalized, E2 operationalized, E3 predictive, E4 replicated, E5 falsified or surviving, E6 externally validated; every core module states its supporting evidence, partial support, failure threshold, and post-failure action. A falsification report template ships with the repository (`.github/ISSUE_TEMPLATE/falsification_report.yml`), together with the commitment that a module will be marked or removed if it is falsified.

### 说明 / Notes

- 本版本不主张任何模块达到 E4 及以上证据等级；各模块的当前等级以正典与白皮书中的标注为准。
- This release claims no module at evidence level E4 or above; the current level of each module is the one annotated in the canonical text and the white paper.
- 18 张可检验假设卡片 H1–H18 及其预注册证伪标准随正典发布；仓库侧只承载引用与报告流程，不复述全部标准。
- The 18 testable hypothesis cards H1–H18 and their preregistered falsification criteria are published with the canonical text; this repository carries references and the reporting workflow, not restatements of every criterion.

[Unreleased]: https://github.com/sara-protocol/meaning-intelligence/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sara-protocol/meaning-intelligence/releases/tag/v0.1.0
