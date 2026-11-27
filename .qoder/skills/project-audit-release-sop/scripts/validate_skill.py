#!/usr/bin/env python3
"""Validate the portable audit-and-release SOP Skill without dependencies."""
from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_DESCRIPTION = 1024
MAX_BODY_LINES = 500
NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
TODO_PATTERN = re.compile(r"\bTODO\s*:", re.IGNORECASE)
REQUIRED_RESOURCES = (
    "references/sop.md",
    "references/prompt-library.md",
    "references/evidence-template.md",
)
REQUIRED_PROMPTS = tuple(f"P{number:02d}" for number in range(17))


def configure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def read_utf8(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{path.name} 无法按 UTF-8 读取：{exc}")
        return ""


def parse_metadata(text: str, errors: list[str]) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        errors.append("frontmatter 必须以 --- 开始")
        return {}
    closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if closing is None:
        errors.append("frontmatter 缺少结束 ---")
        return {}
    metadata: dict[str, str] = {}
    for number, line in enumerate(lines[1:closing], start=2):
        if not line.strip() or line[:1].isspace():
            continue
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*):[ \t]*(.*)", line)
        if not match:
            errors.append(f"frontmatter 第 {number} 行不是合法键")
            continue
        key, raw = match.groups()
        if key in metadata:
            errors.append(f"frontmatter 键重复：{key}")
        if key in {"name", "description"}:
            if not raw or raw[0] in "|>[{&*!#'\"":
                errors.append(f"{key} 必须是非空单行标量")
                continue
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
                raw = raw[1:-1]
        metadata[key] = raw
    return metadata


def main() -> int:
    configure_utf8()
    skill_dir = Path(__file__).resolve().parents[1]
    skill_file = skill_dir / "SKILL.md"
    errors: list[str] = []
    text = read_utf8(skill_file, errors) if skill_file.is_file() else ""
    if not skill_file.is_file():
        errors.append("缺少 SKILL.md")

    metadata = parse_metadata(text, errors) if text else {}
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if not NAME_PATTERN.fullmatch(name):
        errors.append("name 必须使用小写字母、数字和单个连字符")
    elif name != skill_dir.name:
        errors.append(f"name 与目录名不一致：{name} != {skill_dir.name}")
    if not description:
        errors.append("缺少 description")
    elif len(description) > MAX_DESCRIPTION:
        errors.append(f"description 超过 {MAX_DESCRIPTION} 字符")

    lines = text.splitlines()
    closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    body = lines[closing + 1 :] if closing is not None else lines
    if len(body) >= MAX_BODY_LINES:
        errors.append(f"正文必须少于 {MAX_BODY_LINES} 行")
    if text and not re.search(r"(?m)^#{1,6}[ \t]+\S", "\n".join(body)):
        errors.append("正文缺少 Markdown 标题")
    if TODO_PATTERN.search(text):
        errors.append("SKILL.md 含未完成 TODO 标记")

    for relative in REQUIRED_RESOURCES:
        path = skill_dir / relative
        if not path.is_file():
            errors.append(f"缺少资源：{relative}")
            continue
        resource = read_utf8(path, errors)
        if TODO_PATTERN.search(resource):
            errors.append(f"{relative} 含未完成 TODO 标记")

    prompt_file = skill_dir / "references/prompt-library.md"
    prompt_text = read_utf8(prompt_file, errors) if prompt_file.is_file() else ""
    for prompt_id in REQUIRED_PROMPTS:
        if f"## {prompt_id}" not in prompt_text:
            errors.append(f"提示词库缺少 {prompt_id}")

    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(skill_dir).as_posix()
        if path.name in {"README.md", "CHANGELOG.md"}:
            errors.append(f"包含多余文档：{relative}")
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            errors.append(f"包含 Python 缓存：{relative}")

    if errors:
        print(f"失败：{skill_dir}")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(
        f"通过：{name}；description {len(description)} 字符；"
        f"正文 {len(body)} 行；P00–P16 完整；资源均为 UTF-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
