from __future__ import annotations

import json
from pathlib import Path

from zang_semantic_steps import (
    apply_zang_step1,
    apply_zang_step2,
    apply_zang_step3,
    apply_zang_step4,
    apply_zang_step5,
    apply_zang_step6,
    apply_zang_step7,
    apply_zang_step8,
    apply_zang_step9,
    apply_zang_step10,
    apply_zang_step11,
    apply_zang_step12,
    apply_zang_step13,
)

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"


def main() -> None:
    data = json.loads(ROUTES.read_text(encoding="utf-8"))
    route = data["zang"]
    route["sub"] = "从塞纳里奥庇护所开始，完成赞加主体路线后由莉萨奥方向进入纳格兰。"
    apply_zang_step1(route)
    apply_zang_step2(route)
    apply_zang_step3(route)
    apply_zang_step4(route)
    apply_zang_step5(route)
    apply_zang_step6(route)
    apply_zang_step7(route)
    apply_zang_step8(route)
    apply_zang_step9(route)
    apply_zang_step10(route)
    apply_zang_step11(route)
    apply_zang_step12(route)
    apply_zang_step13(route)
    route["uiStandard"] = "semantic-hud-v45"
    ROUTES.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "zang_step1_refactored",
                "points": len(route["points"]),
                "steps": len(route["stepGroups"]),
                "step1_range": [route["stepGroups"][0]["start"], route["stepGroups"][0]["end"]],
                "step1_title": route["stepGroups"][0]["title"],
                "semantic_steps": sum(bool(group.get("actionHtml")) for group in route["stepGroups"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
