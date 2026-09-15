from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_README = ROOT / "README.md"
RULES = ROOT / "docs/rules"
SKILL = ROOT / "SKILL.md"
INDEX = ROOT / "docs/INDEX.md"
RULE_INDEX = RULES / "README.md"
CLAUDE = ROOT / "CLAUDE.md"
SOP = ROOT / "docs/verified-routes/ROUTE-DESIGN-PROCESS.md"
DK_STARTING_ZONE = ROOT / "docs/verified-routes/DK-STARTING-ZONE-NOTES.md"
ARCHIVED_SCRIPTS = ROOT / "docs/archive/scripts"
SCRIPTS_README = ROOT / "scripts/README.md"
STATE_COMPAT = RULES / "state-and-validation.md"


def _active_python_files() -> list[Path]:
    files = [
        *sorted((ROOT / "lib").rglob("*.py")),
        *sorted((ROOT / "scripts").rglob("*.py")),
        ROOT / "cli.py",
    ]
    this_test = Path(__file__).resolve()
    files.extend(
        path
        for path in sorted((ROOT / "tests").glob("test_*.py"))
        if path.resolve() != this_test
    )
    return files


def test_rules_registry_routes_every_permanent_child_rule() -> None:
    """The rules registry is the one exhaustive owner catalog."""
    child_rules = sorted(path.name for path in RULES.glob("*.md") if path.name != "README.md")
    assert child_rules

    registry = RULE_INDEX.read_text(encoding="utf-8")
    for rule_name in child_rules:
        assert rule_name in registry, f"{rule_name} is not routed from docs/rules/README.md"


def test_index_is_navigation_not_a_second_behavior_router() -> None:
    """INDEX may list files, but must point back to the unique rules registry."""
    text = INDEX.read_text(encoding="utf-8")
    assert "docs/rules/README.md" in text or "rules/README.md" in text


def test_skill_uses_progressive_rule_routing() -> None:
    """SKILL must route to registries/processes, not enumerate every child rule."""
    text = SKILL.read_text(encoding="utf-8")
    assert "docs/rules/README.md" in text or "rules/README.md" in text
    assert "ROUTE-DESIGN-PROCESS.md" in text

    child_rules = sorted(path.name for path in RULES.glob("*.md") if path.name != "README.md")
    # If almost every child rule name is copied into SKILL, progressive disclosure has regressed.
    copied = [name for name in child_rules if name in text]
    assert len(copied) <= max(4, len(child_rules) // 2), (
        "SKILL is becoming a duplicate exhaustive rule directory: " + ", ".join(copied)
    )


def test_claude_points_to_skill_and_rules_registry_without_owning_rule_catalog() -> None:
    text = CLAUDE.read_text(encoding="utf-8")
    assert "SKILL.md" in text
    assert "docs/rules/README.md" in text or "rules/README.md" in text


def test_sop_declares_it_is_only_an_orchestrator() -> None:
    text = SOP.read_text(encoding="utf-8")
    assert "流程调度器" in text
    assert "不定义任务机制" in text


def test_archived_stage_scripts_cannot_reenter_active_python_paths() -> None:
    archived_names = {path.name for path in ARCHIVED_SCRIPTS.glob("*.py")}
    assert archived_names

    for path in _active_python_files():
        text = path.read_text(encoding="utf-8")
        assert "docs/archive/scripts" not in text, (
            f"active code references archive script directory: {path.relative_to(ROOT)}"
        )
        leaked_names = sorted(name for name in archived_names if name in text)
        assert not leaked_names, (
            f"active code references archived stage scripts {leaked_names}: {path.relative_to(ROOT)}"
        )


def test_scripts_registry_covers_every_top_level_script() -> None:
    registry = SCRIPTS_README.read_text(encoding="utf-8")
    actual = {path.name for path in (ROOT / "scripts").glob("*.py")}
    registered = set(re.findall(r"^\| `([^`]+\.py)` \|", registry, flags=re.MULTILINE))
    assert registered == actual, (
        f"scripts registry mismatch; missing={sorted(actual - registered)}, "
        f"extra={sorted(registered - actual)}"
    )


def test_root_readme_routes_to_frozen_truth_layers() -> None:
    text = ROOT_README.read_text(encoding="utf-8")
    assert "data/task-cards/" in text
    assert "data/route-profiles/" in text
    assert "Generated Product" in text
    assert "workbench-routes.json` 保存当前有效路线数据" not in text
    assert "具体任务事实优先复用 `docs/task-library/` 和 `data/observations/`" not in text


def test_active_dk_writeback_does_not_promote_legacy_fivebox_store() -> None:
    text = DK_STARTING_ZONE.read_text(encoding="utf-8")
    assert "TASK_FACT" in text
    assert "fivebox.status" in text
    assert "不再作为新事实写入口" in text


def test_retired_state_document_is_only_a_compatibility_pointer() -> None:
    text = STATE_COMPAT.read_text(encoding="utf-8")
    assert "不再是现役规则owner" in text
    assert "新规则不得继续写入这里" in text


def test_old_propagation_owner_name_is_gone_from_active_routing_docs() -> None:
    for path in [ROOT_README, SKILL, INDEX, RULE_INDEX, CLAUDE, SOP, DK_STARTING_ZONE]:
        assert "route-profile-and-propagation.md" not in path.read_text(encoding="utf-8")
