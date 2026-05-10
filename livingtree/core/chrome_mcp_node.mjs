#!/usr/bin/env node

import { createInterface } from "node:readline";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { homedir } from "node:os";

const rl = createInterface({ input: process.stdin, terminal: false });

let browser = null;
let page = null;

// ═══ Chrome binary search paths (same as Python chrome_mcp.py) ═══
function findChromeBinary() {
  const localAppData = process.env.LOCALAPPDATA || resolve(homedir(), "AppData", "Local");
  const candidates = [
    resolve("C:", "Program Files", "Google", "Chrome", "Application", "chrome.exe"),
    resolve("C:", "Program Files (x86)", "Google", "Chrome", "Application", "chrome.exe"),
    resolve(localAppData, "Google", "Chrome", "Application", "chrome.exe"),
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ];
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  return null;
}

// ═══ ensure puppeteer ═══
async function ensurePuppeteer() {
  try {
    const pu = await import("puppeteer-core");
    return pu;
  } catch {
    try {
      const pu = await import("puppeteer");
      return pu;
    } catch {
      console.error(JSON.stringify({ jsonrpc: "2.0", id: 0, error: { code: -1, message: "puppeteer not installed. Run: npm install puppeteer-core" } }));
      process.exit(1);
    }
  }
}

// ═══ Launch Chrome ═══
async function launchChrome(puppeteer, headless) {
  const chromePath = findChromeBinary();
  const opts = {
    headless: headless ? "new" : false,
    args: [
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-extensions",
      "--disable-background-networking",
      "--remote-debugging-port=0",
    ],
  };
  if (chromePath) {
    opts.executablePath = chromePath;
  }
  browser = await puppeteer.launch(opts);
  page = await browser.newPage();
  return { ok: true, chromePath: chromePath || "(bundled)" };
}

// ═══ Methods ═══
async function navigate(params) {
  await page.goto(params.url, { waitUntil: "domcontentloaded", timeout: 15000 });
  return { ok: true, url: params.url, title: await page.title() };
}

async function screenshot(params) {
  if (params.selector) {
    const el = await page.$(params.selector);
    if (!el) throw new Error("selector not found: " + params.selector);
    const buf = await el.screenshot({ encoding: "base64", type: "png" });
    return { ok: true, format: "png", data: buf };
  }
  const opts = { encoding: "base64", type: "png", fullPage: !!params.full_page };
  const buf = await page.screenshot(opts);
  return { ok: true, format: "png", data: buf };
}

async function evaluate(params) {
  const value = await page.evaluate(params.expression);
  return { value, type: typeof value };
}

async function domQuery(params) {
  const elements = await page.$$eval(params.selector, function (els) {
    return els.slice(0, 20).map(function (el) {
      const attrs = [];
      if (el.attributes) {
        for (const a of el.attributes) attrs.push(a.name, a.value);
      }
      return { tag: el.tagName.toLowerCase(), attributes: attrs, text: (el.textContent || "").substring(0, 200) };
    });
  });
  return { count: elements.length, elements };
}

async function accessibilityAudit() {
  const issues = [];
  const title = await page.title();
  if (!title) issues.push("Missing page title");

  const imgCount = await page.$$eval("img:not([alt])", function (els) { return els.length; });
  if (imgCount > 0) issues.push(imgCount + " images missing alt text");

  const headings = await page.$$eval("h1,h2,h3,h4,h5,h6", function (els) { return els.map(function (e) { return e.tagName; }); });
  if (headings.length === 0) issues.push("No heading structure found");

  return { issues, score: Math.max(0, 100 - issues.length * 15) };
}

async function consoleLogs(params) {
  const limit = params.limit || 50;
  return { logs: [], total: 0, note: "console capture requires Runtime.enable before navigation" };
}

async function close() {
  if (browser) {
    await browser.close();
    browser = null;
    page = null;
  }
  return { ok: true };
}

async function status() {
  return {
    running: browser !== null && browser.isConnected(),
    pageUrl: page ? page.url() : "",
    pageTitle: page ? await page.title() : "",
  };
}

// ═══ JSON-RPC Handler ═══
const handlers = {
  initialize: async function (params) {
    const puppeteer = await ensurePuppeteer();
    const headless = params.headless !== undefined ? params.headless : true;
    return await launchChrome(puppeteer, headless);
  },
  navigate: navigate,
  screenshot: screenshot,
  evaluate: evaluate,
  dom_query: domQuery,
  accessibility_audit: accessibilityAudit,
  console_logs: consoleLogs,
  close: close,
  status: status,
};

const toolNames = Object.keys(handlers);

async function handleRequest(msg) {
  const id = msg.id;
  const method = msg.method;
  const params = msg.params;

  if (method === "initialize") {
    const result = await handlers.initialize(params || {});
    return { jsonrpc: "2.0", id: id, result: result };
  }

  if (method === "tools/list") {
    return {
      jsonrpc: "2.0", id: id,
      result: {
        tools: toolNames.filter(function (n) { return n !== "initialize" && n !== "close" && n !== "status"; }).map(function (name) {
          return { name: name, description: "Chrome " + name.replace(/_/g, " ") + " tool", inputSchema: { type: "object", properties: {} } };
        }),
      },
    };
  }

  if (method === "tools/call") {
    const toolName = (params && params.name) || (params && params.tool);
    const toolParams = (params && params.arguments) || (params && params.params) || {};
    if (!toolName || !handlers[toolName]) {
      return { jsonrpc: "2.0", id: id, error: { code: -32601, message: "Unknown tool: " + toolName } };
    }
    try {
      const result = await handlers[toolName](toolParams);
      return { jsonrpc: "2.0", id: id, result: { content: [{ type: "text", text: JSON.stringify(result) }] } };
    } catch (err) {
      return { jsonrpc: "2.0", id: id, error: { code: -32000, message: err.message } };
    }
  }

  return { jsonrpc: "2.0", id: id, error: { code: -32601, message: "Unknown method: " + method } };
}

// ═══ Main loop ═══
rl.on("line", async function (line) {
  line = line.trim();
  if (!line) return;
  try {
    const msg = JSON.parse(line);
    const resp = await handleRequest(msg);
    process.stdout.write(JSON.stringify(resp) + "\n");
  } catch (err) {
    process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32700, message: err.message } }) + "\n");
  }
});

rl.on("close", async function () {
  if (browser) await browser.close();
  process.exit(0);
});
