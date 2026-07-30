from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib.navigator_renderer import write_navigator_html
from lib.questie_source import load_questie
from lib.route_builder import build_route, write_route
from lib.world_builder import build_world_routes


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SPEC = PROJECT_ROOT / "data/route-specs/sunstrider-isle.json"
DEFAULT_OBSERVATIONS = PROJECT_ROOT / "data/observations/fivebox-task-types.json"
DEFAULT_JOURNEY = PROJECT_ROOT / "data/journey/current-paladin.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/routes/horde/blood-elf"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Questie任务数据与五开候选路线工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-sunstrider", help="生成逐日岛候选路线与交互HTML")
    build.add_argument(
        "--questie-source",
        required=True,
        help="Questie完整ZIP，或已解压的Questie目录",
    )
    build.add_argument("--spec", default=str(DEFAULT_SPEC), help="路线骨架JSON")
    build.add_argument("--observations", default=str(DEFAULT_OBSERVATIONS), help="五开实测JSON")
    build.add_argument("--journey", default=str(DEFAULT_JOURNEY), help="脱敏人物历程JSON")
    build.add_argument("--output", default=str(DEFAULT_OUTPUT), help="输出目录")

    world = subparsers.add_parser("build-world", help="生成血精灵圣骑士1-80全部户外区域候选导航")
    world.add_argument("--questie-source", required=True, help="Questie完整ZIP，或已解压的Questie目录")
    world.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "data/routes/world-candidate"),
        help="全区域输出目录",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build-sunstrider":
            data = load_questie(args.questie_source)
            route = build_route(data, Path(args.spec), Path(args.observations))
            output = Path(args.output)
            markdown_path, json_path = write_route(route, output)
            navigator_path = write_navigator_html(route, output, Path(args.journey))
            print(f"Questie版本: {data.version}")
            print(f"已生成: {markdown_path}")
            print(f"已生成: {json_path}")
            print(f"已生成: {navigator_path}")
            return 0
        if args.command == "build-world":
            data = load_questie(args.questie_source)
            manifest = build_world_routes(data, args.questie_source, Path(args.output))
            print(f"Questie版本: {data.version}")
            print(f"已生成区域: {manifest['zone_count']}")
            print(f"候选任务总数: {manifest['quest_count']}")
            print(f"索引: {Path(args.output) / manifest['index']}")
            return 0
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
