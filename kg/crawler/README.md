# kg/crawler — feed crawler for TWK drafts

Stdlib-only (like `kg/server/`). No dependencies, no `requirements.txt`.

```
python kg/crawler/pipeline.py [--source innermost-loop|american-alchemy|cre|all] [--limit N] [--dry-run]
python kg/crawler/pipeline.py --fixture
```

`crawl.py` forwards to `pipeline.py`. The stages are `prepare.py` (run folder + already-have index), `crawl.py` (fetch raw entries only), `normalize.py` (one decision per feed entry), `pipeline.py` (write drafts), `assess.py` (score the decisions). `--dry-run` and `--fixture` still score; neither writes into `kg/drafts/`.

Each feed entry gets one outcome: `write`, `skip-same-stem`, `skip-different-stem`, `skip-no-date`, `skip-no-chapters`, `skip-chapters-external`, `skip-no-enclosure`, or `not-examined` (the `--limit` cut the tail). A live run stores the feed bytes, `decisions.json`, and `report.json` under `kg/crawler/runs/` (gitignored). `--fixture` replays `fixtures/*.xml` against `fixtures/expected.json` and is the regression gate.

Assess fails the run when a feed errors, an entry is unaccounted for, a write is invalid or has an empty section/chapter list, a graph field is filled, a skip is missing its reason fields, two writes claim the same stem, or a
file lands outside `kg/drafts/`. The scorecard (coverage, transparent refusals, stem collisions, noun garbage rate) is printed either way. Noun garbage — cross-sentence joins, month names, hyphenated verb phrases — is a score, not a gate. Candidate nouns stay on the decision and in the TODO; they are not written into the document.

Every draft is assembled by `normalize.base_doc()`. It owns what does not vary by
source: the four empty graph fields, the dictionary pointer, the `layer:extracted`
layer, and provenance. An adapter passes only the id scheme, `clock`, `media`,
`speakers` and `sources`. An adapter that needs to change something `base_doc` owns
is not a new source — it is a second kind of document, and that is a bigger decision
than adding a feed.

Note that a source object's type field is `type`, not `kind`: `twk_lib`'s graph
projection reads `s.get("type")`, so a source written with `kind` projects as
`type: None` and nothing complains.

Writes three files per entry into `kg/drafts/`:

| file | what it is |
|---|---|
| `<stem>.document.twk` | TWK 0.2 draft, validated with `twk_lib.validate()` |
| `<stem>.source.txt` | the raw fetched surface (issue body / video description) |
| `<stem>.TODO.md` | reviewer checklist + unresolved candidate proper nouns |

Never writes into `kg/repo/`. A same-stem file already in `repo/` or `drafts/` is
`skip-same-stem`. The same video id or canonical URL inside a differently named
file is `skip-different-stem` (slug drift, not a second draft). 1.5 s between
requests; `--limit` caps writes per source, and every entry past that cap is
`not-examined` rather than dropped.

## Sources

- **The Innermost Loop** — `https://theinnermostloop.substack.com/feed`, RSS 2.0,
  full body in `<content:encoded>`. Date comes from the issue **title**, not `pubDate`
  (the "September 20" issue is sent on the 21st). `clock.kind = text-locator`,
  `locatorScheme = anchor`, sections `p1..pN`.
- **American Alchemy** — Jesse Michels' longform channel, `channel_id`
  `UCuG2KzrIMe3qoNcuDVpwnXw`, resolved at runtime from `youtube.com/@JesseMichels`
  (`externalId`) and pinned as a fallback constant. `clock.kind = media-time`;
  chapters parsed from the `HH:MM:SS - Title` list in the description. An entry with
  no public chapter list (fewer than three `HH:MM:SS` lines) is skipped as
  `skip-no-chapters`, with the video id, description length, and how many
  timestamp lines the regex accepted.
- **CRE** — `https://cre.fm/feed/mp3/`, a Podlove feed. The adapter is general:
  any RSS carrying `psc:chapters` works, so pointing `PODLOVE_FEED` at another
  Podlove show needs no new code. `clock.kind = media-time`; chapters are the
  publisher's own `<psc:chapter start="HH:MM:SS.mmm" title="..."/>` elements, so
  nothing is scraped and nothing is inferred. `<itunes:duration>` fills
  `media.duration` and closes the last chapter, which is why step 6 of the promote
  checklist does not apply to this source. Marks carry **fractional seconds**;
  `hhmmss()` returns an int for a whole-second mark and a float only for a
  genuinely fractional one, so the YouTube adapters keep emitting integer bounds.

  Three refusals are its own. `skip-no-chapters` (fewer than three inline marks,
  and no chapter list published anywhere) carries `psc_chapter_count`.
  `skip-chapters-external` is the interesting one: the feed declares
  `<podcast:chapters url=...>` but we did not fetch that JSON, so the refusal
  carries the URL. Chapters that exist and were not fetched must never look like
  chapters that do not exist. Fetching them is a second request per episode and
  belongs in `crawl.py` behind a budget, not in `normalize.py`.
  `skip-no-enclosure` is an item with no audio artifact at all.

## Why the drafts stop short

`kg/RESEARCH-METHODS.md` §8: *"If a pipeline appears, it should emit the same
claim-kind split or it should not write to this directory."*

The `asserted-in-media` / `external-fact` split, the confidence rubric, and Wikidata
resolution — including the discipline of leaving a name as a deferred local id rather
than minting a fake Q-id — are editorial judgment. A crawler cannot do them honestly,
so it does not do them at all: `entities`, `claims`, `relations` and `timeline` are
written **empty**. The candidate proper nouns in the TODO are a dumb capitalized-phrase
scan, explicitly unresolved, and are never written into the document.

## draft → review → promote

1. Run the crawler. Read the `.TODO.md` and `.source.txt`.
2. Walk the names (§3.4): local id, type, Q-id or deferred-with-a-date.
3. Write contrast (`external-fact`) claims first, extracted (`asserted-in-media`) second,
   each with a quote a stranger can find on the public surface (§3.5).
4. Relations and timeline intervals — not one interval per chapter (§3.6).
5. Write `<stem>.dictionary.twk`; `composition.dictionary` already points at it.
6. For American Alchemy, set `media.duration` by hand — the feed does not report it.
   (Podlove sources already carry it.)
7. Replace `provenance` (drop `status: draft`, set `creator` to the human/seed pass).
8. Validate, move both files into `kg/repo/`, add the document to the series manifest.

A file in `kg/drafts/` is never a seed. It is a review artifact.
