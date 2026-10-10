#!/usr/bin/env python3
"""Find where the vsfan wiki lives now.

The archived page's images are served from static.miraheze.org/vsfanwiki, so the
wiki migrated to Miraheze under some other title. Extract every miraheze/vsfan
URL the archive knows about, then probe those hosts.

GUARD: positive control = the archived page must still contain the day-1 cell.
"""
import re
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (blustone login-bonus research; read-only)"})

LOCAL = (r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets"
         r"\login-bonus-2026-10-09\Hunter_Supply_Office__20200808181724.html")

t = open(LOCAL, "rb").read().decode("utf-8", "replace")
print("control marker x3000 present:", "\u00d73000" in t, "| Daily Rewards:", "Daily Rewards" in t)

hosts = set()
for m in re.finditer(r"https?://([A-Za-z0-9.\-]+)", t):
    hosts.add(m.group(1))
print("\nhosts referenced by the 2020-08-08 capture:")
for h in sorted(hosts):
    print("   ", h)

# look for a "moved to" / interwiki hint
for kw in ("moved", "redirect", "Miraheze", "miraheze"):
    for m in re.finditer(kw, t):
        a = max(0, m.start() - 200)
        frag = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t[a:m.end() + 200]))
        print("\n[%s] ...%s..." % (kw, frag))
        break

print("\n--- probing candidate Miraheze wiki hosts ---")
CANDS = [
    "https://vsfan.miraheze.org/wiki/Hunter_Supply_Office",
    "https://vsfanwiki.miraheze.org/wiki/Hunter_Supply_Office",
    "https://blustone.miraheze.org/wiki/Main_Page",
    "https://miraheze.org/wiki/Special:Search?search=blustone",
]
for u in CANDS:
    try:
        r = S.get(u, timeout=40)
        print("%-62s code=%s bytes=%d" % (u, r.status_code, len(r.content)))
    except Exception as e:
        print("%-62s EXC %s" % (u, str(e)[:60]))