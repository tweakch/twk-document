# TWK — Temporal Knowledge Document

A portable, immutable, addressable knowledge layer for media: audio, video, lectures, and e-books.

A `.twk` file is not a player, not a chat overlay, and not a live model call. It is a sidecar knowledge document that travels with a work. A renderer can operate offline from one file. A player that is only looking at the current ninety seconds — or page 94 of an EPUB — can load just the knowledge that belongs next to that window.

MIME type: `application/vnd.twk+json`

This repository is the 0.2 CORE snapshot: spec, schema, conformance cases, examples, a reference player, and a claim-aware knowledge-graph pilot.

## What 0.2 adds

0.1 already said: self-contained, media-independent, time-addressable, immutable, source-aware, renderer-neutral, no mandatory server.

0.2 makes CORE honest about how a real client consumes knowledge:

- **Address space beyond seconds.** EPUB CFI, page numbers, and other locators sit next to the clock.
- **Document kinds.** `document` (the 0.1 shape), `manifest` (catalog for a long work), `dictionary` (things that exist, independent of time), `shard` (knowledge that intersects one address window).
- **Speakers and chapters** as first-class structure.
- **Confidence and salience** on events and claims.
- **Claim kind distinction.** `asserted-in-media` is not the same truth as `external-fact`.
- **Windowed loading.** `window(t, 90s)` against a manifest loads only intersecting shards.

REPO (community revision store) and DISCOVERY (feeds, indexes) remain out of CORE.

## Layout

```
spec/            TWK 0.2 specification
schema/          JSON Schema (twk-0.2.schema.json)
conformance/     Valid / invalid / behavioural cases
examples/        Minimal, geography, ebook, manifest, dictionary, shard
player/          Vite 6 reference player (Leaflet map + contextAt)
kg/              Claim-aware KG plan + American Alchemy Drumm/pyramids pilot
```

## Quick start — player

```bash
cd player
npm install
npm run dev
```

Open the local Vite URL. Presets load the example documents from `player/public/data/`. You can also drop any `.twk` file onto the Open control.

## Quick start — validate

The KG server ships a small library that understands 0.2 kinds and window loading:

```bash
cd kg/server
python server.py
```

Point the admin UI at a document, dictionary, or manifest. The schema file is also at `schema/twk-0.2.schema.json` for any JSON Schema validator.

## Principles (normative)

From 0.1, still in force:

- Self-contained — a renderer can operate offline
- Media-independent — audio, video, lecture, audiobook, e-book, livestream recording
- Addressable — every contextual event maps onto the work’s address space
- Immutable — a TWK document is a particular knowledge revision
- Source-aware — factual information can carry provenance
- Extensible — unknown fields and types MUST NOT break clients
- Renderer-neutral — TWK describes what is relevant, not how a UI must look
- Cheap to author and cheap to parse
- No mandatory server
- The media resource remains the source of experience; TWK is a layer on top

## Knowledge graph pilot

`kg/` is a public-source, Wikidata-aligned graph intended to feed TWK layers for *American Alchemy* episodes (Jesse Michels; UAP, ancient tech, frontier physics interviews). Guest hypotheses stay `asserted-in-media`. They are never promoted to facts by being written down in the sidecar.

Pilot episode: Drumm / pyramids (`BSXdnsyCqxw`). Seed files:

- `kg/american-alchemy/drumm-pyramids.dictionary.twk`
- `kg/american-alchemy/drumm-pyramids.document.twk`

## Status

Draft. Version field is `"twk": "0.2"`. A 0.2 reader SHOULD still load a 0.1 document.

## License

MIT. See [LICENSE](LICENSE).
