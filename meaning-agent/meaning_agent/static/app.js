"use strict";

const $ = (id) => document.getElementById(id);
const state = { result: null, meta: null, language: "zh", experienceHtml: "", llmConfigured: null };
const SAMPLE = {
  text: "团队报告：试点用户完成率从 60% 提升到 72%，但两位用户退出。团队应该优先降低使用门槛，同时保留数据删除权。是否需要在三个月后扩大范围？个人希望节省时间，组织希望稳定交付，城市合作方担心隐私。请评估证据。",
  context: {
    source: "合成演示文本，不是真实研究",
    preferred_direction: "先降低使用门槛，三个月后再评估是否扩大范围",
    value_types: ["utility", "intrinsic", "relational"],
    boundaries: { temporal: "三个月试点期", spatial: "试点团队", relational: "用户保留数据删除权" },
    spectrum_position: 42,
    scale_positions: {
      individual: { direction: "节省时间", alignment: "support", costs: ["学习新流程"] },
      organization: { direction: "稳定交付", alignment: "support", costs: ["维护成本"] },
      city: { direction: "隐私保护", alignment: "conflict", costs: ["数据治理成本"] },
      national: { direction: "稳定交付", alignment: "neutral", costs: ["跨地区协调"] },
      humanity: { direction: "尊重自主", alignment: "support", costs: ["跨文化协调"] }
    },
    scale_priorities: ["individual", "organization", "city", "national", "humanity"],
    triggers: ["完成率连续两周低于 60%", "出现隐私投诉"],
    expires_on: "2027-01-31"
  }
};

const I18N = {
  zh: {
    checking: "检查模式", offline: "离线确定性", llmReady: "LLM 可选", eyebrow: "方向 · 价值 · 边界",
    title: "让信息成为可审问的意义。", lede: "六个技能协同工作，保留不确定性、尺度冲突与人工决定。",
    stamp: "六层为工程扩展\n不是正典固定层次", inputTitle: "输入材料", inputHint: "陈述、问题与条件尽量分开。",
    textLabel: "待分析文本", charLimit: "/ 20,000", scaleTitle: "选择尺度", scaleHint: "尺度不可通约，系统不会加权求和。",
    individual: "个人", organization: "组织", city: "城市", national: "国家", humanity: "人类",
    contextTitle: "情境与证据（可选 JSON）", contextHint: "可填写 direction、boundaries、scale_positions、costs、scale_priorities、expires_on、evidence。",
    run: "运行分析", running: "正在审视…", sample: "载入示例", privacy: "仅在本地处理。服务不读取任意文件、不执行命令、不保存分析。",
    emptyTitle: "等待一次意义审视", emptyText: "输入材料并运行后，这里会展示六层结果、证据边界、证伪条件与批准门。",
    resultEyebrow: "分析结果", approvalTitle: "人工批准门", clarificationTitle: "需要澄清",
    tabOverview: "意义结构", tabEvidence: "证据与证伪", tabDirection: "方向与冲突", tabReview: "递归审视", tabJson: "JSON",
    direction: "方向", value: "价值", boundary: "边界", spectrumTitle: "连续意义光谱带", situational: "情境 / 具体 / 短时距", meta: "元意义 / 抽象 / 长时距",
    statementsTitle: "文本陈述 · 未核实", questionsTitle: "待决问题", experienceTitle: "结构体验", experienceHint: "调节参数只改变呈现，不增加证据。",
    download: "下载 HTML", detailLevel: "细节层级", noAutoLevel: "实证等级不自动授予", noAutoLevelText: "E0–E6 描述知识状态，不是质量分数。用户声明与独立核验始终分开。",
    evidenceScale: "正典 V7.0 证据标尺", level: "等级", meaning: "含义", evidenceItems: "用户提供的证据", hypothesisTitle: "相关正典假设", d7Title: "附录 D.7",
    draftTitle: "工程证伪草案 · 未预注册", draftHint: "这些条件只能指导探索，不能触发正式删除或覆盖正典阈值。",
    noSum: "不可加权求和", noSumText: "个人、组织、城市、国家、人类的意义不可通约。冲突须回到元意义层校准。",
    provisionalTitle: "临时方向 · 尚非承诺", scaleMatrix: "五尺度检查", scale: "尺度", alignment: "对齐", cost: "代价",
    conflictTitle: "冲突校准", priorityTitle: "优先级与代价", triggerTitle: "修正触发条件", metaTitle: "元认知问题", reviewTriggerTitle: "复核触发",
    revisionTitle: "修订建议", zeroTitle: "受控归零", professionalTitle: "专业判断边界",
    professionalText: "本工具不能替代医疗、法律、财务、安全等领域的专业判断。高影响决定必须由有资格的人复核。",
    rawTitle: "结构化结果", copy: "复制 JSON", footer: "正典 H1–H18 与附录 D.7 优先 · 六层工程草案不冒充已证实结论 · 人类最终批准",
    none: "无", unknown: "未提供", pending: "pending · 自动化批准关闭", copied: "已复制 JSON", downloadReady: "已生成独立 HTML",
    invalidContext: "情境 JSON 无效，请检查格式。", requestFailed: "请求失败，未输出错误详情。", emptyInput: "请先输入需要分析的文本。",
    mentions: "次", status: "状态", mode: "模式", claimed: "声明", accepted: "核验", basis: "依据", correction: "修正",
    notProvided: "未提供", noConflicts: "未检测到显式冲突；未知立场不等于一致。", notAssessed: "尚未评估"
  },
  en: {
    checking: "Checking mode", offline: "Offline deterministic", llmReady: "LLM optional", eyebrow: "Direction · Value · Boundary",
    title: "Turn information into meaning you can question.", lede: "Six skills work together while preserving uncertainty, scale conflicts and human choice.",
    stamp: "Six-layer engineering extension\nNot a fixed canon hierarchy", inputTitle: "Input material", inputHint: "Separate statements, questions and conditions where possible.",
    textLabel: "Text to analyze", charLimit: "/ 20,000", scaleTitle: "Select scales", scaleHint: "Scales are incommensurable; no weighted sum is used.",
    individual: "Individual", organization: "Organization", city: "City", national: "National", humanity: "Humanity",
    contextTitle: "Context and evidence (optional JSON)", contextHint: "Supports direction, boundaries, scale_positions, costs, scale_priorities, expires_on and evidence.",
    run: "Run analysis", running: "Reviewing…", sample: "Load example", privacy: "Local processing only. No arbitrary file reads, command execution or saved analyses.",
    emptyTitle: "Waiting for a meaning review", emptyText: "Run an analysis to see six-layer results, evidence boundaries, falsifiers and the approval gate.",
    resultEyebrow: "Analysis result", approvalTitle: "Human approval gate", clarificationTitle: "Clarification needed",
    tabOverview: "Meaning", tabEvidence: "Evidence", tabDirection: "Direction", tabReview: "Review", tabJson: "JSON",
    direction: "Direction", value: "Value", boundary: "Boundary", spectrumTitle: "Continuous meaning spectrum", situational: "Situational / concrete / short", meta: "Meta / abstract / long",
    statementsTitle: "Text statements · unverified", questionsTitle: "Open questions", experienceTitle: "Structural experience", experienceHint: "Parameters change presentation, not evidence strength.",
    download: "Download HTML", detailLevel: "Detail level", noAutoLevel: "No automatic empirical level", noAutoLevelText: "E0–E6 describes knowledge state, not quality. User claims and independent verification stay separate.",
    evidenceScale: "Canon V7.0 evidence scale", level: "Level", meaning: "Meaning", evidenceItems: "User-supplied evidence", hypothesisTitle: "Linked canon hypotheses", d7Title: "Appendix D.7",
    draftTitle: "Engineering falsification drafts · not preregistered", draftHint: "These conditions guide exploration only; they cannot trigger formal removal or override canon thresholds.",
    noSum: "No weighted summation", noSumText: "Individual, organization, city, national and humanity meanings are incommensurable. Conflicts return to meta-meaning calibration.",
    provisionalTitle: "Provisional direction · not a commitment", scaleMatrix: "Five-scale check", scale: "Scale", alignment: "Alignment", cost: "Cost",
    conflictTitle: "Conflict calibration", priorityTitle: "Priorities and costs", triggerTitle: "Correction triggers", metaTitle: "Metacognition questions", reviewTriggerTitle: "Review triggers",
    revisionTitle: "Revision suggestions", zeroTitle: "Controlled zeroing", professionalTitle: "Professional judgment boundary",
    professionalText: "This tool cannot replace professional medical, legal, financial or safety judgment. High-impact decisions require qualified human review.",
    rawTitle: "Structured result", copy: "Copy JSON", footer: "Canon H1–H18 and Appendix D.7 prevail · Engineering drafts are not confirmed findings · Humans approve finally",
    none: "None", unknown: "Not provided", pending: "pending · automated approval disabled", copied: "JSON copied", downloadReady: "Standalone HTML generated",
    invalidContext: "Context JSON is invalid.", requestFailed: "Request failed; error details were not exposed.", emptyInput: "Enter text to analyze first.",
    mentions: "mentions", status: "Status", mode: "Mode", claimed: "Claimed", accepted: "Verified", basis: "Basis", correction: "Correction",
    notProvided: "Not provided", noConflicts: "No explicit conflict detected; unknown positions do not imply alignment.", notAssessed: "Not assessed"
  }
};

const t = (key) => I18N[state.language][key] || key;
const localize = (value) => {
  if (Array.isArray(value)) return value.map(localize);
  if (value && typeof value === "object") {
    if (Object.hasOwn(value, "zh") || Object.hasOwn(value, "en")) {
      const selected = state.language === "zh" ? value.zh : value.en;
      return selected === undefined ? localize(value.en ?? value.zh) : localize(selected);
    }
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, localize(item)]));
  }
  return value;
};
const format = (value) => {
  if (value === null || value === undefined || value === "") return t("notProvided");
  if (typeof value === "object") return JSON.stringify(localize(value), null, 2);
  return String(value);
};
const setText = (id, value) => { $(id).textContent = format(value); };
const clear = (id) => { $(id).replaceChildren(); };
const make = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};
const renderList = (id, items, formatter = format) => {
  const node = $(id);
  node.replaceChildren();
  const values = Array.isArray(items) ? items : [];
  if (!values.length) node.append(make("li", "", t("none")));
  values.forEach((item) => node.append(make("li", "", formatter(item))));
};
const renderCards = (id, items) => {
  const node = $(id);
  node.replaceChildren();
  if (!Array.isArray(items) || !items.length) {
    node.append(make("p", "field-help", t("none")));
    return;
  }
  items.forEach((item) => {
    const card = make("article", "info-card");
    const header = make("header");
    header.append(make("strong", "", item.title || item.id || item.layer || ""));
    if (item.tag) header.append(make("span", "", item.tag));
    card.append(header);
    card.append(make("p", "", item.body || ""));
    node.append(card);
  });
};
const toast = (message) => {
  $("toast").textContent = message;
  $("toast").hidden = false;
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => { $("toast").hidden = true; }, 2400);
};

function setLanguage(language) {
  state.language = language;
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.dataset.i18n;
    node.textContent = t(key).replaceAll("\\n", "\n");
  });
  $("lang-zh").classList.toggle("active", language === "zh");
  $("lang-en").classList.toggle("active", language === "en");
  $("lang-zh").setAttribute("aria-pressed", String(language === "zh"));
  $("lang-en").setAttribute("aria-pressed", String(language === "en"));
  $("text").placeholder = language === "zh" ? "例如：团队报告……是否应该……？" : "For example: A team reports… should we…?";
  if (state.llmConfigured !== null) {
    $("engine-mode").querySelector("span").textContent = state.llmConfigured ? t("llmReady") : t("offline");
  }
  if (state.result) renderResult(state.result);
}

function switchTab(name) {
  document.querySelectorAll("[data-tab]").forEach((button) => button.setAttribute("aria-selected", String(button.dataset.tab === name)));
  document.querySelectorAll(".tab-panel").forEach((panel) => { panel.hidden = panel.id !== `tab-${name}`; });
}

function renderConcepts(nodes) {
  const list = $("concept-list");
  const range = $("detail-range");
  list.replaceChildren();
  const safeNodes = Array.isArray(nodes) ? nodes.slice(0, 10) : [];
  const maximum = Math.max(1, safeNodes.length);
  range.max = String(maximum);
  range.value = String(Math.min(3, maximum));
  if (!safeNodes.length) list.append(make("span", "concept-chip", t("none")));
  safeNodes.forEach((node) => {
    const chip = make("span", "concept-chip", node.label || "");
    chip.append(make("small", "", `${node.mentions ?? 0} ${t("mentions")}`));
    list.append(chip);
  });
  updateConcepts();
}
function updateConcepts() {
  const count = Number($("detail-range").value);
  $("detail-count").textContent = String(count);
  Array.from($("concept-list").children).forEach((node, index) => { node.hidden = index >= count; });
}

function renderResult(result) {
  state.result = result;
  const skills = result.skills || {};
  const data = (layer) => skills[layer]?.data || {};
  const l1 = data("L1"), l2 = data("L2"), l3 = data("L3"), l4 = data("L4"), l5 = data("L5"), l6 = data("L6");
  $("empty-state").hidden = true;
  $("result-content").hidden = false;
  setText("result-summary", result.summary);
  setText("result-status", result.status);
  setText("result-mode", result.mode);
  const gate = result.approval_gate || {};
  setText("approval-text", `${gate.status || "pending"} · ${state.language === "zh" ? "自动化批准关闭" : "automated approval disabled"}`);
  setText("approval-status", String(gate.status || "pending").toUpperCase());
  $("approval-gate").classList.toggle("approved", gate.status === "approved");
  const questions = result.needs_clarification || [];
  $("clarification-banner").hidden = questions.length === 0;
  renderList("clarification-list", questions, (item) => format(localize(item && typeof item === "object" ? item.question ?? item : item)));

  const dimensions = l3.dimensions || {};
  setText("dimension-direction", dimensions.direction?.statement);
  setText("dimension-value", dimensions.value?.candidates);
  const boundary = dimensions.boundary || {};
  setText("dimension-boundary", { temporal: boundary.temporal, spatial: boundary.spatial, relational: boundary.relational });
  const spectrum = l3.spectrum || {};
  setText("spectrum-label", spectrum.status || spectrum.segment);
  setText("spectrum-method", `${spectrum.method || ""} · ${spectrum.model || ""}`);
  $("spectrum-marker").hidden = typeof spectrum.position !== "number";
  if (typeof spectrum.position === "number") $("spectrum-marker").style.left = `${Math.max(0, Math.min(100, spectrum.position))}%`;
  const separation = l1.fact_question_separation || {};
  renderList("statements-list", separation.reported_statements, (item) => item.text);
  renderList("questions-list", separation.open_questions, (item) => item.text);
  renderConcepts(l1.key_structure?.nodes);
  state.experienceHtml = l2.interactive_html || "";

  const evidenceTable = $("evidence-table");
  evidenceTable.replaceChildren();
  (l4.reference_scale || []).forEach((item) => {
    const row = make("tr");
    row.append(make("td", "", `${item.id} · ${state.language === "zh" ? item.name : item.name_en}`));
    row.append(make("td", "", state.language === "zh" ? item.definition : item.definition_en));
    evidenceTable.append(row);
  });
  renderList("evidence-list", l4.evidence_items, (item) => `${item.source}: ${item.description || ""} | ${t("claimed")}: ${item.claimed_level ?? "—"} | ${t("accepted")}: ${item.accepted_level ?? "—"}`);
  renderCards("hypothesis-list", (l4.linked_hypotheses || []).map((item) => ({ title: `${item.id} · ${item.name}`, tag: item.recorded_level, body: item.falsifier })));
  renderCards("d7-list", (l4.appendix_d7 || []).map((item) => ({ title: item.name, tag: "D.7", body: `${item.failure_threshold} → ${item.action}` })));
  renderCards("draft-list", (l4.falsification_conditions?.engineering_drafts || []).map((item) => ({ title: `${item.layer} · ${item.scope}`, tag: state.language === "zh" ? "未预注册" : "Not preregistered", body: `${item.condition} ${item.action}` })));

  const direction = l5.provisional_direction || {};
  setText("provisional-direction", direction.direction ? `${direction.direction}\n[${direction.status}]` : null);
  const scaleTable = $("scale-table");
  scaleTable.replaceChildren();
  const scaleNames = new Map((state.meta?.scales || []).map((item) => [item.id, state.language === "zh" ? item.zh : item.en]));
  (l5.scale_positions || []).forEach((item) => {
    const row = make("tr");
    row.append(make("td", "", scaleNames.get(item.scale) || item.scale));
    row.append(make("td", "", item.direction));
    row.append(make("td", "", item.alignment));
    row.append(make("td", "", item.costs));
    scaleTable.append(row);
  });
  renderCards("conflict-list", (l5.conflicts || []).map((item) => ({ title: (item.scales || []).join(" ↔ "), tag: item.status, body: `${item.reason || item.description || ""}\n${item.calibration_question || ""}` })));
  if (!(l5.conflicts || []).length) renderCards("conflict-list", [{ title: t("none"), body: t("noConflicts") }]);
  setText("priority-list", l5.priority_order);
  setText("cost-list", l5.costs);
  renderList("trigger-list", l5.trigger_conditions, (item) => typeof item === "string" ? item : `${item.condition || ""} [${item.source || item.measurement || ""}]`);
  setText("expiry-line", `${state.language === "zh" ? "失效 / 复核日期" : "Expiry / review date"}: ${l5.expires_on || t("notProvided")}`);

  renderList("meta-list", l6.metacognition_questions);
  renderCards("review-trigger-list", (l6.review_triggers || []).map((item) => ({ title: item.code, tag: item.severity, body: item.reason })));
  renderList("revision-list", l6.revision_suggestions);
  const zero = l6.zeroing_plan || {};
  setText("zero-summary", `${zero.recommended ? (state.language === "zh" ? "建议受控归零" : "Controlled zeroing suggested") : (state.language === "zh" ? "当前未请求归零" : "Zeroing not requested")} · ${zero.mode || ""}`);
  $("zero-details").replaceChildren();
  (zero.safety_check || []).forEach((item) => $("zero-details").append(make("p", "field-help", `□ ${item}`)));
  setText("professional-domains", gate.required_professional_domains?.length ? `${state.language === "zh" ? "检测到领域" : "Detected domains"}: ${gate.required_professional_domains.join(", ")}` : null);
  $("raw-json").textContent = JSON.stringify(result, null, 2);
}

async function runAnalysis(text, context, scales) {
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, context, scales }),
    signal: AbortSignal.timeout(20000)
  });
  if (!response.ok) throw new Error("request_failed");
  return response.json();
}

$("analysis-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = $("text").value.trim();
  if (!text) return toast(t("emptyInput"));
  let context;
  try { context = JSON.parse($("context").value || "{}"); }
  catch { return toast(t("invalidContext")); }
  if (!context || typeof context !== "object" || Array.isArray(context)) return toast(t("invalidContext"));
  const scales = Array.from(document.querySelectorAll('input[name="scale"]:checked')).map((input) => input.value);
  const button = $("run-button");
  button.disabled = true;
  button.querySelector("span").textContent = t("running");
  try {
    const result = await runAnalysis(text, context, scales);
    renderResult(result);
    if (window.innerWidth < 781) $("result-panel").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch { toast(t("requestFailed")); }
  finally { button.disabled = false; button.querySelector("span").textContent = t("run"); }
});

$("sample-button").addEventListener("click", () => {
  $("text").value = SAMPLE.text;
  $("context").value = JSON.stringify(SAMPLE.context, null, 2);
  $("char-count").textContent = String(SAMPLE.text.length);
  $("text").focus();
});
$("text").addEventListener("input", () => { $("char-count").textContent = String($("text").value.length); });
$("context").value = "{}";
$("lang-zh").addEventListener("click", () => setLanguage("zh"));
$("lang-en").addEventListener("click", () => setLanguage("en"));
document.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.tab)));
$("detail-range").addEventListener("input", updateConcepts);
$("download-html").addEventListener("click", () => {
  if (!state.experienceHtml) return;
  const blob = new Blob([state.experienceHtml], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "meaning-structure.html";
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast(t("downloadReady"));
});
$("copy-json").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(JSON.stringify(state.result, null, 2)); toast(t("copied")); }
  catch { $("raw-json").focus(); }
});

Promise.allSettled([fetch("/health").then((response) => response.json()), fetch("/api/meta").then((response) => response.json())]).then(([health, meta]) => {
  if (health.status === "fulfilled") {
    state.llmConfigured = Boolean(health.value.llm_configured);
    $("engine-mode").querySelector("span").textContent = state.llmConfigured ? t("llmReady") : t("offline");
  }
  if (meta.status === "fulfilled") state.meta = meta.value;
});
setLanguage("zh");
