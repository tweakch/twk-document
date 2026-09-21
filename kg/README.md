# TWK knowledge graph pilot

Public-source, Wikidata-aligned graph layers.

- *American Alchemy* (Jesse Michels): longform video, media-time clock.
- *The Innermost Loop* (Alex Wissner-Gross): daily Substack plus named episode essays, text-locator clock, podcast voiceovers on the same publication.

Guest / newsletter hypotheses stay `asserted-in-media`.
Catalog identities (Wikidata people, places, orgs, works) live as `external-fact`.

How the seeds were built, step by step: [RESEARCH-METHODS.md](RESEARCH-METHODS.md).

## Run the server

```bash
cd kg/server
python3 server.py
```

Open http://127.0.0.1:8765/admin

The working store is `kg/repo/`.

## Current seeds (2026-09-22)

American Alchemy

- Drumm / pyramids — `BSXdnsyCqxw` (2026-09-19)
- Grant Cameron — `fpUa3xJN64Q` (2026-09-15)
- Ellsworth / Woods–Johnson — `rjUdn6FklAU` (2026-09-07)

The Innermost Loop

- Welcome to September 20, 2026
- Welcome to September 13, 2026
- Episode: The First Interstellar Spacecraft to Alpha Centauri (2026-09-02)
- Episode: The First AI Chip Designed End-to-End by AI (2026-08-27)
- Podcast show: The Innermost Loop with Dr. Alex Wissner-Gross (Spotify `1thtZk5vHTXbtDHezPT7tl`)
