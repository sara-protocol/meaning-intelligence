#!/usr/bin/env python3
"""Build the offline bilingual Meaning Intelligence project guide inside this directory."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import wave
import zipfile
from pathlib import Path

import figures

TARGET = Path(__file__).resolve().parent
DEFAULT_SOURCE = TARGET.parent.parent
LANGUAGES = ("zh", "en")
GAP_SECONDS = 0.32
SAPI_RATE = 1
VOICE_NAMES = {"zh": "Microsoft Huihui Desktop", "en": "Microsoft Zira Desktop"}
CONTENT: dict = {}
FFMPEG = ""
FFPROBE = ""
GUIDE_ARCHIVE = "meaning-intelligence-project-guide-2026-11-27-final4.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_text(path: Path, value: str) -> None:
    """Write atomically and leave unchanged generated files untouched."""
    if path.is_file() and path.read_text(encoding="utf-8") == value:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    for attempt in range(240):
        try:
            temporary.write_text(value, encoding="utf-8")
            temporary.replace(path)
            return
        except PermissionError:
            temporary.unlink(missing_ok=True)
            if attempt == 239:
                raise
            time.sleep(0.25)


def write_json(path: Path, value) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + chr(10))


def tool_path(name: str, explicit: str | None = None) -> str:
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise FileNotFoundError(path)
        return str(path)
    found = shutil.which(name)
    if found:
        return found
    conda = Path.home() / "miniconda3" / "Library" / "bin" / f"{name}.exe"
    if conda.is_file():
        return str(conda)
    raise FileNotFoundError(f"{name} was not found.")


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(command, check=False, text=True, encoding="utf-8", errors="replace", capture_output=capture)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {command[0]}\n{(result.stderr or result.stdout or '')[-6000:]}")
    return result


def probe(path: Path, ffprobe: str) -> dict:
    result = run([ffprobe, "-v", "error", "-show_entries", "format=duration,size:stream=index,codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels", "-of", "json", str(path)], capture=True)
    return json.loads(result.stdout)


def validate_content(content: dict) -> None:
    expected = {"canon": "V7.0", "research_system": "0.2.0", "operational_stack": "2.0", "whitepaper": "1.1", "msi_demo": "2.1"}
    if any(content["meta"].get(key) != value for key, value in expected.items()):
        raise ValueError("Version identities do not match the verified source facts.")
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
    if identifier != expected_identifier:
        raise ValueError("Project identifier does not match the verified OSF project metadata.")
    if len(content["chapters"]) != 18 or len({item["id"] for item in content["chapters"]}) != 18:
        raise ValueError("Expected 18 unique chapters.")
    if [item["id"] for item in content["evidence"]] != [f"E{i}" for i in range(7)]:
        raise ValueError("Expected E0-E6 in order.")
    if len(content["skills"]) != 6 or len(content["scales"]) != 5 or len(content["acts"]) != 8:
        raise ValueError("Expected six skills, five scales, and eight MSI acts.")
    for item in content["chapters"]:
        for key in ("title", "eyebrow", "summary", "paragraphs", "bullets", "practice", "source"):
            if set(item.get(key, {})) != set(LANGUAGES):
                raise ValueError(f"Incomplete localization: {item['id']}.{key}")
        if set(item["visual"].get("alt", {})) != set(LANGUAGES) or set(item["visual"].get("caption", {})) != set(LANGUAGES):
            raise ValueError(f"Incomplete visual localization: {item['id']}")


def remove_tree(path: Path) -> None:
    for attempt in range(12):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            if attempt == 11:
                print(f"WARNING: generated directory remained locked: {path}", file=sys.stderr)
                return
            time.sleep(0.25)


def clean_stale_outputs() -> None:
    """Remove only obsolete derivatives that later stages do not replace."""
    for name in ("verification-summary.js", "audio/meaning-intelligence-guide-zh.mp3", "audio/meaning-intelligence-guide-en.mp3"):
        path = TARGET / name
        if path.is_file():
            path.unlink()
    rendered = TARGET / "rendered"
    if rendered.is_dir():
        remove_tree(rendered)


def convert_to_pdf(document: Path) -> Path:
    """Convert DOCX using a reproducible profile inside the guide directory."""
    candidates = [shutil.which("soffice"), "C:/Program Files/LibreOffice/program/soffice.exe", "C:/Program Files (x86)/LibreOffice/program/soffice.exe"]
    soffice = next((Path(item) for item in candidates if item and Path(item).is_file()), None)
    if soffice is None:
        raise FileNotFoundError("LibreOffice soffice.exe was not found.")
    profile = Path(tempfile.gettempdir()) / f"mi-lo-{time.time_ns()}"
    rendered = TARGET / ".build" / f"pdf-{time.time_ns()}"
    rendered.mkdir(parents=True, exist_ok=True)
    run([str(soffice), f"-env:UserInstallation={profile.resolve().as_uri()}", "--headless", "--convert-to", "pdf", "--outdir", str(rendered), str(document)])
    output = rendered / f"{document.stem}.pdf"
    if not output.is_file() or output.stat().st_size < 1000:
        raise RuntimeError(f"PDF conversion did not create {output}")
    return output


def copy_downloads(content: dict, source_root: Path) -> list[dict]:
    publication = source_root / "意义智能有声读物_发布包"
    download = publication / "download"
    documents = download / "documents"
    repo = source_root / "mi-repo"
    paper_pdf = next((repo / "whitepaper" / "dist").glob("*v1.1*中英双语*.pdf"))
    paper_docx = next((repo / "whitepaper" / "dist").glob("*v1.1*中英双语*.docx"))
    audit_docx = documents / "意义智能_项目审查与优化报告_2026-11-26.docx"
    manual_docx = documents / "意义智能_有声读物_发布指南与操作手册_v3.0.docx"
    attachment_docx = documents / "意义智能_附件衍生更新版_2026-11-26.docx"
    errata_docx = documents / "意义智能_书稿勘误与补充说明_2026-11-26.docx"
    pairs = {
        "downloads/whitepaper-v1.1.pdf": paper_pdf,
        "downloads/whitepaper-v1.1.docx": paper_docx,
        "downloads/msi-eight-acts-43s.mp4": repo / "msi" / "MeaningIntelligenceScene.mp4",
        "downloads/ebook-v1.1-bilingual.epub": download / "Meaning_Intelligence_Audio_Book_v1.1_ZH-EN.epub",
        "downloads/ebook-v1.1-zh.epub": download / "Meaning_Intelligence_Audio_Book_v1.1_ZH.epub",
        "downloads/ebook-v1.1-en.epub": download / "Meaning_Intelligence_Audio_Book_v1.1_EN.epub",
        "downloads/source-v0.2.0-release.zip": download / "Meaning_Intelligence_Source_v0.2.0_2026-11-27_release-final3.zip",
        "downloads/lecture-deck.pptx": download / "意义智能_讲课展示.pptx",
        "downloads/msi-deck.pptx": download / "MSI演进视频讲解版.pptx",
        "downloads/meaning-intelligence-zh-web.mp4": publication / "assets" / "video" / "release" / "meaning_intelligence_zh-web.mp4",
        "downloads/meaning-intelligence-en-web.mp4": publication / "assets" / "video" / "release" / "meaning_intelligence_en-web.mp4",
        "downloads/project-audit-2026-11-26.docx": audit_docx,
        "downloads/release-manual-v3.0.docx": manual_docx,
        "downloads/attachment-updated-2026-11-26.docx": attachment_docx,
        "downloads/attachment-errata-2026-11-26.docx": errata_docx,
        "downloads/release-subtitles-zh.srt": download / "video" / "meaning_intelligence_zh.srt",
        "downloads/release-subtitles-en.srt": download / "video" / "meaning_intelligence_en.srt",
        "downloads/release-narration-zh.txt": download / "video" / "narration_zh.txt",
        "downloads/release-narration-en.txt": download / "video" / "narration_en.txt",
        "downloads/release-verification.json": download / "video" / "build" / "verification.json",
    }
    pdf_derivatives = {
        "downloads/project-audit-2026-11-26.pdf": audit_docx,
        "downloads/release-manual-v3.0.pdf": manual_docx,
        "downloads/attachment-updated-2026-11-27.pdf": attachment_docx,
        "downloads/attachment-errata-2026-11-26.pdf": errata_docx,
    }
    pdf_sources = {relative: document.with_suffix(".pdf") for relative, document in pdf_derivatives.items()}
    generated = {"downloads/project-guide-bilingual.docx", "downloads/project-guide-bilingual.pdf", "downloads/guide-narration-zh.mp3", "downloads/guide-narration-en.mp3"}
    records = []
    for item in content["downloads"]:
        relative = item["path"]
        if relative in generated:
            continue
        source = pairs.get(relative)
        if source is None and relative in pdf_sources:
            source = pdf_sources[relative]
        if source is None:
            raise ValueError(f"No reproducible source mapping for {relative}")
        if not source.is_file():
            raise FileNotFoundError(source)
        target = TARGET / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target.resolve():
            if not target.is_file() or sha256(target) != sha256(source):
                temporary = target.with_name(target.name + ".tmp")
                shutil.copy2(source, temporary)
                replace_generated_file(temporary, target)
        record = {"path": relative, "source": str(source.relative_to(source_root)), "source_sha256": sha256(source), "bytes": target.stat().st_size, "sha256": sha256(target)}
        if relative in pdf_derivatives:
            document = pdf_derivatives[relative]
            if not document.is_file():
                raise FileNotFoundError(document)
            record["derived_from"] = str(document.relative_to(source_root))
            record["derived_from_sha256"] = sha256(document)
        records.append(record)
    missing_pdf_records = set(pdf_derivatives) - {item["path"] for item in records}
    if missing_pdf_records:
        raise ValueError(f"PDF downloads missing from content catalog: {sorted(missing_pdf_records)}")
    return records


def narration_cues(item: dict, index: int, language: str) -> list[str]:
    if language == "zh":
        cues = [f"第{index}章。{item['title']['zh']}。{item['summary']['zh']}"]
        cues.extend(item["paragraphs"]["zh"])
        if item.get("commands"):
            cues.append("可运行命令：" + "；".join(item["commands"]))
        cues.extend(item["bullets"]["zh"])
        cues.append("动手一步：" + item["practice"]["zh"])
        if item.get("pending"):
            cues.append("待核验事项：" + item["pending"]["zh"])
    else:
        cues = [f"Chapter {index}. {item['title']['en']}. {item['summary']['en']}"]
        cues.extend(item["paragraphs"]["en"])
        if item.get("commands"):
            cues.append("Runnable commands: " + "; ".join(item["commands"]))
        cues.extend(item["bullets"]["en"])
        cues.append("Try one step: " + item["practice"]["en"])
        if item.get("pending"):
            cues.append("Pending verification: " + item["pending"]["en"])
    cleaned = []
    for cue in cues:
        value = " ".join(cue.replace("\x00", "").split()).strip()
        if len(value) > 420:
            parts = re.split(r"(?<=[。！？.!?])\s*", value)
            current = ""
            for part in parts:
                if len(current) + len(part) > 420 and current:
                    cleaned.append(current.strip())
                    current = part
                else:
                    current += part
            if current.strip():
                cleaned.append(current.strip())
        elif value:
            cleaned.append(value)
    return cleaned


def read_wav(path: Path) -> tuple[int, bytes]:
    with wave.open(str(path), "rb") as handle:
        if handle.getsampwidth() != 2 or handle.getnchannels() != 1:
            raise RuntimeError(f"Unexpected SAPI WAV format: {path}")
        return handle.getframerate(), handle.readframes(handle.getnframes())


def synthesize(content: dict, content_hash: str, powershell: str) -> dict:
    work = TARGET / ".audio-work"
    if work.exists():
        shutil.rmtree(work)
    wav_root = work / "wav"
    wav_root.mkdir(parents=True)
    cue_map: dict[tuple[str, str], list[dict]] = {}
    jobs = []
    reused = 0
    for index, item in enumerate(content["chapters"], 1):
        for language in LANGUAGES:
            cues = []
            for cue_index, cue_text in enumerate(narration_cues(item, index, language)):
                filename = f"{language}__{item['id']}__{cue_index:03d}.wav"
                destination = wav_root / filename
                digest = hashlib.sha256((cue_text + VOICE_NAMES[language] + str(SAPI_RATE)).encode("utf-8")).hexdigest()
                cached = TARGET / ".build" / "raw" / language / f"{item['id']}_{cue_index + 1:02d}_{digest[:16]}.wav"
                if cached.is_file() and cached.stat().st_size > 1000:
                    shutil.copy2(cached, destination)
                    reused += 1
                else:
                    jobs.append({"language": language, "chapter": item["id"], "index": cue_index, "filename": filename, "text": cue_text})
                cues.append({"index": cue_index, "filename": filename, "text": cue_text})
            cue_map[(item["id"], language)] = cues
    if jobs:
        job_path = work / "cues.json"
        write_json(job_path, {"voices": VOICE_NAMES, "rate": SAPI_RATE, "cues": jobs})
        result = run([powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "RemoteSigned", "-File", str(TARGET / "synthesize.ps1"), "-JobPath", str(job_path), "-OutputDirectory", str(wav_root)], capture=True)
        print(result.stdout.splitlines()[-1] if result.stdout.splitlines() else "SAPI narration completed", flush=True)
    print(f"SAPI cache reused: {reused}; newly synthesized cues: {len(jobs)}", flush=True)
    records = {"version": "1.0.0", "content_sha256": content_hash, "engine": "Windows System.Speech.Synthesis", "rate": SAPI_RATE, "gap_seconds": GAP_SECONDS, "voices": VOICE_NAMES, "sample_rate": 48000, "channels": 1, "mp3_bitrate": "64k", "chapters": []}
    ffmpeg = FFMPEG
    ffprobe = FFPROBE
    for item in content["chapters"]:
        record = {"id": item["id"], "audio": {}}
        for language in LANGUAGES:
            cue_records = cue_map[(item["id"], language)]
            wavs = [wav_root / cue["filename"] for cue in cue_records]
            pieces = [read_wav(path) for path in wavs]
            rates = {rate for rate, _ in pieces}
            if len(rates) != 1:
                raise RuntimeError(f"SAPI sample-rate mismatch: {item['id']} {language}")
            sample_rate = pieces[0][0]
            durations = [len(pcm) / 2 / sample_rate for _, pcm in pieces]
            if any(duration < .15 for duration in durations):
                raise RuntimeError(f"Unexpectedly short cue: {item['id']} {language}")
            chapter_work = work / item["id"] / language
            chapter_work.mkdir(parents=True)
            combined = chapter_work / "combined.wav"
            silence = b"\0\0" * round(sample_rate * GAP_SECONDS)
            with wave.open(str(combined), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(sample_rate)
                for piece_index, (_, pcm) in enumerate(pieces):
                    if piece_index:
                        handle.writeframes(silence)
                    handle.writeframes(pcm)
            output = TARGET / "audio" / language / f"{item['id']}.mp3"
            output.parent.mkdir(parents=True, exist_ok=True)
            run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(combined), "-map_metadata", "-1", "-ar", "48000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k", "-y", str(output)])
            duration = float(probe(output, ffprobe)["format"]["duration"])
            current = 0.0
            timed = []
            for cue, cue_duration in zip(cue_records, durations):
                timed.append({"start": round(current, 3), "end": round(min(duration, current + cue_duration), 3), "text": cue["text"]})
                current += cue_duration + GAP_SECONDS
            record["audio"][language] = {"duration": round(duration, 6), "cues": timed}
            write_captions_and_transcript(item, language, timed, output, duration, VOICE_NAMES[language])
            print(f"AUDIO {language}/{item['id']}: {duration:.3f}s, {len(timed)} cues", flush=True)
        records["chapters"].append(record)
    write_json(TARGET / "audio-timings.json", records)
    return records


def load_existing_audio(content_hash: str) -> dict:
    records = json.loads((TARGET / "audio-timings.json").read_text(encoding="utf-8"))
    if records.get("content_sha256") != content_hash:
        if len(records.get("chapters", [])) != len(CONTENT["chapters"]):
            raise RuntimeError("content.json changed; rerun without --skip-audio.")
        for chapter_index, (record, item) in enumerate(zip(records["chapters"], CONTENT["chapters"]), 1):
            if record["id"] != item["id"]:
                raise RuntimeError("content.json changed; rerun without --skip-audio.")
            for language in LANGUAGES:
                expected_text = narration_cues(item, chapter_index, language)
                recorded_text = [cue["text"] for cue in record["audio"][language]["cues"]]
                if expected_text != recorded_text:
                    raise RuntimeError("Narration content changed; rerun without --skip-audio.")
        records["content_sha256"] = content_hash
        write_json(TARGET / "audio-timings.json", records)
    for record in records["chapters"]:
        item = next(chapter for chapter in CONTENT["chapters"] if chapter["id"] == record["id"])
        for language in LANGUAGES:
            path = TARGET / "audio" / language / f"{item['id']}.mp3"
            if not path.is_file():
                raise FileNotFoundError(path)
            write_captions_and_transcript(item, language, record["audio"][language]["cues"], path, record["audio"][language]["duration"], VOICE_NAMES[language])
    return records


def timestamp(value: float, vtt: bool = False) -> str:
    milliseconds = max(0, round(value * 1000))
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{'.' if vtt else ','}{millis:03d}"


def write_captions_and_transcript(item: dict, language: str, cues: list[dict], audio_path: Path, duration: float, voice: str) -> None:
    caption_dir = TARGET / "captions" / language
    transcript_dir = TARGET / "transcripts" / language
    caption_dir.mkdir(parents=True, exist_ok=True)
    transcript_dir.mkdir(parents=True, exist_ok=True)
    srt, vtt = [], ["WEBVTT", ""]
    transcript = [
        "意义智能" if language == "zh" else "Meaning Intelligence",
        f"{'章节' if language == 'zh' else 'Chapter'}: {item['title'][language]}",
        f"{'语言' if language == 'zh' else 'Language'}: {'中文' if language == 'zh' else 'English'}",
        f"{'旁白' if language == 'zh' else 'Narration'}: {voice} ({'本地 Windows SAPI' if language == 'zh' else 'Windows SAPI'})",
        f"{'音频' if language == 'zh' else 'Audio'}: {audio_path.name}",
        f"{'时长' if language == 'zh' else 'Duration'}: {duration:.3f} {'秒' if language == 'zh' else 'seconds'}",
        ""
    ]
    for index, cue in enumerate(cues, 1):
        srt.extend([str(index), f"{timestamp(cue['start'])} --> {timestamp(cue['end'])}", cue["text"], ""])
        vtt.extend([str(index), f"{timestamp(cue['start'], True)} --> {timestamp(cue['end'], True)}", cue["text"], ""])
        transcript.extend([f"[{timestamp(cue['start'])} --> {timestamp(cue['end'])}]", cue["text"], ""])
    (caption_dir / f"{item['id']}.srt").write_text("\n".join(srt), encoding="utf-8")
    (caption_dir / f"{item['id']}.vtt").write_text("\n".join(vtt), encoding="utf-8")
    (transcript_dir / f"{item['id']}.txt").write_text("\n".join(transcript), encoding="utf-8")


def deterministic_zip(path: Path, files: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(files, key=lambda item: item.name):
            info = zipfile.ZipInfo(source.name, date_time=(2026, 11, 27, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())


def write_audio_metadata(timings: dict) -> None:
    totals = {language: round(sum(chapter["audio"][language]["duration"] for chapter in timings["chapters"]), 6) for language in LANGUAGES}
    write_json(TARGET / ".build" / "audio-metadata.json", {
        "provider": "local Windows SAPI / System.Speech",
        "synthetic": True,
        "rate": SAPI_RATE,
        "voices": {
            "zh": {"Name": VOICE_NAMES["zh"], "Culture": "zh-CN"},
            "en": {"Name": VOICE_NAMES["en"], "Culture": "en-US"},
        },
        "gap_seconds": GAP_SECONDS,
        "chapter_count": len(timings["chapters"]) * len(LANGUAGES),
        "sample_rate": 48000,
        "channels": 1,
        "mp3_bitrate": "64k",
        "total_duration_seconds": totals,
        "aggregate_duration_seconds": round(sum(totals.values()), 6),
    })


def write_bundles(content: dict) -> None:
    for language in LANGUAGES:
        chapter_files = [TARGET / "audio" / language / f"{item['id']}.mp3" for item in content["chapters"]]
        concat_file = TARGET / ".build" / f"guide-{language}.concat.txt"
        lines = [f"file '../{path.relative_to(TARGET).as_posix()}'" for path in chapter_files]
        write_text(concat_file, chr(10).join(lines) + chr(10))
        output = TARGET / "downloads" / f"guide-narration-{language}.mp3"
        run([FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-map_metadata", "-1", "-ar", "48000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k", "-y", str(output)])
        duration = float(probe(output, FFPROBE)["format"]["duration"])
        print(f"Complete narration {language}: {duration:.3f}s", flush=True)
        captions = [TARGET / "captions" / language / f"{item['id']}.{suffix}" for item in content["chapters"] for suffix in ("srt", "vtt")]
        deterministic_zip(TARGET / "captions" / language / "all-captions.zip", captions)
        parts = ["意义智能" if language == "zh" else "Meaning Intelligence", f"{'语言' if language == 'zh' else 'Language'}: {'中文' if language == 'zh' else 'English'}", "完整同步章节文稿" if language == "zh" else "Complete synchronized chapter transcripts", ""]
        for index, item in enumerate(content["chapters"], 1):
            parts.extend([f"===== {index:02d} {item['title'][language]} =====", "", (TARGET / "transcripts" / language / f"{item['id']}.txt").read_text(encoding="utf-8"), ""])
        write_text(TARGET / "transcripts" / language / "all-transcripts.txt", chr(10).join(parts))


def make_docx(content: dict) -> None:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor
    document = Document()
    section = document.sections[0]
    section.top_margin = section.bottom_margin = Pt(18)
    normal = document.styles["Normal"]
    normal.font.name, normal.font.size = "Aptos", Pt(10)
    normal.paragraph_format.space_after = Pt(5)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    for name, size, color in (("Title", 28, "163A5F"), ("Heading 1", 18, "163A5F"), ("Heading 2", 12, "087E8C")):
        style = document.styles[name]
        style.font.name, style.font.size = "Aptos Display", Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    document.add_heading("Meaning Intelligence · 意义智能", 0)
    document.add_paragraph("Bilingual Illustrated Audio Project Guide / 双语图文音频项目手册").alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph("Guide v1.0.0 · Canon V7.0 · Research system v0.2.0 · White paper v1.1 · MSI v2.1")
    identifier = content["meta"]["project_identifier"]
    document.add_paragraph(f"{identifier['title_zh']} / {identifier['title_en']}")
    document.add_paragraph(f"Project DOI: {identifier['resolver']} · OSF category=project; registration=false; preprint=false. Identifier only; no evidence-level promotion.")
    document.add_paragraph("This concise edition contains chapter summaries, key points, practical actions, source trails, and pending items. Audio, subtitles, figures, and downloads are in index.html.")
    document.add_paragraph("本文本版收录章节摘要、关键要点、动手一步、来源线索与待定事项；音频、字幕、插图和下载位于 index.html。")
    document.add_paragraph("Automated results: verification.json. Human accessibility and rights review remain separate; Git, Pages, and online results are recorded in external reports. / 自动结果见 verification.json；人工无障碍与权利审阅另列，Git、Pages 与线上结果见外部报告。")
    for index, item in enumerate(content["chapters"], 1):
        document.add_page_break()
        document.add_heading(f"{index:02d} · {item['title']['zh']}", 1)
        document.add_heading(f"{index:02d} · {item['title']['en']}", 2)
        for language in LANGUAGES:
            document.add_heading("中文" if language == "zh" else "English", 2)
            document.add_paragraph(item["summary"][language])
            for bullet in item["bullets"][language]:
                document.add_paragraph(bullet, style="List Bullet")
            document.add_paragraph(f"{'动手一步' if language == 'zh' else 'Try one step'}: {item['practice'][language]}")
            if item.get("pending"):
                document.add_paragraph(f"{'待核验 / Pending' if language == 'zh' else 'Pending verification'}: {item['pending'][language]}")
            document.add_paragraph(f"{'来源线索' if language == 'zh' else 'Source trail'}: {item['source'][language]}")
            for command in item.get("commands", []):
                text_run = document.add_paragraph().add_run(command)
                text_run.font.name, text_run.font.size = "Consolas", Pt(8)
    document.add_heading("Verification / 验证", 1)
    document.add_paragraph("manifest.json records SHA-256, bytes, media facts, and source mappings. verification.json records exact local automated checks and separately listed human or external production evidence.")
    document.add_paragraph("manifest.json 记录 SHA-256、字节数、媒体事实与来源映射；verification.json 记录精确的本地自动检查，并单列人工或外部生产证据。")
    output = TARGET / "downloads" / "project-guide-bilingual.docx"
    temporary = output.with_name(output.name + ".tmp")
    document.save(temporary)
    replace_generated_file(temporary, output)
    converted = convert_to_pdf(output)
    pdf_output = TARGET / "downloads" / "project-guide-bilingual.pdf"
    replace_generated_file(converted, pdf_output)


def write_runtime(content: dict, timings: dict) -> None:
    runtime = runtime_content(content, timings)
    write_text(TARGET / "content.js", "window.GUIDE_CONTENT = " + json.dumps(runtime, ensure_ascii=False, separators=(",", ":")) + ";" + chr(10))
    template = (TARGET / "template.html").read_text(encoding="utf-8")
    description = runtime["meta"]["description"]["zh"].replace('"', "&quot;")
    template = template.replace('<meta name="description" content="Meaning Intelligence bilingual illustrated offline audio project guide">', f'<meta name="description" content="{description}">')
    write_text(TARGET / "index.html", template)
    write_text(TARGET / "verification.js", 'window.GUIDE_VERIFICATION = {"build_complete":false,"checks":[],"pending":true};' + chr(10))
    write_json(TARGET / "verification.json", {"schema": "meaning-intelligence-project-guide-verification-v1", "ok": False, "build_state": "pending", "generated": runtime["meta"]["generated"], "summary": {"checks_total": 0, "checks_passed": 0, "checks_failed": 0}, "checks": [], "failed": [], "pending": ["Final verification is running."]})


def runtime_content(content: dict, timings: dict) -> dict:
    runtime = copy.deepcopy(content)
    for chapter, record in zip(runtime["chapters"], timings["chapters"]):
        if chapter["id"] != record["id"]:
            raise ValueError("Audio timing order mismatch.")
        chapter["narration"], chapter["audioMeta"] = {}, {}
        for language in LANGUAGES:
            chapter["narration"][language] = record["audio"][language]["cues"]
            chapter["audioMeta"][language] = {"duration": record["audio"][language]["duration"], "file": f"audio/{language}/{chapter['id']}.mp3"}
    return runtime


def replace_generated_file(source: Path, target: Path) -> None:
    for attempt in range(900):
        try:
            source.replace(target)
            return
        except PermissionError:
            if attempt == 899:
                raise
            time.sleep(0.25)


def package_guide() -> None:
    output = TARGET / GUIDE_ARCHIVE
    files = [path for path in manifest_files() if path.name != output.name]
    for name in ("verification.js", "manifest.json", "manifest.sha256", "verification.json"):
        path = TARGET / name
        if path.is_file():
            files.append(path)
    required = {
        "index.html",
        "content.js",
        "verification.js",
        "manifest.json",
        "manifest.sha256",
        "verification.json",
        "downloads/project-guide-bilingual.pdf",
        "downloads/guide-narration-zh.mp3",
        "downloads/guide-narration-en.mp3",
    }
    included = {path.relative_to(TARGET).as_posix() for path in files}
    if not required <= included:
        raise RuntimeError(f"Standalone guide is missing required files: {sorted(required - included)}")
    temporary = output.with_name(output.name + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        stored = {".mp4", ".mp3", ".jpg", ".jpeg", ".png", ".zip", ".epub"}
        for source in files:
            archive.write(source, source.relative_to(TARGET).as_posix(), compress_type=zipfile.ZIP_STORED if source.suffix.lower() in stored else zipfile.ZIP_DEFLATED, compresslevel=6)
    replace_generated_file(temporary, output)


def summary_value(report: dict) -> dict:
    return {"build_complete": report.get("ok", False), "checks": report.get("checks", []), "pending": report.get("pending", [])}


def write_summary(report: dict) -> None:
    write_text(TARGET / "verification.js", "window.GUIDE_VERIFICATION = " + json.dumps(summary_value(report), ensure_ascii=False, separators=(",", ":")) + ";" + chr(10))


def manifest_files() -> list[Path]:
    excluded = {"manifest.json", "manifest.sha256", "verification.json", "verification.js", "meaning-intelligence-project-guide.zip", "meaning-intelligence-project-guide-2026-11-27.zip", GUIDE_ARCHIVE, "downloads/source-v0.2.0.zip", "downloads/source-v0.2.0-final.zip", "downloads/attachment-updated-2026-11-26.pdf", "build_final.py", "verify_package_final.py"}
    files = []
    for path in TARGET.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(TARGET)
        if ".uploading" in relative.name.lower() or ".downloading" in relative.name.lower() or path.suffix.lower() in {".tmp", ".part"}:
            continue
        if relative.parts[0] in {".audio-work", ".build", "rendered", "__pycache__"} or relative.parts[0].startswith(".browser-profile"):
            continue
        if relative.as_posix() in excluded:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(TARGET).as_posix())


def make_manifest(figure_records: list[dict], download_records: list[dict]) -> dict:
    content = json.loads((TARGET / "content.json").read_text(encoding="utf-8"))
    timings = json.loads((TARGET / "audio-timings.json").read_text(encoding="utf-8"))
    files = [{"path": path.relative_to(TARGET).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in manifest_files()]
    media, totals = [], {language: 0.0 for language in LANGUAGES}
    ffprobe = FFPROBE
    for chapter in timings["chapters"]:
        for language in LANGUAGES:
            path = TARGET / "audio" / language / f"{chapter['id']}.mp3"
            details = probe(path, ffprobe)
            stream = next(item for item in details["streams"] if item["codec_type"] == "audio")
            duration = float(details["format"]["duration"])
            totals[language] += duration
            media.append({"path": path.relative_to(TARGET).as_posix(), "language": language, "chapter": chapter["id"], "duration_seconds": duration, "codec": stream.get("codec_name"), "sample_rate_hz": int(stream.get("sample_rate", 0)), "channels": stream.get("channels"), "cue_count": len(chapter["audio"][language]["cues"]), "sha256": sha256(path)})
    recorded_paths = {record["path"] for record in download_records}
    for item in content["downloads"]:
        relative = item["path"]
        if relative not in recorded_paths:
            path = TARGET / relative
            download_records.append({"path": relative, "source": "generated locally by build.py", "bytes": path.stat().st_size, "sha256": sha256(path)})
            recorded_paths.add(relative)
    video_path = TARGET / "downloads" / "msi-eight-acts-43s.mp4"
    video = probe(video_path, ffprobe)
    video_stream = next(item for item in video["streams"] if item["codec_type"] == "video")
    manifest = {
        "schema": "meaning-intelligence-project-guide-manifest-v1",
        "guide": content["meta"], "canon": "V7.0", "research_system": "0.2.0",
        "operational_stack": {"version": "2.0", "evidence_status": "E0", "note": "Engineering extension; not a fixed canon hierarchy."},
        "whitepaper": {"version": "1.1", "pdf_pages": 22, "docx_tables": 9, "docx_inline_figures": 3},
        "msi": {"demo_version": "2.1", "acts": 8, "configured_counts": {"overload_fragments": 45, "core_statements": 3, "structural_nodes": 2, "l3_points": 9}, "video": {"path": video_path.relative_to(TARGET).as_posix(), "duration_seconds": float(video["format"]["duration"]), "codec": video_stream.get("codec_name"), "width": video_stream.get("width"), "height": video_stream.get("height"), "fps": video_stream.get("r_frame_rate"), "audio_streams": sum(1 for item in video["streams"] if item["codec_type"] == "audio")}, "source_preview_provenance": {"duration_seconds": 13.533333, "decision": "Historical source-audit record only; the guide bundles the verified 43.433333-second research render, and current publication acceptance is recorded externally."}},
        "counts": {"chapters": 18, "languages": 2, "narration_files": 36, "srt_files": 36, "vtt_files": 36, "chapter_transcripts": 36},
        "narration": {"engine": "Windows System.Speech.Synthesis", "rate": SAPI_RATE, "voices": VOICE_NAMES, "total_duration_seconds": {key: round(value, 6) for key, value in totals.items()}, "aggregate_duration_seconds": round(sum(totals.values()), 6)},
        "media": media, "figures": figure_records, "copied_downloads": download_records, "files": files,
        "excluded_from_manifest": {"verification.json": "Generated after manifest validation to avoid a circular hash; verification.js is also excluded because it embeds the verification result.", GUIDE_ARCHIVE: "Standalone archive is excluded to avoid self-reference and is validated separately by CRC, safe paths, required files, and self-exclusion."},
        "scope": {"built_in_target_only": True, "publication_root_modified": False, "external_git_actions_performed_by_builder": False, "external_deployment_performed_by_builder": False, "credentials_read": False},
    }
    write_json(TARGET / "manifest.json", manifest)
    lines = [f"{sha256(TARGET / 'manifest.json')}  manifest.json"] + [f"{item['sha256']}  {item['path']}" for item in files]
    write_text(TARGET / "manifest.sha256", "\n".join(lines) + "\n")
    return manifest


def verify(source_root: Path, skip_browser: bool) -> dict:
    run_id = uuid.uuid4().hex
    command = [sys.executable, str(TARGET / "verify.py"), "--source-root", str(source_root), "--ffprobe", FFPROBE, "--run-id", run_id]
    if skip_browser:
        command.append("--skip-browser")
    result = subprocess.run(command, check=False, text=True, encoding="utf-8", errors="replace")
    if result.returncode not in (0, 1):
        raise RuntimeError(f"Verification process failed ({result.returncode}).")
    report = json.loads((TARGET / "verification.json").read_text(encoding="utf-8"))
    if report.get("run_id") != run_id:
        raise RuntimeError("Verification report does not belong to the current run; stale evidence rejected.")
    return report


def main() -> int:
    global CONTENT, FFMPEG, FFPROBE
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--skip-audio", action="store_true")
    parser.add_argument("--skip-browser", action="store_true")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    parser.add_argument("--powershell", default="powershell.exe")
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    if not source_root.is_dir():
        raise NotADirectoryError(source_root)
    FFMPEG = tool_path("ffmpeg", args.ffmpeg)
    FFPROBE = tool_path("ffprobe", args.ffprobe)
    CONTENT = json.loads((TARGET / "content.json").read_text(encoding="utf-8"))
    validate_content(CONTENT)
    clean_stale_outputs()
    content_hash = sha256(TARGET / "content.json")
    print("Building language-specific guide illustrations...", flush=True)
    figure_records = figures.build_figures()
    print("Copying verified downloads and rendering document derivatives...", flush=True)
    download_records = copy_downloads(CONTENT, source_root)
    if args.skip_audio:
        timings = load_existing_audio(content_hash)
    else:
        print("Assembling dedicated Chinese and English SAPI narration...", flush=True)
        timings = synthesize(CONTENT, content_hash, args.powershell)
    write_audio_metadata(timings)
    write_bundles(CONTENT)
    make_docx(CONTENT)
    write_runtime(CONTENT, timings)
    if not args.skip_browser:
        print("Running local HTTP and file browser self-tests...", flush=True)
        run(["node", str(TARGET / "browser_check.mjs"), str(TARGET)])
    make_manifest(figure_records, download_records)
    package_guide()
    print("Verifying structure, media, documents, archives, and hashes...", flush=True)
    report = verify(source_root, args.skip_browser)
    for _ in range(5):
        previous = summary_value(report)
        write_summary(report)
        manifest = make_manifest(figure_records, download_records)
        package_guide()
        report = verify(source_root, args.skip_browser)
        if summary_value(report) == previous:
            break
    else:
        raise RuntimeError("Verification summary did not stabilize after five passes.")
    write_summary(report)
    manifest = make_manifest(figure_records, download_records)
    package_guide()
    if report.get("ok"):
        for name in (".audio-work", ".build", "rendered"):
            path = TARGET / name
            if path.exists():
                remove_tree(path)
        for cache in list(TARGET.rglob("__pycache__")):
            remove_tree(cache)
        for profile in TARGET.glob(".browser-profile*"):
            if profile.is_dir():
                remove_tree(profile)
        for language in LANGUAGES:
            legacy = TARGET / "audio" / f"meaning-intelligence-guide-{language}.mp3"
            if legacy.is_file():
                legacy.unlink()
    print(json.dumps({"ok": report.get("ok"), "checks_passed": sum(1 for item in report.get("checks", []) if item.get("ok")), "checks_total": len(report.get("checks", [])), "pending": len(report.get("pending", [])), "manifest_files": len(manifest["files"]), "narration": manifest["narration"]}, ensure_ascii=False, indent=2), flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"BUILD ERROR: {error}", file=sys.stderr)
        raise
