"""Un-wedge the battle lifecycle that silently rejected every mission.

Found by the tester agent (report-006). `/mission/Start` has been answering

    {"accepted":false, "stage_id":"N003", "error_code":"BATTLE_ALREADY_ACTIVE"}

`server-ts/data/state.json` holds a battle left over from the earliest runs,
back when the client could not resolve a node and sent `stage_id: ""`:

    "active_battle": { "stage_id": "", "state": "active", ... }

The guard was `if (existingBattle?.state === "active")` and then
`if (existingBattle.stage_id !== stageId) reject`. With the stored stage_id empty
and the requested one `N003`, that took the rejection branch on *every*
subsequent request, forever. So every mission test since the stage id became
resolvable was talking to a REJECTED battle, and the crash we have been
chasing was measured against a rejection rather than against a battle setup.

The guard should reject only a genuinely live battle for the same stage.
Anything else - an empty placeholder from an old run, or a different stage that
the client has since moved on from - is recoverable.

Also clears the stale entry from the persisted state file so the first run after
this change is not itself wedged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "server-ts" / "src" / "state.ts"
STATE_FILE = ROOT / "server-ts" / "data" / "state.json"

OLD = """    const stageId = requestedStageId.length > 1 ? requestedStageId : "n_01_01";
    const existingBattle = game.active_battle;
    if (existingBattle?.state === "active") {
      if (existingBattle.stage_id !== stageId) {
        return this.envelope({
          accepted: false,
          stage_id: stageId,
          battle_id: existingBattle.battle_id,
          error_code: "BATTLE_ALREADY_ACTIVE",
        });
      }
      return this.envelope({"""

NEW = """    const stageId = requestedStageId.length > 1 ? requestedStageId : "n_01_01";
    const existingBattle = game.active_battle;
    // Reject only a genuinely live battle for THIS stage.
    //
    // A stored battle with an empty stage_id is a leftover from the earliest
    // runs, when the client could not resolve a node and sent `stage_id: ""`.
    // With the old guard, `"" !== "N003"` took the rejection branch on every
    // later request and the battle could never start, so every mission test
    // since the stage id became resolvable was measured against a rejection
    // rather than a battle setup. An empty, stale or superseded placeholder is
    // recoverable; only a live battle for the same stage blocks a restart.
    if (existingBattle?.state === "active" && existingBattle.stage_id === stageId) {
      return this.envelope({"""


def clear_persisted() -> str:
    if not STATE_FILE.exists():
        return "no state file to clear"
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"could not parse state file: {exc}"
    cleared = 0
    entries = data.get("gameStates") or []
    # Serialised as a list of [pvid, game] pairs, not an object.
    pairs = entries.items() if isinstance(entries, dict) else entries
    for pair in pairs:
        pvid, game = pair if isinstance(pair, (list, tuple)) and len(pair) == 2 else (None, pair)
        if not isinstance(game, dict):
            continue
        battle = game.get("active_battle")
        if isinstance(battle, dict) and battle.get("state") == "active":
            game["active_battle"] = None
            game["active_stage_id"] = ""
            cleared += 1
            print(f"  cleared stuck battle for pvid {pvid} (stage_id={battle.get('stage_id')!r})")
    if cleared:
        STATE_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return f"cleared {cleared} stuck battle(s)"


def main() -> int:
    src = STATE.read_text(encoding="utf-8")
    if "A stored battle with an empty stage_id" in src:
        print("guard already corrected")
    else:
        if src.count(OLD) != 1:
            raise SystemExit(f"guard anchor found {src.count(OLD)} times")
        STATE.write_text(src.replace(OLD, NEW), encoding="utf-8")
        print("battle guard corrected")
    print(" ", clear_persisted())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
