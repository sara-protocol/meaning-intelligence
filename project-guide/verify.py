#!/usr/bin/env python3
"""Automated structural, media, archive, provenance, and manifest verification."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import posixpath
import re
import subprocess
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET

TARGET = Path(__file__).resolve().parent
LANGUAGES = ("zh", "en")
SKILLS = ["reduce-cognitive-load", "model-experiential-interface", "map-direction-value-boundary", "grade-evidence-falsification", "calibrate-five-scales", "recursive-review-zeroing"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path: Path, value) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    for attempt in range(12):
        try:
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 11:
                path.write_text(text, encoding="utf-8")
                return
            time.sleep(0.25)


def run(command: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed: {(result.stderr or result.stdout)[-2000:]}")
    return result


def probe_media(path: Path, ffprobe: str) -> dict:
    return json.loads(run([ffprobe, "-v", "error", "-show_entries", "format=duration,size:stream=index,codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels", "-of", "json", str(path)]).stdout)


def parse_time(value: str) -> float:
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_caption(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if path.suffix == ".vtt":
        if not lines or lines[0] != "WEBVTT":
            raise ValueError("Missing WEBVTT header")
        lines = lines[1:]
    cues = []
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        if re.fullmatch(r"\d+", lines[index].strip()):
            index += 1
            if index >= len(lines):
                raise ValueError("Missing timing line")
        if " --> " not in lines[index]:
            raise ValueError(f"Invalid timing line: {lines[index]}")
        start_text, end_text = lines[index].split(" --> ")
        index += 1
        text_lines = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index])
            index += 1
        cues.append({"start": parse_time(start_text.strip()), "end": parse_time(end_text.strip()), "text": "\n".join(text_lines)})
    return cues


def parse_transcript(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    cues = []
    for index, line in enumerate(lines):
        match = re.fullmatch(r"\[(.+) --> (.+)\]", line.strip())
        if match:
            cues.append({"start": parse_time(match.group(1)), "end": parse_time(match.group(2)), "text": lines[index + 1] if index + 1 < len(lines) else ""})
    return cues


def check_epub(path: Path) -> tuple[bool, str]:
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                return False, "CRC failure"
            names = set(archive.namelist())
            if archive.read("mimetype") != b"application/epub+zip":
                return False, "Invalid mimetype"
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile = container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
            if rootfile is None or not rootfile.attrib.get("full-path"):
                return False, "No OPF rootfile"
            opf_name = rootfile.attrib["full-path"]
            opf = ET.fromstring(archive.read(opf_name))
            ns = {"opf": "http://www.idpf.org/2007/opf"}
            manifest = opf.find("opf:manifest", ns)
            spine = opf.find("opf:spine", ns)
            if manifest is None or spine is None or len(spine.findall("opf:itemref", ns)) == 0:
                return False, "Missing manifest or spine entries"
            missing = []
            opf_dir = posixpath.dirname(opf_name)
            for item in manifest.findall("opf:item", ns):
                href = unquote(item.attrib.get("href", "")).split("#", 1)[0]
                if href and not href.startswith(("http:", "https:")):
                    resolved = posixpath.normpath(posixpath.join(opf_dir, href))
                    if resolved not in names:
                        missing.append(resolved)
            return (not missing, "OK" if not missing else f"Missing {missing[:3]}")
    except Exception as error:
        return False, str(error)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=TARGET.parent.parent)
    parser.add_argument("--skip-browser", action="store_true")
    parser.add_argument("--ffprobe")
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    ffprobe = args.ffprobe or __import__("shutil").which("ffprobe") or str(Path.home() / "miniconda3" / "Library" / "bin" / "ffprobe.exe")
    ffmpeg = __import__("shutil").which("ffmpeg") or str(Path.home() / "miniconda3" / "Library" / "bin" / "ffmpeg.exe")
    checks = []
    pending = [
        {"id": "human-accessibility", "title": {"zh": "人工无障碍与视觉验收", "en": "Human accessibility and visual acceptance"}, "detail": {"zh": "读屏、键盘、移动端、打印与内容人工审阅未由自动检查替代。", "en": "Screen-reader, keyboard, mobile, print, and human content review are not replaced by automated checks."}},
        {"id": "rights", "title": {"zh": "内容与合成语音权利审阅", "en": "Content and synthetic-voice rights review"}, "detail": {"zh": "文稿、图片、文档及 SAPI 声音的发布权利需由项目方确认。", "en": "The project owner must confirm publication rights for scripts, figures, documents, and SAPI voices."}},
        {"id": "upstream-canon", "title": {"zh": "上游正典未修问题", "en": "Unresolved upstream canon issues"}, "detail": {"zh": "H5 截断、H6 冲突、英文正文不完整及候选 DOCX 图片占位仍按审计记录保留。", "en": "H5 truncation, H6 conflict, incomplete English body, and candidate DOCX image placeholders remain recorded upstream issues."}},
        {"id": "production", "title": {"zh": "生产部署与线上复验", "en": "Production deployment and online re-verification"}, "detail": {"zh": "指南构建器不执行 Git 或部署；提交、推送、Pages、公共 MCP 配置与线上验收以外部部署报告和在线验收报告为准。", "en": "The guide builder performs no Git or deployment actions; commit, push, Pages, public MCP configuration, and online acceptance are evidenced by external deployment and online verification reports."}},
        {"id": "empirical-validation", "title": {"zh": "独立实证验证", "en": "Independent empirical validation"}, "detail": {"zh": "本指南不把 E0 工程草案或运行原型宣称为独立实证结论。", "en": "The guide does not present E0 engineering drafts or runnable prototypes as independently validated findings."}},
        {"id": "pronunciation", "title": {"zh": "合成语音发音人工试听", "en": "Manual listening for synthetic pronunciation"}, "detail": {"zh": "技术名词与中英混读建议人工试听；自动检查只验证非静音与时长。", "en": "Technical terms and mixed-language pronunciation need manual listening; automation checks only non-silence and duration."}},
    ]

    def check(category: str, name: str, ok: bool, detail="") -> None:
        checks.append({"category": category, "name": name, "ok": bool(ok), "detail": str(detail)})

    try:
        runtime = (TARGET / "content.js").read_text(encoding="utf-8")
        content = json.loads(runtime.split("=", 1)[1].rstrip().removesuffix(";"))
        timings = json.loads((TARGET / ".build" / "audio-metadata.json").read_text(encoding="utf-8"))
        manifest = json.loads((TARGET / "manifest.json").read_text(encoding="utf-8"))
        check("structure", "parse-runtime-content", True, "18 chapters with narration")
        check("structure", "parse-audio-metadata", timings.get("chapter_count") == 36 and set(timings.get("voices", {})) == set(LANGUAGES), "36 chapter voices")
        check("structure", "parse-manifest-json", manifest.get("schema") == "meaning-intelligence-project-guide-manifest-v1", manifest.get("schema"))
    except Exception as error:
        check("structure", "parse-required-json", False, error)
        report = {"schema": "meaning-intelligence-project-guide-verification-v1", "ok": False, "generated": "2026-11-26", "summary": {"checks_total": len(checks), "checks_passed": 0, "checks_failed": len(checks)}, "checks": checks, "pending": pending}
        write_json_atomic(TARGET / "verification.json", report)
        return 1

    chapter_ids = [item["id"] for item in content["chapters"]]
    check("structure", "chapter-count-unique", len(chapter_ids) == 18 and len(set(chapter_ids)) == 18, f"{len(chapter_ids)} chapters, {len(set(chapter_ids))} unique")
    check("structure", "six-skill-registry", [item["name"] for item in content["skills"]] == SKILLS, ", ".join(SKILLS))
    check("structure", "five-scales-eight-acts", len(content["scales"]) == 5 and len(content["acts"]) == 8, f"{len(content['scales'])} scales, {len(content['acts'])} acts")
    localized_ok = True
    missing_keys = []
    for item in content["chapters"]:
        for key in ("title", "eyebrow", "summary", "paragraphs", "bullets", "practice", "source"):
            if set(item.get(key, {})) != set(LANGUAGES):
                localized_ok = False
                missing_keys.append(f"{item['id']}.{key}")
        if set(item["visual"].get("alt", {})) != set(LANGUAGES) or set(item["visual"].get("caption", {})) != set(LANGUAGES):
            localized_ok = False
            missing_keys.append(f"{item['id']}.visual")
    check("bilingual", "chapter-localization-complete", localized_ok and not missing_keys, ", ".join(missing_keys) or "all chapter fields have zh/en")
    check("bilingual", "ui-localization-parity", set(content["ui"]["zh"]) == set(content["ui"]["en"]) and all(str(value).strip() for lang in LANGUAGES for value in content["ui"][lang].values()), f"{len(content['ui']['zh'])} UI keys per language")
    check("bilingual", "no-known-mixed-wording", "文本 fragment" not in json.dumps(content, ensure_ascii=False) and "章节 Narration" not in json.dumps(content, ensure_ascii=False), "known mixed-language fragments removed")
    check("structure", "version-identities", content["meta"]["canon"] == "V7.0" and content["meta"]["research_system"] == "0.2.0" and content["meta"]["whitepaper"] == "1.1" and content["meta"]["msi_demo"] == "2.1", json.dumps({key: content["meta"][key] for key in ("canon", "research_system", "operational_stack", "whitepaper", "msi_demo")}))
    identifier = content["meta"].get("project_identifier", {})
    expected_identifier = {
        "title_zh": "意义智能：理论框架、证据设计和验证",
        "title_en": "Meaning Intelligence: Theoretical Framework, Evidence Design, and Validation",
        "doi": "10.17605/OSF.IO/3XKGY",
        "resolver": "https://doi.org/10.17605/OSF.IO/3XKGY",
        "landing_page": "https://osf.io/3xkgy/",
        "registry": "OSF", "registry_id": "3xkgy",
        "category": "project", "public": True, "registration": False, "preprint": False,
        "verified": "2026-11-27",
        "evidence_boundary": "Identifier only; not preregistration, peer review, publication, replication, or evidence-level promotion.",
    }
    check("provenance", "project-doi-boundary", identifier == expected_identifier and identifier["doi"] in (source_root / "mi-repo" / "VERSION.yaml").read_text(encoding="utf-8"), "OSF project identifier; not registration/preprint; no evidence promotion")
    check("structure", "evidence-e0-e6", [item["id"] for item in content["evidence"]] == [f"E{i}" for i in range(7)] and "preregistered" in content["evidence"][3]["definition"]["en"] and "independent" in content["evidence"][4]["definition"]["en"] and "contexts" in content["evidence"][6]["definition"]["en"], "V7 evidence semantics")

    for script in ("content.js", "verification.js", "app.js"):
        result = subprocess.run(["node", "--check", str(TARGET / script)], text=True, capture_output=True)
        check("structure", f"javascript-syntax-{script}", result.returncode == 0, result.stderr.strip() or "OK")
    import ast
    python_errors = []
    for script in ("build.py", "verify.py"):
        try:
            ast.parse((TARGET / script).read_text(encoding="utf-8"), filename=script)
        except SyntaxError as error:
            python_errors.append(str(error))
    check("structure", "python-syntax", not python_errors, "; ".join(python_errors) or "OK")
    result = subprocess.run(["node", "--check", str(TARGET / "browser_check.mjs")], text=True, capture_output=True)
    check("structure", "browser-script-syntax", result.returncode == 0, result.stderr.strip() or "OK")

    expected = [TARGET / "index.html", TARGET / "content.js", TARGET / "verification.js", TARGET / "app.js", TARGET / "styles.css", TARGET / "content.json", TARGET / "manifest.json", TARGET / "manifest.sha256", TARGET / "verification.json", TARGET / "browser_check.mjs", TARGET / "meaning-intelligence-project-guide-2026-11-27.zip", TARGET / "downloads/project-guide-bilingual.pdf", TARGET / "downloads/meaning-intelligence-zh.mp4", TARGET / "downloads/meaning-intelligence-en.mp4", TARGET / "downloads/guide-narration-zh.mp3", TARGET / "downloads/guide-narration-en.mp3"]
    expected += [TARGET / "audio" / lang / f"{item}.mp3" for lang in LANGUAGES for item in chapter_ids]
    expected += [TARGET / "captions" / lang / f"{item}.{suffix}" for lang in LANGUAGES for item in chapter_ids for suffix in ("srt", "vtt")]
    expected += [TARGET / "transcripts" / lang / f"{item}.txt" for lang in LANGUAGES for item in chapter_ids]
    expected += [TARGET / "downloads" / item["path"].split("/")[-1] for item in content["downloads"]]
    expected += [TARGET / "captions" / lang / "all-captions.zip" for lang in LANGUAGES]
    expected += [TARGET / "transcripts" / lang / "all-transcripts.txt" for lang in LANGUAGES]
    expected += [TARGET / "assets" / "figures" / lang / f"{alias}.jpg" for lang in LANGUAGES for alias in ("fig1-1", "figC-1", "fig7-1", "fig5-1", "fig25-1")]
    missing = [str(path.relative_to(TARGET)) for path in expected if not path.is_file()]
    check("structure", "expected-local-files", not missing, f"{len(expected)} expected; missing={missing}")
    counts = {"audio": len(list((TARGET / "audio").glob("*/*.mp3"))), "srt": len(list((TARGET / "captions").glob("*/*.srt"))), "vtt": len(list((TARGET / "captions").glob("*/*.vtt"))), "transcripts": len([path for path in (TARGET / "transcripts").glob("*/*.txt") if path.name != "all-transcripts.txt"])}
    check("structure", "media-file-counts", counts == {"audio": 36, "srt": 36, "vtt": 36, "transcripts": 36}, json.dumps(counts))
    try:
        from PIL import Image
        images = list((TARGET / "assets" / "figures").glob("*/*.jpg"))
        dimensions = []
        for image in images:
            with Image.open(image) as opened:
                opened.verify()
            with Image.open(image) as opened:
                dimensions.append(opened.size)
        check("structure", "figure-images-decodable", len(images) == 10 and all((width, height) == (1600, 900) for width, height in dimensions), f"{len(images)} images; dimensions={dimensions}")
    except Exception as error:
        check("structure", "figure-images-decodable", False, error)

    html = (TARGET / "index.html").read_text(encoding="utf-8")
    hrefs = re.findall(r"(?:href|src)=\"([^\"]+)\"", html)
    external = [value for value in hrefs if re.match(r"^(?:https?:)?//", value, re.I) or value.startswith("http:") or value.startswith("https:")]
    missing_html = [value for value in hrefs if not value.startswith("#") and not external and not (TARGET / value.split("?", 1)[0]).is_file()]
    check("structure", "html-local-resources", not external and not missing_html, f"external={external}; missing={missing_html}")
    check("structure", "offline-csp", "connect-src 'none'" in html and "default-src 'self' data: blob:" in html and "script-src 'self'" in html and "object-src 'none'" in html, "local-only CSP present")
    check("structure", "download-paths-local", all(item["path"].startswith("downloads/") and (TARGET / item["path"]).is_file() for item in content["downloads"]), f"{len(content['downloads'])} download records")
    try:
        with zipfile.ZipFile(TARGET / "meaning-intelligence-project-guide-2026-11-27.zip") as archive:
            names = archive.namelist()
            unsafe = [name for name in names if name.startswith("/") or ".." in Path(name).parts]
            required = {"index.html", "content.js", "verification.js", "manifest.json", "manifest.sha256", "verification.json", "downloads/project-guide-bilingual.pdf", "downloads/guide-narration-zh.mp3", "downloads/guide-narration-en.mp3"}
            ok = archive.testzip() is None and not unsafe and required <= set(names) and "meaning-intelligence-project-guide-2026-11-27.zip" not in names and not any(name.endswith((".tmp", ".part")) for name in names)
            check("structure", "standalone-guide-archive", ok, f"{len(names)} entries; CRC={archive.testzip()}; unsafe={unsafe}; missing={sorted(required - set(names))}")
    except Exception as error:
        check("structure", "standalone-guide-archive", False, error)

    source_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in TARGET.rglob("*") if path.is_file() and path.suffix.lower() in {".py", ".js", ".json", ".html", ".css", ".ps1", ".txt", ".md"} and ".audio-work" not in path.parts)
    patterns = [r"AKIA[0-9A-Z]{16}", r"sk-[A-Za-z0-9]{20,}", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", r"Bearer\s+[A-Za-z0-9_\-]{24,}"]
    secret_hits = [pattern for pattern in patterns if re.search(pattern, source_text)]
    check("security", "no-credential-like-values", not secret_hits, f"patterns matched={secret_hits}")

    version_path = source_root / "mi-repo" / "VERSION.yaml"
    version = version_path.read_text(encoding="utf-8")
    check("provenance", "source-version-yaml", all(value in version for value in ('version: "V7.0"', 'version: "0.2.0"', 'evidence_status: "E0"', 'version: "1.1"', 'pages: 22', 'tables: 9', 'figures: 3', 'version: "2.1"', 'acts: 8')), str(version_path))
    canon_hash = "0fedff1ee5775bbc6812cea24f6024e36e54d43fac4776ba6f94c402ff4cb574"
    english_hash = "b4225b6371d0ea013fe2ae4db9ac396537e2bf30f94cbda5a2c342e5f570396b"
    serialized = json.dumps(content, ensure_ascii=False)
    check("provenance", "canon-hashes-documented", canon_hash in version and english_hash in version and canon_hash in serialized and english_hash in serialized, "primary and English-mother recorded hashes")
    audit = (source_root / "mi-repo" / "docs" / "canon-audit.md").read_text(encoding="utf-8")
    check("provenance", "upstream-issues-documented", all(value in serialized for value in ("H5", "H6", "English", "DOCX")) and "H5" in audit and "H6" in audit, "H5/H6/English/DOCX issues retained")
    engine = (source_root / "mi-repo" / "meaning-agent" / "meaning_agent" / "engine.py").read_text(encoding="utf-8")
    check("agent", "approval-pending-default", "pending_human_approval" in engine and '"execution_authorized": False' in engine and '"performed": False' in engine, "pending human approval; execution not authorized or performed")
    public_mcp = (source_root / "意义智能有声读物_发布包" / "functions" / "api" / "mcp.js").read_text(encoding="utf-8")
    check("agent", "web-mcp-boundary", all(value in public_mcp for value in ("2025-03-26", "32", "60", "MI_MCP_PUBLIC_TOKEN", "Origin")), "protocol, body cap, rate, token, Origin")
    local_mcp = (source_root / "mi-repo" / "meaning-agent" / "meaning_agent" / "mcp_server.py").read_text(encoding="utf-8")
    check("agent", "local-mcp-read-only", "2024-11-05" in local_mcp and "meaning_analyze" in local_mcp and "meaning_review" in local_mcp, "fixed analysis/review surface")

    duration_totals = {lang: 0.0 for lang in LANGUAGES}
    for item in content["chapters"]:
        for language in LANGUAGES:
            prefix = f"{language}/{item['id']}"
            audio_path = TARGET / "audio" / language / f"{item['id']}.mp3"
            try:
                media = probe_media(audio_path, ffprobe)
                stream = next(entry for entry in media["streams"] if entry["codec_type"] == "audio")
                duration = float(media["format"]["duration"])
                duration_totals[language] += duration
                volume = run([ffmpeg, "-hide_banner", "-i", str(audio_path), "-af", "volumedetect", "-f", "null", "-"]).stderr
                mean_match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", volume)
                max_match = re.search(r"max_volume:\s*(-?[\d.]+) dB", volume)
                mean = float(mean_match.group(1)) if mean_match else -999
                maximum = float(max_match.group(1)) if max_match else -999
                ok = stream.get("codec_name") == "mp3" and int(stream.get("sample_rate", 0)) == 48000 and stream.get("channels") == 1 and duration > 5 and mean > -45 and maximum > -20
                check("media", f"audio-{prefix}", ok, f"{duration:.6f}s; {stream.get('codec_name')}; {stream.get('sample_rate')}Hz; {stream.get('channels')}ch; mean={mean}dB; max={maximum}dB")
            except Exception as error:
                check("media", f"audio-{prefix}", False, error)
                continue
            try:
                expected_cues = item["narration"][language]
                srt = parse_caption(TARGET / "captions" / language / f"{item['id']}.srt")
                vtt = parse_caption(TARGET / "captions" / language / f"{item['id']}.vtt")
                transcript = parse_transcript(TARGET / "transcripts" / language / f"{item['id']}.txt")
                def normalized(cues):
                    return [{"start": round(cue["start"], 3), "end": round(cue["end"], 3), "text": cue["text"]} for cue in cues]
                exact = normalized(expected_cues) == normalized(srt) == normalized(vtt) == normalized(transcript)
                monotonic = all(cue["start"] >= 0 and cue["end"] > cue["start"] for cue in srt) and all(srt[index]["end"] <= srt[index + 1]["start"] + .002 for index in range(len(srt) - 1)) and srt[-1]["end"] <= duration + .1
                check("media", f"captions-transcript-{prefix}", exact and monotonic, f"{len(srt)} synchronized cues; last={srt[-1]['end']:.3f}s; audio={duration:.3f}s")
            except Exception as error:
                check("media", f"captions-transcript-{prefix}", False, error)
    check("media", "narration-duration-totals", all(value > 60 for value in duration_totals.values()), json.dumps({key: round(value, 6) for key, value in duration_totals.items()}))
    check("media", "narration-voices-recorded", timings.get("voices", {}).get("zh", {}).get("Name") == "Microsoft Huihui Desktop" and timings.get("voices", {}).get("en", {}).get("Name") == "Microsoft Zira Desktop" and timings.get("provider") == "local Windows SAPI / System.Speech", json.dumps(timings.get("voices")))
    bundle_durations = {}
    bundle_hashes = []
    for language in LANGUAGES:
        try:
            bundle = TARGET / "downloads" / f"guide-narration-{language}.mp3"
            media = probe_media(bundle, ffprobe)
            stream = next(entry for entry in media["streams"] if entry["codec_type"] == "audio")
            duration = float(media["format"]["duration"])
            bundle_durations[language] = duration
            bundle_hashes.append(sha256(bundle))
            ok = stream.get("codec_name") == "mp3" and int(stream.get("sample_rate", 0)) == 48000 and stream.get("channels") == 1 and abs(duration - duration_totals[language]) < 2
            check("media", f"complete-guide-narration-{language}", ok, f"{duration:.6f}s; chapters={duration_totals[language]:.6f}s")
        except Exception as error:
            check("media", f"complete-guide-narration-{language}", False, error)
    check("media", "language-narration-distinct", len(set(bundle_hashes)) == 2, json.dumps(bundle_hashes))

    video_path = TARGET / "downloads" / "msi-eight-acts-43s.mp4"
    try:
        media = probe_media(video_path, ffprobe)
        stream = next(entry for entry in media["streams"] if entry["codec_type"] == "video")
        duration = float(media["format"]["duration"])
        fps = stream.get("r_frame_rate")
        ok = abs(duration - 43.433333) < .03 and stream.get("codec_name") == "h264" and stream.get("width") == 1920 and stream.get("height") == 1080 and fps == "60/1" and not any(entry["codec_type"] == "audio" for entry in media["streams"])
        check("media", "msi-eight-act-video", ok, f"{duration:.6f}s; {stream.get('codec_name')}; {stream.get('width')}x{stream.get('height')}; {fps}fps; no audio")
    except Exception as error:
        check("media", "msi-eight-act-video", False, error)

    for language in LANGUAGES:
        try:
            with zipfile.ZipFile(TARGET / "captions" / language / "all-captions.zip") as archive:
                names = archive.namelist()
                ok = archive.testzip() is None and len(names) == 36 and all(name.endswith((".srt", ".vtt")) for name in names)
                check("media", f"caption-bundle-{language}", ok, f"{len(names)} caption files")
            complete = (TARGET / "transcripts" / language / "all-transcripts.txt").read_text(encoding="utf-8")
            check("media", f"complete-transcript-{language}", all(item["title"][language] in complete for item in content["chapters"]), "all 18 chapter titles")
        except Exception as error:
            check("media", f"narration-bundle-{language}", False, error)

    try:
        import fitz
        pdf = fitz.open(TARGET / "downloads" / "whitepaper-v1.1.pdf")
        check("documents", "whitepaper-pdf-22-pages", pdf.page_count == 22, f"{pdf.page_count} pages")
        pdf.close()
    except Exception as error:
        check("documents", "whitepaper-pdf-22-pages", False, error)
    try:
        from docx import Document
        paper = Document(TARGET / "downloads" / "whitepaper-v1.1.docx")
        check("documents", "whitepaper-docx-9-tables-3-figures", len(paper.tables) == 9 and len(paper.inline_shapes) == 3, f"{len(paper.tables)} tables; {len(paper.inline_shapes)} inline figures; {len(paper.paragraphs)} paragraphs")
        guide = Document(TARGET / "downloads" / "project-guide-bilingual.docx")
        guide_text = "\n".join(paragraph.text for paragraph in guide.paragraphs)
        titles_ok = all(item["title"][language] in guide_text for item in content["chapters"] for language in LANGUAGES)
        check("documents", "guide-docx-bilingual-18-chapters", titles_ok and "Pending verification" in guide_text and "待核验" in guide_text, f"{len(guide.paragraphs)} paragraphs; all localized chapter titles present")
    except Exception as error:
        check("documents", "docx-verification", False, error)

    for name in ("ebook-v1.1-bilingual.epub", "ebook-v1.1-zh.epub", "ebook-v1.1-en.epub"):
        ok, detail = check_epub(TARGET / "downloads" / name)
        check("documents", f"epub-{name}", ok, detail)
    for name in ("source-v0.2.0-release.zip", "lecture-deck.pptx", "msi-deck.pptx"):
        try:
            with zipfile.ZipFile(TARGET / "downloads" / name) as archive:
                bad = archive.testzip()
                names = archive.namelist()
                unsafe = [entry for entry in names if entry.startswith("/") or ".." in Path(entry).parts]
                ok = bad is None and not unsafe
                detail = f"{len(names)} entries; CRC={bad}; unsafe={unsafe}"
                if name == "source-v0.2.0-release.zip":
                    required = ["meaning-intelligence/meaning-agent/meaning_agent/engine.py", "meaning-intelligence/meaning-agent/meaning_agent/skills/registry.py", "meaning-intelligence/meaning-agent/meaning_agent/mcp_server.py", "meaning-intelligence/VERSION.yaml"]
                    authoritative = source_root / "意义智能有声读物_发布包" / "download" / "Meaning_Intelligence_Source_v0.2.0_2026-11-27_release-final3.zip"
                    identical = authoritative.is_file() and sha256(TARGET / "downloads" / name) == sha256(authoritative)
                    ok = ok and all(entry in names for entry in required) and identical
                    detail += f"; required={all(entry in names for entry in required)}; authoritative_identity={identical}"
                check("documents", f"archive-{name}", ok, detail)
        except Exception as error:
            check("documents", f"archive-{name}", False, error)

    try:
        mismatches = []
        for entry in manifest["files"]:
            path = TARGET / entry["path"]
            if not path.is_file() or path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
                mismatches.append(entry["path"])
        check("hash", "manifest-file-hashes", not mismatches and len(manifest["files"]) >= 130, f"{len(manifest['files'])} files verified; mismatches={mismatches}")
        lines = (TARGET / "manifest.sha256").read_text(encoding="utf-8").splitlines()
        parsed = {}
        for line in lines:
            digest, name = line.split("  ", 1)
            parsed[name] = digest
        expected_hashes = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
        expected_hashes["manifest.json"] = sha256(TARGET / "manifest.json")
        check("hash", "manifest-sha256-list", parsed == expected_hashes, f"{len(parsed)} digest lines")
        check("hash", "manifest-scope", manifest.get("scope") == {"built_in_target_only": True, "publication_root_modified": False, "external_git_actions_performed_by_builder": False, "external_deployment_performed_by_builder": False, "credentials_read": False}, json.dumps(manifest.get("scope")))
    except Exception as error:
        check("hash", "manifest-verification", False, error)

    if args.skip_browser:
        pending.append({"id": "browser", "title": {"zh": "浏览器自动检查已跳过", "en": "Browser automation skipped"}, "detail": {"zh": "使用 --skip-browser 运行；最终验收不应跳过。", "en": "Run used --skip-browser; final acceptance must not skip it."}})
    else:
        try:
            browser = json.loads((TARGET / "browser-check.json").read_text(encoding="utf-8"))
            check("browser", "browser-two-modes", browser.get("ok") and [entry.get("mode") for entry in browser.get("modes", [])] == ["http", "file"], f"{browser.get('checks_passed')}/{browser.get('checks_total')} checks")
            for result in browser.get("modes", []):
                failures = [entry for entry in result.get("checks", []) if not entry.get("ok")]
                check("browser", f"browser-{result.get('mode')}", result.get("ok") and not failures, f"{len(result.get('checks', [])) - len(failures)}/{len(result.get('checks', []))}; failures={failures}")
        except Exception as error:
            check("browser", "browser-report", False, error)

    failed = [entry for entry in checks if not entry["ok"]]
    categories = Counter(entry["category"] for entry in checks)
    report = {
        "schema": "meaning-intelligence-project-guide-verification-v1",
        "ok": not failed,
        "generated": content["meta"]["generated"],
        "target": str(TARGET),
        "summary": {"checks_total": len(checks), "checks_passed": len(checks) - len(failed), "checks_failed": len(failed), "pending_total": len(pending), "categories": dict(sorted(categories.items())), "narration_duration_seconds": {key: round(value, 6) for key, value in duration_totals.items()}, "aggregate_narration_duration_seconds": round(sum(duration_totals.values()), 6)},
        "checks": checks,
        "failed": failed,
        "pending": pending,
        "manifest_sha256": sha256(TARGET / "manifest.json"),
    }
    write_json_atomic(TARGET / "verification.json", report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if failed:
        for entry in failed:
            print(f"FAIL {entry['category']} {entry['name']}: {entry['detail']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
