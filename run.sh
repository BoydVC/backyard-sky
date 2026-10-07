#!/usr/bin/env bash
# Backyard Sky Tonight: refresh public data (keeps the cache if offline), recompute, build, serve on :4268.
#   nohup ./run.sh &            refresh + compute + build + serve (stays in the foreground under nohup)
#   ./run.sh --offline          skip fetching, recompute from cached data
cd "$(dirname "$0")"
[[ -x .venv/bin/python ]] || { python3 -m venv .venv && .venv/bin/pip install -q skyfield ephem numpy; }
if [[ "${1:-}" != "--offline" ]]; then .venv/bin/python fetch.py || echo "(fetch failed; using cached data)"; fi
.venv/bin/python compute.py > data/compute.log 2>&1 || { echo "compute failed, see data/compute.log"; exit 1; }
.venv/bin/python build.py
if [[ -f data/server.pid ]] && kill -0 "$(cat data/server.pid)" 2>/dev/null; then echo "already serving http://127.0.0.1:4268/"; exit 0; fi
echo $$ > data/server.pid
echo "serving http://127.0.0.1:4268/"
exec python3 server.py
