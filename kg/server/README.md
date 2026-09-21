# TWK KG server

Stdlib-only authoring desk for TWK 0.2 documents.

```bash
cd kg/server
python3 server.py
```

Open http://127.0.0.1:8765/admin

Working store is `kg/repo/` (`.twk` files). The American Alchemy pilot seeds are also under `kg/american-alchemy/`. Saving a `drumm-pyramids*` file writes both places.

API:

- `GET /api/docs` — list files
- `GET /api/docs/{file}` — load + validate
- `PUT /api/docs/{file}` — save
- `GET /api/compose?file=` — merge dictionary into document
- `GET /api/graph?file=` — nodes/edges
- `GET /api/context?file=&t=` — `contextAt(t)`
- `POST /api/validate` — `{ "doc": … }`
- `POST /api/patch` — upsert one item into a collection
