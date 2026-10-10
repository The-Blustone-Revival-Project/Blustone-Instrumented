"""Update the smoke tests for the bare-array GetStage/GetArea contract."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "tests" / "smoke.ts"

REPLACEMENTS = [
    (
        '    if (endpoint === "/reference/GetStage") assert.ok(Array.isArray((result.body.ret_data as Record<string, unknown>).stage), `${endpoint} requires ret_data.stage[]`);\n'
        "    else assert.ok(Array.isArray(result.body.ret_data), `${endpoint} requires an array`);",
        "    // GetStage/GetArea return bare arrays: this parser family reads\n"
        "    // ret_data as an array and indexes it numerically, and wrapping the\n"
        "    // table in an object left the client's stage table empty.\n"
        "    assert.ok(Array.isArray(result.body.ret_data), `${endpoint} requires an array`);",
    ),
    (
        '  const stageCatalog = await postFixture("/reference/GetStage") as { stage: Array<{ id: string; stage_id: string; achieve_condition: string }> };\n'
        "  const stages = stageCatalog.stage;\n"
        '  const areas = await postFixture("/reference/GetArea") as { area: Array<{ id: string; serial: number }>; stage: Array<{ area_id: string; stage_id: string }> };',
        "  const stages = await postFixture(\"/reference/GetStage\") as Array<{ id: string; stage_id: string; achieve_condition: string }>;\n"
        "  const areas = await postFixture(\"/reference/GetArea\") as Array<{ id: string; area_id: string; serial: number; achieve_cnt?: number }>;",
    ),
]


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "reads\n    // ret_data as an array" in src:
        print("already updated")
        return 0
    for old, new in REPLACEMENTS:
        if src.count(old) != 1:
            raise SystemExit(f"anchor found {src.count(old)} times: {old[:60]!r}")
        src = src.replace(old, new)

    # The area assertion below reads areas.area; the array form means `areas` itself.
    old_area_assert = '  assert.deepEqual(areas.area.map((area) => area.serial).sort((a, b) => a - b), areas.area.map((_, index) => index), "area serials must include hidden origin 0 and be contiguous");'
    new_area_assert = '  assert.deepEqual(areas.map((area) => area.serial).sort((a, b) => a - b), areas.map((_, index) => index), "area serials must include hidden origin 0 and be contiguous");\n'
    "  // The native area record is keyed on area_id, not id: CSRGameStage::GetAreaData\n"
    "  // takes an area_id, and publishing only id left the area table unresolvable.\n"
    "  for (const area of areas) assert.equal(area.area_id, area.id, `${area.id} must carry area_id`);"
    if src.count(old_area_assert) == 1:
        src = src.replace(old_area_assert, new_area_assert)

    TARGET.write_text(src, encoding="utf-8")
    print(f"updated {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
