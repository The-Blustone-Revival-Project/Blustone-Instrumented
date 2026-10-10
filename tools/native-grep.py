"""Fast, bounded search over the native evidence tables.

    python tools/native-grep.py --table both -p Gacha -p Draw -p Recruit --max 200

Why this exists
---------------
`analysis/native-all-strings.tsv` is 12 MB and `analysis/native-evidence.tsv`
is 7.6 MB - roughly 400k lines. Running PowerShell `Select-String` once per
search term is slow enough that a research agent can burn its whole budget on
the scanning and never reach the analysis. This does ONE streaming pass per
table with every pattern compiled up front, so twenty questions cost one read.

It is deliberately bounded: `--max` caps what is printed, and output is grouped
by pattern so a caller can see at a glance which terms had no hits - an honest
negative, which is worth as much as a hit.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = {
    "strings": ROOT / "local" / "legacy-analysis" / "native-all-strings.tsv",
    "symbols": ROOT / "local" / "legacy-analysis" / "native-evidence.tsv",
    "logs": ROOT / "local" / "legacy-analysis",
}


def patterns_for(raw: list[str], use_regex: bool) -> dict[str, re.Pattern[str]]:
    out: dict[str, re.Pattern[str]] = {}
    for item in raw:
        if use_regex:
            out[item] = re.compile(item, re.IGNORECASE)
        else:
            out[item] = re.compile(re.escape(item), re.IGNORECASE)
    return out


def search_file(path: Path, pats: dict[str, re.Pattern[str]], limit: int,
                only: str) -> None:
    if not path.exists():
        print(f"[missing] {path}")
        return
    hits: dict[str, list[str]] = {name: [] for name in pats}
    truncated: set[str] = set()
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            for name, pat in pats.items():
                if len(hits[name]) >= limit:
                    truncated.add(name)
                    continue
                if pat.search(line):
                    hits[name].append(line.rstrip("\n"))
    print(f"===== {path.name} ({only}) =====")
    for name, rows in hits.items():
        if not rows:
            print(f"  [no hits] {name!r}")
            continue
        for row in rows:
            if len(row) > 300:
                row = row[:300] + "..."
            print(f"  {name:>24s} | {row}")
        if name in truncated:
            print(f"  ... {name!r} truncated at {limit} matches")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-p", "--pattern", action="append", required=True,
                    help="term to search for; repeat for several (one pass)")
    ap.add_argument("-t", "--table", default="both", choices=["strings", "symbols", "both"])
    ap.add_argument("-m", "--max", type=int, default=60, help="max matches per pattern per table")
    ap.add_argument("-r", "--regex", action="store_true", help="treat patterns as regular expressions")
    args = ap.parse_args()

    pats = patterns_for(args.pattern, args.regex)
    if args.table in ("strings", "both"):
        search_file(TABLES["strings"], pats, args.max, "strings")
    if args.table in ("symbols", "both"):
        search_file(TABLES["symbols"], pats, args.max, "symbols")
    return 0


if __name__ == "__main__":
    sys.exit(main())
