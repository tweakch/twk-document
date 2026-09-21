# TWK knowledge graph pilot

Public-source, Wikidata-aligned graph layers.

- *American Alchemy* (Jesse Michels): longform video, media-time clock.
- *The Innermost Loop* (Alex Wissner-Gross): daily Substack, text-locator clock.

Guest / newsletter hypotheses stay `asserted-in-media`.
Catalog identities (Wikidata people, places, orgs, works) live as `external-fact`.

## Run the server

```bash
cd kg/server
python3 server.py
```

Open http://127.0.0.1:8765/admin

The working store is `kg/repo/`. On boot it lists every `.twk` there.

```
kg/server/server.py          HTTP API (stdlib)
kg/server/twk_lib.py         validate / compose / contextAt / graph
kg/server/static/admin.html  authoring desk
kg/repo/                     document + dictionary + manifest seeds
schema/twk-0.2.schema.json   repo root
```

## Current seeds (2026-09-22)

American Alchemy

- Drumm / pyramids — `BSXdnsyCqxw` (2026-09-19)
- Grant Cameron — `fpUa3xJN64Q` (2026-09-15)
- Ellsworth / Woods–Johnson — `rjUdn6FklAU` (2026-09-07)

The Innermost Loop

- Welcome to September 20, 2026
- Welcome to September 13, 2026
