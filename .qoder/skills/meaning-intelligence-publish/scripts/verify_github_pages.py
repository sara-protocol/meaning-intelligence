import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    doi_phrases = (
        "意义智能：理论框架、证据设计和验证",
        "Meaning Intelligence: Theoretical Framework, Evidence Design, and Validation",
        "10.17605/OSF.IO/3XKGY", 'name="citation_doi"',
        'id="mi-project-identifier"', "registration=false", "preprint=false",
    )
    checks = {
        "/": (("意义智能", "audio", "downloads.html", "mcp.html", *doi_phrases), {"btnEn", "btnZh"}),
        "/listen.html": (("audio", "subtitles", "数学模型", "预注册假设，数据收集中", *doi_phrases), {"btnEn", "btnZh"}),
        "/downloads.html": (("下载中心", "manifest", "download", *doi_phrases), {"btnEn", "btnZh"}),
        "/project-guide/index.html": (("language-toggle", "chapter-select", "narration", "content.js", "verification.js", 'id="project-identifier-note"'), {"language-toggle", "chapter-select"}),
        "/mcp.html": (("MCP", "/api/mcp", *doi_phrases), {"lang-en", "lang-zh"}),
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


def hash_fingerprint(site, entries):
    payload = json.dumps({
        "site_url": site,
        "entries": [
            {"path": entry["path"], "bytes": entry["bytes"], "sha256": entry["sha256"]}
            for entry in entries
        ],
    }, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_hash_cache(path, fingerprint):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if payload.get("fingerprint") != fingerprint or not isinstance(payload.get("results"), dict):
        return {}
    return payload["results"]


def save_hash_cache(path, fingerprint, results):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fingerprint": fingerprint,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def verify_hashes_parallel(site, entries, failures, cache_path, batch_size=None):
    fingerprint = hash_fingerprint(site, entries)
    cached = load_hash_cache(cache_path, fingerprint)

    def fetch(entry):
        session = requests.Session()
        session.trust_env = False
        session.headers.update({"User-Agent": "meaning-intelligence-github-pages-verify/1.0", "Accept-Encoding": "identity"})
        path = entry["path"]
        try:
            with session.get(verify.url(site, path), timeout=180, stream=True) as response:
                if response.status_code != 200:
                    return path, False, f"HTTP {response.status_code}", None, None
                length = response.headers.get("content-length")
                if length is not None and int(length) != entry["bytes"]:
                    return path, False, f"Content-Length {length} != {entry['bytes']}", None, None
                digest, total = verify.digest_stream(response, entry["bytes"])
            ok = total == entry["bytes"] and digest == entry["sha256"]
            return path, ok, f"{total} bytes", total, digest
        except Exception as exc:
            return path, False, verify.safe_error(exc), None, None
        finally:
            session.close()

    pending = []
    for entry in entries:
        record = cached.get(entry["path"])
        if (
            isinstance(record, dict)
            and record.get("status") == "pass"
            and record.get("bytes") == entry["bytes"]
            and record.get("sha256") == entry["sha256"]
        ):
            verify.result(failures, f"hash {entry['path']}", True, f"cached {record['bytes']} bytes")
        else:
            pending.append(entry)
    if batch_size is not None:
        pending = pending[:batch_size]

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch, entry): entry for entry in pending}
        for future in as_completed(futures):
            path, ok, detail, total, digest = future.result()
            verify.result(failures, f"hash {path}", ok, detail)
            if ok:
                cached[path] = {
                    "status": "pass",
                    "bytes": total,
                    "sha256": digest,
                    "verified_utc": datetime.now(timezone.utc).isoformat(),
                }
                save_hash_cache(cache_path, fingerprint, cached)

    passed_paths = {
        path for path, record in cached.items()
        if isinstance(record, dict) and record.get("status") == "pass"
    }
    return sum(1 for entry in entries if entry["path"] not in passed_paths)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("site_url")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("github-pages-static-verification.json"))
    parser.add_argument("--cache", type=Path, help="逐文件哈希缓存；默认位于输出 JSON 旁")
    parser.add_argument("--batch-size", type=int, help="本次最多下载并哈希的文件数；未完成项保留到下次")
    args = parser.parse_args()
    if args.batch_size is not None and args.batch_size < 1:
        parser.error("--batch-size 必须大于 0")
    cache_path = args.cache or args.output.with_name(args.output.stem + "-hash-cache.json")
    site = args.site_url.rstrip("/")
    if not site.startswith(("http://", "https://")):
        raise SystemExit("site_url must use HTTP or HTTPS")
    failures = []
    hash_pending = 0
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        _, entries = verify.load_manifest(args.manifest.resolve())
        hash_pending = len(entries)
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
            hash_pending = verify_hashes_parallel(site, entries, failures, cache_path, args.batch_size)
            if hash_pending:
                verify.result(failures, "hash-verification-complete", False, f"{hash_pending} pending")
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
        "full_get_integrity_verified": hash_pending == 0 and len([line for line in passed if line.strip().startswith("hash ")]) == len(entries),
        "hash_cache": str(cache_path),
        "hash_pending": hash_pending,
        "media_metadata_verified": len([line for line in passed if line.strip().startswith("media ")]) == len(verify.WEB_MEDIA),
        "range_supported": range_supported,
        "range_samples": range_samples,
        "range_note": "Range behavior is recorded from live responses. Full GET byte counts and SHA-256 hashes are verified independently; HTTP 206 remains required for Cloudflare deployment verification.",
        "mcp_function_verified": False,
        "mcp_endpoint_http_status": mcp_status,
        "mcp_note": "GitHub Pages serves static assets only; the Cloudflare Pages Function remains a separate production surface.",
        "evidence": str(MODULE_PATH),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("site_url", "static_ok", "checks_passed", "checks_total", "manifest_entries", "hash_pending", "mcp_endpoint_http_status", "failed")}, ensure_ascii=False, indent=2))
    sys.exit(0 if report["static_ok"] else 1)


if __name__ == "__main__":
    main()
