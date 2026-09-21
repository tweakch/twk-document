import L from "leaflet";
import "leaflet/dist/leaflet.css";
import iconUrl from "leaflet/dist/images/marker-icon.png";
import iconRetinaUrl from "leaflet/dist/images/marker-icon-2x.png";
import shadowUrl from "leaflet/dist/images/marker-shadow.png";
import * as TWK from "./engine.js";
import "./style.css";

L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl });

const $ = (id) => document.getElementById(id);

const state = {
  pack: null,
  t: 731.42,
  playing: false,
  lastAnim: 0,
  map: null,
  markers: [],
  minSalience: 0,
  audioOk: false,
  windowHint: 90,
};

const fileCache = new Map();

async function resolver(uri) {
  if (fileCache.has(uri)) return JSON.parse(fileCache.get(uri));
  const base = state.sourceDir || "";
  const tryUris = [uri];
  if (base && !/^https?:/i.test(uri)) tryUris.unshift(base + uri.replace(/^\.\//, ""));
  for (const u of tryUris) {
    try {
      const res = await fetch(u);
      if (res.ok) return await res.json();
    } catch (_) {}
  }
  return null;
}

function setStatus(html) {
  $("status").innerHTML = html;
}

function entityName(id) {
  const doc = state.pack && state.pack.doc;
  if (!doc) return id;
  const e = (doc.entities || []).find((x) => x.id === id);
  return e ? e.name : id;
}

function speakerName(id) {
  const doc = state.pack && state.pack.doc;
  if (!doc || !id) return "";
  const s = (doc.speakers || []).find((x) => x.id === id);
  return s ? s.name : id;
}

function meter(label, v) {
  if (v == null) return "";
  const pct = Math.round(v * 100);
  return `<span>${label}<span class="bar"><i style="width:${pct}%"></i></span> ${pct}%</span>`;
}

function claimKindLabel(kind) {
  if (kind === "external-fact") return "external fact — not spoken here";
  if (kind === "disputed") return "disputed";
  return "asserted in media";
}

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderMap(entities) {
  const geo = (entities || []).filter((e) => e.geo && typeof e.geo.lat === "number");
  const el = $("map");
  if (!geo.length) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  if (!state.map && typeof L !== "undefined") {
    state.map = L.map(el, { scrollWheelZoom: false, attributionControl: true });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OSM",
      maxZoom: 18,
    }).addTo(state.map);
  }
  if (!state.map) return;
  state.markers.forEach((m) => m.remove());
  state.markers = [];
  const bounds = [];
  geo.forEach((e) => {
    const m = L.marker([e.geo.lat, e.geo.lon]).addTo(state.map);
    m.bindPopup(`<strong>${esc(e.name)}</strong><br>${esc(e.description || e.type)}`);
    state.markers.push(m);
    bounds.push([e.geo.lat, e.geo.lon]);
  });
  if (bounds.length === 1) state.map.setView(bounds[0], 8);
  else state.map.fitBounds(bounds, { padding: [24, 24], maxZoom: 9 });
  setTimeout(() => state.map.invalidateSize(), 80);
}

function render() {
  const pack = state.pack;
  if (!pack) return;
  const doc = pack.doc;
  const dur = TWK.durationOf(doc) || 1;
  $("title").textContent = doc.title || doc.id;
  const kind = pack.kind || doc.kind || "document";
  const clock = TWK.clockKind(doc);
  $("sub").textContent = `${doc.id} · ${kind} · clock:${clock} · media ${doc.media && doc.media.type ? doc.media.type : "?"} · ${doc.media && doc.media.uri ? doc.media.uri : ""}`;
  $("scrub").max = String(dur);
  $("t-cur").textContent = clock === "text-locator" ? TWK.posLabel({ page: state.t }) : TWK.formatTime(state.t);
  $("t-end").textContent = clock === "text-locator" ? String(Math.round(dur)) : TWK.formatTime(dur);
  if (document.activeElement !== $("scrub")) $("scrub").value = String(state.t);
  const ctx = TWK.contextAt(doc, state.t, { minSalience: state.minSalience });
  const segs = (doc.transcript && doc.transcript.segments) || [];
  const nowSeg = $("now-seg");
  if (ctx.segments.length) {
    nowSeg.className = "";
    nowSeg.innerHTML = ctx.segments
      .map((s) => {
        const who = speakerName(s.speaker);
        return `<div><span class="who">${esc(who)}</span><span class="when">${esc(TWK.posLabel(s.start))}</span><p class="txt">${esc(s.text)}</p></div>`;
      })
      .join("");
  } else {
    nowSeg.className = "empty";
    nowSeg.textContent = ctx.empty
      ? "No covering interval at " + TWK.formatTime(state.t) + " — empty context, not an error."
      : "No transcript segment on the needle.";
  }
  $("transcript").innerHTML = segs
    .map((s) => {
      const on = ctx.segments.some((x) => x.id === s.id);
      return `<div class="seg${on ? " active" : ""}" data-t="${TWK.posSeconds(s.start)}">
        <span class="who">${esc(speakerName(s.speaker) || "—")}</span>
        <span class="when">${esc(TWK.posLabel(s.start))}</span>
        <p class="txt">${esc(s.text)}</p>
      </div>`;
    })
    .join("");
  const ctxEl = $("context");
  const bits = [];
  ctx.events.forEach((ev) => {
    const ent = ev.entity ? entityName(ev.entity) : "";
    bits.push(`<div class="card">
      <span class="type-pill">${esc(ev.type)}</span>
      ${ent ? `<h3>${esc(ent)}</h3>` : ""}
      ${ev.quote ? `<p class="quote">“${esc(ev.quote)}”</p>` : ""}
      ${ev.relation ? `<p>relation ${esc(ev.relation)}</p>` : ""}
      ${ev.claim ? `<p>claim ${esc(ev.claim)}</p>` : ""}
      <div class="meters">${meter("conf", ev.confidence)}${meter("sal", ev.salience)}</div>
    </div>`);
  });
  ctx.relations.forEach((rel) => {
    bits.push(`<div class="card">
      <span class="type-pill">${esc(rel.type)}</span>
      <h3>${esc(entityName(rel.from))} → ${esc(entityName(rel.to))}</h3>
      ${rel.via && rel.via.length ? `<p>via ${rel.via.map(entityName).map(esc).join(", ")}</p>` : ""}
    </div>`);
  });
  ctx.claims.forEach((cl) => {
    const kindC = cl.kind || "asserted-in-media";
    const obj =
      cl.object && typeof cl.object === "object"
        ? [cl.object.value, cl.object.unit].filter(Boolean).join(" ")
        : cl.object != null
        ? String(cl.object)
        : "";
    bits.push(`<div class="card claim ${esc(kindC)}">
      <div class="claim-kind">${esc(claimKindLabel(kindC))}</div>
      <h3>${esc(entityName(cl.subject))} · ${esc(cl.predicate)}${obj ? " = " + esc(obj) : ""}</h3>
      ${cl.quote ? `<p class="quote">“${esc(cl.quote)}”</p>` : ""}
      <div class="meters">${meter("conf", cl.confidence)}</div>
    </div>`);
  });
  if (!bits.length) {
    ctxEl.innerHTML = `<p class="empty">Nothing on the needle. Drag toward 12:11 (731s) on the geography example.</p>`;
  } else ctxEl.innerHTML = bits.join("");
  renderMap(ctx.entities.length ? ctx.entities : doc.entities || []);
  const chs = (doc.structure && doc.structure.chapters) || [];
  $("chapters").innerHTML = chs.length
    ? chs
        .map((ch) => {
          const on = ctx.chapters.some((c) => c.id === ch.id);
          return `<div class="row" data-t="${TWK.posSeconds(ch.start)}"><span>${on ? "▸ " : ""}${esc(ch.title || ch.id)}</span><span>${esc(TWK.posLabel(ch.start))}</span></div>`;
        })
        .join("")
    : `<p class="empty">No chapters.</p>`;
  const track = $("ch-track");
  track.innerHTML = chs
    .map((ch) => {
      const a = TWK.posSeconds(ch.start) || 0;
      const b = ch.end != null ? TWK.posSeconds(ch.end) : a;
      const left = (a / dur) * 100;
      const width = Math.max(0.4, ((b - a) / dur) * 100);
      return `<b title="${esc(ch.title || "")}" style="left:${left}%;width:${width}%"></b>`;
    })
    .join("");
  $("entity-list").innerHTML =
    (doc.entities || [])
      .map((e) => {
        const live = ctx.entities.some((x) => x.id === e.id);
        return `<div class="chip${live ? " on" : ""}" data-eid="${esc(e.id)}">${esc(e.name)} <small>${esc(e.type)}</small></div>`;
      })
      .join("") || `<p class="empty">No entities in this file (shards may rely on a dictionary).</p>`;
  $("entity-list").className = "chips";
  $("claim-list").innerHTML =
    (doc.claims || [])
      .map((cl) => {
        const k = cl.kind || "asserted-in-media";
        return `<div class="row" data-t="${cl.start != null ? TWK.posSeconds(cl.start) : ""}"><span>${esc(cl.predicate)} <small class="claim-kind">${esc(k)}</small></span><span>${esc(entityName(cl.subject))}</span></div>`;
      })
      .join("") || `<p class="empty">No claims catalogued.</p>`;
  const report = pack.report || { errors: [], warnings: [] };
  const shards = pack.loadedShards || [];
  const layers = (doc.layers || []).map((l) => l.role || l.id).join(", ");
  const prov = doc.provenance || {};
  $("prov").innerHTML = `
    <p>${esc(layers || "no layers")} · rev ${esc(prov.revision != null ? prov.revision : "—")}</p>
    <p class="empty">${shards.length ? "loaded: " + shards.map((s) => s.kind + " " + (s.uri || "")).join(" · ") : "monolithic document"}</p>
    ${report.errors && report.errors.length ? `<p class="err">${esc(report.errors.join("; "))}</p>` : ""}
    ${report.warnings && report.warnings.length ? `<p class="warn">${esc(report.warnings.join("; "))}</p>` : ""}
  `;
  setStatus(
    `contextAt(${TWK.formatTime(state.t)}) · events ${ctx.events.length} · entities ${ctx.entities.length} · ${ctx.empty ? "empty" : "live"}` +
      (state.audioOk ? " · media attached" : " · synthetic clock (example media URI is not playable)")
  );
}

function seek(t) {
  const doc = state.pack && state.pack.doc;
  const dur = doc ? TWK.durationOf(doc) : 0;
  state.t = Math.max(0, Math.min(dur || t, t));
  const audio = $("audio");
  if (state.audioOk && Math.abs((audio.currentTime || 0) - state.t) > 0.25) {
    try {
      audio.currentTime = state.t;
    } catch (_) {}
  }
  render();
}

async function maybeReloadWindow() {
  const pack = state.pack;
  if (!pack || pack.kind !== "manifest" || !pack.manifest) return;
  const hint = (pack.manifest.composition && pack.manifest.composition.windowHintSeconds) || 90;
  const win = pack.window || { from: 0, to: 0 };
  if (state.t >= win.from + hint * 0.25 && state.t <= win.to - hint * 0.25) return;
  const next = await TWK.load(pack.manifest, { t: state.t, windowSec: hint, resolver });
  state.pack = next;
}

async function openDoc(uriOrDoc, sourceDir) {
  state.sourceDir = sourceDir || (typeof uriOrDoc === "string" ? uriOrDoc.replace(/[^/]+$/, "") : "data/");
  setStatus("Loading…");
  const pack = await TWK.load(uriOrDoc, { t: state.t, resolver });
  state.pack = pack;
  const dur = TWK.durationOf(pack.doc);
  if (state.t > dur) state.t = Math.min(state.t, dur);
  const ctx = TWK.contextAt(pack.doc, state.t);
  if (ctx.empty && pack.doc.timeline && pack.doc.timeline[0]) {
    const s = TWK.posSeconds(pack.doc.timeline[0].start);
    if (s != null) state.t = s;
  }
  const audio = $("audio");
  state.audioOk = false;
  audio.removeAttribute("src");
  const uri = pack.doc.media && pack.doc.media.uri;
  if (uri && /^(https?:)?\/\//.test(uri) && (pack.doc.media.type === "audio" || pack.doc.media.type === "video" || /\.(mp3|ogg|wav|m4a)(\?|$)/i.test(uri))) {
    audio.src = uri;
    audio.onloadedmetadata = () => {
      state.audioOk = true;
      render();
    };
    audio.onerror = () => {
      state.audioOk = false;
      render();
    };
  }
  render();
}

$("preset").addEventListener("change", (e) => openDoc(e.target.value));
$("file").addEventListener("change", async (e) => {
  const f = e.target.files && e.target.files[0];
  if (!f) return;
  const text = await f.text();
  fileCache.set(f.name, text);
  const doc = JSON.parse(text);
  await openDoc(doc, "");
});
$("scrub").addEventListener("input", (e) => {
  seek(Number(e.target.value));
});
$("scrub").addEventListener("change", () => maybeReloadWindow().then(render));
document.body.addEventListener("click", (e) => {
  const row = e.target.closest("[data-t]");
  if (row && row.dataset.t !== "") seek(Number(row.dataset.t));
});
$("play").addEventListener("click", () => {
  state.playing = !state.playing;
  $("play").textContent = state.playing ? "Pause clock" : "Play clock";
  const audio = $("audio");
  if (state.audioOk) {
    if (state.playing) audio.play().catch(() => {});
    else audio.pause();
  }
  state.lastAnim = performance.now();
});

function tick(now) {
  if (state.playing && state.pack) {
    const audio = $("audio");
    if (state.audioOk && !audio.paused) {
      state.t = audio.currentTime;
    } else {
      const dt = (now - state.lastAnim) / 1000;
      state.t += dt;
      const dur = TWK.durationOf(state.pack.doc);
      if (state.t >= dur) {
        state.t = dur;
        state.playing = false;
        $("play").textContent = "Play clock";
      }
    }
    state.lastAnim = now;
    render();
  } else {
    state.lastAnim = now;
  }
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

openDoc("/data/geography.twk").catch((err) => {
  setStatus('<span class="err">' + err.message + "</span>");
});
