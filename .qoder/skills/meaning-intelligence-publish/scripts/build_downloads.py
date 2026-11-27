#!/usr/bin/env python3
"""Build verified downloads, curated source, and the self-excluding delivery ZIP."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

from finalize_publish import PROJECT_IDENTIFIER, REPO, WORKSPACE, finalize_accessibility, finalize_index, finalize_listen, finalize_project_identifier

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")

PACKAGE = WORKSPACE / "意义智能有声读物_发布包"
PUBLISH = WORKSPACE / "meaning-intelligence-publish"
if not (PUBLISH / "SKILL.md").is_file():
    PUBLISH = REPO / "skills" / "meaning-intelligence-publish"
PUBLISH_SCRIPTS = PUBLISH / "scripts"
VIDEO_SOURCE = WORKSPACE / "deliverables" / "video"
DELIVERABLES = WORKSPACE / "deliverables"
DOCS_SOURCE = DELIVERABLES / "documents"
BEST_PRACTICE_GUIDE = DOCS_SOURCE / "意义智能_最佳应用指南.md"
GUIDE_SOURCE = WORKSPACE / "deliverables" / "project-guide"
PUBLICATION_BROWSER_REPORT = WORKSPACE / "deliverables" / "publication-browser-check.json"
WEB_MEDIA_REPORT = WORKSPACE / "deliverables" / "web-media-verification.json"
ARCHIVE = WORKSPACE / "deliverables" / "archive"
WHITEPAPER = REPO / "whitepaper" / "dist"
DOWNLOAD = PACKAGE / "download"
VIDEO_DOWNLOAD = DOWNLOAD / "video"
DOCS_DOWNLOAD = DOWNLOAD / "documents"
SOURCE_ARCHIVE = DOWNLOAD / "Meaning_Intelligence_Source_v0.2.0_2026-11-27_release-final3.zip"
COMPLETE_ARCHIVE = DOWNLOAD / "意义智能_完整交付包_2026-11-27_release.zip"
PROVISIONAL_ARCHIVE = DOWNLOAD / "意义智能_完整交付包_2026-11-27_release-provisional.zip"
VERIFICATION_REPORT = DOWNLOAD / "verification.json"
DATE = "2026-11-27"
VERSION = "1.1"
RELEASE_VIDEOS = {
    "meaning_intelligence_zh.mp4": "zh",
    "meaning_intelligence_en.mp4": "en",
}
TEXT_SUFFIXES = {
    ".py", ".js", ".mjs", ".json", ".md", ".txt", ".html", ".css",
    ".yml", ".yaml", ".toml", ".ini", ".cfg", ".srt", ".vtt", ".bat", ".ps1", ".sh",
}
EXCLUDED_PARTS = {
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".cache", "node_modules", ".wrangler", ".lingxi", ".qoder",
}
EXCLUDED_NAMES = {
    ".env", ".env.local", ".npmrc", ".netrc", "credentials.json", "token.txt",
    "tokens.json", "secrets.json", "id_rsa", "id_ed25519",
    "意义智能_完整交付包.zip", "意义智能_完整交付包_2026-11-27_release-provisional.zip", "meaning-intelligence-project-guide.zip", "meaning-intelligence-project-guide-2026-11-27.zip",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".pem", ".key", ".pfx", ".p12"}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{32,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{20,})"),
)

ZH_CHAPTERS = [
    (0, "第一章 · 为什么现在需要意义智能"),
    (301, "第二章 · 核心理论体系"),
    (868, "第三章 · 运行机制与工程化"),
    (1302, "第四章 · 多尺度多领域实践"),
    (1560, "第五章 · 文明演化总结与展望"),
    (1888, "附录 · 实践工具与研究支撑"),
    (2182, "全书总结 · 给智能装上方向舵"),
]


class ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for key in ("href", "src", "poster"):
            if values.get(key):
                self.refs.append(values[key])


def replace_file(source: Path, target: Path) -> None:
    backup = target.with_name(f".{target.name}.{os.getpid()}.old.tmp")
    for attempt in range(240):
        try:
            if backup.exists():
                backup.unlink()
            if target.exists():
                os.replace(target, backup)
            try:
                os.replace(source, target)
            except PermissionError:
                if backup.exists() and not target.exists():
                    os.replace(backup, target)
                raise
            if backup.exists():
                backup.unlink()
            return
        except PermissionError:
            if backup.exists() and not target.exists():
                os.replace(backup, target)
            if attempt == 239:
                raise
            time.sleep(0.25)


def atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        replace_file(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"路径越出允许目录: {path}") from exc
    pure = PurePosixPath(relative.as_posix())
    if not relative.parts or pure.is_absolute() or ".." in pure.parts or "\\" in relative.as_posix():
        raise RuntimeError(f"不安全相对路径: {relative}")
    return relative


def excluded(relative: Path) -> bool:
    return (
        relative.as_posix() in {
            "download/Meaning_Intelligence_Source_v0.2.0.zip",
            "download/Meaning_Intelligence_Source_v0.2.0_2026-11-27.zip",
            "download/Meaning_Intelligence_Source_v0.2.0_2026-11-27_final.zip",
            "download/Meaning_Intelligence_Source_v0.2.0_2026-11-27_release.zip",
            "download/Meaning_Intelligence_Source_v0.2.0_2026-11-27_release-final.zip",
            "download/Meaning_Intelligence_Source_v0.2.0_2026-11-27_release-final2.zip",
            "download/意义智能_完整交付包.zip",
            "downloads/attachment-updated-2026-11-26.pdf",
            "project-guide/downloads/attachment-updated-2026-11-26.pdf",
        }
        or any(part.lower() in EXCLUDED_PARTS or part.lower().startswith(".project-guide-") for part in relative.parts)
        or relative.name.lower() in EXCLUDED_NAMES
        or relative.name in {"source-v0.2.0.zip", "source-v0.2.0-final.zip"}
        or relative.name in {"verify_package_final.py", "build_final.py", "build_downloads_final.py", "build_downloads_release.py", "verify_package_release.py"}
        or relative.name.lower().startswith(".env")
        or ".uploading" in relative.name.lower() or ".downloading" in relative.name.lower()
        or relative.suffix.lower() in EXCLUDED_SUFFIXES | {".tmp", ".part", ".crdownload"}
    )


def reject_secrets(path: Path) -> None:
    if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 2 * 1024 * 1024:
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        raise RuntimeError(f"拒绝打包疑似密钥/令牌: {path}")


def add_member(members: dict[str, Path], name: str, source: Path) -> None:
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or "\\" in name or not pure.parts:
        raise RuntimeError(f"不安全归档成员: {name}")
    if excluded(Path(name)):
        raise RuntimeError(f"归档成员命中排除规则: {name}")
    if not source.is_file():
        raise RuntimeError(f"归档源文件不存在: {source}")
    reject_secrets(source)
    previous = members.get(name)
    if previous is not None:
        if previous.resolve() != source.resolve() and sha256(previous) != sha256(source):
            raise RuntimeError(f"归档成员内容冲突: {name}")
        return
    members[name] = source


def collect_tree(root: Path, prefix: str, members: dict[str, Path]) -> int:
    if not root.is_dir():
        return 0
    count = 0
    for source in sorted(root.rglob("*")):
        if not source.is_file():
            continue
        relative = safe_relative(source, root)
        if excluded(relative):
            continue
        add_member(members, f"{prefix}/{relative.as_posix()}", source)
        count += 1
    return count


def validate_best_practice_guide(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"缺少中英双语最佳应用指南: {path}")
    text = path.read_text(encoding="utf-8")
    required = (
        "# 中文版", "# English Edition", "### L1", "### L2", "### L3",
        "### L4", "### L5", "### L6", "Meaning Agent", "2024-11-05",
        "2025-03-26", "MI_MCP_PUBLIC_TOKEN", "approval.status=pending",
        "V7.0", "30-day", "三十天", PROJECT_IDENTIFIER["title_zh"],
        PROJECT_IDENTIFIER["title_en"], PROJECT_IDENTIFIER["doi"],
        PROJECT_IDENTIFIER["resolver"], "category=project", "registration=false",
        "preprint=false", "不提升 E0–E6", "does not promote E0–E6",
    )
    missing = [token for token in required if token not in text]
    if missing:
        raise RuntimeError(f"最佳应用指南缺少双语或安全内容: {missing}")
    if text.count("```text") < 12:
        raise RuntimeError("最佳应用指南缺少完整的中英六技能提示词")


def final_document_sources() -> list[Path]:
    if not DOCS_SOURCE.is_dir():
        raise RuntimeError(f"缺少最终文档目录: {DOCS_SOURCE}")
    documents = [
        path for path in sorted(DOCS_SOURCE.iterdir())
        if path.is_file() and path.suffix.lower() in {".docx", ".md", ".pdf"}
        and "_v2.0" not in path.name
    ]
    validate_best_practice_guide(BEST_PRACTICE_GUIDE)
    if BEST_PRACTICE_GUIDE not in documents:
        documents.append(BEST_PRACTICE_GUIDE)
    stems = {path.stem for path in documents}
    rendered = DOCS_SOURCE / "rendered"
    if rendered.is_dir():
        documents.extend(
            path for path in sorted(rendered.iterdir())
            if path.is_file() and path.suffix.lower() == ".pdf"
            and path.stem in stems and "_v2.0" not in path.name
        )
    manual = WORKSPACE / "意义智能有声读物_发布指南与操作手册.md"
    retrospective = DELIVERABLES / "意义智能_并行审视反思与SOP总结.md"
    if manual.is_file():
        documents.append(manual)
    if not retrospective.is_file():
        raise RuntimeError(f"缺少项目复盘: {retrospective}")
    documents.append(retrospective)
    if not documents:
        raise RuntimeError("最终文档目录没有可交付 DOCX/Markdown/PDF")
    return documents


def whitepaper_sources() -> dict[str, Path]:
    result: dict[str, Path] = {}
    for suffix in ("docx", "pdf"):
        matches = sorted(WHITEPAPER.glob(f"*_v{VERSION}_*.{suffix}"))
        if len(matches) != 1:
            raise RuntimeError(f"白皮书 v{VERSION} {suffix.upper()} 权威源应恰有一个，实际 {len(matches)}")
        result[suffix] = matches[0]
    return result


def sync_project_guide() -> bool:
    if not GUIDE_SOURCE.is_dir():
        return False
    try:
        verification = json.loads((GUIDE_SOURCE / "verification.json").read_text(encoding="utf-8"))
        browser = json.loads((GUIDE_SOURCE / "browser-check.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    modes = browser.get("modes", [])
    if not verification.get("ok") or not browser.get("ok") or [item.get("mode") for item in modes] != ["http", "file"] or any(not item.get("ok") for item in modes):
        raise RuntimeError("项目说明书验证或浏览器检查未通过，拒绝复制到发布包。")
    required = ("index.html", "content.js", "verification.js", "app.js", "styles.css", "manifest.json", "manifest.sha256", "verification.json", "downloads/project-guide-bilingual.pdf", "downloads/guide-narration-zh.mp3", "downloads/guide-narration-en.mp3")
    missing = [name for name in required if not (GUIDE_SOURCE / name).is_file()]
    if missing:
        raise RuntimeError(f"项目说明书缺少必要文件: {missing}")
    guide_source = GUIDE_SOURCE / "downloads" / "source-v0.2.0-release.zip"
    if not guide_source.is_file() or sha256(guide_source) != sha256(SOURCE_ARCHIVE):
        raise RuntimeError("项目说明书便捷源码包与权威 final3 源码包不一致，拒绝同步。")
    target = PACKAGE / "project-guide"
    if target.exists():
        marker = target / "manifest.json"
        try:
            existing = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError("发布包已有 project-guide 但缺少可识别清单，拒绝覆盖。") from exc
        if existing.get("schema") != "meaning-intelligence-project-guide-manifest-v1":
            raise RuntimeError("发布包已有 project-guide 不是本项目生成目录，拒绝覆盖。")
    excluded_parts = {".build", ".audio-work", "rendered", "__pycache__"}
    expected = {}
    for source in sorted(GUIDE_SOURCE.rglob("*")):
        if not source.is_file():
            continue
        relative = safe_relative(source, GUIDE_SOURCE)
        if any(part.lower() in excluded_parts for part in relative.parts) or any(part.lower().startswith(".browser-profile") for part in relative.parts):
            continue
        if excluded(relative):
            continue
        expected[relative.as_posix()] = sha256(source)
    if target.is_dir():
        actual = {}
        for source in target.rglob("*"):
            if not source.is_file():
                continue
            relative = safe_relative(source, target)
            if any(part.lower() in excluded_parts for part in relative.parts) or any(part.lower().startswith(".browser-profile") for part in relative.parts):
                continue
            if excluded(relative):
                continue
            actual[relative.as_posix()] = sha256(source)
        if actual == expected:
            print(f"REUSE 双语项目说明书: {target}")
            return True
    stage = Path(tempfile.mkdtemp(prefix=".project-guide-", dir=PACKAGE))
    try:
        for source in sorted(GUIDE_SOURCE.rglob("*")):
            if not source.is_file():
                continue
            relative = safe_relative(source, GUIDE_SOURCE)
            if any(part.lower() in excluded_parts for part in relative.parts) or any(part.lower().startswith(".browser-profile") for part in relative.parts):
                continue
            if excluded(relative):
                continue
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        if target.exists():
            for source in sorted(stage.rglob("*")):
                if not source.is_file():
                    continue
                relative = source.relative_to(stage)
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.is_file() and sha256(destination) == sha256(source):
                    continue
                replace_file(source, destination)
            shutil.rmtree(stage, ignore_errors=True)
        else:
            stage.replace(target)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        raise
    print(f"PASS 已同步并验证双语项目说明书: {target}")
    return True


def sync_publication_browser_report() -> dict:
    report = json.loads(PUBLICATION_BROWSER_REPORT.read_text(encoding="utf-8"))
    if not report.get("ok") or report.get("checks_total") != report.get("checks_passed") or report.get("checks_total", 0) < 21:
        raise RuntimeError("发布页真实浏览器检查未通过，拒绝打包。")
    target = PACKAGE / PUBLICATION_BROWSER_REPORT.name
    shutil.copy2(PUBLICATION_BROWSER_REPORT, target)
    if sha256(PUBLICATION_BROWSER_REPORT) != sha256(target):
        raise RuntimeError("发布页浏览器报告复制校验失败")
    print(f"PASS 已同步发布页浏览器检查: {report['checks_passed']}/{report['checks_total']}")
    return report


def sync_web_media_report() -> dict:
    report = json.loads(WEB_MEDIA_REPORT.read_text(encoding="utf-8"))
    records = report.get("records", [])
    if not report.get("ok") or report.get("masters_modified") is not False or len(records) != 3:
        raise RuntimeError("流媒体派生验证报告不完整，拒绝打包。")
    for record in records:
        source = WORKSPACE / record["path"]
        if not source.is_file() or source.stat().st_size != record.get("bytes") or sha256(source) != record.get("sha256"):
            raise RuntimeError(f"流媒体派生文件校验失败: {record.get('path')}")
        if source.stat().st_size >= report.get("platform_file_limit_bytes", 25 * 1024 * 1024):
            raise RuntimeError(f"流媒体派生文件超过平台限制: {record.get('path')}")
    target = PACKAGE / WEB_MEDIA_REPORT.name
    shutil.copy2(WEB_MEDIA_REPORT, target)
    if sha256(WEB_MEDIA_REPORT) != sha256(target):
        raise RuntimeError("流媒体验证报告复制校验失败")
    print("PASS 已同步并验证 3 个合规流媒体派生文件")
    return report


def guide_source_files() -> list[Path]:
    if not GUIDE_SOURCE.is_dir():
        return []
    generated_parts = {".build", "assets", "audio", "captions", "downloads", "transcripts", "rendered"}
    generated_names = {
        "index.html", "content.js", "verification.js", "audio-timings.json",
        "manifest.json", "manifest.sha256", "verification.json", "browser-check.json",
        "meaning-intelligence-project-guide.zip",
    }
    return [
        path for path in sorted(GUIDE_SOURCE.rglob("*"))
        if path.is_file()
        and path.name not in generated_names
        and not any(part.lower() in generated_parts for part in path.relative_to(GUIDE_SOURCE).parts)
        and path.suffix.lower() in {".py", ".json", ".html", ".css", ".js", ".mjs", ".ps1", ".md", ".txt"}
        and not excluded(path.relative_to(GUIDE_SOURCE))
    ]


def collect_repository_sources(members: dict[str, Path]) -> int:
    count = 0
    root_names = {".gitattributes", ".gitignore", "CNAME", "LICENSE", "LICENSE-DOCS"}
    publication_outputs = {
        "index.html", "listen.html", "downloads.html", "mcp.html",
        "publication-browser-check.json", "web-media-verification.json",
        "subtitles.json", "subtitles.vtt", "subtitles_en.json", "subtitles_en.vtt",
        "subtitles_zh.vtt", "timeline_en.json",
    }
    for source in sorted(REPO.rglob("*")):
        if not source.is_file():
            continue
        relative = safe_relative(source, REPO)
        if relative.parts[0] in {"meaning-agent", "web-mcp", ".qoder", "download", "project-guide", "functions"}:
            continue
        if relative.as_posix() in publication_outputs:
            continue
        if excluded(relative):
            continue
        if source.suffix.lower() not in TEXT_SUFFIXES and relative.name not in root_names:
            continue
        add_member(members, f"repository/{relative.as_posix()}", source)
        count += 1
    return count


def curated_sources() -> tuple[dict[str, Path], dict]:
    members: dict[str, Path] = {}
    agent = REPO / "meaning-agent"
    skill_docs = sorted((agent / "skills").glob("*/SKILL.md"))
    test_files = sorted((agent / "tests").glob("test_*.py"))
    if len(skill_docs) != 6 or not test_files:
        raise RuntimeError(f"meaning-agent 来源不完整: skills={len(skill_docs)}, tests={len(test_files)}")
    collect_tree(agent, "meaning-agent", members)
    collect_tree(REPO / "web-mcp", "web-mcp", members)
    repository_source_files = collect_repository_sources(members)
    collect_tree(PUBLISH_SCRIPTS, "scripts", members)
    reusable_skills = {
        "meaning-intelligence-maintain": REPO / ".qoder" / "skills" / "meaning-intelligence-maintain",
        "meaning-intelligence-publish": PUBLISH,
        "project-audit-release-sop": REPO / ".qoder" / "skills" / "project-audit-release-sop",
    }
    for name, root in reusable_skills.items():
        if not (root / "SKILL.md").is_file():
            raise RuntimeError(f"缺少可复用 Skill: {name}")
        collect_tree(root, f"skills/{name}", members)
    for name in ("build_publish.py", "build_bilingual.py", "build_en_audio2.py"):
        source = WORKSPACE / name
        if source.is_file():
            add_member(members, f"scripts/{name}", source)
    builder = VIDEO_SOURCE / "build_video.py"
    if not builder.is_file():
        raise RuntimeError(f"缺少视频构建器: {builder}")
    add_member(members, "video/build_video.py", builder)
    guide_files = guide_source_files()
    for source in guide_files:
        add_member(members, f"guide/{safe_relative(source, GUIDE_SOURCE).as_posix()}", source)
    final_overrides = {
        "scripts/build_downloads.py": PUBLISH_SCRIPTS / "build_downloads.py",
        "skills/meaning-intelligence-publish/scripts/build_downloads.py": PUBLISH_SCRIPTS / "build_downloads.py",
        "scripts/verify_package.py": PUBLISH_SCRIPTS / "verify_package.py",
        "skills/meaning-intelligence-publish/scripts/verify_package.py": PUBLISH_SCRIPTS / "verify_package.py",
        "guide/build.py": GUIDE_SOURCE / "build.py",
    }
    for name, source in final_overrides.items():
        if not source.is_file():
            raise RuntimeError(f"缺少最终构建或验收脚本: {source}")
        reject_secrets(source)
        members[name] = source
    for source in final_document_sources():
        add_member(members, f"documents/{source.name}", source)
    retrospective = DELIVERABLES / "意义智能_并行审视反思与SOP总结.md"
    if not retrospective.is_file():
        raise RuntimeError(f"缺少项目复盘: {retrospective}")
    add_member(members, "documents/意义智能_并行审视反思与SOP总结.md", retrospective)
    add_member(members, "scripts/build_documents.py", DOCS_SOURCE / "build_documents.py")
    add_member(members, "documents/document-manifest.json", DOCS_SOURCE / "document-manifest.json")
    for source in whitepaper_sources().values():
        add_member(members, f"documents/whitepaper/{source.name}", source)
    for name in ("README.md", "README.en.md", "LICENSE", "LICENSE-DOCS", "VERSION.yaml"):
        source = REPO / name
        if source.is_file():
            add_member(members, name, source)
    metadata = {
        "files": len(members),
        "skill_documents": len(skill_docs),
        "reusable_skill_documents": len(reusable_skills),
        "test_files": len(test_files),
        "guide_files": len(guide_files),
        "guide_builder_present": any(path.suffix.lower() == ".py" for path in guide_files),
        "repository_source_files": repository_source_files,
    }
    return members, metadata


def archive_stale_videos() -> list[Path]:
    moved: list[Path] = []
    for source in sorted(PACKAGE.rglob("meaning_intelligence_launch*.mp4")):
        if not source.is_file():
            continue
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        destination = ARCHIVE / source.name
        counter = 1
        while destination.exists():
            destination = ARCHIVE / f"{source.stem}.{counter}{source.suffix}"
            counter += 1
        shutil.move(str(source), str(destination))
        moved.append(destination)
        print(f"ARCHIVE 旧发布视频移出发布包: {source.relative_to(PACKAGE).as_posix()} -> {destination}")
    return moved


def stamp(seconds: float, separator: str = ".") -> str:
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    secs, millis = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def write_subtitles() -> None:
    for lang, label in (("zh", "Chinese"), ("en", "English")):
        source = PACKAGE / f"subtitles{'_en' if lang == 'en' else ''}.json"
        cues = json.loads(source.read_text(encoding="utf-8"))
        vtt = "WEBVTT\n\n" + "\n\n".join(
            f"{index}\n{stamp(cue['s'])} --> {stamp(cue['e'])}\n{cue['t']}"
            for index, cue in enumerate(cues, 1)
        )
        srt = "\n\n".join(
            f"{index}\n{stamp(cue['s'], ',')} --> {stamp(cue['e'], ',')}\n{cue['t']}"
            for index, cue in enumerate(cues, 1)
        ) + "\n"
        atomic_write_text(PACKAGE / f"subtitles_{lang}.vtt", vtt)
        atomic_write_text(DOWNLOAD / f"Meaning_Intelligence_{label}_subtitles.srt", srt)
    # Historical players request /subtitles.vtt; keep it as the Chinese compatibility track.
    shutil.copy2(PACKAGE / "subtitles_zh.vtt", PACKAGE / "subtitles.vtt")


def chapter_text(cues: list[dict], chapters: list[tuple[float, str]]) -> list[tuple[str, str]]:
    result = []
    for index, (start, title) in enumerate(chapters):
        end = chapters[index + 1][0] if index + 1 < len(chapters) else float("inf")
        selected = [cue["t"].strip() for cue in cues if start <= cue["s"] < end and cue["t"].strip()]
        paragraphs, current = [], ""
        for text in selected:
            current = f"{current} {text}".strip()
            if len(current) >= 140 or text.endswith(("。", "！", "？", ".", "!", "?")):
                paragraphs.append(current)
                current = ""
        if current:
            paragraphs.append(current)
        result.append((title, "\n\n".join(paragraphs)))
    return result


def xhtml_document(title: str, body: str, lang: str, css: str = "") -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{lang}" xml:lang="{lang}">
<head><meta charset="utf-8"/><title>{html.escape(title)}</title><link rel="stylesheet" type="text/css" href="style.css"/>{css}</head>
<body>{body}</body></html>"""


def build_epub(path: Path, language: str, zh_chapters: list[tuple[str, str]], en_chapters: list[tuple[str, str]]) -> None:
    bilingual = language == "bilingual"
    identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, f"meaning-intelligence:{VERSION}:{language}"))
    primary_language = "zh-CN" if language in {"zh", "bilingual"} else "en"
    languages_metadata = "<dc:language>zh-CN</dc:language><dc:language>en</dc:language>" if bilingual else f"<dc:language>{primary_language}</dc:language>"
    manifest_items = [
        ("nav", "nav.xhtml", "application/xhtml+xml", "nav"),
        ("ncx", "toc.ncx", "application/x-dtbncx+xml", "ncx"),
        ("css", "style.css", "text/css", ""),
        ("cover", "cover.xhtml", "application/xhtml+xml", ""),
        ("cover-image", "images/cover.jpg", "image/jpeg", "cover-image"),
        ("content", "content.xhtml", "application/xhtml+xml", ""),
    ]
    nav_points = []
    ncx_points = []
    languages = (("zh", zh_chapters), ("en", en_chapters)) if bilingual else ((language, zh_chapters if language == "zh" else en_chapters),)
    for lang, chapters in languages:
        for index, (title, _) in enumerate(chapters, 1):
            anchor = f"{lang}-{index}"
            nav_points.append(f'<li><a href="content.xhtml#{anchor}">{html.escape(title)}</a></li>')
            ncx_points.append(f'<navPoint id="navPoint-{anchor}" playOrder="{len(ncx_points)+1}"><navLabel><text>{html.escape(title)}</text></navLabel><content src="content.xhtml#{anchor}"/></navPoint>')

    language_toggle = ""
    content_class = "content bilingual"
    css_extra = ""
    if bilingual:
        language_toggle = '<input type="radio" name="language" id="show-zh" checked="checked"/><input type="radio" name="language" id="show-en"/><div class="language-switch"><div><label for="show-zh">中文</label><label for="show-en">English</label></div></div>'
        css_extra = "<style>#show-zh:checked~.language-switch label[for=show-zh],#show-en:checked~.language-switch label[for=show-en]{background:#1b3a5c;color:white}#show-zh:checked~.content .en,#show-en:checked~.content .zh{display:none}</style>"
    sections = []
    for lang, chapters in languages:
        rendered = []
        for index, (title, text) in enumerate(chapters, 1):
            paragraphs = "\n".join(f"<p>{html.escape(part)}</p>" for part in text.split("\n\n") if part)
            rendered.append(f'<section class="chapter" id="{lang}-{index}"><h1>{html.escape(title)}</h1>{paragraphs}</section>')
        sections.append(f'<div class="{lang}">{"".join(rendered)}</div>')
    body = language_toggle + f'<main class="{content_class}"><h1 class="book-title">意义智能 / Meaning Intelligence</h1><p class="subtitle">给智能装上方向舵 · A Rudder for Intelligence</p>{"".join(sections)}</main>'
    content = xhtml_document("意义智能 / Meaning Intelligence", body, primary_language, css_extra)
    nav = xhtml_document("目录 / Contents", f'<nav epub:type="toc" id="toc"><h1>目录 / Contents</h1><ol>{"".join(nav_points)}</ol></nav>', primary_language)
    ncx = f'''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head><meta name="dtb:uid" content="{identifier}"/></head><docTitle><text>意义智能 / Meaning Intelligence</text></docTitle><navMap>{"".join(ncx_points)}</navMap></ncx>'''
    cover = xhtml_document("封面 / Cover", '<div class="cover-page"><img src="images/cover.jpg" alt="意义智能封面"/><h1>意义智能</h1><p>Meaning Intelligence</p><p>给智能装上方向舵</p></div>', primary_language)
    style = """body{font-family:serif;line-height:1.7;margin:5%;color:#1f2937}h1{color:#1b3a5c;line-height:1.3}.book-title{text-align:center}.subtitle{text-align:center;color:#6b7280}.chapter{page-break-before:always}.language-switch{text-align:center;margin:1em}.language-switch input{position:absolute;opacity:0}.language-switch label{display:inline-block;padding:.5em 1.2em;border:1px solid #1b3a5c;cursor:pointer}#show-zh:checked~div label[for=show-zh],#show-en:checked~div label[for=show-en]{background:#1b3a5c;color:white}.cover-page{text-align:center}.cover-page img{max-width:100%;max-height:80vh}"""
    files = {name: data for name, data in (
        ("mimetype", "application/epub+zip"),
        ("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'),
        ("OEBPS/content.opf", f'''<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bookid">{identifier}</dc:identifier><dc:title>意义智能 / Meaning Intelligence</dc:title><dc:creator>JING CHENG</dc:creator>{languages_metadata}<dc:date>{DATE}</dc:date><dc:description>Meaning Intelligence audio-book text edition, aligned with Canon V7.0.</dc:description></metadata><manifest>{"".join(f'<item id="{item_id}" href="{href}" media-type="{media}"{f" properties={properties!r}" if properties else ""}/>' for item_id, href, media, properties in manifest_items)}</manifest><spine toc="ncx"><itemref idref="content"/></spine></package>'''),
        ("OEBPS/nav.xhtml", nav),
        ("OEBPS/toc.ncx", ncx),
        ("OEBPS/style.css", style),
        ("OEBPS/cover.xhtml", cover),
        ("OEBPS/content.xhtml", content),
        ("OEBPS/images/cover.jpg", (PACKAGE / "assets" / "cover.jpg").read_bytes()),
    )}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for name, data in files.items():
            if name != "mimetype":
                archive.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)


def copy_release_videos() -> list[tuple[Path, str]]:
    target = PACKAGE / "assets" / "video" / "release"
    target.mkdir(parents=True, exist_ok=True)
    copied: list[tuple[Path, str]] = []
    for name, language in RELEASE_VIDEOS.items():
        source = VIDEO_SOURCE / name
        if not source.is_file():
            raise RuntimeError(f"缺少权威发布视频: {source}")
        destination = target / name
        shutil.copy2(source, destination)
        if sha256(source) != sha256(destination):
            raise RuntimeError(f"发布视频复制校验失败: {name}")
        copied.append((destination, language))
    return copied


def copy_release_support() -> list[Path]:
    mapping = {
        "subtitles.zh.srt": "meaning_intelligence_zh.srt",
        "subtitles.zh.vtt": "meaning_intelligence_zh.vtt",
        "subtitles.en.srt": "meaning_intelligence_en.srt",
        "subtitles.en.vtt": "meaning_intelligence_en.vtt",
        "narration_zh.txt": "narration_zh.txt",
        "narration_en.txt": "narration_en.txt",
        "cover.jpg": "cover.jpg",
        "chapter_manifest.json": "chapter_manifest.json",
        "build/verification.json": "build/verification.json",
    }
    VIDEO_DOWNLOAD.mkdir(parents=True, exist_ok=True)
    copied = []
    for source_name, target_name in mapping.items():
        source = VIDEO_SOURCE / source_name
        if not source.is_file():
            raise RuntimeError(f"缺少发布视频配套文件: {source}")
        destination = VIDEO_DOWNLOAD / target_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if sha256(source) != sha256(destination):
            raise RuntimeError(f"视频配套文件复制校验失败: {source_name}")
        copied.append(destination)
    return copied


def copy_final_documents() -> list[Path]:
    DOCS_DOWNLOAD.mkdir(parents=True, exist_ok=True)
    sources = final_document_sources()
    expected = {source.name for source in sources}
    for stale in DOCS_DOWNLOAD.iterdir():
        if stale.is_file() and stale.name not in expected:
            stale.unlink()
    copied = []
    for source in sources:
        destination = DOCS_DOWNLOAD / source.name
        shutil.copy2(source, destination)
        if sha256(source) != sha256(destination):
            raise RuntimeError(f"最终文档复制校验失败: {source.name}")
        copied.append(destination)
    return copied


def copy_whitepaper() -> list[Path]:
    copied = []
    for suffix, label in (("docx", "DOCX"), ("pdf", "PDF")):
        source = whitepaper_sources()[suffix]
        destination = DOWNLOAD / f"Meaning_Intelligence_White_Paper_v{VERSION}_{label}.{suffix}"
        shutil.copy2(source, destination)
        if sha256(source) != sha256(destination):
            raise RuntimeError(f"白皮书复制校验失败: {suffix}")
        copied.append(destination)
    return copied


def compression_for(path: Path) -> int:
    return zipfile.ZIP_STORED if path.suffix.lower() in {
        ".mp4", ".mp3", ".wav", ".jpg", ".jpeg", ".png", ".docx", ".pdf",
        ".pptx", ".epub", ".zip",
    } else zipfile.ZIP_DEFLATED


def source_zip(path: Path, members: dict[str, Path], metadata: dict) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for name, source in sorted(members.items()):
                archive.write(source, f"meaning-intelligence/{name}", compress_type=compression_for(source))
        with zipfile.ZipFile(temporary) as archive:
            names = set(archive.namelist())
            if archive.testzip():
                raise RuntimeError("源代码 ZIP CRC 校验失败")
            if any(PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts for name in names):
                raise RuntimeError("源代码 ZIP 含不安全路径")
            if any(excluded(Path(name)) for name in names):
                raise RuntimeError("源代码 ZIP 含缓存或敏感文件名")
            if path.name in {PurePosixPath(name).name for name in names}:
                raise RuntimeError("源代码 ZIP 错误地包含自身")
        required = (
            "meaning-intelligence/meaning-agent/README.md",
            "meaning-intelligence/web-mcp/package.json",
            "meaning-intelligence/scripts/build_downloads.py",
            "meaning-intelligence/scripts/build_documents.py",
            "meaning-intelligence/documents/document-manifest.json",
            "meaning-intelligence/video/build_video.py",
            "meaning-intelligence/guide/content.json",
            "meaning-intelligence/guide/verify.py",
            "meaning-intelligence/skills/meaning-intelligence-maintain/SKILL.md",
            "meaning-intelligence/skills/meaning-intelligence-publish/SKILL.md",
            "meaning-intelligence/skills/project-audit-release-sop/SKILL.md",
            "meaning-intelligence/skills/project-audit-release-sop/scripts/validate_skill.py",
            "meaning-intelligence/documents/意义智能_最佳应用指南.md",
            "meaning-intelligence/documents/意义智能_并行审视反思与SOP总结.md",
            "meaning-intelligence/repository/pr_sdk_v2/meaning_intelligence/falsify.py",
            "meaning-intelligence/repository/msi/build.py",
            "meaning-intelligence/repository/whitepaper/build_whitepaper.py",
            "meaning-intelligence/repository/tools/verify_final.py",
            "meaning-intelligence/repository/audit/index.html",
            "meaning-intelligence/repository/check-token.bat",
            "meaning-intelligence/repository/.github/workflows/ci.yml",
        )
        for name in required:
            if name not in names:
                raise RuntimeError(f"源代码 ZIP 缺少: {name}")
        skills = [name for name in names if re.fullmatch(r"meaning-intelligence/meaning-agent/skills/[^/]+/SKILL\.md", name)]
        tests = [name for name in names if name.startswith("meaning-intelligence/meaning-agent/tests/") and name.endswith(".py")]
        if len(skills) != 6 or len(tests) != metadata["test_files"]:
            raise RuntimeError(f"源代码 ZIP 技能/测试不完整: skills={len(skills)}, tests={len(tests)}")
        replace_file(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def reuse_source_archive(path: Path, members: dict[str, Path], metadata: dict) -> None:
    if not path.is_file():
        raise RuntimeError(f"无法复用不存在的源代码 ZIP: {path}")
    expected = {f"meaning-intelligence/{name}": source for name, source in members.items()}
    with zipfile.ZipFile(path) as archive:
        names = {name for name in archive.namelist() if not name.endswith("/")}
        if archive.testzip():
            raise RuntimeError("源代码 ZIP CRC 校验失败")
        if names != set(expected):
            missing = sorted(set(expected) - names)[:8]
            extra = sorted(names - set(expected))[:8]
            raise RuntimeError(f"源代码 ZIP 与当前来源不一致: missing={missing}, extra={extra}")
        for name, source in expected.items():
            if hashlib.sha256(archive.read(name)).digest() != hashlib.sha256(source.read_bytes()).digest():
                raise RuntimeError(f"源代码 ZIP 成员与当前来源字节不一致: {name}")
    metadata["source_archive_reused"] = True
    print(f"PASS 复用并逐字节验证源代码 ZIP: {path}")


def write_verification_report(videos: list[tuple[Path, str]], documents: list[Path], source_metadata: dict, guide_ready: bool, publication_browser: dict, web_media: dict) -> dict:
    guide_evidence = {}
    if guide_ready:
        guide_verification = json.loads((PACKAGE / "project-guide" / "verification.json").read_text(encoding="utf-8"))
        guide_browser = json.loads((PACKAGE / "project-guide" / "browser-check.json").read_text(encoding="utf-8"))
        guide_evidence = {
            "verification_report": "project-guide/verification.json",
            "verification_summary": guide_verification.get("summary"),
            "browser_report": "project-guide/browser-check.json",
            "browser_checks_passed": guide_browser.get("checks_passed"),
            "browser_checks_total": guide_browser.get("checks_total"),
            "narration_duration_seconds": guide_verification.get("summary", {}).get("narration_duration_seconds"),
        }
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "date": DATE,
        "version": VERSION,
        "canon": "V7.0",
        "project_identifier": PROJECT_IDENTIFIER,
        "status": "ready" if guide_ready else "awaiting_project_guide",
        "project_guide": {
            "ready": guide_ready,
            "publication_path": "project-guide/index.html" if guide_ready else None,
            "note": "双语项目说明书已包含。" if guide_ready else "首次构建暂跳过项目说明书；主代理完成并复制到 project-guide 后必须重跑。",
            **guide_evidence,
        },
        "release_videos": [
            {
                "path": path.relative_to(PACKAGE).as_posix(),
                "language": language,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "source": path.relative_to(PACKAGE).as_posix(),
            }
            for path, language in videos
        ],
        "video_verification_report": "download/video/build/verification.json",
        "web_media": {
            "report": WEB_MEDIA_REPORT.name,
            "platform_file_limit_bytes": web_media.get("platform_file_limit_bytes"),
            "masters_modified": web_media.get("masters_modified"),
            "records": web_media.get("records", []),
        },
        "publication_browser": {
            "report": PUBLICATION_BROWSER_REPORT.name,
            "checks_passed": publication_browser.get("checks_passed"),
            "checks_total": publication_browser.get("checks_total"),
            "sha256": sha256(PACKAGE / PUBLICATION_BROWSER_REPORT.name),
        },
        "documents": [
            {"path": path.relative_to(PACKAGE).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in documents
        ],
        "source_archive": {
            "path": SOURCE_ARCHIVE.relative_to(PACKAGE).as_posix(),
            "bytes": SOURCE_ARCHIVE.stat().st_size,
            "sha256": sha256(SOURCE_ARCHIVE),
            **source_metadata,
        },
        "complete_archive": {
            "path": COMPLETE_ARCHIVE.relative_to(PACKAGE).as_posix(),
            "self_included": False,
        },
        "portable_sop_skill": {
            "path": "download/project-audit-release-sop.zip",
            "bytes": (DOWNLOAD / "project-audit-release-sop.zip").stat().st_size,
            "sha256": sha256(DOWNLOAD / "project-audit-release-sop.zip"),
            "prompt_stages": "P00-P16",
        },
        "best_practice_guide": {
            "path": "download/documents/意义智能_最佳应用指南.md",
            "bytes": BEST_PRACTICE_GUIDE.stat().st_size,
            "sha256": sha256(BEST_PRACTICE_GUIDE),
            "languages": ["zh", "en"],
            "skills": ["L1", "L2", "L3", "L4", "L5", "L6"],
            "bilingual_prompt_pairs": True,
        },
        "checks": {
            "release_video_copies_match_sources": True,
            "authoritative_whitepaper_copies_match_sources": True,
            "safe_relative_paths": True,
            "caches_and_secret_files_excluded": True,
            "project_identifier_consistent": True,
            "osf_record_is_project_not_registration_or_preprint": True,
        },
    }
    atomic_write_text(VERIFICATION_REPORT, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def complete_members(curated: dict[str, Path], guide_ready: bool) -> dict[str, Path]:
    members: dict[str, Path] = {}
    for source in sorted(PACKAGE.rglob("*")):
        if not source.is_file() or source.resolve() in {COMPLETE_ARCHIVE.resolve(), PROVISIONAL_ARCHIVE.resolve()}:
            continue
        relative = safe_relative(source, PACKAGE)
        if relative.as_posix() in {
            "scripts/build_downloads.py",
            "scripts/verify_package.py",
            "skills/meaning-intelligence-publish/scripts/build_downloads.py",
            "skills/meaning-intelligence-publish/scripts/verify_package.py",
            "guide/build.py",
        }:
            continue
        if excluded(relative) or source.name.startswith("meaning_intelligence_launch"):
            continue
        if relative.parts[0] == "project-guide" and not guide_ready:
            continue
        add_member(members, relative.as_posix(), source)
    for name, source in curated.items():
        add_member(members, name, source)
    for name in ("meaning_intelligence_zh.mp4", "meaning_intelligence_en.mp4"):
        add_member(members, f"video/{name}", PACKAGE / "assets" / "video" / "release" / name)
    for source in sorted(VIDEO_DOWNLOAD.rglob("*")):
        if source.is_file():
            relative = safe_relative(source, VIDEO_DOWNLOAD)
            add_member(members, f"video/{relative.as_posix()}", source)
    for source in sorted(DOCS_DOWNLOAD.rglob("*")):
        if source.is_file():
            relative = safe_relative(source, DOCS_DOWNLOAD)
            add_member(members, f"documents/{relative.as_posix()}", source)
    add_member(members, "manifest.json", DOWNLOAD / "manifest.json")
    add_member(members, "verification.json", VERIFICATION_REPORT)
    return members


def build_complete_zip(curated: dict[str, Path], guide_ready: bool, provisional_entries: list[dict], target: Path | None = None) -> int:
    target = target or COMPLETE_ARCHIVE
    members = complete_members(curated, guide_ready)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for name, source in sorted(members.items()):
                archive.write(source, name, compress_type=compression_for(source))
        with zipfile.ZipFile(temporary) as archive:
            names = set(archive.namelist())
            if archive.testzip():
                raise RuntimeError("完整交付 ZIP CRC 校验失败")
            if any(PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name for name in names):
                raise RuntimeError("完整交付 ZIP 含不安全路径")
            if any(excluded(Path(name)) for name in names):
                raise RuntimeError("完整交付 ZIP 含缓存或敏感文件名")
            if target.name in {PurePosixPath(name).name for name in names}:
                raise RuntimeError("完整交付 ZIP 错误地包含自身")
            if any("meaning_intelligence_launch" in name for name in names):
                raise RuntimeError("完整交付 ZIP 仍含旧发布视频")
            required = [
                "index.html", "manifest.json", "verification.json", "downloads.html", "video/build_video.py",
                "assets/audio-web.mp3",
                "assets/video/release/meaning_intelligence_zh-web.mp4",
                "assets/video/release/meaning_intelligence_en-web.mp4",
                "publication-browser-check.json", "web-media-verification.json",
                "skills/meaning-intelligence-maintain/SKILL.md",
                "skills/meaning-intelligence-publish/SKILL.md",
                "skills/project-audit-release-sop/SKILL.md",
                "skills/project-audit-release-sop/references/prompt-library.md",
                "skills/project-audit-release-sop/scripts/validate_skill.py",
                "download/project-audit-release-sop.zip",
                "documents/意义智能_最佳应用指南.md",
                "documents/意义智能_并行审视反思与SOP总结.md",
                "documents/意义智能_附件衍生更新版_2026-11-26.pdf",
                "documents/意义智能_书稿勘误与补充说明_2026-11-26.pdf",
                "documents/意义智能_项目审查与优化报告_2026-11-26.pdf",
                "documents/意义智能_有声读物_发布指南与操作手册_v3.0.pdf",
                "documents/意义智能有声读物_发布指南与操作手册.md",
            ]
            if guide_ready:
                required.extend([
                    "project-guide/index.html",
                    "project-guide/content.js",
                    "project-guide/verification.js",
                    "project-guide/manifest.json",
                    "project-guide/verification.json",
                    "project-guide/browser-check.json",
                    "project-guide/downloads/project-guide-bilingual.pdf",
                    "project-guide/downloads/project-guide-bilingual.docx",
                    "project-guide/downloads/guide-narration-zh.mp3",
                    "project-guide/downloads/guide-narration-en.mp3",
                ])
            for name in required:
                if name not in names:
                    raise RuntimeError(f"完整交付 ZIP 缺少: {name}")
            json.loads(archive.read("manifest.json"))
            json.loads(archive.read("verification.json"))
            for entry in provisional_entries:
                name = entry["path"]
                if name not in names:
                    raise RuntimeError(f"完整交付 ZIP 缺少 manifest 资源: {name}")
                if archive.getinfo(name).file_size != entry["bytes"]:
                    raise RuntimeError(f"完整交付 ZIP 资源字节数不一致: {name}")
        replace_file(temporary, target)
        return len(names)
    finally:
        if temporary.exists():
            temporary.unlink()


def stabilize_complete_package(curated: dict[str, Path], guide_ready: bool, entries: list[dict]) -> int:
    report_path = PACKAGE / PUBLICATION_BROWSER_REPORT.name
    browser = json.loads(report_path.read_text(encoding="utf-8"))
    updated = 0
    for check in browser.get("checks", []):
        if check.get("name") == "download-range-request":
            check["detail"], count = re.subn(r"(bytes \d+-\d+)/\d+", r"\1", check["detail"])
            if count != 1:
                raise RuntimeError("发布页 Range 检查格式不符合预期")
            updated += 1
    if updated != 1:
        raise RuntimeError("发布页报告缺少唯一的 Range 检查")
    atomic_write_text(report_path, json.dumps(browser, ensure_ascii=False, indent=2) + "\n")
    verification = json.loads(VERIFICATION_REPORT.read_text(encoding="utf-8"))
    verification["publication_browser"]["sha256"] = sha256(report_path)
    atomic_write_text(VERIFICATION_REPORT, json.dumps(verification, ensure_ascii=False, indent=2) + "\n")
    for entry in entries:
        source = PACKAGE / entry["path"]
        entry["bytes"] = source.stat().st_size
        entry["sha256"] = sha256(source)
    write_manifest(entries)
    download_page(entries)
    candidate = Path(tempfile.gettempdir()) / f"meaning-intelligence-complete-{os.getpid()}.stabilizing.zip"
    try:
        member_count = build_complete_zip(curated, guide_ready, entries, candidate)
        if COMPLETE_ARCHIVE.exists():
            replace_file(candidate, COMPLETE_ARCHIVE)
        else:
            os.replace(candidate, COMPLETE_ARCHIVE)
        return member_count
    finally:
        if candidate.exists():
            candidate.unlink()


def make_entry(path: Path, label_zh: str, label_en: str, kind: str, category: str, language: str) -> dict:
    relative = safe_relative(path, PACKAGE)
    return {
        "path": relative.as_posix(),
        "label_zh": label_zh,
        "label_en": label_en,
        "kind": kind,
        "category": category,
        "language": language,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def validate_download_page(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "manifest" not in text.lower():
        raise RuntimeError("downloads.html 缺少字面 manifest")
    parser = ReferenceParser()
    parser.feed(text)
    for ref in parser.refs:
        parsed = urlsplit(ref)
        if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("#"):
            continue
        target = unquote(parsed.path)
        candidate = PACKAGE / target.lstrip("/") if target.startswith("/") else path.parent / target
        if not candidate.is_file():
            raise RuntimeError(f"downloads.html 引用缺失: {ref}")


def download_page(entries: list[dict]) -> None:
    cards = []
    for entry in entries:
        href = quote(entry["path"])
        size = f'{entry["bytes"] / 1048576:.2f} MiB' if entry["bytes"] >= 1048576 else f'{entry["bytes"] / 1024:.1f} KiB'
        cards.append(f'''<article class="download"><div><span class="kind">{html.escape(entry["kind"])}</span><h2>{html.escape(entry["label_zh"])}</h2><p class="en">{html.escape(entry["label_en"])}</p><small>{size} · SHA-256 {entry["sha256"][:16]}…</small></div><a href="{href}" download>下载 / Download</a></article>''')
    page = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>意义智能 · 下载中心 / Downloads</title><style>:root{{--bg:#0b1020;--card:#131b33;--line:#24325c;--gold:#e8b34b;--cyan:#5ad1e6;--text:#e8ecf6;--dim:#9aa7c7}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,"Microsoft YaHei",sans-serif;line-height:1.6}}main{{max-width:1050px;margin:auto;padding:42px 20px 80px}}header{{text-align:center;margin-bottom:34px}}h1{{font-size:clamp(28px,5vw,44px);margin:0 0 8px}}header p,.en,small{{color:var(--dim)}}.toolbar,.language-switch{{display:flex;justify-content:center;gap:12px;margin:20px;flex-wrap:wrap}}.toolbar a,.language-switch button{{color:var(--cyan);border:1px solid var(--cyan);border-radius:999px;padding:8px 18px;text-decoration:none;background:transparent;font:inherit;cursor:pointer}}.download{{display:flex;gap:20px;justify-content:space-between;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;margin:12px 0}}.download h2{{margin:4px 0;color:var(--gold);font-size:20px}}.download p{{margin:0}}.kind{{font-size:12px;color:var(--cyan);letter-spacing:.08em}}.download a{{flex:none;background:var(--gold);color:#0b1020;text-decoration:none;font-weight:700;border-radius:999px;padding:10px 18px}}footer{{text-align:center;color:var(--dim);margin-top:36px}}.mi-skip-link{{position:absolute;left:16px;top:-96px;z-index:999;background:var(--gold);color:var(--bg);padding:10px 16px;border-radius:8px;font:700 15px system-ui,"Microsoft YaHei",sans-serif}}.mi-skip-link:focus{{top:12px;outline:3px solid var(--cyan);outline-offset:3px}}[data-en]{{display:none}}html.en [data-zh]{{display:none}}html.en [data-en]{{display:inline}}@media(max-width:640px){{.download{{align-items:flex-start;flex-direction:column}}.download a{{width:100%;text-align:center}}}}</style></head><body><a class="mi-skip-link" href="#main">跳转到正文 / Skip to content</a><main id="main" tabindex="-1"><header><h1><span data-zh>下载中心</span><span data-en>Downloads</span></h1><p><span data-zh>意义智能 / Meaning Intelligence 发布资源</span><span data-en>Meaning Intelligence publication resources</span></p><div class="language-switch"><button id="btnZh" type="button" onclick="setLang('zh')">中文</button><button id="btnEn" type="button" onclick="setLang('en')">English</button></div><div class="toolbar"><a href="index.html">视听中心 / Media</a><a href="listen.html">有声读物 / Audio Book</a><a href="mcp.html">Web MCP</a><a href="download/manifest.json">manifest.json</a></div></header>{"".join(cards)}<footer>所有文件均提供 SHA-256 校验值 · manifest · Canon V7.0 · {DATE}</footer></main><script>function setLang(lang){{document.documentElement.lang=lang==='en'?'en':'zh-CN';document.documentElement.classList.toggle('en',lang==='en');}}</script></body></html>'''
    path = PACKAGE / "downloads.html"
    atomic_write_text(path, page)
    validate_download_page(path)


def write_manifest(entries: list[dict]) -> None:
    seen: set[str] = set()
    for entry in entries:
        relative = entry["path"]
        pure = PurePosixPath(relative)
        if not relative or pure.is_absolute() or ".." in pure.parts or "\\" in relative or relative in seen:
            raise RuntimeError(f"manifest 路径不安全或重复: {relative}")
        if not (PACKAGE / relative).is_file():
            raise RuntimeError(f"manifest 文件不存在: {relative}")
        seen.add(relative)
    manifest = {
        "version": VERSION,
        "generated": DATE,
        "canon": "V7.0",
        "project_identifier": PROJECT_IDENTIFIER,
        "complete_package": COMPLETE_ARCHIVE.relative_to(PACKAGE).as_posix(),
        "files": entries,
    }
    atomic_write_text(DOWNLOAD / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-missing-guide", action="store_true", help="首次构建可暂缺项目说明书，并在 verification.json 中如实记录")
    parser.add_argument("--reuse-source-archive", action="store_true", help="复用现有源码 ZIP，但逐成员核对当前来源字节")
    args = parser.parse_args()
    version_text = (REPO / "VERSION.yaml").read_text(encoding="utf-8")
    for key, expected in PROJECT_IDENTIFIER.items():
        expected_text = str(expected).lower() if isinstance(expected, bool) else str(expected)
        if expected_text not in version_text:
            raise RuntimeError(f"VERSION.yaml 项目标识字段缺失或不一致: {key}")
    required = [
        PACKAGE / "assets" / "audio.mp3", PACKAGE / "assets_en" / "audio_en.mp3",
        PACKAGE / "assets" / "cover.jpg", PACKAGE / "subtitles.json",
        PACKAGE / "subtitles_en.json", PACKAGE / "timeline_en.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        print("FAIL 缺少发布源文件:", *missing, sep="\n")
        return 1
    subprocess.run([sys.executable, str(PUBLISH_SCRIPTS / "prepare_web_media.py")], check=True)
    web_media = sync_web_media_report()
    guide_ready = sync_project_guide()
    if not guide_ready and not args.allow_missing_guide:
        print("FAIL 缺少 project-guide/index.html；首次构建可显式使用 --allow-missing-guide，完成后必须重跑。")
        return 1
    if not guide_ready:
        print("WARN 首次构建暂跳过 project-guide；其余交付物继续打包。")

    DOWNLOAD.mkdir(parents=True, exist_ok=True)
    DOCS_DOWNLOAD.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DELIVERABLES / "project-audit-release-sop.zip", DOWNLOAD / "project-audit-release-sop.zip")
    shutil.copy2(DELIVERABLES / "意义智能_并行审视反思与SOP总结.md", DOCS_DOWNLOAD / "意义智能_并行审视反思与SOP总结.md")
    archive_stale_videos()
    write_subtitles()
    zh_cues = json.loads((PACKAGE / "subtitles.json").read_text(encoding="utf-8"))
    en_cues = json.loads((PACKAGE / "subtitles_en.json").read_text(encoding="utf-8"))
    en_chapters = [(item["t"], item["n"]) for item in json.loads((PACKAGE / "timeline_en.json").read_text(encoding="utf-8"))["chapters"]]
    zh_text = chapter_text(zh_cues, ZH_CHAPTERS)
    en_text = chapter_text(en_cues, en_chapters)
    for language, label in (("bilingual", "ZH-EN"), ("zh", "ZH"), ("en", "EN")):
        build_epub(DOWNLOAD / f"Meaning_Intelligence_Audio_Book_v{VERSION}_{label}.epub", language, zh_text, en_text)

    whitepaper = copy_whitepaper()
    videos = copy_release_videos()
    support = copy_release_support()
    documents = copy_final_documents()
    curated, source_metadata = curated_sources()
    if args.reuse_source_archive:
        reuse_source_archive(SOURCE_ARCHIVE, curated, source_metadata)
    else:
        source_zip(SOURCE_ARCHIVE, curated, source_metadata)
    finalize_listen(PACKAGE / "listen.html")
    finalize_index(PACKAGE / "index.html")
    for name in ("index.html", "listen.html", "downloads.html", "mcp.html"):
        page = PACKAGE / name
        if page.is_file():
            finalize_project_identifier(page)
    for name in ("index.html", "listen.html", "mcp.html"):
        finalize_accessibility(PACKAGE / name)

    candidates: list[tuple[Path, str, str, str, str, str]] = [
        (PACKAGE / "assets" / "audio.mp3", "中文有声读物母版", "Chinese audio-book master", "音频 / Audio", "audio", "zh"),
        (PACKAGE / "assets" / "audio-web.mp3", "中文有声读物在线版", "Chinese streaming audio book", "音频 / Audio", "audio", "zh"),
        (PACKAGE / "assets_en" / "audio_en.mp3", "英文有声读物", "English audio book", "音频 / Audio", "audio", "en"),
        (DOWNLOAD / "Meaning_Intelligence_Audio_Book_v1.1_ZH-EN.epub", "双语电子书", "Bilingual EPUB", "电子书 / EPUB", "ebook", "bilingual"),
        (DOWNLOAD / "Meaning_Intelligence_Audio_Book_v1.1_ZH.epub", "中文电子书", "Chinese EPUB", "电子书 / EPUB", "ebook", "zh"),
        (DOWNLOAD / "Meaning_Intelligence_Audio_Book_v1.1_EN.epub", "英文电子书", "English EPUB", "电子书 / EPUB", "ebook", "en"),
        (DOWNLOAD / "Meaning_Intelligence_Chinese_subtitles.srt", "中文有声书字幕", "Chinese audio-book subtitles", "字幕 / Subtitles", "subtitles", "zh"),
        (DOWNLOAD / "Meaning_Intelligence_English_subtitles.srt", "英文有声书字幕", "English audio-book subtitles", "字幕 / Subtitles", "subtitles", "en"),
        (VIDEO_DOWNLOAD / "meaning_intelligence_zh.srt", "中文发布视频字幕", "Chinese release-video subtitles", "字幕 / Subtitles", "subtitles", "zh"),
        (VIDEO_DOWNLOAD / "meaning_intelligence_zh.vtt", "中文发布视频字幕", "Chinese release-video subtitles", "字幕 / Subtitles", "subtitles", "zh"),
        (VIDEO_DOWNLOAD / "meaning_intelligence_en.srt", "英文发布视频字幕", "English release-video subtitles", "字幕 / Subtitles", "subtitles", "en"),
        (VIDEO_DOWNLOAD / "meaning_intelligence_en.vtt", "英文发布视频字幕", "English release-video subtitles", "字幕 / Subtitles", "subtitles", "en"),
        (PACKAGE / "subtitles.vtt", "中文兼容字幕", "Chinese compatibility subtitles", "字幕 / Subtitles", "subtitles", "zh"),
        (VIDEO_DOWNLOAD / "narration_zh.txt", "中文发布视频旁白稿", "Chinese release-video narration", "旁白 / Narration", "narration", "zh"),
        (VIDEO_DOWNLOAD / "narration_en.txt", "英文发布视频旁白稿", "English release-video narration", "旁白 / Narration", "narration", "en"),
        (VIDEO_DOWNLOAD / "cover.jpg", "发布视频封面", "Release-video cover", "封面 / Cover", "cover", "bilingual"),
        (VIDEO_DOWNLOAD / "chapter_manifest.json", "发布视频章节清单", "Release-video chapter manifest", "清单 / Manifest", "verification", "bilingual"),
        (VIDEO_DOWNLOAD / "build" / "verification.json", "发布视频验证报告", "Release-video verification report", "验证 / Verification", "verification", "und"),
        (whitepaper[0], "中英双语白皮书", "Bilingual white paper", "文档 / DOCX", "document", "bilingual"),
        (whitepaper[1], "中英双语白皮书", "Bilingual white paper", "文档 / PDF", "document", "bilingual"),
        (PACKAGE / "download" / "意义智能_讲课展示.pptx", "讲课展示（含语音）", "Lecture deck with narration", "演示 / PPTX", "presentation", "bilingual"),
        (PACKAGE / "download" / "MSI演进视频讲解版.pptx", "MSI 演进讲解（含语音）", "MSI evolution deck with narration", "演示 / PPTX", "presentation", "bilingual"),
        (PACKAGE / "assets" / "video" / "MeaningIntelligenceScene.mp4", "MSI 演进短视频", "MSI evolution video", "视频 / Video", "video", "bilingual"),
        (SOURCE_ARCHIVE, "可运行项目源代码", "Runnable project source code", "代码 / Source", "source", "bilingual"),
        (DOWNLOAD / "project-audit-release-sop.zip", "可迁移项目审查与发布 SOP Skill", "Portable project audit and release SOP Skill", "Skill / SOP", "skill", "bilingual"),
    ]
    for path, language in videos:
        if language == "zh":
            labels = ("中文发布讲解视频 1080p 母版", "Chinese release explainer video 1080p master")
        else:
            labels = ("英文发布讲解视频 1080p 母版", "English release explainer video 1080p master")
        candidates.append((path, labels[0], labels[1], "视频 / Video", "video", language))
    for language, label in (("zh", "中文"), ("en", "英文")):
        path = PACKAGE / "assets" / "video" / "release" / f"meaning_intelligence_{language}-web.mp4"
        candidates.append((path, f"{label}发布讲解视频在线版", f"{'Chinese' if language == 'zh' else 'English'} streaming release video", "视频 / Video", "video", language))
    for path in documents:
        label = path.stem
        candidates.append((path, label, label, "文档 / Document", "document", "bilingual" if "指南" in path.name or "SOP" in path.name else "zh"))
    if guide_ready:
        candidates.extend([
            (PACKAGE / "project-guide" / "index.html", "双语图文音频项目说明书", "Bilingual illustrated audio project guide", "指南 / Guide", "guide", "bilingual"),
            (PACKAGE / "project-guide" / "downloads" / "project-guide-bilingual.pdf", "项目说明书 PDF", "Project guide PDF", "指南 / Guide", "guide", "bilingual"),
            (PACKAGE / "project-guide" / "downloads" / "project-guide-bilingual.docx", "项目说明书 Word", "Project guide Word document", "指南 / Guide", "guide", "bilingual"),
            (PACKAGE / "project-guide" / "downloads" / "guide-narration-zh.mp3", "项目说明书中文音频", "Chinese project-guide narration", "音频 / Audio", "audio", "zh"),
            (PACKAGE / "project-guide" / "downloads" / "guide-narration-en.mp3", "项目说明书英文音频", "English project-guide narration", "音频 / Audio", "audio", "en"),
        ])

    entries = [make_entry(*candidate) for candidate in candidates]
    provisional_entries = list(entries)
    if COMPLETE_ARCHIVE.is_file():
        provisional_entries.insert(0, make_entry(COMPLETE_ARCHIVE, "意义智能完整交付包", "Meaning Intelligence complete delivery package", "完整交付 / Complete", "package", "bilingual"))
    write_manifest(provisional_entries)
    download_page(provisional_entries)
    for name in ("index.html", "listen.html", "downloads.html", "mcp.html"):
        page = PACKAGE / name
        if page.is_file():
            finalize_project_identifier(page)
    if not COMPLETE_ARCHIVE.is_file():
        build_complete_zip(curated, guide_ready, provisional_entries, PROVISIONAL_ARCHIVE)
        provisional_entries.insert(0, make_entry(PROVISIONAL_ARCHIVE, "意义智能完整交付包", "Meaning Intelligence complete delivery package", "完整交付 / Complete", "package", "bilingual"))
        write_manifest(provisional_entries)
        download_page(provisional_entries)
    subprocess.run([
        "node", str(PUBLISH_SCRIPTS / "browser_verify.mjs"),
        str(PACKAGE), str(PUBLICATION_BROWSER_REPORT),
    ], check=True)
    publication_browser = sync_publication_browser_report()
    write_verification_report(videos, documents + whitepaper, source_metadata, guide_ready, publication_browser, web_media)
    candidates.extend([
        (VERIFICATION_REPORT, "交付构建验证报告", "Delivery build verification report", "验证 / Verification", "verification", "und"),
        (PACKAGE / PUBLICATION_BROWSER_REPORT.name, "发布页真实浏览器检查", "Publication real-browser check", "验证 / Verification", "verification", "und"),
        (PACKAGE / WEB_MEDIA_REPORT.name, "流媒体派生验证", "Streaming-media derivative verification", "验证 / Verification", "verification", "und"),
    ])
    entries = [make_entry(*candidate) for candidate in candidates]
    write_manifest(entries)
    # The self-excluding ZIP gets an offline page without a link to itself.
    download_page(entries)
    member_count = stabilize_complete_package(curated, guide_ready, entries)
    entries.insert(0, make_entry(COMPLETE_ARCHIVE, "意义智能完整交付包", "Meaning Intelligence complete delivery package", "完整交付 / Complete", "package", "bilingual"))
    write_manifest(entries)
    download_page(entries)
    for name in ("index.html", "listen.html", "downloads.html", "mcp.html"):
        page = PACKAGE / name
        if page.is_file():
            finalize_project_identifier(page)

    package_files = [
        path for path in PACKAGE.rglob("*")
        if path.is_file() and not excluded(path.relative_to(PACKAGE))
        and not any(marker in path.name.lower() for marker in (".uploading", ".downloading", ".tmp", ".part", ".crdownload"))
    ]
    package_bytes = sum(path.stat().st_size for path in package_files)
    print(f"PASS {len(entries)} 个可下载资源；EPUB 3 个；完整 ZIP {member_count} 个成员")
    print(f"PASS 完整交付包: {COMPLETE_ARCHIVE} ({COMPLETE_ARCHIVE.stat().st_size} bytes)")
    print(f"PASS 发布包 {len(package_files)} 个文件；{package_bytes} bytes ({package_bytes / 1048576:.1f} MiB)")
    if not guide_ready:
        print("REMAINING project-guide/index.html 尚未由主代理复制；本次按要求仅跳过指南包装。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
