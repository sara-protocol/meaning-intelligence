import argparse
import contextlib
import importlib.util
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
MODULE_PATH = Path(__file__).with_name("verify_site.py")
spec = importlib.util.spec_from_file_location("verify_site", MODULE_PATH)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def verify_pages_html(session, site, failures):
    texts = {}
    references = set()
    checks = {
        "/": (("意义智能", "audio", "downloads.html", "mcp.html"), {"btnEn", "btnZh"}),
        "/listen.html": (("audio", "subtitles", "数学模型", "预注册假设，数据收集中"), {"btnEn", "btnZh"}),
        "/downloads.html": (("下载中心", "manifest", "download"), {"btnEn", "btnZh"}),
        "/project-guide/index.html": (("language-toggle", "chapter-select", "narration", "content.js", "verification.js"), {"language-toggle", "chapter-select"}),
        "/mcp.html": (("MCP", "/api/mcp"), {"lang-en", "lang-zh"}),
    }
    for path, (phrases, controls) in checks.items():
        try:
            with session.get(verify.url(site, path), timeout=60) as response:
                content_type = response.headers.get("content-type", "").lower()
                text = response.content.decode("utf-8")
                if response.status_code != 200 or "text/html" not in content_type:
                    verify.result(failures, f"content {path}", False, f"HTTP {response.status_code}; {content_type}")
                    continue
                texts[path] = text
                parser = verify.PageParser()
                parser.feed(text)
                missing = [phrase for phrase in phrases if phrase.lower() not in text.lower()]
                missing_controls = sorted(controls - parser.ids)
                valid_lang = bool(parser.langs) and parser.langs[0].lower().startswith(("zh", "en"))
                verify.result(failures, f"content {path}", not missing and not missing_controls and valid_lang, f"missing={missing}, controls={missing_controls}, lang={parser.langs[:1]}")
                page_url = verify.url(site, path.lstrip("/") or "index.html")
                for ref in parser.refs:
                    parsed = urlsplit(ref)
                    if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("#"):
                        continue
                    if parsed.path == "/api/mcp":
                        continue
                    target = unquote(urlsplit(urljoin(page_url, ref)).path).lstrip("/") or "index.html"
                    references.add(target)
        except Exception as exc:
            verify.result(failures, f"content {path}", False, verify.safe_error(exc))
    listen = texts.get("/listen.html")
    if listen is not None:
        parser = verify.PageParser()
        parser.feed(listen)
        scripts = "\n".join(parser.scripts)
        evidence = all(path in listen for path in verify.WEB_MEDIA if path.endswith(".mp3")) and "assets_en/audio_en.mp3" in listen
        evidence = evidence and bool(verify.re.search(r"audio\.src\s*=\s*BI\.i18n\[[^\]]+\]\.audio", scripts))
        verify.result(failures, "bilingual-audio-static-switching-evidence", evidence, "dynamic execution is checked by browser_verify.mjs")
    downloads = texts.get("/downloads.html")
    if downloads is not None:
        lowered = downloads.lower()
        no_complete = "意义智能完整交付包" not in downloads and "meaning intelligence complete delivery package" not in lowered
        no_complete = no_complete and not any(path in lowered for path in verify.FORBIDDEN_PATHS)
        derivatives = all(path in downloads for path in verify.WEB_MEDIA)
        verify.result(failures, "downloads-deployment-cards", no_complete and derivatives, "complete card absent; three web derivatives linked")
    return texts, references


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("site_url")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("github-pages-static-verification.json"))
    args = parser.parse_args()
    site = args.site_url.rstrip("/")
    if not site.startswith(("http://", "https://")):
        raise SystemExit("site_url must use HTTP or HTTPS")
    failures = []
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        _, entries = verify.load_manifest(args.manifest.resolve())
        expected = {entry["path"]: entry for entry in entries}
        session = requests.Session()
        session.trust_env = False
        session.headers.update({"User-Agent": "meaning-intelligence-github-pages-verify/1.0", "Accept-Encoding": "identity"})
        try:
            _, references = verify_pages_html(session, site, failures)
            online_manifest, online_entries = verify.fetch_online_manifest(session, site, failures)
            local_resources = sorted((entry["path"], entry["bytes"], entry["sha256"]) for entry in entries)
            online_resources = sorted((entry["path"], entry["bytes"], entry["sha256"]) for entry in online_entries)
            verify.result(failures, "online-manifest-matches-deployment", bool(online_entries) and local_resources == online_resources, f"local={len(entries)}, online={len(online_entries)}")
            paths = set(verify.PAGES) | set(expected) | references
            verify.verify_head_resources(session, site, paths, expected, failures)
            verify.verify_hashes(session, site, entries, failures)
            range_samples = []
            for path in ("download/manifest.json", "assets/audio-web.mp3"):
                try:
                    with session.get(verify.url(site, path), headers={"Range": "bytes=0-1023"}, timeout=90, stream=True) as response:
                        prefix = next(response.iter_content(1024), b"")
                        range_samples.append({
                            "path": path,
                            "status": response.status_code,
                            "content_range": response.headers.get("content-range", ""),
                            "content_length": response.headers.get("content-length", ""),
                            "prefix_bytes_read": len(prefix),
                        })
                except Exception as exc:
                    verify.result(failures, f"range-policy {path}", False, verify.safe_error(exc))
                    range_samples.append({"path": path, "status": None, "error": verify.safe_error(exc)})
            range_supported = bool(range_samples) and all(
                sample.get("status") == 206 and sample.get("content_range", "").startswith("bytes 0-")
                for sample in range_samples
            )
            if range_supported:
                verify.verify_ranges(session, site, entries, failures)
            verify.verify_media(site, failures)
            try:
                mcp_response = session.get(verify.url(site, "api/mcp"), timeout=30, allow_redirects=False)
                mcp_status = mcp_response.status_code
            except Exception as exc:
                mcp_status = None
                verify.result(failures, "MCP endpoint probe", False, verify.safe_error(exc))
        finally:
            session.close()
    lines = [line for line in log.getvalue().splitlines() if line.startswith(("OK ", "FAIL "))]
    passed = [line[4:].strip() for line in lines if line.startswith("OK ")]
    failed = [line[5:].strip() for line in lines if line.startswith("FAIL ")]
    report = {
        "schema": "meaning-intelligence-github-pages-static-verification-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "site_url": site,
        "manifest_path": str(args.manifest.resolve()),
        "static_ok": not failures,
        "checks_passed": len(passed),
        "checks_total": len(lines),
        "passed": passed,
        "failed": failed,
        "manifest_entries": len(entries),
        "full_get_integrity_verified": len([line for line in passed if line.startswith("hash ")]) == len(entries),
        "media_metadata_verified": len([line for line in passed if line.startswith("media ")]) == len(verify.WEB_MEDIA),
        "range_supported": range_supported,
        "range_samples": range_samples,
        "range_note": "GitHub Pages returned full HTTP 200 responses to Range probes. Full GET byte counts and SHA-256 hashes were verified instead; HTTP 206 remains required for Cloudflare deployment verification.",
        "mcp_function_verified": False,
        "mcp_endpoint_http_status": mcp_status,
        "mcp_note": "GitHub Pages serves static assets only; the Cloudflare Pages Function remains a separate production surface.",
        "evidence": str(MODULE_PATH),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("site_url", "static_ok", "checks_passed", "checks_total", "manifest_entries", "full_get_integrity_verified", "media_metadata_verified", "range_supported", "mcp_endpoint_http_status", "failed")}, ensure_ascii=False, indent=2))
    sys.exit(0 if report["static_ok"] else 1)


if __name__ == "__main__":
    main()
