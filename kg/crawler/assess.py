"""Score a decision list against the crawl contract.

Live runs are scored on invariants (pass/fail) and a scorecard (printed, not a
gate, except where a missing field is already an invariant). `--fixture`
replays normalize on frozen feeds and diffs the decision list.
"""

from __future__ import annotations

import json
import re

from normalize import MONTHS
from prepare import DRAFTS, FIXTURES, KG

GRAPH_FIELDS = ("entities", "claims", "relations", "timeline")

SKIP_FIELDS = {
    "skip-same-stem": ("stem", "existing", "needle"),
    "skip-different-stem": ("stem", "existing", "needle"),
    "skip-no-date": ("title",),
    "skip-no-chapters": ("id", "title"),
    "skip-chapters-external": ("id", "title", "chapters_url", "enclosure_url"),
    "skip-no-enclosure": ("id", "title"),
}

MONTH_TOKENS = set(MONTHS) | {"sept"}


def is_garbage(noun: str) -> bool:
    """Known-bad noun-scan patterns. A score, not a judgment about the name."""
    if re.search(r"\.\s*\S", noun):
        return True
    token = noun.strip().rstrip(".").lower()
    if token in MONTH_TOKENS:
        return True
    if re.search(r"-[a-z]", noun):
        return True
    return False


def _present(decision: dict, fields: tuple[str, ...]) -> bool:
    for field in fields:
        value = decision.get(field)
        if value is None or value == "":
            return False
    return True


def skip_is_transparent(decision: dict) -> bool:
    outcome = decision["outcome"]
    fields = SKIP_FIELDS.get(outcome)
    if fields is None:
        return True
    if not _present(decision, fields):
        return False
    stem = decision.get("stem") or ""
    existing = decision.get("existing") or ""
    if outcome == "skip-same-stem" and existing != f"{stem}.document.twk":
        return False
    if outcome == "skip-different-stem" and existing == f"{stem}.document.twk":
        return False
    if outcome == "skip-no-chapters":
        # Each adapter counts what it actually looked at. A refusal that names no
        # count is not transparent, whichever surface it was reading.
        counts = ("description_length", "timestamp_lines", "psc_chapter_count")
        if not any(isinstance(decision.get(field), int) for field in counts):
            return False
    if outcome == "skip-chapters-external" and not decision.get("chapters_url"):
        return False
    return True


def _under_drafts(path: str) -> bool:
    try:
        (KG / path).resolve().relative_to(DRAFTS.resolve())
    except ValueError:
        return False
    return True


def _add(invariants: list[dict], name: str, ok: bool, detail: str) -> None:
    invariants.append({"name": name, "ok": ok, "detail": detail})


def _ratio(part: int, whole: int) -> float | None:
    if whole == 0:
        return None
    return part / whole


def evaluate(meta: list[dict], decisions: list[dict]) -> dict:
    """meta: [{source, entries, error}]. decisions cover every feed entry."""
    invariants: list[dict] = []
    by_source: dict[str, list[dict]] = {}
    for decision in decisions:
        by_source.setdefault(decision["source"], []).append(decision)

    accounted = []
    fetch_errors = []
    for source in meta:
        name = source["source"]
        got = len(by_source.get(name, []))
        if source.get("error"):
            fetch_errors.append(f"{name}: {source['error']}")
        if got != source["entries"]:
            accounted.append(f"{name}: {got} decisions, {source['entries']} entries")
    _add(invariants, "fetch", not fetch_errors, "; ".join(fetch_errors) or "feeds fetched")
    _add(invariants, "accounted", not accounted, "; ".join(accounted) or "every entry has one outcome")

    wrote = [path for decision in decisions for path in decision.get("wrote") or []]
    escaped = [path for path in wrote if not _under_drafts(path)]
    _add(
        invariants,
        "drafts-only",
        not escaped,
        ", ".join(escaped) or "writes stayed under kg/drafts/",
    )

    invalid = []
    nonempty = []
    empty_structure = []
    for decision in decisions:
        if decision["outcome"] != "write":
            continue
        validation = decision.get("validation") or {}
        if not validation.get("ok"):
            invalid.append(f"{decision.get('stem')}: {validation.get('errors')}")
        doc = decision.get("doc") or {}
        filled = [field for field in GRAPH_FIELDS if doc.get(field)]
        if filled:
            nonempty.append(f"{decision.get('stem')}: {', '.join(filled)}")
        if not decision.get("structure_count"):
            empty_structure.append(str(decision.get("stem") or decision.get("title") or "?"))
    _add(invariants, "valid", not invalid, "; ".join(invalid) or "every write validates")
    _add(
        invariants,
        "empty-graph",
        not nonempty,
        "; ".join(nonempty) or "entities/claims/relations/timeline empty",
    )
    _add(
        invariants,
        "structure",
        not empty_structure,
        ", ".join(empty_structure) or "every write has at least one section or chapter",
    )

    seen_stems: dict[str, int] = {}
    for decision in decisions:
        if decision["outcome"] == "write":
            stem = decision.get("stem") or "?"
            seen_stems[stem] = seen_stems.get(stem, 0) + 1
    dupes = [stem for stem, count in seen_stems.items() if count > 1]
    _add(
        invariants,
        "unique-writes",
        not dupes,
        ", ".join(sorted(dupes)) or "no two writes claim the same stem",
    )

    skips = [d for d in decisions if str(d["outcome"]).startswith("skip-")]
    opaque = [d for d in skips if not skip_is_transparent(d)]
    opaque_detail = ", ".join(
        f"{d['source']}[{d['entry_index']}] {d['outcome']}" for d in opaque[:8]
    )
    _add(
        invariants,
        "transparent",
        not opaque,
        opaque_detail or "every skip carries its reason fields",
    )

    tailless = [d for d in decisions if d["outcome"] == "not-examined" and not d.get("title")]
    _add(
        invariants,
        "limit-tail",
        not tailless,
        f"{len(tailless)} not-examined without a title" if tailless else "limit tail is named",
    )

    writes = [d for d in decisions if d["outcome"] == "write"]
    nouns = [noun for decision in writes for noun in decision.get("nouns") or []]
    garbage = [noun for noun in nouns if is_garbage(noun)]
    examined = [d for d in decisions if d["outcome"] != "not-examined"]
    collisions = [d for d in decisions if d["outcome"] == "skip-different-stem"]
    transparent = len(skips) - len(opaque)

    outcomes: dict[str, dict[str, int]] = {}
    for decision in decisions:
        bucket = outcomes.setdefault(decision["source"], {})
        bucket[decision["outcome"]] = bucket.get(decision["outcome"], 0) + 1

    return {
        "ok": all(item["ok"] for item in invariants),
        "invariants": invariants,
        "scores": {
            "coverage": _ratio(len(examined), len(decisions)),
            "examined": len(examined),
            "entries": len(decisions),
            "transparent_refusals": _ratio(transparent, len(skips)),
            "transparent_skips": transparent,
            "skips": len(skips),
            "stem_collisions": len(collisions),
            "collisions": [
                {"stem": d.get("stem"), "existing": d.get("existing"), "needle": d.get("needle")}
                for d in collisions
            ],
            "noun_garbage_rate": _ratio(len(garbage), len(nouns)),
            "noun_candidates": len(nouns),
            "noun_garbage": len(garbage),
        },
        "outcomes": outcomes,
    }


def check_fixture(decisions: list[dict], expected: dict) -> list[str]:
    """Diff decisions against the frozen expected list. Extra keys are allowed."""
    errors = []
    by_source: dict[str, list[dict]] = {}
    for decision in decisions:
        by_source.setdefault(decision["source"], []).append(decision)
    for source, rows in expected["sources"].items():
        actual = by_source.get(source, [])
        if len(actual) != len(rows):
            errors.append(f"{source}: {len(actual)} decisions, expected {len(rows)}")
            continue
        for index, row in enumerate(rows):
            got = actual[index]
            for key, value in row.items():
                if got.get(key) != value:
                    errors.append(
                        f"{source}[{index}] {key}: {got.get(key)!r} != {value!r} "
                        f"(outcome {got.get('outcome')})"
                    )
                    break
    til_write = next(
        (d for d in decisions if d["source"] == "innermost-loop" and d["outcome"] == "write"),
        None,
    )
    if til_write is None:
        errors.append("fixture noun sample: no innermost-loop write")
        return errors
    nouns = til_write.get("nouns") or []
    garbage = [noun for noun in nouns if is_garbage(noun)]
    if not any(re.search(r"\.\s*\S", noun) for noun in garbage):
        errors.append(f"fixture noun sample: no cross-sentence join in {nouns}")
    if not any(noun.strip().rstrip(".").lower() in MONTH_TOKENS for noun in garbage):
        errors.append(f"fixture noun sample: no calendar token in {nouns}")
    if not any(re.search(r"-[a-z]", noun) for noun in garbage):
        errors.append(f"fixture noun sample: no verb-phrase hyphen in {nouns}")
    if "OpenAI" not in nouns or is_garbage("OpenAI"):
        errors.append(f"fixture noun sample: OpenAI missing or flagged in {nouns}")
    return errors


def load_fixture() -> tuple[dict, list[dict], list[dict]]:
    from crawl import load_aa, load_podlove, load_til
    from normalize import decide, reserve

    spec = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    index = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
    fetched = "2026-01-01T00:00:00+00:00"
    meta = []
    decisions = []
    for source, loader, filename in (
        ("innermost-loop", load_til, "til-feed.xml"),
        ("american-alchemy", load_aa, "aa-feed.xml"),
        ("cre", load_podlove, "cre-feed.xml"),
    ):
        entries = loader((FIXTURES / filename).read_text(encoding="utf-8"))
        meta.append({"source": source, "entries": len(entries), "error": None})
        rows = decide(entries, index["known"], spec["limit"], fetched)
        reserve(index["known"], rows)
        decisions.extend(rows)
    return spec, meta, decisions


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def format_decision(decision: dict) -> str:
    outcome = decision["outcome"]
    title = (decision.get("title") or "")[:80]
    if outcome == "write":
        validation = decision.get("validation") or {}
        flag = "+" if decision.get("wrote") else "DRY"
        return (
            f"  {flag} {decision.get('stem')}.document.twk  "
            f"ok={validation.get('ok')} errors={validation.get('errors')} "
            f"warnings={validation.get('warnings')}"
        )
    if outcome == "skip-same-stem":
        return f"  = skip {decision.get('stem')} (same stem: {decision.get('existing')})"
    if outcome == "skip-different-stem":
        return f"  = skip {decision.get('stem')} (different stem: {decision.get('existing')})"
    if outcome == "skip-no-date":
        return f"  ? skip (no date): {title}"
    if outcome == "skip-no-chapters":
        return (
            f"  ? skip (no chapters): {title}  id={decision.get('id')} "
            f"desc_len={decision.get('description_length')} "
            f"timestamp_lines={decision.get('timestamp_lines')}"
        )
    if outcome == "not-examined":
        ident = decision.get("id") or ""
        suffix = f"  id={ident}" if ident else ""
        return f"  . not examined (limit): {title}{suffix}"
    return f"  ! {outcome}: {title}"


def format_report(report: dict) -> str:
    scores = report["scores"]
    lines = []
    for source, counts in report.get("outcomes", {}).items():
        rendered = ", ".join(f"{name} {count}" for name, count in sorted(counts.items()))
        lines.append(f"{source}: {rendered}")
    lines.append("assess")
    for item in report["invariants"]:
        mark = "pass" if item["ok"] else "FAIL"
        lines.append(f"  {item['name']:<16} {mark}  {item['detail']}")
    lines.append(
        f"  coverage             {_pct(scores['coverage'])}  "
        f"({scores['examined']}/{scores['entries']})"
    )
    lines.append(
        f"  transparent refusals {_pct(scores['transparent_refusals'])}  "
        f"({scores['transparent_skips']}/{scores['skips']})"
    )
    lines.append(f"  stem collisions      {scores['stem_collisions']}")
    for collision in scores["collisions"]:
        lines.append(f"    {collision['stem']} -> {collision['existing']}")
    lines.append(
        f"  noun garbage rate    {_pct(scores['noun_garbage_rate'])}  "
        f"({scores['noun_garbage']}/{scores['noun_candidates']})"
    )
    lines.append("result               " + ("pass" if report["ok"] else "FAIL"))
    return "\n".join(lines)
