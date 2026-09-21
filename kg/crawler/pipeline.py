#!/usr/bin/env python3
"""prepare -> crawl (one feed at a time) -> normalize -> assess.

The only command. Draft files are written for outcome=write, and only under
kg/drafts/. entities/claims/relations/timeline stay empty (RESEARCH-METHODS.md
sec 8). Assess scores the decision list, including --dry-run and --fixture.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

KG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(KG / "server"))

from assess import check_fixture, evaluate, format_decision, format_report, load_fixture  # noqa: E402
from crawl import (  # noqa: E402
    AA_FEED,
    PODLOVE_FEED,
    TIL_FEED,
    fetch_aa,
    fetch_podlove,
    fetch_til,
    resolve_channel_id,
)
from normalize import decide, reserve  # noqa: E402
from prepare import (  # noqa: E402
    DRAFTS,
    SOURCES,
    build_index,
    open_run,
    save_bytes,
    save_json,
    select_sources,
)
from twk_lib import validate  # noqa: E402


def _public_decision(decision: dict) -> dict:
    """Run record without the document body duplicated beside the feed snapshot."""
    skip = {"doc", "surface"}
    return {key: value for key, value in decision.items() if key not in skip}


def _write_draft(decision: dict) -> list[str]:
    stem = decision["stem"]
    DRAFTS.mkdir(parents=True, exist_ok=True)
    doc_path = DRAFTS / f"{stem}.document.twk"
    source_path = DRAFTS / f"{stem}.source.txt"
    todo_path = DRAFTS / f"{stem}.TODO.md"
    doc_path.write_text(
        json.dumps(decision["doc"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    source_path.write_text(decision.get("surface") or "", encoding="utf-8")
    nouns = (decision.get("nouns") or [])[:80]
    todo = [
        f"# TODO — {stem}",
        "",
        "Machine-generated draft. Nothing below is resolved. Do NOT copy these into the",
        "document without doing the judgment pass in `kg/RESEARCH-METHODS.md` sec 3.4-3.6.",
        "",
        "## Reviewer checklist",
        "- [ ] entities: local id, type, Wikidata Q-id or explicitly deferred (with the date you looked)",
        "- [ ] claims: split asserted-in-media vs external-fact; quote must exist on the public surface",
        "- [ ] confidence per the sec 3.5 rubric",
        "- [ ] relations + timeline intervals (not one per chapter)",
        "- [ ] write `<stem>.dictionary.twk` and point composition.dictionary at it",
        "- [ ] validate, then move both files to kg/repo/ and add to the series manifest",
        "",
        "## Unresolved candidate proper nouns (capitalized-phrase scan, no judgment applied)",
        "",
    ]
    todo += [f"- {noun}" for noun in nouns]
    todo_path.write_text("\n".join(todo) + "\n", encoding="utf-8")
    return [
        doc_path.relative_to(KG).as_posix(),
        source_path.relative_to(KG).as_posix(),
        todo_path.relative_to(KG).as_posix(),
    ]


def _attach_validation(decisions: list[dict]) -> None:
    for decision in decisions:
        if decision["outcome"] == "write":
            decision["validation"] = validate(decision["doc"])


def _print_run(meta: list[dict], decisions: list[dict], report: dict, run: Path | None) -> None:
    by_source: dict[str, list[dict]] = {}
    for decision in decisions:
        by_source.setdefault(decision["source"], []).append(decision)
    for source in meta:
        name = source["source"]
        rows = by_source.get(name, [])
        if rows:
            print(name)
        for decision in rows:
            print(format_decision(decision))
    print(format_report(report))
    if run is not None:
        print(f"run                  {run.relative_to(KG.parent).as_posix()}")


def run_live(source: str, limit: int, dry_run: bool) -> int:
    sources = select_sources(source)
    run = open_run(source, limit, dry_run)
    known = build_index()
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta: list[dict] = []
    decisions: list[dict] = []
    channel_id = None

    for name in sources:
        try:
            if name == "innermost-loop":
                print(f"innermost-loop: {TIL_FEED}", flush=True)
                xml_text, entries = fetch_til()
                save_bytes(run, "innermost-loop.xml", xml_text)
            elif name == "cre":
                print(f"cre: {PODLOVE_FEED}", flush=True)
                xml_text, entries = fetch_podlove()
                save_bytes(run, "cre.xml", xml_text)
            else:
                channel_id, channel_html = resolve_channel_id()
                print(f"american-alchemy: channel_id={channel_id}", flush=True)
                if channel_html:
                    save_bytes(run, "channel.html", channel_html)
                feed = AA_FEED.format(channel_id)
                print(f"  {feed}", flush=True)
                xml_text, entries = fetch_aa(channel_id)
                save_bytes(run, "american-alchemy.xml", xml_text)
            print(f"  feed entries: {len(entries)}")
            meta.append({"source": name, "entries": len(entries), "error": None})
            rows = decide(entries, known, limit, fetched)
            reserve(known, rows)
            decisions.extend(rows)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! fetch error: {exc}")
            meta.append({"source": name, "entries": 0, "error": str(exc)})

    _attach_validation(decisions)
    if not dry_run:
        for decision in decisions:
            if decision["outcome"] != "write":
                continue
            if not decision["validation"]["ok"]:
                continue
            decision["wrote"] = _write_draft(decision)

    report = evaluate(meta, decisions)
    save_json(run, "plan.json", {
        "source": source,
        "limit": limit,
        "dry_run": dry_run,
        "fetched": fetched,
        "channel_id": channel_id,
        "sources": meta,
    })
    save_json(run, "decisions.json", [_public_decision(d) for d in decisions])
    save_json(run, "report.json", report)
    _print_run(meta, decisions, report, run)
    return 0 if report["ok"] else 1


def _configure_stdout() -> None:
    """Feed titles include characters cp1252 cannot encode. Don't die on print."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def main() -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", choices=[*SOURCES, "all"], default="all"
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="replay the frozen feeds and diff decisions against fixtures/expected.json",
    )
    args = parser.parse_args()
    if args.fixture:
        return run_fixture_command()
    return run_live(args.source, args.limit, args.dry_run)


def run_fixture_command() -> int:
    _spec, meta, decisions = load_fixture()
    _attach_validation(decisions)
    report = evaluate(meta, decisions)
    errors = check_fixture(decisions, _spec)
    report["invariants"].append(
        {
            "name": "fixture",
            "ok": not errors,
            "detail": "; ".join(errors) if errors else "decision list matches",
        }
    )
    report["ok"] = report["ok"] and not errors
    print(format_report(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
