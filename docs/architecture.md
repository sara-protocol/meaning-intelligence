# 系统架构 / System Architecture

> 这份文档回答一个问题：**这个仓库由哪些部分组成，数据如何在其中流动，以及哪些环节是刻意设计成这样而不是那样的？**
> This document answers one question: **what parts make up this repository, how does data move through them, and which design decisions are deliberate rather than incidental?**

---

## 一、仓库分层 / Repository Layering

分层判据不是目录大小，而是「改动它会牵动什么」。`whitepaper/` 与 `msi/` 互不依赖；`docs/` 只读它们；
`meaning-agent/` 与 `web-mcp/` 是独立运行入口；`pr_sdk_v2/` 读取 `msi/config.json` 与 `hypotheses.yaml`；
`audit/` 在浏览器中运行，只把可选的 AI 输入直接发往用户选择的引擎；`tools/` 校验来源、配置与构建产物。

Layers are divided by **blast radius**, not directory size. `whitepaper/` and `msi/` are independent; `docs/`
only reads them. `meaning-agent/` and `web-mcp/` are standalone runtime entry points. `pr_sdk_v2/` reads
`msi/config.json` and `hypotheses.yaml`; `audit/` runs in the browser and sends optional AI input directly to
the user's chosen engine. `tools/` validates sources, configuration, and build artifacts.

| 目录 / Directory | 角色 Role | 改动它的影响 Blast radius |
|---|---|---|
| [`msi/`](../msi) | **演示系统**：六层栈的可操作实现（Manim 场景 + 单文件交互页构建）<br>**Demonstration system**: an operable implementation of the six-layer stack | `config.json` 是唯一数据源，改它会同时影响动画与页面；`timeline.json` 是渲染产物，不是手写输入<br>`config.json` is the single source of truth; `timeline.json` is a render artifact |
| [`whitepaper/`](../whitepaper) | **生成脚本与产物**：正文、排版、插图，以及 `dist/` 下已发布的 DOCX/PDF<br>**Generator scripts and artifacts**: body, layout, figures, released DOCX/PDF | 改脚本会改变发布产物；直接改 `dist/` 下的二进制会被下一次构建静默覆盖<br>Script edits change the release; edits to `dist/` binaries are overwritten |
| `docs/` | **说明性文档层**（本目录）：架构、证据、失败矩阵、路线图、术语<br>**Explanatory documentation layer** (this directory) | 只引用不定义；与正典冲突时以正典为准<br>Cites only, defines nothing; the canon prevails on conflict |
| [`tools/`](../tools) | **校验工具**：页面、版本、issue 表单、发布同步与 v0.3.0 语义门槛<br>**Verification tooling**: page, version, issue-form, publication-sync, and v0.3.0 semantic gates | 读取来源与产物；测试通过不代表实证证据<br>Reads sources and artifacts; passing checks is not empirical evidence |
| [`meaning-agent/`](../meaning-agent) | **本地智能体**：六项确定性技能、回环 UI/MCP、待定批准门<br>**Local agent**: six deterministic skills, loopback UI/MCP, pending approval | 未配置 LLM 时离线；可选 LLM 只给未核验建议<br>Offline without LLM configuration; optional LLM advice is unverified |
| [`web-mcp/`](../web-mcp) | **公共只读 MCP**：Pages Function、Bearer 鉴权、白名单资源与工具<br>**Public read-only MCP**: Pages Function, Bearer auth, whitelisted resources/tools | 不执行输入代码，不提供任意文件/URL/命令访问；端点可用性不在本文断言<br>No input execution or arbitrary file/URL/command access; endpoint availability is not asserted here |
| [`pr_sdk_v2/`](../pr_sdk_v2) | **SDK 0.3.0（未发布工程版本）**：配置、六层启发式、假说判定<br>**SDK 0.3.0 (unreleased engineering)**: config, heuristics, hypothesis verdicts | 不改研究系统 0.2.0；注册元数据与设计上限不是已取得证据<br>Does not change research system 0.2.0; registration metadata and design ceilings are not achieved evidence |
| [`audit/`](../audit) | **浏览器本地审计/助手**：手动启发式、历史、可选双引擎 AI<br>**Browser-local audit/assistant**: manual heuristics, history, optional dual-engine AI | 输入仅在选择云引擎时直接发往 GitHub；本地历史含用户原文<br>Input goes directly to GitHub only when the cloud engine is chosen; local history contains user text |
| [`.github/`](../.github) | **贡献入口与 CI**：issue 表单（含证伪报告模板）、PR 模板、工作流<br>**Contribution entry points and CI** | 模板坏掉等于贡献入口坏掉；CI 不渲染 Manim，也不自动提交产物<br>A broken template is a broken entry point |

---

## 二、数据流架构图 / Architecture at a Glance

```
    ┌───────────────────────────────────────────────────────┐
    │ msi/config.json —— 唯一数据源 / single source of truth │
    │ 六层 L1–L6 · 三带 bands · 证据色阶 E0–E6               │
    └──────────┬─────────────────────────────┬──────────────┘
               ▼                             ▼
  ┌──────────────────────────┐  ┌───────────────────────────────┐
  │ msi/scenes/              │  │ msi/mi_common.py              │
  │  meaning_intelligence.py │  │  load_config()                │
  │ 八幕动画 Act1…Act8       │  │  calculate_layer_             │
  │ 每幕 self.mark() 打点     │  │   timestamps()（预算时间轴）   │
  └────────────┬─────────────┘  └───────────────┬───────────────┘
               │ export_timeline()              │ 仅在缺失时回退
               ▼                                │ fallback only
  ┌──────────────────────────┐                  │
  │ msi/timeline.json        │                  │
  │ 实测时间轴（渲染产物）     │                  │
  └────────────┬─────────────┘                  │
               └───────────────┬────────────────┘
                               ▼
         ┌───────────────────────────────────────────┐
         │ msi/build.py                              │
         │  注入 LAYERS / BANDS / EVIDENCE            │
         │  注入 TIMELINE + TIMELINE_SOURCE           │
         │   （"measured" 或 "planned"）              │
         │  扫描残留 {{...}}，有残留即非零退出         │
         └─────────────────────┬─────────────────────┘
                               ▼
         ┌───────────────────────────────────────────┐
         │ msi/meaning_intelligence.html             │
         │  单文件交互页：视频 + 时间轴联动 + 六层导航  │
         │  八幕 43 秒；实测末点 43.433 秒               │
         │  SOURCE === "planned" 时页面显示提示        │
         └─────────────────────┬─────────────────────┘
                               ▼
         ┌───────────────────────────────────────────┐
         │ tools/verify_html.py                      │
         │  占位符残留 · node --check 内联 JS · 抽查   │
         └───────────────────────────────────────────┘
```

`{{...}}` 指模板占位符。[`mi_common.py`](../msi/mi_common.py) 被 Manim 场景与构建脚本共用，因此两者
对「层顺序」与「层名」的理解不会漂移——层顺序由 `LAYER_ORDER = ["L1" … "L6"]` 单点定义。

`{{...}}` denotes a placeholder. `mi_common.py` is shared by the scene and the builder, so the two
cannot drift on layer order or names — order is defined once, in `LAYER_ORDER`.

---

## 三、MSI 数据流：四步 / The MSI Data Flow in Four Steps

1. **配置**：[`msi/config.json`](../msi/config.json) 定义每层的中英文名、定义、正典概念关联、证据等级与证伪条件来源，以及八幕的进入/停留时长、三带和 E0–E6 色阶。六层栈是 E0 工程扩展，不是正典固定层次；文案与演示参数修改一律从它开始。
   **Config**: bilingual layer names, definitions, canon concept links, evidence levels, falsifier scope, eight-act timing, bands, and palette. The stack is an E0 engineering extension, not a canon hierarchy.
2. **渲染**：[`msi/scenes/meaning_intelligence.py`](../msi/scenes/meaning_intelligence.py) 逐幕推进，
   每幕用 `self.mark()` 记录进入与退出时刻，结束时 `export_timeline()` 写出
   [`msi/timeline.json`](../msi/timeline.json)。
   **Render**: each act stamps entry and exit via `self.mark()`; `export_timeline()` writes `timeline.json`.
3. **构建**：[`msi/build.py`](../msi/build.py) 把配置与时间轴作为**合法 JS 字面量**注入
   [`msi/templates/html_template.html`](../msi/templates/html_template.html)，产出单文件页面；随后扫描
   残留占位符，有残留即非零退出——不静默产出坏页面。
   **Build**: injects config and timeline as **valid JS literals**, then scans for leftover placeholders and exits non-zero on any.
4. **校验**：[`tools/verify_html.py`](../tools/verify_html.py) 做三件事：残留占位符检查、抽出内联
   `<script>` 交给 `node --check` 做**真实语法检查**、关键注入项抽查。
   **Verify**: leftover placeholders, real syntax checking of every inline `<script>` via `node --check`, and spot checks.

一键流程见 [`msi/run.ps1`](../msi/run.ps1) 与 [`msi/run.sh`](../msi/run.sh)：渲染 → 把 MP4 复制到 HTML
同级目录 → `python build.py`。复制那一步不能省：页面引用的是同级目录的文件名，否则 `<video>` 永远黑屏。

The one-command path (`run.ps1` / `run.sh`): render → copy the MP4 next to the HTML → `build.py`. The
copy is not optional — the page references a file name in its own directory, or `<video>` stays black.

---

## 四、时间轴：为什么必须实测注入 / Why the Timeline Must Be Measured

**结论：动画时长由渲染决定，不由脚本里的意图决定。**

**The point: animation duration is decided by the render, not by the intent written in the script.**

- **手写会错位。** 每一幕的实际耗时取决于 `run_time`、等待、以及 Manim 自身的排布与字体度量，这些
  只有在渲染完成时才是确定的。手写时间轴会与画面逐渐错开——到第八幕时，页面指向的秒数与屏幕上
  正在发生的事情已经不是同一件事。
  **Hand-writing drifts.** Real duration depends on `run_time`, waits, and Manim's layout and font metrics, known only after rendering. By act eight the page points at a moment that no longer matches the screen.
- **打点位置在场景里。** `self.mark()` 记录的是渲染时钟 `self.renderer.time`，因此时间轴描述的是
  **实际发生过的**推进，而不是计划中的推进。实测值的形状见 [`msi/timeline.json`](../msi/timeline.json)。
  **The stamps live in the scene.** `self.mark()` records `self.renderer.time`, so the timeline describes what happened, not what was planned.
- **缺失时不失败，而是降级并提示。** 若 `timeline.json` 不存在（只跑 `python build.py`，或 CI 有意不
  渲染 Manim），`build.py` 用 `calculate_layer_timestamps()` 按 `config.json` 的 `duration` 累加出
  **预算时间轴**，把 `SOURCE` 标为 `"planned"`，页面据此显示提示：当前注入的是预算时间轴，渲染后
  重建即可同步毫秒级数据；缺少的层会另行告警。
  **Missing data degrades instead of failing.** Without it, `build.py` falls back to a **planned timeline** accumulated from each layer's `duration`, sets `SOURCE` to `"planned"`, and the page says so; missing layers are warned about separately.

降级状态因此是**可见的**：读者能区分「这是实测的」和「这是推算的」。这是本项目对证据的态度在工程上的
一个具体落点——不确定处标注不确定，而不是让它看起来一样。

The degraded state is therefore **visible**: a reader can tell "measured" from "extrapolated" — one
concrete engineering instance of this project's stance on evidence.

---

## 五、六层栈与正典运行机制的映射 / Mapping onto Canon Mechanisms

正典的运行机制是**三模块**（M1 感知 / M2 判断 / M3 行动）与**四流程**（F1 意义识别 / F2 意义评估 /
F3 意义决策 / F4 意义反馈）。六层栈不是正典机制，而是本项目把这些机制转译为应用层工程结构的一种**待检验假设**（白皮书表 2）。

The canon's mechanisms are **three modules** (M1 / M2 / M3) and **four processes** (F1–F4). The stack is not a canon mechanism; it is a **testable engineering hypothesis** about how to translate those mechanisms into an application structure (white paper Table 2).

| 六层 Layer | 正典三模块 Canon modules | 正典四流程 Canon processes | 主要产出 Primary output |
|---|---|---|---|
| **L1 减负** / Cognitive Load Reduction | M1 感知（输入侧） | F1 意义识别 | 结构化材料 |
| **L2 可体验** / Experiential Rendering | M1 感知（呈现侧） | F1 意义识别 | 可交互产物 |
| **L3 意义生成** / Meaning Generation | M2 判断 | F2 意义评估 | 候选意义结构 |
| **L4 价值评估** / Value Assessment | M2 判断 | F2 意义评估 | 证据强度标注 |
| **L5 方向选择** / Direction Selection | M3 行动 | F3 意义决策 | 方向声明＋偏离阈值 |
| **L6 反思与审视递归** / Recursive Reflection and Review | M1→M2→M3 回环 | F4 意义反馈 | 前提改写＋螺旋回环 |

三带划分由 `config.json` 的 `bands` 定义，动画与页面共用：界面带（L1–L2）解决**信息进不来**，
加工带（L3–L4）解决**意义出不来**，元带（L5–L6）解决**方向守不住**——只有元带能改写下层前提。

The bands come from `bands` in `config.json`: interface (L1–L2) for **information cannot get in**,
processing (L3–L4) for **meaning cannot get out**, meta (L5–L6) for **direction cannot be held** —
and only the meta band can rewrite the premises below it.

![六层栈](../whitepaper/figures/fig1_six_layer_stack.png)

![递归螺旋](../whitepaper/figures/fig2_recursive_spiral.png)

图中关键几何：归零后的落点 L1′ 与原点 L1 处于同一角度，但半径更大——L6 到 L1 的那条回边意味着第二轮的
输入标准已被第一轮的 L6 改写。若第二轮与第一轮完全重合，说明这一轮没有产生意义增量。

Key geometry: the post-zeroing point L1′ sits at the same angle as L1 at a larger radius — the L6→L1 back
edge means cycle two's input criteria were rewritten by cycle one's L6. Exact coincidence of the two
cycles means no meaning increment was produced.

---

## 六、SDK、智能体与浏览器助手数据流 / SDK, Agent, and Browser-Assistant Data Flow

### 6.1 SDK 0.3.0（未发布工程版本）/ SDK 0.3.0 (unreleased engineering)

```
msi/config.json ──► pr_sdk_v2/config.py ──► 配置校验/旧结构迁移 ──► CLI/API JSON
hypotheses.yaml ─► pr_sdk_v2/falsify.py ─► 按 status、数据与 inconclusive_if 判定
                                               ├─ draft / 缺数据 / 条件不足 / 未实现 → INCONCLUSIVE
                                               └─ 已实现的 L3-H1 名义 alpha 阈值      → FALSIFIED / NOT_FALSIFIED
pr_sdk_v2/layers.py ─► 文本/分桶/方向/反思启发式 ─► 带 limitations 的结果
tools/verify_final.py ─► 配置、消融、注册状态与引用结构门槛（含 --negative）
```

`registered` 只说明预注册元数据存在；`evidence_ceiling` 是设计上限，**不是已取得证据**。
`FALSIFIED` 与 `NOT_FALSIFIED` 都不授予实证等级，后者也不等于已证实。SDK 输出和结构检查均不是实证验证，
且不改变研究系统 v0.2.0（2026-10-08）。

`registered` means only that preregistration metadata exists; `evidence_ceiling` is a design ceiling,
**not achieved evidence**. Neither `FALSIFIED` nor `NOT_FALSIFIED` grants an empirical evidence level, and the
latter does not mean confirmed. SDK outputs and structural checks are not empirical validation and do not change
research system v0.2.0 (2026-10-08).

### 6.2 Meaning Agent 与 Web MCP / Meaning Agent and Web MCP

```
CLI / 回环 UI ─► 六项确定性技能 ─► 结构、证据边界、五尺度与证伪草案 ─► 人类批准待定
回环 http://127.0.0.1:8767/mcp ─► 同一智能体的只读资源/工具
Cloudflare Pages Function + MI_MCP_PUBLIC_TOKEN ─► 白名单双语资源与五个只读工具
                                                    └► 离线确定性分析；无任意代码/文件/URL/命令访问
```

Meaning Agent 是本地、离线优先入口；可选 LLM 只能提供未核验写作建议。公共 Web MCP 是独立的 Pages Function，
部署端点必须鉴权；本仓库不提供生产端点或凭据，本文不声称已完成部署。两者都不是实证验证。

The Meaning Agent is a local, offline-first entry point; an optional LLM can only suggest unverified prose.
The public Web MCP is a separate Pages Function whose deployed endpoint requires authentication. The repository
provides no production endpoint or credentials, and this document does not assert completed deployment.
Neither component is empirical validation.

### 6.3 浏览器本地审计/助手 / Browser-local audit/assistant

```
audit/index.html（浏览器）
  ├─ 手动路径 ─► 用户填写方向/价值/边界 + 启发式报告 ─► localStorage 历史
  └─ 可选 AI 路径
       ├─ GitHub Models ─► 浏览器直接 HTTPS 调用；token 与设置保存在 localStorage
       └─ 本地 Ollama ───► 浏览器调用 http://localhost:11434（需本地服务与跨源配置）
                     └─ JSON 建议 ─► 用户可编辑字段 ─► 人工生成/审阅报告
audit/qr.html ─► 指向 https://sara-protocol.github.io/meaning-intelligence/audit/ 的二维码入口
```

云引擎会把用户输入直接发送给 GitHub；项目没有后端代理。本地历史可能保存用户原文与报告。
界面按文本长度生成的 E 标签只是启发式占位，不是 V7.0 证据评级。二维码页面与 GitHub Pages URL 的存在
不等于已完成部署、可访问性或下载验证；助手与 AI 输出都不是实证验证。

With the cloud engine, user input goes directly to GitHub; there is no project backend proxy. Local history
may contain the user's original text and report. Evidence labels derived from text length are heuristic
placeholders, not V7.0 evidence grades. A QR page and GitHub Pages URL do not establish deployment,
availability, or download validation; neither the assistant nor its AI output is empirical validation.

---

## 七、这套架构不承诺什么 / What This Architecture Does Not Claim

- 六层栈本身是**整合结构，证据等级 E0**，未经独立检验；在 `config.json` 里把它数据化不会提高它的证据等级。
  The stack is an **integrative structure at E0**, untested; encoding it does not raise that level.
- 演示系统能让每一层**可被体验**，但不能替代对每一层的**检验**。可体验不等于已证实。
  The demo makes each layer *experienceable*; it does not test it. Experiential is not confirmed.
- SDK、审计/助手、Meaning Agent 与 Web MCP 都**不是实证验证**；代码可运行、注册元数据存在或检查通过，
  都不表示理论、机制或用户效果已取得证据。
  The SDK, audit/assistant, Meaning Agent, and Web MCP are **not empirical validation**. Runnable code,
  registration metadata, and passing checks do not show that the theory, mechanisms, or user effects have evidence.

后续阅读：[证据体系](evidence.md) · [理论失败矩阵](failure-matrix.md) · [术语对照](glossary.md)

## 构造边界 / Construct Boundary

![构造边界图](../whitepaper/figures/fig3_construct_boundary.png)

MIT 在概念空间中的位置:

| 环 | 内容 | 与 MIT 的关系 |
|---|---|---|
| **内环** | MIT | 元层:对智能活动的方向性调控 |
| **中环** | IQ · EQ · SQ | 平行能力;被 MIT 约束,而非与之并列 |
| **外环** | Semantic / Pragmatic · Decision Intelligence · Metacognitive AI · AI Alignment · Wisdom | 邻接场域;与 MIT 相邻但不同构造 |

**"元"的形式特征**:只有 MIT 位于其他智能活动之上,对它们进行方向约束。IQ 关心「能不能算」,
EQ 关心「能不能相处」,SQ 关心「能不能共处」——三者都在回答「如何做到」。唯有 MIT 追问
「为何要做」以及「值不值得」。

**命名提示**:本项目的 "Meaning Intelligence Theory" 使用 `MIT` 缩写时,指**方向性调控**,
与语义/语用/决策方向的同名 `Meaning Intelligence` 是不同构造。详见
[`docs/glossary.md`](glossary.md) 的命名冲突声明。

