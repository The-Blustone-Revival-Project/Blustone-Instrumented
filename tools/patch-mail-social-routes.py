"""Implement the mail and social routes from the recovered native contract.

Evidence: analysis/research/mail-social.md, every key offset taken from
`analysis/native-all-strings.tsv` and every callback signature from
`analysis/native-evidence.tsv`.

One live bug is fixed here. `CPVRelation::ReqBlockListCB` has the mangled
signature

    ... function<void(int, map<unsigned long, basic_string>&)>, int, ...

so `/relation/BlockList` is a MAP keyed by pvid, not an array. The replica
returned `[]`, which cannot satisfy a `map` sink. It is now `{}`.

`/message/GetUnreadCount` is on the village boot path every session and had no
handler at all, so it fell through to the generic mock and the client got a
metadata object where it expects the unread count. `unread_count` sits at
0x1d6a8f2, immediately beside the `GetUnreadCount` path literal.

`/relation/GetList` is called twice per session, with `type` 1 then 3, and
`CPVRelation::ReqFriendListCB` takes `list<PV_FRIEND_INFO>&` for one
`PV_FRIEND_INFO::TYPE` per call. So the response is a list, and the buckets are
selected by the request's `type` rather than all being present at once.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "src" / "game-routes.ts"

OLD = '''  if (route === "/relation/GetSuggestedFriendList") return state.envelope([]);'''
NEW = '''  // --- mail and social, implemented from analysis/research/mail-social.md ---

  if (route === "/message/GetUnreadCount") {
    // `unread_count` at 0x1d6a8f2, beside the GetUnreadCount path literal.
    // This route is on the village boot path every session and previously had no
    // handler, so the client received the generic mock metadata object.
    return state.envelope({ unread_count: 0 });
  }

  if (route === "/message/GetReceivedList" || route === "/message/GetSentList") {
    // `list` at 0x1d6a8ff is the array wrapper these two share via
    // ProcessCommonGetListComplete.
    return state.envelope({ list: [] });
  }

  if (route === "/relation/GetList") {
    // CPVRelation::ReqFriendListCB takes list<PV_FRIEND_INFO>& for ONE
    // PV_FRIEND_INFO::TYPE per call; the client asks for type 1 and then type 3.
    // An empty list is a valid answer for both buckets.
    return state.envelope([]);
  }

  if (route === "/relation/GetSuggestedFriendList") return state.envelope([]);'''

OLD_BLOCK = '''  if (route === "/relation/BlockList") return state.envelope([]);'''
NEW_BLOCK = '''  if (route === "/relation/BlockList") {
    // A MAP keyed by pvid, not an array. CPVRelation::ReqBlockListCB's recovered
    // signature is function<void(int, map<unsigned long, basic_string>&)>; the
    // previous `[]` could not satisfy that sink. This also supersedes the
    // workspace note listing BlockList as an array-indexing parser.
    return state.envelope({});
  }'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "unread_count" in src:
        print("mail/social routes already implemented")
        return 0
    for old, new in ((OLD, NEW), (OLD_BLOCK, NEW_BLOCK)):
        if src.count(old) != 1:
            raise SystemExit(f"anchor found {src.count(old)} times: {old[:50]!r}")
        src = src.replace(old, new)
    TARGET.write_text(src, encoding="utf-8")
    print("mail/social routes implemented; BlockList corrected to a map")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
