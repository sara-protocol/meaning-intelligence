"""mi_common.py —— Meaning Intelligence 演示系统 / 公共层

职责：
  · 路径与配置加载（一律以本文件所在目录为基准，不依赖调用时的 cwd）
  · 中文 Windows 控制台的 UTF-8 兜底（GBK 控制台打印 emoji 会抛 UnicodeEncodeError）
  · 六层时间轴的推算（planned）与读取（measured）
  · 跨平台 CJK 字体选择

本模块只依赖标准库，Manim 场景与 HTML 构建脚本共用。
"""
import json
import os
import sys
from pathlib import Path

# msi/ 根目录（本文件所在目录）
BASE_DIR = Path(__file__).resolve().parent

LAYER_ORDER = ["L1", "L2", "L3", "L4", "L5", "L6"]


def enable_utf8_console():
    """中文 Windows 控制台默认 GBK，打印 emoji / 生僻字会抛 UnicodeEncodeError。

    这个坑在 build.py 与场景文件里各踩过一次：build.py 是 print("⚠️ ...") 直接崩；
    场景文件是渲染完成后 print("📐 ...") 崩，导致 manim 以非零码退出。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def safe_print(*args, **kwargs):
    """即便 reconfigure 失效（例如流被 rich 之类接管），也绝不因编码而崩溃。"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(*(str(a).encode(enc, "replace").decode(enc, "replace") for a in args), **kwargs)


def resolve(path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (BASE_DIR / p)


def load_config(config_path="config.json"):
    with open(resolve(config_path), "r", encoding="utf-8-sig") as f:
        return json.load(f)


def get_cjk_font():
    if os.name == "nt":
        return "Microsoft YaHei"
    if sys.platform == "darwin":
        return "PingFang SC"
    # Linux / CI：Manim 的 Pango 后端会回退到系统已装字体
    return "Noto Sans CJK SC"


def calculate_layer_timestamps(layers):
    """无实测数据时的预算时间轴。"""
    timestamps = {}
    current = 0.0
    for key in LAYER_ORDER:
        layer = layers[key]
        start = round(current, 2)
        duration = layer.get("duration", 4.5)
        current += duration
        timestamps[key] = {
            "name": f"{layer['name']} ({layer['en']})",
            "index": layer["index"],
            "band": layer["band"],
            "start": start,
            "end": round(current, 2),
            "duration": duration,
        }
    return timestamps
