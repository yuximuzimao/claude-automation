from __future__ import annotations

import argparse
import sys

from .instance_lock import AlreadyRunningError, SingleInstanceGuard
from .ui import run_app


def main() -> int:
    parser = argparse.ArgumentParser(description="审单悬浮窗")
    parser.add_argument("--version", action="version", version="order-review 0.1.0")
    parser.parse_args()
    try:
        with SingleInstanceGuard():
            run_app()
    except AlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
