# 正典与工程来源手册

维护理论表述、构建 MSI 或白皮书、运行仓库校验、检查发布包时使用本文件。路径均相对仓库根。

## 1. 权威顺序与来源边界

| 优先级 | 来源 | 可据此声明 | 不可据此声明 |
|---|---|---|---|
| 1 | KDP 定稿02中文 V7 正典；哈希见 `VERSION.yaml` 与 `docs/canon-audit.md` | 正典构念、H1–H18、附录 D.7、E0–E6、§8.1 光谱带 | 把工程 L1–L6 称为正典固定层次 |
| 2 | `Meaning IntelligenceV7.docx` 英文母本 | 校对英文标题与术语 | 与中文正典并行修改、另立版本 |
| 3 | `whitepaper/build_whitepaper.py` 及受控发布产物 | 应用层转译与双语表述 | 新增本体论或覆盖正典 |
| 4 | `msi/config.json`、场景代码与实测 `timeline.json` | 六层工程实现、演示参数、实际时间轴 | 以动画或交互证明理论 |
| 5 | `README.md`、`README.en.md`、`CHANGELOG.md`、`index.html` | 版本一致的传播说明 | 绕过 `VERSION.yaml` 或取代原始来源 |

- `VERSION.yaml` 是版本号唯一来源；正典与研究系统分别版本化。
- `hypotheses.yaml`、`docs/`、`.github/ISSUE_TEMPLATE/` 是引用、说明与贡献入口，不替代正典。
- 正典 L1–L3 原指元意义、结构意义、情境意义，§8.1 已重释为连续光谱带；它与工程 L1–L6 不是同一编号系统。
- 六层栈、三带与 MSI 是 E0 工程扩展。六层栈整体仍是 E0，即使某层已有更高操作化状态。
- 发现冲突时保留冲突记录；不得静默改写正典、重编号或删除失败证据。正典 H1–H18 与附录 D.7 优先于工程草案。

## 2. V7.0 E0–E6 精确定义

以正典表 I.2 为准。等级描述关于主张的知识状态，不是质量评分或进度条。

| 等级 | 名称 | 精确判据 | 禁止误读 |
|---|---|---|---|
| E0 | 概念 | 理论构念已定义 | 已证实或无用 |
| E1 | 形式化 | 已建立数学模型 | 已有测量工具 |
| E2 | 操作化 | 已有测量工具，信效度验证中 | 信效度已完成 |
| E3 | 预测性 | 有预注册假设，数据收集中 | 已做出成功预测 |
| E4 | 复制 | 独立实验室复现结果 | 仅在独立数据上重复 |
| E5 | 证伪或存活 | 预注册证伪标准已检验 | 已证伪即失败，或 E5 即可靠 |
| E6 | 外部验证 | 跨情境、跨文化、跨时间泛化 | 框架外领域表示认可 |

E5 有“已证伪”和“经预注册检验存活”两个出口。升级必须补对应证据链，不得为升级放宽标准。

## 3. 六层证据与 H 映射

“本框架状态”和“正典关联”必须分列。外部机制成熟度不能转移给工程操作化。

| 工程层 | 一句话定义 | 本框架状态 | 正典概念关联与 H 映射 | 证伪范围 |
|---|---|---|---|---|
| L1 减负 | 把认知负荷从信息量转移到结构 | E1；外部机制待核验 | §1.1、工具 A.1；无直接 H 映射 | 工程草案 |
| L2 可体验 | 把“读到”变成“操作到” | E1；外部机制待核验 | 第3章、第9章 M1；无直接 H 映射 | 工程草案 |
| L3 意义生成 | 组织成方向·价值·边界 | E0–E1 | §3.1/§3.2、§8.1；**H2（E0）** | 正典 H2 |
| L4 价值评估 | 为判断标注证据强度 | E2（工具）/ E1（模型） | 第6章 E0–E6、§3.3 PE；关联 **H10（E2）** | 工程草案；H10 另按正典 |
| L5 方向选择 | 在五尺度上选定值得的方向 | E1 | 第4章、DC 指标；关联 **H7/H8（均 E1）** | 工程草案；H7/H8 另按正典 |
| L6 反思与审视递归 | 让系统审视自己的审视 | E2 | §7B.2–§7B.4；关联 **H12/H13（E2）、H14（E1）** | 工程草案；三者不得合并处置 |

映射边界：

- H2 直接对应 L3 的意义不可还原性；L4 的评审一致性不等于 H10 的量表信度。
- H7/H8 检验跨尺度生存与危机，不等于 L5 选路优于基线。
- H12 检验主动归零防僵化，H13 检验元认知训练，H14 检验无归零僵化；均不能替代 L6 递归审视的工程检验。
- `hypotheses.yaml` 中的 `layer` 字段只是引用归类，不证明正典采用工程六层。

H1–H18 的正式定义和当前等级以正典卡片为准；`hypotheses.yaml` 是机器可读引用。`docs/failure-matrix.md` 可作摘要，但不能覆盖正典。附录 D.7 只覆盖 SG、Spectrum Spiral、Witness→Leap、MI-AI、Weaving Sovereignty 五个模块，**不是**六层工程失败矩阵。已知上游问题（H5 等级截断、H6 简表与卡片冲突等）见 `docs/canon-audit.md`，不得自行“修复”原件。

## 4. 正式处置规则

1. **先分类，后检验。** 明确对象是正典 H 假设、D.7 模块、外部机制，还是某工程组件；一次失败只推翻被检验的主张。
2. **工程草案必须预注册。** 在观察数据前登记假设、指标、样本量、停止规则、SESOI、统计方法、多重比较方案和处置规则，并保存时间戳与版本。仓库内草案或 `d < 0.3, p > 0.05` 不自动构成正式阈值。
3. **区间判定优先。** 按 `docs/equivalence-tests.md`，Cohen's d 的 90% CI 完全落在 `[-SESOI, +SESOI]` 内才支持等效；CI 越界即证据不足，既不宣告支持也不宣告证伪。
4. **禁止事后放宽。** 数据后调整阈值属于 HARKing；只能追加公开修订并记录理由、影响和时间顺序。
5. **正典按正典处置。** H1–H18 与 D.7 的阈值不能被工程草案覆盖。未达到预注册标准的探索结果必须公开，但不能标记为正式证伪。
6. **处置不越权。** 达到正式标准后标记或删除、不辩护；删除或其他破坏性操作仍需用户明确授权。未经授权不得 commit、push、部署、删除或修改共享配置。
7. **留痕。** 记录对象、版本、证据、理由与处置；正典上游冲突保持只读并进入审查记录。

## 5. 构建与校验命令

从仓库根执行：

```bash
# 默认：按指定顺序审计，不构建白皮书
python .qoder/skills/meaning-intelligence-maintain/scripts/audit.py

# 可选：审计后重建白皮书插图与 DOCX；不转换 PDF、不部署
python .qoder/skills/meaning-intelligence-maintain/scripts/audit.py --build-whitepaper

# 校验本 Skill 本身
python .qoder/skills/meaning-intelligence-maintain/scripts/validate_skill.py
```

依赖：Python 3、PyYAML；白皮书另需 `python-docx`、Pillow 与 CJK 字体；`verify_html.py` 用 Node 检查真实 JS 语法，缺失时会明确报告跳过，不能把跳过当语法通过。不要为校验安装或修改共享配置，除非用户授权。

审计顺序固定为：

1. `python tools/verify_issue_forms.py`
2. `python tools/verify_consistency.py`
3. `python tools/verify_html.py msi/meaning_intelligence.html`
4. `python tools/verify_planned_fallback.py`
5. `cd msi && python build.py`
6. `python tools/verify_html.py msi/meaning_intelligence.html`

`--build-whitepaper` 仅在上述六步成功后追加：

```bash
cd whitepaper
python make_figures.py
python build_whitepaper.py
```

`msi/build.py` 会重写 `msi/meaning_intelligence.html` 与 `msi/meaning_intelligence_diagram.md`；白皮书构建会重写插图与 `whitepaper/dist/` 中的 DOCX。运行前告知这些生成物会变化。不要手改 DOCX，应改生成脚本。Manim 渲染不是审计的一部分；预算时间轴必须标为 `planned`，不得冒充实测。

## 6. 发布包检查清单（不部署）

- 只检查已生成包：文件名、版本、体积、可读性、DOCX 内含 `word/document.xml`、PDF 可打开、页面与图片资源存在。
- 将 `whitepaper/dist/` 的 DOCX/PDF 与 `VERSION.yaml` 的白皮书版本、页数、表数、图数交叉核对；PDF 不是 `build_whitepaper.py` 的自动产物。
- 检查 MSI 引用的 MP4、截图与时间轴是否匹配；确认页面显示 `measured` 或显式的 `planned` 提示。
- 不读取 token、API key 或凭据文件，不打印环境变量，不调用 `tools/publish.py` 或任何发布/部署工具。
- 构建、检查和发布是三个阶段；检查通过不等于获得部署授权。
