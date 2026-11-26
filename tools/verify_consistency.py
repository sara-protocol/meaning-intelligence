"""CI 一致性检查:版本号 / 根 ROADMAP.md / MIT 缩写 / 证据等级 / hypotheses.yaml。
任何一项失败 → 非零退出码。"""
import re
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")

ROOT = Path(__file__).resolve().parents[1]
failures = []
hypothesis_data = {}


def fail(msg):
    failures.append(msg)
    print(f"::error::{msg}")


def ok(msg):
    print(f"OK   {msg}")


# ---------------------------------------------------------------- 1. VERSION.yaml
v = ROOT / "VERSION.yaml"
if not v.exists():
    fail("VERSION.yaml 不存在")
    print(f"\n共 {len(failures)} 项失败")
    sys.exit(1)

try:
    import yaml
    version_data = yaml.safe_load(v.read_text(encoding="utf-8"))
except Exception as e:
    fail(f"VERSION.yaml 解析失败: {e}")
    print(f"\n共 {len(failures)} 项失败")
    sys.exit(1)

ok("VERSION.yaml 存在")
version = version_data.get("research_system", {}).get("version")
if version:
    ok(f"research_system.version = {version}")
else:
    fail("VERSION.yaml 找不到 research_system.version")

# ---------------------------------------------------------------- 2. README badge
if version:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    badge = re.search(r"badge/version-(\d+\.\d+\.\d+)", readme)
    if not badge:
        fail("README.md 找不到 version badge")
    elif badge.group(1) != version:
        fail(f"README badge ({badge.group(1)}) != VERSION.yaml ({version})")
    else:
        ok(f"README badge 版本一致 = {version}")

# ---------------------------------------------------------------- 3. docs/roadmap.md 当前版本
if version:
    rm = ROOT / "docs" / "roadmap.md"
    if rm.exists():
        rt = rm.read_text(encoding="utf-8")
        m2 = re.search(r"(?:当前版本|Current Release)\s+(\d+\.\d+\.\d+)", rt, re.IGNORECASE)
        if m2 and m2.group(1) != version:
            fail(f"docs/roadmap.md 当前版本 ({m2.group(1)}) != VERSION.yaml ({version})")
        elif m2:
            ok(f"docs/roadmap.md 当前版本一致 = {version}")
        else:
            print("INFO docs/roadmap.md 无'当前版本'标记,跳过")

# ---------------------------------------------------------------- 4. 根 ROADMAP.md 有效
root_rm = ROOT / "ROADMAP.md"
if root_rm.exists():
    t = root_rm.read_text(encoding="utf-8")
    if len(t) < 100 or "notepad" in t.lower() or "文件 2" in t:
        fail(f"根 ROADMAP.md 内容异常 (长度 {len(t)})")
    else:
        ok(f"根 ROADMAP.md 有效 ({len(t)} 字符)")

# ---------------------------------------------------------------- 5. MIT 缩写不冲突
readme = (ROOT / "README.md").read_text(encoding="utf-8")
if re.search(r"\bMIT\b(?!\s*[Ll]icense)", readme) and re.search(r"MIT [Ll]icense", readme):
    stray_mit = re.findall(r"\bMIT\b(?!\s*[Ll]icense)(?!\s*Theory)", readme)
    if stray_mit:
        fail(f"README 里 {len(stray_mit)} 处裸露的 MIT (既不是 License 也不是 Theory)")
    else:
        ok("MIT 缩写无冲突")
else:
    ok("MIT 缩写无冲突")

# ---------------------------------------------------------------- 6. 六层来源与证据等级
readme = (ROOT / "README.md").read_text(encoding="utf-8")
ev = ROOT / "docs" / "evidence.md"
if not ev.exists():
    fail("docs/evidence.md 不存在")
else:
    evt = ev.read_text(encoding="utf-8")
    if "机制 E3–E4" in evt or "机制 E3)" in readme:
        fail("L1/L2 仍把未核验的外部机制证据写成确定等级")
    else:
        ok("L1/L2 未宣称未经核验的机制等级")

# ---------------------------------------------------------------- 7. hypotheses.yaml 完整性
hy = ROOT / "hypotheses.yaml"
if hy.exists():
    try:
        import yaml
        data = yaml.safe_load(hy.read_text(encoding="utf-8"))
        hypothesis_data = data
        expected = {f"H{i}" for i in range(1, 19)}
        actual = set(data.get("hypotheses", {}).keys())
        missing = expected - actual
        if missing:
            fail(f"hypotheses.yaml 缺少: {sorted(missing)}")
        else:
            ok(f"hypotheses.yaml 完整 ({len(actual)} 条)")
    except ImportError:
        print("INFO 未装 pyyaml,跳过 hypotheses.yaml 检查")
    except Exception as e:
        fail(f"hypotheses.yaml 解析失败: {e}")
else:
    print("INFO hypotheses.yaml 不存在,跳过")

# ---------------------------------------------------------------- 8. 白皮书版本跨文件一致
wp = version_data.get("whitepaper", {})
wp_version = str(wp.get("version", ""))
if not wp_version:
    fail("VERSION.yaml 找不到 whitepaper.version")
else:
    current_docs = [
        ("README.md", (ROOT / "README.md").read_text(encoding="utf-8")),
        ("README.en.md", (ROOT / "README.en.md").read_text(encoding="utf-8")),
        ("docs/roadmap.md", (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")),
        ("index.html", (ROOT / "index.html").read_text(encoding="utf-8")),
    ]
    for name, text in current_docs:
        refs = set(re.findall(r"(?:白皮书|white paper)\s+(?:\*\*)?v(\d+\.\d+)", text, re.I))
        if wp_version not in refs:
            fail(f"{name} 未引用白皮书 v{wp_version}")
        elif refs - {wp_version}:
            fail(f"{name} 白皮书版本不一致: {sorted(refs)} != v{wp_version}")
        else:
            ok(f"{name} 白皮书版本一致 = v{wp_version}")

    pages = wp.get("pages")
    tables = wp.get("tables")
    figures = wp.get("figures")
    readme_en = (ROOT / "README.en.md").read_text(encoding="utf-8")
    if pages is not None and (f"{pages} 页" not in readme or f"{pages} pages" not in readme_en):
        fail(f"README 白皮书页数未统一为 {pages}")
    elif pages is not None:
        ok(f"README 白皮书页数一致 = {pages}")
    if figures is not None and (f"{figures} 图" not in readme or f"{figures} figures" not in readme_en):
        fail(f"README 白皮书图数未统一为 {figures}")
    elif figures is not None:
        ok(f"README 白皮书图数一致 = {figures}")

    index = (ROOT / "index.html").read_text(encoding="utf-8")
    if pages is not None and figures is not None and tables is not None:
        expected_meta = f"{pages} 页 / {tables} 表 / {figures} 图"
        if expected_meta not in index:
            fail(f"index.html 白皮书元数据不是 {expected_meta}")
        else:
            ok(f"index.html 白皮书元数据一致 = {pages} 页 / {tables} 表 / {figures} 图")
    if not re.search(rf'<div class="version">v{re.escape(wp_version)}</div>', index):
        fail(f"index.html 版本标签不是 v{wp_version}")
    else:
        ok(f"index.html 版本标签一致 = v{wp_version}")

    dist = ROOT / "whitepaper" / "dist"
    docx_files = list(dist.glob(f"*_v{wp_version}_*.docx"))
    pdf_files = list(dist.glob(f"*_v{wp_version}_*.pdf"))
    for suffix, artifacts in (("DOCX", docx_files), ("PDF", pdf_files)):
        if not artifacts:
            fail(f"whitepaper/dist 缺少 v{wp_version} 的 {suffix} 产物")
        else:
            ok(f"whitepaper/dist 存在 v{wp_version} {suffix}")
    if docx_files:
        try:
            import xml.etree.ElementTree as ET
            import zipfile
            with zipfile.ZipFile(docx_files[0]) as archive:
                document_xml = archive.read("word/document.xml")
            root = ET.fromstring(document_xml)
            namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            actual_tables = len(root.findall(".//w:tbl", namespaces))
            actual_figures = len(root.findall(".//w:drawing", namespaces))
            if tables is not None and actual_tables != tables:
                fail(f"白皮书 DOCX 实际表格数 {actual_tables} != VERSION.yaml {tables}")
            else:
                ok(f"白皮书 DOCX 表格数一致 = {actual_tables}")
            if figures is not None and actual_figures != figures:
                fail(f"白皮书 DOCX 实际插图数 {actual_figures} != VERSION.yaml {figures}")
            else:
                ok(f"白皮书 DOCX 插图数一致 = {actual_figures}")
        except Exception as exc:
            fail(f"白皮书 DOCX 结构解析失败: {exc}")
    if pdf_files:
        try:
            pdf_bytes = pdf_files[0].read_bytes()
            actual_pages = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))
            if pages is not None and actual_pages != pages:
                fail(f"白皮书 PDF 实际页数 {actual_pages} != VERSION.yaml {pages}")
            else:
                ok(f"白皮书 PDF 页数一致 = {actual_pages}")
            if not pdf_bytes.startswith(b"%PDF-") or b"%%EOF" not in pdf_bytes[-2048:]:
                fail("白皮书 PDF 文件头或 EOF 标记无效")
        except Exception as exc:
            fail(f"白皮书 PDF 结构解析失败: {exc}")

# ---------------------------------------------------------------- 9. MSI 演示配置
msi_version = version_data.get("msi_demo", {})
config_path = ROOT / "msi" / "config.json"
try:
    import json
    msi_cfg = json.loads(config_path.read_text(encoding="utf-8"))
except Exception as e:
    fail(f"msi/config.json 解析失败: {e}")
    msi_cfg = {}

if msi_cfg.get("source_kind") != "engineering_extension":
    fail("MSI 未声明 source_kind=engineering_extension")
else:
    ok("MSI 来源类型为工程扩展")
if "version" in msi_cfg:
    fail("MSI config 仍使用含义含糊的顶层 version 字段")
else:
    ok("MSI 无歧义版本字段")
if msi_cfg.get("canon_version") != version_data.get("canon", {}).get("version"):
    fail("MSI canon_version 与 VERSION.yaml 不一致")
else:
    ok("MSI 正典版本一致")

layers = msi_cfg.get("layers", [])
expected_layers = {
    "L1": ("本框架 E1；机制待核验", [], "engineering_draft"),
    "L2": ("本框架 E1；机制待核验", [], "engineering_draft"),
    "L3": ("本框架 E0–E1；机制 E0", ["H2"], "canon"),
    "L4": ("本框架 E2（工具）/ E1（模型）", ["H10"], "engineering_draft"),
    "L5": ("本框架 E1；关联 H7/H8（E1）", ["H7", "H8"], "engineering_draft"),
    "L6": ("本框架 E2；关联 H12/H13（E2）、H14（E1）", ["H12", "H13", "H14"], "engineering_draft"),
}
actual_layers = {item.get("id"): item for item in layers}
if set(actual_layers) != set(expected_layers):
    fail(f"MSI 层 ID 不完整或重复: {sorted(actual_layers)}")
else:
    ok("MSI 六层 ID 完整")
available_hypotheses = set(hypothesis_data.get("hypotheses", {}))
for layer_id, (evidence, hypotheses, scope) in expected_layers.items():
    layer = actual_layers.get(layer_id, {})
    if layer.get("evidence") != evidence:
        fail(f"{layer_id} 证据等级与验收基线不一致")
    if not isinstance(layer.get("evidence_en"), str) or not layer["evidence_en"].strip() or any(
        "\u4e00" <= char <= "\u9fff" for char in layer["evidence_en"]
    ):
        fail(f"{layer_id} 缺少可用的英文证据等级")
    if layer.get("canon_hypotheses") != hypotheses:
        fail(f"{layer_id} 正典假设映射与验收基线不一致")
    if not set(layer.get("canon_hypotheses", [])).issubset(available_hypotheses):
        fail(f"{layer_id} 引用了 hypotheses.yaml 中不存在的假设")
    if layer.get("falsifier_scope") != scope:
        fail(f"{layer_id} 证伪条件范围与验收基线不一致")
    if not all(isinstance(layer.get(key, {}).get(lang), str) and layer[key][lang].strip()
               for key in ("falsifier",) for lang in ("zh", "en")):
        fail(f"{layer_id} 缺少双语证伪条件")
if not any("证据等级与验收基线" in item for item in failures):
    ok("六层证据、正典映射与证伪范围一致")

whitepaper_source = ROOT / "whitepaper" / "build_whitepaper.py"
if whitepaper_source.exists():
    wpt = whitepaper_source.read_text(encoding="utf-8")
    for layer_id, (evidence, _, _) in expected_layers.items():
        if evidence not in wpt:
            fail(f"白皮书生成器缺少 {layer_id} 证据基线: {evidence}")
    for retired in ("机制 E3–E4", "机制成熟，框架内操作化待测", "机制 E3)"):
        if retired in wpt:
            fail(f"白皮书生成器仍含旧证据表述: {retired}")
    if ("不是正典附录 D.7" not in wpt and "不是正典附录D.7" not in wpt) or "工程证伪草案与正典假设映射" not in wpt:
        fail("白皮书生成器未区分工程草案与正典附录 D.7")
else:
    fail("whitepaper/build_whitepaper.py 不存在")

for relative in ("docs/evidence.md", "docs/claims.md", "docs/glossary.md", "CONTRIBUTING.md"):
    text = (ROOT / relative).read_text(encoding="utf-8")
    if "有预注册假设，数据收集中" not in text or "跨情境、跨文化、跨时间泛化" not in text:
        fail(f"{relative} 未完整采用 V7 的 E3/E6 判据")
    else:
        ok(f"{relative} E3/E6 判据符合 V7")

if msi_cfg.get("overload", {}).get("count") != 45:
    fail("MSI overload.count 应为实际实现的 45")
else:
    ok("MSI 过载文本数量为 45")
content = msi_cfg.get("content", {})
if any(len(content.get(key, {}).get(lang, [])) != count
       for key, count in (("ste_lines", 3),) for lang in ("zh", "en")):
    fail("MSI 核心语句应为每语言 3 条")
else:
    ok("MSI 核心语句数量为 3")
if len(msi_cfg.get("demo", {}).get("assess_levels", [])) != 9:
    fail("MSI 示意点数量应为 9")

canon = version_data.get("canon", {})
for key in ("primary_artifact", "english_mother"):
    digest = canon.get(key, {}).get("sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        fail(f"VERSION.yaml canon.{key}.sha256 无效")
    elif digest not in (ROOT / "docs" / "canon-audit.md").read_text(encoding="utf-8"):
        fail(f"canon-audit.md 未记录 {key} 的 SHA-256")
if not canon.get("authority_order"):
    fail("VERSION.yaml 缺少正典权威顺序")
else:
    ok("正典来源哈希与权威顺序已登记")

acts = msi_cfg.get("acts", [])
expected_acts = msi_version.get("acts")
if expected_acts is not None and len(acts) != expected_acts:
    fail(f"MSI 幕数 {len(acts)} != VERSION.yaml ({expected_acts})")
elif acts:
    ok(f"MSI 幕数一致 = {len(acts)}")

if len(msi_cfg.get("layers", [])) != len(version_data.get("operational_stack", {}).get("layers", [])):
    fail("MSI 层数与 VERSION.yaml operational_stack.layers 不一致")
else:
    ok("MSI 层数与 VERSION.yaml 一致")

if acts:
    runtime = sum(float(act.get("enter", 0)) + float(act.get("hold", 0)) for act in acts)
    runtime += float(msi_cfg.get("final", {}).get("enter", 0)) + float(msi_cfg.get("final", {}).get("hold", 0))
    expected_runtime = msi_version.get("runtime_seconds")
    if expected_runtime is not None and abs(runtime - expected_runtime) > 0.5:
        fail(f"MSI 配置时长 {runtime:.1f}s != VERSION.yaml ({expected_runtime}s)")
    else:
        ok(f"MSI 配置时长一致 = {runtime:.1f}s")

# ---------------------------------------------------------------- 10. toolkit 数量
toolkit_count = version_data.get("toolkit", {}).get("count")
toolkit_files = list((ROOT / "toolkit").glob("*.md"))
if toolkit_count is not None and len(toolkit_files) != toolkit_count:
    fail(f"toolkit 文件数 {len(toolkit_files)} != VERSION.yaml ({toolkit_count})")
elif toolkit_files:
    ok(f"toolkit 文件数一致 = {len(toolkit_files)}")

readme_en = (ROOT / "README.en.md").read_text(encoding="utf-8")
if toolkit_count is not None:
    if f"{toolkit_count} 份工具" not in readme and f"{toolkit_count} fillable" not in readme_en.lower():
        fail(f"README 未声明 toolkit 数量 {toolkit_count}")
    else:
        ok(f"README toolkit 数量一致 = {toolkit_count}")

# ---------------------------------------------------------------- 11. 正典版本
canon_version = version_data.get("canon", {}).get("version")
if canon_version and canon_version not in readme:
    fail(f"README.md 未引用正典 {canon_version}")
elif canon_version:
    ok(f"README.md 正典版本一致 = {canon_version}")

# ---------------------------------------------------------------- 12. 引用日期与文档索引版本
citation_path = ROOT / "CITATION.cff"
try:
    citation = yaml.safe_load(citation_path.read_text(encoding="utf-8"))
    citation_date = str(citation.get("date-released", ""))
    research_date = str(version_data.get("research_system", {}).get("date", ""))
    if citation_date != research_date:
        fail(f"CITATION.cff 日期 ({citation_date}) != VERSION.yaml ({research_date})")
    else:
        ok(f"CITATION.cff 日期一致 = {research_date}")
except Exception as e:
    fail(f"CITATION.cff 解析失败: {e}")

docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
if version and f"what {version} already delivers" not in docs_index:
    fail(f"docs/README.md 英文索引未引用当前版本 {version}")
else:
    ok(f"docs/README.md 当前版本一致 = {version}")

# ---------------------------------------------------------------- 结果
print()
if failures:
    print(f"共 {len(failures)} 项失败")
    sys.exit(1)
print("所有一致性检查通过")
sys.exit(0)