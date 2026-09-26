// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 FireBall1725
//
// Lovelace cards for the plants integration, ported from "The Watering Clock" mockup:
//   custom:plants-card         one plant: hero moisture, trend, pills, 7-day curve
//   custom:plants-triage-card  every plant, sorted by need, with each plant's floor
// Data comes from the integration's websocket API (plants/list, plants/history),
// shared by every card on the page.

const VERSION = "0.0.0";

// The seven plant marks, the same line drawings the FireLabs display uses.
const MARKS = {
  succulent: `<path d='M12 21v-8'/><ellipse cx='8.4' cy='10.2' rx='2.9' ry='3.9' transform='rotate(-24 8.4 10.2)'/><ellipse cx='15.6' cy='8.6' rx='2.9' ry='3.9' transform='rotate(24 15.6 8.6)'/><path d='M8.5 21h7'/>`,
  herb: `<path d='M12 21V9'/><path d='M12 13c-3.4 0-5.8-2.4-6-6 3.6.2 6 2.6 6 6Z'/><path d='M12 11c.2-3.6 2.6-6 6.2-6.2-.2 3.6-2.6 6-6.2 6.2Z'/><path d='M9 21h6'/>`,
  seedling: `<path d='M12 21v-7'/><path d='M12 14c-3 0-5.4-2.2-5.8-5C9.4 9.3 12 11 12 14Z'/><path d='M12 12c.4-2.7 2.8-4.7 5.8-4.7C17.4 10 15 12 12 12Z'/><path d='M9 21h6'/>`,
  cactus: `<path d='M10 21V6.5a2 2 0 0 1 4 0V21'/><path d='M10 13.5H8a2 2 0 0 1-2-2V9.5'/><path d='M14 11.5h2a2 2 0 0 0 2-2V8'/><path d='M8 21h8'/>`,
  fern: `<path d='M12 21V5'/><path d='M12 8 9.5 6.3M12 8l2.5-1.7M12 11 8.5 9M12 11l3.5-2M12 14 8 12M12 14l4-2M12 17 9 15.3M12 17l3-1.7'/><path d='M9 21h6'/>`,
  flowering: `<path d='M12 21v-8'/><path d='M8 5.5l2 2 2-3 2 3 2-2V9a4 4 0 0 1-8 0Z'/><path d='M12 17c-2.3 0-3.8-1.1-4.3-3 2.3 0 3.8 1.1 4.3 3Z'/><path d='M9 21h6'/>`,
  tropical: `<path d='M12 21v-5'/><path d='M12 16c-4.7 0-7.8-2.9-7.8-6.8 2.8-2 5.6-2 7.8 0 2.2-2 5-2 7.8 0 0 3.9-3.1 6.8-7.8 6.8Z'/><path d='M12 16V8.6'/><path d='M4.5 10.2l2.7.6M19.5 10.2l-2.7.6M6.4 13.4l2.3-1M17.6 13.4l-2.3-1'/><path d='M9 21h6'/>`,
};
const PROBE_MARK = `<path d='M12 21v-7'/><path d='M12 14c-3 0-5.4-2.2-5.8-5C9.4 9.3 12 11 12 14Z'/><path d='M12 12c.4-2.7 2.8-4.7 5.8-4.7C17.4 10 15 12 12 12Z'/><path d='M4.5 4.5l15 15'/>`;
const ALERT_MARK = `<path d='M12 3.5 3 20h18L12 3.5Z'/><path d='M12 10v4.5'/><circle cx='12' cy='17.3' r='.9' fill='currentColor' stroke='none'/>`;
const CHECK_MARK = `<path d='M4 13l5 5L20 6'/>`;

const HUE = {
  moist: "#4f8ad6", fert: "#58a05c", light: "#dfae3c", bad: "#c8503f",
  warn: "#d98b39", ok: "#58a05c", ink: "#e7e9ec", dim: "#8a9099",
};

const STYLE = `
  :host {
    --ground: #0e1012; --card: #191c1f; --inset: #23272b; --hair: #2b3036;
    --ink: #e7e9ec; --dim: #8a9099; --dimmer: #5f666e;
    --moist: #4f8ad6; --fert: #58a05c; --light: #dfae3c; --temp: #e07a45;
    --bad: #c8503f; --warn: #d98b39; --ok: #58a05c;
    --ha: "Roboto", "Helvetica Neue", Helvetica, Arial, sans-serif;
    --hacond: "Roboto Condensed", "Roboto", Arial, sans-serif;
    display: block;
  }
  *, *::before, *::after { box-sizing: border-box; }
  .hacard { background: var(--card); border-radius: 12px; overflow: hidden; position: relative;
    font-family: var(--ha); color: var(--ink); box-shadow: 0 1px 2px rgba(0,0,0,.4); }
  .band { position: relative; display: flex; align-items: center; gap: 14px;
    padding: 10px 16px 10px 80px; min-height: 66px; }
  .notch { position: absolute; left: 0; top: 0; width: 66px; height: 66px;
    border-radius: 12px 0 22px 0; display: grid; place-items: center; pointer-events: none; }
  .notch svg { width: 34px; height: 34px; }
  .notch .mask { width: 34px; height: 34px; -webkit-mask-size: contain; mask-size: contain;
    -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat;
    -webkit-mask-position: center; mask-position: center; }
  .ident { flex: 1; min-width: 0; }
  .ident b { display: block; font-size: 17px; font-weight: 500; line-height: 1.25; color: var(--ink);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ident span { display: block; font-size: 12.5px; color: var(--dim);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .chips { display: flex; gap: 15px; align-items: baseline; flex: none; }
  .chip { text-align: right; }
  .chip i { display: block; font-style: normal; font-size: 9.5px; font-weight: 700;
    letter-spacing: .1em; color: var(--dimmer); text-transform: uppercase; white-space: nowrap; }
  .chip b { font-family: var(--hacond); font-size: 20px; font-weight: 700;
    font-variant-numeric: tabular-nums; color: var(--ink); white-space: nowrap; }
  .chip b small { font-size: 11px; margin-left: 1px; color: var(--dim); }

  .band + * { padding-top: 13px; }
  .band + .bleedchart { padding-top: 0; }

  .reading { display: flex; align-items: flex-end; gap: 18px; padding: 2px 16px 10px 80px; }
  .reading .big { font-family: var(--hacond); font-size: 66px; font-weight: 700; line-height: .86;
    letter-spacing: -.01em; font-variant-numeric: tabular-nums; }
  .reading .big sup { font-size: 22px; font-weight: 700; vertical-align: top; margin-left: 2px; }
  .reading .aside { padding-bottom: 5px; min-width: 0; }
  .reading .aside div { font-size: 12.5px; color: var(--dim); line-height: 1.5; }
  .reading .aside b { color: var(--ink); font-weight: 500; }

  .pills { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 16px 12px; }
  .pill { font-size: 10.5px; letter-spacing: .04em; color: var(--dim); background: var(--inset);
    border-radius: 5px; padding: 3px 8px; white-space: nowrap; }
  .pill.bad  { background: rgba(200,80,63,.18);  color: #eb9184; }
  .pill.warn { background: rgba(217,139,57,.18); color: #e9b276; }
  .pill.good { background: rgba(88,160,92,.18);  color: #8cc08f; }

  .empty { padding: 18px 16px 22px; text-align: center; }
  .empty b { display: block; font-family: var(--hacond); font-size: 30px; font-weight: 700; }
  .empty span { font-size: 12.5px; color: var(--dim); }

  .bleedchart { position: relative; }
  .bleedchart svg { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
  .bleedchart .lab { position: absolute; font-size: 8.5px; font-weight: 700; letter-spacing: .09em;
    text-transform: uppercase; pointer-events: none; padding: 1px 5px; border-radius: 3px;
    line-height: 1.25; background: color-mix(in srgb, var(--card) 86%, transparent); }
  .nodata { position: absolute; inset: 0; display: grid; place-items: center;
    font-size: 11px; color: var(--dimmer); letter-spacing: .06em; }

  .triage { padding: 2px 14px 12px; display: grid; gap: 2px; }
  .trow { display: grid; grid-template-columns: 84px 1fr 58px 92px; gap: 10px;
    align-items: center; padding: 6px 0; cursor: pointer; }
  .trow .who { font-size: 13px; color: var(--ink); font-weight: 500; min-width: 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .trow .who i { display: block; font-style: normal; font-size: 9.5px; color: var(--dimmer);
    font-weight: 400; letter-spacing: .04em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .trow .meter { position: relative; height: 8px; border-radius: 4px; background: var(--inset); }
  .trow .meter u { position: absolute; top: 0; bottom: 0; left: 0; border-radius: 4px;
    background: var(--moist); text-decoration: none; }
  .trow .meter em { position: absolute; top: -4px; width: 2px; height: 16px; font-style: normal;
    background: var(--dim); opacity: .8; }
  .trow .val { font-family: var(--hacond); font-size: 15px; font-weight: 700; text-align: right;
    font-variant-numeric: tabular-nums; }
  .trow .verdict { font-size: 10px; font-weight: 700; letter-spacing: .05em; text-align: right;
    text-transform: uppercase; color: var(--dim); }
  .trow .verdict.bad { color: var(--bad); }
  .trow .verdict.warn { color: var(--warn); }
  .trow .verdict.ok { color: var(--ok); }
  .tscale { display: flex; justify-content: space-between; padding: 2px 14px 12px 94px;
    font-size: 9.5px; color: var(--dimmer); letter-spacing: .08em; }

  .key { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 14px; padding: 0 16px 12px;
    font-size: 10px; letter-spacing: .05em; color: var(--dim); }
  .key span { display: flex; align-items: center; gap: 6px; }
  .key u { width: 16px; height: 7px; border-radius: 3px; text-decoration: none; }
  .key em { width: 2px; height: 12px; font-style: normal; background: var(--dim); }

  .msg { padding: 18px 16px; font-size: 13px; color: var(--dim); }
  .clickable { cursor: pointer; }
`;

// ---------- shared data ----------

const LIST_TTL_MS = 30 * 1000;
const HISTORY_TTL_MS = 10 * 60 * 1000;

const store = {
  hass: null,
  plants: null,
  listAt: 0,
  listing: null,
  history: null,
  historyAt: 0,
  historying: null,
  watched: new Map(), // entity_id -> last_updated, to refetch when a reading changes
  listeners: new Set(),
};

function notify() {
  for (const fn of store.listeners) fn();
}

async function fetchList(force) {
  if (!store.hass) return;
  if (!force && store.plants && Date.now() - store.listAt < LIST_TTL_MS) return;
  if (store.listing) return store.listing;
  store.listing = store.hass
    .callWS({ type: "plants/list" })
    .then((plants) => {
      store.plants = plants;
      store.listAt = Date.now();
      store.watched.clear();
      for (const p of plants) {
        for (const r of Object.values(p.readings || {})) {
          if (r.entity_id) store.watched.set(r.entity_id, null);
        }
      }
      notify();
    })
    .catch((err) => {
      store.error = String(err && err.message ? err.message : err);
      notify();
    })
    .finally(() => { store.listing = null; });
  return store.listing;
}

async function fetchHistory() {
  if (!store.hass) return;
  if (store.history && Date.now() - store.historyAt < HISTORY_TTL_MS) return;
  if (store.historying) return store.historying;
  store.historying = store.hass
    .callWS({ type: "plants/history", hours: 168 })
    .then((h) => {
      store.history = h;
      store.historyAt = Date.now();
      notify();
    })
    .catch(() => {})
    .finally(() => { store.historying = null; });
  return store.historying;
}

// Called from every card's hass setter: refetch when any plant's reading changed.
function feed(hass) {
  store.hass = hass;
  let changed = false;
  for (const [id, seen] of store.watched) {
    const st = hass.states[id];
    const at = st ? st.last_updated : null;
    if (seen !== at) {
      if (seen !== null) changed = true;
      store.watched.set(id, at);
    }
  }
  fetchList(changed);
  fetchHistory();
}

// ---------- helpers ----------

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);

function fmt(v, digits = 0) {
  const n = num(v);
  return n === null ? "–" : n.toFixed(digits);
}

function reading(p, key) {
  const r = (p.readings || {})[key] || {};
  return { value: num(r.value), age: num(r.age), unit: r.unit || "", entity: r.entity_id };
}

function ago(iso) {
  if (!iso) return null;
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (!Number.isFinite(s)) return null;
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 36 * 3600) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}

function until(iso) {
  if (!iso) return null;
  const s = (new Date(iso).getTime() - Date.now()) / 1000;
  if (!Number.isFinite(s)) return null;
  if (s < 3600) return "within the hour";
  if (s < 36 * 3600) return `in ${Math.round(s / 3600)} h`;
  return `in ${Math.round(s / 86400)} days`;
}

function hhmm(iso) {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function lux(v) {
  if (v === null) return null;
  return v >= 1000 ? `${(v / 1000).toFixed(1)} klx` : `${Math.round(v)} lx`;
}

// Status -> colour of the hero number and the triage value.
function statusHue(p) {
  switch (p.status) {
    case "dry":
    case "check_probe":
      return "var(--bad)";
    case "water_soon":
      return "var(--warn)";
    case "stale":
      return "var(--dim)";
    default:
      return "var(--ink)";
  }
}

// Status -> notch colour: green like the mockup, red for a failed probe, grey when stale.
function notchHue(p) {
  if (p.status === "check_probe") return HUE.bad;
  if (p.status === "stale") return HUE.dim;
  return HUE.fert;
}

function notch(hue, inner) {
  return `<div class="notch" style="background:color-mix(in srgb, ${hue} 22%, transparent)">${inner}</div>`;
}

function markSvg(p, hue) {
  if (p.status === "check_probe") return svg(PROBE_MARK, hue, 1.6);
  if (p.icon === "custom" && p.icon_image) {
    return `<div class="mask" style="background:${hue};-webkit-mask-image:url(${p.icon_image});mask-image:url(${p.icon_image})"></div>`;
  }
  return svg(MARKS[p.icon] || MARKS.seedling, hue, 1.6);
}

function svg(body, hue, width = 1.8) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="${hue}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round" color="${hue}">${body}</svg>`;
}

function chip(label, value, unit = "", color = null) {
  const style = color ? ` style="color:${color}"` : "";
  return `<div class="chip"><i>${esc(label)}</i><b${style}>${value}${unit ? `<small>${unit}</small>` : ""}</b></div>`;
}

function trendLine(p) {
  const t = num(p.trend);
  if (t === null) return "Trend <b>settling</b>";
  if (Math.abs(t) < 0.1) return "Holding <b>steady</b>";
  return t < 0 ? `Falling <b>${Math.abs(t).toFixed(2)}%/day</b>` : `Rising <b>${t.toFixed(2)}%/day</b>`;
}

function wateredLine(p) {
  if (p.watering_pending) {
    const at = p.watering_pending.at || p.watering_pending.since;
    return at ? `Watering seen <b>${esc(hhmm(at))}</b>, confirming` : "Watering seen, <b>confirming</b>";
  }
  const when = ago(p.last_watered);
  return when ? `Watered <b>${esc(when)}</b>` : "No watering seen yet";
}

function pills(p) {
  const out = [];
  const m = reading(p, "moisture");
  if (p.status === "dry") out.push(["bad", `Below floor ${fmt(p.floor)}%`]);
  if (p.status === "water_soon") {
    const w = until(p.forecast);
    out.push(["warn", w ? `Reaches floor ${w}` : "Reaches floor soon"]);
  }
  if (p.status === "check_probe") out.push(["bad", "No soil reading: check the probe"]);
  if (p.status === "stale") out.push(["warn", m.age !== null ? `No reading for ${Math.round(m.age / 3600)} h` : "No recent reading"]);
  if (p.watering_pending) out.push(["good", "Watering detected"]);
  if (!out.length) return "";
  return `<div class="pills">${out.map(([k, t]) => `<span class="pill ${k}">${esc(t)}</span>`).join("")}</div>`;
}

// The 7-day curve: hourly means with a gradient fill, the floor dashed, a dot on now.
function curve(p, id) {
  const hist = store.history && store.history.series ? store.history.series[p.entry_id] : null;
  const series = Array.isArray(hist) ? hist : [];
  const floor = num(p.floor) ?? 0;
  const ceiling = num(p.ceiling) ?? 0;
  const vals = series.filter((v) => num(v) !== null);
  const top = Math.max(20, ceiling, ...vals) * 1.1;
  const y = (v) => (100 - (v / top) * 100).toFixed(1);
  const probe = p.status === "check_probe";
  const line = probe ? HUE.bad : HUE.moist;
  const floorY = y(floor);
  let body = `<line x1="0" y1="${floorY}" x2="100" y2="${floorY}" stroke="${HUE.dim}" stroke-width=".7"
      stroke-dasharray="2 2" vector-effect="non-scaling-stroke" opacity=".55"/>`;
  if (vals.length > 1) {
    // Split at gaps so a missing hour doesn't draw a line through it.
    const n = series.length;
    const runs = [];
    let run = [];
    series.forEach((v, i) => {
      if (num(v) === null) {
        if (run.length) runs.push(run);
        run = [];
      } else {
        run.push(`${((i / (n - 1)) * 100).toFixed(2)},${y(v)}`);
      }
    });
    if (run.length) runs.push(run);
    for (const r of runs) {
      if (!probe && r.length > 1) {
        const first = r[0].split(",")[0];
        const last = r[r.length - 1].split(",")[0];
        body += `<polygon fill="url(#g${id})" points="${first},100 ${r.join(" ")} ${last},100"/>`;
      }
      body += `<polyline fill="none" stroke="${line}" stroke-width="${probe ? 2.2 : 1.6}" vector-effect="non-scaling-stroke"
        stroke-linejoin="round" points="${r.join(" ")}"/>`;
    }
    const lastIdx = series.map((v) => num(v) !== null).lastIndexOf(true);
    body += `<circle cx="${((lastIdx / (n - 1)) * 100).toFixed(2)}" cy="${y(series[lastIdx])}" r="1.9" fill="${line}" vector-effect="non-scaling-stroke"/>`;
  }
  const label = `<span class="lab" style="right:6px;top:${floorY}%;transform:translateY(-50%);color:${HUE.dim}">Floor ${fmt(floor)}%</span>`;
  const empty = vals.length > 1 ? "" : `<div class="nodata">${store.history ? "No history yet" : "Loading history"}</div>`;
  return `<div class="bleedchart" style="height:120px">
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="${esc(p.name)} moisture over the last seven days">
      <defs><linearGradient id="g${id}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${HUE.moist}" stop-opacity=".42"/>
        <stop offset="100%" stop-color="${HUE.moist}" stop-opacity="0"/></linearGradient></defs>
      ${body}
    </svg>${label}${empty}</div>`;
}

function moreInfo(el, entityId) {
  if (!entityId) return;
  el.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
}

let uid = 0;

// ---------- base ----------

class PlantsBase extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._id = ++uid;
    this._render = () => this.render();
  }

  connectedCallback() {
    store.listeners.add(this._render);
    this.render();
  }

  disconnectedCallback() {
    store.listeners.delete(this._render);
  }

  set hass(hass) {
    this._hass = hass;
    feed(hass);
    if (!this._drawn) this.render();
  }

  setConfig(config) {
    this._config = config || {};
    this.render();
  }

  paint(html) {
    this._drawn = true;
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>${html}`;
  }

  message(text) {
    this.paint(`<div class="hacard"><div class="msg">${esc(text)}</div></div>`);
  }
}

// ---------- one plant ----------

class PlantsCard extends PlantsBase {
  static getConfigElement() {
    return document.createElement("plants-card-editor");
  }

  static getStubConfig() {
    const first = store.plants && store.plants[0];
    return { plant: first ? first.entry_id : "" };
  }

  getCardSize() {
    return 5;
  }

  getGridOptions() {
    return { columns: 6, min_columns: 6, rows: "auto" };
  }

  plant() {
    const want = this._config && this._config.plant;
    if (!store.plants || !want) return null;
    return store.plants.find((p) => p.entry_id === want || p.name === want) || null;
  }

  render() {
    if (!this._config) return;
    if (!this._config.plant) return this.message("Pick a plant in the card editor.");
    if (store.error && !store.plants) return this.message(`Plants integration: ${store.error}`);
    if (!store.plants) return this.message("Loading…");
    const p = this.plant();
    if (!p) return this.message(`No plant "${this._config.plant}".`);

    const temp = reading(p, "temperature");
    const light = reading(p, "illuminance");
    const fert = reading(p, "conductivity");
    const moist = reading(p, "moisture");
    const sub = [
      temp.value !== null ? `${temp.value.toFixed(1)}°C` : null,
      light.value !== null ? lux(light.value) : null,
    ].filter(Boolean).join(" · ") || esc(p.species || p.sensor || "");
    const hue = notchHue(p);
    const probe = p.status === "check_probe";

    const band = `<div class="band clickable" data-entity="${esc(moist.entity || "")}">
      ${notch(hue, markSvg(p, hue))}
      <div class="ident"><b>${esc(p.name)}</b><span>${esc(sub)}</span></div>
      <div class="chips">
        ${chip("fert", fmt(fert.value), "", probe ? "var(--bad)" : null)}
        ${chip("floor", fmt(p.floor), "%")}
      </div></div>`;

    const hero = probe
      ? `<div class="empty"><b style="color:var(--bad)">${fmt(moist.value)}<span style="font-size:20px">%</span></b>
          <span>Soil moisture reads zero, which a probe in soil never does</span></div>`
      : `<div class="reading">
          <div class="big" style="color:${statusHue(p)}">${fmt(moist.value)}<sup>%</sup></div>
          <div class="aside">
            <div>Floor <b>${fmt(p.floor)}%</b>, target to ${fmt(p.ceiling)}%</div>
            <div>${trendLine(p)}</div>
            <div>${wateredLine(p)}</div>
          </div></div>`;

    this.paint(`<div class="hacard">${band}${hero}${pills(p)}${curve(p, this._id)}</div>`);
    const b = this.shadowRoot.querySelector(".band");
    b.addEventListener("click", () => moreInfo(this, b.dataset.entity));
  }
}

// ---------- triage ----------

const NEED = { check_probe: 0, dry: 1, water_soon: 2, stale: 3, ok: 4 };

function verdict(p) {
  switch (p.status) {
    case "check_probe": return ["bad", "Check probe"];
    case "dry": return ["bad", "Water now"];
    case "water_soon": return ["warn", "Soon"];
    case "stale": return ["", "No reading"];
    default: return ["ok", "OK"];
  }
}

function whoLine(p) {
  if (p.watering_pending) return "watering detected";
  if (p.status === "check_probe") return "probe suspect";
  if (p.status === "stale") return "sensor quiet";
  if (p.status === "dry") {
    const w = ago(p.last_watered);
    return w ? `watered ${w}` : "below floor";
  }
  const f = until(p.forecast);
  return f ? `floor ${f}` : "in range";
}

class PlantsTriageCard extends PlantsBase {
  static getStubConfig() {
    return {};
  }

  getCardSize() {
    return 3;
  }

  getGridOptions() {
    return { columns: 6, min_columns: 6, rows: "auto" };
  }

  render() {
    if (!this._config) return;
    if (store.error && !store.plants) return this.message(`Plants integration: ${store.error}`);
    if (!store.plants) return this.message("Loading…");
    const plants = [...store.plants].sort((a, b) => {
      const d = (NEED[a.status] ?? 5) - (NEED[b.status] ?? 5);
      if (d) return d;
      const ra = (reading(a, "moisture").value ?? 0) / Math.max(1, a.floor || 1);
      const rb = (reading(b, "moisture").value ?? 0) / Math.max(1, b.floor || 1);
      return ra - rb;
    });
    if (!plants.length) return this.message("No plants yet. Add one under Settings, Devices and services.");

    const due = plants.filter((p) => p.status === "dry" || p.status === "check_probe").length;
    const soon = plants.filter((p) => p.status === "water_soon").length;
    const scale = Math.max(60, ...plants.map((p) => num(p.ceiling) ?? 0), ...plants.map((p) => reading(p, "moisture").value ?? 0));
    const hue = due ? HUE.bad : soon ? HUE.warn : HUE.ok;
    const count = plants.length === 1 ? "One plant" : `${plants.length} plants`;
    const summary = due === plants.length ? "all below their floor"
      : due ? `${due} below the floor` : soon ? `${soon} due soon` : "all in range";

    const rows = plants.map((p) => {
      const m = reading(p, "moisture");
      const [cls, text] = verdict(p);
      const width = m.value === null ? 0 : Math.max(0.4, Math.min(100, (m.value / scale) * 100));
      const tick = Math.min(100, ((num(p.floor) ?? 0) / scale) * 100);
      return `<div class="trow" data-entity="${esc(m.entity || "")}">
        <span class="who">${esc(p.name)}<i>${esc(whoLine(p))}</i></span>
        <span class="meter"><u style="width:${width.toFixed(1)}%"></u><em style="left:calc(${tick.toFixed(1)}% - 1px)"></em></span>
        <span class="val" style="color:${statusHue(p)}">${fmt(m.value)}%</span>
        <span class="verdict ${cls}">${esc(text)}</span></div>`;
    }).join("");

    this.paint(`<div class="hacard">
      <div class="band">
        ${notch(hue, svg(due || soon ? ALERT_MARK : CHECK_MARK, hue))}
        <div class="ident"><b>${esc(this._config.title || "Watering")}</b><span>${esc(`${count} · ${summary}`)}</span></div>
        <div class="chips">${chip("due", String(due), "", due ? "var(--bad)" : null)}</div>
      </div>
      <div class="triage">${rows}</div>
      <div class="tscale"><span>0%</span><span>${Math.round(scale)}%</span></div>
      <div class="key">
        <span><u style="background:var(--moist)"></u>Measured moisture</span>
        <span><em></em>Each plant&rsquo;s floor</span>
      </div></div>`);
    for (const r of this.shadowRoot.querySelectorAll(".trow")) {
      r.addEventListener("click", () => moreInfo(this, r.dataset.entity));
    }
  }
}

// ---------- editor ----------

class PlantsCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    feed(hass);
    if (!this._listening) {
      this._listening = () => this.render();
      store.listeners.add(this._listening);
    }
    if (this._form) this._form.hass = hass;
  }

  disconnectedCallback() {
    if (this._listening) store.listeners.delete(this._listening);
    this._listening = null;
  }

  render() {
    if (!this._config) return;
    const options = (store.plants || []).map((p) => ({ value: p.entry_id, label: p.name }));
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => (s.name === "plant" ? "Plant" : s.name);
      this._form.addEventListener("value-changed", (ev) => {
        this._config = { ...this._config, ...ev.detail.value };
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = [{ name: "plant", required: true, selector: { select: { options, mode: "dropdown" } } }];
    this._form.data = this._config;
  }
}

const define = (name, cls) => {
  if (!customElements.get(name)) customElements.define(name, cls);
};
define("plants-card", PlantsCard);
define("plants-triage-card", PlantsTriageCard);
define("plants-card-editor", PlantsCardEditor);

window.customCards = window.customCards || [];
for (const c of [
  { type: "plants-card", name: "Plant", description: "One plant: moisture, trend and its week." },
  { type: "plants-triage-card", name: "Plants: who needs water", description: "Every plant, sorted by need, against its own floor." },
]) {
  if (!window.customCards.some((x) => x.type === c.type)) window.customCards.push({ ...c, preview: true });
}

console.info(`%c plants-card %c ${VERSION} `, "background:#58a05c;color:#0e1012;font-weight:700", "background:#23272b;color:#e7e9ec");
