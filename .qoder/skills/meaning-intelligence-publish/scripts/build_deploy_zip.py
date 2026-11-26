#!/usr/bin/env python3
"""Build a verified Cloudflare Pages staging tree and deployment ZIP.

The publication package is read-only. Large local masters, the complete delivery
ZIP, caches, temporary files, and sync artifacts are replaced or excluded only
in the deployment staging tree.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import os
import posixpath
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

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")

WORKSPACE = Path(__file__).resolve().parents[2]
PACKAGE = WORKSPACE / "意义智能有声读物_发布包"
DELIVERABLES = WORKSPACE / "deliverables"
DEFAULT_OUTPUT = DELIVERABLES / "意义智能_部署包.zip"
DEFAULT_STAGING = DELIVERABLES / "meaning-intelligence-deploy-staging"
DEFAULT_REPORT = DELIVERABLES / "deployment-report.json"
MAX_FILE_BYTES = 25 * 1024 * 1024

EXCLUDED_PARTS = {
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".cache", "cache", "node_modules", ".wrangler", ".lingxi",
    ".qoder", ".ipynb_checkpoints",
}
EXCLUDED_NAMES = {
    ".env", ".env.local", ".npmrc", ".netrc", "credentials.json", "token.txt",
    "tokens.json", "secrets.json", "id_rsa", "id_ed25519", ".ds_store",
    "desktop.ini", "thumbs.db",
}
EXCLUDED_SUFFIXES = {
    ".tmp", ".temp", ".part", ".crdownload", ".uploading", ".downloading",
    ".swp", ".swo", ".bak", ".pyc", ".pyo", ".pem", ".key", ".pfx", ".p12",
}
EXPLICIT_EXCLUSIONS = {
    "assets/audio.mp3": "original oversized Chinese audio; use assets/audio-web.mp3",
    "assets/video/release/meaning_intelligence_zh.mp4": "original 1080p Chinese master; use web derivative",
    "assets/video/release/meaning_intelligence_en.mp4": "original 1080p English master; use web derivative",
    "project-guide/downloads/meaning-intelligence-zh.mp4": "remaining 1080p Chinese guide copy; use web derivative",
    "project-guide/downloads/meaning-intelligence-en.mp4": "remaining 1080p English guide copy; use web derivative",
    "project-guide/downloads/guide-narration-zh.mp3": "original oversized Chinese guide narration; use 48 kb/s web derivative",
    "project-guide/downloads/guide-narration-en.mp3": "original English guide narration; use 48 kb/s web derivative",
}
DERIVATIVES = {
    "assets/audio.mp3": {
        "path": "assets/audio-web.mp3", "label_zh": "中文有声读物（网页版）",
        "label_en": "Chinese audio book (web)", "kind": "音频 / Audio (Web)",
        "category": "audio", "language": "zh",
    },
    "assets/video/release/meaning_intelligence_zh.mp4": {
        "path": "assets/video/release/meaning_intelligence_zh-web.mp4",
        "label_zh": "中文发布讲解视频（网页版）", "label_en": "Chinese release explainer video (web)",
        "kind": "视频 / Video (Web)", "category": "video", "language": "zh",
    },
    "assets/video/release/meaning_intelligence_en.mp4": {
        "path": "assets/video/release/meaning_intelligence_en-web.mp4",
        "label_zh": "英文发布讲解视频（网页版）", "label_en": "English release explainer video (web)",
        "kind": "视频 / Video (Web)", "category": "video", "language": "en",
    },
    "project-guide/downloads/guide-narration-zh.mp3": {
        "path": "project-guide/downloads/guide-narration-zh-web.mp3",
        "label_zh": "项目说明书中文音频（网页版）", "label_en": "Chinese project-guide narration (web)",
        "kind": "音频 / Audio (Web)", "category": "audio", "language": "zh",
    },
    "project-guide/downloads/guide-narration-en.mp3": {
        "path": "project-guide/downloads/guide-narration-en-web.mp3",
        "label_zh": "项目说明书英文音频（网页版）", "label_en": "English project-guide narration (web)",
        "kind": "音频 / Audio (Web)", "category": "audio", "language": "en",
    },
}
GUIDE_LINKS = {
    "downloads/meaning-intelligence-zh.mp4": "../assets/video/release/meaning_intelligence_zh-web.mp4",
    "downloads/meaning-intelligence-en.mp4": "../assets/video/release/meaning_intelligence_en-web.mp4",
    "downloads/guide-narration-zh.mp3": "downloads/guide-narration-zh-web.mp3",
    "downloads/guide-narration-en.mp3": "downloads/guide-narration-en-web.mp3",
}
GUIDE_1080_DESCRIPTIONS = (
    "1080p H.264/AAC，含可选中文字幕与音轨。",
    "1080p H.264/AAC with selectable Chinese subtitles and audio.",
    "1080p H.264/AAC，含可选中英字幕与音轨。",
    "1080p H.264/AAC with selectable Chinese/English subtitles and audio.",
)
REQUIRED_DEPLOYMENT_FILES = {
    "index.html", "listen.html", "downloads.html", "mcp.html",
    "project-guide/index.html", "download/manifest.json",
    *(item["path"] for item in DERIVATIVES.values() if not item["path"].startswith("project-guide/")),
}


class ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []
        self.ids: set[str] = set()
        self.langs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag.lower() == "html" and values.get("lang"):
            self.langs.append(values["lang"])
        if values.get("id"):
            self.ids.add(values["id"])
        for key in ("src", "href", "poster"):
            if values.get(key):
                self.refs.append(values[key])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_bytes(rel: str, data: bytes) -> dict:
    return {"path": rel, "bytes": len(data), "sha256": hash_bytes(data)}


def record_file(rel: str, path: Path) -> dict:
    before = path.stat().st_size
    digest = sha256(path)
    after = path.stat().st_size
    if before != after:
        raise RuntimeError(f"源文件在读取时发生变化: {rel}")
    return {"path": rel, "bytes": after, "sha256": digest}


def prepare_guide_audio(records: dict[str, dict]) -> list[dict]:
    changes = []
    for language, label in (("zh", "Chinese"), ("en", "English")):
        source_rel = f"project-guide/downloads/guide-narration-{language}.mp3"
        source = PACKAGE / source_rel
        target_rel = DERIVATIVES[source_rel]["path"]
        with tempfile.TemporaryDirectory(prefix="mi-guide-audio-") as temporary:
            output = Path(temporary) / PurePosixPath(target_rel).name
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-i", str(source), "-map_metadata", "0",
                "-ac", "1", "-c:a", "libmp3lame", "-b:a", "48k", str(output),
            ], check=True, capture_output=True)
            probe = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(output),
            ], text=True, encoding="utf-8"))
            duration = float(probe["format"]["duration"])
            data = output.read_bytes()
        if len(data) >= MAX_FILE_BYTES or duration <= 120:
            raise RuntimeError(f"{label} guide audio derivative exceeds 25 MiB or is too short")
        records[target_rel] = record_bytes(target_rel, data)
        records[target_rel]["_data"] = data
        changes.append({
            "path": target_rel, "source": source_rel, "bytes": len(data),
            "sha256": records[target_rel]["sha256"], "duration_seconds": duration,
            "reason": "48 kb/s mono web derivative; local master unchanged",
        })
    return changes


def guide_record_rel(link: str) -> str:
    return link.removeprefix("../") if link.startswith("../") else f"project-guide/{link}"


def safe_relative(value: str) -> str:
    pure = PurePosixPath(value)
    if not value or pure.is_absolute() or ".." in pure.parts or "\\" in value or pure.as_posix() != value:
        raise ValueError(f"不安全相对路径: {value!r}")
    return pure.as_posix()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def is_complete_package(rel: str) -> bool:
    rel = safe_relative(rel)
    return rel.startswith("download/") and rel.lower().endswith(".zip") and "完整交付包" in PurePosixPath(rel).name


def exclusion_reason(rel: str, path: Path, output: Path) -> str | None:
    pure = PurePosixPath(rel)
    lowered = [part.lower() for part in pure.parts]
    name = pure.name.lower()
    if path.resolve() == output.resolve() or path.name == output.name:
        return "deployment ZIP itself"
    if is_complete_package(rel):
        return "local complete delivery ZIP"
    if rel in EXPLICIT_EXCLUSIONS:
        return EXPLICIT_EXCLUSIONS[rel]
    if rel.startswith("project-guide/downloads/") and pure.suffix.lower() == ".mp4":
        if name in {"meaning_intelligence_zh.mp4", "meaning_intelligence_en.mp4", "release-zh.mp4", "release-en.mp4"} or "1080p" in name:
            return "remaining 1080p release copy under project-guide/downloads"
    if any(part in EXCLUDED_PARTS for part in lowered):
        return "cache, dependency, VCS, or tool directory"
    if name in EXCLUDED_NAMES or name.startswith(".env"):
        return "secret, system, or metadata file"
    if name.startswith(("~$", ".~lock", ".baidu")) or ("baidu" in name and "sync" in name):
        return "Baidu sync or Office lock artifact"
    if ".uploading" in name or ".downloading" in name or pure.suffix.lower() in EXCLUDED_SUFFIXES:
        return "temporary, partial, backup, or compiled artifact"
    if path.is_symlink():
        return "symbolic link"
    return None


def collect_sources(output: Path) -> tuple[dict[str, Path], list[dict], list[str]]:
    sources: dict[str, Path] = {}
    exclusions: list[dict] = []
    errors: list[str] = []
    for path in sorted(PACKAGE.rglob("*")):
        try:
            rel = safe_relative(path.relative_to(PACKAGE).as_posix())
            if not path.is_file():
                continue
            reason = exclusion_reason(rel, path, output)
            if reason:
                exclusions.append({"path": rel, "reason": reason})
            else:
                sources[rel] = path
        except (OSError, ValueError) as exc:
            errors.append(f"发布包扫描失败 {path}: {exc}")
    for rel in sorted(REQUIRED_DEPLOYMENT_FILES):
        if rel not in sources:
            errors.append(f"部署必需文件缺失或被排除: {rel}")
    return sources, exclusions, errors


def derivative_entry(source_rel: str, record: dict) -> dict:
    metadata = DERIVATIVES[source_rel]
    return {
        "path": metadata["path"], "label_zh": metadata["label_zh"],
        "label_en": metadata["label_en"], "kind": metadata["kind"],
        "category": metadata["category"], "language": metadata["language"],
        "bytes": record["bytes"], "sha256": record["sha256"],
        "web_derivative": True, "replaces": source_rel,
    }


def deployment_manifest(source_manifest: dict, records: dict[str, dict], sources: dict[str, Path], exclusions: list[dict]) -> tuple[dict, dict, list[str]]:
    errors: list[str] = []
    info = {"removed_entries": [], "replaced_entries": [], "added_entries": []}
    excluded = {item["path"]: item["reason"] for item in exclusions}
    result = copy.deepcopy(source_manifest)
    if "complete_package" in result:
        info["removed_entries"].append({"path": result["complete_package"], "reason": "complete_package top-level field removed"})
        result.pop("complete_package", None)
    source_entries = result.get("files")
    if not isinstance(source_entries, list) or not source_entries:
        return {}, info, ["download/manifest.json files 必须是非空数组"]
    entries: list[dict] = []
    source_seen: set[str] = set()
    output_seen: set[str] = set()
    complete_paths = {entry.get("path") for entry in source_entries if isinstance(entry, dict) and entry.get("category") == "package"}
    for original in source_entries:
        if not isinstance(original, dict):
            errors.append("download/manifest.json 含非对象条目")
            continue
        try:
            rel = safe_relative(str(original.get("path", "")))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if rel in source_seen:
            errors.append(f"download/manifest.json 重复路径: {rel}")
            continue
        source_seen.add(rel)
        if original.get("category") == "package" or is_complete_package(rel):
            info["removed_entries"].append({"path": rel, "reason": "complete-package entry removed"})
            continue
        if rel in DERIVATIVES:
            target = DERIVATIVES[rel]["path"]
            if target not in records:
                errors.append(f"网页派生文件不可用: {target}")
                continue
            entry = derivative_entry(rel, records[target])
            info["replaced_entries"].append({"from": rel, "to": target})
        elif rel in sources:
            entry = copy.deepcopy(original)
            entry.update({"bytes": records[rel]["bytes"], "sha256": records[rel]["sha256"]})
            if rel in excluded:
                errors.append(f"manifest 条目同时被选择和排除: {rel}")
                continue
        elif rel in excluded:
            info["removed_entries"].append({"path": rel, "reason": excluded[rel]})
            continue
        else:
            errors.append(f"manifest 部署资源缺失: {rel}")
            continue
        if entry["path"] in output_seen:
            if rel in DERIVATIVES or rel in {item["path"] for item in DERIVATIVES.values()}:
                continue
            errors.append(f"manifest 替换后路径重复: {entry['path']}")
            continue
        output_seen.add(entry["path"])
        entries.append(entry)
    present = {entry["path"] for entry in entries}
    for source_rel, metadata in DERIVATIVES.items():
        target = metadata["path"]
        if target in present:
            continue
        if target not in records:
            errors.append(f"网页派生文件不可用: {target}")
            continue
        entries.append(derivative_entry(source_rel, records[target]))
        present.add(target)
        info["added_entries"].append(target)
    result["files"] = entries
    result["deployment"] = {
        "schema": "meaning-intelligence-deployment-manifest-v1",
        "kind": "cloudflare-pages",
        "max_file_bytes": MAX_FILE_BYTES,
        "complete_package_included": False,
        "web_derivatives": [item["path"] for item in DERIVATIVES.values()],
    }
    for entry in entries:
        rel = entry["path"]
        if rel not in records:
            errors.append(f"部署 manifest 指向未选择文件: {rel}")
        elif (entry.get("bytes"), entry.get("sha256")) != (records[rel]["bytes"], records[rel]["sha256"]):
            errors.append(f"部署 manifest 哈希或字节数不一致: {rel}")
    info["complete_paths"] = sorted(path for path in complete_paths if path)
    return result, info, errors


def rewrite_guide_content(text: str) -> str:
    for old, new in GUIDE_LINKS.items():
        text = text.replace(old, new)
    for description in GUIDE_1080_DESCRIPTIONS:
        text = text.replace(description, description.replace("1080p", "720p", 1))
    return text


def apply_guide_overrides(sources: dict[str, Path], records: dict[str, dict]) -> tuple[dict[str, bytes], list[dict]]:
    generated: dict[str, bytes] = {}
    changes: list[dict] = []
    for rel in ("project-guide/content.json", "project-guide/content.js"):
        if rel not in sources:
            continue
        original = sources[rel].read_text(encoding="utf-8")
        rewritten = rewrite_guide_content(original)
        if rewritten != original:
            data = rewritten.encode("utf-8")
            generated[rel] = data
            records[rel] = record_bytes(rel, data)
            changes.append({"path": rel, "reason": "guide release links redirected to compliant web derivatives"})
    manifest_rel = "project-guide/manifest.json"
    if manifest_rel not in sources:
        return generated, changes
    manifest_text = sources[manifest_rel].read_text(encoding="utf-8")
    if not generated and not any(old in manifest_text for old in GUIDE_LINKS):
        return generated, changes
    manifest = json.loads(manifest_text)
    for collection in ("copied_downloads", "files"):
        items = manifest.get(collection, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("path") not in GUIDE_LINKS:
                continue
            old = item["path"]
            new = GUIDE_LINKS[old]
            root_rel = guide_record_rel(new)
            record = records[root_rel]
            item["path"] = new
            item["bytes"] = record["bytes"]
            item["sha256"] = record["sha256"]
            if "source_sha256" in item:
                item["source_sha256"] = record["sha256"]
            if "source" in item:
                item["source"] = "意义智能有声读物_发布包\\" + root_rel.replace("/", "\\")
    for item in manifest.get("files", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        generated_rel = posixpath.normpath(posixpath.join("project-guide", item["path"]))
        if generated_rel.startswith("../") or generated_rel not in generated:
            continue
        item.update({"bytes": records[generated_rel]["bytes"], "sha256": records[generated_rel]["sha256"]})
    data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    generated[manifest_rel] = data
    records[manifest_rel] = record_bytes(manifest_rel, data)
    changes.append({"path": manifest_rel, "reason": "guide download metadata redirected to compliant web derivatives"})
    sums_rel = "project-guide/manifest.sha256"
    if sums_rel in sources:
        lines = []
        for line in sources[sums_rel].read_text(encoding="utf-8").splitlines():
            parts = line.split("  ", 1)
            if len(parts) != 2:
                lines.append(line)
                continue
            digest, rel = parts
            if rel in GUIDE_LINKS:
                rel = GUIDE_LINKS[rel]
                digest = records[guide_record_rel(rel)]["sha256"]
            elif posixpath.normpath(posixpath.join("project-guide", rel)) in generated:
                digest = records[posixpath.normpath(posixpath.join("project-guide", rel))]["sha256"]
            elif rel == "manifest.json":
                digest = records[manifest_rel]["sha256"]
            lines.append(f"{digest}  {rel}")
        data = ("\n".join(lines) + "\n").encode("utf-8")
        generated[sums_rel] = data
        records[sums_rel] = record_bytes(sums_rel, data)
        changes.append({"path": sums_rel, "reason": "guide checksum list updated for deployment metadata"})
    return generated, changes


def human_size(size: int) -> str:
    return f"{size / 1048576:.2f} MiB" if size >= 1048576 else f"{size / 1024:.1f} KiB"


def download_card(entry: dict) -> str:
    href = quote(entry["path"], safe="/")
    return (
        f'<article class="download"><div><span class="kind">{html.escape(str(entry.get("kind", "")))}</span>'
        f'<h3>{html.escape(str(entry.get("label_zh", "")))}</h3>'
        f'<p class="en">{html.escape(str(entry.get("label_en", "")))}</p>'
        f'<small>{human_size(int(entry["bytes"]))} · SHA-256 {entry["sha256"][:16]}…</small></div>'
        f'<a href="{href}" download>下载 / Download</a></article>'
    )


def local_reference(rel: str, ref: str) -> str | None:
    parsed = urlsplit(html.unescape(ref))
    if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("#"):
        return None
    target = unquote(parsed.path)
    if target == "/api/mcp":
        return None
    if target in ("", "/"):
        return "index.html"
    candidate = posixpath.normpath(target.lstrip("/") if target.startswith("/") else posixpath.join(posixpath.dirname(rel), target))
    if candidate == ".." or candidate.startswith("../"):
        raise ValueError(f"HTML 引用越出部署目录: {rel}: {ref}")
    return candidate


def deployment_downloads_html(source: str, manifest: dict, records: dict[str, dict], exclusions: list[dict], complete_paths: set[str]) -> tuple[str, list[str]]:
    entries = {entry["path"]: entry for entry in manifest["files"]}
    excluded = {item["path"]: item["reason"] for item in exclusions}
    replacement_targets = {metadata["path"] for metadata in DERIVATIVES.values()}
    card_paths: set[str] = set()
    errors: list[str] = []
    pattern = re.compile(r'<article\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bdownload\b)[^>]*>.*?</article>', re.I | re.S)

    def replace_card(match: re.Match) -> str:
        card = match.group(0)
        href = re.search(r'<a\b[^>]*\bhref\s*=\s*(["\'])(.*?)\1', card, re.I | re.S)
        if not href:
            return card
        try:
            target = local_reference("downloads.html", href.group(2))
        except ValueError as exc:
            errors.append(str(exc))
            return card
        if target is None:
            return card
        if target in complete_paths or is_complete_package(target):
            return ""
        if target in DERIVATIVES:
            target = DERIVATIVES[target]["path"]
        if target in entries:
            card_paths.add(target)
            return download_card(entries[target])
        if target in excluded:
            return ""
        return card

    rewritten = pattern.sub(replace_card, source)
    missing = [entry for entry in manifest["files"] if entry["path"] in replacement_targets and entry["path"] not in card_paths]
    if missing:
        cards = "".join(download_card(entry) for entry in missing)
        if re.search(r"<footer\b", rewritten, re.I):
            rewritten = re.sub(r"<footer\b", cards + "<footer", rewritten, count=1, flags=re.I)
        else:
            rewritten = rewritten.replace("</main>", cards + "</main>", 1)
    return rewritten, errors


def validate_html_references(records: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    for rel, record in sorted(records.items()):
        if PurePosixPath(rel).suffix.lower() not in {".html", ".htm"}:
            continue
        source = records[rel].get("_source")
        try:
            text = source.read_text(encoding="utf-8") if source else records[rel]["_data"].decode("utf-8")
        except Exception as exc:
            errors.append(f"HTML 读取失败 {rel}: {exc}")
            continue
        parser = ReferenceParser()
        parser.feed(text)
        for ref in parser.refs:
            try:
                target = local_reference(rel, ref)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if target is not None and target not in records:
                errors.append(f"{rel} 引用缺失或已排除: {ref} -> {target}")
    return errors


def retry_windows(operation, attempts: int = 12) -> None:
    for attempt in range(attempts):
        try:
            operation()
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.25)


def remove_tree(path: Path) -> bool:
    if not path.exists():
        return True
    for attempt in range(12):
        try:
            shutil.rmtree(path)
            return True
        except (PermissionError, OSError):
            if attempt == 11:
                return False
            time.sleep(0.25)
    return False


def atomic_replace_file(temp: Path, destination: Path) -> None:
    retry_windows(lambda: os.replace(temp, destination))


def atomic_replace_directory(temp: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.old-{uuid.uuid4().hex}")
    had_previous = destination.exists()
    if had_previous:
        retry_windows(lambda: os.replace(destination, backup))
    try:
        retry_windows(lambda: os.replace(temp, destination))
    except Exception:
        if had_previous and not destination.exists():
            retry_windows(lambda: os.replace(backup, destination))
        raise
    if had_previous:
        remove_tree(backup)


def verify_staging(staging: Path, records: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    actual = {path.relative_to(staging).as_posix(): path for path in staging.rglob("*") if path.is_file()}
    if set(actual) != set(records):
        errors.append(f"staging 文件集合不一致: missing={sorted(set(records)-set(actual))[:8]}, extra={sorted(set(actual)-set(records))[:8]}")
    for rel, expected in records.items():
        path = actual.get(rel)
        if not path:
            continue
        if path.stat().st_size != expected["bytes"] or sha256(path) != expected["sha256"]:
            errors.append(f"staging 字节数或 SHA-256 不一致: {rel}")
        if expected["bytes"] > MAX_FILE_BYTES:
            errors.append(f"staging 文件超过 25 MiB: {rel} ({expected['bytes']} bytes)")
    return errors


def compression_for(rel: str) -> int:
    return zipfile.ZIP_STORED if PurePosixPath(rel).suffix.lower() in {
        ".mp4", ".mp3", ".wav", ".m4a", ".jpg", ".jpeg", ".png", ".docx",
        ".pdf", ".pptx", ".epub", ".zip",
    } else zipfile.ZIP_DEFLATED


def write_zip(temp: Path, staging: Path, records: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for rel in sorted(records):
            archive.write(staging / rel, rel, compress_type=compression_for(rel))
    with zipfile.ZipFile(temp) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if "index.html" not in names:
            errors.append("部署 ZIP 根目录缺少 index.html")
        if len(names) != len(set(names)) or set(names) != set(records):
            errors.append("部署 ZIP 成员缺失、重复或多余")
        for info in infos:
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                errors.append(f"部署 ZIP 含不安全路径: {info.filename}")
            if info.file_size > MAX_FILE_BYTES:
                errors.append(f"部署 ZIP 成员超过 25 MiB: {info.filename}")
        bad = archive.testzip()
        if bad:
            errors.append(f"部署 ZIP CRC 失败: {bad}")
        for info in infos:
            expected = records.get(info.filename)
            if not expected:
                continue
            digest = hashlib.sha256()
            total = 0
            with archive.open(info) as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
                    total += len(chunk)
            if total != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
                errors.append(f"部署 ZIP 字节数或 SHA-256 不一致: {info.filename}")
    return errors


def validate_destinations(output: Path, staging: Path, report: Path) -> list[str]:
    errors: list[str] = []
    package = PACKAGE.resolve()
    for label, path in (("输出 ZIP", output), ("staging", staging), ("报告", report)):
        try:
            path.resolve().relative_to(package)
        except ValueError:
            pass
        else:
            errors.append(f"{label} 不能位于发布包目录内: {path}")
        if path.exists() and not (path.is_file() if label != "staging" else path.is_dir()):
            errors.append(f"{label} 路径类型不正确: {path}")
    if output.suffix.lower() != ".zip":
        errors.append("输出 ZIP 路径必须以 .zip 结尾")
    if len({output, staging, report}) != 3:
        errors.append("输出 ZIP、staging 和报告路径必须互不相同")
    for label, child, parent in (("输出 ZIP", output, staging), ("报告", report, staging)):
        try:
            child.resolve().relative_to(parent.resolve())
        except ValueError:
            pass
        else:
            errors.append(f"{label} 不能位于 {parent}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    output = args.output.resolve()
    staging = args.staging.resolve()
    report_path = args.report.resolve()
    report = {
        "schema": "meaning-intelligence-deployment-report-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "ok": False, "package": str(PACKAGE), "deployment_zip": str(output),
        "staging_directory": str(staging), "platform_file_limit_bytes": MAX_FILE_BYTES,
        "exclusions": [], "selected_files": [], "generated_files": [],
        "manifest_changes": {}, "errors": [],
    }
    work: Path | None = None
    zip_temp: Path | None = None
    exit_code = 1
    report_safe = not is_within(report_path, PACKAGE) and report_path not in {output, staging} and not is_within(report_path, staging)
    try:
        errors = validate_destinations(output, staging, report_path)
        if errors:
            raise RuntimeError("; ".join(errors))
        output.parent.mkdir(parents=True, exist_ok=True)
        staging.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        sources, exclusions, errors = collect_sources(output)
        report["exclusions"] = exclusions
        if errors:
            raise RuntimeError("; ".join(errors))
        records = {rel: record_file(rel, path) for rel, path in sources.items()}
        for rel, path in sources.items():
            records[rel]["_source"] = path
        guide_audio_changes = prepare_guide_audio(records)
        generated, guide_changes = apply_guide_overrides(sources, records)
        for rel, data in generated.items():
            records[rel]["_data"] = data
        report["generated_files"] = guide_audio_changes + guide_changes
        source_manifest = json.loads(sources["download/manifest.json"].read_text(encoding="utf-8"))
        manifest, manifest_info, errors = deployment_manifest(source_manifest, records, sources, exclusions)
        report["manifest_changes"] = manifest_info
        if errors:
            raise RuntimeError("; ".join(errors))
        manifest_data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        generated["download/manifest.json"] = manifest_data
        records["download/manifest.json"] = record_bytes("download/manifest.json", manifest_data)
        records["download/manifest.json"]["_data"] = manifest_data
        downloads_rel = "downloads.html"
        downloads_data, errors = deployment_downloads_html(
            sources[downloads_rel].read_text(encoding="utf-8"), manifest, records,
            exclusions, set(manifest_info.get("complete_paths", [])),
        )
        if errors:
            raise RuntimeError("; ".join(errors))
        downloads_bytes = downloads_data.encode("utf-8")
        generated[downloads_rel] = downloads_bytes
        records[downloads_rel] = record_bytes(downloads_rel, downloads_bytes)
        records[downloads_rel]["_data"] = downloads_bytes
        for entry in manifest["files"]:
            rel = entry["path"]
            if rel in generated and rel != "download/manifest.json":
                entry.update({"bytes": records[rel]["bytes"], "sha256": records[rel]["sha256"]})
        manifest_data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        generated["download/manifest.json"] = manifest_data
        records["download/manifest.json"] = record_bytes("download/manifest.json", manifest_data)
        records["download/manifest.json"]["_data"] = manifest_data
        report["generated_files"].extend([
            {"path": "download/manifest.json", "reason": "deployment-specific download manifest"},
            {"path": downloads_rel, "reason": "deployment-specific download page without complete-package card"},
        ])
        errors = validate_html_references(records)
        oversized = [record for record in records.values() if record["bytes"] > MAX_FILE_BYTES]
        if oversized:
            errors.extend(f"部署文件超过 25 MiB: {item['path']} ({item['bytes']} bytes)" for item in oversized)
        if errors:
            raise RuntimeError("; ".join(errors))
        public_records = {rel: {key: value for key, value in record.items() if not key.startswith("_")} for rel, record in records.items()}
        report["selected_files"] = [public_records[rel] for rel in sorted(public_records)]
        maximum = max(public_records.values(), key=lambda item: item["bytes"])
        report["max_file"] = maximum
        report["totals"] = {"files": len(public_records), "bytes": sum(item["bytes"] for item in public_records.values())}
        work = Path(tempfile.mkdtemp(prefix=f".{staging.name}.tmp-", dir=staging.parent))
        for rel, record in records.items():
            destination = work / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            if rel in generated:
                destination.write_bytes(generated[rel])
            elif "_data" in record:
                destination.write_bytes(record["_data"])
            else:
                shutil.copy2(sources[rel], destination)
        errors = verify_staging(work, public_records)
        if errors:
            raise RuntimeError("; ".join(errors))
        handle, temp_name = tempfile.mkstemp(prefix=f".{output.stem}.tmp-", suffix=".zip", dir=output.parent)
        os.close(handle)
        zip_temp = Path(temp_name)
        errors = write_zip(zip_temp, work, public_records)
        if errors:
            raise RuntimeError("; ".join(errors))
        atomic_replace_directory(work, staging)
        work = None
        atomic_replace_file(zip_temp, output)
        zip_temp = None
        report["zip_bytes"] = output.stat().st_size
        report["zip_sha256"] = sha256(output)
        report["ok"] = True
        print(f"PASS {len(public_records)} 个部署文件，{report['totals']['bytes'] / 1048576:.1f} MiB")
        print(f"PASS 最大单文件 {maximum['path']} ({maximum['bytes'] / 1048576:.2f} MiB)")
        print(f"PASS ZIP 根目录含 index.html: {output}")
        print(f"PASS staging: {staging}")
        print(f"PASS report: {report_path}")
        exit_code = 0
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        print(f"FAIL {exc}")
        exit_code = 1
    finally:
        if work is not None:
            remove_tree(work)
        if zip_temp is not None:
            try:
                zip_temp.unlink(missing_ok=True)
            except OSError:
                pass
        if not report_safe:
            print("FAIL 报告路径不安全，未写入报告以保护发布包或输出文件")
            exit_code = 1
        else:
            try:
                report_path.parent.mkdir(parents=True, exist_ok=True)
                handle, temp_name = tempfile.mkstemp(prefix=f".{report_path.stem}.tmp-", suffix=".json", dir=report_path.parent)
                os.close(handle)
                temp_report = Path(temp_name)
                try:
                    temp_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    atomic_replace_file(temp_report, report_path)
                finally:
                    temp_report.unlink(missing_ok=True)
            except Exception as exc:
                print(f"FAIL 部署报告写入失败: {exc}")
                exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
