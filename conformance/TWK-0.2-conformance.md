# TWK 0.2 conformance cases

These cases are the real contract. A client that only implements a pretty UI against one example file is not a TWK client.

## Valid

| Case | Expected |
|---|---|
| Minimal document (`twk`, `id`, `media.uri`) | valid |
| `kind` omitted | treat as `document` |
| Unknown entity type | valid, render as generic entity |
| Unknown event type | valid, may hide from UI |
| Unknown media type | valid |
| Missing optional fields | valid |
| Bare-number timestamps (0.1 style) | valid seconds |
| Object positions with `locator` | valid |
| Timeline intervals overlapping | valid |
| Extra keys at any level | valid, ignore |
| `x` extension bag present | valid |
| Manifest with shards and no timeline | valid |
| Shard that omits entities (dictionary lives elsewhere) | valid |
| Dictionary with entities and no timeline | valid |
| 0.1 document with `"twk": "0.1"` | 0.2 reader SHOULD load if it understands 0.1 |

## Invalid

| Case | Expected |
|---|---|
| Missing `twk` | invalid |
| Missing `id` | invalid |
| Missing `media.uri` | invalid |
| Duplicate entity IDs in one ID space | invalid |
| Duplicate relation / claim / source / asset IDs | invalid |
| Timeline not sorted by start | invalid |
| `end` before `start` on the same clock | invalid |
| Negative seconds | invalid |
| `confidence` or `salience` outside 0–1 | invalid |
| Shard whose media identity does not match the manifest | invalid |
| Two entities with the same `id` across dictionary + shard | invalid (shared ID space) |

## Behavioural

| Case | Expected |
|---|---|
| `contextAt(t)` with no covering interval | empty context, not an error |
| `window(t, 90s)` against a manifest | load every shard that intersects `[t-90, t+90]` |
| Overlapping shards | merge by ID; later shard in the array does not silently overwrite unless IDs collide (collisions are invalid) |
| Event with `salience` | UI MAY hide events below an implementation threshold |
| `kind: asserted-in-media` vs `external-fact` | MUST NOT be presented as the same kind of truth |
