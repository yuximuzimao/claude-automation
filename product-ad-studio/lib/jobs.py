from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_CANVAS = {"width": 1080, "height": 1920, "orientation": "portrait", "aspect_ratio": "9:16"}


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value)
    return value.strip("-") or "job"


def create_job(project_root: Path, *, brand: str, name: str, job_id: str | None = None) -> Path:
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    resolved_job_id = job_id or f"{date_prefix}-{slugify(name)}"
    job_dir = project_root / "jobs" / resolved_job_id
    if job_dir.exists():
        raise FileExistsError(job_dir)

    for relative in ("input", "brief", "working", "output"):
        (job_dir / relative).mkdir(parents=True, exist_ok=False)

    job_json: dict[str, Any] = {
        "job_id": resolved_job_id,
        "name": name,
        "brand": brand,
        "status": "intake",
        "canvas": DEFAULT_CANVAS,
        "input_asset_ids": [],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (job_dir / "job.json").write_text(json.dumps(job_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (job_dir / "brief" / "human-alignment.md").write_text(
        "# 人话对齐说明\n\n"
        "待 GPT 根据 Demo、产品素材、参考图和用户要求填写。控制在设计师可快速判断的长度。\n",
        encoding="utf-8",
    )
    (job_dir / "brief" / "design-intent.json").write_text(
        json.dumps(
            {
                "objective": "",
                "canvas": DEFAULT_CANVAS,
                "asset_ids": [],
                "content_hierarchy": [],
                "layout_freedom": "high",
                "product_constraints": {
                    "preserve_geometry": True,
                    "preserve_relative_scale": True,
                    "avoid_perspective": True,
                    "protect_logo": True,
                    "partial_overlap_allowed": True,
                },
                "style_features": [],
                "forbidden_reference_elements": ["watermark", "account_name", "other_brand_logo", "other_brand_product"],
                "exact_copy": [],
                "open_questions": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (job_dir / "brief" / "render-plan.json").write_text(
        json.dumps(
            {
                "background": {"method": "undecided", "notes": ""},
                "product": {"method": "use_original_assets", "notes": ""},
                "integration": {"method": "layered_lighting_and_shadows", "notes": ""},
                "graphics": {"method": "svg_or_canvas", "notes": ""},
                "text": {"method": "deterministic_layout", "notes": ""},
                "qa": ["copy_accuracy", "product_fidelity", "logo_visibility", "layout_readability", "style_alignment"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (job_dir / "revisions.jsonl").write_text("", encoding="utf-8")
    return job_dir
