(() => {
  "use strict";
  const data = window.GUIDE_CONTENT;
  if (!data || !Array.isArray(data.chapters)) throw new Error("Guide content is unavailable.");
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const audio = $("#narration");
  const storage = {
    get(key, fallback) { try { return localStorage.getItem(key) ?? fallback; } catch (_) { return fallback; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (_) {} }
  };
  const state = {
    lang: storage.get("mi-guide-language", "zh") === "en" ? "en" : "zh",
    chapter: 0,
    speed: Number(storage.get("mi-guide-speed", "1")),
    subtitles: storage.get("mi-guide-subtitles", "on") !== "off",
    search: "",
    msiTime: 0,
    errors: []
  };
  if (![0.75, 1, 1.25, 1.5, 2].includes(state.speed)) state.speed = 1;
  window.addEventListener("error", (event) => state.errors.push(String(event.message || "unknown")));
  const ui = () => data.ui[state.lang];
  const chapter = () => data.chapters[state.chapter];
  const text = (value) => value?.[state.lang] || "";
  const pad = (value) => String(value).padStart(2, "0");
  function formatTime(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
    const whole = Math.floor(seconds);
    const hours = Math.floor(whole / 3600);
    const minutes = Math.floor((whole % 3600) / 60);
    const secs = whole % 60;
    return hours ? `${hours}:${pad(minutes)}:${pad(secs)}` : `${pad(minutes)}:${pad(secs)}`;
  }
  function esc(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  }
  function announce(message) { $("#announcer").textContent = message; }
  function chapterNumber(index) { return state.lang === "zh" ? `${ui().chapterLabel} ${index + 1} ${ui().chapterUnit}` : `${ui().chapterLabel} ${index + 1}`; }

  function renderStatic() {
    const t = ui();
    document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
    document.title = `${text(data.meta.title)} · ${data.meta.canon}`;
    $('meta[name="description"]').setAttribute("content", text(data.meta.description));
    $$('[data-i18n]').forEach((element) => {
      const key = element.dataset.i18n;
      if (t[key]) element.textContent = t[key];
    });
    $("#brand-title").textContent = state.lang === "zh" ? "意义智能" : "Meaning Intelligence";
    $("#brand-sub").textContent = t.brandSub;
    $("#language-label").textContent = t.languageLabel;
    $("#language-toggle-text").textContent = t.switchLanguage;
    $("#language-toggle").setAttribute("aria-label", `${t.languageLabel}: ${t.switchLanguage}`);
    $("#topnav").setAttribute("aria-label", t.contents);
    $("#chapter-nav").setAttribute("aria-label", t.chaptersTitle);
    $("#hero-eyebrow").textContent = t.heroEyebrow;
    $("#hero-title").textContent = t.heroTitle;
    $("#hero-subtitle").textContent = t.heroSubtitle;
    $("#hero-description").textContent = t.heroDescription;
    $("#hero-chips").innerHTML = [t.canonChip, t.researchChip, t.paperChip, t.msiChip, t.stackChip].map((label) => `<span class="chip">${esc(label)}</span>`).join("");
    $("#chapter-search").placeholder = t.searchPlaceholder;
    $("#footer-note").textContent = t.footerNote;
    $("#footer-generated").textContent = `${t.generated}: ${data.meta.generated}`;
    $("#footer-version").textContent = state.lang === "zh" ? `手册 v${data.meta.version} · 正典 ${data.meta.canon}` : `Guide v${data.meta.version} · Canon ${data.meta.canon}`;
    $("#play-pause").setAttribute("aria-label", audio.paused ? t.play : t.pause);
    $("#previous-chapter").setAttribute("aria-label", t.previous);
    $("#next-chapter").setAttribute("aria-label", t.next);
    $("#progress").setAttribute("aria-label", t.progress);
    $("#volume").setAttribute("aria-label", t.volume);
    $("#speed").setAttribute("aria-label", t.speed);
    $("#chapter-select").setAttribute("aria-label", t.chapter);
    $("#toggle-subtitles").textContent = state.subtitles ? t.hideSubtitles : t.showSubtitles;
    $("#toggle-subtitles").setAttribute("aria-pressed", String(state.subtitles));
    $("#subtitle-box").hidden = !state.subtitles;
  }

  function renderNavigation() {
    const select = $("#chapter-select");
    select.innerHTML = data.chapters.map((item, index) => `<option value="${index}">${esc(chapterNumber(index))} · ${esc(text(item.title))}</option>`).join("");
    select.value = String(state.chapter);
    const query = state.search.trim().toLocaleLowerCase();
    const matches = data.chapters.map((item, index) => {
      const haystack = `${text(item.title)} ${text(item.summary)} ${text(item.eyebrow)}`.toLocaleLowerCase();
      return !query || haystack.includes(query);
    });
    $("#chapter-nav").innerHTML = data.chapters.map((item, index) => matches[index] ? `<a href="#chapter-${item.id}" data-nav-index="${index}" class="${index === state.chapter ? "active" : ""}"><span>${pad(index + 1)}</span><span>${esc(text(item.title))}</span></a>` : "").join("");
    $$('[data-nav-index]').forEach((link) => link.addEventListener("click", () => {
      const index = Number(link.dataset.navIndex);
      if (index !== state.chapter) selectChapter(index, false);
    }));
    $$("[data-chapter]").forEach((element) => { element.hidden = !matches[Number(element.dataset.chapter)]; });
    $("#no-results").hidden = matches.some(Boolean);
  }

  function renderChapter(item, index) {
    const pending = item.pending ? `<section class="pending"><h4>${esc(ui().pendingLabel)}</h4><p>${esc(text(item.pending))}</p></section>` : "";
    const commands = item.commands ? `<div class="command-list">${item.commands.map((command) => `<div class="command-row"><code>${esc(command)}</code><button type="button" data-copy="${esc(command)}">${esc(ui().copyCommand)}</button></div>`).join("")}</div>` : "";
    return `<article class="chapter" id="chapter-${item.id}" data-chapter="${index}" aria-labelledby="title-${item.id}">
      <header class="chapter-header"><div class="chapter-number">${pad(index + 1)}</div><div><p class="eyebrow">${esc(text(item.eyebrow))}</p><h3 id="title-${item.id}">${esc(text(item.title))}</h3><p class="chapter-summary">${esc(text(item.summary))}</p></div></header>
      <div class="chapter-body"><div class="chapter-prose">${item.paragraphs[state.lang].map((paragraph) => `<p>${esc(paragraph)}</p>`).join("")}${commands}</div><aside class="key-card"><h4>${esc(ui().keyPoints)}</h4><ul>${item.bullets[state.lang].map((bullet) => `<li>${esc(bullet)}</li>`).join("")}</ul></aside></div>
      <section class="practice"><h4>${esc(ui().practiceLabel)}</h4><p>${esc(text(item.practice))}</p></section>
      ${pending}
      <p class="source-trail"><strong>${esc(ui().sourceTrail)}:</strong> ${esc(text(item.source))}</p>
      <div class="chapter-actions"><a class="button secondary" href="#listen" data-listen-index="${index}">${esc(ui().listenChapter)}</a><button class="button secondary" type="button" data-open-chapter="${index}">${esc(ui().readChapter)}</button></div>
      ${renderVisual(item, index)}
    </article>`;
  }

  function renderChapters() {
    $("#chapters").innerHTML = data.chapters.map(renderChapter).join("");
    $$('[data-listen-index]').forEach((button) => button.addEventListener("click", () => {
      selectChapter(Number(button.dataset.listenIndex), true);
      $("#listen").scrollIntoView({ behavior: "smooth", block: "start" });
    }));
    $$('[data-open-chapter]').forEach((button) => button.addEventListener("click", () => {
      const target = $(`#chapter-${data.chapters[Number(button.dataset.openChapter)].id}`);
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      $("#chapter-search").value = "";
      state.search = "";
      renderNavigation();
    }));
    $$('[data-copy]').forEach((button) => button.addEventListener("click", () => copyText(button.dataset.copy, button)));
    $$('[data-act-start]').forEach((button) => button.addEventListener("click", () => {
      const video = $("#msi-video");
      if (!video) return;
      video.currentTime = Number(button.dataset.actStart);
      video.play().catch(() => {});
    }));
    const msiVideo = $("#msi-video");
    if (msiVideo) {
      msiVideo.addEventListener("timeupdate", () => { state.msiTime = msiVideo.currentTime; });
      msiVideo.addEventListener("loadedmetadata", () => { if (state.msiTime) msiVideo.currentTime = state.msiTime; });
    }
    $$(".visual-content > img").forEach((image) => image.addEventListener("click", () => openFigure(image, image.closest("figure"))));
  }

  function renderVisual(item) {
    const visual = item.visual;
    let content = "";
    if (visual.kind === "image" || visual.kind === "msi") {
      content = `<img src="assets/figures/${state.lang}/${visual.asset}.jpg" alt="${esc(text(visual.alt))}" loading="lazy" decoding="async">`;
    }
    if (visual.kind === "provenance") content = `<p class="diagram-notice">${esc(ui().diagramNotice)}</p><div class="flow-grid">${[
      ["01", text({ zh: "KDP 定稿02中文 V7", en: "KDP Final 02 Chinese V7" }), text({ zh: "主正典 · 记录哈希", en: "Primary canon · recorded hash" })],
      ["02", "Meaning IntelligenceV7.docx", text({ zh: "英文校对母本", en: "English proof mother" })],
      ["03", text({ zh: "白皮书 v1.1", en: "White paper v1.1" }), text({ zh: "应用层摘要", en: "Application-layer summary" })],
      ["04", "msi/config.json", text({ zh: "E0 工程实现", en: "E0 engineering implementation" })],
      ["05", "README / CHANGELOG", text({ zh: "传播材料 · 最低权威", en: "Communication · lowest authority" })]
    ].map(([number, title, detail], index) => `<div class="flow-node ${index === 0 ? "gold" : ""}"><strong>${esc(number)} · ${esc(title)}</strong><span>${esc(detail)}</span></div>`).join("")}</div>`;
    if (visual.kind === "evidence") content = `<p class="diagram-notice">${esc(ui().diagramNotice)}</p><div class="evidence-ladder">${data.evidence.map((level) => `<div class="evidence-step"><b>${level.id}</b><strong>${esc(text(level.name))}</strong><span>${esc(text(level.definition))}</span></div>`).join("")}</div>`;
    if (visual.kind === "spectrum") content = `<p class="diagram-notice">${esc(ui().diagramNotice)}</p><div class="spectrum-band"><div class="spectrum-rail"></div><div class="spectrum-labels">${data.layers.map((layer) => `<span><b>${layer.id}</b>${esc(text(layer.name))}</span>`).join("")}</div></div><div class="flow-grid" style="margin-top:12px">${[
      [text({ zh: "方向", en: "Direction" }), text({ zh: "变化会走向哪里", en: "Where change is headed" })],
      [text({ zh: "价值", en: "Value" }), text({ zh: "为什么值得", en: "Why it is worthwhile" })],
      [text({ zh: "边界", en: "Boundary" }), text({ zh: "哪些条件构成限制", en: "Which conditions constrain action" })]
    ].map(([title, detail], index) => `<div class="flow-node ${index === 0 ? "purple" : index === 1 ? "gold" : ""}"><strong>${esc(title)}</strong><span>${esc(detail)}</span></div>`).join("")}</div>`;
    if (visual.kind === "scales") content = `<p class="diagram-notice">${esc(ui().diagramNotice)}</p><div class="scale-grid">${data.scales.map((scale) => `<div class="scale-node"><strong>${esc(text(scale.name))}</strong><span>${esc(text({ zh: "不可通约", en: "Incommensurable" }))}</span></div>`).join("")}</div><div class="flow-grid" style="margin-top:12px"><div class="flow-node gold"><strong>${esc(text({ zh: "递归校准", en: "Recursive calibration" }))}</strong><span>${esc(text({ zh: "冲突 · 优先级 · 代价 · 触发器", en: "Conflicts · priorities · costs · triggers" }))}</span></div><div class="flow-node"><strong>${esc(text({ zh: "禁止", en: "Forbidden" }))}</strong><span>${esc(text({ zh: "补偿性加权求和", en: "Compensatory weighted summation" }))}</span></div></div>`;
    if (visual.kind === "mapping") content = `<p class="diagram-notice">${esc(ui().diagramNotice)}</p><div class="band-stack">${data.bands.map((band) => `<div class="band ${band.id}"><h4>${esc(text(band.name))}</h4><div><p>${esc(text(band.problem))}</p><div class="layer-list">${data.layers.filter((layer) => layer.band === band.id).map((layer) => `<div class="layer-line"><b>${layer.id}</b><span>${esc(text(layer.name))} · ${esc(text(layer.output))}</span><em>${esc(text(layer.status))}</em></div>`).join("")}</div></div></div>`).join("")}</div><div class="flow-grid" style="margin-top:12px"><div class="flow-node"><strong>M1 · ${esc(text({ zh: "感知", en: "Perception" }))}</strong><span>F1 · ${esc(text({ zh: "意义识别", en: "Meaning identification" }))}</span></div><div class="flow-node purple"><strong>M2 · ${esc(text({ zh: "判断", en: "Judgment" }))}</strong><span>F2 · ${esc(text({ zh: "意义评估", en: "Meaning assessment" }))}</span></div><div class="flow-node gold"><strong>M3 · ${esc(text({ zh: "行动", en: "Action" }))}</strong><span>F3 · ${esc(text({ zh: "意义决策", en: "Meaning decision" }))} → F4 · ${esc(text({ zh: "意义反馈", en: "Meaning feedback" }))}</span></div></div>`;
    if (visual.kind === "skills") content = `<p class="diagram-notice">${esc(ui().diagramNotice)}</p><div class="skill-grid">${data.skills.map((skill) => `<div class="skill-card"><header><b>${skill.layer}</b><strong>${esc(text(skill.title))}</strong></header><code>${esc(skill.name)}</code><p>${esc(text(skill.output))}<br>${esc(text(skill.limit))}</p></div>`).join("")}</div><div class="flow-grid" style="margin-top:12px"><div class="flow-node"><strong>${esc(text({ zh: "结构化结果", en: "Structured result" }))}</strong><span>${esc(text({ zh: "来源 · 限制 · 待澄清", en: "Provenance · limits · clarification" }))}</span></div><div class="flow-node gold"><strong>${esc(text({ zh: "人工批准门", en: "Human approval gate" }))}</strong><span>approval.status=pending<br>execution_authorized=false</span></div></div>`;
    if (visual.kind === "terminal") {
      const sample = state.lang === "zh" ? "试点是否应该扩大？" : "Should the pilot expand?";
      content = `<div class="terminal"><span class="prompt">PS C:\\meaning-agent&gt;</span> python -m meaning_agent analyze --text "${sample}" --json\n\n{\n  "mode": "offline",\n  "status": "pending_human_approval",\n  "skills": {"L1": …, "L2": …, "L3": …, "L4": …, "L5": …, "L6": …},\n  "approval": {"status": "pending", "execution_authorized": false},\n  "safety": {"arbitrary_file_or_command_execution": false}\n}</div>`;
    }
    if (visual.kind === "approval") content = `<p class="diagram-notice">${esc(ui().diagramNotice)}</p><div class="flow-grid"><div class="flow-node"><strong>${esc(text({ zh: "分析", en: "Analyze" }))}</strong><span>status=pending_human_approval</span></div><div class="flow-node purple"><strong>${esc(text({ zh: "人工复核", en: "Human review" }))}</strong><span>approved / rejected</span></div><div class="flow-node gold"><strong>${esc(text({ zh: "记录决定", en: "Record decision" }))}</strong><span>execution_authorized=false</span></div><div class="flow-node"><strong>${esc(text({ zh: "检测到修订", en: "Revision detected" }))}</strong><span>${esc(text({ zh: "批准重置为 pending", en: "Approval resets to pending" }))}</span></div></div>`;
    if (visual.kind === "mcp") content = `<p class="diagram-notice">${esc(ui().diagramNotice)}</p><div class="mcp-boundary"><div class="flow-node"><strong>${esc(text({ zh: "客户端", en: "Client" }))}</strong><span>JSON-RPC 2.0</span></div><div class="arrow" aria-hidden="true">→</div><div class="flow-node gold"><strong>POST /api/mcp</strong><span>2025-03-26 · 32 KiB<br>Bearer · Origin · 60/min</span></div><div class="arrow" aria-hidden="true">→</div><div class="flow-node"><strong>${esc(text({ zh: "固定只读表面", en: "Fixed read-only surface" }))}</strong><span>${esc(text({ zh: "资源 · 分析 · 复核 · 清单", en: "Resources · analysis · review · manifest" }))}</span></div></div><div class="mcp-tool-list">${["meaning_analyze", "meaning_review", "resource_catalog", "evidence_levels", "download_manifest"].map((name) => `<code>${name}</code>`).join("")}</div><div class="flow-grid" style="margin-top:12px"><div class="flow-node"><strong>${esc(text({ zh: "允许", en: "Allowed" }))}</strong><span>meaning:// · mi:// · same-origin manifest</span></div><div class="flow-node gold"><strong>${esc(text({ zh: "边界之外", en: "Outside the boundary" }))}</strong><span>${esc(text({ zh: "任意 URL · 文件 · shell · 凭据 · 执行", en: "Arbitrary URL · files · shell · credentials · execution" }))}</span></div></div>`;
    if (visual.kind === "msi") content = `${content}<p class="video-notice">${esc(ui().videoNotice)}</p><video id="msi-video" class="video-frame" controls preload="metadata" playsinline src="downloads/msi-eight-acts-43s.mp4"></video><div class="act-grid">${data.acts.map((act, index) => `<div class="act-card"><span class="act-time">${pad(index + 1)} · ${act.start.toFixed(3)} s</span><strong>${esc(text(act.title))}</strong><p>${esc(text(act.detail))}</p><button type="button" data-act-start="${act.start}">${esc(ui().playAct)}</button></div>`).join("")}</div>`;
    if (visual.kind === "library") content = `<div class="library-grid">${[
      [text({ zh: "文档", en: "Documents" }), text({ zh: "PDF / DOCX · 22 页 · 9 表 · 3 图", en: "PDF / DOCX · 22 pages · 9 tables · 3 figures" })],
      [text({ zh: "电子书", en: "Ebooks" }), text({ zh: "EPUB · 中文 / 英文 / 双语", en: "EPUB · Chinese / English / bilingual" })],
      [text({ zh: "音频", en: "Audio" }), text({ zh: "MP3 · 逐章中英文旁白", en: "MP3 · per-chapter Chinese and English narration" })],
      [text({ zh: "视频", en: "Video" }), text({ zh: "MP4 · 43.433 s · H.264 · 无声", en: "MP4 · 43.433 s · H.264 · silent" })],
      [text({ zh: "源码", en: "Source" }), text({ zh: "ZIP · v0.2.0 · 智能体与测试", en: "ZIP · v0.2.0 · agent and tests" })],
      [text({ zh: "校验", en: "Verification" }), text({ zh: "SHA-256 · bytes · media facts", en: "SHA-256 · bytes · media facts" })]
    ].map(([title, detail]) => `<div class="library-card"><strong>${esc(title)}</strong><span>${esc(detail)}</span></div>`).join("")}</div>`;
    if (visual.kind === "pipeline") content = `<p class="diagram-notice">${esc(ui().diagramNotice)}</p><div class="pipeline">${[
      ["01", text({ zh: "修改源材料", en: "Edit source" }), "content / scripts / assets"],
      ["02", text({ zh: "重建派生文件", en: "Rebuild derivatives" }), text({ zh: "音频 · 字幕 · 文档 · 页面", en: "Audio · captions · documents · pages" })],
      ["03", text({ zh: "测试与校验", en: "Test and verify" }), text({ zh: "结构 · 媒体 · 哈希", en: "Structure · media · hashes" })],
      ["04", text({ zh: "人工浏览器验收", en: "Human browser acceptance" }), text({ zh: "语言 · 播放 · 无障碍", en: "Language · playback · accessibility" })],
      ["05", text({ zh: "生成部署 ZIP", en: "Build deployment ZIP" }), text({ zh: "根目录 index.html", en: "index.html at ZIP root" })],
      ["06", text({ zh: "明确授权门", en: "Explicit authorization gate" }), text({ zh: "未授权不部署", en: "No deployment without authorization" })],
      ["07", text({ zh: "授权后部署", en: "Authorized deployment" }), "wrangler pages deploy"],
      ["08", text({ zh: "线上复验", en: "Online re-verification" }), text({ zh: "资源 · MCP · 下载", en: "Resources · MCP · downloads" })]
    ].map(([number, title, detail]) => `<div class="pipeline-step"><b>${number}</b><strong>${esc(title)}</strong><span>${esc(detail)}</span></div>`).join("")}</div>`;
    if (visual.kind === "security") content = `<div class="security-layers">${[
      [text({ zh: "输入", en: "Input" }), text({ zh: "脱敏 · 20,000 字符 · 深度限制", en: "Redaction · 20,000 characters · depth limits" })],
      [text({ zh: "传输", en: "Transport" }), text({ zh: "回环 · TLS · Host / Origin", en: "Loopback · TLS · Host / Origin" })],
      [text({ zh: "资源", en: "Resources" }), text({ zh: "固定白名单 · 同源 · CSP", en: "Fixed allowlist · same-origin · CSP" })],
      [text({ zh: "凭据", en: "Credentials" }), text({ zh: "环境密钥 · 不回显 · 不落盘", en: "Environment secrets · no echo · no persistence" })],
      [text({ zh: "执行", en: "Execution" }), text({ zh: "只读 · 人工批准 · 不授权执行", en: "Read-only · human approval · no execution authorization" })]
    ].map(([title, detail]) => `<div class="security-layer"><b>${esc(title)}</b><span>${esc(detail)}</span></div>`).join("")}</div>`;
    if (visual.kind === "acceptance") content = `<div class="acceptance-grid">${[
      [text({ zh: "自动结构", en: "Automated structure" }), text({ zh: "文件 · JSON · 语法 · 容器", en: "Files · JSON · syntax · containers" })],
      [text({ zh: "自动媒体", en: "Automated media" }), text({ zh: "流 · 时长 · 非静音 · 字幕", en: "Streams · duration · non-silence · captions" })],
      [text({ zh: "浏览器", en: "Browser" }), text({ zh: "切换 · 播放 · 字幕 · 离线", en: "Switching · playback · subtitles · offline" })],
      [text({ zh: "人工", en: "Human" }), text({ zh: "键盘 · 读屏 · 移动端 · 内容", en: "Keyboard · screen reader · mobile · content" })],
      [text({ zh: "生产", en: "Production" }), text({ zh: "URL · 认证 · 限流 · 部署", en: "URLs · authentication · rate limits · deployment" })],
      [text({ zh: "权利", en: "Rights" }), text({ zh: "文稿 · 音频 · 图片 · 文档", en: "Scripts · audio · figures · documents" })]
    ].map(([title, detail]) => `<div class="acceptance-card"><strong>${esc(title)}</strong><span>${esc(detail)}</span></div>`).join("")}</div>`;
    return `<figure><div class="visual-toolbar"><span>${esc(ui().visualLabel)}</span>${visual.kind === "image" || visual.kind === "msi" ? `<button type="button" data-enlarge="${item.id}">${esc(ui().openFigure)}</button>` : ""}</div><div class="visual-content">${content}</div><figcaption><strong>${esc(ui().caption)}:</strong> ${esc(text(visual.caption))}</figcaption></figure>`;
  }

  function openFigure(image, figure) {
    const caption = $("figcaption", figure)?.textContent || "";
    $("#figure-dialog-content").innerHTML = `<img src="${esc(image.src)}" alt="${esc(image.alt)}"><p>${esc(caption)}</p>`;
    $("#figure-dialog").showModal();
  }

  function renderDownloads() {
    $("#download-grid").innerHTML = data.downloads.map((item) => `<article class="download-card"><span class="download-kind">${esc(text(item.kind))} · ${esc(ui().localFile)}</span><h3>${esc(text(item.title))}</h3><p>${esc(text(item.description))}</p><div class="download-meta"><small>${esc(item.path.split("/").pop())}</small><a href="${esc(item.path)}" download>${esc(ui().downloadButton)}</a></div></article>`).join("");
    const current = chapter();
    const isZh = state.lang === "zh";
    const title = isZh ? ui().ownAudio : ui().ownAudioEn;
    const captionTitle = isZh ? ui().ownCaptionsZh : ui().ownCaptionsEn;
    const transcriptTitle = isZh ? ui().ownTranscriptZh : ui().ownTranscriptEn;
    $("#narration-bundles").innerHTML = `<article class="bundle-card"><h3>${esc(title)}</h3><div class="bundle-links"><a href="audio/${state.lang}/${current.id}.mp3" download>${esc(ui().downloadAudio)}</a><a href="captions/${state.lang}/all-captions.zip" download>${esc(ui().downloadSrt)} + VTT</a></div></article><article class="bundle-card"><h3>${esc(captionTitle)} / ${esc(transcriptTitle)}</h3><div class="bundle-links"><a href="captions/${state.lang}/all-captions.zip" download>SRT + VTT</a><a href="transcripts/${state.lang}/all-transcripts.txt" download>${esc(ui().downloadTranscript)}</a></div></article>`;
  }

  function renderProofs() {
    const report = window.GUIDE_VERIFICATION;
    const groups = [
      ["structure", ui().proofLocal],
      ["bilingual", ui().proofBilingual],
      ["hash", ui().proofHashes],
      ["browser", ui().proofAccessible],
      ["media", ui().proofMedia]
    ];
    $("#proof-grid").innerHTML = groups.map(([category, title]) => {
      const checks = report?.checks?.filter((item) => item.category === category) || [];
      const ok = checks.length > 0 && checks.every((item) => item.ok);
      return `<article class="proof-card ${ok ? "" : "pending"}"><span class="status">${esc(ok ? ui().checkPassed : ui().checkPending)}</span><h3>${esc(title)}</h3><p>${checks.length ? `${checks.filter((item) => item.ok).length}/${checks.length} ${esc(ui().checkPassed.toLocaleLowerCase())}` : esc(ui().verificationIntro)}</p></article>`;
    }).join("") + `<article class="proof-card pending"><span class="status">${esc(ui().checkPending)}</span><h3>${esc(ui().proofPending)}</h3><p>${esc(ui().verificationIntro)}</p></article>`;
  }

  function renderPlayer() {
    const current = chapter();
    const cues = current.narration?.[state.lang] || [];
    $("#chapter-select").value = String(state.chapter);
    $("#speed").value = String(state.speed);
    $("#volume").value = String(audio.volume);
    $("#player-downloads").innerHTML = [
      [ui().downloadAudio, `audio/${state.lang}/${current.id}.mp3`],
      [ui().downloadSrt, `captions/${state.lang}/${current.id}.srt`],
      [ui().downloadVtt, `captions/${state.lang}/${current.id}.vtt`],
      [ui().downloadTranscript, `transcripts/${state.lang}/${current.id}.txt`]
    ].map(([label, path]) => `<a href="${path}" download>${esc(label)}</a>`).join("");
    $("#transcript-content").innerHTML = cues.length ? cues.map((cue, index) => `<div class="transcript-cue"><button type="button" data-cue-index="${index}">${formatTime(cue.start)}</button><p>${esc(cue.text)}</p></div>`).join("") : `<p>${esc(ui().playerLoading)}</p>`;
    $$('[data-cue-index]').forEach((button) => button.addEventListener("click", () => {
      const cue = cues[Number(button.dataset.cueIndex)];
      if (cue && Number.isFinite(audio.duration)) audio.currentTime = cue.start + 0.03;
      updateProgress();
    }));
    $$("#narration track").forEach((track) => track.remove());
    if (cues.length) {
      const track = document.createElement("track");
      track.kind = "subtitles";
      track.src = `captions/${state.lang}/${current.id}.vtt`;
      track.srclang = state.lang === "zh" ? "zh-CN" : "en";
      track.label = state.lang === "zh" ? "中文" : "English";
      track.default = true;
      audio.appendChild(track);
    }
  }

  function renderAll() {
    renderStatic();
    renderNavigation();
    renderChapters();
    renderDownloads();
    renderProofs();
    renderPlayer();
    bindFigureButtons();
  }

  function bindFigureButtons() {
    $$('[data-enlarge]').forEach((button) => button.addEventListener("click", () => {
      const id = button.dataset.enlarge;
      const figure = $(`#chapter-${id} figure`);
      const image = $(".visual-content > img", figure);
      if (image) openFigure(image, figure);
    }));
  }

  function loadAudio(ratio = 0, autoplay = false) {
    const current = chapter();
    audio.pause();
    const applyPosition = () => {
      if (Number.isFinite(audio.duration) && audio.duration > 0) {
        audio.currentTime = Math.min(Math.max(ratio, 0), .999) * audio.duration;
        audio.dispatchEvent(new Event("timeupdate"));
      }
      updateProgress();
      if (autoplay) audio.play().catch(() => {});
    };
    audio.addEventListener("loadedmetadata", applyPosition, { once: true });
    audio.src = `audio/${state.lang}/${current.id}.mp3`;
    audio.load();
    audio.playbackRate = state.speed;
    if (audio.readyState >= 1 && Number.isFinite(audio.duration)) {
      audio.removeEventListener("loadedmetadata", applyPosition);
      applyPosition();
    }
  }

  function setLanguage(lang, shouldAnnounce = true) {
    if (!data.ui[lang] || lang === state.lang) return;
    const ratio = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.currentTime / audio.duration : 0;
    const oldMsi = state.msiTime;
    audio.pause();
    state.lang = lang;
    storage.set("mi-guide-language", lang);
    renderAll();
    const newDuration = chapter().audioMeta?.[state.lang]?.duration || 0;
    const newCues = chapter().narration?.[state.lang] || [];
    const approximateTime = ratio * newDuration;
    const immediateCue = newCues.find((cue) => approximateTime >= cue.start && approximateTime < cue.end) || newCues[0];
    $("#current-subtitle").textContent = immediateCue?.text || "";
    loadAudio(ratio, false);
    state.msiTime = oldMsi;
    if (shouldAnnounce) announce(ui().languageSwitched);
  }

  function selectChapter(index, autoplay = false) {
    const next = Math.max(0, Math.min(data.chapters.length - 1, Number(index)));
    if (!Number.isFinite(next)) return;
    state.chapter = next;
    renderNavigation();
    renderDownloads();
    renderPlayer();
    loadAudio(0, autoplay);
    if (autoplay) audio.play().catch(() => {});
  }

  function updateProgress() {
    const duration = Number.isFinite(audio.duration) ? audio.duration : 0;
    const current = Number.isFinite(audio.currentTime) ? audio.currentTime : 0;
    const ratio = duration > 0 ? current / duration : 0;
    $("#progress").max = String(duration || 100);
    $("#progress").value = String(duration ? current : 0);
    $("#progress").style.setProperty("--progress", `${ratio * 100}%`);
    $("#progress").setAttribute("aria-valuetext", `${formatTime(current)} / ${formatTime(duration)}`);
    $("#elapsed").textContent = formatTime(current);
    $("#duration").textContent = formatTime(duration);
    const cues = chapter().narration?.[state.lang] || [];
    const cue = cues.find((item) => current >= item.start && current < item.end) || (current > 0 ? cues[cues.length - 1] : cues[0]);
    const subtitle = cue ? cue.text : "";
    if ($("#current-subtitle").textContent !== subtitle) $("#current-subtitle").textContent = subtitle;
    const status = audio.error ? ui().playerError : !audio.paused ? ui().playerPlaying : audio.readyState < 1 ? ui().playerLoading : ui().playerPaused;
    $("#player-status").textContent = status;
    $("#play-pause").setAttribute("aria-label", audio.paused ? ui().play : ui().pause);
    $("#play-pause").innerHTML = audio.paused ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"></path></svg>' : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h4v14H7zm6 0h4v14h-4z"></path></svg>';
  }

  async function copyText(value, button) {
    let copied = false;
    try { await navigator.clipboard.writeText(value); copied = true; } catch (_) {
      const area = document.createElement("textarea");
      area.value = value;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try { copied = document.execCommand("copy"); } catch (_) {}
      area.remove();
    }
    button.textContent = copied ? ui().copied : ui().copyFailed;
    setTimeout(() => { button.textContent = ui().copyCommand; }, 1800);
  }

  $("#language-toggle").addEventListener("click", () => setLanguage(state.lang === "zh" ? "en" : "zh"));
  $("#chapter-select").addEventListener("change", (event) => selectChapter(Number(event.target.value), false));
  $("#previous-chapter").addEventListener("click", () => selectChapter(state.chapter - 1, !audio.paused));
  $("#next-chapter").addEventListener("click", () => selectChapter(state.chapter + 1, !audio.paused));
  $("#play-pause").addEventListener("click", () => {
    if (audio.paused) audio.play().catch(() => announce(ui().audioUnavailable));
    else audio.pause();
  });
  $("#start-listening").addEventListener("click", () => {
    selectChapter(0, true);
    $("#listen").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  $("#speed").addEventListener("change", (event) => {
    state.speed = Number(event.target.value);
    audio.playbackRate = state.speed;
    storage.set("mi-guide-speed", String(state.speed));
  });
  $("#volume").addEventListener("input", (event) => { audio.volume = Number(event.target.value); });
  $("#toggle-subtitles").addEventListener("click", () => {
    state.subtitles = !state.subtitles;
    storage.set("mi-guide-subtitles", state.subtitles ? "on" : "off");
    renderStatic();
  });
  $("#progress").addEventListener("input", (event) => {
    if (Number.isFinite(audio.duration)) audio.currentTime = (Number(event.target.value) / audio.duration) * audio.duration;
    updateProgress();
  });
  $("#chapter-search").addEventListener("input", (event) => { state.search = event.target.value; renderNavigation(); });
  $("#close-figure").addEventListener("click", () => $("#figure-dialog").close());
  $("#figure-dialog").addEventListener("click", (event) => { if (event.target === $("#figure-dialog")) $("#figure-dialog").close(); });
  ["play", "pause", "loadedmetadata", "durationchange", "timeupdate", "seeked", "error"].forEach((name) => audio.addEventListener(name, updateProgress));
  audio.volume = Number(storage.get("mi-guide-volume", ".9"));
  $("#volume").value = String(audio.volume);

  function updateReadingProgress() {
    const scrollable = document.documentElement.scrollHeight - window.innerHeight;
    const ratio = scrollable > 0 ? window.scrollY / scrollable : 0;
    $("#reading-progress").style.width = `${Math.max(0, Math.min(1, ratio)) * 100}%`;
  }
  window.addEventListener("scroll", updateReadingProgress, { passive: true });
  window.addEventListener("resize", updateReadingProgress);
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      const index = Number(visible.target.dataset.chapter);
      $$("#chapter-nav a").forEach((link) => link.classList.toggle("active", Number(link.dataset.navIndex) === index));
    }, { rootMargin: "-15% 0px -65% 0px", threshold: [0, .1, .3] });
    data.chapters.forEach((item) => { const element = $(`#chapter-${item.id}`); if (element) observer.observe(element); });
  }

  renderAll();
  loadAudio(0, false);
  updateReadingProgress();
  window.GuideApp = { setLanguage, selectChapter, getState: () => ({ ...state }), formatTime };

  async function runSelfTest() {
    const checks = [];
    const check = (name, ok, detail = "") => checks.push({ name, ok: Boolean(ok), detail });
    const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const metadata = () => new Promise((resolve) => {
      if (audio.readyState >= 1 && Number.isFinite(audio.duration)) return resolve(true);
      const timer = setTimeout(() => resolve(false), 8000);
      audio.addEventListener("loadedmetadata", () => { clearTimeout(timer); resolve(true); }, { once: true });
      audio.addEventListener("error", () => { clearTimeout(timer); resolve(false); }, { once: true });
    });
    try {
      setLanguage("zh", false);
      await wait(80);
      check("zh-title", $("#hero-title").textContent.includes("方向舵"), $("#hero-title").textContent);
      check("zh-navigation", $("#chapter-nav").textContent.includes("项目总览"), $("#chapter-nav").textContent.slice(0, 120));
      check("zh-downloads", $("#download-grid").textContent.includes("下载"), "download labels");
      check("zh-figure", $$(".visual-content > img").some((image) => image.src.includes("/figures/zh/")), "Chinese figure source");
      setLanguage("en", false);
      const loaded = await metadata();
      check("audio-metadata", loaded && audio.duration > 5, `${audio.duration || 0}s`);
      check("en-title", $("#hero-title").textContent.includes("rudder"), $("#hero-title").textContent);
      check("en-navigation", $("#chapter-nav").textContent.includes("Project overview"), "English navigation");
      check("en-downloads", $("#download-grid").textContent.includes("Download"), "English download labels");
      check("en-figure", $$(".visual-content > img").some((image) => image.src.includes("/figures/en/")), "English figure source");
      check("en-audio-source", audio.src.includes("/audio/en/") && audio.src.endsWith("overview.mp3"), audio.src);
      const track = $("#narration track");
      check("en-track", track && track.srclang === "en" && track.src.endsWith("overview.vtt"), track?.src || "missing");
      check("chapter-count", $("#chapter-select").options.length === 18 && $$("[data-chapter]").length === 18, `${$("#chapter-select").options.length} chapters`);
      check("i18n-complete", $$('[data-i18n]').every((element) => element.textContent.trim().length > 0), `${$$('[data-i18n]').length} localized nodes`);
      check("image-alt", $$("img").every((image) => image.alt.trim().length > 0), `${$$("img").length} images`);
      check("button-names", $$("button").every((button) => (button.getAttribute("aria-label") || button.textContent).trim().length > 0), `${$$("button").length} buttons`);
      const overflow = [...document.querySelectorAll("body *")].filter((element) => {
        const box = element.getBoundingClientRect();
        return box.width > 0 && (box.right > window.innerWidth + 2 || element.scrollWidth > element.clientWidth + 2);
      }).slice(0, 8).map((element) => `${element.tagName}.${element.className}:${Math.round(element.getBoundingClientRect().right)}/${element.scrollWidth}`);
      check("mobile-layout", document.documentElement.scrollWidth <= window.innerWidth + 2, `${document.documentElement.scrollWidth}px content / ${window.innerWidth}px viewport; ${overflow.join(", ")}`);
      $$(".visual-content > img").forEach((image) => { image.loading = "eager"; });
      await wait(650);
      check("images-loaded", $$(".visual-content > img").every((image) => image.complete && image.naturalWidth > 0), `${$$(".visual-content > img").filter((image) => image.complete && image.naturalWidth > 0).length}/${$$(".visual-content > img").length} images`);
      const expected = data.chapters[0].audioMeta?.en?.duration || audio.duration;
      check("duration-match", Math.abs(audio.duration - expected) < .6, `${audio.duration}s vs ${expected}s`);
      $("#speed").value = "1.25";
      $("#speed").dispatchEvent(new Event("change", { bubbles: true }));
      check("playback-speed", audio.playbackRate === 1.25, String(audio.playbackRate));
      if (Number.isFinite(audio.duration)) audio.currentTime = audio.duration * .45;
      await wait(120);
      updateProgress();
      check("current-subtitle", $("#current-subtitle").textContent.trim().length > 0, $("#current-subtitle").textContent);
      check("progress-slider", Number($("#progress").max) > 5 && Number($("#progress").value) > 0, `${$("#progress").value}/${$("#progress").max}`);
      $("#toggle-subtitles").click();
      check("subtitle-toggle-off", $("#subtitle-box").hidden === true, "hidden");
      $("#toggle-subtitles").click();
      check("subtitle-toggle-on", $("#subtitle-box").hidden === false, "visible");
      $("#transcript-details").open = true;
      const firstCue = $("[data-cue-index]", $("#transcript-content"));
      const firstCueTime = Number(data.chapters[0].narration.en[0].start);
      firstCue?.click();
      check("transcript-seeking", Math.abs(audio.currentTime - firstCueTime) < .3, `${audio.currentTime}s vs ${firstCueTime}s`);
      $("#chapter-search").value = "V7.0";
      $("#chapter-search").dispatchEvent(new Event("input", { bubbles: true }));
      check("chapter-search", $$("[data-chapter]:not([hidden])").length > 0 && $$("[data-chapter]:not([hidden])").length < 18, `${$$("[data-chapter]:not([hidden])").length} matches`);
      $("#chapter-search").value = "";
      $("#chapter-search").dispatchEvent(new Event("input", { bubbles: true }));
      const enlarge = $("[data-enlarge]");
      enlarge?.click();
      check("figure-dialog", $("#figure-dialog").open === true, "dialog opened");
      $("#figure-dialog").close();
      audio.muted = true;
      try { await audio.play(); } catch (_) {}
      await wait(650);
      check("audio-playback", !audio.paused && audio.currentTime > 0, `${audio.currentTime}s paused=${audio.paused}`);
      audio.pause();
      selectChapter(1, false);
      const chapterMetadata = await metadata();
      check("chapter-switch", chapterMetadata && audio.src.endsWith("provenance.mp3") && $("#chapter-select").value === "1", audio.src);
      if (chapterMetadata && Number.isFinite(audio.duration) && audio.duration > 0) {
        audio.currentTime = audio.duration * .3;
        await wait(180);
      }
      const ratio = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.currentTime / audio.duration : 0;
      check("chapter-progress-seek", ratio > .2 && ratio < .4, `${ratio}`);
      setLanguage("zh", false);
      const languageMetadata = await metadata();
      await wait(120);
      check("language-audio-switch", languageMetadata && audio.src.includes("/audio/zh/") && audio.src.endsWith("provenance.mp3"), audio.src);
      check("language-caption-switch", $("#current-subtitle").textContent.trim().length > 0 && /[\u3400-\u9fff]/.test($("#current-subtitle").textContent), $("#current-subtitle").textContent);
      check("language-progress-preserved", Number.isFinite(audio.duration) && audio.duration > 0 && Math.abs(audio.currentTime / audio.duration - ratio) < .08, `${ratio} → ${audio.currentTime / audio.duration}`);
      await wait(500);
      const external = performance.getEntriesByType("resource").filter((entry) => /^https?:/.test(entry.name) && !["127.0.0.1", "localhost"].includes(new URL(entry.name).hostname));
      check("no-external-resources", external.length === 0, external.map((entry) => entry.name).join(", "));
      check("javascript-errors", state.errors.length === 0, state.errors.join(" | "));
      const result = { ok: checks.every((item) => item.ok), mode: location.protocol === "file:" ? "file" : "http", checks };
      window.__SELFTEST_RESULTS__ = result;
      $("#selftest-results").textContent = JSON.stringify(result);
      document.body.dataset.selftest = "complete";
    } catch (error) {
      const result = { ok: false, mode: location.protocol === "file:" ? "file" : "http", checks, error: String(error?.stack || error) };
      window.__SELFTEST_RESULTS__ = result;
      $("#selftest-results").textContent = JSON.stringify(result);
      document.body.dataset.selftest = "complete";
    }
  }
  if (new URLSearchParams(location.search).has("selftest")) runSelfTest();
})();
