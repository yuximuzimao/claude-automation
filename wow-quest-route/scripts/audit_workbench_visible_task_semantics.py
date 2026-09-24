from __future__ import annotations

import json
import glob
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIND = {"接": "accept", "做": "objective", "交": "turnin"}

checked = 0
issues: list[dict] = []

for f in sorted(glob.glob(str(ROOT / "data/generated/route-lifecycle/profiles/*/publisher.json"))):
    payload = json.load(open(f, encoding="utf-8"))
    key = payload["display"]["publish_key"]
    for si, step in enumerate(payload.get("steps") or [], 1):
        for li, line in enumerate(step.get("lines") or [], 1):
            text = str(line.get("text") or "")
            refs = line.get("task_refs") or []
            if not refs:
                continue

            cursor = 0
            current_kind = None
            for oi, ref in enumerate(refs, 1):
                name = str(ref.get("name") or "")
                token = f"《{name}》"
                start = text.find(token, cursor)
                if start < 0:
                    issues.append(
                        {
                            "route": key,
                            "step": si,
                            "line": li,
                            "occurrence": oi,
                            "text": text,
                            "kind": "task_ref_not_visible",
                            "ref_name": name,
                            "ref_kind": ref.get("kind"),
                        }
                    )
                    continue

                between = text[cursor:start]
                verbs = re.findall(r"(?:^|→|↳|\s)(接|做|交)\s*$", between)
                if verbs:
                    current_kind = KIND[verbs[-1]]

                actual = ref.get("kind")
                if current_kind is None:
                    issues.append(
                        {
                            "route": key,
                            "step": si,
                            "line": li,
                            "occurrence": oi,
                            "text": text,
                            "kind": "visible_verb_not_inferred",
                            "ref_name": name,
                            "ref_kind": actual,
                        }
                    )
                elif current_kind != actual:
                    issues.append(
                        {
                            "route": key,
                            "step": si,
                            "line": li,
                            "occurrence": oi,
                            "text": text,
                            "kind": "visible_kind_mismatch",
                            "ref_name": name,
                            "visible_kind": current_kind,
                            "ref_kind": actual,
                        }
                    )

                checked += 1
                cursor = start + len(token)

print(
    json.dumps(
        {
            "checked_task_occurrences": checked,
            "issues": issues,
        },
        ensure_ascii=False,
        indent=2,
    )
)
if issues:
    raise SystemExit(1)
