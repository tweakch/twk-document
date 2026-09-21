"""Run folder, already-have index, and where a crawl is allowed to write.

No network. The raw feed bytes land in the run folder after fetch, so a live
run can be replayed through normalize later.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

KG = Path(__file__).resolve().parents[1]
CRAWLER = Path(__file__).resolve().parent
REPO = KG / "repo"
DRAFTS = KG / "drafts"
RUNS = CRAWLER / "runs"
FIXTURES = CRAWLER / "fixtures"

SOURCES = ("innermost-loop", "american-alchemy", "cre")


def select_sources(source: str) -> list[str]:
    if source == "all":
        return list(SOURCES)
    if source not in SOURCES:
        raise ValueError(f"unknown source {source}")
    return [source]


def build_index(repo: Path = REPO, drafts: Path = DRAFTS) -> list[dict]:
    """Stem + file text for every document already in repo/ or drafts/.

    Repo is scanned first so a seed wins over a draft with the same needle.
    """
    known = []
    for directory in (repo, drafts):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.document.twk")):
            stem = path.name[: -len(".document.twk")]
            known.append(
                {
                    "stem": stem,
                    "name": path.name,
                    "text": path.read_text(encoding="utf-8"),
                }
            )
    return known


def open_run(source: str, limit: int, dry_run: bool) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run = RUNS / stamp
    run.mkdir(parents=True, exist_ok=False)
    (run / "plan.json").write_text(
        json.dumps(
            {
                "source": source,
                "limit": limit,
                "dry_run": dry_run,
                "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return run


def save_bytes(run: Path, name: str, text: str) -> None:
    (run / name).write_text(text, encoding="utf-8")


def save_json(run: Path, name: str, obj: object) -> None:
    (run / name).write_text(
        json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
