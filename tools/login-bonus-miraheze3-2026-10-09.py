#!/usr/bin/env python3
"""1) Content-scan all 335 ns-0 pages of blustone.miraheze.org for attendance.
   2) Locate the REAL vsfan wiki (static.miraheze.org/vsfanwiki).

Control for (1): the page count must equal 335 and at least one page must
contain the game's own vocabulary ('Metron' or 'hunter'). If neither holds the
scan is meaningless.
"""
import json
import re
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

S = requests.Session()
S.headers.update({"User-Agent": "blustone login-bonus research (read-only)"})
API = "https://blustone.miraheze.org/w/api.php"

KEY = re.compile(r"attend|login|sign.?in|daily|cumulative|supply|veteran", re.I)
GAMEPROOF = re.compile(r"Metron|hunter|Expedition|Manda", re.I)


def api(**p):
    p.setdefault("format", "json")
    p.setdefault("action", "query")
    for i in range(4):
        try:
            return S.get(API, params=p, timeout=60).json()
        except Exception:
            if i == 3:
                raise
            time.sleep(1.2 * (i + 1))


titles = [x["title"] for x in api(list="allpages", apnamespace=0, aplimit="max")["query"]["allpages"]]
print("ns-0 pages:", len(titles))

texts = {}
for k in range(0, len(titles), 50):
    batch = titles[k:k + 50]
    j = api(prop="revisions", titles="|".join(batch), rvprop="content", rvslots="main")
    for pg in j["query"]["pages"].values():
        try:
            texts[pg["title"]] = pg["revisions"][0]["slots"]["main"]["*"]
        except Exception:
            texts[pg["title"]] = ""
print("fetched contents:", len(texts), "| non-empty:", sum(1 for v in texts.values() if v.strip()))

proof = [t for t, v in texts.items() if GAMEPROOF.search(v or "")]
print("CONTROL: pages containing game vocabulary: %d  -> %s"
      % (len(proof), "PASS" if proof else "FAIL"))
if not proof:
    sys.exit(2)

hits = []
for t, v in texts.items():
    if not v:
        continue
    for m in KEY.finditer(v):
        a = max(0, m.start() - 220)
        hits.append((t, re.sub(r"\s+", " ", v[a:m.end() + 260])))
        break

print("\nattendance/login/supply/veteran pages: %d" % len(hits))
for t, frag in sorted(hits):
    print("\n### %s\n    ...%s..." % (t, frag))

# --- locate the real vsfan wiki ---
print("\n\n--- vsfan wiki host probes ---")
for u in ["https://vsfanwiki.miraheze.org/w/api.php?action=query&meta=siteinfo&format=json",
          "https://vsfan.miraheze.org/w/api.php?action=query&meta=siteinfo&format=json"]:
    try:
        r = S.get(u, timeout=40)
        print("%-70s code=%s %s" % (u[:70], r.status_code, r.text[:160].replace("\n", " ")))
    except Exception as e:
        print("%-70s EXC %s" % (u[:70], str(e)[:60]))