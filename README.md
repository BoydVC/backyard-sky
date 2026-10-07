# Backyard Sky Tonight

A dark-mode sky guide for Boyd, Char (13) and Vic (11): what's up tonight and the next three nights from the backyard in
**Millersville, MD**. The page uses a town-center point (39.06° N, 76.65° W, about 30 m elevation), not the street address. All times are Eastern.

* **Live:** `nohup ./run.sh &` → http://127.0.0.1:4268/ (refetches data, recomputes, rebuilds, then serves)
* **Offline:** `dist/backyard-sky-snapshot.html` is a single file with everything inlined (no internet needed)
* **Best screenshot:** `screenshots/00-best-desktop-tonight-9pm.png` (phone: `03-phone-top.png`, `04-phone-sky-dome.png`)
* **Test:** `.venv/bin/python tests/smoke.py` (results in `tests/last-run.txt`)
* **Refresh without network:** `./run.sh --offline`

## What's on the page
* **Go outside at…**: a ranked list of moments for each night. Space-station flyovers are scored by peak height and estimated brightness. Planets are scored by brightness, and Moon and dark-sky notes are included. Moments between 6 and 10:30 PM get a kid-hours bonus, and pre-dawn ones are tagged *early bird*. A moment that has already happened is greyed out. Tap any moment to see it on the dome.
* **Sky dome**: an all-sky map (north at top, east on the left, as when you lie on your back with your head to the north). It shows bright stars and a few star patterns (the Big Dipper, Cassiopeia, the Summer Triangle, Orion and the Great Square), plus planets, the Moon with its phase, twilight glow, and space-station or satellite paths with a moving dot. Use the slider or ▶ Play to move from sunset to sunrise. The Now, Dark, 9 PM, 10 PM and Pre-dawn buttons jump to those times.
* **Sunset & darkness**: sunset, the end of civil, nautical and astronomical twilight, dawn, and sunrise.
* **Moon**: phase, percent lit, rise and set, and the next main phases.
* **Planets**: Mercury through Neptune, described in kid-friendly words (direction, height in "fists", and rise and set times). Uranus and Neptune are marked as telescope-only.
* **Space stations**: visible ISS and Tiangong passes for 4 nights. **Starlink trains**: passes of recently launched batches. **Bright satellites**: high passes from CelesTrak's brightest-satellites list.
* **Clouds**: National Weather Service evening cloud cover (hourly bars) and the night's forecast text.

## Sources (all cached in `data/`, fetch times in `data/manifest.json`)
| Data | Source | Notes / limits |
|---|---|---|
| Sun, Moon, planets | **skyfield 1.55** with **JPL DE421** ephemeris (`data/de421.bsp`) | Accurate to well under a second of time for rise and set. Rise and set use the standard −0.8333° horizon (refraction plus the Sun's or Moon's radius). Your actual horizon (trees, houses) will differ. |
| Space stations | **CelesTrak** `GROUP=stations` TLEs, propagated with SGP4 (skyfield) | A pass counts as visible when the station is sunlit, is more than 10° up, and the Sun is more than 6° below the horizon. Elements age: re-run daily, and ISS times can shift after a re-boost. Brightness is an **estimate** from a standard formula (−1.8 for ISS and −0.8 for Tiangong at 1000 km, plus a phase factor). |
| Bright satellites | **CelesTrak** `GROUP=visual` | Only passes reaching 60° or more for at least 2 minutes are listed, with up to 3 in the "go outside" list per night. No brightness estimate (it varies a lot, especially for tumbling rocket bodies). |
| Starlink trains | **CelesTrak** `GROUP=last-30-days` (Starlink objects), cross-checked with the full Starlink set cached by `../starlink-globe` (fetched 6:28 PM ET) | A train means 5 or more satellites from one fresh launch that are sunlit, above 15°, and in a dark sky at the same moment. As of this run, **no train is visible from Millersville in the next 4 nights**. Both fresh batches (2026-219 at about 340–366 km and 2026-225 at about 296–316 km) pass over in Earth's shadow. Batch 2026-225 wasn't in the earlier Starlink cache yet, so the last-30-days file is the one used. Real trains can still be dimmer than predicted. |
| Bright stars | PyEphem's built-in catalog (stars of magnitude 3.2 or brighter) | The dome computes star positions in JavaScript from J2000 coordinates (precession of about 0.4° is ignored). Good enough to find things by eye. |
| Clouds | **api.weather.gov** (NWS LWX grid 109,80): `skyCover` grid and the 7-day forecast | This is a forecast, not an observation, and it only covers what NWS publishes. The page doesn't cover haze, light pollution or the actual horizon. |
| Cross-check only | **US Naval Observatory** API `rstt/oneday` (today) | Used by the smoke test as an independent source for sunset, civil twilight and Moon phase. |

Plain HTTP is used for CelesTrak because HTTPS to celestrak.org fails the TLS handshake from this box. The `starlink-globe` project ran into the same issue.

## Smoke test (`tests/smoke.py`)
* **Sunset and civil dusk** for all 4 nights: skyfield vs **PyEphem** (an independent algorithm), with a 60 s tolerance. Today's sunset and civil dusk are also checked against the **USNO API** (90 s tolerance, since USNO rounds to the minute).
* **Moonrise and moonset** vs PyEphem, plus the Moon phase name vs USNO.
* **Saturn, Jupiter and Mars** altitude and azimuth at 9 PM vs PyEphem.
* **Every ISS and Tiangong pass**: rise, peak and set times and peak altitude are recomputed with **PyEphem's own SGP4 propagator**. Rise and set are found by bisection at 10°. Tolerance is 15 s, and peak altitude must match within 0.5°.
* **Page checks**: both the served page (:4268) and the offline snapshot load in headless Chrome. The test clicks every night tab, jump button and moment, plays the dome, and **fails on any JavaScript error or failed resource**. It also checks that the dome's star math (Vega) matches PyEphem.
* **Data checks**: every source in the manifest has a fetch time, there are no NaNs, and the snapshot is self-contained.

## Files
`fetch.py` (downloads and writes the manifest) → `compute.py` (writes `data/sky.json`) → `build.py` (inlines the data into `web/template.html`, producing `web/index.html` and `dist/backyard-sky-snapshot.html`) → `server.py` (:4268). `tests/cdp.mjs` is a tiny headless-Chrome driver copied from `starlink-globe`. `tests/shots.mjs` takes the screenshots.


---
## Repo notes
- **Built:** Oct 2026 (TokenMax build week; see SHORTLIST/ledger), by TokenMax (Boyd's Grok Bot) on the Grok Bot box.
- **Run:** `./run.sh` (then open the localhost URL it prints).
- Imported from `/workspace/tokenmax/backyard-sky` on Oct 23, 2026. node_modules, virtualenvs, logs and files over 20 MB were left out.
- Personal details (emails, phone numbers, home street address) were replaced with `[redacted-…]` placeholders.
