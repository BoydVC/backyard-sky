#!/usr/bin/env python3
"""Backyard Sky Tonight smoke test. Cross-checks the computed data against independent methods/sources and checks the page for JS errors.
Run: .venv/bin/python tests/smoke.py   (writes tests/last-run.txt)"""
import json, os, sys, math, subprocess, datetime as dt, urllib.request
from zoneinfo import ZoneInfo
import ephem
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); D = os.path.join(H, "data"); ET = ZoneInfo("America/New_York")
sky = json.load(open(os.path.join(D, "sky.json"))); man = json.load(open(os.path.join(D, "manifest.json")))
res = []; 
def check(name, ok, detail=""): res.append((bool(ok), name, detail)); print(("PASS " if ok else "FAIL ") + name + (" :: " + detail if detail else ""))
def p(s): return dt.datetime.fromisoformat(s)
def e2dt(d): return ephem.Date(d).datetime().replace(tzinfo=dt.timezone.utc).astimezone(ET)
def obs(horizon="-0:34", pressure=0):
    o = ephem.Observer(); o.lat, o.lon, o.elevation = str(sky["location"]["lat"]), str(sky["location"]["lon"]), 30; o.pressure = pressure; o.horizon = horizon; return o

# 1. data / manifest
for k, v in man["sources"].items(): check(f"manifest has fetch time: {k}", v.get("fetched_at"), v.get("fetched_at", "missing"))
check("4 nights computed", len(sky["nights"]) == 4)
raw = open(os.path.join(D, "sky.json")).read(); check("no NaN/Infinity in sky.json", "NaN" not in raw and "Infinity" not in raw)

# 2. sunset: skyfield (page) vs PyEphem (independent algorithm), all nights; vs USNO API (independent source) for today
for n in sky["nights"]:
    day = dt.date.fromisoformat(n["date"]); o = obs(); o.date = ephem.Date(dt.datetime(day.year, day.month, day.day, 16, 0))  # noon ET = 16 UTC
    es = e2dt(o.next_setting(ephem.Sun())); diff = abs((p(n["sunset"]) - es).total_seconds())
    check(f"sunset {n['date']} skyfield {p(n['sunset']).strftime('%H:%M:%S')} vs ephem {es.strftime('%H:%M:%S')}", diff < 60, f"{diff:.0f}s apart")
    o2 = obs("-6", 0); o2.date = o.date; ec = e2dt(o2.next_setting(ephem.Sun(), use_center=True)); d2 = abs((p(n["civil_dusk"]) - ec).total_seconds())
    check(f"civil dusk {n['date']} vs ephem {ec.strftime('%H:%M:%S')}", d2 < 60, f"{d2:.0f}s apart")
u = json.load(open(os.path.join(D, "usno.json")))["properties"]["data"]
usno_day = dt.date(u["year"], u["month"], u["day"])
n0 = next((n for n in sky["nights"] if n["date"] == usno_day.isoformat()), None)
if n0:
    for phen, key in (("Set", "sunset"), ("End Civil Twilight", "civil_dusk")):
        t = next(x["time"] for x in u["sundata"] if x["phen"] == phen); hh, mm = map(int, t.split()[0].split(":"))
        ut = dt.datetime(usno_day.year, usno_day.month, usno_day.day, hh, mm, tzinfo=ET); d = abs((p(n0[key]) - ut).total_seconds())
        check(f"{key} today vs US Naval Observatory API ({t.strip()})", d <= 90, f"page {p(n0[key]).strftime('%H:%M:%S')}, {d:.0f}s from USNO's rounded minute")
    check("moon phase name matches USNO", n0["moon"]["phase"] == u["curphase"], f"{n0['moon']['phase']} vs {u['curphase']}")
else: check("USNO data is for a computed night", False, str(usno_day))

# 3. moon rise/set vs ephem
for n in sky["nights"]:
    day = dt.date.fromisoformat(n["date"]); o = obs(); o.date = ephem.Date(dt.datetime(day.year, day.month, day.day, 16, 0))
    for key, fn in (("rise", o.next_rising), ("set", o.next_setting)):
        if not n["moon"][key]: continue
        try: e = e2dt(fn(ephem.Moon()))
        except Exception as ex: check(f"moon{key} {n['date']}", False, str(ex)); continue
        d = abs((p(n["moon"][key]) - e).total_seconds()); check(f"moon{key} {n['date']} vs ephem", d < 120, f"{d:.0f}s apart")

# 4. planets: Saturn & Jupiter position vs ephem at 9 PM tonight
n = sky["nights"][0]; k = 0; g0 = p(n["grid_start"])
target = g0.replace(hour=21, minute=0, second=0); k = int((target - g0).total_seconds() // 300); tk = g0 + dt.timedelta(minutes=5 * k)
for pl in n["planets"]:
    if pl["name"] not in ("Saturn", "Jupiter", "Mars"): continue
    o = obs(); o.date = ephem.Date(tk.astimezone(dt.timezone.utc).replace(tzinfo=None)); b = getattr(ephem, pl["name"])(); b.compute(o)
    alt, az = math.degrees(b.alt), math.degrees(b.az); a2, z2 = pl["track"][k]
    check(f"{pl['name']} alt/az at {tk.strftime('%H:%M')} vs ephem", abs(alt - a2) < 0.3 and abs((az - z2 + 180) % 360 - 180) < 0.5, f"page {a2},{z2} vs ephem {alt:.1f},{az:.1f}")

# 5. space-station passes: skyfield SGP4 vs PyEphem's own SGP4 implementation
L = [l.rstrip() for l in open(os.path.join(D, "stations.tle")) if l.strip()]
tles = {L[i].strip(): (L[i], L[i + 1], L[i + 2]) for i in range(0, len(L) - 2, 3)}
check("at least one visible space-station pass computed", len(sky["station_passes"]) > 0, str(len(sky["station_passes"])))
def alt_at(sat, o, d):
    o.date = ephem.Date(d.astimezone(dt.timezone.utc).replace(tzinfo=None)); sat.compute(o); return math.degrees(sat.alt)
def cross(sat, o, lo, hi, rising):  # bisection for the 10-degree crossing using ephem's propagator
    for _ in range(40):
        mid = lo + (hi - lo) / 2
        if (alt_at(sat, o, mid) > 10) == rising: hi = mid
        else: lo = mid
    return lo + (hi - lo) / 2
for sp in sky["station_passes"]:
    t = tles[sp["name"]]; sat = ephem.readtle(*t); o = obs("0", 0)
    o.date = ephem.Date((p(sp["culm"]) - dt.timedelta(minutes=15)).astimezone(dt.timezone.utc).replace(tzinfo=None))
    r = o.next_pass(sat); mt, malt = e2dt(r[2]), math.degrees(r[3])
    rt = cross(sat, o, mt - dt.timedelta(minutes=12), mt, True); st = cross(sat, o, mt, mt + dt.timedelta(minutes=12), False)
    dr, dm, ds = (abs((p(sp[a]) - b).total_seconds()) for a, b in (("rise", rt), ("culm", mt), ("set", st)))
    check(f"{'ISS' if sp['name'].startswith('ISS') else 'Tiangong'} pass {p(sp['rise']).strftime('%a %H:%M:%S')} vs PyEphem SGP4", dr < 15 and dm < 15 and ds < 15 and abs(malt - sp["culm_alt"]) < 0.5,
          f"rise {dr:.0f}s, peak {dm:.0f}s, set {ds:.0f}s apart; peak alt ephem {malt:.1f} deg vs page {sp['culm_alt']} deg")

# 6. served page + JS errors (served page and offline snapshot)
try:
    body = urllib.request.urlopen("http://127.0.0.1:4268/", timeout=10).read().decode()
    check("server on :4268 serves the page with data", "Backyard Sky" in body and '"nights"' in body)
except Exception as ex: check("server on :4268 reachable", False, str(ex))
for url in ("http://127.0.0.1:4268/", "file://" + os.path.join(H, "dist/backyard-sky-snapshot.html")):
    r = subprocess.run(["node", "--experimental-websocket", os.path.join(H, "tests/js_check.mjs"), url], capture_output=True, text=True, timeout=120)
    try: j = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception: check(f"JS check ran: {url}", False, r.stderr[-300:]); continue
    tag = "snapshot" if url.startswith("file") else "server"
    check(f"[{tag}] no JavaScript errors", not j.get("errors") and "exception" not in j, json.dumps(j.get("errors"))[:300] + j.get("exception", ""))
    check(f"[{tag}] page ready, moments + 4 night tabs rendered", j.get("ready") and j.get("moments", 0) > 0 and j.get("nights") == 4, f"moments={j.get('moments')} tabs={j.get('nights')}")
    check(f"[{tag}] sky dome drawn and animates", j.get("domeNonBlank", 0) > 100 and j.get("played") is not None, f"pixels={j.get('domeNonBlank')} minute={j.get('played')}")
    if tag == "snapshot":
        o = obs("0", 0); o.date = "2026/10/8 01:00:00"; v = ephem.star("Vega"); v.compute(o)
        a, z = j["vega"]; check("dome star math (Vega, JS) vs ephem", abs(a - math.degrees(v.alt)) < 0.7 and abs((z - math.degrees(v.az) + 180) % 360 - 180) < 0.9, f"JS {a:.2f},{z:.2f} vs ephem {math.degrees(v.alt):.2f},{math.degrees(v.az):.2f}")
snap = open(os.path.join(H, "dist/backyard-sky-snapshot.html")).read()
check("snapshot is self-contained (no external src/href)", not any(s in snap for s in ('src="http', "src='http", 'href="http', "@import")))
passed = sum(1 for r in res if r[0])
summary = f"{passed}/{len(res)} checks passed at {dt.datetime.now(ET).isoformat(timespec='seconds')}"
print(summary)
with open(os.path.join(H, "tests/last-run.txt"), "w") as f:
    f.write("\n".join(("PASS " if ok else "FAIL ") + n + (" :: " + d if d else "") for ok, n, d in res) + "\n" + summary + "\n")
sys.exit(0 if passed == len(res) else 1)
