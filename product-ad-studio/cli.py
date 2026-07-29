from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib.assets import import_asset, verify_catalog
from lib.demo import write_demo_json
from lib.jobs import create_job


PROJECT_ROOT = Path(__file__).resolve().parent
BRANDS_ROOT = PROJECT_ROOT / "data" / "brands"


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def command_import_assets(args: argparse.Namespace) -> int:
    brand_dir = BRANDS_ROOT / args.brand
    entry, created = import_asset(
        source=Path(args.source),
        brand_dir=brand_dir,
        asset_id=args.asset_id,
        role=args.role,
        description=args.description,
        tags=split_csv(args.tags),
        aliases=split_csv(args.aliases),
        protection=json.loads(args.protection) if args.protection else None,
        move=args.move,
    )
    action = "imported" if created else "deduplicated"
    print(json.dumps({"action": action, "asset": entry}, ensure_ascii=False, indent=2))
    return 0


def command_parse_demo(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else PROJECT_ROOT / "jobs" / "_parsed-demo.json"
    result = write_demo_json(Path(args.source), output)
    print(json.dumps({"output": str(output), "sheets": len(result["sheets"])}, ensure_ascii=False, indent=2))
    return 0


def command_new_job(args: argparse.Namespace) -> int:
    job_dir = create_job(PROJECT_ROOT, brand=args.brand, name=args.name, job_id=args.job_id)
    print(job_dir)
    return 0


def command_verify(args: argparse.Namespace) -> int:
    brands = [BRANDS_ROOT / args.brand] if args.brand else [path for path in BRANDS_ROOT.iterdir() if path.is_dir()]
    errors: list[str] = []
    for brand_dir in brands:
        errors.extend(f"{brand_dir.name}: {message}" for message in verify_catalog(brand_dir))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("catalog verification passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="商品宣传图工作台本地工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import-assets", help="导入、指纹登记并去重图片素材")
    import_parser.add_argument("--brand", required=True)
    import_parser.add_argument("--source", required=True)
    import_parser.add_argument("--asset-id", required=True)
    import_parser.add_argument(
        "--role",
        required=True,
        choices=[
            "product_source",
            "product_set",
            "brand_logo",
            "demo_layout",
            "style_reference",
            "designer_output",
            "edit_target",
            "generated_draft",
        ],
    )
    import_parser.add_argument("--description", required=True)
    import_parser.add_argument("--tags", help="逗号分隔")
    import_parser.add_argument("--aliases", help="逗号分隔")
    import_parser.add_argument("--protection", help="JSON 对象")
    import_parser.add_argument("--move", action="store_true", help="成功后移动源文件而不是复制")
    import_parser.set_defaults(func=command_import_assets)

    demo_parser = subparsers.add_parser("parse-demo", help="可选：辅助提取下载后的 Excel 文案和结构")
    demo_parser.add_argument("--source", required=True)
    demo_parser.add_argument("--output")
    demo_parser.set_defaults(func=command_parse_demo)

    job_parser = subparsers.add_parser("new-job", help="创建通用设计任务包")
    job_parser.add_argument("--brand", required=True)
    job_parser.add_argument("--name", required=True)
    job_parser.add_argument("--job-id")
    job_parser.set_defaults(func=command_new_job)

    verify_parser = subparsers.add_parser("verify", help="校验素材文件和目录指纹")
    verify_parser.add_argument("--brand")
    verify_parser.set_defaults(func=command_verify)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (FileNotFoundError, FileExistsError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
