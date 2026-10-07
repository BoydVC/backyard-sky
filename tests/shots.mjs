import { launch, sleep } from "./cdp.mjs";
import { fileURLToPath } from "node:url"; import { dirname, join } from "node:path";
const R = join(dirname(fileURLToPath(import.meta.url)), ".."), OUT = join(R, "screenshots"), U = "file://" + join(R, "dist/backyard-sky-snapshot.html");
const b = await launch(9800 + Math.floor(Math.random() * 90), 1440, 900);
const full = async (path, w) => { const h = await b.ev("document.documentElement.scrollHeight"); await b.viewport(w, Math.min(h, 4000), w < 600, w < 600 ? 2 : 1); await sleep(800); await b.shot(path); };
try {
  await b.viewport(1440, 900); await b.goto(U + "?t=21", 2500); await b.shot(join(OUT, "00-best-desktop-tonight-9pm.png"));
  await full(join(OUT, "01-desktop-full-page.png"), 1440);
  await b.viewport(1440, 900); await b.goto(U + "?night=3&t=dawn", 2500); await b.ev("document.querySelector('.m').click()"); await sleep(1200);
  await b.ev("window.scrollTo(0,0)"); await sleep(300); await b.shot(join(OUT, "02-desktop-saturday-preDawn-iss.png"));
  await b.viewport(390, 844, true, 2); await b.goto(U + "?t=21", 2500); await b.shot(join(OUT, "03-phone-top.png"));
  await b.ev("document.getElementById('domeCard').scrollIntoView()"); await sleep(500); await b.shot(join(OUT, "04-phone-sky-dome.png"));
} catch (e) { console.error(e.stack); process.exitCode = 1; }
console.log("errors", JSON.stringify(b.errors)); await b.close();
