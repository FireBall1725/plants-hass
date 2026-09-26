// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 FireBall1725
// Renders every card against a stubbed DOM and fake plants/list + plants/history,
// and checks each card has the blocks that make it that card (node --check won't
// catch a ReferenceError or a typo in a template).
import assert from "node:assert/strict";

class Node_ { constructor() { this.children = []; this.listeners = {}; this.dataset = {}; }
  addEventListener(t, f) { (this.listeners[t] ||= []).push(f); }
  appendChild(c) { this.children.push(c); return c; }
  dispatchEvent() { return true; } }
class ShadowRoot_ extends Node_ { constructor() { super(); this.innerHTML = ""; }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  querySelectorAll(sel) {
    const cls = sel.replace(".", "");
    const n = (this.innerHTML.match(new RegExp(`class="[^"]*\\b${cls}\\b`, "g")) || []).length;
    return Array.from({ length: n }, () => { const e = new Node_(); e.dataset = { entity: "sensor.x" }; return e; });
  } }
globalThis.HTMLElement = class extends Node_ { attachShadow() { this.shadowRoot = new ShadowRoot_(); return this.shadowRoot; } };
const registry = new Map();
globalThis.customElements = { get: (n) => registry.get(n), define: (n, c) => registry.set(n, c) };
globalThis.CustomEvent = class { constructor(t, o) { this.type = t; Object.assign(this, o); } };
globalThis.document = { createElement: (n) => { const C = registry.get(n); return C ? new C() : new Node_(); } };
globalThis.window = globalThis;
console.info = () => {};

const now = Date.now();
const iso = (h) => new Date(now + h * 3600e3).toISOString();
const r = (value, unit = "%", entity = "sensor.m") => ({ value, unit, age: 120, entity_id: entity });
const plants = [
  { entry_id: "a", name: "Jade", icon: "succulent", status: "ok", floor: 8, ceiling: 30, trend: -0.96,
    forecast: iso(72), last_watered: iso(-40), watering_pending: null,
    readings: { moisture: r(18), temperature: r(20.6, "°C", "sensor.t"), illuminance: r(9700, "lx"), conductivity: r(22, "µS/cm"), battery: r(98) } },
  { entry_id: "b", name: "Basil", icon: "herb", status: "dry", floor: 25, ceiling: 60, trend: null,
    forecast: null, last_watered: null, watering_pending: { since: iso(-6), rise: 23, confirms_at: iso(1) },
    readings: { moisture: r(6), temperature: r(null), illuminance: r(null), conductivity: r(35), battery: r(98) } },
  { entry_id: "c", name: "Ginger <b>", icon: "custom", icon_image: "data:image/png;base64,AAAA", status: "check_probe",
    floor: 20, ceiling: 50, trend: 0, forecast: null, last_watered: iso(-200), watering_pending: null,
    readings: { moisture: r(0), temperature: r(20.9), illuminance: r(400), conductivity: r(0), battery: r(98) } },
];
const series = Array.from({ length: 168 }, (_, i) => (i % 40 === 7 ? null : 12 - i * 0.05));
// Daily light peaks: day 6 is dark for everyone, which the card should mark.
const peaks = (base) => Array.from({ length: 10 }, (_, i) => (i === 6 ? base * 0.3 : base));
let light = { a: peaks(9700), b: [], c: peaks(9900) };
const hass = { states: {}, callWS: async (m) =>
  m.type === "plants/list" ? plants
    : m.reading === "illuminance" ? { start: iso(-240), period: "day", series: light }
    : { start: iso(-168), series: { a: series, b: series, c: series.map(() => 0) } } };

await import("../../custom_components/plants/frontend/plants-card.js");
const Plant = registry.get("plants-card"), Triage = registry.get("plants-triage-card");
assert.ok(Plant && Triage && registry.get("plants-card-editor"), "all three elements defined");

const cards = {};
for (const id of ["a", "b", "c"]) {
  const c = new Plant(); c.setConfig({ plant: id }); c.connectedCallback(); c.hass = hass; cards[id] = c;
}
const t = new Triage(); t.setConfig({}); t.connectedCallback(); t.hass = hass;
const Light = registry.get("plants-light-card"), Battery = registry.get("plants-battery-card");
assert.ok(Light && Battery, "light and battery cards defined");
const l = new Light(); l.setConfig({}); l.connectedCallback(); l.hass = hass;
const bt = new Battery(); bt.setConfig({}); bt.connectedCallback(); bt.hass = hass;
await new Promise((res) => setTimeout(res, 20));

const html = (c) => c.shadowRoot.innerHTML;
for (const id of ["a", "b", "c"]) {
  const h = html(cards[id]);
  for (const block of ["class=\"band", "class=\"notch", "class=\"chips", "class=\"bleedchart", "class=\"pills", "Floor "]) {
    assert.ok(h.includes(block), `plant ${id} missing ${block}`);
  }
}
assert.ok(html(cards.a).includes("class=\"reading") && html(cards.a).includes("Falling <b>0.96%/day"), "jade reading + trend");
assert.ok(html(cards.a).includes("<polyline"), "curve drawn");
assert.ok(html(cards.b).includes("pill bad") && html(cards.b).includes("Watering detected"), "basil pills");
assert.ok(html(cards.c).includes("class=\"empty") && !html(cards.c).includes("class=\"reading"), "probe card uses the empty block");
assert.ok(html(cards.c).includes("Ginger &lt;b&gt;"), "names are escaped");
const th = html(t);
for (const block of ["class=\"triage", "class=\"trow", "class=\"meter", "class=\"verdict", "class=\"tscale", "class=\"key"]) {
  assert.ok(th.includes(block), `triage missing ${block}`);
}
assert.ok(th.indexOf("Ginger") < th.indexOf("Basil") && th.indexOf("Basil") < th.indexOf("Jade"), "sorted by need");
assert.ok(th.includes("2 below the floor"), "summary counts");

l.render();
const lh = html(l);
for (const block of ["class=\"band", "class=\"bleedchart", "class=\"key", "peak lux per day"]) {
  assert.ok(lh.includes(block), `light missing ${block}`);
}
assert.equal((lh.match(/<polyline/g) || []).length, 2, "one line per plant with history");
assert.ok(lh.includes("dimmest day") && lh.includes("Dimmest"), "dark day marked");
assert.ok(lh.includes("Jade 9.7k"), "key carries the latest peak");

// A lasting drop (moved away from the window) is a step, not a dark day.
const stepped = (base) => Array.from({ length: 10 }, (_, i) => (i >= 6 ? base * 0.05 : base));
light = { a: stepped(9700), b: stepped(5000), c: stepped(9900) };
const l2 = new Light(); l2.setConfig({ days: 9 }); l2.connectedCallback(); l2.hass = hass;
await new Promise((res) => setTimeout(res, 20));
l2.render();
assert.ok(html(l2).includes("less light since") && !html(l2).includes("dimmest day"), "step reads as less light");
const xs = [...html(l2).matchAll(/points="([^"]*)"/g)].flatMap((m) => m[1].trim().split(/\s+/).map((pt) => Number(pt.split(",")[0])));
assert.ok(xs.length && xs.every((x) => x >= 0 && x <= 100), "no point past the right edge");
const bh = html(bt);
for (const block of ["class=\"bat\"", "class=\"batrow", "class=\"cell", "Last contact", "2 min ago", "lowest"]) {
  assert.ok(bh.includes(block), `battery missing ${block}`);
}
assert.equal((bh.match(/class="batrow" data-entity/g) || []).length, 3, "a row per plant");

// Custom icon on a plant that isn't in check_probe renders as a tinted mask.
plants[2].status = "ok";
const c2 = new Plant(); c2.setConfig({ plant: "c" }); c2.hass = hass; c2.render();
assert.ok(html(c2).includes("mask-image:url(data:image/png"), "custom icon mask");
console.log("plants-card smoke: ok");
