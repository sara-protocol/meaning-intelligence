"""build.py —— 把 config.json 与时间轴注入 HTML 模板，产出单文件交互页。

设计要点（都是踩过坑之后定下来的）：
  1. 中文 Windows 控制台默认 GBK，打印 emoji 会抛 UnicodeEncodeError。
     早期版本因此在第一个 print 就崩溃，从未产出过 HTML。统一走 mi_common.safe_print。
  2. 所有路径以 BASE_DIR（本文件所在目录）为基准，从任意 cwd 调用都能工作。
  3. timeline.json 用 utf-8-sig 读取，容忍记事本 / PowerShell 写出的 BOM。
  4. 占位符注入的必须是**合法的 JS 字面量**。模板里写 const X = {{X_JSON}};，
     由本脚本注入带引号/带括号的 JSON —— 模板外层绝不能再套引号，
     否则会得到 ""planned"" 这种 SyntaxError，整段内联 JS 失效。
  5. 构建后扫描残留的 {{...}}，有残留直接非零退出，不静默产出坏页面。
"""
import json
import re
import sys

from mi_common import (BASE_DIR, LAYER_ORDER, calculate_layer_timestamps,
                       enable_utf8_console, load_config, safe_print)

enable_utf8_console()


def js_literal(obj):
    """输出可直接嵌入 <script> 的 JS 字面量。

    · ensure_ascii=False 保留中文，便于阅读与 diff
    · 转义 < > 防止 JSON 中出现 </script> 提前闭合脚本块
    """
    return (json.dumps(obj, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e"))


def build():
    config = load_config("config.json")
    layers = config["layers"]
    theme = config["theme"]

    timeline_path = BASE_DIR / "timeline.json"
    if timeline_path.exists():
        with open(timeline_path, "r", encoding="utf-8-sig") as f:
            timeline = json.load(f)
        source = "measured"
        safe_print("[timeline] 检测到实测时间轴 timeline.json，注入毫秒级测量数据。")
    else:
        timeline = calculate_layer_timestamps(layers)
        source = "planned"
        safe_print("[timeline] 未检测到实测时间轴，注入预算推算时间轴。")

    missing = [k for k in LAYER_ORDER if k not in timeline]
    if missing:
        safe_print(f"[timeline] 警告：时间轴缺少 {missing}，对应层将无法与视频对齐。")

    template = (BASE_DIR / "templates" / "html_template.html").read_text(encoding="utf-8")

    tokens = {
        "PROJECT_NAME": config["project_name"],
        "VERSION": config["version"],
        "CANON": config["canon"],
        "THEME_BACKGROUND": theme["background"],
        "THEME_TEXT": theme["text"],
        "THEME_MUTED": theme["muted"],
        "THEME_ACCENT": theme["accent"],
        "THEME_FAIL": theme["fail"],
        "THEME_NAVY": theme["navy"],
        "LAYERS_JSON": js_literal(layers),
        "BANDS_JSON": js_literal(config["bands"]),
        "EVIDENCE_JSON": js_literal(config["evidence_palette"]),
        "EVIDENCE_NAMES_JSON": js_literal(config["evidence_names"]),
        "TIMELINE_DATA": js_literal(timeline),
        "TIMELINE_SOURCE": js_literal(source),
    }

    html = template
    for key, value in tokens.items():
        html = html.replace("{{" + key + "}}", value)

    leftover = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", html)))
    if leftover:
        safe_print(f"[build] 失败：模板中仍有未替换的占位符 {leftover}")
        return 1

    out_path = BASE_DIR / "meaning_intelligence.html"
    out_path.write_text(html, encoding="utf-8")
    safe_print(f"[build] 已生成：{out_path}")

    video = BASE_DIR / "MeaningIntelligenceScene.mp4"
    if video.exists():
        safe_print(f"[build] 已检测到 {video.name}（{video.stat().st_size:,} 字节），视频可直接播放。")
    else:
        safe_print("[build] 未检测到 MeaningIntelligenceScene.mp4 —— "
                   "页面仍可用，但动画区会是空的。运行 run.ps1 / run.sh 完成渲染。")
    return 0


if __name__ == "__main__":
    sys.exit(build())
