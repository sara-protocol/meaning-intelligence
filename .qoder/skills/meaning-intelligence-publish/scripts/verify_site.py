#!/usr/bin/env python3
"""Read-only verification of a deployed Meaning Intelligence Cloudflare Pages site.

The expected resources come from a deployment manifest, never from an assumed
online complete-package ZIP. MI_MCP_PUBLIC_TOKEN is read only from the environment
and is never printed. Dynamic browser behavior is covered separately by
browser_verify.mjs; this script validates HTTP, content, hashes, ranges, media,
and the authenticated read-only MCP boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

import requests

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = WORKSPACE / "deliverables" / "meaning-intelligence-deploy-staging" / "download" / "manifest.json"
MAX_FILE_BYTES = 25 * 1024 * 1024
PAGES = [
    "/", "/listen.html", "/downloads.html", "/mcp.html", "/project-guide/index.html",
    "/subtitles.json", "/subtitles_en.json", "/subtitles_zh.vtt", "/subtitles_en.vtt",
    "/timeline_en.json", "/download/manifest.json",
]
WEB_MEDIA = {
    "assets/audio-web.mp3": "audio",
    "assets/video/release/meaning_intelligence_zh-web.mp4": "video",
    "assets/video/release/meaning_intelligence_en-web.mp4": "video",
}
FORBIDDEN_PATHS = {
    "assets/audio.mp3",
    "assets/video/release/meaning_intelligence_zh.mp4",
    "assets/video/release/meaning_intelligence_en.mp4",
    "project-guide/downloads/meaning-intelligence-zh.mp4",
    "project-guide/downloads/meaning-intelligence-en.mp4",
}
MCP_TOOLS = {
    "meaning_analyze", "meaning_review", "resource_catalog", "evidence_levels", "download_manifest",
}
MCP_RESOURCES = {
    "mi://canon/v7", "mi://evidence/e0-e6", "mi://chapters/zh", "mi://chapters/en",
    "mi://skills/l1-l6", "mi://downloads",
}
MCP_SECURITY_HEADERS = {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.langs: list[str] = []
        self.refs: list[str] = []
        self.scripts: list[str] = []
        self._script_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag.lower() == "html" and values.get("lang"):
            self.langs.append(values["lang"])
        if values.get("id"):
            self.ids.add(values["id"])
        for key in ("src", "href", "poster"):
            if values.get(key):
                self.refs.append(values[key])
        if tag.lower() == "script":
            self._script_depth += 1
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._script_depth:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._script_depth:
            self._script_depth -= 1
            self.scripts.append("".join(self._chunks))


def url(site: str, path: str) -> str:
    return site + "/" + quote(path.lstrip("/"), safe="/%:@!$&'()*+,;=-._~")


def safe_error(exc: BaseException, token: str = "") -> str:
    text = f"{type(exc).__name__}: {exc}"
    if token:
        text = text.replace(token, "<redacted>")
    return text[:240]


def result(failures: list[str], name: str, ok: bool, detail: str = "") -> bool:
    if ok:
        print(f"OK   {name}" + (f": {detail}" if detail else ""))
    else:
        message = f"{name}: {detail}" if detail else name
        failures.append(message)
        print(f"FAIL {message}")
    return ok


def validate_manifest(data: object, source: str) -> list[dict]:
    if not isinstance(data, dict):
        raise ValueError(f"{source}: manifest 必须是对象")
    if data.get("complete_package"):
        raise ValueError(f"{source}: deployment manifest 仍含 complete_package 字段")
    deployment = data.get("deployment")
    if isinstance(deployment, dict) and deployment.get("complete_package_included") is not False:
        raise ValueError(f"{source}: deployment manifest 未明确排除完整包")
    entries = data.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{source}: files 必须是非空数组")
    seen: set[str] = set()
    validated: list[dict] = []
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ValueError(f"{source}: files[{index}] 必须是对象")
        rel = entry.get("path")
        if not isinstance(rel, str) or not rel:
            raise ValueError(f"{source}: files[{index}] 路径无效")
        pure = PurePosixPath(rel)
        if pure.is_absolute() or ".." in pure.parts or "\\" in rel or pure.as_posix() != rel:
            raise ValueError(f"{source}: 不安全路径 {rel!r}")
        if rel in seen:
            raise ValueError(f"{source}: 重复路径 {rel}")
        seen.add(rel)
        size = entry.get("bytes")
        digest = entry.get("sha256")
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise ValueError(f"{source}: {rel} 字节数无效")
        if size > MAX_FILE_BYTES:
            raise ValueError(f"{source}: {rel} 超过 25 MiB ({size} bytes)")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"{source}: {rel} SHA-256 无效")
        if entry.get("category") == "package" or rel in FORBIDDEN_PATHS:
            raise ValueError(f"{source}: 仍含本地完整包或原始超大媒体 {rel}")
        if rel.startswith("project-guide/downloads/") and rel.lower().endswith(".mp4") and "1080p" in rel.lower():
            raise ValueError(f"{source}: 仍含 1080p guide 视频副本 {rel}")
        if rel.startswith("download/") and rel.lower().endswith(".zip") and "完整交付包" in PurePosixPath(rel).name:
            raise ValueError(f"{source}: 仍含完整交付 ZIP {rel}")
        validated.append(entry)
    missing = set(WEB_MEDIA) - seen
    if missing:
        raise ValueError(f"{source}: 缺少网页音视频派生资源 {sorted(missing)}")
    return validated


def load_manifest(path: Path) -> tuple[dict, list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, validate_manifest(data, str(path))


def local_reference(ref: str) -> str | None:
    parsed = urlsplit(ref)
    if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("#"):
        return None
    target = unquote(parsed.path)
    if target in ("", "/"):
        return "index.html"
    if target == "/api/mcp":
        return None
    return target.lstrip("/")


def fetch_online_manifest(session: requests.Session, site: str, failures: list[str]) -> tuple[dict, list[dict]]:
    try:
        with session.get(url(site, "download/manifest.json"), timeout=60, stream=True) as response:
            if response.status_code != 200:
                raise ValueError(f"HTTP {response.status_code}")
            length = response.headers.get("content-length")
            if length is not None and int(length) > 1024 * 1024:
                raise ValueError("online manifest 超过 1 MiB")
            chunks = []
            total = 0
            for chunk in response.iter_content(64 * 1024):
                total += len(chunk)
                if total > 1024 * 1024:
                    raise ValueError("online manifest 超过 1 MiB")
                chunks.append(chunk)
            data = json.loads(b"".join(chunks).decode("utf-8"))
        entries = validate_manifest(data, "online download/manifest.json")
        result(failures, "online-deployment-manifest", True, f"{len(entries)} entries")
        return data, entries
    except Exception as exc:
        result(failures, "online-deployment-manifest", False, safe_error(exc))
        return {}, []


def verify_html(session: requests.Session, site: str, failures: list[str]) -> tuple[dict[str, str], set[str]]:
    texts: dict[str, str] = {}
    references: set[str] = set()
    checks = {
        "/": ("视听中心", "listen.html", "downloads.html", "project-guide/index.html", "mcp.html"),
        "/listen.html": ("audio", "subtitles", "数学模型", "预注册假设，数据收集中", "btnEn"),
        "/downloads.html": ("下载中心", "manifest", "download"),
        "/project-guide/index.html": ("project-guide", "language-toggle", "chapter-select", "narration", "GUIDE_CONTENT"),
        "/mcp.html": ("MCP", "/api/mcp"),
    }
    controls = {
        "/": {"btnEn", "btnZh"},
        "/listen.html": {"btnEn", "btnZh"},
        "/downloads.html": {"btnEn", "btnZh"},
        "/project-guide/index.html": {"language-toggle", "chapter-select"},
        "/mcp.html": {"lang-en", "lang-zh"},
    }
    for path, phrases in checks.items():
        try:
            with session.get(url(site, path), timeout=60) as response:
                text = response.text
                content_type = response.headers.get("content-type", "").lower()
                if response.status_code != 200 or "text/html" not in content_type:
                    result(failures, f"content {path}", False, f"HTTP {response.status_code}; {content_type}")
                    continue
                texts[path] = text
                parser = PageParser()
                parser.feed(text)
                missing = [phrase for phrase in phrases if phrase.lower() not in text.lower()]
                missing_controls = sorted(controls.get(path, set()) - parser.ids)
                valid_lang = bool(parser.langs) and parser.langs[0].lower().startswith(("zh", "en"))
                ok = not missing and not missing_controls and valid_lang
                result(failures, f"content {path}", ok, f"missing={missing}, controls={missing_controls}, lang={parser.langs[:1]}")
                for ref in parser.refs:
                    target = local_reference(ref)
                    if target:
                        references.add(target)
        except Exception as exc:
            result(failures, f"content {path}", False, safe_error(exc))
    listen = texts.get("/listen.html")
    if listen is not None:
        parser = PageParser()
        parser.feed(listen)
        scripts = "\n".join(parser.scripts)
        evidence = all(path in scripts for path in WEB_MEDIA if path.endswith(".mp3")) and "assets_en/audio_en.mp3" in scripts
        evidence = evidence and bool(re.search(r"audio\.src\s*=\s*BI\.i18n\[[^\]]+\]\.audio", scripts))
        result(failures, "bilingual-audio-static-switching-evidence", evidence, "dynamic execution is checked by browser_verify.mjs")
    downloads = texts.get("/downloads.html")
    if downloads is not None:
        lowered = downloads.lower()
        no_complete = "意义智能完整交付包" not in downloads and "meaning intelligence complete delivery package" not in lowered
        no_complete = no_complete and not any(path in lowered for path in FORBIDDEN_PATHS)
        derivatives = all(path in downloads for path in WEB_MEDIA)
        result(failures, "downloads-deployment-cards", no_complete and derivatives, "complete card absent; three web derivatives linked")
    return texts, references


def verify_head_resources(session: requests.Session, site: str, paths: set[str], expected: dict[str, dict], failures: list[str]) -> None:
    for path in sorted(paths):
        try:
            with session.head(url(site, path), timeout=60, allow_redirects=True) as response:
                if response.status_code != 200:
                    result(failures, f"HEAD {path}", False, f"HTTP {response.status_code}")
                    continue
                length = response.headers.get("content-length")
                if length is not None:
                    try:
                        actual = int(length)
                    except ValueError:
                        result(failures, f"HEAD {path}", False, "invalid Content-Length")
                        continue
                    if path in expected and actual != expected[path]["bytes"]:
                        result(failures, f"HEAD {path}", False, f"Content-Length {actual} != {expected[path]['bytes']}")
                        continue
                    if actual <= 0:
                        result(failures, f"HEAD {path}", False, "empty body")
                        continue
                result(failures, f"HEAD {path}", True)
        except Exception as exc:
            result(failures, f"HEAD {path}", False, safe_error(exc))


def digest_stream(response: requests.Response, maximum: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    for chunk in response.iter_content(1024 * 1024):
        total += len(chunk)
        if total > maximum:
            raise ValueError(f"response exceeded expected maximum {maximum} bytes")
        digest.update(chunk)
    return digest.hexdigest(), total


def verify_hashes(session: requests.Session, site: str, entries: list[dict], failures: list[str]) -> None:
    for entry in entries:
        path = entry["path"]
        try:
            with session.get(url(site, path), timeout=180, stream=True) as response:
                if response.status_code != 200:
                    result(failures, f"hash {path}", False, f"HTTP {response.status_code}")
                    continue
                length = response.headers.get("content-length")
                if length is not None and int(length) != entry["bytes"]:
                    result(failures, f"hash {path}", False, f"Content-Length {length} != {entry['bytes']}")
                    continue
                digest, total = digest_stream(response, entry["bytes"])
            ok = total == entry["bytes"] and digest == entry["sha256"]
            result(failures, f"hash {path}", ok, f"{total} bytes")
        except Exception as exc:
            result(failures, f"hash {path}", False, safe_error(exc))


def verify_ranges(session: requests.Session, site: str, entries: list[dict], failures: list[str]) -> None:
    expected = {entry["path"]: entry for entry in entries}
    for path in sorted(expected):
        entry = expected[path]
        end = min(1023, entry["bytes"] - 1)
        try:
            with session.get(url(site, path), headers={"Range": "bytes=0-1023"}, timeout=90, stream=True) as response:
                content_range = response.headers.get("content-range", "")
                match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range)
                valid = response.status_code == 206 and match is not None
                valid = valid and tuple(map(int, match.groups())) == (0, end, entry["bytes"])
                length = response.headers.get("content-length")
                if length is not None:
                    valid = valid and int(length) == end + 1
                total = sum(len(chunk) for chunk in response.iter_content(16 * 1024))
                valid = valid and total == end + 1
            result(failures, f"range {path}", valid, f"HTTP {response.status_code}; {content_range}")
        except Exception as exc:
            result(failures, f"range {path}", False, safe_error(exc))


def verify_media(site: str, failures: list[str]) -> None:
    executable = shutil.which("ffprobe")
    if not executable:
        result(failures, "deep-media-ffprobe", False, "ffprobe not found")
        return
    for path, kind in WEB_MEDIA.items():
        try:
            command = [
                executable, "-v", "error", "-rw_timeout", "18000000", "-show_entries",
                "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate:stream_tags=language",
                "-of", "json", url(site, path),
            ]
            probe = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
            if probe.returncode:
                raise RuntimeError((probe.stderr or probe.stdout).strip()[-500:])
            info = json.loads(probe.stdout)
            duration = float(info.get("format", {}).get("duration", 0))
            streams = info.get("streams", [])
            audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
            video = [stream for stream in streams if stream.get("codec_type") == "video"]
            subtitles = [stream for stream in streams if stream.get("codec_type") == "subtitle"]
            if kind == "audio":
                ok = duration > 120 and bool(audio)
                detail = f"duration={duration:.3f}s; audio_streams={len(audio)}"
            else:
                languages = {stream.get("tags", {}).get("language") for stream in subtitles}
                dimensions = (video[0].get("width"), video[0].get("height")) if video else None
                ok = duration > 120 and bool(audio) and dimensions == (1280, 720) and {"zho", "eng"} <= languages
                ok = ok and bool(video) and video[0].get("codec_name") == "h264" and any(stream.get("codec_name") == "aac" for stream in audio)
                detail = f"duration={duration:.3f}s; video={dimensions}; audio={len(audio)}; subtitles={sorted(languages)}"
            result(failures, f"media {path}", ok, detail)
        except Exception as exc:
            result(failures, f"media {path}", False, safe_error(exc))


def rpc(session: requests.Session, site: str, method: str, params=None, token: str = "", request_id: int = 1, *, raw: str | None = None, content_type: str = "application/json", notification: bool = False) -> tuple[int, dict, dict, str]:
    if raw is None:
        payload = {"jsonrpc": "2.0", "method": method}
        if not notification:
            payload["id"] = request_id
        if params is not None:
            payload["params"] = params
        raw = json.dumps(payload, ensure_ascii=False)
    headers = {"Content-Type": content_type, "Origin": site}
    if token:
        headers["Authorization"] = "Bearer " + token
    with session.post(url(site, "api/mcp"), data=raw.encode("utf-8"), headers=headers, timeout=60) as response:
        text = response.text
        try:
            data = response.json()
        except Exception:
            data = {}
        return response.status_code, data if isinstance(data, dict) else {}, dict(response.headers), text


def check_security_headers(headers: dict, name: str, failures: list[str]) -> None:
    missing = [key for key, value in MCP_SECURITY_HEADERS.items() if headers.get(key, "").lower() != value.lower()]
    result(failures, f"security-headers {name}", not missing, f"missing={missing}")


def tool_result(data: dict) -> dict:
    payload = data.get("result", {})
    structured = payload.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    content = payload.get("content", [])
    if content and isinstance(content[0], dict) and isinstance(content[0].get("text"), str):
        try:
            value = json.loads(content[0]["text"])
            return value if isinstance(value, dict) else {}
        except ValueError:
            return {}
    return {}


def verify_mcp(session: requests.Session, site: str, failures: list[str], token: str, online_manifest: dict, probe_rate_limit: bool) -> None:
    endpoint = url(site, "api/mcp")
    try:
        with session.options(endpoint, headers={
            "Origin": site, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        }, timeout=60) as response:
            headers = dict(response.headers)
            ok = response.status_code == 204 and headers.get("access-control-allow-origin") == site
            ok = ok and "POST" in headers.get("access-control-allow-methods", "") and "authorization" in headers.get("access-control-allow-headers", "").lower()
            result(failures, "MCP CORS preflight", ok, f"HTTP {response.status_code}")
            check_security_headers(headers, "preflight", failures)
        with session.options(endpoint, headers={
            "Origin": "https://invalid.example", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        }, timeout=60) as response:
            result(failures, "MCP invalid-origin denied", response.status_code == 403 and not response.headers.get("access-control-allow-origin"), f"HTTP {response.status_code}")
    except Exception as exc:
        result(failures, "MCP preflight", False, safe_error(exc, token))
    for method in ("GET", "HEAD", "PUT", "DELETE"):
        try:
            with session.request(method, endpoint, timeout=60) as response:
                ok = response.status_code == 405 and "POST" in response.headers.get("allow", "") and "OPTIONS" in response.headers.get("allow", "")
                result(failures, f"MCP wrong-method {method}", ok, f"HTTP {response.status_code}")
                check_security_headers(dict(response.headers), method, failures)
        except Exception as exc:
            result(failures, f"MCP wrong-method {method}", False, safe_error(exc, token))
    initialize_params = {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "verify-site", "version": "2.0"}}
    status, data, headers, _ = rpc(session, site, "initialize", initialize_params)
    check_security_headers(headers, "unauthorized-initialize", failures)
    if not token:
        ok = status == 401 and headers.get("www-authenticate") == "Bearer"
        result(failures, "MCP unauthenticated denied", ok, f"HTTP {status}")
        print("SKIP MCP authenticated resources/tools/oversize/content-type/rate-limit: MI_MCP_PUBLIC_TOKEN not set (token never printed)")
        return
    status, data, headers, text = rpc(session, site, "initialize", initialize_params, token)
    check_security_headers(headers, "initialize", failures)
    initialized = data.get("result", {})
    ok = status == 200 and initialized.get("protocolVersion") == "2025-03-26"
    ok = ok and initialized.get("serverInfo", {}).get("name") == "meaning-intelligence-web-mcp"
    ok = ok and "read-only" in initialized.get("instructions", "").lower()
    if not result(failures, "MCP initialize", ok, f"HTTP {status}"):
        return
    status, data, _, _ = rpc(session, site, "notifications/initialized", notification=True, token=token)
    result(failures, "MCP initialized-notification", status == 202 and not data, f"HTTP {status}")
    status, data, _, _ = rpc(session, site, "tools/list", {}, token, 2)
    tools = data.get("result", {}).get("tools", []) if status == 200 else []
    names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
    annotations_ok = all(tool.get("annotations", {}).get("readOnlyHint") is True and tool.get("annotations", {}).get("destructiveHint") is False for tool in tools)
    result(failures, "MCP tools/list read-only", status == 200 and names == MCP_TOOLS and annotations_ok, f"{sorted(names)}")
    status, data, _, _ = rpc(session, site, "resources/list", {}, token, 3)
    resources = data.get("result", {}).get("resources", []) if status == 200 else []
    uris = {resource.get("uri") for resource in resources if isinstance(resource, dict)}
    result(failures, "MCP resources/list", status == 200 and uris == MCP_RESOURCES, f"{len(uris)} resources")
    for uri in sorted(MCP_RESOURCES):
        status, data, _, _ = rpc(session, site, "resources/read", {"uri": uri}, token, 4)
        contents = data.get("result", {}).get("contents", []) if status == 200 else []
        ok = status == 200 and len(contents) == 1 and contents[0].get("uri") == uri and contents[0].get("mimeType") == "application/json"
        if ok:
            try:
                value = json.loads(contents[0]["text"])
                ok = isinstance(value, dict) and bool(value)
            except Exception:
                ok = False
        result(failures, f"MCP resource {uri}", ok, f"HTTP {status}")
    for uri in ("file:///etc/passwd", "https://invalid.example/secret", "mi://../../etc/passwd"):
        status, data, _, _ = rpc(session, site, "resources/read", {"uri": uri}, token, 5)
        result(failures, "MCP arbitrary-resource denied", status == 200 and data.get("error", {}).get("code") == -32002, uri)
    status, data, _, _ = rpc(session, site, "resources/write", {"uri": "mi://canon/v7"}, token, 6)
    result(failures, "MCP write-method denied", status == 200 and data.get("error", {}).get("code") == -32601, f"HTTP {status}")
    calls = [
        ("meaning_analyze", {"text": "这个方案帮助我澄清目标，但需要可证伪的验证标准。", "language": "zh"}),
        ("meaning_review", {"previous": {"approval": {"status": "pending"}}, "feedback": "请复核边界，不自动批准。", "language": "zh"}),
        ("resource_catalog", {}), ("evidence_levels", {}), ("download_manifest", {}),
    ]
    for request_id, (name, arguments) in enumerate(calls, 10):
        status, data, _, _ = rpc(session, site, "tools/call", {"name": name, "arguments": arguments}, token, request_id)
        payload = data.get("result", {}) if status == 200 else {}
        ok = status == 200 and payload.get("isError") is False
        value = tool_result(data)
        if name in {"meaning_analyze", "meaning_review"}:
            ok = ok and value.get("mode", "offline") == "offline" and value.get("approval") == {"required": True, "status": "pending"}
        if name == "meaning_analyze":
            ok = ok and value.get("L4", {}).get("assigned_level") == "E0"
        if name == "meaning_review":
            ok = ok and value.get("evidence_level_changed") is False
        if name == "evidence_levels":
            ok = ok and len(value.get("levels", [])) == 7
        if name == "resource_catalog":
            ok = ok and value.get("canon", {}).get("version") == "V7.0" and len(value.get("resources", [])) == 6
        if name == "download_manifest":
            ok = ok and value.get("files") == online_manifest.get("files")
        result(failures, f"MCP tool {name}", ok, f"HTTP {status}")
    status, data, _, _ = rpc(session, site, "tools/call", {"name": "delete_everything", "arguments": {}}, token, 20)
    result(failures, "MCP unknown-tool denied", status == 200 and data.get("error", {}).get("code") == -32602, f"HTTP {status}")
    oversized = json.dumps({"jsonrpc": "2.0", "id": 21, "method": "ping", "params": {"padding": "x" * 33000}})
    status, data, headers, _ = rpc(session, site, "ping", token=token, request_id=21, raw=oversized)
    result(failures, "MCP oversize-body denied", status == 413 and data.get("error", {}).get("message") == "request too large", f"HTTP {status}")
    check_security_headers(headers, "oversize", failures)
    status, data, _, _ = rpc(session, site, "ping", token=token, content_type="text/plain")
    result(failures, "MCP wrong-content-type denied", status == 415, f"HTTP {status}")
    if probe_rate_limit:
        limited = False
        attempts = 0
        for request_id in range(30, 100):
            attempts += 1
            status, data, headers, _ = rpc(session, site, "ping", token=token, request_id=request_id)
            if status == 429:
                retry = headers.get("retry-after", "")
                limited = retry.isdigit() and int(retry) > 0
                break
        result(failures, "MCP rate-limit 429", limited, f"{attempts} requests; Retry-After={headers.get('retry-after', '')}")
    else:
        print("SKIP MCP rate-limit trigger: use --mcp-rate-limit to send more than 60 authenticated requests")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site_url", nargs="?", default="https://msi-5e5.pages.dev")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=f"deployment manifest (default: {DEFAULT_MANIFEST})")
    parser.add_argument("--deep", action="store_true", help="hash every download, verify byte ranges, and ffprobe web audio/video")
    parser.add_argument("--mcp-rate-limit", action="store_true", help="with a token, trigger the MCP 60/minute limit using more than 60 requests")
    args = parser.parse_args()
    site = args.site_url.rstrip("/")
    parsed = urlsplit(site)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        print("FAIL site_url 必须是完整 HTTP(S) URL，且不能包含凭据")
        return 1
    token = os.environ.get("MI_MCP_PUBLIC_TOKEN", "")
    failures: list[str] = []
    try:
        _, entries = load_manifest(args.manifest.resolve())
        print(f"OK   local deployment manifest: {args.manifest.resolve()} ({len(entries)} entries)")
    except Exception as exc:
        print(f"FAIL local deployment manifest: {safe_error(exc)}")
        return 1
    expected = {entry["path"]: entry for entry in entries}
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": "meaning-intelligence-verify-site/2.0", "Accept-Encoding": "identity"})
    try:
        _, references = verify_html(session, site, failures)
        online_manifest, online_entries = fetch_online_manifest(session, site, failures)
        local_resources = sorted((entry["path"], entry["bytes"], entry["sha256"]) for entry in entries)
        online_resources = sorted((entry["path"], entry["bytes"], entry["sha256"]) for entry in online_entries)
        result(failures, "online-manifest-matches-deployment", bool(online_entries) and local_resources == online_resources, f"local={len(entries)}, online={len(online_entries)}")
        paths = set(PAGES) | set(expected) | references
        verify_head_resources(session, site, paths, expected, failures)
        if args.deep:
            verify_hashes(session, site, entries, failures)
            verify_ranges(session, site, entries, failures)
            verify_media(site, failures)
        else:
            print("SKIP download hashes, byte ranges, and media stream/duration checks: use --deep")
        verify_mcp(session, site, failures, token, online_manifest, args.mcp_rate_limit)
    except Exception as exc:
        failures.append(safe_error(exc, token))
        print(f"FAIL {safe_error(exc, token)}")
    finally:
        session.close()
    print(f"范围: deployment manifest；HTML 语言控件；静态双语音轨切换证据；HTTP 资源；MCP 只读边界")
    print("SKIP dynamic browser interactions: run browser_verify.mjs against local staging or with --online")
    print(f"模式: deep={args.deep}; authenticated_mcp={bool(token)}; rate_limit_probe={bool(token) and args.mcp_rate_limit}; token 从不输出")
    if failures:
        print(f"线上验证未通过: {len(failures)} 项")
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print(f"全部通过: {site}（manifest {len(entries)} 项；deep={args.deep}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
