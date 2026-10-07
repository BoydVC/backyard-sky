// Loads a page in headless Chrome, clicks through every night/tab/button and plays the dome; prints JSON with any JS errors.
import { launch, sleep } from "./cdp.mjs";
const url = process.argv[2];
const b = await launch(9900 + Math.floor(Math.random() * 90), 1280, 900); await b.viewport(1280, 900);
const out = { url };
try {
  await b.goto(url, 2500);
  out.ready = await b.ev("!!(window.__sky && __sky.ready)");
  out.moments = await b.ev("document.querySelectorAll('.m').length");
  out.nights = await b.ev("document.querySelectorAll('.tab').length");
  out.domeNonBlank = await b.ev("(()=>{const c=document.getElementById('dome');const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4*97)if(d[i]>0)n++;return n})()");
  for (let i = 0; i < out.nights; i++) { await b.ev(`document.querySelectorAll('.tab')[${i}].click()`); await sleep(300);
    await b.ev("document.querySelectorAll('[data-jump]').forEach(x=>x.click())"); await b.ev("document.querySelectorAll('.m').forEach(x=>x.click())"); }
  await b.ev("document.getElementById('nowBtn').click()"); await b.ev("document.getElementById('play').click()"); await sleep(1500);
  out.played = await b.ev("__sky.minute"); await b.ev("document.getElementById('play').click()");
  // star position check point: Vega alt/az from the page's JS at a fixed instant
  out.vega = await b.ev("(()=>{const s=__sky.SKY.stars.find(x=>x[0]==='Vega');return __sky.starAltAz(s[1],s[2],new Date('2026-10-08T01:00:00Z'))})()");
  out.text = await b.ev("document.body.innerText.length");
} catch (e) { out.exception = String(e); }
out.errors = b.errors; console.log(JSON.stringify(out)); await b.close();
