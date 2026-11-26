#!/usr/bin/env python3
"""Validate this Skill's metadata and layout without third-party dependencies."""
from __future__ import annotations

import re
import sys
from pathlib import Path


SKILL_NAME = "meaning-intelligence-maintain"
MAX_DESCRIPTION = 1024
MAX_BODY_LINES = 500
EXTRA_FILES = {"README.md", "CHANGELOG.md"}
NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
TODO_PATTERN = re.compile(r"\bTODO\s*:", re.IGNORECASE)


def configure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def main() -> int:
    configure_utf8()
    skill_dir = Path(__file__).resolve().parents[1]
    skill_file = skill_dir / "SKILL.md"
    errors: list[str] = []

    if not skill_file.is_file():
        print(f"失败：缺少 {skill_file}")
        return 1

    try:
        text = skill_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"失败：SKILL.md 不是有效 UTF-8 文本：{exc}")
        return 1

    lines = text.splitlines()
    metadata: dict[str, str] = {}
    if not lines or lines[0].strip() != "---":
        errors.append("frontmatter 必须以 --- 开始")
    else:
        closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if closing is None:
            errors.append("frontmatter 缺少结束 ---")
        else:
            scalar_key_pattern = re.compile(
                r"([A-Za-z][A-Za-z0-9_-]*):[ \t]+(.*)"
            )
            block_headers = ("|", "|-", "|+", ">", ">-", ">+")
            for number, line in enumerate(lines[1:closing], start=2):
                if line[:1].isspace() or not line.strip():
                    continue
                scalar_key = scalar_key_pattern.fullmatch(line)
                block_header = (
                    scalar_key
                    and scalar_key.group(1) in ("name", "description")
                    and scalar_key.group(2).strip() in block_headers
                )
                if block_header:
                    errors.append(
                        f"第 {number} 行 {scalar_key.group(1)} 必须使用单行标量"
                    )
                    continue
                match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*):[ \t]*(.*)", line)
                if not match:
                    errors.append(f"第 {number} 行不是合法 frontmatter 键")
                    continue
                key, raw_value = match.groups()
                if key in metadata:
                    errors.append(f"frontmatter 键 {key} 重复")
                if raw_value.startswith(("'", '"')):
                    quote = raw_value[0]
                    if len(raw_value) < 2 or not raw_value.endswith(quote):
                        errors.append(f"{key} 的引号字符串未闭合，description 必须单行")
                        continue
                    value = raw_value[1:-1]
                    if key == "description" and quote == "'" and "''" in value:
                        value = value.replace("''", "'")
                elif raw_value.startswith(("[", "{")) or raw_value.startswith(block_headers):
                    errors.append(f"{key} 必须使用单行标量")
                    continue
                elif key == "description" and (not raw_value or raw_value[0] in "#&*!{}"):
                    errors.append("description 必须是非空单行字符串")
                    continue
                else:
                    value = raw_value
                metadata[key] = value

    body_start = 2 if lines and lines[0].strip() == "---" else 1
    for i in range(body_start, len(lines)):
        if lines[i].strip() == "---":
            body_start = i + 1
            break
    body_lines = lines[body_start:]
    body_line_count = len(body_lines)

    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if not name:
        errors.append("缺少 name")
    elif not NAME_PATTERN.fullmatch(name):
        errors.append("name 只能使用小写字母、数字和单个连字符")
    elif name != skill_dir.name:
        errors.append(f"name 与目录名不一致：{name} != {skill_dir.name}")
    elif name != SKILL_NAME:
        errors.append(f"name 应为 {SKILL_NAME}")

    if not description:
        errors.append("缺少 description")
    else:
        if len(description) > MAX_DESCRIPTION:
            errors.append(f"description 为 {len(description)} 字符，超过 {MAX_DESCRIPTION}")
        if "\n" in description or "\r" in description:
            errors.append("description 必须单行")
    if body_line_count >= MAX_BODY_LINES:
        errors.append(f"正文 {body_line_count} 行，必须少于 {MAX_BODY_LINES} 行")
    body_text = "\n".join(body_lines)
    if not re.search(r"(?m)^#{1,6}[ \t]+\S", body_text):
        errors.append("正文缺少 Markdown 标题")
    if not any(line.strip() and not line.startswith("#") for line in body_lines):
        errors.append("正文为空")

    for path in sorted(skill_dir.rglob("*")):
        if path.is_file():
            relative = path.relative_to(skill_dir).as_posix()
            if path.name in EXTRA_FILES:
                errors.append(f"包含多余文档：{relative}")
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                errors.append(f"包含 Python 缓存：{relative}")
            if relative != "SKILL.md" and path.suffix in {".md", ".py"}:
                try:
                    content = path.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    errors.append(f"{relative} 不是有效 UTF-8 文本：{exc}")
                    continue
                if TODO_PATTERN.search(content):
                    errors.append(f"{relative} 含未完成 TODO 标记")

    if TODO_PATTERN.search(text):
        errors.append("SKILL.md 含未完成 TODO 标记")

    if errors:
        print(f"失败：{skill_file}")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(
        f"通过：{skill_dir.name}；description {len(description)} 字符；"
        f"正文 {body_line_count} 行；文件均为 UTF-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
