# TWK 0.2 specification

Draft. MIME `application/vnd.twk+json`. File extension `.twk`. Encoding UTF-8 JSON.

The long-form draft lives alongside this repo in the working package (`TWK-0.2-Specification.docx` / `spec/TWK-0.2.md` in the local snapshot). This page is the map.

## A `.twk` file is a knowledge layer, not a player

A renderer can work offline from one file. A player looking at one segment of a work can load just the knowledge that belongs next to that segment.

Required keys: `twk`, `id`, `media.uri`. Everything else is progressive enhancement. Unknown fields MUST be ignored.

## Document kinds

| kind | Role |
| --- | --- |
| `document` | Self-contained artifact. The 0.1 shape. Default if omitted. |
| `manifest` | Small catalog: media, chapters, dictionary URI, shards. |
| `dictionary` | Things that exist independent of time: entities, speakers, sources, assets. |
| `shard` | Knowledge that intersects one address window: timeline, relations, claims, transcript slice. |

All four kinds share one ID space for a given work. `entity:alice-springs` in the dictionary is the same object in a shard.

## Address space

A bare JSON number is always seconds from media origin (0.1 compatible).

```json
731.42
```

An object can carry a locator for books and mixed clocks:

```json
{
  "t": 731.42,
  "locator": "epubcfi(/6/14!/4/2/8)",
  "scheme": "epubcfi",
  "page": 94,
  "frac": 0.328
}
```

`clock.kind` is `media-time`, `text-locator`, or `mixed`.

## Claims are not all the same kind of truth

If `claims` are present, `kind` is one of:

- `asserted-in-media` — a speaker or the text said this
- `external-fact` — an independent source asserts this
- `disputed` — sources or media disagree

A renderer MUST NOT present the first two as the same sentence.

## Windowed loading

`window(position, radius)` loads every shard whose span intersects `[position − radius, position + radius]`, then the dictionary if it is not already loaded. There is no live stream in 0.2.

## Rendering contract

```
load(resource)         → handle
contextAt(handle, pos) → Context
window(handle, pos, r) → Context
```

Context is chapters, speakers on-mic, mentioned entities, covering relations and claims, and attached assets — already filterable by salience.

## Split that stays reserved

- **CORE** is this format.
- **REPO** is community editing, history, moderation.
- **DISCOVERY** is how a publisher advertises that a TWK exists.

The moment CORE starts to know about accounts, it stops being a file format.

See also `conformance/TWK-0.2-conformance.md` and `schema/twk-0.2.schema.json`.
