#!/usr/bin/env python3
"""Validate the complete Meaning Intelligence publication package and optional deployment ZIP."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")

WORKSPACE = Path(__file__).resolve().parents[2]
PACKAGE = WORKSPACE / "意义智能有声读物_发布包"
REPO = WORKSPACE / "mi-repo"
DEPLOY_STAGING = WORKSPACE / "deliverables" / "meaning-intelligence-deploy-staging"
REQUIRED = [
    "index.html", "listen.html", "downloads.html", "mcp.html",
    "project-guide/index.html", "project-guide/content.js", "project-guide/verification.js",
    "project-guide/manifest.json", "project-guide/verification.json", "project-guide/browser-check.json",
    "project-guide/downloads/project-guide-bilingual.pdf", "project-guide/downloads/project-guide-bilingual.docx",
    "project-guide/downloads/guide-narration-zh.mp3", "project-guide/downloads/guide-narration-en.mp3",
    "functions/api/mcp.js",
    "subtitles.json", "subtitles.vtt", "subtitles_en.json", "timeline_en.json",
    "assets/audio.mp3", "assets/audio-web.mp3", "assets/cover.jpg", "assets/qr_site.png",
    "assets/video/MeaningIntelligenceScene.mp4",
    "assets/video/release/meaning_intelligence_zh.mp4",
    "assets/video/release/meaning_intelligence_en.mp4",
    "assets/video/release/meaning_intelligence_zh-web.mp4",
    "assets/video/release/meaning_intelligence_en-web.mp4",
    "publication-browser-check.json", "web-media-verification.json",
    "assets_en/audio_en.mp3",
    "download/意义智能_讲课展示.pptx", "download/MSI演进视频讲解版.pptx",
    "download/Meaning_Intelligence_White_Paper_v1.1_DOCX.docx",
    "download/Meaning_Intelligence_White_Paper_v1.1_PDF.pdf",
    "download/Meaning_Intelligence_Source_v0.2.0.zip",
    "download/意义智能_完整交付包.zip", "download/verification.json",
    "download/video/meaning_intelligence_zh.srt", "download/video/meaning_intelligence_zh.vtt",
    "download/video/meaning_intelligence_en.srt", "download/video/meaning_intelligence_en.vtt",
    "download/video/narration_zh.txt", "download/video/narration_en.txt",
    "download/video/cover.jpg", "download/video/build/verification.json",
    "download/documents/意义智能_附件衍生更新版_2026-11-26.docx",
    "download/documents/意义智能_附件衍生更新版_2026-11-26.pdf",
    "download/documents/意义智能_书稿勘误与补充说明_2026-11-26.docx",
    "download/documents/意义智能_书稿勘误与补充说明_2026-11-26.pdf",
    "download/documents/意义智能_项目审查与优化报告_2026-11-26.docx",
    "download/documents/意义智能_项目审查与优化报告_2026-11-26.pdf",
    "download/documents/意义智能_项目审查与优化报告_2026-11-26.md",
    "download/documents/意义智能_有声读物_发布指南与操作手册_v3.0.docx",
    "download/documents/意义智能_有声读物_发布指南与操作手册_v3.0.pdf",
    "download/documents/意义智能有声读物_发布指南与操作手册.md",
    "download/manifest.json",
]
JSON_FILES = [
    "subtitles.json", "subtitles_en.json", "timeline_en.json",
    "download/manifest.json", "download/verification.json",
    "publication-browser-check.json", "web-media-verification.json",
    "project-guide/manifest.json", "project-guide/verification.json", "project-guide/browser-check.json",
    "download/video/chapter_manifest.json", "download/video/build/verification.json",
]
MEDIA_SUFFIXES = {".mp3", ".mp4", ".wav", ".m4a"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_files() -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in PACKAGE.rglob("*"):
        name = path.name.lower()
        if ".uploading" in name or ".downloading" in name or path.suffix.lower() in {".tmp", ".part", ".crdownload"}:
            continue
        try:
            if path.is_file():
                path.stat().st_size
                files[path.relative_to(PACKAGE).as_posix()] = path
        except OSError:
            continue
    return files


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: list[str] = []
        self.refs: list[tuple[str, str, str]] = []
        self.scripts: list[str] = []
        self._script_depth = 0
        self._script_type = ""
        self._script_src = ""
        self._chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"])
        for key in ("src", "href", "poster"):
            value = values.get(key)
            if value:
                self.refs.append((tag, key, value))
        if tag == "script":
            self._script_depth += 1
            self._script_type = values.get("type", "").lower()
            self._script_src = values.get("src", "")
            self._chunks = []

    def handle_data(self, data):
        if self._script_depth:
            self._chunks.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._script_depth:
            self._script_depth -= 1
            if not self._script_src and self._script_type not in ("application/json", "application/ld+json"):
                self.scripts.append("".join(self._chunks))


def safe_member(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def inspect_html(files: dict[str, Path], errors: list[str]) -> None:
    root = PACKAGE.resolve()
    for rel, path in sorted(files.items()):
        if path.suffix.lower() not in (".html", ".htm"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            errors.append(f"HTML 读取失败 {rel}: {exc}")
            continue
        parser = PageParser()
        try:
            parser.feed(text)
        except Exception as exc:
            errors.append(f"HTML 解析失败 {rel}: {exc}")
        duplicates = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
        if duplicates:
            errors.append(f"{rel} 重复 ID: {duplicates}")
        if "__DATA__" in text or "__CUES__" in text:
            errors.append(f"{rel} 含未替换构建占位符")
        for tag, attr, ref in parser.refs:
            parsed = urlsplit(ref)
            if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("#"):
                continue
            target = unquote(parsed.path)
            candidate = (root / target.lstrip("/")) if target.startswith("/") else (path.parent / target)
            if not safe_member(candidate, root):
                errors.append(f"{rel} 引用越出发布包: {ref}")
            elif not candidate.is_file():
                errors.append(f"{rel} 引用缺失: {ref}")
        if rel in ("index.html", "listen.html", "downloads.html", "mcp.html", "project-guide/index.html"):
            language_controls = ("btnEn", "setLang", "setL(", "lang-en", "data-i18n")
            if not any(control in text for control in language_controls):
                errors.append(f"{rel} 缺少可见语言切换")
        if shutil.which("node"):
            for index, script in enumerate(parser.scripts, 1):
                if not script.strip():
                    continue
                with tempfile.TemporaryDirectory() as temp:
                    script_path = Path(temp) / f"inline-{index}.mjs"
                    script_path.write_text(script, encoding="utf-8")
                    result = subprocess.run(["node", "--check", str(script_path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
                    if result.returncode:
                        message = (result.stderr or result.stdout).strip().splitlines()[-1]
                        errors.append(f"{rel} 内联脚本 {index} 语法失败: {message}")
        elif parser.scripts:
            errors.append("Node.js 不可用，无法验证内联脚本语法")


def inspect_subtitles(files: dict[str, Path], errors: list[str]) -> None:
    for rel in ("subtitles.json", "subtitles_en.json"):
        path = files.get(rel)
        if not path:
            continue
        try:
            cues = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(cues, list) or not cues:
                errors.append(f"{rel} 不是非空字幕数组")
                continue
            previous_end = -1.0
            for index, cue in enumerate(cues):
                start, end = float(cue["s"]), float(cue["e"])
                if start < 0 or end <= start or start < previous_end - 0.05:
                    errors.append(f"{rel} 字幕 {index + 1} 时间轴无效或重叠")
                    break
                if not str(cue.get("t", "")).strip():
                    errors.append(f"{rel} 字幕 {index + 1} 文本为空")
                    break
                previous_end = end
        except Exception as exc:
            errors.append(f"{rel} 字幕结构失败: {exc}")
    for rel in sorted(files):
        if not rel.lower().endswith((".srt", ".vtt")):
            continue
        try:
            text = files[rel].read_text(encoding="utf-8")
            if rel.lower().endswith(".vtt") and not text.startswith("WEBVTT"):
                errors.append(f"{rel} 缺少 WEBVTT 头")
            times = re.findall(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", text)
            if not times:
                errors.append(f"{rel} 无可解析时间轴")
            for values in times:
                start = int(values[0]) * 3600 + int(values[1]) * 60 + int(values[2]) + int(values[3]) / 1000
                end = int(values[4]) * 3600 + int(values[5]) * 60 + int(values[6]) + int(values[7]) / 1000
                if end <= start:
                    errors.append(f"{rel} 含倒序或零长时间轴")
                    break
        except Exception as exc:
            errors.append(f"{rel} 字幕文件读取失败: {exc}")


def inspect_epub(path: Path, errors: list[str]) -> None:
    rel = path.relative_to(PACKAGE).as_posix()
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "mimetype" not in names:
                errors.append(f"{rel} 缺少 mimetype")
                return
            info = archive.getinfo("mimetype")
            if info.compress_type != zipfile.ZIP_STORED or archive.read("mimetype") != b"application/epub+zip":
                errors.append(f"{rel} mimetype 必须未压缩且内容正确")
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
            rootfile = container.find(".//c:rootfile", ns)
            if rootfile is None:
                errors.append(f"{rel} container 缺少 rootfile")
                return
            opf_path = rootfile.attrib["full-path"]
            if opf_path not in names:
                errors.append(f"{rel} OPF 不存在: {opf_path}")
                return
            opf = ET.fromstring(archive.read(opf_path))
            opf_ns = {"o": "http://www.idpf.org/2007/opf"}
            manifest = {item.attrib["id"]: item.attrib["href"] for item in opf.findall(".//o:manifest/o:item", opf_ns)}
            if not manifest:
                errors.append(f"{rel} OPF manifest 为空")
            base = PurePosixPath(opf_path).parent
            for href in manifest.values():
                target = (base / href).as_posix()
                if target not in names:
                    errors.append(f"{rel} manifest 引用缺失: {target}")
            spine = opf.findall(".//o:spine/o:itemref", opf_ns)
            if not spine:
                errors.append(f"{rel} OPF spine 为空")
            for item in spine:
                if item.attrib.get("idref") not in manifest:
                    errors.append(f"{rel} spine idref 不存在: {item.attrib.get('idref')}")
            xhtml_count = 0
            for href in manifest.values():
                if not href.lower().endswith((".xhtml", ".html")):
                    continue
                xhtml_count += 1
                target = (base / href).as_posix()
                try:
                    document = ET.fromstring(archive.read(target))
                    ids = {node.attrib["id"] for node in document.iter() if "id" in node.attrib}
                    for node in document.iter():
                        for key, value in node.attrib.items():
                            if key.endswith("href") and value.startswith("#") and value[1:] not in ids:
                                errors.append(f"{rel} {target} 锚点缺失: {value}")
                                break
                except Exception as exc:
                    errors.append(f"{rel} XHTML 解析失败 {target}: {exc}")
            if xhtml_count < 2:
                errors.append(f"{rel} XHTML 内容过少")
    except Exception as exc:
        errors.append(f"{rel} EPUB 解析失败: {exc}")


def inspect_office(files: dict[str, Path], errors: list[str]) -> None:
    for rel, path in sorted(files.items()):
        suffix = path.suffix.lower()
        if suffix not in (".docx", ".pptx"):
            continue
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                required = "word/document.xml" if suffix == ".docx" else "ppt/presentation.xml"
                if required not in names:
                    errors.append(f"{rel} 缺少 {required}")
                if suffix == ".docx":
                    root = ET.fromstring(archive.read(required))
                    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                    if not root.findall(".//w:p", ns):
                        errors.append(f"{rel} 无正文段落")
        except Exception as exc:
            errors.append(f"{rel} Office 结构失败: {exc}")
    for rel, path in sorted(files.items()):
        if path.suffix.lower() != ".pdf":
            continue
        try:
            data = path.read_bytes()
            if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]:
                errors.append(f"{rel} PDF 文件头或 EOF 无效")
        except Exception as exc:
            errors.append(f"{rel} PDF 读取失败: {exc}")


def inspect_manifest(files: dict[str, Path], errors: list[str]) -> dict:
    path = files.get("download/manifest.json")
    if not path:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("files")
        if not isinstance(entries, list) or not entries:
            errors.append("download/manifest.json files 为空")
            return data
        seen = set()
        categories = set()
        by_path = {}
        root = PACKAGE.resolve()
        allowed_languages = {"zh", "en", "bilingual", "und"}
        allowed_categories = {"package", "audio", "video", "subtitles", "narration", "cover", "ebook", "document", "presentation", "source", "guide", "verification"}
        for entry in entries:
            rel = entry.get("path", "")
            pure = PurePosixPath(rel)
            if not rel or pure.is_absolute() or ".." in pure.parts or "\\" in rel:
                errors.append(f"manifest 不安全路径: {rel}")
                continue
            if rel in seen:
                errors.append(f"manifest 重复路径: {rel}")
            seen.add(rel)
            by_path[rel] = entry
            category = entry.get("category")
            categories.add(category)
            if category not in allowed_categories:
                errors.append(f"manifest 类别无效: {rel}: {category}")
            if entry.get("language") not in allowed_languages:
                errors.append(f"manifest 语言标签无效: {rel}: {entry.get('language')}")
            if "meaning_intelligence_launch" in rel:
                errors.append(f"manifest 仍含旧发布视频: {rel}")
            target = PACKAGE / rel
            if not safe_member(target, root) or not target.is_file():
                errors.append(f"manifest 文件不存在: {rel}")
                continue
            if target.stat().st_size != entry.get("bytes"):
                errors.append(f"manifest 字节数不一致: {rel}")
            if sha256(target) != entry.get("sha256"):
                errors.append(f"manifest SHA-256 不一致: {rel}")
        for category in ("package", "audio", "video", "subtitles", "narration", "cover", "ebook", "document", "presentation", "source", "guide", "verification"):
            if category not in categories:
                errors.append(f"manifest 缺少类别: {category}")
        required_paths = {
            "download/意义智能_完整交付包.zip": ("package", "bilingual"),
            "download/Meaning_Intelligence_Source_v0.2.0.zip": ("source", "bilingual"),
            "assets/video/release/meaning_intelligence_zh.mp4": ("video", "zh"),
            "assets/video/release/meaning_intelligence_en.mp4": ("video", "en"),
            "assets/video/release/meaning_intelligence_zh-web.mp4": ("video", "zh"),
            "assets/video/release/meaning_intelligence_en-web.mp4": ("video", "en"),
            "assets/audio-web.mp3": ("audio", "zh"),
            "publication-browser-check.json": ("verification", "und"),
            "web-media-verification.json": ("verification", "und"),
            "download/video/meaning_intelligence_zh.srt": ("subtitles", "zh"),
            "download/video/meaning_intelligence_zh.vtt": ("subtitles", "zh"),
            "download/video/meaning_intelligence_en.srt": ("subtitles", "en"),
            "download/video/meaning_intelligence_en.vtt": ("subtitles", "en"),
            "download/video/narration_zh.txt": ("narration", "zh"),
            "download/video/narration_en.txt": ("narration", "en"),
            "download/video/cover.jpg": ("cover", "bilingual"),
            "download/video/build/verification.json": ("verification", "und"),
            "download/verification.json": ("verification", "und"),
            "project-guide/index.html": ("guide", "bilingual"),
            "project-guide/downloads/project-guide-bilingual.pdf": ("guide", "bilingual"),
            "project-guide/downloads/project-guide-bilingual.docx": ("guide", "bilingual"),
            "project-guide/downloads/guide-narration-zh.mp3": ("audio", "zh"),
            "project-guide/downloads/guide-narration-en.mp3": ("audio", "en"),
        }
        for rel, (category, language) in required_paths.items():
            entry = by_path.get(rel)
            if not entry:
                errors.append(f"manifest 缺少必需资源: {rel}")
            elif entry.get("category") != category or entry.get("language") != language:
                errors.append(f"manifest 类别或语言标签不实: {rel}")
        for rel in ("assets/video/release/meaning_intelligence_zh.mp4", "assets/video/release/meaning_intelligence_en.mp4"):
            entry = by_path.get(rel, {})
            if "bilingual" in (entry.get("label_zh", "") + entry.get("label_en", "")).lower():
                errors.append(f"manifest 错误地将单语发布视频标为双语: {rel}")
        suffixes = {PurePosixPath(entry.get("path", "")).suffix.lower() for entry in entries}
        for suffix in (".epub", ".docx", ".pdf", ".pptx", ".srt", ".vtt", ".mp4", ".zip"):
            if suffix not in suffixes:
                errors.append(f"manifest 缺少 {suffix} 交付物")
        for suffix, label in (("docx", "DOCX"), ("pdf", "PDF")):
            rel = f"download/Meaning_Intelligence_White_Paper_v1.1_{label}.{suffix}"
            sources = sorted((REPO / "whitepaper" / "dist").glob(f"*_v1.1_*.{suffix}"))
            if len(sources) != 1:
                errors.append(f"白皮书权威源不唯一: {suffix}")
            elif rel in by_path and sha256(sources[0]) != by_path[rel].get("sha256"):
                errors.append(f"白皮书与权威源 SHA-256 不一致: {rel}")
        return data
    except Exception as exc:
        errors.append(f"manifest 解析失败: {exc}")
        return {}


def inspect_verification_reports(files: dict[str, Path], errors: list[str]) -> None:
    browser_path = files.get("publication-browser-check.json")
    if browser_path:
        try:
            browser = json.loads(browser_path.read_text(encoding="utf-8"))
            if not browser.get("ok") or browser.get("checks_passed") != browser.get("checks_total") or browser.get("checks_total", 0) < 21:
                errors.append("发布页真实浏览器检查未通过或覆盖不足")
        except Exception as exc:
            errors.append(f"发布页浏览器报告解析失败: {exc}")
    media_path = files.get("web-media-verification.json")
    if media_path:
        try:
            media = json.loads(media_path.read_text(encoding="utf-8"))
            records = media.get("records", [])
            if not media.get("ok") or media.get("masters_modified") is not False or len(records) != 3:
                errors.append("流媒体派生验证报告状态无效")
            normalized_paths = {record.get("path", "").replace("\\", "/") for record in records}
            if normalized_paths != {
                "意义智能有声读物_发布包/assets/audio-web.mp3",
                "意义智能有声读物_发布包/assets/video/release/meaning_intelligence_zh-web.mp4",
                "意义智能有声读物_发布包/assets/video/release/meaning_intelligence_en-web.mp4",
            }:
                errors.append("流媒体派生验证报告资源集合不完整")
            for record in records:
                workspace_rel = record.get("path", "").replace("\\", "/")
                source_path = WORKSPACE / workspace_rel
                try:
                    rel = source_path.resolve().relative_to(PACKAGE.resolve()).as_posix()
                except ValueError:
                    errors.append(f"流媒体派生路径越出发布包: {workspace_rel}")
                    continue
                target = files.get(rel)
                if not target:
                    errors.append(f"流媒体派生文件缺失: {rel}")
                    continue
                if target.stat().st_size != record.get("bytes") or sha256(target) != record.get("sha256"):
                    errors.append(f"流媒体派生文件哈希或字节数不一致: {rel}")
                if target.stat().st_size >= media.get("platform_file_limit_bytes", 25 * 1024 * 1024):
                    errors.append(f"流媒体派生文件超过 25 MiB: {rel}")
                master = WORKSPACE / record.get("source", "").replace("\\", "/")
                if not master.is_file() or sha256(master) != record.get("source_sha256"):
                    errors.append(f"流媒体派生母版哈希不一致: {record.get('source')}")
        except Exception as exc:
            errors.append(f"流媒体验证报告解析失败: {exc}")


def probe_media(path: Path) -> dict:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,sample_rate,channels:stream_tags=language,title:stream_disposition=default",
        "-of", "json", str(path),
    ], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return json.loads(result.stdout)


def inspect_media(files: dict[str, Path], errors: list[str]) -> None:
    if not shutil.which("ffprobe"):
        errors.append("ffprobe 不可用，无法验证媒体")
        return
    for rel, path in sorted(files.items()):
        if path.suffix.lower() not in MEDIA_SUFFIXES:
            continue
        try:
            info = probe_media(path)
            duration = float(info.get("format", {}).get("duration", 0))
            streams = info.get("streams", [])
            audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
            video = [stream for stream in streams if stream.get("codec_type") == "video"]
            subtitles = [stream for stream in streams if stream.get("codec_type") == "subtitle"]
            silent_animation = "MeaningIntelligenceScene" in rel
            research_render = rel == "project-guide/downloads/msi-eight-acts-43s.mp4"
            if duration <= 0:
                errors.append(f"{rel} 媒体时长无效")
            if not audio and not (silent_animation or research_render):
                errors.append(f"{rel} 缺少音频流")
            if research_render:
                if abs(duration - 43.433333) > 0.01:
                    errors.append(f"{rel} 研究仓库渲染时长不一致: {duration:.3f}")
                if not video or video[0].get("width") != 1920 or video[0].get("height") != 1080:
                    errors.append(f"{rel} 研究仓库渲染分辨率不是 1920×1080")
                rate = video[0].get("avg_frame_rate", "0/1").split("/")
                if len(rate) != 2 or not rate[1] or abs(float(rate[0]) / float(rate[1]) - 60) > 0.01:
                    errors.append(f"{rel} 研究仓库渲染不是 60 fps")
            if path.suffix.lower() == ".mp4" and not video:
                errors.append(f"{rel} 缺少视频流")
            release = rel.startswith("assets/video/release/meaning_intelligence_")
            web_release = rel.endswith("-web.mp4")
            if release:
                if duration <= 120:
                    errors.append(f"{rel} 发布视频未超过 120 秒: {duration:.3f}")
                subtitle_languages = {stream.get("tags", {}).get("language") for stream in subtitles}
                if not {"zho", "eng"} <= subtitle_languages:
                    errors.append(f"{rel} 缺少中英内嵌字幕: {sorted(subtitle_languages)}")
            if web_release:
                if path.stat().st_size >= 25 * 1024 * 1024:
                    errors.append(f"{rel} 在线视频超过 Cloudflare 25 MiB 限制")
                if not video or video[0].get("width") != 1280 or video[0].get("height") != 720:
                    errors.append(f"{rel} 在线视频不是 1280×720")
            if rel == "assets/audio-web.mp3" and path.stat().st_size >= 25 * 1024 * 1024:
                errors.append(f"{rel} 在线音频超过 Cloudflare 25 MiB 限制")
            if "MeaningIntelligenceScene" in rel and duration <= 5:
                errors.append(f"{rel} MSI 视频异常过短: {duration:.3f}")
            if path.suffix.lower() == ".mp3" and duration <= 60:
                errors.append(f"{rel} 有声读物异常过短: {duration:.3f}")
            if rel.endswith(".mp3") or release:
                volume = subprocess.run([
                    "ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-",
                ], capture_output=True, text=True, encoding="utf-8", errors="replace")
                match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", volume.stderr)
                if not match or float(match.group(1)) < -55:
                    errors.append(f"{rel} 音频静音或峰值异常")
        except Exception as exc:
            errors.append(f"{rel} 媒体探测失败: {exc}")


def inspect_source_zip(path: Path, errors: list[str]) -> None:
    rel = path.relative_to(PACKAGE).as_posix()
    try:
        with zipfile.ZipFile(path) as archive:
            names = {name for name in archive.namelist() if not name.endswith("/")}
            if archive.testzip():
                errors.append(f"{rel} CRC 校验失败")
            excluded_parts = {".git", "__pycache__", ".pytest_cache", "node_modules", ".wrangler", ".lingxi", ".qoder"}
            excluded_names = {".env", ".npmrc", ".netrc", "credentials.json", "token.txt", "tokens.json", "secrets.json"}
            for name in names:
                pure = PurePosixPath(name)
                if pure.is_absolute() or ".." in pure.parts or "\\" in name:
                    errors.append(f"{rel} 含不安全成员: {name}")
                if any(part.lower() in excluded_parts for part in pure.parts) or pure.name.lower() in excluded_names or ".uploading" in pure.name.lower() or ".downloading" in pure.name.lower() or pure.suffix.lower() in {".pyc", ".pyo", ".pem", ".key"}:
                    errors.append(f"{rel} 含缓存或敏感文件: {name}")
                if "meaning_intelligence_launch" in name:
                    errors.append(f"{rel} 含旧发布视频: {name}")
            if path.name in {PurePosixPath(name).name for name in names}:
                errors.append(f"{rel} 错误地包含自身")
            root = "meaning-intelligence/"
            required = (
                root + "meaning-agent/README.md", root + "web-mcp/package.json",
                root + "web-mcp/functions/api/mcp.js",
                root + "scripts/build_downloads.py", root + "scripts/build_documents.py",
                root + "documents/document-manifest.json", root + "scripts/verify_package.py",
                root + "scripts/prepare_web_media.py", root + "scripts/browser_verify.mjs",
                root + "scripts/build_deploy_zip.py", root + "scripts/verify_site.py",
                root + "scripts/finalize_publish.py", root + "scripts/build_publish.py",
                root + "video/build_video.py", root + "guide/content.json",
                root + "guide/build.py", root + "guide/build_audio.py", root + "guide/verify.py",
                root + "guide/template.html", root + "guide/app.js",
                root + "skills/meaning-intelligence-maintain/SKILL.md",
                root + "skills/meaning-intelligence-publish/SKILL.md",
                root + "repository/pr_sdk_v2/meaning_intelligence/falsify.py",
                root + "repository/pr_sdk_v2/test_pr.py",
                root + "repository/msi/build.py",
                root + "repository/msi/config.json",
                root + "repository/whitepaper/build_whitepaper.py",
                root + "repository/whitepaper/make_figures.py",
                root + "repository/tools/verify_final.py",
                root + "repository/audit/index.html",
                root + "repository/check-token.bat",
                root + "repository/.github/workflows/ci.yml",
            )
            for name in required:
                if name not in names:
                    errors.append(f"{rel} 缺少成员: {name}")
            function_name = root + "web-mcp/functions/api/mcp.js"
            if function_name in names and b"export const onRequest" not in archive.read(function_name):
                errors.append(f"{rel} Web MCP 缺少 Pages Function onRequest 适配器")
            skills = [name for name in names if re.fullmatch(r"meaning-intelligence/meaning-agent/skills/[^/]+/SKILL\.md", name)]
            tests = [name for name in names if name.startswith(root + "meaning-agent/tests/") and name.endswith(".py")]
            if len(skills) != 6:
                errors.append(f"{rel} 六技能文档数量错误: {len(skills)}")
            if not tests:
                errors.append(f"{rel} 缺少 meaning-agent 测试")
            if not any(name.startswith(root + "documents/") and name.endswith(".docx") for name in names):
                errors.append(f"{rel} 缺少最终 DOCX")
            if not any(name.startswith(root + "documents/") and name.endswith(".pdf") for name in names):
                errors.append(f"{rel} 缺少最终 PDF")
            if not any(name.startswith(root + "documents/whitepaper/") and name.endswith(".pdf") for name in names):
                errors.append(f"{rel} 缺少白皮书 PDF")
    except Exception as exc:
        errors.append(f"{rel} 源代码 ZIP 解析失败: {exc}")


def inspect_complete_zip(files: dict[str, Path], errors: list[str]) -> None:
    candidates = [path for rel, path in files.items() if rel.startswith("download/") and path.suffix.lower() == ".zip" and "完整交付包" in rel]
    if not candidates:
        errors.append("缺少完整交付 ZIP")
        return
    for path in candidates:
        rel = path.relative_to(PACKAGE).as_posix()
        try:
            with zipfile.ZipFile(path) as archive:
                names = {name for name in archive.namelist() if not name.endswith("/")}
                if archive.testzip():
                    errors.append(f"{rel} CRC 校验失败")
                guide_ready = False
                if "verification.json" in names:
                    verification = json.loads(archive.read("verification.json"))
                    guide_ready = bool(verification.get("project_guide", {}).get("ready"))
                else:
                    errors.append(f"{rel} 缺少 verification.json")
                if not guide_ready:
                    errors.append(f"{rel} 项目说明书未标记为完整交付")
                excluded_parts = {".git", "__pycache__", ".pytest_cache", "node_modules", ".wrangler", ".lingxi", ".qoder"}
                excluded_names = {".env", ".npmrc", ".netrc", "credentials.json", "token.txt", "tokens.json", "secrets.json"}
                for name in names:
                    pure = PurePosixPath(name)
                    if pure.is_absolute() or ".." in pure.parts or "\\" in name:
                        errors.append(f"{rel} 含不安全成员: {name}")
                    if any(part.lower() in excluded_parts for part in pure.parts) or pure.name.lower() in excluded_names or ".uploading" in pure.name.lower() or ".downloading" in pure.name.lower() or pure.suffix.lower() in {".pyc", ".pyo", ".pem", ".key"}:
                        errors.append(f"{rel} 含缓存或敏感文件: {name}")
                    if "meaning_intelligence_launch" in name:
                        errors.append(f"{rel} 含旧发布视频: {name}")
                required_fragments = ("documents/", "video/", "meaning-agent/", "web-mcp/", "scripts/", "guide/", "skills/", "download/", "manifest", "verification")
                if guide_ready:
                    required_fragments += ("project-guide/",)
                for fragment in required_fragments:
                    if not any(fragment in name for name in names):
                        errors.append(f"{rel} 缺少成员类别: {fragment}")
                for name in (
                    "index.html", "downloads.html", "manifest.json", "verification.json",
                    "video/build_video.py", "video/meaning_intelligence_zh.mp4", "video/meaning_intelligence_en.mp4",
                    "skills/meaning-intelligence-maintain/SKILL.md", "skills/meaning-intelligence-publish/SKILL.md",
                    "documents/意义智能_附件衍生更新版_2026-11-26.pdf",
                    "documents/意义智能_书稿勘误与补充说明_2026-11-26.pdf",
                    "documents/意义智能_项目审查与优化报告_2026-11-26.pdf",
                    "documents/意义智能_有声读物_发布指南与操作手册_v3.0.pdf",
                    "documents/意义智能有声读物_发布指南与操作手册.md",
                ):
                    if name not in names:
                        errors.append(f"{rel} 缺少成员: {name}")
                if path.name in {PurePosixPath(name).name for name in names}:
                    errors.append(f"{rel} 错误地包含自身")
                if "manifest.json" in names:
                    manifest = json.loads(archive.read("manifest.json"))
                    for entry in manifest.get("files", []):
                        name = entry.get("path", "")
                        if name not in names:
                            errors.append(f"{rel} 内部 manifest 资源缺失: {name}")
                        elif archive.getinfo(name).file_size != entry.get("bytes"):
                            errors.append(f"{rel} 内部 manifest 字节数不一致: {name}")
        except Exception as exc:
            errors.append(f"{rel} 完整 ZIP 解析失败: {exc}")


def deployment_files(errors: list[str]) -> dict[str, Path]:
    if not DEPLOY_STAGING.is_dir():
        errors.append(f"部署暂存目录不存在: {DEPLOY_STAGING}")
        return {}
    files: dict[str, Path] = {}
    for path in DEPLOY_STAGING.rglob("*"):
        name = path.name.lower()
        if ".uploading" in name or ".downloading" in name or path.suffix.lower() in {".tmp", ".part", ".crdownload"}:
            continue
        try:
            if path.is_file():
                if path.stat().st_size >= 25 * 1024 * 1024:
                    errors.append(f"部署暂存文件超过 25 MiB: {path.relative_to(DEPLOY_STAGING)}")
                files[path.relative_to(DEPLOY_STAGING).as_posix()] = path
        except OSError as exc:
            errors.append(f"部署暂存文件不可读取: {path}: {exc}")
    return files


def inspect_zip(zip_path: Path, expected: dict[str, Path], errors: list[str]) -> None:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = {name for name in archive.namelist() if not name.endswith("/")}
            if "index.html" not in names:
                errors.append("部署 ZIP 根目录缺少 index.html")
            for name in names:
                pure = PurePosixPath(name)
                if pure.is_absolute() or ".." in pure.parts:
                    errors.append(f"部署 ZIP 含不安全路径: {name}")
            missing = set(expected) - names
            extra = names - set(expected)
            if missing:
                errors.append(f"部署 ZIP 缺少 {len(missing)} 个文件: {sorted(missing)[:8]}")
            if extra:
                errors.append(f"部署 ZIP 多出 {len(extra)} 个文件: {sorted(extra)[:8]}")
            for name in sorted(set(expected) & names):
                with archive.open(name) as source, expected[name].open("rb") as target:
                    if archive.getinfo(name).file_size != expected[name].stat().st_size:
                        errors.append(f"部署 ZIP 字节数不一致: {name}")
                        continue
                    digest = hashlib.sha256()
                    target_digest = hashlib.sha256()
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                    for chunk in iter(lambda: target.read(1024 * 1024), b""):
                        target_digest.update(chunk)
                    if digest.digest() != target_digest.digest():
                        errors.append(f"部署 ZIP 内容与暂存目录不一致: {name}")
            bad = archive.testzip()
            if bad:
                errors.append(f"部署 ZIP CRC 失败: {bad}")
    except Exception as exc:
        errors.append(f"部署 ZIP 解析失败: {exc}")


def inspect_package():
    errors: list[str] = []
    files = package_files()
    for rel, path in files.items():
        if path.name.startswith("meaning_intelligence_launch"):
            errors.append(f"发布包仍含旧发布视频: {rel}")
    for rel in REQUIRED:
        path = PACKAGE / rel
        if not path.is_file():
            errors.append(f"缺少核心文件: {rel}")
        elif path.stat().st_size == 0:
            errors.append(f"核心文件为空: {rel}")
    for rel in JSON_FILES:
        try:
            json.loads((PACKAGE / rel).read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"JSON 解析失败 {rel}: {exc}")
    inspect_html(files, errors)
    function_path = PACKAGE / "functions" / "api" / "mcp.js"
    if function_path.is_file() and "export const onRequest" not in function_path.read_text(encoding="utf-8"):
        errors.append("发布包 Web MCP 缺少 Pages Function onRequest 适配器")
    inspect_subtitles(files, errors)
    for rel, path in files.items():
        if path.suffix.lower() == ".epub":
            inspect_epub(path, errors)
    inspect_office(files, errors)
    manifest = inspect_manifest(files, errors)
    inspect_verification_reports(files, errors)
    inspect_media(files, errors)
    source_archive = PACKAGE / "download" / "Meaning_Intelligence_Source_v0.2.0.zip"
    if source_archive.is_file():
        inspect_source_zip(source_archive, errors)
    inspect_complete_zip(files, errors)
    listen = PACKAGE / "listen.html"
    if listen.is_file():
        text = listen.read_text(encoding="utf-8")
        for retired in ("逻辑论证", "案例支持", "观察证据", "实验验证", "跨情境复现", "跨文化外部验证"):
            if retired in text:
                errors.append(f"listen.html 仍含旧证据标签: {retired}")
        for required in ("数学模型", "预注册假设，数据收集中", "跨情境、跨文化、跨时间泛化"):
            if required not in text:
                errors.append(f"listen.html 缺少 V7 证据判据: {required}")
    return files, manifest, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("zip", nargs="?", type=Path, help="可选：校验待部署 ZIP 是否与发布包一致")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    files, manifest, errors = inspect_package()
    if args.zip:
        if not args.zip.is_file():
            errors.append(f"ZIP 不存在: {args.zip}")
        else:
            inspect_zip(args.zip, deployment_files(errors), errors)
    result = {
        "package": str(PACKAGE),
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files.values()),
        "manifest_entries": len(manifest.get("files", [])) if isinstance(manifest, dict) else 0,
        "errors": errors,
        "ok": not errors,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"发布包: {PACKAGE}")
        print(f"文件: {result['files']}；体积: {result['bytes'] / 1048576:.1f} MiB；清单: {result['manifest_entries']}")
        if errors:
            for error in errors:
                print(f"FAIL {error}")
        else:
            print("PASS HTML/JS、字幕、EPUB、Office、媒体、manifest 与完整 ZIP 验收通过")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
