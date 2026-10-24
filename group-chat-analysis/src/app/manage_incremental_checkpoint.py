"""Create or inspect a one-shot incremental anchor checkpoint."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from src.store import IncrementalCheckpointStore


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--runtime-root", type=Path, default=Path("runtime"))
    parser.add_argument("--source-runtime", type=Path)
    parser.add_argument("--group-key")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    store = IncrementalCheckpointStore(
        args.project_root,
        args.runtime_root,
    )
    if args.show:
        document = store.load()
        print(
            json.dumps(
                {
                    "status": "absent" if document is None else "ready",
                    "checkpoint": document,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.source_runtime is None or not args.group_key:
        parser.error("--source-runtime and --group-key are required unless --show is used")

    result = store.create_from_completed_runtime(
        source_runtime=args.source_runtime,
        group_key=args.group_key,
        created_at=utc_now(),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
