#!/usr/bin/env python3
"""Is blustone.miraheze.org actually the vsfan game wiki? Verify, do not assume.

The walk returned exactly 335 ns-0 pages and 485 revids - the values GUARD
rule 9 documents as the INCOMPLETE count, and far below the 1254/1568 the
project previously measured for the vsfan wiki. Either the walk is still
truncating, or this is a different wiki. Test both.

Control: fetch Main Page wikitext and look for the game wiki's own vocabulary
("Blustone", "hunter", "Expedition", "visualshower"). A fan-fiction wiki will
not carry those.
"""
import json
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

S = requests.Session()
S.headers.update({"User-Agent": "blustone login-bonus research (read-only)"})
API = "https://blustone.miraheze.org/w/api.php"

GAME_VOCAB = ["Blustone", "visualshower", "Expedition", "hunter", "hunter", "Metron",
              "Fight Club", "Manda", "Rupee", "attendance", "login bonus"]


def api(**params):
    params.setdefault("format", "json")
    params.setdefault("action", "query")
    for i in range(4):
        try:
            return S.get(API, params=params, timeout=60).json()
        except Exception:
            if i == 3:
                raise
            time.sleep(1.5 * (i + 1))


# 1. is the walk still truncating?  Use a DIFFERENT enumeration: recentchanges
rc = api(list="recentchanges", rclimit="max", rcprop="title|timestamp")
titles = [c["title"] for c in rc.get("query", {}).get("recentchanges", [])]
print("recentchanges sample (%d):" % len(titles), titles[:8])

j = api(list="allpages", apnamespace=0, aplimit="max")
print("allpages first batch:", len(j["query"]["allpages"]))
print("   has 'continue'?", "continue" in j)

# 2. Main Page content test
j = api(prop="revisions", titles="Main Page", rvprop="content", rvslots="main")
pg = list(j["query"]["pages"].values())[0]
txt = pg["revisions"][0]["slots"]["main"]["*"]
print("\n--- Main Page wikitext (first 1200 chars) ---")
print(txt[:1200])
print("\n--- game vocabulary hits ---")
for v in GAME_VOCAB:
    print("   %-14s %s" % (v, v.lower() in txt.lower()))

# 3. namespace census
print("\n--- namespace census ---")
for ns in range(0, 16):
    j = api(list="allpages", apnamespace=ns, aplimit="max")
    n = len(j.get("query", {}).get("allpages", []))
    if n:
        print("   ns=%-3d %d" % (ns, n))

j = api(meta="siteinfo")
si = j["query"]["general"] if "query" in j else {}
print("\nsitename:", si.get("sitename"), "| base:", si.get("base"))