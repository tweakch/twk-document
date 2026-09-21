"""Fetch a feed and emit raw entries. No skip decisions and no draft writes.

`python kg/crawler/crawl.py` forwards to `pipeline.py`.
"""

from __future__ import annotations

import re
import time
import urllib.request
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) twk-kg-crawler/0.1"
DELAY = 1.5

TIL_FEED = "https://theinnermostloop.substack.com/feed"
AA_CHANNEL_PAGE = "https://www.youtube.com/@JesseMichels"
# Resolved 2026-09-22 from the channel page (externalId). Longform channel, not the clips one.
AA_CHANNEL_ID = "UCuG2KzrIMe3qoNcuDVpwnXw"
AA_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"

# Podlove/Podcasting 2.0 chapter feed. The adapter is general -- any RSS carrying
# psc:chapters works -- so the show is a constant, not a second code path.
PODLOVE_FEED = "https://cre.fm/feed/mp3/"

NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
    "psc": "http://podlove.org/simple-chapters",
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "podcast": "https://podcastindex.org/namespace/1.0",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read()
    time.sleep(DELAY)
    return raw.decode("utf-8", "replace")


def resolve_channel_id() -> tuple[str, str | None]:
    """Best-effort; falls back to the pinned constant if the page is unreachable."""
    try:
        html = fetch(AA_CHANNEL_PAGE)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! channel page unreachable ({exc}); using pinned id")
        return AA_CHANNEL_ID, None
    ids = re.findall(r'(?:channel_id=|"externalId":")(UC[\w-]{22})', html)
    return (ids[0] if ids else AA_CHANNEL_ID), html


def load_til(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS feed has no channel")
    entries = []
    for item in channel.findall("item"):
        link = (item.findtext("link") or "").strip()
        entries.append(
            {
                "source": "innermost-loop",
                "id": link,
                "title": (item.findtext("title") or "").strip(),
                "url": link,
                "published": item.findtext("pubDate") or "",
                "body": item.findtext("content:encoded", "", NS) or item.findtext("description") or "",
                "creator": (item.findtext("dc:creator", "", NS) or "").strip(),
            }
        )
    return entries


def load_aa(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    entries = []
    for entry in root.findall("atom:entry", NS):
        vid = entry.findtext("yt:videoId", "", NS) or ""
        group = entry.find("media:group", NS)
        desc = (group.findtext("media:description", "", NS) if group is not None else "") or ""
        entries.append(
            {
                "source": "american-alchemy",
                "id": vid,
                "title": (entry.findtext("atom:title", "", NS) or "").strip(),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "published": (entry.findtext("atom:published", "", NS) or "")[:10],
                "body": desc,
                "creator": "",
            }
        )
    return entries


def load_podlove(xml_text: str) -> list[dict]:
    """Podlove RSS -> entries. Chapter marks stay as the publisher wrote them.

    The start strings are NOT converted here: what counts as a chapter list, and
    what a mark means in seconds, is normalize's judgment. This stage only reports
    what the feed said, so a frozen feed replays byte-for-byte.
    """
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS feed has no channel")
    author = (channel.findtext("itunes:author", "", NS) or "").strip()
    language = (channel.findtext("language") or "").strip().split("-")[0]
    entries = []
    for item in channel.findall("item"):
        link = (item.findtext("link") or "").strip()
        enclosure = item.find("enclosure")
        external = item.find("podcast:chapters", NS)
        entries.append(
            {
                "source": "cre",
                "id": (item.findtext("guid") or "").strip(),
                "title": (item.findtext("title") or "").strip(),
                "url": link,
                "published": item.findtext("pubDate") or "",
                "body": item.findtext("description") or "",
                "creator": author,
                "language": language,
                "duration": (item.findtext("itunes:duration", "", NS) or "").strip(),
                "enclosure": dict(enclosure.attrib) if enclosure is not None else {},
                "chapters_url": (external.get("url") or "") if external is not None else "",
                "chapters_raw": [
                    {"start": chapter.get("start") or "", "title": (chapter.get("title") or "").strip()}
                    for chapter in item.findall("psc:chapters/psc:chapter", NS)
                ],
            }
        )
    return entries


def fetch_podlove(feed_url: str = PODLOVE_FEED) -> tuple[str, list[dict]]:
    xml_text = fetch(feed_url)
    return xml_text, load_podlove(xml_text)


def fetch_til() -> tuple[str, list[dict]]:
    xml_text = fetch(TIL_FEED)
    return xml_text, load_til(xml_text)


def fetch_aa(channel_id: str) -> tuple[str, list[dict]]:
    xml_text = fetch(AA_FEED.format(channel_id))
    return xml_text, load_aa(xml_text)


def main() -> int:
    from pipeline import main as pipeline_main

    return pipeline_main()


if __name__ == "__main__":
    raise SystemExit(main())
