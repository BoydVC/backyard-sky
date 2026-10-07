#!/usr/bin/env python3
"""Inline data/sky.json into web/template.html -> web/index.html (served) and dist/backyard-sky-snapshot.html (offline, single file)."""
import os, json
H = os.path.dirname(os.path.abspath(__file__))
sky = open(os.path.join(H, "data/sky.json")).read()
json.loads(sky)
html = open(os.path.join(H, "web/template.html")).read().replace("/*__SKY__*/", sky.replace("</", "<\\/"))
os.makedirs(os.path.join(H, "dist"), exist_ok=True)
for p in ("web/index.html", "dist/backyard-sky-snapshot.html"):
    open(os.path.join(H, p), "w").write(html)
print("built", len(html) // 1024, "KB")
