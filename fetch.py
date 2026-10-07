#!/usr/bin/env python3
"""Backyard Sky Tonight: fetch raw public data into data/ and record fetch times in data/manifest.json.
Keeps the previous file if a source is unreachable (the manifest says so)."""
import json, os, shutil, subprocess, sys, datetime, hashlib
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(D, exist_ok=True)
LAT, LON = 39.06, -76.65
UA = "BackyardSky/1.0 (personal family sky page; contact: none)"
today = datetime.date.today()
SOURCES = [
  # name, url, file, note
  ("celestrak-stations", "http://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle", "stations.tle", "Space stations (ISS, Tiangong) two-line elements. Plain HTTP because HTTPS to CelesTrak fails the TLS handshake from this box."),
  ("celestrak-visual", "http://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle", "visual.tle", "CelesTrak '100 (or so) brightest' satellites."),
  ("celestrak-last-30-days", "http://celestrak.org/NORAD/elements/gp.php?GROUP=last-30-days&FORMAT=json", "last30.json", "Objects launched in the last 30 days (used to find fresh Starlink batches = 'trains')."),
  ("weather-gov-points", f"https://api.weather.gov/points/{LAT},{LON}", "points.json", "NWS grid lookup for the town-center point."),
  ("weather-gov-forecast", "https://api.weather.gov/gridpoints/LWX/109,80/forecast", "forecast.json", "NWS 7-day text forecast (12-hour periods)."),
  ("weather-gov-grid", "https://api.weather.gov/gridpoints/LWX/109,80", "grid.json", "NWS raw gridded forecast (skyCover % by hour)."),
  ("usno-rstt-today", f"https://aa.usno.navy.mil/api/rstt/oneday?date={today.isoformat()}&coords={LAT},{LON}&tz=-5&dst=true", "usno.json", "US Naval Observatory sun/moon rise-set, used only as an independent cross-check."),
  ("jpl-de421", "https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de421.bsp", "de421.bsp", "JPL DE421 planetary ephemeris (valid 1900-2050). Downloaded once."),
]
man_path = os.path.join(D, "manifest.json")
man = json.load(open(man_path)) if os.path.exists(man_path) else {"sources": {}}
man.setdefault("sources", {})
for name, url, fn, note in SOURCES:
    out = os.path.join(D, fn)
    if fn == "de421.bsp" and os.path.exists(out) and os.path.getsize(out) > 16_000_000:
        e = man["sources"].get(name, {}); e.update(url=url, file=fn, note=note, bytes=os.path.getsize(out))
        e.setdefault("fetched_at", datetime.datetime.fromtimestamp(os.path.getmtime(out)).astimezone().isoformat(timespec="seconds"))
        man["sources"][name] = e; print("keep", fn); continue
    tmp = out + ".part"
    r = subprocess.run(["curl", "-sS", "-f", "-m", "60", "-A", UA, "-H", "Accept: application/geo+json, application/json, */*", "-o", tmp, url], capture_output=True, text=True)
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    if r.returncode == 0 and os.path.getsize(tmp) > 100:
        shutil.move(tmp, out)
        man["sources"][name] = dict(url=url, file=fn, note=note, fetched_at=now, bytes=os.path.getsize(out),
                                    sha256=hashlib.sha256(open(out, "rb").read()).hexdigest()[:16], status="ok")
        print("ok  ", fn, os.path.getsize(out))
    else:
        if os.path.exists(tmp): os.remove(tmp)
        e = man["sources"].get(name, dict(url=url, file=fn, note=note))
        e.update(last_attempt=now, status="failed, kept previous copy" if os.path.exists(out) else "failed, no copy", error=r.stderr.strip()[:200])
        man["sources"][name] = e; print("FAIL", fn, r.stderr.strip()[:120])
# Starlink cache from the sibling project (read-only reference; copied so this folder is self-contained)
sg = "/workspace/tokenmax/starlink-globe/data"
if os.path.exists(os.path.join(sg, "starlink-omm.json")):
    meta = json.load(open(os.path.join(sg, "fetch-meta.json")))
    shutil.copy(os.path.join(sg, "starlink-omm.json"), os.path.join(D, "starlink-omm.json"))
    man["sources"]["celestrak-starlink (via starlink-globe cache)"] = dict(url=meta["url"], file="starlink-omm.json", fetched_at=meta["fetched_at"], count=meta["count"],
        note="Full Starlink element set fetched earlier tonight by the Starlink Globe project; copied here. Used to cross-check the fresh last-30-days Starlink elements.", status="ok (copied)")
man["location"] = dict(lat=LAT, lon=LON, label="Millersville, MD (town center, not a street address)", elevation_m=30)
man["updated_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
json.dump(man, open(man_path, "w"), indent=1)
print("manifest written")
