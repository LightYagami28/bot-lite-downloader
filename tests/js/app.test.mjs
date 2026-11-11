import assert from "node:assert/strict";
import { test } from "node:test";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const APP_PATH = path.resolve(import.meta.dirname, "../../botlite/webapp/static/app.js");
const APP = pathToFileURL(APP_PATH).href;
const SOURCE = readFileSync(APP_PATH, "utf8");
const MB = 1024 * 1024;
const GB = 1024 * MB;

function makeElement() {
  const classes = new Set();
  return {
    textContent: "",
    className: "",
    value: "",
    style: {},
    children: [],
    listeners: {},
    classList: {
      add: (name) => classes.add(name),
      remove: (name) => classes.delete(name),
      has: (name) => classes.has(name),
    },
    replaceChildren(child) { this.children = [child]; },
    addEventListener(type, handler) { this.listeners[type] = handler; },
  };
}

function reply(body, { ok = true, status = 200 } = {}) {
  return { ok, status, json: async () => body };
}

const STATUS = { version: "1.2.0", uptime: "1h", max_concurrent: 3, active_downloads: 0, free_disk_bytes: 10 * GB, free_disk: "10 GB" };

// Loads app.js in a fresh module instance against a fake DOM and fake fetch.
async function load({ initData = "", routes = {} }) {
  const elements = new Map();
  const calls = [];
  const timers = [];
  globalThis.document = {
    getElementById(id) {
      if (!elements.has(id)) { elements.set(id, makeElement()); }
      return elements.get(id);
    },
    createElement: () => makeElement(),
  };
  globalThis.Telegram = initData ? { WebApp: { initData, expand() {}, ready() {} } } : undefined;
  globalThis.setTimeout = (callback) => { timers.push(callback); return timers.length; };
  globalThis.clearTimeout = () => {};
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    const route = routes[url];
    if (route instanceof Error) { throw route; }
    return route;
  };
  // Same identifier on every run, so V8 coverage is attributed to the real file.
  const module = new vm.SourceTextModule(SOURCE, { identifier: APP, context: vm.createContext(globalThis) });
  await module.link(() => { throw new Error("app.js has no imports"); });
  await module.evaluate();
  const el = (id) => document.getElementById(id);
  return { el, calls, timers };
}

test("status ok with idle downloads and plenty of disk", async () => {
  const { el } = await load({ routes: { "/api/status": reply(STATUS) } });
  assert.equal(el("ver").textContent, "v1.2.0");
  assert.equal(el("active").children[0].className, "badge badge-green");
  assert.equal(el("disk").children[0].className, "badge badge-green");
  assert.equal(el("disk-bar").style.width, "20%");
  assert.equal(el("disk-bar").classList.has("crit"), false);
});

test("status with active downloads and critical disk", async () => {
  const body = { ...STATUS, active_downloads: 2, free_disk_bytes: 100 * MB };
  const { el } = await load({ routes: { "/api/status": reply(body) } });
  assert.equal(el("active").children[0].className, "badge badge-orange");
  assert.equal(el("disk").children[0].className, "badge badge-red");
  assert.ok(el("disk-bar").classList.has("crit"));
});

test("status with low disk shows a warning and caps the bar at 100%", async () => {
  const low = await load({ routes: { "/api/status": reply({ ...STATUS, free_disk_bytes: GB }) } });
  assert.equal(low.el("disk").children[0].className, "badge badge-orange");
  assert.ok(low.el("disk-bar").classList.has("warn"));
  const huge = await load({ routes: { "/api/status": reply({ ...STATUS, free_disk_bytes: 100 * GB }) } });
  assert.equal(huge.el("disk-bar").style.width, "100%");
});

test("status errors raise a toast that hides itself", async () => {
  for (const route of [reply({}, { ok: false, status: 500 }), new Error("offline")]) {
    const { el, timers } = await load({ routes: { "/api/status": route } });
    assert.match(el("toast").textContent, /Could not load status/);
    assert.ok(el("toast").classList.has("show"));
    timers[0]();
    assert.equal(el("toast").classList.has("show"), false);
  }
});

test("admin statistics map the success rate to a badge", async () => {
  const cases = [[0, 0, "100%", "badge-green"], [95, 5, "95%", "badge-green"], [75, 25, "75%", "badge-orange"], [10, 90, "10%", "badge-red"]];
  for (const [total_downloads, failed_downloads, text, badge] of cases) {
    const { el, calls } = await load({
      initData: "signed",
      routes: { "/api/status": reply(STATUS), "/api/stats": reply({ total_downloads, failed_downloads }) },
    });
    assert.equal(calls[1].options.headers["X-Telegram-Init-Data"], "signed");
    assert.equal(el("admin-section").style.display, "block");
    assert.equal(el("success-rate").children[0].textContent, text);
    assert.equal(el("success-rate").children[0].className, `badge ${badge}`);
  }
});

test("admin section stays hidden when statistics are refused or unreachable", async () => {
  for (const route of [reply({}, { ok: false, status: 403 }), new Error("offline")]) {
    const { el } = await load({ initData: "signed", routes: { "/api/status": reply(STATUS), "/api/stats": route } });
    assert.equal(el("admin-section").style.display, undefined);
  }
});

test("ban and unban actions", async () => {
  const post = reply({});
  const { el, calls } = await load({
    initData: "signed",
    routes: { "/api/status": reply(STATUS), "/api/stats": reply({ total_downloads: 1, failed_downloads: 0 }), "/api/ban": post, "/api/unban": post },
  });
  const input = el("ban-uid");

  input.value = "  ";
  await el("btn-ban").listeners.click();
  assert.equal(el("toast").textContent, "Enter a Telegram User ID");

  input.value = "abc";
  await el("btn-ban").listeners.click();
  assert.equal(el("toast").textContent, "Invalid User ID");

  input.value = "42";
  await el("btn-ban").listeners.click();
  assert.match(el("toast").textContent, /User 42 banned/);
  assert.equal(input.value, "");
  assert.deepEqual(JSON.parse(calls.at(-1).options.body), { user_id: 42 });

  input.value = "42";
  await el("btn-unban").listeners.click();
  assert.match(el("toast").textContent, /User 42 unbanned/);
});

test("ban action reports authorization, server and network failures", async () => {
  const routes = { "/api/status": reply(STATUS), "/api/ban": reply({}, { ok: false, status: 403 }) };
  const { el } = await load({ routes });
  el("ban-uid").value = "7";
  await el("btn-ban").listeners.click();
  assert.match(el("toast").textContent, /Not authorized/);

  routes["/api/ban"] = reply({}, { ok: false, status: 500 });
  await el("btn-ban").listeners.click();
  assert.match(el("toast").textContent, /Failed/);

  routes["/api/ban"] = new Error("offline");
  await el("btn-ban").listeners.click();
  assert.match(el("toast").textContent, /Network error/);
});
