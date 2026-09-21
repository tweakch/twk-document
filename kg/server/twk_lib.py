"""TWK 0.2 lite validation + composition + graph index (server-side)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

KINDS = {"document", "manifest", "shard", "dictionary"}
ENTITY_TYPES = {
    "person",
    "place",
    "organization",
    "work",
    "event",
    "concept",
    "chemical",
    "document",
}
CLAIM_KINDS = {"asserted-in-media", "external-fact", "disputed"}
REL_TYPES = {
    "mentions",
    "asserts",
    "about",
    "producedChemical",
    "extractedChemical",
    "functionedAs",
    "hadComponentFunction",
    "instanceOf",
    "created",
    "contrastsWith",
    "associatedWith",
    "sameAs",
    "cites",
    "participantIn",
    "tookPlaceAt",
    "travel",
}


def pos_seconds(p: Any) -> float | None:
    if p is None:
        return None
    if isinstance(p, (int, float)) and p == p:
        return float(p)
    if isinstance(p, dict):
        if isinstance(p.get("t"), (int, float)):
            return float(p["t"])
        if p.get("scheme") == "seconds" and p.get("locator") is not None:
            try:
                return float(p["locator"])
            except (TypeError, ValueError):
                return None
        if isinstance(p.get("page"), (int, float)):
            return float(p["page"])
        if isinstance(p.get("frac"), (int, float)):
            return float(p["frac"])
    return None


def spans_cover(start: Any, end: Any, t: float) -> bool:
    a = pos_seconds(start)
    if a is None:
        return False
    b = pos_seconds(end) if end is not None else a
    if b is None:
        return t == a
    return a <= t <= b


def validate(doc: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(doc, dict):
        return {"ok": False, "errors": ["not an object"], "warnings": []}
    if doc.get("twk") is None:
        errors.append("missing twk")
    if not doc.get("id"):
        errors.append("missing id")
    media = doc.get("media") or {}
    if not media.get("uri"):
        errors.append("missing media.uri")
    kind = doc.get("kind") or "document"
    if doc.get("kind") and kind not in KINDS:
        warnings.append(f"unknown kind: {kind}")
    twk = str(doc.get("twk") or "")
    if twk.startswith("0.1"):
        warnings.append("loaded 0.1 document in 0.2 reader")
    elif twk and not twk.startswith("0.2"):
        warnings.append(f"unexpected version {twk}")

    def check_ids(arr, label):
        if not arr:
            return
        seen = set()
        for item in arr:
            if not item or not item.get("id"):
                continue
            if item["id"] in seen:
                errors.append(f"duplicate {label} id {item['id']}")
            seen.add(item["id"])

    check_ids(doc.get("entities"), "entity")
    check_ids(doc.get("relations"), "relation")
    check_ids(doc.get("claims"), "claim")
    check_ids(doc.get("sources"), "source")
    check_ids(doc.get("assets"), "asset")
    check_ids(doc.get("speakers"), "speaker")

    for ent in doc.get("entities") or []:
        if ent.get("type") and ent["type"] not in ENTITY_TYPES:
            warnings.append(f"entity type '{ent['type']}' not on v1 allowlist ({ent.get('id')})")

    prev = float("-inf")
    for iv in doc.get("timeline") or []:
        s = pos_seconds(iv.get("start"))
        e = pos_seconds(iv.get("end")) if iv.get("end") is not None else s
        if s is not None and s < 0:
            errors.append("negative start")
        if s is not None and e is not None and e < s:
            errors.append("end before start")
        if s is not None:
            if s < prev:
                errors.append("timeline not sorted by start")
            prev = s
        for ev in iv.get("events") or []:
            for key in ("confidence", "salience"):
                v = ev.get(key)
                if v is not None and not (0 <= float(v) <= 1):
                    errors.append(f"{key} out of range")

    for cl in doc.get("claims") or []:
        k = cl.get("kind")
        if k and k not in CLAIM_KINDS:
            warnings.append(f"unknown claim.kind {k}")
        pred = cl.get("predicate")
        if pred and pred not in REL_TYPES:
            warnings.append(f"predicate '{pred}' not on v1 allowlist ({cl.get('id')})")

    for rel in doc.get("relations") or []:
        t = rel.get("type")
        if t and t not in REL_TYPES:
            warnings.append(f"relation.type '{t}' not on v1 allowlist ({rel.get('id')})")

    return {"ok": not errors, "errors": errors, "warnings": warnings, "kind": kind}


def merge_docs(base: dict, incoming: dict) -> dict:
    out = copy.deepcopy(base)
    arrays = [
        "speakers",
        "entities",
        "timeline",
        "relations",
        "claims",
        "sources",
        "assets",
        "layers",
    ]
    for key in arrays:
        a = list(out.get(key) or [])
        b = list(incoming.get(key) or [])
        if not a and not b:
            continue
        seen = {x.get("id") for x in a if x and x.get("id")}
        for item in b:
            iid = item.get("id") if item else None
            if iid and iid in seen:
                continue
            if iid:
                seen.add(iid)
            a.append(item)
        if key == "timeline":
            a.sort(key=lambda x: pos_seconds(x.get("start")) or 0)
        out[key] = a
    inc_tr = incoming.get("transcript") or {}
    if inc_tr.get("segments"):
        segs = list((out.get("transcript") or {}).get("segments") or [])
        seen = {s.get("id") for s in segs if s.get("id")}
        extra = [s for s in inc_tr["segments"] if s.get("id") and s["id"] not in seen]
        segs = segs + extra
        segs.sort(key=lambda s: pos_seconds(s.get("start")) or 0)
        tr = dict(out.get("transcript") or inc_tr)
        tr["segments"] = segs
        out["transcript"] = tr
    return out


def context_at(doc: dict, t: float, min_salience: float = 0.0) -> dict:
    entities = {e["id"]: e for e in doc.get("entities") or [] if e.get("id")}
    relations = {r["id"]: r for r in doc.get("relations") or [] if r.get("id")}
    claims = {c["id"]: c for c in doc.get("claims") or [] if c.get("id")}
    events = []
    intervals = []
    for iv in doc.get("timeline") or []:
        if not spans_cover(iv.get("start"), iv.get("end"), t):
            continue
        intervals.append(iv)
        for ev in iv.get("events") or []:
            sal = ev.get("salience")
            if sal is not None and float(sal) < min_salience:
                continue
            events.append(ev)
    mentioned = []
    seen_e = set()
    for ev in events:
        eid = ev.get("entity")
        if eid and eid in entities and eid not in seen_e:
            seen_e.add(eid)
            mentioned.append(entities[eid])
    active_rel = []
    seen_r = set()
    for ev in events:
        rid = ev.get("relation")
        if rid and rid in relations and rid not in seen_r:
            seen_r.add(rid)
            active_rel.append(relations[rid])
    for rel in doc.get("relations") or []:
        if rel.get("id") in seen_r:
            continue
        if rel.get("start") is not None and spans_cover(rel.get("start"), rel.get("end"), t):
            seen_r.add(rel["id"])
            active_rel.append(rel)
    active_cl = []
    seen_c = set()
    for ev in events:
        cid = ev.get("claim")
        if cid and cid in claims and cid not in seen_c:
            seen_c.add(cid)
            active_cl.append(claims[cid])
    for cl in doc.get("claims") or []:
        if cl.get("id") in seen_c:
            continue
        if cl.get("start") is not None and spans_cover(cl.get("start"), cl.get("end"), t):
            seen_c.add(cl["id"])
            active_cl.append(cl)
    chapters = [
        ch
        for ch in (doc.get("structure") or {}).get("chapters") or []
        if spans_cover(ch.get("start"), ch.get("end"), t)
    ]
    return {
        "t": t,
        "empty": not events and not active_rel and not active_cl,
        "intervals": intervals,
        "events": events,
        "entities": mentioned,
        "relations": active_rel,
        "claims": active_cl,
        "chapters": chapters,
    }


def graph_of(doc: dict) -> dict:
    nodes = []
    edges = []
    for e in doc.get("entities") or []:
        nodes.append(
            {
                "id": e.get("id"),
                "kind": "entity",
                "type": e.get("type"),
                "label": e.get("name") or e.get("id"),
            }
        )
    for c in doc.get("claims") or []:
        nodes.append(
            {
                "id": c.get("id"),
                "kind": "claim",
                "type": c.get("kind"),
                "label": f"{c.get('predicate')} ({c.get('kind')})",
            }
        )
        if c.get("subject"):
            edges.append(
                {"id": f"e:{c.get('id')}:subject", "from": c["subject"], "to": c["id"], "type": "subject"}
            )
        obj = c.get("object")
        if isinstance(obj, str) and obj.startswith("entity:"):
            edges.append({"id": f"e:{c.get('id')}:object", "from": c["id"], "to": obj, "type": c.get("predicate")})
    for r in doc.get("relations") or []:
        edges.append(
            {
                "id": r.get("id"),
                "from": r.get("from"),
                "to": r.get("to"),
                "type": r.get("type"),
            }
        )
    for s in doc.get("sources") or []:
        nodes.append(
            {
                "id": s.get("id"),
                "kind": "source",
                "type": s.get("type"),
                "label": s.get("title") or s.get("id"),
            }
        )
    return {"nodes": nodes, "edges": edges}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
