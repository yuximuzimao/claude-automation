from __future__ import annotations

import argparse

from .ui import run_app


def main() -> None:
    parser = argparse.ArgumentParser(description="审单悬浮窗")
    parser.add_argument("--version", action="version", version="order-review 0.1.0")
    parser.parse_args()
    run_app()


if __name__ == "__main__":
    main()
