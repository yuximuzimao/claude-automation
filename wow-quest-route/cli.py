from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib.navigator_renderer import write_navigator_html
from lib.questie_source import load_questie
from lib.route_builder import build_route, write_route
from lib.simple_route import build_simple_route, write_audit_markdown, write_simple_html
from lib.world_builder import build_world_routes
from lib.world_review import build_world_review, write_world_review_markdown


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SPEC = PROJECT_ROOT / "data/route-specs/sunstrider-isle.json"
DEFAULT_OBSERVATIONS = PROJECT_ROOT / "data/observations/fivebox-task-types.json"
DEFAULT_JOURNEY = PROJECT_ROOT / "data/journey/current-paladin.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/routes/horde/blood-elf"
DEFAULT_SIMPLE_SPEC = PROJECT_ROOT / "data/route-specs/simple-leveling-route.json"
DEFAULT_CANDIDATE_ROOT = PROJECT_ROOT / "data/routes/world-candidate"
DEFAULT_SIMPLE_HTML = PROJECT_ROOT / "data/routes/simple-leveling-route.html"
DEFAULT_SIMPLE_AUDIT = PROJECT_ROOT / "docs/NEAT_SIMPLE_LEVELING_ROUTE.md"
DEFAULT_DK_CANDIDATE_ROOT = PROJECT_ROOT / "data/routes/world-candidate-dk"
DEFAULT_DK_WORLD_HTML = PROJECT_ROOT / "data/routes/dk-55-80-world-tasks.html"
DEFAULT_DK_WORLD_AUDIT = PROJECT_ROOT / "docs/DK_55_80_WORLD_TASKS.md"


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
    world.add_argument(
        "--profile",
        choices=("paladin", "death-knight"),
        default="paladin",
        help="角色任务过滤配置",
    )

    simple = subparsers.add_parser("build-simple", help="生成血精灵圣骑士1-80单页极简任务路线")
    simple.add_argument("--questie-source", required=True, help="Questie完整ZIP，或已解压的Questie目录")
    simple.add_argument("--rxp-source", help="历史RXPGuides.lua；只读取指南元数据，不要求当前安装RXP")
    simple.add_argument("--spec", default=str(DEFAULT_SIMPLE_SPEC), help="极简路线地图阶段JSON")
    simple.add_argument("--candidate-root", default=str(DEFAULT_CANDIDATE_ROOT), help="现有全区域候选JSON目录")
    simple.add_argument("--output", default=str(DEFAULT_SIMPLE_HTML), help="单页HTML输出路径")
    simple.add_argument("--audit-output", default=str(DEFAULT_SIMPLE_AUDIT), help="内部NEAT归档路径")

    dk_world = subparsers.add_parser(
        "build-dk-world",
        help="生成血精灵死亡骑士55-80全世界任务母版",
    )
    dk_world.add_argument("--questie-source", required=True, help="Questie完整ZIP，或已解压的Questie目录")
    dk_world.add_argument(
        "--candidate-output",
        default=str(DEFAULT_DK_CANDIDATE_ROOT),
        help="死亡骑士全区域候选数据目录",
    )
    dk_world.add_argument("--output", default=str(DEFAULT_DK_WORLD_HTML), help="全任务单页HTML输出路径")
    dk_world.add_argument("--audit-output", default=str(DEFAULT_DK_WORLD_AUDIT), help="内部归档路径")
    dk_world.add_argument("--min-level", type=int, default=55)
    dk_world.add_argument("--max-level", type=int, default=80)
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
            manifest = build_world_routes(
                data,
                args.questie_source,
                Path(args.output),
                profile=args.profile,
            )
            print(f"Questie版本: {data.version}")
            print(f"已生成区域: {manifest['zone_count']}")
            print(f"候选任务总数: {manifest['quest_count']}")
            print(f"索引: {Path(args.output) / manifest['index']}")
            return 0
        if args.command == "build-simple":
            data = load_questie(args.questie_source)
            route = build_simple_route(
                data,
                Path(args.spec),
                Path(args.candidate_root),
                Path(args.rxp_source) if args.rxp_source else None,
            )
            html_path = write_simple_html(route, Path(args.output))
            audit_path = write_audit_markdown(route, Path(args.audit_output))
            print(f"Questie版本: {data.version}")
            print(f"地图阶段: {route['stats']['segment_count']}")
            print(f"内部候选步骤: {route['stats']['step_count']}")
            print(f"用户页面步骤: {route['stats']['public_step_count']}")
            print(f"打怪掉物·必做: {route['stats']['loot_must_count']}")
            print(f"打怪掉物·可跳: {route['stats']['loot_optional_count']}")
            print(f"HTML: {html_path}")
            print(f"内部归档: {audit_path}")
            return 0
        if args.command == "build-dk-world":
            data = load_questie(args.questie_source)
            candidate_output = Path(args.candidate_output)
            manifest = build_world_routes(
                data,
                args.questie_source,
                candidate_output,
                profile="death-knight",
            )
            route = build_world_review(
                data,
                candidate_output,
                min_level=args.min_level,
                max_level=args.max_level,
            )
            html_path = write_simple_html(route, Path(args.output))
            audit_path = write_world_review_markdown(route, Path(args.audit_output))
            print(f"Questie版本: {data.version}")
            print(f"死亡骑士候选区域: {manifest['zone_count']}")
            print(f"全任务母版地图: {route['stats']['segment_count']}")
            print(f"全任务母版任务: {route['stats']['selected_quest_count']}")
            print(f"用户页面步骤: {route['stats']['public_step_count']}")
            print(f"HTML: {html_path}")
            print(f"内部归档: {audit_path}")
            return 0
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
