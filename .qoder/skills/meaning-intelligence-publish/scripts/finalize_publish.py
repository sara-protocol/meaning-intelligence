#!/usr/bin/env python3
"""Apply deterministic bilingual, provenance and accessibility fixes after page builds."""
from __future__ import annotations

import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")

PACKAGE = Path(__file__).resolve().parents[2] / "意义智能有声读物_发布包"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        return text.replace(old, new, 1)
    if new not in text:
        raise RuntimeError(f"Expected source not found: {label}")
    return text


def finalize_accessibility(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if 'class="mi-skip-link"' in text:
        return
    marker = next((value for value in ('<main', '<div class="wrap"') if value in text), None)
    if marker is None:
        raise RuntimeError(f"Accessibility target not found: {path.name}")
    start = text.index(marker)
    end = text.index(">", start)
    tag = text[start:end]
    if 'id="main"' not in tag:
        tag += ' id="main"'
    if 'tabindex="-1"' not in tag:
        tag += ' tabindex="-1"'
    text = text[:start] + tag + text[end:]
    css = ('<style>.mi-skip-link{position:absolute;left:16px;top:-96px;z-index:999;'
           'background:#e8b34b;color:#0b1020;padding:10px 16px;border-radius:8px;'
           'font:700 15px system-ui,"Microsoft YaHei",sans-serif}'
           '.mi-skip-link:focus{top:12px;outline:3px solid #5ad1e6;outline-offset:3px}</style>')
    text = text.replace("</head>", css + "\n</head>", 1)
    text = text.replace("<body>", '<body>\n<a class="mi-skip-link" href="#main">跳转到正文 / Skip to content</a>', 1)
    path.write_text(text, encoding="utf-8")


def finalize_listen(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    replacements = {
        "<b>E1</b>逻辑论证": "<b>E1</b>数学模型",
        "<b>E2</b>案例支持": "<b>E2</b>测量工具，信效度验证中",
        "<b>E3</b>观察证据": "<b>E3</b>预注册假设，数据收集中",
        "<b>E4</b>实验验证": "<b>E4</b>独立实验室复现",
        "<b>E5</b>跨情境复现": "<b>E5</b>预注册证伪标准已检验",
        "<b>E6</b>跨文化外部验证": "<b>E6</b>跨情境、跨文化、跨时间泛化",
        "实验全部预注册": "实验路径要求预注册",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    old_ladder = """      <div class="step"><b>E0</b>概念定义</div>
      <div class="step"><b>E1</b>数学模型</div>
      <div class="step"><b>E2</b>测量工具，信效度验证中</div>
      <div class="step"><b>E3</b>预注册假设，数据收集中</div>
      <div class="step"><b>E4</b>独立实验室复现</div>
      <div class="step"><b>E5</b>预注册证伪标准已检验</div>
      <div class="step e6"><b>E6</b>跨情境、跨文化、跨时间泛化</div>"""
    new_ladder = """      <div class="step"><b>E0</b><span data-zh>概念定义</span><span data-en>Construct defined</span></div>
      <div class="step"><b>E1</b><span data-zh>数学模型</span><span data-en>Mathematical model</span></div>
      <div class="step"><b>E2</b><span data-zh>测量工具，信效度验证中</span><span data-en>Instrument; validation under way</span></div>
      <div class="step"><b>E3</b><span data-zh>预注册假设，数据收集中</span><span data-en>Preregistered; data collection under way</span></div>
      <div class="step"><b>E4</b><span data-zh>独立实验室复现</span><span data-en>Independent-lab replication</span></div>
      <div class="step"><b>E5</b><span data-zh>预注册证伪标准已检验</span><span data-en>Preregistered falsification tested</span></div>
      <div class="step e6"><b>E6</b><span data-zh>跨情境、跨文化、跨时间泛化</span><span data-en>Generalization across contexts, cultures, time</span></div>"""
    text = replace_once(text, old_ladder, new_ladder, "evidence ladder")

    old_cards = """      <div class="mini"><b>核心诊断：力量与意义的分离</b>
        <p>逻辑、计算、感知智能越来越强，但"判断一件事值不值得做"从未被理论化、工程化。AI 能回答"怎么做到"，回答不了"为了什么"。</p></div>
      <div class="mini"><b>意义智能 = 元智能</b>
        <p>不是与 IQ / EQ 并列，而是在所有智能活动之上做<b style="display:inline;color:var(--cyan)">方向性调控</b>：其他智能回答"能不能做"，意义智能回答"值不值得做、对谁值得、在什么尺度上值得"。</p></div>
      <div class="mini"><b>三大拐点叠加（为什么是现在）</b>
        <p>① 技术拐点：AGI 与生物工程让"能做的事"激增；② 社会拐点：信任危机，旧意义体系松动；③ 认知拐点：信息过载，人们渴望意义锚点。</p></div>
      <div class="mini"><b>三条科学验证战线</b>
        <p>① 文明风险科学：失稳风险能否量化；② 认知跃迁科学：跃迁能否被观察与训练；③ 意义 AI 工程：能否提升长期决策质量。</p></div>"""
    new_cards = """      <div class="mini"><b data-zh>核心诊断：力量与意义的分离</b><b data-en>Core diagnosis: capability without direction</b>
        <p data-zh>逻辑、计算、感知智能越来越强，但"判断一件事值不值得做"尚未形成统一操作化。AI 能回答"怎么做到"，仍需回答"为了什么"。</p><p data-en>Logical, computational and perceptual capabilities are growing, while judging what is worth doing remains under-operationalized. AI can answer how; it still needs to answer why.</p></div>
      <div class="mini"><b data-zh>意义智能 = 元智能</b><b data-en>Meaning intelligence = meta-intelligence</b>
        <p data-zh>不是与 IQ / EQ 并列，而是在所有智能活动之上做<b style="display:inline;color:var(--cyan)">方向性调控</b>：其他智能回答"能不能做"，意义智能回答"值不值得做、对谁值得、在什么尺度上值得"。</p><p data-en>Not a peer of IQ or EQ, but directional regulation of intelligent activity: other capabilities ask whether something can be done; meaning intelligence asks whether it is worth doing, for whom, and at what scale.</p></div>
      <div class="mini"><b data-zh>三大拐点叠加（为什么是现在）</b><b data-en>Three converging turning points</b>
        <p data-zh>① 技术拐点：AGI 与生物工程让"能做的事"激增；② 社会拐点：信任危机，旧意义体系松动；③ 认知拐点：信息过载，人们渴望意义锚点。</p><p data-en>Technology expands possible action; social trust and old meaning systems weaken; information overload increases demand for direction.</p></div>
      <div class="mini"><b data-zh>三条科学验证战线</b><b data-en>Three empirical research fronts</b>
        <p data-zh>① 文明风险科学：失稳风险能否量化；② 认知跃迁科学：跃迁能否被观察与训练；③ 意义 AI 工程：能否提升长期决策质量。</p><p data-en>Quantify civilizational instability; observe and train meaningful leaps; test whether meaning-aware AI improves long-term decisions.</p></div>"""
    text = replace_once(text, old_cards, new_cards, "intro cards")

    css = """<style>[data-en]{display:none}html[lang="en"] [data-zh]{display:none}html[lang="en"] [data-en]{display:inline}html[lang="en"] p[data-en],html[lang="en"] b[data-en]{display:block}</style>"""
    if "[data-en]{display:none}" not in text:
        text = text.replace("</head>", css + "\n</head>", 1)
    text = text.replace("document.documentElement.lang=l==='zh'?'zh-CN':'en';",
                        "document.documentElement.lang=l==='zh'?'zh-CN':'en';document.documentElement.classList.toggle('en',l==='en');")
    path.write_text(text, encoding="utf-8")


def finalize_index(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace('poster="assets/video/MeaningIntelligenceScene.mp4"', 'poster="assets/cover.jpg"')
    text = text.replace("18 幅书稿原版插图", "18 幅项目示意图")
    text = text.replace("18 figures from the V7 edition", "18 project illustrations")
    text = text.replace('id="cpBtn" data-en', 'id="cpBtnEn" data-en')
    text = text.replace("const b=document.getElementById('cpBtn');const old=b.textContent;",
                        "const b=document.documentElement.classList.contains('en')?document.getElementById('cpBtnEn'):document.getElementById('cpBtn');const old=b.textContent;")
    text = text.replace("function setL(l){document.documentElement.classList.toggle('en',l==='en');",
                        "function setL(l){document.documentElement.classList.toggle('en',l==='en');document.documentElement.lang=l==='en'?'en':'zh-CN';")
    links = []
    if (PACKAGE / "downloads.html").is_file():
        links.append('<a class="btn sec" href="downloads.html" data-zh>下载中心</a><a class="btn sec" href="downloads.html" data-en>Downloads</a>')
    if (PACKAGE / "project-guide" / "index.html").is_file():
        links.append('<a class="btn sec" href="project-guide/" data-zh>双语项目说明书</a><a class="btn sec" href="project-guide/" data-en>Project Guide</a>')
    if (PACKAGE / "mcp.html").is_file():
        links.append('<a class="btn sec" href="mcp.html" data-zh>Web MCP</a><a class="btn sec" href="mcp.html" data-en>Web MCP</a>')
    if links and 'data-mi-extra-links' not in text:
        extra = '      <div data-mi-extra-links>' + "".join(links) + '</div>\n'
        markers = ('<!-- 播放器 -->', '<div class="player"', '<h2 data-zh>双语有声读物', '<h2 class="sec"')
        marker = next((value for value in markers if value in text), None)
        if marker is not None:
            text = text.replace(marker, extra + marker, 1)
        elif "</header>" in text:
            text = text.replace("</header>", extra + "</header>", 1)
        else:
            text = text.replace("<body>", "<body>\n" + extra, 1)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    listen = PACKAGE / "listen.html"
    index = PACKAGE / "index.html"
    if not listen.is_file() or not index.is_file():
        raise RuntimeError("Publication package is missing index.html or listen.html")
    finalize_listen(listen)
    finalize_index(index)
    for name in ("index.html", "listen.html", "downloads.html", "mcp.html"):
        page = PACKAGE / name
        if page.is_file():
            finalize_accessibility(page)
    print("PASS deterministic publication finalization applied")


if __name__ == "__main__":
    main()
