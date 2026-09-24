from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from lib.route_dependencies import ROOT
from lib.route_final_audit import (
    PREREQUISITE_STAGE_ORDER,
    evaluate_profile_final_audit,
    evaluate_project_final_audit,
    load_cutover_blockers,
)


def _stages() -> list[dict]:
    rows = []
    for name in PREREQUISITE_STAGE_ORDER:
        detail = {"root_fingerprint": "root-v1"} if name == "dependency_fingerprint" else {}
        rows.append(
            {
                "name": name,
                "implementation_status": "implemented",
                "evaluation_status": "pass",
                "publish_gate_applies": True,
                "detail": detail,
            }
        )
    return rows


def _display() -> list[dict]:
    return [
        {
            "kind": "route_display",
            "profile_id": "audit-fixture",
            "profile_version": 2,
            "program_id": None,
            "status": "pass",
            "input_fingerprint": "display-v2",
        }
    ]


def _publisher() -> list[dict]:
    return [
        {
            "kind": "publisher_payload",
            "profile_id": "audit-fixture",
            "profile_version": 2,
            "program_id": None,
            "status": "pass",
            "publishable": True,
            "input_fingerprint": "publisher-v2",
            "stage11_input_fingerprint": "display-v2",
            "display": {"publish_key": "audit_fixture"},
        }
    ]


def _assets(text: str | None = None) -> dict:
    return {
        "kind": "player_assets",
        "status": "pass",
        "publishable": True,
        "input_fingerprint": "assets-v2",
        "publisher_fingerprints": ["publisher-v2"],
        "player_views": {
            "audit_fixture": text
            or "# 审计路线\n\n## 步骤 1｜起点\n- 起点\n- NPC → 接《测试任务》\n\n## 步骤 2｜终点\n- 终点\n- NPC → 交《测试任务》\n"
        },
    }


def _profile_audit(**overrides) -> dict:
    kwargs = {
        "profile_id": "audit-fixture",
        "profile_version": 2,
        "root_fingerprint": "root-v1",
        "prerequisite_stages": _stages(),
        "display_reports": _display(),
        "publisher_payloads": _publisher(),
        "player_assets_report": _assets(),
        "source_root": ROOT,
    }
    kwargs.update(overrides)
    return evaluate_profile_final_audit(**kwargs)


def test_profile_final_audit_passes_only_with_complete_fresh_single_source_chain() -> None:
    report = _profile_audit()
    assert report["status"] == "pass"
    assert report["publishable"] is True
    assert report["cutover_status"] == "pass"
    assert report["cutover_publishable"] is True
    assert report["mechanical_summary"] == {
        "prerequisite_stage_count": 13,
        "implemented_stage_count": 13,
        "blocked_stage_count": 0,
        "requirements_stage_count": 0,
        "active_consumer_count": 4,
    }
    assert report["issues"] == []
    assert report["cold_read"]["audit_fixture"]["step_action_line_counts"] == [
        {"step_heading": "## 步骤 1｜起点", "action_line_count": 2},
        {"step_heading": "## 步骤 2｜终点", "action_line_count": 2},
    ]


def test_profile_final_audit_preserves_blocked_requirements_and_cold_read_review() -> None:
    stages = _stages()
    stages[4]["evaluation_status"] = "blocked"
    stages[7]["evaluation_status"] = "requirements"
    long_view = "# 审计路线\n\n## 步骤 1｜过长段\n" + "\n".join(f"- 动作{i}" for i in range(1, 12)) + "\n已实测\n"
    assets = _assets(long_view)
    assets["status"] = "blocked"
    assets["publishable"] = False

    report = _profile_audit(prerequisite_stages=stages, player_assets_report=assets)
    kinds = [issue["kind"] for issue in report["issues"]]
    assert report["status"] == "blocked"
    assert report["publishable"] is False
    assert report["cutover_status"] == "blocked"
    assert report["cutover_publishable"] is False
    assert "final_audit_upstream_blocked" in kinds
    assert "final_audit_upstream_requirements" in kinds
    assert "cold_read_step_overlong_review" in kinds
    assert "cold_read_process_language" in kinds


def test_profile_final_audit_requirements_remain_diagnostic_but_do_not_block_cutover() -> None:
    stages = _stages()
    stages[6]["evaluation_status"] = "requirements"
    stages[7]["evaluation_status"] = "requirements"
    long_view = "# 审计路线\n\n## 步骤 1｜过长段\n" + "\n".join(f"- 动作{i}" for i in range(1, 12)) + "\n"
    report = _profile_audit(prerequisite_stages=stages, player_assets_report=_assets(long_view))
    assert report["status"] == "requirements"
    assert report["publishable"] is False
    assert report["cutover_status"] == "pass"
    assert report["cutover_publishable"] is True
    assert any(issue["kind"] == "cold_read_step_overlong_review" for issue in report["issues"])


def test_profile_final_audit_blocks_fingerprint_chain_mismatch() -> None:
    publisher = _publisher()
    publisher[0]["stage11_input_fingerprint"] = "stale-display"
    assets = _assets()
    assets["publisher_fingerprints"] = ["stale-publisher"]
    report = _profile_audit(publisher_payloads=publisher, player_assets_report=assets)
    kinds = {issue["kind"] for issue in report["issues"]}
    assert report["status"] == "blocked"
    assert "final_audit_stage11_stage12_fingerprint_mismatch" in kinds
    assert "final_audit_stage12_stage13_fingerprint_mismatch" in kinds


def test_profile_final_audit_fails_closed_on_stage_order_or_implementation_gap() -> None:
    stages = _stages()
    stages[1], stages[2] = stages[2], stages[1]
    stages[0]["implementation_status"] = "not_implemented"
    report = _profile_audit(prerequisite_stages=stages)
    kinds = {issue["kind"] for issue in report["issues"]}
    assert report["status"] == "blocked"
    assert "final_audit_stage_order_mismatch" in kinds
    assert "final_audit_stage_not_implemented" in kinds


def test_profile_final_audit_detects_legacy_consumer_reintroduced_into_active_chain(tmp_path: Path) -> None:
    for relative in (
        "scripts/rebuild_route_profile.py",
        "lib/route_display.py",
        "lib/route_publisher_payload.py",
        "lib/route_player_assets.py",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# clean\n", encoding="utf-8")
    (tmp_path / "lib/route_display.py").write_text('DATA="workbench-routes.json"\n', encoding="utf-8")
    registry = tmp_path / "scripts/README.md"
    registry.write_text("# current scripts\n", encoding="utf-8")
    legacy_writer = tmp_path / "scripts/legacy_writer.py"
    legacy_writer.write_text(
        'WORKBENCH="workbench-routes.json"\nWORKBENCH.write_text("bad")\n',
        encoding="utf-8",
    )
    report = _profile_audit(source_root=tmp_path)
    assert report["status"] == "blocked"
    assert any(
        issue["kind"] == "final_audit_active_legacy_consumer"
        and issue["path"] == "lib/route_display.py"
        and issue["token"] == "workbench-routes.json"
        for issue in report["issues"]
    )
    assert any(
        issue["kind"] == "final_audit_legacy_workbench_consumers_active"
        and issue["paths"] == ["scripts/legacy_writer.py"]
        for issue in report["issues"]
    )


def test_project_final_audit_requires_explicit_complete_profile_set() -> None:
    a = _profile_audit()
    b = deepcopy(a)
    b["profile_id"] = "audit-fixture-b"
    b["input_fingerprint"] = "audit-b"

    complete = evaluate_project_final_audit(
        [a, b],
        required_profile_ids=["audit-fixture", "audit-fixture-b"],
        cutover_blocker_ids=[],
    )
    assert complete["status"] == "pass"
    assert complete["cutover_status"] == "pass"
    assert complete["cutover_ready"] is True

    missing = evaluate_project_final_audit(
        [a],
        required_profile_ids=["audit-fixture", "audit-fixture-b"],
        cutover_blocker_ids=[],
    )
    assert missing["status"] == "requirements"
    assert missing["cutover_ready"] is False
    assert missing["issues"] == [
        {
            "severity": "requirement",
            "kind": "project_final_audit_profiles_missing",
            "profile_ids": ["audit-fixture-b"],
        }
    ]

    open_blocker = evaluate_project_final_audit(
        [a, b],
        required_profile_ids=["audit-fixture", "audit-fixture-b"],
        cutover_blocker_ids=["HD-test"],
    )
    assert open_blocker["status"] == "requirements"
    assert open_blocker["cutover_ready"] is False
    assert open_blocker["open_cutover_blocker_ids"] == ["HD-test"]
    assert open_blocker["issues"] == [
        {
            "severity": "requirement",
            "kind": "project_final_audit_todo_blockers_open",
            "blocker_ids": ["HD-test"],
        }
    ]


def test_cutover_blockers_are_loaded_from_unfinished_todo_items(tmp_path: Path) -> None:
    todo = tmp_path / "todo.md"
    todo.write_text(
        "# 当前待办\n"
        "- [ ] [CUTOVER-BLOCKER:HD-open] 未完成\n"
        "- [x] [CUTOVER-BLOCKER:HD-closed] 已完成\n"
        "- [ ] 普通待办\n",
        encoding="utf-8",
    )
    assert load_cutover_blockers(todo) == ["HD-open"]
