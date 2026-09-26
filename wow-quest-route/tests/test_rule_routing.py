from __future__ import annotations

import json
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
TODO = ROOT / "tasks/todo.md"
FIVEBOX_PENDING = ROOT / "tasks/fivebox-pending.md"
DK_STARTING_ZONE = ROOT / "docs/verified-routes/DK-STARTING-ZONE-NOTES.md"
ARCHIVED_SCRIPTS = ROOT / "docs/archive/scripts"
SCRIPTS_README = ROOT / "scripts/README.md"

RETIRED_ACTIVE_FILES = [
    RULES / "workflow-governance.md",
    RULES / "route-lifecycle-execution.md",
    RULES / "state-and-validation.md",
    ROOT / "tasks/final-human-decisions.json",
    ROOT / "tasks/publisher-replacement-review.md",
]


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


def _active_routing_docs() -> list[Path]:
    return [
        ROOT_README,
        SKILL,
        INDEX,
        RULE_INDEX,
        CLAUDE,
        SOP,
        TODO,
        FIVEBOX_PENDING,
        ROOT / "docs/verified-routes/CURRENT.md",
        ROOT / "docs/task-library/README.md",
        ROOT / "tests/README.md",
        SCRIPTS_README,
        *sorted(path for path in RULES.glob("*.md") if path.name != "README.md"),
    ]


def test_rules_readme_is_complete_folder_directory() -> None:
    expected = {
        "execution-and-mechanics.md",
        "leveling-and-selection.md",
        "xp-model.md",
        "timing-and-benchmarking.md",
        "economy-model.md",
        "route-profile-and-lifecycle.md",
        "route-atlas-optimization.md",
        "route-atlas-player-contract.md",
        "route-atlas-route-display.md",
        "route-atlas-task-presentation.md",
        "route-atlas-ui-and-assets.md",
        "route-lifecycle-final-audit.md",
    }
    actual = {path.name for path in RULES.glob("*.md") if path.name != "README.md"}
    assert actual == expected

    directory = RULE_INDEX.read_text(encoding="utf-8")
    for name in expected:
        assert name in directory
    assert "python3 " not in directory
    assert "TASK_FACT" not in directory


def test_index_is_pure_navigation() -> None:
    text = INDEX.read_text(encoding="utf-8")
    assert "纯导航" in text
    assert "rules/README.md" in text
    assert "tasks/todo.md" in text
    assert "python3 " not in text


def test_skill_is_low_ambiguity_first_level_router() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "低歧义一级分流" in text
    assert "ROUTE-DESIGN-PROCESS.md" in text
    assert "普通业务执行不从Scripts README挑脚本" in text

    copied_rules = [
        path.name for path in RULES.glob("*.md")
        if path.name != "README.md" and path.name in text
    ]
    assert len(copied_rules) <= 4, f"SKILL duplicates too many owners: {copied_rules}"


def test_project_claude_defers_workspace_governance_to_root() -> None:
    text = CLAUDE.read_text(encoding="utf-8")
    assert "SKILL.md" in text
    assert "/Users/chat/claude/CLAUDE.md" in text
    assert "本项目不复制第二套定义" in text


def test_sop_is_classifier_not_execution_manual() -> None:
    text = SOP.read_text(encoding="utf-8")
    assert "唯一分类SOP" in text
    assert "当前输入属于哪一类" in text
    assert "下一份唯一应该读取的owner" in text
    assert ".py" not in text
    assert "python3 " not in text
    assert "route-lifecycle-execution.md" not in text
    assert "workflow-governance.md" not in text
    assert "Stage 1–14" not in text


def test_sop_routes_every_declared_change_type_from_one_table() -> None:
    text = SOP.read_text(encoding="utf-8")
    change_types = [
        "TASK_FACT",
        "TASK_PRESENTATION",
        "PROFILE_STEPS",
        "PROFILE_TASK_SET",
        "PROFILE_CONTRACT",
        "PROFILE_DISPLAY",
        "ROUTE_PROGRAM",
        "NEW_PROFILE",
        "CURRENT_RUNTIME",
        "OBSERVATION",
        "UI_ENGINEERING",
        "MODEL_OR_RULE",
        "REPUBLISH_ONLY",
        "ARCHITECTURE_MIGRATION",
    ]
    for change_type in change_types:
        rows = re.findall(rf"^\| `{re.escape(change_type)}` \|", text, flags=re.MULTILINE)
        assert len(rows) == 1, f"{change_type} must have exactly one canonical SOP row"


def test_formal_operations_live_in_their_real_owners() -> None:
    owner_tokens = {
        "route-profile-and-lifecycle.md": [
            "python3 scripts/build_route_replay.py <profile_id>",
            "python3 scripts/build_program_continuity.py <program_id>",
            "python3 scripts/update_program_continuity_from_member.py <program_id> <profile_id>",
        ],
        "xp-model.md": [
            "python3 scripts/build_route_xp.py <profile_id>",
            "python3 scripts/build_program_xp.py <program_id>",
            "python3 scripts/update_program_xp_from_member.py <program_id> <profile_id>",
        ],
        "timing-and-benchmarking.md": [
            "python3 scripts/build_route_timing.py <profile_id>",
            "python3 scripts/build_program_timing.py <program_id>",
            "python3 scripts/update_program_member_timing.py <program_id> <profile_id>",
        ],
        "economy-model.md": [
            "python3 scripts/build_route_economy.py <profile_id>",
            "python3 scripts/build_program_economy.py <program_id>",
            "python3 scripts/update_program_member_economy.py <program_id> <profile_id>",
        ],
        "route-atlas-optimization.md": [
            "python3 scripts/audit_route_interaction_continuity.py <profile_id>",
            "python3 scripts/build_route_movement.py <profile_id>",
            "python3 scripts/build_route_service_context.py <profile_id>",
        ],
        "route-atlas-route-display.md": [
            "python3 scripts/build_route_display.py <profile_id>",
            "python3 scripts/update_route_display_task.py <profile_id> <task_id>",
        ],
        "route-atlas-task-presentation.md": [
            "python3 scripts/build_task_presentation.py <task_id>",
        ],
        "route-atlas-player-contract.md": [
            "python3 scripts/rebuild_publisher_payload.py <profile_id>",
        ],
        "route-atlas-ui-and-assets.md": [
            "python3 scripts/render_route_assets.py <profile_id> --output-dir <dir>",
        ],
        "leveling-and-selection.md": [
            "python3 scripts/build_route_review_trigger.py program <program_id>",
            "python3 scripts/build_route_review_trigger.py profile <profile_id>",
        ],
        "route-lifecycle-final-audit.md": [
            "python3 scripts/audit_generated_cutover.py",
        ],
    }
    all_rule_text = {
        path.name: path.read_text(encoding="utf-8")
        for path in RULES.glob("*.md")
        if path.name != "README.md"
    }
    sop = SOP.read_text(encoding="utf-8")
    for owner, tokens in owner_tokens.items():
        for token in tokens:
            assert token in all_rule_text[owner], f"{token} missing from {owner}"
            assert token not in sop
            other_hits = [name for name, text in all_rule_text.items() if name != owner and token in text]
            assert not other_hits, f"{token} duplicated in owners: {other_hits}"


def test_unfinished_human_decisions_live_only_in_todo() -> None:
    text = TODO.read_text(encoding="utf-8")
    blockers = re.findall(r"^- \[ \] \[CUTOVER-BLOCKER:([^\]]+)\]", text, flags=re.MULTILINE)
    assert blockers == []
    assert len(blockers) == len(set(blockers))


def test_fivebox_pending_checklist_matches_formal_route_pending_tasks() -> None:
    checklist = FIVEBOX_PENDING.read_text(encoding="utf-8")
    checklist_ids = [
        int(match)
        for match in re.findall(r"^- \[ \] (\d+)《", checklist, flags=re.MULTILINE)
    ]
    assert len(checklist_ids) == len(set(checklist_ids))

    formal_task_ids: set[int] = set()
    for path in sorted((ROOT / "data/route-profiles").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data.get("profile_id"):
            continue
        for action in data.get("actions", []):
            task_id = action.get("task_id")
            if isinstance(task_id, int):
                formal_task_ids.add(task_id)

    pending_ids = set()
    for task_id in formal_task_ids:
        card = json.loads((ROOT / f"data/task-cards/{task_id}.json").read_text(encoding="utf-8"))
        if card.get("fivebox", {}).get("status") == "pending":
            pending_ids.add(task_id)

    assert set(checklist_ids) == pending_ids
    todo = TODO.read_text(encoding="utf-8")
    assert "tasks/fivebox-pending.md" in todo


def test_removed_intermediate_layers_do_not_exist_or_reenter_active_docs() -> None:
    for path in RETIRED_ACTIVE_FILES:
        assert not path.exists(), f"retired intermediate layer still active: {path.relative_to(ROOT)}"

    forbidden = [
        "workflow-governance.md",
        "route-lifecycle-execution.md",
        "state-and-validation.md",
        "final-human-decisions.json",
        "publisher-replacement-review.md",
    ]
    for path in _active_routing_docs():
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token} referenced by active doc {path.relative_to(ROOT)}"


def test_migration_history_is_not_embedded_in_sop() -> None:
    sop = SOP.read_text(encoding="utf-8")
    history = (ROOT / "docs/archive/analysis/2026-09-21-route-lifecycle-migration-history.md").read_text(
        encoding="utf-8"
    )
    assert "2026-09-21-route-lifecycle-migration-history.md" not in sop
    assert "../archive/" in sop
    assert "Stage 1–14" not in sop
    assert "本次迁移中的Stage编号" in history


def test_sop_keeps_classification_boundaries_and_stop_conditions() -> None:
    text = SOP.read_text(encoding="utf-8")
    for token in [
        "先拆信息，再分类",
        "事实 vs 路线",
        "路线动作 vs 玩家展示",
        "当前状态 vs 长期真源",
        "单例问题 vs 通用规则",
        "业务错误 vs 架构缺口",
        "缺证据",
        "需要用户业务裁决",
    ]:
        assert token in text


def test_player_semantic_parity_rule_has_one_permanent_owner() -> None:
    sop = SOP.read_text(encoding="utf-8")
    final_audit = (RULES / "route-lifecycle-final-audit.md").read_text(encoding="utf-8")
    for token in ["旧/新玩家表达逐句语义对拍", "changed_intentionally", "mismatch"]:
        assert token in final_audit
        assert token not in sop


def test_archived_scripts_cannot_reenter_active_python_paths() -> None:
    archived_names = {path.name for path in ARCHIVED_SCRIPTS.rglob("*.py")}
    assert archived_names
    for path in _active_python_files():
        text = path.read_text(encoding="utf-8")
        assert "docs/archive/scripts" not in text, (
            f"active code references archive script directory: {path.relative_to(ROOT)}"
        )
        leaked_names = sorted(name for name in archived_names if name in text)
        assert not leaked_names, (
            f"active code references archived scripts {leaked_names}: {path.relative_to(ROOT)}"
        )


def test_scripts_readme_is_complete_inventory_not_operation_router() -> None:
    registry = SCRIPTS_README.read_text(encoding="utf-8")
    actual = {path.name for path in (ROOT / "scripts").glob("*.py")}
    registered = set(re.findall(r"^\| `([^`]+\.py)` \|", registry, flags=re.MULTILINE))
    assert registered == actual, (
        f"scripts inventory mismatch; missing={sorted(actual - registered)}, "
        f"extra={sorted(registered - actual)}"
    )
    assert "它不决定业务流程" in registry
    assert "route-lifecycle-execution.md" not in registry


def test_root_readme_is_human_overview_not_second_rule_or_state_store() -> None:
    text = ROOT_README.read_text(encoding="utf-8")
    assert "data/routes/route-atlas-workbench.html" in text
    assert "SKILL.md" in text
    assert "tasks/todo.md" in text
    assert "docs/INDEX.md" in text
    assert "README不复制规则、Todo或CURRENT" in text
    assert "state-and-validation.md" not in text


def test_active_dk_writeback_does_not_promote_legacy_fivebox_store() -> None:
    text = DK_STARTING_ZONE.read_text(encoding="utf-8")
    assert "TASK_FACT" in text
    assert "fivebox.status" in text
    assert "不再作为新事实写入口" in text


def test_old_propagation_owner_name_is_gone_from_active_routing_docs() -> None:
    for path in _active_routing_docs():
        assert "route-profile-and-propagation.md" not in path.read_text(encoding="utf-8")
