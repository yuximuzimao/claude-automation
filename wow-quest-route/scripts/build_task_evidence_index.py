from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.task_evidence_index import build_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the disposable current Task Card evidence SQLite index.")
    parser.add_argument("--questie-source", required=True, help="Questie 11.34.0 ZIP or directory")
    parser.add_argument(
        "--output",
        default=str(ROOT / "_sandbox/task-evidence-index.sqlite"),
        help="Disposable SQLite output; _sandbox is ignored by git.",
    )
    args = parser.parse_args()
    result = build_index(ROOT, Path(args.questie_source), Path(args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
