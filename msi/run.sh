#!/usr/bin/env bash
# run.sh —— 一键渲染 + 构建（Linux / macOS / Git-Bash）
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v manim >/dev/null 2>&1; then
  echo "未找到 manim，请先 pip install manim" >&2
  exit 1
fi

# 1. 渲染六幕场景（-ql = 480p15 快速预览；正式出片用 -qh）
manim -ql scenes/meaning_intelligence.py MeaningIntelligenceScene

# 2. 把产物复制到 HTML 同级目录
#    Manim 输出在 media/videos/<module>/480p15/ 下，而 HTML 引用的是同级文件名。
#    少了这一步，<video> 永远黑屏。
MP4=$(find media -name 'MeaningIntelligenceScene.mp4' | head -n 1 || true)
if [ -n "${MP4}" ]; then
  cp "$MP4" ./MeaningIntelligenceScene.mp4
  echo "已复制视频: $MP4 -> ./MeaningIntelligenceScene.mp4"
else
  echo "警告: 未找到渲染出的 MP4" >&2
fi

# 3. 构建 HTML（读取 config.json 与实测 timeline.json）
python3 build.py 2>/dev/null || python build.py
