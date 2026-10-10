#!/usr/bin/env python3
"""Walk blustone.miraheze.org for attendance/login-bonus pages.

GUARD rule 8: CirrusSearch on this wiki is UNINDEXED. A search returning 0 is
meaningless, so enumerate via list=allpages WITH apnamespace (rule 9) and
list=allrevisions.

Control: revid count must exceed 1567; page count must exceed 335.
"""
import json
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

S = requests.Session()
S.headers.update({"User-Agent": "blustone login-bonus research (read-only)"})
API = "https://blustone.miraheze.org/w/api.php"

WANT = re.compile(r"suppl|attend|login|sign|daily|veteran|reward|item", re.I) if False else None

import re
WANT = re.compile(r"suppl|attend|login|sign|daily|veteran|reward|item", re.I)


def api(**params):
    params.setdefault("format", "json")
    params.setdefault("action", "query")
    for attempt in range(4):
        try:
            r = S.get(API, params=params, timeout=60)
            return r.json()
        except Exception as e:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


# ---- control ----
j = api(list="allpages", apnamespace=0, aplimit=5)
if "error" in j:
    print("ABORT api error:", j)
    sys.exit(2)
print("CONTROL allpages ns0 sample:", [p["title"] for p in j["query"]["allpages"]])

pages, cont = [], None
while True:
    p = {"list": "allpages", "apnamespace": 0, "aplimit": "max"}
    if cont:
        p["apcontinue"] = cont
    j = api(**p)
    if "error" in j:
        print("ABORT during walk:", j["error"])
        break
    pages += [x["title"] for x in j["query"]["allpages"]]
    cont = j.get("continue", {}).get("apcontinue")
    if not cont:
        break
print("\nnamespace-0 pages:", len(pages), "(must be > 335 for the control to mean anything)")

# all revisions, to satisfy rule 9's stronger control
revs, cont = 0, None
while True:
    p = {"list": "allrevisions", "arvlimit": "max"}
    if cont:
        p["arcontinue"] = cont
    j = api(**p)
    if "error" in j:
        break
    revs += len(j["query"]["allrevisions"])
    cont = j.get("continue", {}).get("arcontinue")
    if not cont:
        break
print("allrevisions walked:", revs, "(must exceed 1567)")

hits = [t for t in pages if WANT.search(t)]
print("\nattendance/login/reward-ish page titles (%d):" % len(hits))
for t in sorted(hits):
    print("   ", t)

json.dump({"pages": pages, "revs": revs, "hits": hits},
          open(r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets"
               r"\login-bonus-2026-10-09\miraheze-pages.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)