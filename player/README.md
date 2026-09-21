# TWK Player

Vite 6 reference renderer for TWK 0.2.

```bash
cd player
npm install
npm run dev
```

`npm install` copies `../examples` into `public/data/` so the presets resolve.

The engine in `src/engine.js` is the interesting part: `load()`, `contextAt(t)`, windowed shard fetch, and the claim-kind distinction. The UI is just one way to bind that payload.
