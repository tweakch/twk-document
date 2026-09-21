# Research methods — TWK KG seeds

How the American Alchemy and Innermost Loop documents in `kg/repo/` were actually built.
Written 2026-09-22 after the second seed pass. This is a lab notebook, not a manifesto.

The point of TWK here is not to decide whether pyramids made ammonia or whether Claude is 26% of Anthropic R&D. The point is to keep a media object addressable, keep a claim attached to a span and a speaker, and keep the catalog world (Wikidata, standard works, established places) from collapsing into the guest's sentence.

## 0. What we inherited

The format is TWK 0.2. A document is a sidecar JSON file (`application/vnd.twk+json`) that points at media, does not replace it, and can be rendered by anyone.

The first seed was already on disk:

- `drumm-pyramids.document.twk` / `.dictionary.twk`
- YouTube `BSXdnsyCqxw`, Jesse Michels × Geoffrey Drumm, 2026-09-19
- Phase 2–3 only: public description + chapter titles
- Guest function claims (`asserted-in-media`); places stay catalog facts
- Kuromanta and White Horse Hills deferred without a Q-id

The authoring server (`kg/server/server.py`, port 8765) treats `kg/repo/` as the working store. On boot it lists every `.twk` in that directory. Validation, composition, `contextAt`, and the graph index live in `kg/server/twk_lib.py`.

V1 allowlists the validator will warn on if you wander off them:

- entity types: person, place, organization, work, event, concept, chemical, document
- claim kinds: `asserted-in-media`, `external-fact`, `disputed`
- relation types: mentions, asserts, about, producedChemical, extractedChemical, functionedAs, hadComponentFunction, instanceOf, created, contrastsWith, associatedWith, sameAs, cites, participantIn, tookPlaceAt, travel

If a new predicate is tempting, that is a spec change, not a seed change.

## 1. What Phase 2-3 means, in practice

The implementation plan split the work:

1. **Phase 1** — duration, media identity, speakers, clock.
2. **Phase 2** — structure (chapters) and named entities already in the public chapter list or description.
3. **Phase 3** — claims and relations, still from those public surfaces, not from a full transcript.

We did not run a transcript pass on the new files. A chapter title is evidence that a topic was addressed in that span. It is not evidence for the wording of a quote unless the same wording also appears in the public description.

That is why most extracted claims have confidence in the 0.25–0.45 band, and why contrast facts (Wikidata instance-of, published books, established bases) sit at 0.9+.

The number is a honesty marker, not a calibrated posterior.

## 2. Choosing the next documents

Two source streams were already in the project memory:

- **American Alchemy** — Jesse Michels, longform video, weekly, UAP / ancient tech / heterodox physics. Media-time clock.
- **The Innermost Loop** — Alex Wissner-Gross, daily Substack, high-velocity intelligence from the event horizon. Text-locator clock.

We did not scrape a catalog and emit a file per episode. We picked items that were public, recent enough to sit next to Drumm, rich in named entities that already have or clearly lack a Wikidata item, and structurally different enough that the second file would teach the format something the first file did not.

American Alchemy picks, 2026-09-22:

- Grant Cameron, 2026-09-15, YouTube `fpUa3xJN64Q`. Dense public chapter list, Wilson-Davis, consciousness-as-core-secret thesis that is easy to misfile as fact.
- Woods and Johnson Ellsworth reunion, 2026-09-07, YouTube `rjUdn6FklAU`. Two named witnesses, Ellsworth AFB Q536854, an event node that must not be promoted to this-happened, hypnotic-regression layer.

Innermost Loop picks:

- Welcome to September 20, 2026 — current issue on the day of the seed.
- Welcome to September 13, 2026 — Amodei We Must Pace the Frontier letter and the same-afternoon Musk / Altman / Hassabis chorus.

Skipped on purpose: members-only early releases, clip-channel cuts, Innermost Loop issues that were only a headline in the archive listing.

## 3. The public-source pass, step by step

For each pick the same walk, in this order.

### 3.1 Resolve the media object

American Alchemy: confirm the longform upload on youtube.com/@JesseMichels, not the clips channel. Record video id, publish date, duration from the last chapter end. Copy the full public description and the public chapter list with timestamps. Ignore auto-generated transcript snippets from search snippets.

Innermost Loop: open the canonical Substack URL. Take the visible issue text (both issues were readable without a paywall in this pass). Keep outbound links the issue itself uses as citations; those become sources, not extra claims.

Media identities: YouTube `{ type: youtube, value: {id} }`. Substack `{ type: url, value: {canonical} }`.

Duration for Cameron is 3:03:36 = 11016 seconds. Duration for Ellsworth is last chapter 2:46:38 = 9998 seconds. If YouTube later reports a different container duration, patch media.duration and the final chapter end. Do not invent a number.

### 3.2 Clock and address space

Video stays on `clock.kind = media-time`. A bare number is seconds from media origin.

Substack cannot honestly use seconds. TWK 0.2 already has text-locator. We used `clock.kind = text-locator` with `locatorScheme = anchor` and paragraph anchors p1-p4 matching the visible sections of the issue. That is a coarse grid, not a DOM promise.

### 3.3 Speakers

Every document gets a speaker list even when the guest is the author.

- American Alchemy: speaker:host = Jesse Michels, speaker:guest or named witnesses.
- Innermost Loop: speaker:author = Alex Wissner-Gross.

Speakers point at entities. Entities do not point back.

### 3.4 Entities, and the refusal to promote

For every name in the description or a chapter title: give it a stable local id; look for Wikidata; attach Q-id and source:wd-* if usable; otherwise keep the local id and write that fact in description. Do not mint a fake Q-id. Do not collapse Michael Johnson, Ellsworth SP onto some other Michael Johnson.

Put function claims on claims, not on the entity description. The Great Pyramid is a tomb/pyramid in Wikidata. Drumm's sulfuric-acid thesis does not live on that node. The Ellsworth 1977 incident is an event node; what they saw is a claim.

Deferred in this pass, same rule as Kuromanta: Grant Cameron, Mario Woods, this Michael Johnson, Yvonne Smith, Tim Taylor / Ron Pandolfi / Kit Green as used in chapter titles, Kingman crash as a catalog event, CIA Weird Desk as a concept not an org unit.

### 3.5 Claims

Two layers, always:

- layer:extracted — the media or the newsletter said this. Kind asserted-in-media. Quote from the public description when possible, otherwise from the chapter title with lower confidence.
- layer:contrast — the catalog says this. Kind external-fact.

Examples of the split:

- Red Pyramid produced ammonia — asserted-in-media (guest thesis).
- Ammonia is Wikidata Q4087 — external-fact.
- Cameron obtained the Wilson-Davis memo — asserted-in-media. We do not upgrade that to the memo is authentic.
- Wilbert Smith associated with Project Magnet — external-fact.
- Do Not Fear at Ellsworth — asserted-in-media.
- Ellsworth AFB is a USAF base — external-fact (Q536854).
- Anthropic says Claude leads 26% of its AI R&D — asserted-in-media.
- Hodge conjecture is a Millennium Prize problem — external-fact. OpenAI nears it is the other kind.

Confidence rubric actually used:

- 0.25-0.32 chapter title only
- 0.35-0.45 public description wording, still one source
- 0.55 description plus a well-known public biography fact
- 0.90-0.99 Wikidata / standard catalog identity

No claim in this pass is marked disputed. That kind is reserved for a later editorial layer that cites a specific contradiction.

### 3.6 Relations and timeline

Relations are the graph edges: asserts from guest to claim, participantIn from person to event, tookPlaceAt from event to place, associatedWith / created for catalog pairs, contrastsWith when a public alternative hypothesis is already in the chapter list.

Timeline intervals are the spans a player can ask contextAt(t) about. We did not emit one interval per chapter. Sponsor reads do not get a timeline row.

### 3.7 Sources

Every claim and almost every entity points at a sources id. Families: source:yt-description / source:yt-chapters, source:til-YYYY-MM-DD, source:wd-slug, plus a rare primary page the issue itself cites.

We did not add I-asked-a-model as a source. The model assembled the JSON. The sources are the pages a human can open.

### 3.8 Composition

Each document points at its dictionary with a relative URI `./{stem}.dictionary.twk`. Jesse Michels is duplicated on purpose across AA files with the same entity id. Do not invent entity:jesse-michels-2.

## 4. File by file

### grant-cameron

id twk:aa/episode/grant-cameron-2026-09-15. 61 chapters. Dictionary includes Cameron (local), Smith Q8000403, Lundahl Q4798444, Lazar Q887942, CIA, Project Magnet, Wilson-Davis as a work, Charlie Red Star as an event, Weird Desk as a concept. Extracted: 1975 entry, Wilson-Davis leak, Weird Desk, consciousness-as-core-secret, time-travel-over-hardware. Contrast: Smith-Magnet, Lundahl-CIA, CE3K as a 1977 film.

The title on the file is the public upload title. That is the media object's name, not an endorsement of the sentence inside it.

### ellsworth-woods-johnson

id twk:aa/episode/ellsworth-woods-johnson-2026-09-07. 59 chapters. Four speakers. Event node entity:ellsworth-1977 with aliases November-5 / L9. Extracted: both men as participants, nine hours, Do Not Fear, dual regression. Contrast: Ellsworth is a USAF base, CE3K is a 1977 film. No Doty-wrote-the-L9-document claim was written from a chapter title alone.

### til-2026-09-20

id twk:til/issue/2026-09-20. Four section-chapters p1-p4. AWG as Q23727955. Extracted claims follow the issue's own attributions. Contrast: Hodge is a Millennium problem; AWG is a catalogued person.

### til-2026-09-13

id twk:til/issue/2026-09-13. Extracted claims are almost all quoted speech. Alignment aristocracy and safety cartel are concept nodes, explicitly not an endorsement. Andy Burnham is catalogued as a person; the issue's office claim stays off the entity node.

### Manifests

american-alchemy.manifest.twk indexes Drumm, Cameron, Ellsworth. innermost-loop.manifest.twk indexes the two issues.

## 5. Assembly and validation

JSON matched the Drumm seed shape. Then validate() against kg/server/twk_lib.py. Every new file in this pass returned ok=True with empty errors and empty warnings.

We did not compute integrity.contentHash. That belongs to a release step, not a seed step.

## 6. What this pass did not do

- No full transcript alignment.
- No salience model. Salience numbers on timeline events are editorial hints.
- No geocoding beyond well-known catalog coordinates.
- No series-wide dictionary merge.
- No members-only cuts.
- No Innermost Loop audio edition / third-party YouTube digest.
- No promotion of guest hypotheses into external-fact because a lot of people say it.

A Phase 4 transcript pass should keep every existing claim id stable, tighten quotes to uttered sentences, add start/end where we only had a chapter envelope, raise confidence only when the wording is in the tape, and introduce disputed only with a cited contrast source.

## 7. How to add the next episode without making a mess

1. Pick one public media object. Write its id first.
2. Fill media and clock before any entities.
3. Paste the public chapter list or the issue's visible sections. Convert timestamps to seconds.
4. Walk names with a notebook: local id, type, Wikidata or deferred, whether a function claim is being smuggled into the description.
5. Write contrast facts first.
6. Write extracted claims second, each with a quote a stranger can find on the public surface.
7. Point the document at `./{stem}.dictionary.twk`.
8. Drop both files in kg/repo/. Run validate. Fix duplicate ids before you look at the graph.
9. Add the document to the series manifest. Do not create a second manifest for the same series.

If a name cannot be resolved, leave it local and write the date you looked. That sentence in the description is the whole method.

## 8. Provenance of this note

This file describes the 2026-09-22 seed pass that added Cameron, Ellsworth, TIL 2026-09-13, and TIL 2026-09-20 to kg/repo/, plus the two series manifests.

It does not describe a future automated pipeline. If a pipeline appears, it should emit the same claim-kind split or it should not write to this directory.
