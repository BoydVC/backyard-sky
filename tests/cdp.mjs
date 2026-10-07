// Minimal Chrome DevTools Protocol driver (Node 20, --experimental-websocket). One headless Chrome, niced, throwaway profile.
// WebGL runs on SwiftShader (software) so it works on the box without a GPU.
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export async function launch(port = 9561, w = 1440, h = 900) {
  const prof = mkdtempSync(join(tmpdir(), "bsky-"));
  const proc = spawn("nice", ["-n", "15", "google-chrome", "--headless=new", "--no-sandbox", "--hide-scrollbars", "--mute-audio", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
    `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, `--window-size=${w},${h}`, "about:blank"], { stdio: "ignore" });
  let target; for (let i = 0; i < 120 && !target; i++) { await sleep(250); try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === "page"); } catch {} }
  if (!target) { proc.kill(); throw new Error("chrome did not start"); }
  const ws = new WebSocket(target.webSocketDebuggerUrl); await new Promise((r, j) => { ws.addEventListener("open", r); ws.addEventListener("error", j); });
  let id = 0; const pending = new Map(); const errors = [];
  ws.addEventListener("message", (m) => { const j = JSON.parse(m.data); if (j.id && pending.has(j.id)) { pending.get(j.id)(j); pending.delete(j.id); }
    if (j.method === "Runtime.exceptionThrown") errors.push(j.params.exceptionDetails.exception?.description || j.params.exceptionDetails.text);
    if (j.method === "Runtime.consoleAPICalled" && j.params.type === "error") errors.push("console.error: " + j.params.args.map((a) => a.value ?? a.description).join(" "));
    if (j.method === "Log.entryAdded" && j.params.entry.level === "error") errors.push("log: " + j.params.entry.text); });
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, (j) => r(j.result || {})); ws.send(JSON.stringify({ id: i, method, params })); });
  await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
  const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error("eval failed: " + expr.slice(0, 90) + " :: " + (r.exceptionDetails.exception?.description || r.exceptionDetails.text)); return r.result?.value; };
  const viewport = (w2, h2, mobile = false, scale = 1) => send("Emulation.setDeviceMetricsOverride", { width: w2, height: h2, deviceScaleFactor: scale, mobile });
  const goto = async (url, wait = 1500) => { await send("Page.navigate", { url }); await sleep(wait); };
  const shot = async (path) => { const r = await send("Page.captureScreenshot", { format: "png" }); writeFileSync(path, Buffer.from(r.data, "base64")); };
  const mouse = (x, y) => send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
  const close = async () => { try { ws.close(); } catch {} proc.kill(); await sleep(400); rmSync(prof, { recursive: true, force: true }); };
  return { send, ev, viewport, goto, shot, mouse, close, errors };
}
