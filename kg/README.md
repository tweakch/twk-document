# TWK knowledge graph pilot

Public-source, Wikidata-aligned graph for *American Alchemy* episodes.
Guest hypotheses stay `asserted-in-media`.

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
kg/repo/drumm-pyramids.document.twk
schema/twk-0.2.schema.json   repo root
```

Pilot episode: Drumm / pyramids, YouTube `BSXdnsyCqxw`.
