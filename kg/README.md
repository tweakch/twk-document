# TWK knowledge graph pilot

Public-source, Wikidata-aligned graph intended to feed TWK layers for *American Alchemy* episodes (Jesse Michels; UAP, ancient tech, frontier physics interviews).

Guest hypotheses stay `asserted-in-media`. Writing them into a sidecar does not promote them to facts.

## Run the server

```bash
cd kg/server
python3 server.py
```

Open http://127.0.0.1:8765/admin

Working store: `kg/repo/`. Pilot snapshot: `kg/american-alchemy/`.

## Pilot

Episode: Drumm / pyramids. YouTube id `BSXdnsyCqxw`.

- `american-alchemy/drumm-pyramids.dictionary.twk`
- `american-alchemy/drumm-pyramids.document.twk`
- `repo/` — same files, what the server lists on boot
- `server/` — stdlib HTTP + admin desk + `twk_lib.py`

## Catalog rule of thumb

Allowed as `external-fact`: Wikidata, GeoNames, VIAF, ORCID, Open Library / ISBN, Crossref / DOI, official records, dated news of record, the guest's published site and ISBN, the episode itself.

Forbidden as fact: fandom wikis, documents the guest says exist but cannot be retrieved, anonymous recaps, private emails, paywalled body text ingested wholesale.

## Closed v1 lists

Entity types stay the CORE set plus a few domain types used in the pilot. Predicates that encode a guest hypothesis (`producedChemical`, `functionedAs`, …) are only legal on `asserted-in-media` claims.
