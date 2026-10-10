"""Implement /relation/GetTargetUserInfo: the user profile that carries the party.

ROOT CAUSE of the five SetRefID assertions, the GetMonsterData miss, and the
abort. Found by reading `CSRSyncGlobal::ParseUserDatailInfo` (0xf6e240) in
libnative_core.so.

That function reads the profile response and, among others:

    ret_data
    pvid  group_exp  vip_exp  league_level  rating_point  awake
    inst_id_leader  ref_id_leader  rank_leader  rank_up_cnt_leader
    awk_step_leader  overcome_cnt_leader  awk_overcome_leader  exp_leader
    skin_ref_id_leader  skill_1_level_leader .. skill_5_level_leader
    inst_id_  ref_id_  rank_  rank_up_cnt_  awk_step_  overcome_cnt_
    awk_overcome_  exp_  skin_ref_id_  skill_1_level_ .. skill_5_level_
    stage_id  prev_rank  win_message

and it feeds `ref_id_` directly into `CSRCard::SetRefID`:

    basic_json::operator[]<char const>(this, pcVar18);
    from_json<...>(pbVar6, &local_a8);
    CSRCard::SetRefID(pCVar22, &local_a8);

`/relation/GetTargetUserInfo` was being served by the generic mock fallback, which
returns `{mock:true, route, request_keys, list:[], users:[]}` and has no card data
whatsoever. So `ref_id_` resolved to an empty string, which is why:

  - `CSRCard::SetRefID` asserted `sRefID.length() > 0` (SRCard.cpp:731) once per
    party member - five times;
  - the actor's ref id stayed empty, so the monster ids the client derived were
    `list=["","","","",""]`;
  - `CSRGameMob::GetMonsterData` missed (SRGameMob.cpp:38);
  - `MakeBackEndActor` then copied an invalid `INFO`, and emplacing its absent
    skill list dereferenced null at +0x10 - SIGSEGV, or in the earlier
    configuration `std::bad_alloc`/SIGABRT.

The party is described by the PROFILE, not by the `/lobby/Enter` deck. That is
why filling deck slots changed the preparation screen but never fixed this.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "src" / "game-routes.ts"

ANCHOR = '''  if (route === "/relation/BlockList") {'''
NEW = '''  if (route === "/relation/GetTargetUserInfo" || route === "/relation/GetTargetUserInfo.WithAI") {
    // The profile describes the party. `CSRSyncGlobal::ParseUserDatailInfo`
    // (0xf6e240) reads these keys and feeds `ref_id_` straight into
    // `CSRCard::SetRefID`, so an absent card list means every party member gets
    // an empty ref id. That was the whole expedition blocker - see the header of
    // tools/patch-user-detail-info.py for the full chain.
    //
    // The recovered key set is `inst_id_ ref_id_ rank_ rank_up_cnt_ awk_step_
    // overcome_cnt_ awk_overcome_ exp_ skin_ref_id_ skill_1_level_ ..
    // skill_5_level_`, with the same names suffixed `_leader`, plus pvid,
    // group_exp, vip_exp, league_level, rating_point, awake, stage_id,
    // prev_rank and win_message.
    const leader = {
      inst_id_leader: 1, ref_id_leader: "001", rank_leader: 1, rank_up_cnt_leader: 0,
      awk_step_leader: 0, overcome_cnt_leader: 0, awk_overcome_leader: 0,
      exp_leader: 0, skin_ref_id_leader: "",
      skill_1_level_leader: 1, skill_2_level_leader: 0, skill_3_level_leader: 0,
      skill_4_level_leader: 0, skill_5_level_leader: 0,
    };
    const card = (instId: number, refId: string, slot: number) => ({
      [`inst_id_${slot}`]: instId,
      [`ref_id_${slot}`]: refId,
      [`rank_${slot}`]: 1,
      [`rank_up_cnt_${slot}`]: 0,
      [`awk_step_${slot}`]: 0,
      [`overcome_cnt_${slot}`]: 0,
      [`awk_overcome_${slot}`]: 0,
      [`exp_${slot}`]: 0,
      [`skin_ref_id_${slot}`]: "",
      [`skill_1_level_${slot}`]: 1,
      [`skill_2_level_${slot}`]: 0,
      [`skill_3_level_${slot}`]: 0,
      [`skill_4_level_${slot}`]: 0,
      [`skill_5_level_${slot}`]: 0,
    });
    return state.envelope({
      pvid: 0, nick_name: "%user_name%", nickname: "%user_name%",
      group_exp: 0, vip_exp: 0, league_level: 1, rating_point: 0, awake: 0,
      stage_id: "N003", prev_rank: 0, win_message: "",
      ...leader,
      ...card(1, "001", 1),
      ...card(2, "001", 2),
      ...card(3, "001", 3),
      ...card(4, "001", 4),
    });
  }
  if (route === "/relation/BlockList") {'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "ref_id_leader" in src:
        print("user detail info already implemented")
        return 0
    if src.count(ANCHOR) != 1:
        raise SystemExit(f"anchor found {src.count(ANCHOR)} times")
    TARGET.write_text(src.replace(ANCHOR, NEW), encoding="utf-8")
    print("/relation/GetTargetUserInfo now returns a profile carrying the party")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
