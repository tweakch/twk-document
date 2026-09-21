// Aspire TypeScript AppHost for the TWK 0.2 repo.
// For more information, see: https://aspire.dev
//
// Resource graph:
//
//   examples-sync  (node, runs to completion)
//        |  mirrors examples/*.twk -> player/public/data
//        v
//   player         (npm run dev -> Vite 6 on :5173, external)
//
//   kg-server      (python server.py -> stdlib http on :8765, external)
//
// player and kg-server are deliberately independent siblings, not linked by
// withReference: the player only ever fetches .twk files (preset paths under
// /data and shard URIs out of a manifest) and never calls the KG server's
// /api/* surface. Injecting service-discovery vars would also be inert here,
// since Vite only forwards VITE_-prefixed vars to the browser.

import { createBuilder } from './.aspire/modules/aspire.mjs';

const builder = await createBuilder();

// The player's preset dropdown fetches /data/geography.twk, /data/manifest.twk,
// /data/shards/*.twk, so the example corpus has to be in player/public/data
// before Vite starts serving. Runs on every start; copying a handful of small
// JSON files is cheap and keeps the served data in step with examples/.
const examples = await builder
  .addExecutable('examples-sync', 'node', 'player', ['scripts/sync-examples.mjs']);

// Vite 6 reference renderer. vite.config.js pins server.port to 5173, so that
// is the target port Aspire's proxy forwards to.
await builder
  .addExecutable('player', 'npm', 'player', ['run', 'dev'])
  .withHttpEndpoint({ name: 'http', targetPort: 5173 })
  .withExternalHttpEndpoints()
  .waitForCompletion(examples);

// Stdlib-only Python authoring/admin desk for TWK 0.2 documents. No
// requirements.txt and no third-party imports, so it runs on a bare
// interpreter with no venv step. server.py hardcodes 0.0.0.0:8765, so that is
// the target port Aspire proxies to. Its working store is kg/repo/, which
// server.py creates on startup.
await builder
  .addExecutable('kg-server', 'python', 'kg/server', ['server.py'])
  .withHttpEndpoint({ name: 'http', targetPort: 8765 })
  .withHttpHealthCheck({ path: '/api/docs' })
  .withUrlForEndpoint('http', async (url) => {
    // The useful entry point is the admin UI, not the bare root.
    url.url = `${(url.url ?? '').replace(/\/$/, '')}/admin`;
    url.displayText = 'admin';
  })
  .withExternalHttpEndpoints();

await builder.build().run();
