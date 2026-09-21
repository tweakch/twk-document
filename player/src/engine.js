/**
 * TWK 0.2 client engine
 * Implements document kinds, positions, contextAt(t), and windowed shard loading.
 */
const KINDS = new Set(["document", "manifest", "shard", "dictionary"]);

function posSeconds(p) {
  if (p == null) return null;
  if (typeof p === "number" && Number.isFinite(p)) return p;
  if (typeof p === "object") {
    if (typeof p.t === "number") return p.t;
    if (p.scheme === "seconds" && typeof p.locator === "string") {
      const n = Number(p.locator);
      return Number.isFinite(n) ? n : null;
    }
    if (typeof p.page === "number") return p.page;
    if (typeof p.frac === "number") return p.frac;
  }
  return null;
}

function posLabel(p) {
  if (p == null) return "";
  if (typeof p === "number") return formatTime(p);
  if (typeof p === "object") {
    if (typeof p.t === "number") return formatTime(p.t);
    if (p.page != null) return "p." + p.page;
    if (p.locator) return String(p.locator).slice(0, 42);
    if (p.frac != null) return Math.round(p.frac * 100) + "%";
  }
  return String(p);
}

function formatTime(s) {
  if (s == null || !Number.isFinite(s)) return "—";
  s = Math.max(0, s);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  const tenths = Math.floor((s % 1) * 10);
  const core =
    (h > 0 ? String(h) + ":" : "") +
    String(m).padStart(h > 0 ? 2 : 1, "0") +
    ":" +
    String(sec).padStart(2, "0");
  return h > 0 ? core : core + "." + tenths;
}

function spansCover(start, end, t) {
  const a = posSeconds(start);
  const b = end == null ? a : posSeconds(end);
  if (a == null) return false;
  if (b == null) return t === a;
  return t >= a && t <= b;
}

function spansIntersect(a0, a1, b0, b1) {
  const s0 = posSeconds(a0);
  const s1 = a1 == null ? s0 : posSeconds(a1);
  const t0 = posSeconds(b0);
  const t1 = b1 == null ? t0 : posSeconds(b1);
  if (s0 == null || t0 == null) return false;
  const ae = s1 == null ? s0 : s1;
  const be = t1 == null ? t0 : t1;
  return s0 <= be && t0 <= ae;
}

function indexById(list) {
  const m = new Map();
  if (!Array.isArray(list)) return m;
  for (const item of list) {
    if (item && item.id) {
      if (!m.has(item.id)) m.set(item.id, item);
    }
  }
  return m;
}

function validateLite(doc) {
  const errors = [];
  const warnings = [];
  if (!doc || typeof doc !== "object") {
    return { ok: false, errors: ["not an object"], warnings };
  }
  if (doc.twk == null) errors.push("missing twk");
  if (!doc.id) errors.push("missing id");
  if (!doc.media || !doc.media.uri) errors.push("missing media.uri");
  const kind = doc.kind || "document";
  if (doc.kind && !KINDS.has(doc.kind)) warnings.push("unknown kind: " + doc.kind);
  const twk = String(doc.twk || "");
  if (twk.startsWith("0.1")) warnings.push("loaded 0.1 document in 0.2 reader");
  else if (!/^0\.2(\.|$)/.test(twk) && twk) warnings.push("unexpected version " + twk);
  function checkIds(arr, label) {
    if (!arr) return;
    const seen = new Set();
    for (const item of arr) {
      if (!item || !item.id) continue;
      if (seen.has(item.id)) errors.push("duplicate " + label + " id " + item.id);
      seen.add(item.id);
    }
  }
  checkIds(doc.entities, "entity");
  checkIds(doc.relations, "relation");
  checkIds(doc.claims, "claim");
  checkIds(doc.sources, "source");
  checkIds(doc.assets, "asset");
  checkIds(doc.speakers, "speaker");
  if (Array.isArray(doc.timeline)) {
    let prev = -Infinity;
    for (const iv of doc.timeline) {
      const s = posSeconds(iv.start);
      const e = iv.end == null ? s : posSeconds(iv.end);
      if (s != null && s < 0) errors.push("negative start");
      if (s != null && e != null && e < s) errors.push("end before start");
      if (s != null) {
        if (s < prev) errors.push("timeline not sorted by start");
        prev = s;
      }
      for (const ev of iv.events || []) {
        if (ev.confidence != null && (ev.confidence < 0 || ev.confidence > 1))
          errors.push("confidence out of range");
        if (ev.salience != null && (ev.salience < 0 || ev.salience > 1))
          errors.push("salience out of range");
      }
    }
  }
  return { ok: errors.length === 0, errors, warnings, kind };
}

function mergeDocs(base, incoming) {
  const out = Object.assign({}, base);
  const arrays = ["speakers", "entities", "timeline", "relations", "claims", "sources", "assets", "layers"];
  for (const key of arrays) {
    const a = Array.isArray(base[key]) ? base[key] : [];
    const b = Array.isArray(incoming[key]) ? incoming[key] : [];
    if (!a.length && !b.length) continue;
    const seen = new Set(a.map((x) => x && x.id).filter(Boolean));
    const merged = a.slice();
    for (const item of b) {
      if (item && item.id && seen.has(item.id)) continue;
      if (item && item.id) seen.add(item.id);
      merged.push(item);
    }
    if (key === "timeline") {
      merged.sort((x, y) => (posSeconds(x.start) || 0) - (posSeconds(y.start) || 0));
    }
    out[key] = merged;
  }
  if (incoming.transcript && incoming.transcript.segments) {
    const segs = (base.transcript && base.transcript.segments) || [];
    const seen = new Set(segs.map((s) => s.id));
    const extra = incoming.transcript.segments.filter((s) => s.id && !seen.has(s.id));
    out.transcript = Object.assign({}, base.transcript || incoming.transcript, {
      segments: segs.concat(extra).sort((a, b) => (posSeconds(a.start) || 0) - (posSeconds(b.start) || 0)),
    });
  } else if (incoming.transcript && !out.transcript) {
    out.transcript = incoming.transcript;
  }
  if (incoming.structure && incoming.structure.chapters && !(base.structure && base.structure.chapters)) {
    out.structure = incoming.structure;
  }
  return out;
}

async function fetchJson(uri, resolver) {
  if (resolver) {
    const resolved = await resolver(uri);
    if (resolved != null) return resolved;
  }
  const res = await fetch(uri);
  if (!res.ok) throw new Error("failed to load " + uri + " (" + res.status + ")");
  return res.json();
}

async function load(uriOrDoc, opts) {
  opts = opts || {};
  const t = opts.t != null ? opts.t : 0;
  const windowSec = opts.windowSec != null ? opts.windowSec : null;
  let doc = typeof uriOrDoc === "string" ? await fetchJson(uriOrDoc, opts.resolver) : uriOrDoc;
  const report = validateLite(doc);
  const kind = doc.kind || "document";
  if (kind !== "manifest") {
    return { doc, report, loadedShards: [], kind };
  }
  const hint = windowSec != null ? windowSec : (doc.composition && doc.composition.windowHintSeconds) || 90;
  const from = Math.max(0, t - hint);
  const to = t + hint;
  let composed = {
    twk: doc.twk,
    id: doc.id,
    kind: "document",
    title: doc.title,
    language: doc.language,
    clock: doc.clock,
    media: doc.media,
    structure: doc.structure,
    composition: doc.composition,
    provenance: doc.provenance,
    speakers: [],
    entities: [],
    timeline: [],
    relations: [],
    claims: [],
    sources: [],
    assets: [],
    layers: doc.layers || [],
  };
  const loadedShards = [];
  const dictUri = doc.composition && doc.composition.dictionary && doc.composition.dictionary.uri;
  if (dictUri) {
    try {
      const dict = await fetchJson(dictUri, opts.resolver);
      const dr = validateLite(dict);
      report.warnings.push.apply(report.warnings, dr.warnings.map((w) => "dictionary: " + w));
      if (!dr.ok) report.warnings.push("dictionary validation: " + dr.errors.join("; "));
      composed = mergeDocs(composed, dict);
      loadedShards.push({ kind: "dictionary", uri: dictUri });
    } catch (e) {
      report.warnings.push("dictionary load failed: " + e.message);
    }
  }
  const shards = (doc.composition && doc.composition.shards) || [];
  for (const ref of shards) {
    if (!spansIntersect(ref.start, ref.end, from, to)) continue;
    try {
      const shard = await fetchJson(ref.uri, opts.resolver);
      if (doc.media && doc.media.identity && shard.media && shard.media.identity) {
        if (
          doc.media.identity.type === shard.media.identity.type &&
          doc.media.identity.value !== shard.media.identity.value
        ) {
          report.errors.push("shard media identity mismatch: " + ref.uri);
          report.ok = false;
          continue;
        }
      }
      composed = mergeDocs(composed, shard);
      loadedShards.push({ kind: "shard", uri: ref.uri, id: ref.id, start: ref.start, end: ref.end });
    } catch (e) {
      report.warnings.push("shard load failed (" + ref.uri + "): " + e.message);
    }
  }
  return { doc: composed, manifest: doc, report, loadedShards, kind: "manifest", window: { from, to, hint } };
}

function contextAt(doc, t, opts) {
  opts = opts || {};
  const minSalience = opts.minSalience != null ? opts.minSalience : 0;
  const entities = indexById(doc.entities);
  const relations = indexById(doc.relations);
  const claims = indexById(doc.claims);
  const speakers = indexById(doc.speakers);
  const sources = indexById(doc.sources);
  const assets = indexById(doc.assets);
  const intervals = [];
  const events = [];
  for (const iv of doc.timeline || []) {
    if (!spansCover(iv.start, iv.end, t)) continue;
    intervals.push(iv);
    for (const ev of iv.events || []) {
      if (ev.salience != null && ev.salience < minSalience) continue;
      events.push(Object.assign({ _interval: iv }, ev));
    }
  }
  const mentioned = [];
  const seenE = new Set();
  for (const ev of events) {
    if (ev.entity && entities.has(ev.entity) && !seenE.has(ev.entity)) {
      seenE.add(ev.entity);
      mentioned.push(entities.get(ev.entity));
    }
  }
  const activeRelations = [];
  const seenR = new Set();
  for (const ev of events) {
    if (ev.relation && relations.has(ev.relation) && !seenR.has(ev.relation)) {
      seenR.add(ev.relation);
      activeRelations.push(relations.get(ev.relation));
    }
  }
  for (const rel of doc.relations || []) {
    if (seenR.has(rel.id)) continue;
    if (rel.start != null && spansCover(rel.start, rel.end, t)) {
      seenR.add(rel.id);
      activeRelations.push(rel);
    }
  }
  const activeClaims = [];
  const seenC = new Set();
  for (const ev of events) {
    if (ev.claim && claims.has(ev.claim) && !seenC.has(ev.claim)) {
      seenC.add(ev.claim);
      activeClaims.push(claims.get(ev.claim));
    }
  }
  for (const cl of doc.claims || []) {
    if (seenC.has(cl.id)) continue;
    if (cl.start != null && spansCover(cl.start, cl.end, t)) {
      seenC.add(cl.id);
      activeClaims.push(cl);
    }
  }
  const segments = [];
  for (const seg of (doc.transcript && doc.transcript.segments) || []) {
    if (spansCover(seg.start, seg.end, t) || (posSeconds(seg.start) != null && Math.abs(posSeconds(seg.start) - t) < 0.05 && seg.end == null)) {
      segments.push(seg);
    }
  }
  const chapters = ((doc.structure && doc.structure.chapters) || []).filter((ch) => spansCover(ch.start, ch.end, t));
  return {
    t,
    empty: events.length === 0 && segments.length === 0 && activeRelations.length === 0 && activeClaims.length === 0,
    intervals,
    events,
    entities: mentioned,
    relations: activeRelations,
    claims: activeClaims,
    segments,
    chapters,
    speakers,
    catalogs: { entities, relations, claims, speakers, sources, assets },
  };
}

function durationOf(doc) {
  if (doc.media && typeof doc.media.duration === "number") return doc.media.duration;
  let max = 0;
  for (const iv of doc.timeline || []) {
    const e = posSeconds(iv.end != null ? iv.end : iv.start);
    if (e != null && e > max) max = e;
  }
  for (const seg of (doc.transcript && doc.transcript.segments) || []) {
    const e = posSeconds(seg.end != null ? seg.end : seg.start);
    if (e != null && e > max) max = e;
  }
  for (const ch of (doc.structure && doc.structure.chapters) || []) {
    const e = posSeconds(ch.end != null ? ch.end : ch.start);
    if (e != null && e > max) max = e;
  }
  return max || 0;
}

function clockKind(doc) {
  if (doc.clock && doc.clock.kind) return doc.clock.kind;
  if (doc.media && doc.media.type === "text") return "text-locator";
  return "media-time";
}

export {
  posSeconds,
  posLabel,
  formatTime,
  spansCover,
  spansIntersect,
  validateLite,
  mergeDocs,
  load,
  contextAt,
  durationOf,
  clockKind,
  indexById,
};

export const TWK = {
  posSeconds,
  posLabel,
  formatTime,
  spansCover,
  spansIntersect,
  validateLite,
  mergeDocs,
  load,
  contextAt,
  durationOf,
  clockKind,
  indexById,
};
