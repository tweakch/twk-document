"""Pure: raw feed entries -> one decision list. Nothing is written here.

Candidate nouns are a field on write decisions. They are not a pipeline stage
and they are never copied into the document.
"""

from __future__ import annotations

import html
import re
from datetime import datetime

MONTHS = "january february march april may june july august september october november december".split()

TIMESTAMP_RE = re.compile(
    r"\s*(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?)\s*[-–—:)\]]?\s+(\S.*?)\s*$"
)

BOILERPLATE = re.compile(
    r"(?i)(thanks for reading|subscribe|share this post|leave a comment|upgrade to paid|"
    r"you're currently a free subscriber|give a gift)"
)

STOP = set(
    "The A An And Or But If In On At To For Of With From This That These Those It Its We You I He "
    "She They There Here What When Where Why How So As By Is Are Was Were Be Been Has Have Had Not "
    "No Now New Thanks Subscribe Welcome".split()
)

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}$")


def strip_tags(value: str) -> str:
    value = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", value)
    value = re.sub(r"(?i)<br[^>]*>", "\n", value)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).replace("\xa0", " ").strip()


def slugify(value: str, words: int = 4) -> str:
    parts = re.sub(r"[^a-z0-9]+", " ", value.lower()).split()
    return "-".join(parts[:words]) or "untitled"


def hhmmss(timestamp: str) -> int | float:
    """`HH:MM:SS`, `MM:SS`, and the fractional `HH:MM:SS.mmm` Podlove writes.

    Returns an int for a whole-second mark so the YouTube adapters keep emitting
    integer chapter bounds; only a genuinely fractional mark yields a float.
    """
    parts = timestamp.strip().replace(",", ".").split(":")
    seconds = float(parts[-1])
    whole = [int(part) for part in parts[:-1]]
    while len(whole) < 2:
        whole.insert(0, 0)
    total = whole[0] * 3600 + whole[1] * 60 + seconds
    return int(total) if total.is_integer() else round(total, 3)


def chapter_marks(description: str) -> list[dict]:
    marks = []
    for line in description.splitlines():
        match = TIMESTAMP_RE.match(line)
        if match:
            marks.append({"t": hhmmss(match.group(1)), "title": match.group(2)})
    return marks


def parse_chapters(description: str) -> list[dict]:
    """`12:34 - Some title` lines -> chapters in seconds. Fewer than 3 marks -> []."""
    marks = chapter_marks(description)
    if len(marks) < 3:
        return []
    chapters = []
    for index, mark in enumerate(marks):
        chapter = {
            "id": f"ch:{index + 1:02d}-{slugify(mark['title'], 3)}",
            "title": mark["title"],
            "start": mark["t"],
        }
        if index + 1 < len(marks):
            chapter["end"] = marks[index + 1]["t"]
        chapters.append(chapter)
    return chapters


def podlove_chapters(marks: list[dict], duration: int | float | None) -> list[dict]:
    """psc:chapter marks -> chapters. Fewer than 3 usable marks -> [].

    Unlike the description scrapes, these are authored chapter elements, so the
    only judgment left is the same >=3 floor and where the last one ends. The
    feed's own itunes:duration closes it; without one the last chapter stays open
    rather than being guessed.
    """
    usable = []
    for mark in marks:
        try:
            start = hhmmss(mark["start"])
        except (ValueError, KeyError, AttributeError):
            continue
        title = (mark.get("title") or "").strip()
        if title:
            usable.append({"t": start, "title": title})
    if len(usable) < 3:
        return []
    chapters = []
    for index, mark in enumerate(usable):
        chapter = {
            "id": f"ch:{index + 1:02d}-{slugify(mark['title'], 3)}",
            "title": mark["title"],
            "start": mark["t"],
        }
        if index + 1 < len(usable):
            chapter["end"] = usable[index + 1]["t"]
        elif duration:
            chapter["end"] = duration
        chapters.append(chapter)
    return chapters


def podlove_stem(link: str, guid: str) -> str:
    """The publisher's own episode slug from the permalink; guid tail otherwise."""
    tail = (link or "").rstrip("/").rsplit("/", 1)[-1].split("?")[0]
    return slugify(tail, 8) if tail else slugify(guid, 8)


def parse_sections(content_html: str) -> list[dict]:
    """Substack issue body -> p1..pN. Headings win; otherwise substantive paragraphs."""
    heads = re.findall(r"(?is)<h([1-3])[^>]*>(.*?)</h\1>", content_html)
    if heads:
        texts = [strip_tags(text) for _, text in heads]
    else:
        texts = []
        for paragraph in re.findall(r"(?is)<p[^>]*>(.*?)</p>", content_html):
            text = strip_tags(paragraph)
            if len(text) < 60 or BOILERPLATE.search(text):
                continue
            texts.append(re.split(r"(?<=[.!?])\s", text)[0][:120])
    sections = []
    for index, text in enumerate(texts, 1):
        sections.append(
            {
                "id": f"ch:p{index}",
                "title": text,
                "start": {"scheme": "anchor", "locator": f"p{index}", "page": index},
                "end": {"scheme": "anchor", "locator": f"p{index}", "page": index},
            }
        )
    return sections


def candidate_nouns(text: str) -> list[str]:
    """Dumb capitalized-phrase scan. Suggestions for a human, never written into the doc."""
    seen: dict[str, int] = {}
    for match in re.finditer(r"\b([A-Z][\w'&.-]*(?:\s+(?:of|the|and|de)?\s*[A-Z][\w'&.-]*)*)", text):
        phrase = match.group(1).strip()
        if phrase in STOP or len(phrase) < 3 or phrase.isupper() and len(phrase) < 3:
            continue
        head = phrase.split()[0]
        if head in STOP and len(phrase.split()) == 1:
            continue
        seen[phrase] = seen.get(phrase, 0) + 1
    return [key for key, _ in sorted(seen.items(), key=lambda item: (-item[1], item[0]))]


def til_date(title: str, published: str) -> str:
    """The issue names its own date; pubDate is the send time and can be the next day."""
    match = re.search(r"(" + "|".join(MONTHS) + r")\s+(\d{1,2}),?\s+(\d{4})", title, re.I)
    if match:
        month = MONTHS.index(match.group(1).lower()) + 1
        return f"{match.group(3)}-{month:02d}-{int(match.group(2)):02d}"
    return (published or "")[:10]


def iso_from_rfc(published: str) -> str:
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(published.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""


def aa_slug(title: str) -> str:
    """`"Quoted hook!" - Guest Name` -> guest-name; otherwise the leading words."""
    match = re.search(r"[-–—]\s*([A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*){0,3})\s*$", title)
    if match:
        return slugify(match.group(1))
    return slugify(re.sub(r"[\"“”]", "", title), 4)


def lookup(known: list[dict], stem: str, needle: str) -> tuple[str, dict] | None:
    """Same-stem wins over a shared video id or canonical URL in a differently named file."""
    for item in known:
        if item["stem"] == stem:
            return "skip-same-stem", item
    if needle:
        for item in known:
            if needle in item["text"]:
                return "skip-different-stem", item
    return None


def _base(entry: dict, index: int, outcome: str) -> dict:
    return {
        "source": entry["source"],
        "entry_index": index,
        "id": entry.get("id") or "",
        "title": entry.get("title") or "",
        "outcome": outcome,
    }


def _exists(decision: dict, stem: str, needle: str, hit: dict) -> dict:
    decision["stem"] = stem
    decision["existing"] = hit["name"]
    decision["needle"] = needle
    return decision


def _reservation(decision: dict) -> dict:
    """The index record a write leaves behind, in the shape build_index() produces."""
    return {
        "stem": decision["stem"],
        "name": f"{decision['stem']}.document.twk",
        "text": decision.get("needle") or "",
    }


def reserve(known: list[dict], decisions: list[dict]) -> list[dict]:
    """Fold this batch's writes into the index so a LATER source cannot reuse the stem.

    decide() reserves only within its own call, against a copy. Nothing used to
    carry across sources, so two sources could each resolve to the same stem, both
    report outcome=write, and the second would silently overwrite the first on
    disk. The caller reserves between sources; decide() stays pure.
    """
    for decision in decisions:
        if decision["outcome"] == "write":
            known.append(_reservation(decision))
    return known


def provenance(fetched: str, note: str) -> dict:
    return {
        "revision": 0,
        "created": fetched,
        "creator": {"type": "agent", "id": "twk-kg-crawler"},
        "status": "draft",
        "note": "MACHINE-GENERATED DRAFT. entities/claims/relations/timeline deliberately empty; "
        "claim-kind split and Wikidata resolution require a human review pass. " + note,
    }


def base_doc(
    *,
    doc_id: str,
    title: str,
    stem: str,
    chapters: list[dict],
    clock: dict,
    media: dict,
    speakers: list[dict],
    sources: list[dict],
    layer_title: str,
    note: str,
    fetched: str,
    language: str = "en",
) -> dict:
    """Everything a draft carries regardless of source. Adapters overlay the rest.

    Shared and not an adapter's business: the four empty graph fields
    (RESEARCH-METHODS.md sec 8), the dictionary pointer, the extracted layer, and
    provenance. An adapter that needs to change one of those is not a new source,
    it is a second kind of document.

    Adapters supply only what genuinely differs: the id scheme, the clock, the
    media artifact, who speaks, and what was cited.
    """
    return {
        "twk": "0.2",
        "id": doc_id,
        "kind": "document",
        "title": title,
        "language": language,
        "clock": clock,
        "media": media,
        "composition": {"dictionary": {"uri": f"./{stem}.dictionary.twk"}},
        "structure": {"chapters": chapters},
        "speakers": speakers,
        "layers": [
            {
                "id": "layer:extracted",
                "role": "extracted",
                "agent": "twk-kg-crawler",
                "title": layer_title,
            }
        ],
        "entities": [],
        "claims": [],
        "relations": [],
        "timeline": [],
        "sources": sources,
        "provenance": provenance(fetched, note),
    }


def build_til_doc(entry: dict, stem: str, date: str, sections: list[dict], fetched: str) -> dict:
    title = entry["title"]
    link = entry["url"]
    return base_doc(
        doc_id=f"twk:til/issue/{date}",
        title=f"{title} — The Innermost Loop",
        stem=stem,
        chapters=sections,
        clock={"kind": "text-locator", "locatorScheme": "anchor"},
        media={
            "uri": link,
            "type": "text",
            "mime": "text/html",
            "locatorScheme": "anchor",
            "published": date,
            "identities": [{"type": "url", "value": link}],
        },
        speakers=[
            {
                "id": "speaker:author",
                "name": entry.get("creator") or "Alex Wissner-Gross",
                "role": "host",
                "entity": "entity:alex-wissner-gross",
            }
        ],
        sources=[
            {
                "id": f"source:{stem}",
                "type": "web",
                "title": f"The Innermost Loop — {title}",
                "uri": link,
                "retrieved": fetched[:10],
            },
            {
                "id": "source:til-feed",
                "type": "web",
                "title": "The Innermost Loop RSS feed",
                "uri": "https://theinnermostloop.substack.com/feed",
                "retrieved": fetched[:10],
            },
        ],
        layer_title="draft from public Substack issue text",
        note=(
            f"Anchors p1..p{len(sections)} derived from the issue's own paragraph sections; "
            "titles are each section's lede sentence, not editorial headings."
        ),
        fetched=fetched,
    )


def build_aa_doc(entry: dict, stem: str, chapters: list[dict], fetched: str) -> dict:
    watch = entry["url"]
    return base_doc(
        doc_id=f"twk:aa/episode/{stem}",
        title=entry["title"],
        stem=stem,
        chapters=chapters,
        clock={"kind": "media-time"},
        media={
            "uri": watch,
            "type": "video",
            "mime": "video/mp4",
            "published": entry["published"],
            "identities": [{"type": "youtube", "value": entry["id"]}],
        },
        speakers=[
            {
                "id": "speaker:host",
                "name": "Jesse Michels",
                "role": "host",
                "entity": "entity:jesse-michels",
            }
        ],
        sources=[
            {
                "id": "source:yt-description",
                "type": "video",
                "uri": watch,
                "title": "YouTube description and chapters",
                "publisher": "Jesse Michels / American Alchemy",
                "retrieved": fetched[:10],
            },
            {
                "id": "source:yt-chapters",
                "type": "video",
                "uri": watch,
                "title": "Public YouTube chapter list",
                "publisher": "Jesse Michels / American Alchemy",
                "retrieved": fetched[:10],
            },
        ],
        layer_title="draft from public description + chapters only",
        note=(
            "No media.duration: the feed does not report it and the last chapter only gives a "
            "start. Guest speaker not added — the feed does not name roles. Slug is provisional."
        ),
        fetched=fetched,
    )


def build_podlove_doc(
    entry: dict, stem: str, chapters: list[dict], duration: int | float | None, fetched: str
) -> dict:
    enclosure = entry.get("enclosure") or {}
    link = entry.get("url") or ""
    media = {
        "uri": enclosure.get("url") or link,
        "type": "audio",
        "mime": enclosure.get("type") or "audio/mpeg",
        "published": iso_from_rfc(entry.get("published") or ""),
        "identities": [
            {"type": "guid", "value": entry.get("id") or ""},
            {"type": "url", "value": link},
        ],
    }
    if duration:
        media["duration"] = duration
    speakers = []
    if entry.get("creator"):
        # No entity id: the feed names the show's author, and resolving that name
        # to a Q-id is the review pass's job (RESEARCH-METHODS.md sec 3.4).
        speakers.append({"id": "speaker:host", "name": entry["creator"], "role": "host"})
    return base_doc(
        doc_id=f"twk:cre/episode/{stem}",
        title=entry.get("title") or stem,
        stem=stem,
        chapters=chapters,
        clock={"kind": "media-time"},
        media=media,
        speakers=speakers,
        sources=[
            {
                "id": f"source:{stem}",
                "type": "audio",
                "uri": link,
                "title": entry.get("title") or stem,
                "retrieved": fetched[:10],
            },
            {
                "id": "source:psc-chapters",
                "type": "audio",
                "uri": link,
                "title": "Podlove Simple Chapters published in the episode's feed item",
                "retrieved": fetched[:10],
            },
        ],
        layer_title="draft from published psc:chapters only",
        note=(
            "Chapters are the publisher's own psc:chapter elements, not a scrape. "
            + (
                "media.duration and the last chapter's end come from itunes:duration."
                if duration
                else "No itunes:duration, so the last chapter has no end."
            )
            + " Speaker is the feed's itunes:author, unresolved."
        ),
        fetched=fetched,
        language=entry.get("language") or "en",
    )


def _classify_podlove(entry: dict, index: int, known: list[dict], fetched: str) -> dict:
    marks = entry.get("chapters_raw") or []
    enclosure = entry.get("enclosure") or {}
    if not enclosure.get("url"):
        decision = _base(entry, index, "skip-no-enclosure")
        decision["chapters_raw_count"] = len(marks)
        return decision
    try:
        duration = hhmmss(entry["duration"]) if entry.get("duration") else None
    except ValueError:
        duration = None
    chapters = podlove_chapters(marks, duration)
    if not chapters:
        # An external <podcast:chapters url=...> is a real chapter list we chose not
        # to fetch, not an absent one. Name it so the two are never confused.
        outcome = "skip-chapters-external" if entry.get("chapters_url") else "skip-no-chapters"
        decision = _base(entry, index, outcome)
        decision.update(
            {
                "psc_chapter_count": len(marks),
                "chapters_url": entry.get("chapters_url") or "",
                "enclosure_url": enclosure.get("url") or "",
            }
        )
        return decision
    stem = podlove_stem(entry.get("url") or "", entry.get("id") or "")
    needle = entry.get("id") or ""
    found = lookup(known, stem, needle)
    decision = _base(entry, index, found[0] if found else "write")
    if found:
        return _exists(decision, stem, needle, found[1])
    surface = strip_tags(entry.get("body") or "")
    decision.update(
        {
            "stem": stem,
            "needle": needle,
            "structure_count": len(chapters),
            "nouns": candidate_nouns(surface),
            "surface": surface,
            "doc": build_podlove_doc(entry, stem, chapters, duration, fetched),
        }
    )
    return decision


def _classify_til(entry: dict, index: int, known: list[dict], fetched: str) -> dict:
    published = iso_from_rfc(entry.get("published") or "")
    date = til_date(entry.get("title") or "", published)
    if not DATE_RE.match(date):
        return _base(entry, index, "skip-no-date")
    stem = f"til-{date}"
    needle = entry.get("url") or ""
    found = lookup(known, stem, needle)
    decision = _base(entry, index, found[0] if found else "write")
    if found:
        return _exists(decision, stem, needle, found[1])
    sections = parse_sections(entry.get("body") or "")
    surface = strip_tags(entry.get("body") or "")
    decision.update(
        {
            "stem": stem,
            "needle": needle,
            "structure_count": len(sections),
            "nouns": candidate_nouns(surface),
            "surface": surface,
            "doc": build_til_doc(entry, stem, date, sections, fetched),
        }
    )
    return decision


def _classify_aa(entry: dict, index: int, known: list[dict], fetched: str) -> dict:
    body = entry.get("body") or ""
    marks = chapter_marks(body)
    chapters = parse_chapters(body)
    if not chapters:
        decision = _base(entry, index, "skip-no-chapters")
        decision.update(
            {
                "description_length": len(body),
                "timestamp_lines": len(marks),
            }
        )
        return decision
    published = entry.get("published") or ""
    stem = f"{aa_slug(entry.get('title') or '')}-{published}"
    needle = entry.get("id") or ""
    found = lookup(known, stem, needle)
    decision = _base(entry, index, found[0] if found else "write")
    if found:
        return _exists(decision, stem, needle, found[1])
    decision.update(
        {
            "stem": stem,
            "needle": needle,
            "structure_count": len(chapters),
            "nouns": candidate_nouns(body),
            "surface": body,
            "doc": build_aa_doc(entry, stem, chapters, fetched),
        }
    )
    return decision


def decide(entries: list[dict], known: list[dict], limit: int, fetched: str) -> list[dict]:
    """One outcome per entry. `limit` caps writes; skips still count as examined.

    Once the write cap is reached, every remaining entry is `not-examined`.
    A stem written earlier in this same list is reserved, so a second entry
    that resolves to it is `skip-same-stem` even before the file exists.
    """
    writes = 0
    decisions = []
    seen = list(known)
    limit = max(0, limit)
    for index, entry in enumerate(entries):
        if writes >= limit:
            decisions.append(_base(entry, index, "not-examined"))
            continue
        classify = CLASSIFIERS.get(entry.get("source"), _classify_til)
        decision = classify(entry, index, seen, fetched)
        decisions.append(decision)
        if decision["outcome"] == "write":
            writes += 1
            seen.append(_reservation(decision))
    return decisions


CLASSIFIERS = {
    "innermost-loop": _classify_til,
    "american-alchemy": _classify_aa,
    "cre": _classify_podlove,
}
