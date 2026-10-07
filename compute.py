#!/usr/bin/env python3
"""Backyard Sky Tonight: compute sky events for Millersville, MD from the cached raw data in data/.
Writes data/sky.json. Everything is computed from: JPL DE421 (skyfield), CelesTrak elements (SGP4 via skyfield),
ephem's built-in bright-star catalog, and the NWS gridded forecast. Nothing is typed in by hand."""
import json, os, math, datetime as dt
from zoneinfo import ZoneInfo
import numpy as np
from skyfield.api import load, wgs84, EarthSatellite, Star
from skyfield import almanac
from skyfield.magnitudelib import planetary_magnitude
import ephem
from ephem import stars as ephem_stars

HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, "data")
ET = ZoneInfo("America/New_York")
LAT, LON, ELEV = 39.06, -76.65, 30
NIGHTS = int(os.environ.get("NIGHTS", 4))
ts = load.timescale()
eph = load(os.path.join(D, "de421.bsp"))
earth, sun, moon = eph["earth"], eph["sun"], eph["moon"]
topo = wgs84.latlon(LAT, LON, elevation_m=ELEV); obs = earth + topo
NOW = dt.datetime.now(ET)
man = json.load(open(os.path.join(D, "manifest.json")))

def et(t):  # skyfield Time -> aware ET datetime
    return t.utc_datetime().astimezone(ET)
def iso(t): return et(t).isoformat(timespec="seconds")
def hm(d):  # 8:05 PM
    return d.strftime("%-I:%M %p")
def hm_round(d, step=5):
    m = (d.minute + step / 2) // step * step
    d2 = d.replace(minute=0, second=0, microsecond=0) + dt.timedelta(minutes=m)
    return hm(d2)
COMPASS = ["north", "north-northeast", "northeast", "east-northeast", "east", "east-southeast", "southeast", "south-southeast",
           "south", "south-southwest", "southwest", "west-southwest", "west", "west-northwest", "northwest", "north-northwest"]
COMPASS8 = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]
def dir8(az): return COMPASS8[int((az % 360) / 45 + 0.5) % 8]
def dir16(az): return COMPASS[int((az % 360) / 22.5 + 0.5) % 16]
def altword(a):
    if a < 10: return "very low (you need a clear view of the horizon)"
    if a < 25: return "low"
    if a < 50: return "about halfway up"
    if a < 75: return "high"
    return "almost straight overhead"
def fists(a): return round(a / 10)  # a fist at arm's length is about 10 degrees

def tt(d): return ts.from_datetime(d)

# ---------------------------------------------------------------- nights: sun + twilight
nights = []
base = NOW.date()
for i in range(NIGHTS):
    day = base + dt.timedelta(days=i)
    noon = dt.datetime(day.year, day.month, day.day, 12, tzinfo=ET)
    t0, t1 = tt(noon), tt(noon + dt.timedelta(days=1))
    f = almanac.dark_twilight_day(eph, topo)
    times, codes = almanac.find_discrete(t0, t1, f)
    ev = {}
    names = {(4, 3): "sunset", (3, 2): "civil_dusk", (2, 1): "nautical_dusk", (1, 0): "astro_dusk",
             (0, 1): "astro_dawn", (1, 2): "nautical_dawn", (2, 3): "civil_dawn", (3, 4): "sunrise"}
    prev = int(f(t0))
    for t, c in zip(times, codes):
        k = names.get((prev, int(c)))
        if k and k not in ev: ev[k] = t
        prev = int(c)
    nights.append(dict(date=day.isoformat(), label=("Tonight" if i == 0 else ("Tomorrow night" if i == 1 else noon.strftime("%A night"))),
                       weekday=noon.strftime("%a %b %-d"), _t=ev, **{k: iso(v) for k, v in ev.items()}))

# ---------------------------------------------------------------- moon
def moon_info(t):
    e = obs.at(t)
    ill = float(almanac.fraction_illuminated(eph, "moon", t))
    ang = float(almanac.moon_phase(eph, t).degrees)
    if ang < 6 or ang > 354: name = "New Moon"
    elif ang < 84: name = "Waxing Crescent"
    elif ang < 96: name = "First Quarter"
    elif ang < 174: name = "Waxing Gibbous"
    elif ang < 186: name = "Full Moon"
    elif ang < 264: name = "Waning Gibbous"
    elif ang < 276: name = "Last Quarter"
    else: name = "Waning Crescent"
    return ill, ang, name
pt, pc = almanac.find_discrete(tt(NOW - dt.timedelta(days=1)), tt(NOW + dt.timedelta(days=35)), almanac.moon_phases(eph))
next_phases = [dict(name=almanac.MOON_PHASES[int(c)], time=iso(t)) for t, c in zip(pt, pc) if et(t) > NOW][:4]

def rises_sets(body, t0, t1, horizon=None):
    kw = {} if horizon is None else dict(horizon_degrees=horizon)
    r, ry = almanac.find_risings(obs, body, t0, t1, **kw)
    s, sy = almanac.find_settings(obs, body, t0, t1, **kw)
    return [x for x, y in zip(r, ry) if y], [x for x, y in zip(s, sy) if y]

for n in nights:
    day = dt.date.fromisoformat(n["date"]); noon = dt.datetime(day.year, day.month, day.day, 12, tzinfo=ET)
    t0, t1 = tt(noon), tt(noon + dt.timedelta(days=1))
    r, s = rises_sets(moon, t0, t1)
    mid = tt(dt.datetime(day.year, day.month, day.day, 22, tzinfo=ET))
    ill, ang, name = moon_info(mid)
    rise = r[0] if r else None; set_ = s[0] if s else None
    # is the moon up at full dark (end of nautical dusk)?
    dark = n["_t"].get("nautical_dusk", n["_t"].get("civil_dusk"))
    alt_dark = obs.at(dark).observe(moon).apparent().altaz()[0].degrees
    if ill < 0.03: kid = f"{name}: basically invisible. Great dark skies for stars!"
    elif alt_dark > 0 and set_ is not None: kid = f"{name} ({round(ill*100)}% lit): up after dark, sets in the {dir8(obs.at(set_).observe(moon).apparent().altaz()[1].degrees)} at {hm(et(set_))}."
    elif rise is not None and et(rise).hour < 12: kid = f"{name} ({round(ill*100)}% lit): not up in the evening. It rises in the {dir8(obs.at(rise).observe(moon).apparent().altaz()[1].degrees)} at {hm(et(rise))} (early birds only), so evening skies stay dark."
    elif rise is not None: kid = f"{name} ({round(ill*100)}% lit): rises in the {dir8(obs.at(rise).observe(moon).apparent().altaz()[1].degrees)} at {hm(et(rise))}."
    else: kid = f"{name} ({round(ill*100)}% lit)."
    n["moon"] = dict(phase=name, illum_pct=round(ill * 100, 1), phase_angle=round(ang, 1), rise=iso(rise) if rise is not None else None, set=iso(set_) if set_ is not None else None,
                     alt_at_dark=round(alt_dark, 1), kid=kid)

# ---------------------------------------------------------------- planets
PLANETS = [("Mercury", "mercury"), ("Venus", "venus"), ("Mars", "mars"), ("Jupiter", "jupiter barycenter"), ("Saturn", "saturn barycenter"),
           ("Uranus", "uranus barycenter"), ("Neptune", "neptune barycenter")]
NAKED = {"Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
COLORS = {"Mercury": "#c9b79c", "Venus": "#fff4c2", "Mars": "#ff7a4d", "Jupiter": "#ffd9a0", "Saturn": "#f0d27a", "Uranus": "#9fe3e8", "Neptune": "#7d9bff", "Moon": "#f4f1e6"}

def track(body, times):
    a = obs.at(times).observe(body).apparent()
    alt, az, _ = a.altaz()
    return alt.degrees, az.degrees

for n in nights:
    t = n["_t"]; dusk = t.get("civil_dusk"); dawn = t.get("civil_dawn")
    start = et(t["sunset"]) - dt.timedelta(minutes=10); start = start.replace(minute=start.minute - start.minute % 5, second=0, microsecond=0); end = et(t["sunrise"]) + dt.timedelta(minutes=10)
    steps = int((end - start).total_seconds() // 300) + 1
    grid = [start + dt.timedelta(minutes=5 * k) for k in range(steps)]
    tg = ts.from_datetimes(grid)
    n["grid_start"] = start.isoformat(timespec="seconds"); n["grid_step_min"] = 5; n["grid_n"] = steps
    salt, saz = track(sun, tg)
    n["sun_track"] = [[round(float(a), 1), round(float(z), 1)] for a, z in zip(salt, saz)]
    malt, maz = track(moon, tg)
    n["moon_track"] = [[round(float(a), 1), round(float(z), 1)] for a, z in zip(malt, maz)]
    plist = []
    dark_mask = salt < -6
    for name, key in PLANETS:
        body = eph[key]
        alt, az = track(body, tg)
        mag = float(planetary_magnitude(obs.at(tg[len(grid)//3]).observe(body)))
        r, s = rises_sets(body, tg[0], tg[-1])
        up_dark = (alt > 5) & dark_mask
        info = dict(name=name, mag=round(mag, 1), color=COLORS[name], naked_eye=name in NAKED,
                    track=[[round(float(a), 1), round(float(z), 1)] for a, z in zip(alt, az)],
                    rise=iso(r[0]) if r else None, set=iso(s[0]) if s else None, visible=bool(up_dark.any()))
        if up_dark.any():
            idx = np.where(up_dark)[0]
            # split into evening (before 1 AM) and morning windows
            first, last = idx[0], idx[-1]
            best = idx[np.argmax(alt[idx])]
            info.update(first_seen=grid[first].isoformat(timespec="seconds"), last_seen=grid[last].isoformat(timespec="seconds"),
                        best_time=grid[best].isoformat(timespec="seconds"), best_alt=round(float(alt[best]), 1), best_dir=dir8(az[best]))
            # kid sentence
            g0 = grid[first]; a0, z0 = alt[first], az[first]
            parts = []
            if dusk is not None and g0.hour >= 17 and g0 <= et(dusk) + dt.timedelta(minutes=10):
                parts.append(f"{altword(a0)} in the {dir8(z0)} as soon as it gets dark (about {hm_round(g0)})")
            else:
                verb = "climbs into view" if a0 < 12 else "is up"
                parts.append(f"{verb} in the {dir8(z0)} around {hm_round(g0)}")
            if alt[best] > a0 + 5 and best != first:
                parts.append(f"highest ({altword(alt[best])}, in the {dir8(az[best])}) around {hm_round(grid[best])}")
            if s and et(s[0]) < end - dt.timedelta(minutes=15):
                sz = obs.at(s[0]).observe(body).apparent().altaz()[1].degrees
                parts.append(f"sets in the {dir8(sz)} at {hm_round(et(s[0]))}")
            elif last < len(grid) - 1 and grid[last].hour < 9:
                parts.append(f"still up when dawn washes it out (about {hm_round(grid[last])})")
            info["kid"] = f"{name} " + "; ".join(parts) + "."
            if not info["naked_eye"]: info["kid"] += " Too faint for eyes alone; needs binoculars or a telescope and a star map."
        else:
            info["kid"] = f"{name} isn't visible at night right now (it's too close to the Sun in our sky)." if name in NAKED else f"{name} isn't well placed tonight."
        plist.append(info)
    n["planets"] = plist

# ---------------------------------------------------------------- satellites
def load_tle(path):
    L = [l.rstrip() for l in open(path) if l.strip()]
    return [EarthSatellite(L[i + 1], L[i + 2], L[i].strip(), ts) for i in range(0, len(L) - 2, 3)]
stations = load_tle(os.path.join(D, "stations.tle"))
visual = load_tle(os.path.join(D, "visual.tle"))
def epoch_age_days(s, ref): return float(ref - s.epoch)

def sat_pass_detail(sat, rise, culm, set_, std_mag=None, step=5):
    """Sample a pass, keep the part where the satellite is sunlit and the observer's sky is dark (Sun below -6 deg)."""
    n = max(2, int((set_ - rise) * 86400 / step) + 1)
    tg = ts.tt_jd(np.linspace(rise.tt, set_.tt, n))
    topoc = (sat - topo).at(tg); alt, az, dist = topoc.altaz()
    lit = sat.at(tg).is_sunlit(eph)
    salt = obs.at(tg).observe(sun).apparent().altaz()[0].degrees
    vis = lit & (salt < -6) & (alt.degrees > 10)
    out = dict(name=sat.name, rise=iso(rise), culm=iso(culm), set=iso(set_), culm_alt=round(float((sat - topo).at(culm).altaz()[0].degrees), 2))
    if not vis.any(): return None
    idx = np.where(vis)[0]; i0, i1 = idx[0], idx[-1]; ib = idx[np.argmax(alt.degrees[idx])]
    out.update(vis_start=iso(tg[i0]), vis_end=iso(tg[i1]), max_time=iso(tg[ib]), max_alt=round(float(alt.degrees[ib]), 1),
               start_dir=dir8(az.degrees[i0]), end_dir=dir8(az.degrees[i1]), max_dir=dir8(az.degrees[ib]), start_alt=round(float(alt.degrees[i0]), 1),
               end_alt=round(float(alt.degrees[i1]), 1), duration_s=int(round((tg[i1] - tg[i0]) * 86400)),
               start_reason=("shadow" if i0 > 0 and not lit[i0 - 1] else ("twilight" if i0 > 0 and salt[i0 - 1] >= -6 else "horizon")),
               fades_into_shadow=bool(i1 < len(tg) - 1 and not lit[i1 + 1] and alt.degrees[i1] > 10.5),
               path=[[round(float(alt.degrees[k]), 1), round(float(az.degrees[k]), 1), et(tg[k]).isoformat(timespec="seconds")] for k in range(i0, i1 + 1, 2)])
    if std_mag is not None:
        # Standard estimate (as used by many pass predictors): mag = std + 5 log10(range/1000 km) - 2.5 log10(phase fn). An ESTIMATE.
        satv = sat.at(tg[ib]).position.km; sunv = earth.at(tg[ib]).observe(sun).position.km
        obsv = topo.at(tg[ib]).position.km
        to_sun = sunv - satv; to_obs = obsv - satv
        cosb = np.dot(to_sun, to_obs) / np.linalg.norm(to_sun) / np.linalg.norm(to_obs); beta = math.acos(max(-1, min(1, cosb)))
        phase = (math.sin(beta) + (math.pi - beta) * math.cos(beta)) / math.pi
        rng = float(dist.km[ib])
        out["est_mag"] = round(std_mag + 5 * math.log10(rng / 1000) - 2.5 * math.log10(max(phase, 1e-3)), 1)
    return out

def passes_for(sat, t0, t1, min_alt=10, std_mag=None):
    tt_, ev = sat.find_events(topo, t0, t1, altitude_degrees=min_alt)
    res = []; cur = {}
    for t, e in zip(tt_, ev):
        cur[int(e)] = t
        if e == 2 and 0 in cur and 1 in cur:
            d = sat_pass_detail(sat, cur[0], cur[1], cur[2], std_mag)
            if d and d["duration_s"] >= 30: res.append(d)
            cur = {}
    return res

win0 = tt(dt.datetime.combine(base, dt.time(12), ET)); win1 = tt(dt.datetime.combine(base + dt.timedelta(days=NIGHTS), dt.time(12), ET))
station_sats = [s for s in stations if s.name.startswith("ISS (ZARYA)") or s.name.startswith("CSS (TIANHE)")]
station_passes = []
for s in station_sats:
    std = -1.8 if s.name.startswith("ISS") else -0.8  # commonly used standard magnitudes; estimates only
    for p in passes_for(s, win0, win1, std_mag=std):
        p["friendly"] = "International Space Station (ISS)" if s.name.startswith("ISS") else "China's Tiangong space station"
        p["epoch"] = iso(s.epoch); p["epoch_age_days"] = round(epoch_age_days(s, win0), 2)
        station_passes.append(p)
bright_passes = []
station_ids = {s.model.satnum for s in station_sats}
for s in visual:
    if s.model.satnum in station_ids: continue
    if abs(epoch_age_days(s, win0)) > 10: continue
    for p in passes_for(s, win0, win1, min_alt=10):
        if p["max_alt"] >= 60 and p["duration_s"] >= 120:
            p["friendly"] = s.name.title() if "R/B" not in s.name else s.name.replace("R/B", "rocket body").title()
            p["norad"] = s.model.satnum
            bright_passes.append(p)

# ---------------------------------------------------------------- Starlink trains (fresh launches)
last30 = json.load(open(os.path.join(D, "last30.json")))
groups = {}
for o in last30:
    if o["OBJECT_NAME"].startswith("STARLINK"):
        groups.setdefault(o["OBJECT_ID"][:8], []).append(o)
cache_ids = set()
try:
    cache = json.load(open(os.path.join(D, "starlink-omm.json"))); cache_by = {o["NORAD_CAT_ID"]: o for o in cache}
except Exception: cache_by = {}
from sgp4.api import Satrec
def omm_sat(o):
    from skyfield.api import EarthSatellite as ES
    return ES.from_omm(ts, o)
trains = []; train_groups = []
for gid, objs in sorted(groups.items()):
    sats = [omm_sat(o) for o in objs]
    in_cache = sum(1 for o in objs if o["NORAD_CAT_ID"] in cache_by)
    mm = [o["MEAN_MOTION"] for o in objs]
    alt_km = [round((398600.4418 / (2 * math.pi * m / 86400) ** 2) ** (1 / 3) - 6378.137) for m in mm]
    train_groups.append(dict(launch=gid, count=len(objs), in_starlink_cache=in_cache, alt_km_min=min(alt_km), alt_km_max=max(alt_km),
                             epoch_latest=max(o["EPOCH"] for o in objs)))
    for n in nights:
        t = n["_t"]
        for wname, a, b in (("evening", et(t["sunset"]), et(t["sunset"]) + dt.timedelta(hours=3)), ("morning", et(t["sunrise"]) - dt.timedelta(hours=3), et(t["sunrise"]))):
            k = int((b - a).total_seconds() // 10) + 1
            grid = [a + dt.timedelta(seconds=10 * j) for j in range(k)]
            tg = ts.from_datetimes(grid)
            salt = obs.at(tg).observe(sun).apparent().altaz()[0].degrees
            ALT = []; AZ = []; LIT = []
            for s in sats:
                al, az, _ = (s - topo).at(tg).altaz(); ALT.append(al.degrees); AZ.append(az.degrees); LIT.append(s.at(tg).is_sunlit(eph))
            ALT = np.array(ALT); AZ = np.array(AZ); LIT = np.array(LIT)
            vis = (ALT > 15) & LIT & (salt < -6)[None, :]
            cnt = vis.sum(0)
            on = cnt >= 5
            j = 0
            while j < k:
                if on[j]:
                    j0 = j
                    while j < k and on[j]: j += 1
                    j1 = j - 1
                    if (j1 - j0) * 10 >= 30:
                        sl = slice(j0, j1 + 1)
                        peak = j0 + int(np.argmax(cnt[sl]))
                        mx = ALT[:, peak][vis[:, peak]].max()
                        first_i = np.where(vis[:, j0])[0]; last_i = np.where(vis[:, j1])[0]
                        frames = []
                        for jj in range(j0, j1 + 1, 3):
                            frames.append(dict(t=grid[jj].isoformat(timespec="seconds"), dots=[[round(float(ALT[q, jj]), 1), round(float(AZ[q, jj]), 1)] for q in np.where(vis[:, jj])[0]]))
                        trains.append(dict(night=n["date"], window=wname, launch=gid, start=grid[j0].isoformat(timespec="seconds"), end=grid[j1].isoformat(timespec="seconds"),
                                           peak_time=grid[peak].isoformat(timespec="seconds"), peak_count=int(cnt[peak]), group_size=len(objs), max_alt=round(float(mx), 1),
                                           start_dir=dir8(float(np.median(AZ[first_i, j0]))), end_dir=dir8(float(np.median(AZ[last_i, j1]))),
                                           peak_dir=dir8(float(np.median(AZ[vis[:, peak], peak]))), frames=frames))
                else: j += 1

# ---------------------------------------------------------------- weather (NWS)
weather = {}
try:
    grid = json.load(open(os.path.join(D, "grid.json")))["properties"]; fc = json.load(open(os.path.join(D, "forecast.json")))["properties"]
    import re
    def parse_vt(v):
        a, d = v.split("/"); start = dt.datetime.fromisoformat(a)
        m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?", d); hours = int(m.group(1) or 0) * 24 + int(m.group(2) or 0)
        return start, max(1, hours)
    hourly = {}
    for v in grid["skyCover"]["values"]:
        s, h = parse_vt(v["validTime"])
        for k in range(h): hourly[(s + dt.timedelta(hours=k)).astimezone(ET).replace(minute=0, second=0)] = v["value"]
    for n in nights:
        day = dt.date.fromisoformat(n["date"])
        ev = [hourly.get(dt.datetime(day.year, day.month, day.day, h, tzinfo=ET)) for h in range(19, 24)]
        ev = [x for x in ev if x is not None]
        per = next((p for p in fc["periods"] if not p["isDaytime"] and p["startTime"][:10] == n["date"]), None)
        weather[n["date"]] = dict(evening_sky_cover_pct=round(sum(ev) / len(ev)) if ev else None,
                                  hourly=[[h, hourly.get(dt.datetime(day.year, day.month, day.day, h, tzinfo=ET))] for h in range(18, 24)],
                                  period=per["name"] if per else None, short=per["shortForecast"] if per else None, detailed=per["detailedForecast"] if per else None)
    weather["_updated"] = grid.get("updateTime")
except Exception as e:
    weather["_error"] = str(e)

# ---------------------------------------------------------------- stars for the dome (ephem built-in catalog, J2000)
starlist = []
for name in sorted(set(ephem_stars.stars)):
    if name in ("Formalhaut", "Albereo", "Alcaid", "Etamin"): continue  # duplicate spellings in ephem's list
    s = ephem.star(name); s.compute("2000/1/1", epoch="2000")
    if s.mag <= 3.2: starlist.append([name, round(math.degrees(s.a_ra), 4), round(math.degrees(s.a_dec), 4), round(s.mag, 2)])

# ---------------------------------------------------------------- best moments
def d_(s): return dt.datetime.fromisoformat(s)
for n in nights:
    m = []
    dusk = et(n["_t"]["civil_dusk"]); naut = et(n["_t"]["nautical_dusk"])
    for p in station_passes:
        st = d_(p["vis_start"])
        if not (et(n["_t"]["sunset"]) <= st <= et(n["_t"]["sunrise"])): continue
        iss = p["name"].startswith("ISS")
        score = (75 if iss else 65) + 0.5 * p["max_alt"] - 10 * p.get("est_mag", 0) - (20 if st.hour < 12 else 0)
        bright = f" Estimated brightness: magnitude {p['est_mag']} (" + ("brighter than any star" if p.get("est_mag", 9) < -1.4 else "like a bright star" if p.get("est_mag", 9) < 1.0 else "fairly faint, since it stays low and far away") + ")." if "est_mag" in p else ""
        fade = " It fades out partway across as it enters Earth's shadow." if p["fades_into_shadow"] else ""
        m.append(dict(time=p["vis_start"], kind="iss" if iss else "station", score=round(score),
                      title=("ISS flyover" if iss else "Tiangong space station flyover") + f" ({p['duration_s']//60} min {p['duration_s']%60:02d} s)",
                      kid=(f"Look {p['start_dir']}{' low' if p['start_alt'] < 20 else ''} at {hm(d_(p['vis_start']))}." if p['start_reason'] != 'shadow' else f"At {hm(d_(p['vis_start']))} it pops out of Earth's shadow {altword(p['start_alt'])} in the {p['start_dir']}.") + f" A steady, non-blinking light glides across, highest ({altword(p['max_alt'])}, in the {p['max_dir']}) around {hm(d_(p['max_time']))}, then heads {p['end_dir']}.{fade}{bright}",
                      ref=p["max_time"]))
    for tr in trains:
        if tr["night"] != n["date"]: continue
        m.append(dict(time=tr["start"], kind="starlink", score=round(70 + tr["peak_count"]), title=f"Starlink train ({tr['launch']} batch, up to {tr['peak_count']} satellites at once)",
                      kid=f"Look {tr['start_dir']} at {hm(d_(tr['start']))}: a line of faint moving dots, one after another, heading {tr['end_dir']} until about {hm(d_(tr['end']))}. Highest about {round(tr['max_alt'])}° up. Fresh Starlinks fade as they climb, so it may be dim.",
                      ref=tr["peak_time"]))
    for pl in n["planets"]:
        if not pl.get("visible") or not pl["naked_eye"]: continue
        # best evening moment: highest point before 11 PM after full dark, otherwise first seen
        tr_ = pl["track"]; g0 = d_(n["grid_start"])
        cands = [(k, tr_[k][0]) for k in range(len(tr_)) if g0 + dt.timedelta(minutes=5 * k) >= naut and (g0 + dt.timedelta(minutes=5 * k)).hour in (19, 20, 21) and tr_[k][0] > 8]
        if cands:
            k, a = max(cands, key=lambda x: x[1]); when = g0 + dt.timedelta(minutes=5 * k); early = False
        else:
            cands = [(k, tr_[k][0]) for k in range(len(tr_)) if n["sun_track"][k][0] < -8 and tr_[k][0] > 8 and (g0 + dt.timedelta(minutes=5 * k)).hour < 8]
            if not cands: continue
            k, a = max(cands, key=lambda x: x[1]); when = g0 + dt.timedelta(minutes=5 * k); early = True
        z = tr_[k][1]
        score = 62 - 9 * pl["mag"] - (25 if early else 0)
        m.append(dict(time=when.isoformat(timespec="seconds"), kind="planet", score=round(score), title=f"{pl['name']} {'(early bird)' if early else ''}".strip(),
                      kid=f"{pl['name']} is {altword(a)} in the {dir16(z)} (about {fists(a)} fists above the horizon at arm's length). " +
                          ("It's the brightest 'star' over there and doesn't twinkle much." if pl['mag'] < 0 else "It looks like a steady star."),
                      ref=when.isoformat(timespec="seconds")))
    mo = n["moon"]
    if mo["illum_pct"] < 25 and mo["alt_at_dark"] < 0:
        m.append(dict(time=naut.isoformat(timespec="seconds"), kind="dark", score=40, title="Moonless dark sky",
                      kid=f"No Moon in the evening sky ({mo['phase']}), so it's a good night to spot fainter stars once your eyes adjust for 15 minutes. Full darkness starts {hm(et(n['_t']['astro_dusk']))}.",
                      ref=naut.isoformat(timespec="seconds")))
    if mo["rise"] and d_(mo["rise"]).hour < 7 and mo["illum_pct"] < 30:
        m.append(dict(time=mo["rise"], kind="moon", score=25, title=f"Thin crescent Moon rises (early bird, {round(mo['illum_pct'])}% lit)",
                      kid=f"Before sunrise, a thin crescent Moon comes up in the east at {hm(d_(mo['rise']))}.", ref=mo["rise"]))
    tonight_bright = [p for p in bright_passes if et(n["_t"]["sunset"]) <= d_(p["vis_start"]) <= et(n["_t"]["sunrise"])]
    tonight_bright.sort(key=lambda p: (d_(p["vis_start"]).hour < 12, -p["max_alt"]))
    for p in tonight_bright[:3]:
        st = d_(p["vis_start"])
        m.append(dict(time=p["vis_start"], kind="satellite", score=round(20 + p["max_alt"] / 4 - (15 if st.hour < 12 else 0)), title=f"Satellite: {p['friendly']}",
                      kid=(f"From the {p['start_dir']} at {hm(st)}" if p['start_reason'] != 'shadow' else f"Pops out of Earth's shadow {altword(p['start_alt'])} in the {p['start_dir']} at {hm(st)}") + ("" if (d_(p['max_time']) - st).total_seconds() < 45 else f", {altword(p['max_alt'])} in the {p['max_dir']} at {hm(d_(p['max_time']))}") + f", then heads toward the {p['end_dir']}. Brightness unknown; look for a slow-moving star.",
                      ref=p["max_time"]))
    for x in m:
        h = d_(x["time"])
        x["kid_hours"] = bool(h.hour >= 18 and (h.hour < 22 or (h.hour == 22 and h.minute <= 30)))
        if x["kid_hours"]: x["score"] += 15
    m.sort(key=lambda x: -x["score"])
    n["moments"] = m

for n in nights: n.pop("_t")
out = dict(generated_at=NOW.isoformat(timespec="seconds"), location=man["location"], nights=nights, station_passes=station_passes,
           bright_passes=bright_passes, starlink_trains=trains, starlink_groups=train_groups, next_moon_phases=next_phases,
           weather=weather, stars=starlist,
           asterisms=[["Dubhe", "Merak", "Phecda", "Megrez", "Alioth", "Mizar", "Alkaid"], ["Megrez", "Dubhe"],
                      ["Schedar", "Caph"], ["Vega", "Deneb", "Altair", "Vega"], ["Betelgeuse", "Bellatrix", "Mintaka", "Alnilam", "Alnitak", "Saiph", "Rigel", "Mintaka"],
                      ["Alpheratz", "Scheat", "Markab", "Algenib", "Alpheratz"]],
           sources={k: dict(fetched_at=v.get("fetched_at"), url=v.get("url"), status=v.get("status")) for k, v in man["sources"].items()})
json.dump(out, open(os.path.join(D, "sky.json"), "w"), separators=(",", ":"))
for n in nights:
    for pl in n["planets"]: print("  ", n["date"], pl["kid"])
    print("  ", n["moon"]["kid"])
print("nights", len(nights), "station passes", len(station_passes), "bright", len(bright_passes), "trains", len(trains), "stars", len(starlist))
for n in nights:
    print(n["label"], n["sunset"][11:16], "dusk", n["civil_dusk"][11:16], n["moon"]["phase"], n["moon"]["illum_pct"])
    for x in n["moments"][:6]: print("   ", x["score"], x["time"][5:16], x["title"], "|", x["kid"][:140])
