from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.task_evidence_index import load_index_task

DEFAULT_INDEX = ROOT / "_sandbox/task-evidence-index.sqlite"


def main() -> None:
    parser = argparse.ArgumentParser(description="Read one task_id from the prebuilt Task Evidence Index; never reparses Questie or SQL.")
    parser.add_argument("task_id", type=int)
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    args = parser.parse_args()
    payload = load_index_task(Path(args.index), args.task_id)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
