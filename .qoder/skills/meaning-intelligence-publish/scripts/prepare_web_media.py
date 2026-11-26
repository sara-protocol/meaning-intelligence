#!/usr/bin/env python3
"""Create and verify size-compliant streaming derivatives without altering masters."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")

WORKSPACE = Path(__file__).resolve().parents[2]
PACKAGE = WORKSPACE / "意义智能有声读物_发布包"
VIDEO_SOURCE = WORKSPACE / "deliverables" / "video"
REPORT = WORKSPACE / "deliverables" / "web-media-verification.json"
LIMIT = 25 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"Command failed: {command[0]}\n{(result.stderr or result.stdout)[-4000:]}")


def probe(path: Path) -> dict:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate:stream_tags=language",
        "-of", "json", str(path),
    ], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    return json.loads(result.stdout)


def convert(source: Path, target: Path, video: bool, reuse: bool = False) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if reuse and target.is_file():
        print(f"REUSE {target.relative_to(WORKSPACE)}")
        return
    with tempfile.TemporaryDirectory(prefix="mi-web-media-") as temporary:
        output = Path(temporary) / target.name
        if video:
            command = [
                "ffmpeg", "-y", "-hide_banner", "-i", str(source),
                "-map", "0:v:0", "-map", "0:a:0", "-map", "0:s?", "-map_metadata", "0",
                "-vf", "scale=1280:720:flags=lanczos", "-r", "24",
                "-c:v", "libopenh264", "-b:v", "1100k",
                "-maxrate", "1200k", "-bufsize", "2400k", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "96k", "-ar", "48000", "-ac", "2",
                "-c:s", "mov_text", "-movflags", "+faststart", str(output),
            ]
        else:
            command = [
                "ffmpeg", "-y", "-hide_banner", "-i", str(source),
                "-map_metadata", "0", "-af", "aresample=async=1000:first_pts=0:min_comp=0.001:min_hard_comp=0.001",
                "-ac", "1", "-c:a", "libmp3lame", "-b:a", "80k",
                str(output),
            ]
        run(command)
        output.replace(target)
    print(f"PASS {target.relative_to(WORKSPACE)} ({target.stat().st_size / 1048576:.2f} MiB)")


def main() -> int:
    previous = {}
    try:
        old_report = json.loads(REPORT.read_text(encoding="utf-8"))
        if old_report.get("ok"):
            previous = {item["path"]: item for item in old_report.get("records", [])}
    except (OSError, ValueError):
        pass
    audio_source = PACKAGE / "assets" / "audio.mp3"
    audio_target = PACKAGE / "assets" / "audio-web.mp3"
    audio_source_hash = sha256(audio_source)
    old_audio = previous.get(str(audio_target.relative_to(WORKSPACE)), {})
    audio_reuse = old_audio.get("source_sha256") == audio_source_hash and old_audio.get("sha256") == sha256(audio_target) if audio_target.is_file() else False
    convert(audio_source, audio_target, False, audio_reuse)
    records = []
    source_info = probe(audio_source)
    target_info = probe(audio_target)
    source_duration = float(source_info["format"]["duration"])
    target_duration = float(target_info["format"]["duration"])
    if audio_target.stat().st_size >= LIMIT or abs(source_duration - target_duration) > 1.0:
        raise RuntimeError("Chinese streaming audio exceeds 25 MiB or changes duration")
    if not any(stream["codec_type"] == "audio" for stream in target_info["streams"]):
        raise RuntimeError("Chinese streaming audio has no audio stream")
    records.append({
        "kind": "audio", "source": str(audio_source.relative_to(WORKSPACE)),
        "source_sha256": audio_source_hash,
        "path": str(audio_target.relative_to(WORKSPACE)), "bytes": audio_target.stat().st_size,
        "sha256": sha256(audio_target), "duration_seconds": target_duration,
    })

    for language in ("zh", "en"):
        source = VIDEO_SOURCE / f"meaning_intelligence_{language}.mp4"
        target = PACKAGE / "assets" / "video" / "release" / f"meaning_intelligence_{language}-web.mp4"
        source_hash = sha256(source)
        old_video = previous.get(str(target.relative_to(WORKSPACE)), {})
        reuse = old_video.get("source_sha256") == source_hash and old_video.get("sha256") == sha256(target) if target.is_file() else False
        convert(source, target, True, reuse)
        source_info = probe(source)
        target_info = probe(target)
        source_duration = float(source_info["format"]["duration"])
        target_duration = float(target_info["format"]["duration"])
        video = next(stream for stream in target_info["streams"] if stream["codec_type"] == "video")
        audio = [stream for stream in target_info["streams"] if stream["codec_type"] == "audio"]
        subtitles = [stream for stream in target_info["streams"] if stream["codec_type"] == "subtitle"]
        subtitle_languages = {stream.get("tags", {}).get("language") for stream in subtitles}
        if target.stat().st_size >= LIMIT:
            raise RuntimeError(f"{language} streaming video exceeds 25 MiB: {target.stat().st_size}")
        if abs(source_duration - target_duration) > 0.2 or target_duration <= 120:
            raise RuntimeError(f"{language} streaming video duration mismatch or below 120 seconds")
        if (video.get("width"), video.get("height")) != (1280, 720) or not audio:
            raise RuntimeError(f"{language} streaming video dimensions/audio invalid")
        if not {"zho", "eng"} <= subtitle_languages:
            raise RuntimeError(f"{language} streaming video lost subtitle languages: {subtitle_languages}")
        records.append({
            "kind": "video", "language": language, "source": str(source.relative_to(WORKSPACE)),
            "source_sha256": source_hash,
            "path": str(target.relative_to(WORKSPACE)), "bytes": target.stat().st_size,
            "sha256": sha256(target), "duration_seconds": target_duration,
            "width": video.get("width"), "height": video.get("height"),
            "frame_rate": video.get("avg_frame_rate"), "subtitle_languages": sorted(subtitle_languages),
        })

    if records[1]["sha256"] == records[2]["sha256"]:
        raise RuntimeError("Chinese and English streaming videos unexpectedly match")
    report = {
        "schema": "meaning-intelligence-web-media-verification-v1",
        "ok": True, "platform_file_limit_bytes": LIMIT, "masters_modified": False,
        "note": "720p H.264/AAC streaming derivatives and 80 kb/s mono Chinese speech; local masters remain unchanged.",
        "records": records,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "records": len(records), "report": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
