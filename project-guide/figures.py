"""Language-specific, code-native guide illustrations (not canon figures)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1600, 900
BG, PANEL, CYAN, PURPLE, GOLD = "#08111d", "#102239", "#64dbe8", "#bba5f4", "#f2c46f"
TEXT, MUTED = "#edf4fb", "#a8bacd"


def font(size: int, lang: str = "zh", bold: bool = False) -> ImageFont.FreeTypeFont:
    name = ("msyhbd.ttc" if bold else "msyh.ttc") if lang == "zh" else ("segoeuib.ttf" if bold else "segoeui.ttf")
    path = Path("C:/Windows/Fonts") / name
    if not path.exists():
        path = Path("C:/Windows/Fonts") / ("segoeuib.ttf" if bold else "segoeui.ttf")
    return ImageFont.truetype(str(path), size)


def wrap(draw: ImageDraw.ImageDraw, value: str, face: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines, current = [], ""
    for char in value:
        candidate = current + char
        if draw.textlength(candidate, font=face) > max_width and current:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def text_block(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, size: int, lang: str, color: str = TEXT, max_width: int = 1200, bold: bool = False, spacing: int = 10) -> int:
    face = font(size, lang, bold)
    x, y = xy
    for line in wrap(draw, value, face, max_width):
        draw.text((x, y), line, font=face, fill=color)
        y += size + spacing
    return y


def base(lang: str, title: str, subtitle: str):
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    for x in range(0, WIDTH, 80):
        draw.line((x, 0, x, HEIGHT), fill="#0d1c2d", width=1)
    for y in range(0, HEIGHT, 80):
        draw.line((0, y, WIDTH, y), fill="#0d1c2d", width=1)
    draw.rounded_rectangle((54, 46, 1546, 854), radius=34, fill="#0a1626", outline="#274158", width=2)
    draw.text((94, 78), "MEANING INTELLIGENCE  /  V7.0", font=font(23, "en", True), fill=CYAN)
    text_block(draw, (94, 132), title, 52, lang, TEXT, 1380, True)
    text_block(draw, (94, 208), subtitle, 25, lang, MUTED, 1380)
    draw.line((94, 792, 1506, 792), fill="#274158", width=2)
    draw.text((94, 814), "GUIDE ILLUSTRATION · NOT A CANON FIGURE" if lang == "en" else "指南插图 · 非正典图", font=font(19, lang), fill=MUTED)
    draw.text((1370, 814), "2026-11-26", font=font(19, "en"), fill=MUTED)
    return image, draw


def card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, detail: str, lang: str, accent: str = CYAN) -> None:
    draw.rounded_rectangle(box, radius=22, fill=PANEL, outline=accent, width=2)
    x1, y1, x2, _ = box
    text_block(draw, (x1 + 24, y1 + 22), title, 29, lang, accent, x2 - x1 - 48, True)
    text_block(draw, (x1 + 24, y1 + 78), detail, 21, lang, MUTED, x2 - x1 - 48)


def make_figure(asset: str, lang: str) -> Image.Image:
    zh = lang == "zh"
    if asset == "fig1-1":
        image, draw = base(lang, "方向性调控，不是第四种能力" if zh else "Directional regulation, not a fourth capability", "意义智能为其他智能活动提供方向、价值与边界" if zh else "Meaning Intelligence supplies direction, value, and boundaries to other intelligent activities")
        card(draw, (470, 288, 1130, 432), "意义智能" if zh else "Meaning Intelligence", "方向 · 价值 · 边界" if zh else "Direction · value · boundary", lang, GOLD)
        for index, (title, detail) in enumerate((("M1 · 感知", "Perception"), ("M2 · 判断", "Judgment"), ("M3 · 行动", "Action"))):
            x = 115 + index * 475
            detail_text = ("信息如何进入" if zh else "How information enters") if index == 0 else ("证据如何判断" if zh else "How evidence is judged") if index == 1 else ("选择如何发生" if zh else "How choices occur")
            card(draw, (x, 528, x + 400, 710), title if zh else detail, detail_text, lang)
            draw.line((800, 432, x + 200, 528), fill=CYAN, width=4)
        return image
    if asset == "figC-1":
        image, draw = base(lang, "六层工程栈与三带" if zh else "Six-layer engineering stack and three bands", "E0 工程扩展 · 不是 V7.0 正典固定层级" if zh else "E0 engineering extension · not a fixed V7.0 canon hierarchy")
        rows = [("L1", "减负", "Load reduction", CYAN), ("L2", "可体验", "Experiential rendering", CYAN), ("L3", "意义生成", "Meaning generation", PURPLE), ("L4", "价值评估", "Value assessment", PURPLE), ("L5", "方向选择", "Direction selection", GOLD), ("L6", "反思递归", "Recursive review", GOLD)]
        for index, (layer, zh_name, en_name, accent) in enumerate(rows):
            y = 280 + index * 78
            draw.rounded_rectangle((180, y, 1300, y + 62), radius=14, fill=PANEL, outline=accent, width=2)
            draw.text((210, y + 13), layer, font=font(26, "en", True), fill=accent)
            draw.text((300, y + 13), zh_name if zh else en_name, font=font(26, lang, True), fill=TEXT)
            band = ("界面带" if index < 2 else "加工带" if index < 4 else "元带") if zh else ("Interface" if index < 2 else "Processing" if index < 4 else "Meta")
            draw.text((1230, y + 16), band, font=font(20, lang), fill=MUTED, anchor="ra")
        draw.line((1390, 704, 1390, 318, 1330, 318), fill=GOLD, width=4)
        draw.polygon([(1330, 318), (1352, 307), (1352, 329)], fill=GOLD)
        draw.text((1420, 500), "L6 → L1", font=font(22, "en", True), fill=GOLD, anchor="lm")
        return image
    if asset == "fig7-1":
        image, draw = base(lang, "MSI：八幕、四组关键计数" if zh else "MSI: eight acts and four key counts", "43.433 秒实测 · 1920×1080 · 60 fps · 无声" if zh else "43.433 s measured · 1920×1080 · 60 fps · silent")
        acts = [("01", "信息洪流" if zh else "Overload", "45"), ("02", "文本降维" if zh else "Reduction", "3"), ("03", "结构图" if zh else "Structure", "2"), ("04", "可操作界面" if zh else "Interface", "L2"), ("05", "意义归位" if zh else "Meaning", "D/V/B"), ("06", "证据着色" if zh else "Evidence", "9"), ("07", "路径选择" if zh else "Selection", "3"), ("08", "递归螺旋" if zh else "Recursion", "L1′")]
        for index, (number, title, count) in enumerate(acts):
            col, row = index % 4, index // 4
            x, y = 105 + col * 360, 292 + row * 224
            draw.rounded_rectangle((x, y, x + 320, y + 184), radius=20, fill=PANEL, outline=CYAN if row == 0 else PURPLE, width=2)
            draw.text((x + 22, y + 18), number, font=font(22, "en", True), fill=GOLD)
            draw.text((x + 22, y + 58), title, font=font(27, lang, True), fill=TEXT)
            draw.text((x + 22, y + 116), count, font=font(36, "en", True), fill=CYAN if row == 0 else PURPLE)
        return image
    if asset == "fig5-1":
        image, draw = base(lang, "正典、白皮书与工程实现的边界" if zh else "Boundaries among canon, white paper, and engineering", "摘要与实现不能反向改写理论来源" if zh else "Summaries and implementations cannot rewrite the theoretical source")
        card(draw, (490, 330, 1110, 526), "方向性调控" if zh else "Directional regulation", "本项目的意义智能构造" if zh else "The project's Meaning Intelligence construct", lang, GOLD)
        nodes = [("正典 V7.0" if zh else "Canon V7.0", "H1–H18 · D.7", 110, 290), ("白皮书 v1.1" if zh else "White paper v1.1", "22 页 · 12 claims" if zh else "22 pages · 12 claims", 1130, 290), ("工程栈 v2.0" if zh else "Stack v2.0", "L1–L6 · E0", 110, 580), ("智能体 v0.2.0" if zh else "Agent v0.2.0", "六技能 · 待批准" if zh else "Six skills · pending", 1130, 580)]
        for title, detail, x, y in nodes:
            card(draw, (x, y, x + 360, y + 138), title, detail, lang)
            draw.line((800, 430, x + 180, y + 69), fill="#39536d", width=3)
        return image
    if asset == "fig25-1":
        image, draw = base(lang, "发展路线图：完成与待定分开" if zh else "Roadmap: separate completion from pending work", "未来阶段不等于当前证据状态" if zh else "A future stage is not current evidence")
        stages = [("01", "来源审计" if zh else "Source audit", "已完成" if zh else "Complete", CYAN), ("02", "本地交付" if zh else "Local delivery", "已验证" if zh else "Verified", CYAN), ("03", "发布与线上验收" if zh else "Publish and verify online", "按授权执行" if zh else "By authorization", GOLD), ("04", "预注册与独立研究" if zh else "Preregistration and independent studies", "待研究" if zh else "Pending research", PURPLE)]
        for index, (number, title, status, accent) in enumerate(stages):
            x = 100 + index * 370
            draw.rounded_rectangle((x, 330, x + 330, 670), radius=24, fill=PANEL, outline=accent, width=3)
            draw.text((x + 26, 356), number, font=font(42, "en", True), fill=accent)
            text_block(draw, (x + 26, 438), title, 29, lang, TEXT, 278, True)
            text_block(draw, (x + 26, 574), status, 23, lang, accent, 278)
            if index < 3:
                draw.line((x + 330, 500, x + 370, 500), fill=MUTED, width=4)
        return image
    raise ValueError(asset)


def build_figures() -> list[dict]:
    records = []
    for asset in ("fig1-1", "figC-1", "fig7-1", "fig5-1", "fig25-1"):
        for lang in ("zh", "en"):
            target = ROOT / "assets" / "figures" / lang / f"{asset}.jpg"
            target.parent.mkdir(parents=True, exist_ok=True)
            make_figure(asset, lang).save(target, "JPEG", quality=92, optimize=True, dpi=(150, 150))
            records.append({"asset": f"assets/figures/{lang}/{asset}.jpg", "language": lang, "kind": "code-native guide illustration", "canon_figure": False, "generator": "figures.py"})
    return records
