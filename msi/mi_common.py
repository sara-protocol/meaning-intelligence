"""Shared helpers: config loading + validation, timeline planning, Mermaid generation.

Used by the Manim scene and build.py so every deliverable derives from
config.json (single source of truth).

Model: 6 `layers` (grouped in 3 `bands`) are what the stack IS;
8 `acts` are what the animation SHOWS. Each act belongs to one layer.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_config(path=None):
    cfg = json.loads(Path(path or HERE / "config.json").read_text(encoding="utf-8"))
    validate_config(cfg)
    return cfg


def validate_config(cfg):
    langs = cfg["languages"]
    assert cfg["default_lang"] in langs, "default_lang must be in languages"

    def need(d, where):
        for lg in langs:
            assert lg in d, f"missing language '{lg}' in {where}"

    layer_ids = [l["id"] for l in cfg["layers"]]
    band_ids = [b["id"] for b in cfg["bands"]]
    assert len(set(layer_ids)) == len(layer_ids), "duplicate layer ids"
    for b in cfg["bands"]:
        need(b["label"], f"band {b['id']}.label")
        need(b["problem"], f"band {b['id']}.problem")
        assert b["tier"] in cfg["colors"], f"unknown tier {b['tier']}"
        assert all(l in layer_ids for l in b["layers"]), f"band {b['id']} lists unknown layer"
    for l in cfg["layers"]:
        assert l["band"] in band_ids, f"layer {l['id']} has unknown band"
        for k in ("name", "definition", "anchor", "falsifier"):
            need(l[k], f"layer {l['id']}.{k}")
    in_bands = [x for b in cfg["bands"] for x in b["layers"]]
    assert sorted(in_bands) == sorted(layer_ids), "every layer must belong to exactly one band"

    acts = cfg["acts"]
    ids = [a["id"] for a in acts]
    assert len(set(ids)) == len(ids), "duplicate act ids"
    seen = []
    for a in acts + [cfg["final"]]:
        need(a["label"], f"act {a['id']}.label")
        need(a["scene"], f"act {a['id']}.scene")
        assert a["enter"] > 0 and a["hold"] >= 0, f"bad timing in {a['id']}"
    for a in acts:
        need(a["desc"], f"act {a['id']}.desc")
        assert a["layer"] in layer_ids, f"act {a['id']} has unknown layer"
        assert a["tier"] in cfg["colors"], f"unknown tier {a['tier']}"
        seen.append(a["layer"])
    # layers must appear in order and every layer must have at least one act
    order = [x for i, x in enumerate(seen) if i == 0 or seen[i - 1] != x]
    assert order == layer_ids, f"acts must cover layers contiguously and in order; got {order}"

    for k, v in cfg["content"].items():
        need(v, f"content.{k}")
    assert len(cfg["content"]["axes"][langs[0]]) == 3
    assert len(cfg["content"]["candidates"][langs[0]]) == 3
    n = len(cfg["content"]["ste_lines"][langs[0]])
    assert all(len(cfg["content"]["ste_lines"][lg]) == n for lg in langs), "ste_lines length mismatch"
    assert len(cfg["evidence_scale"]) == 7, "evidence_scale must have E0..E6"
    assert all(0 <= x <= 6 for x in cfg["demo"]["assess_levels"])
    need(cfg["source_note"], "source_note")
    for lg in langs:
        assert lg in cfg["ui"], f"missing ui.{lg}"
        assert len(cfg["ui"][lg]["tabs"]) == 4


def layer_of(cfg, lid):
    return next(l for l in cfg["layers"] if l["id"] == lid)


def band_of(cfg, layer):
    return next(b for b in cfg["bands"] if b["id"] == layer["band"])


def plan_timeline(cfg):
    """Start second of every act and every layer (= its first act), from enter/hold only."""
    t, tl = 0.0, {}
    for a in cfg["acts"] + [cfg["final"]]:
        tl[a["id"]] = round(t, 3)
        if a.get("layer") and a["layer"] not in tl:
            tl[a["layer"]] = round(t, 3)
        t += a["enter"] + a["hold"]
    tl["end"] = round(t, 3)
    return tl


# ---------------------------------------------------------------- Mermaid
def _classdefs(c):
    d = []
    for k, fill, extra in [("gray", "fill_gray", ",stroke-dasharray:4 3"), ("cyan", "fill_cyan", ""),
                           ("purple", "fill_purple", ""), ("amber", "fill_amber", "")]:
        d.append(f"    classDef {k} fill:{c[fill]},stroke:{c[k]}{extra},color:{c[k]}")
    d.append(f"    classDef white fill:{c['bg']},stroke:{c['white']},stroke-width:2px,color:{c['white']}")
    return d


def mermaid_pipeline(cfg, lang):
    lines = ["flowchart LR"]
    for bi, b in enumerate(cfg["bands"]):
        lines.append(f'    subgraph B{bi}["{b["label"][lang]} · {b["problem"][lang]}"]')
        lines.append("        direction LR")
        for lid in b["layers"]:
            l = layer_of(cfg, lid)
            lines.append(f'        {lid}["{lid} · {l["name"][lang]}<br/>{l["definition"][lang]}<br/>{l["evidence"]}"]:::{b["tier"]}')
        lines.append("    end")
    lines.append("    " + " --> ".join(l["id"] for l in cfg["layers"]))
    last, first = cfg["layers"][-1]["id"], cfg["layers"][0]["id"]
    lines.append(f'    {last} -. "{first}′" .-> {first}')
    return "\n".join(lines + _classdefs(cfg["colors"]))


def mermaid_scenes(cfg, lang):
    lines = ["flowchart TD"]
    ids, count = [], cfg["overload"]["count"]
    for i, a in enumerate(cfg["acts"] + [cfg["final"]]):
        nid = f"N{i}"
        ids.append(nid)
        tag = f'{a["layer"]} · ' if a.get("layer") else ""
        text = a["scene"][lang].replace("{count}", str(count))
        lines.append(f'    {nid}["{tag}{a["label"][lang]}<br/>{text}"]:::{a.get("tier", "white")}')
    lines.append("    " + " --> ".join(ids))
    return "\n".join(lines + _classdefs(cfg["colors"]))


def mermaid_palette(cfg, lang):
    c, roles = cfg["colors"], cfg["color_roles"]
    order = ["gray", "cyan", "purple", "amber"]
    lines = ["flowchart LR"]
    for i, k in enumerate(order):
        lines.append(f'    P{i}["{k} {c[k]}<br/>{roles[k][lang]}"]:::{k}')
    ev = " → ".join(f"E{i}" for i in (0, 6))
    lines.append(f'    P4["{ev}<br/>{" ".join(cfg["evidence_scale"][:1] + cfg["evidence_scale"][-1:])}"]:::white')
    lines.append("    " + " --> ".join(f"P{i}" for i in range(5)))
    return "\n".join(lines + _classdefs(c))


def all_mermaid(cfg):
    return {
        lg: {"pipeline": mermaid_pipeline(cfg, lg), "scenes": mermaid_scenes(cfg, lg), "palette": mermaid_palette(cfg, lg)}
        for lg in cfg["languages"]
    }
