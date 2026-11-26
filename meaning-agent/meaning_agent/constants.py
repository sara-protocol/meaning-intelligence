SCALES = (
    ("individual", "个人", "Individual"),
    ("organization", "组织", "Organization"),
    ("city", "城市", "City"),
    ("national", "国家", "National"),
    ("humanity", "人类", "Humanity"),
)

SCALE_ALIASES = {
    "individual": "individual", "personal": "individual", "self": "individual",
    "个人": "individual", "个体": "individual", "自我": "individual",
    "organization": "organization", "organisational": "organization", "org": "organization",
    "组织": "organization", "机构": "organization", "企业": "organization",
    "city": "city", "urban": "city", "城市": "city", "城市尺度": "city",
    "national": "national", "nation": "national", "country": "national",
    "国家": "national", "国家尺度": "national",
    "humanity": "humanity", "human": "humanity", "humankind": "humanity",
    "人类": "humanity", "人类尺度": "humanity",
}

EVIDENCE_LEVELS = (
    {"id": "E0", "name": "概念", "name_en": "Conceptual", "definition": "理论构念已定义。", "definition_en": "The theoretical construct is defined."},
    {"id": "E1", "name": "形式化", "name_en": "Formalized", "definition": "已建立数学模型。", "definition_en": "A mathematical model has been established."},
    {"id": "E2", "name": "操作化", "name_en": "Operationalized", "definition": "已有测量工具，信效度验证中。", "definition_en": "A measurement instrument exists; reliability and validity are under validation."},
    {"id": "E3", "name": "预测性", "name_en": "Predictive", "definition": "有预注册假设，数据收集中。", "definition_en": "A preregistered hypothesis exists and data collection is under way."},
    {"id": "E4", "name": "复制", "name_en": "Replicated", "definition": "独立实验室复现结果。", "definition_en": "Results have been replicated by an independent laboratory."},
    {"id": "E5", "name": "证伪或存活", "name_en": "Falsified or Survived", "definition": "预注册证伪标准已检验。", "definition_en": "The preregistered falsification criterion has been tested."},
    {"id": "E6", "name": "外部验证", "name_en": "Externally Validated", "definition": "跨情境、跨文化、跨时间泛化。", "definition_en": "Generalization across contexts, cultures, and time."},
)

HYPOTHESES = (
    {"id": "H1", "name": "意义智能必要性", "recorded_level": "E1", "falsifier": "无 MI 系统在 10 年模拟决策中的方向漂移率 ≤ 有 MI 系统（d < 0.3，p > 0.05，功效 ≥ 0.80）。"},
    {"id": "H2", "name": "意义不可还原性", "recorded_level": "E0", "falsifier": "意义判断方差被单一维度解释 > 90%。"},
    {"id": "H3", "name": "无 MI 方向漂移", "recorded_level": "E1", "falsifier": "长期运行（>10 年）的无 MI 系统方向漂移率 < 5%/年。"},
    {"id": "H4", "name": "势能驱动行动", "recorded_level": "E2", "falsifier": "PE 高位但行动意图 < 3/10，或行动后 PE 变化 < 5%。"},
    {"id": "H5", "name": "稳定性–适应性倒 U 型", "recorded_level": "E0", "falsifier": "稳定性与适应性呈线性正相关（r > 0.7）或线性负相关（r < -0.7）。", "audit_note": "附录 D.2 等级单元格截断；此处采用信息更完整的假设卡片。"},
    {"id": "H6", "name": "螺旋速率与意义危机", "recorded_level": "E0", "falsifier": "极快（>2 SD/月）但危机指数 < 3/10，或极慢（<0.1 SD/年）但意义状态健康。", "audit_note": "简表与假设卡片对极慢速率表述冲突；此处采用假设卡片。"},
    {"id": "H7", "name": "跨尺度一致性–生存", "recorded_level": "E1", "falsifier": "两尺度长期不一致（一致性 < 0.5）但生存概率高于高一致性对照组。"},
    {"id": "H8", "name": "尺度背离–危机", "recorded_level": "E1", "falsifier": "两尺度长期背离（>10 年，一致性 < 0.4）但均未出现可测意义危机。"},
    {"id": "H9", "name": "冲突校准", "recorded_level": "E0", "falsifier": "无法由元意义层校准的冲突通过其他方式解决且未导致分裂。"},
    {"id": "H10", "name": "变量可测性", "recorded_level": "E2", "falsifier": "到 2031 年，MC、BS、SD 等核心变量仍无信度 > 0.7 的量表。"},
    {"id": "H11", "name": "MI-AI 优势", "recorded_level": "E1", "falsifier": "连续 3 次对照实验中，MI 辅助决策未优于人类专家组（d < 0.3，p > 0.05）。"},
    {"id": "H12", "name": "归零防僵化", "recorded_level": "E2", "falsifier": "主动归零后僵化程度未缓解（变化 < 5%）或加剧。"},
    {"id": "H13", "name": "元认知–判断质量", "recorded_level": "E2", "falsifier": "RCT 中训练组与对照组的意义判断质量无显著差异（d < 0.3，p > 0.05）。"},
    {"id": "H14", "name": "无归零–僵化", "recorded_level": "E1", "falsifier": "长期运行（>20 年）的无归零系统意义螺旋持续上升（SD 持续 > 0）而未停滞。"},
    {"id": "H15", "name": "三特性协同", "recorded_level": "E0", "falsifier": "协同组与最优单一特性组无显著差异（d < 0.3，p > 0.05）。"},
    {"id": "H16", "name": "系缚–健康", "recorded_level": "E1", "falsifier": "BS > 0.8 但文明明显衰退，或 BS < 0.4 但文明繁荣。"},
    {"id": "H17", "name": "转型–归零重构", "recorded_level": "E1", "falsifier": "任一公认重大转型不符合归零–重构模型（经 3 位独立历史学家认定）。"},
    {"id": "H18", "name": "当代窗口", "recorded_level": "E1", "falsifier": "到 2050 年，>60% 受访者认为文明方向未发生根本变化。"},
)

D7_MODULES = (
    {"id": "SG", "name": "SG 假说", "failure_threshold": "3 个历史时期无显著相关", "action": "重参或放弃"},
    {"id": "Spectrum Spiral", "name": "Spectrum Spiral", "failure_threshold": "90% 以上变化无法捕获", "action": "修改或放弃"},
    {"id": "Witness→Leap", "name": "Witness→Leap", "failure_threshold": "RCT 无显著差异", "action": "放弃有效性"},
    {"id": "MI-AI", "name": "MI-AI 优势", "failure_threshold": "3 次实验均无优势", "action": "修改或放弃"},
    {"id": "Weaving Sovereignty", "name": "Weaving Sovereignty", "failure_threshold": "跨 5 种环境均无效", "action": "重构理论"},
)

ENGINEERING_FALSIFIERS = (
    {"layer": "L1", "scope": "engineering_draft", "condition": "结构化压缩相对原文的决策质量提升 d < 0.3。", "action": "重设压缩比或放弃字数硬限；不自动推翻认知负荷机制。"},
    {"layer": "L2", "scope": "engineering_draft", "condition": "预注册迁移任务中交互组与静态组无显著差异。", "action": "降为可选增强。"},
    {"layer": "L3", "scope": "canon_H2", "condition": "意义判断方差被单一维度解释 > 90%。", "action": "按正典程序检验 H2；另行评估 L3 工程界面。"},
    {"layer": "L4", "scope": "engineering_draft", "condition": "证据等级标注跨评审者不一致，或与后续检验结果无单调关系。", "action": "退回定性评估；先补预注册阈值。"},
    {"layer": "L5", "scope": "engineering_draft", "condition": "所选方向在事后评估中不优于基线或随机选择。", "action": "删除或重做方向选择操作化；不自动处置 H7/H8。"},
    {"layer": "L6", "scope": "engineering_draft", "condition": "预注册后续轮次中递归审视的纠错率不高于无审视对照。", "action": "仅移除递归组件；不自动推翻 H12/H13/H14。"},
)

CORRECTION_LEVELS = (
    {"level": 1, "deviation": "<10%", "action": "记录偏差并继续观察", "scope": "engineering_operationalization"},
    {"level": 2, "deviation": "10–30%", "action": "回到元意义层校准方向与边界", "scope": "engineering_operationalization"},
    {"level": 3, "deviation": ">30%", "action": "暂停执行并进行受控归零复核", "scope": "engineering_operationalization"},
)

PROVENANCE = {
    "canon": "V7.0 正典 H1–H18、附录 D.7、E0–E6 优先",
    "six_layers": "本项目 E0 工程扩展，不是正典固定层次，也未经本项目独立检验",
    "dimensions": "方向 / 价值 / 边界（正典 §3.2）",
    "spectrum": "连续意义光谱带（正典 §8.1），不是三个固定抽屉",
    "scales": "个人 / 组织 / 城市 / 国家 / 人类；不可通约，不可加权求和（正典公理三、§4.3）",
    "approval": "人类最终批准；本工具不替代专业判断",
}

SCHEMA_VERSION = "1.0.0"
DEFAULT_WEB_PORT = 8766
DEFAULT_MCP_PORT = 8767
SKILL_NAMES = (
    "reduce-cognitive-load",
    "model-experiential-interface",
    "map-direction-value-boundary",
    "grade-evidence-falsification",
    "calibrate-five-scales",
    "recursive-review-zeroing",
)
