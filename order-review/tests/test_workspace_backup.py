import json
import os
from pathlib import Path
import subprocess


def _valid_cases() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "cases": [],
        "orderAssignments": [],
        "ruleStats": {},
    }


def _valid_event() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "eventId": "event-1",
        "occurredAt": "2026-07-23T01:00:00Z",
        "eventType": "shown",
        "applicationSessionId": "session-1",
        "orderSignature": "order-1",
        "recommendationId": "rule-1",
        "ruleId": "rule-1",
        "matchType": "exact_structure",
        "algorithmVersion": 1,
        "sourceCaseIds": ["case-1"],
    }


def test_workspace_backup_includes_cases_and_keeps_multiple_generations(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "marker.txt").write_text("workspace", encoding="utf-8")
    case_file = tmp_path / "application-support" / "cases.json"
    case_file.parent.mkdir()
    case_file.write_text(json.dumps(_valid_cases()), encoding="utf-8")
    event_file = tmp_path / "application-support" / "recommendation-events.jsonl"
    event_file.write_text(
        json.dumps(_valid_event(), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    backup_dir = tmp_path / "backups"
    project_root = Path(__file__).resolve().parents[2]
    script = project_root / "backup-workspace.sh"
    source_dir = project_root / "order-review" / "src"
    env = {
        **os.environ,
        "WORKSPACE_BACKUP_SOURCE_DIR": str(workspace),
        "WORKSPACE_BACKUP_DIR": str(backup_dir),
        "WORKSPACE_BACKUP_KEEP": "2",
        "ORDER_REVIEW_CASE_FILE": str(case_file),
        "ORDER_REVIEW_EVENT_FILE": str(event_file),
        "ORDER_REVIEW_HEALTH_FILE": str(backup_dir / "order-review-health.txt"),
        "ORDER_REVIEW_SOURCE_DIR": str(source_dir),
        "ORDER_REVIEW_PYTHON": os.environ.get(
            "ORDER_REVIEW_PYTHON",
            "/Users/chat/miniconda3/bin/python3.13",
        ),
    }

    for _ in range(3):
        subprocess.run([str(script)], env=env, check=True, capture_output=True)

    archives = sorted(backup_dir.glob("workspace-*.tar.gz"))
    assert len(archives) == 2
    listing = subprocess.run(
        ["tar", "tzf", str(archives[-1])],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert any(item.endswith("marker.txt") for item in listing)
    assert "order-review-data/cases.json" in listing
    assert "order-review-data/recommendation-events.jsonl" in listing
    assert "status=healthy" in (
        backup_dir / "order-review-health.txt"
    ).read_text(encoding="utf-8")


def test_workspace_backup_quarantines_invalid_cases_without_blocking_workspace(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "marker.txt").write_text("workspace survives", encoding="utf-8")
    case_file = tmp_path / "cases.json"
    case_file.write_text('{"schemaVersion":1,"cases":"broken"}', encoding="utf-8")
    application_backups = tmp_path / "application-backups"
    application_backups.mkdir()
    (application_backups / "cases-20260723T010000000000Z.json").write_text(
        json.dumps(_valid_cases()),
        encoding="utf-8",
    )
    backup_dir = tmp_path / "backups"
    project_root = Path(__file__).resolve().parents[2]
    script = project_root / "backup-workspace.sh"
    env = {
        **os.environ,
        "WORKSPACE_BACKUP_SOURCE_DIR": str(workspace),
        "WORKSPACE_BACKUP_DIR": str(backup_dir),
        "WORKSPACE_BACKUP_KEEP": "2",
        "ORDER_REVIEW_CASE_FILE": str(case_file),
        "ORDER_REVIEW_CASE_BACKUP_DIR": str(application_backups),
        "ORDER_REVIEW_EVENT_FILE": str(tmp_path / "missing-events.jsonl"),
        "ORDER_REVIEW_HEALTH_FILE": str(backup_dir / "order-review-health.txt"),
        "ORDER_REVIEW_SOURCE_DIR": str(project_root / "order-review" / "src"),
        "ORDER_REVIEW_PYTHON": os.environ.get(
            "ORDER_REVIEW_PYTHON",
            "/Users/chat/miniconda3/bin/python3.13",
        ),
    }

    result = subprocess.run(
        [str(script)],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 3
    assert "archived as cases.invalid.json" in result.stderr
    archives = sorted(backup_dir.glob("workspace-*.tar.gz"))
    assert len(archives) == 1
    listing = subprocess.run(
        ["tar", "tzf", str(archives[0])],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert any(item.endswith("marker.txt") for item in listing)
    assert "order-review-data/cases.invalid.json" in listing
    assert "order-review-data/cases.json" not in listing
    assert "order-review-data/ORDER_REVIEW_CASES_INVALID.txt" in listing
    assert (
        "order-review-data/valid-case-backups/"
        "cases-20260723T010000000000Z.json"
    ) in listing
    assert "status=degraded" in (
        backup_dir / "order-review-health.txt"
    ).read_text(encoding="utf-8")


def test_workspace_backup_marks_missing_cases_degraded_and_keeps_valid_backup(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "marker.txt").write_text("workspace survives", encoding="utf-8")
    case_file = tmp_path / "missing" / "cases.json"
    application_backups = tmp_path / "application-backups"
    application_backups.mkdir()
    valid_backup = application_backups / "pre-restore-20260724T010000000000Z.json"
    valid_backup.write_text(json.dumps(_valid_cases()), encoding="utf-8")
    backup_dir = tmp_path / "backups"
    project_root = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "WORKSPACE_BACKUP_SOURCE_DIR": str(workspace),
        "WORKSPACE_BACKUP_DIR": str(backup_dir),
        "ORDER_REVIEW_CASE_FILE": str(case_file),
        "ORDER_REVIEW_CASE_BACKUP_DIR": str(application_backups),
        "ORDER_REVIEW_EVENT_FILE": str(tmp_path / "missing-events.jsonl"),
        "ORDER_REVIEW_HEALTH_FILE": str(backup_dir / "order-review-health.txt"),
        "ORDER_REVIEW_SOURCE_DIR": str(project_root / "order-review" / "src"),
        "ORDER_REVIEW_PYTHON": os.environ.get(
            "ORDER_REVIEW_PYTHON",
            "/Users/chat/miniconda3/bin/python3.13",
        ),
    }

    result = subprocess.run(
        [str(project_root / "backup-workspace.sh")],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 3
    assert "cases not found" in result.stderr
    archive = next(backup_dir.glob("workspace-*.tar.gz"))
    listing = subprocess.run(
        ["tar", "tzf", str(archive)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert any(item.endswith("marker.txt") for item in listing)
    assert "order-review-data/cases.json" not in listing
    assert "order-review-data/ORDER_REVIEW_CASES_MISSING.txt" in listing
    assert (
        "order-review-data/valid-case-backups/"
        "pre-restore-20260724T010000000000Z.json"
    ) in listing
    marker = subprocess.run(
        [
            "tar",
            "xOzf",
            str(archive),
            "order-review-data/ORDER_REVIEW_CASES_MISSING.txt",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "正式 cases.json 不存在" in marker
    assert "附带有效应用内备份：1" in marker
    assert "status=degraded" in (
        backup_dir / "order-review-health.txt"
    ).read_text(encoding="utf-8")


def test_workspace_backup_uses_newest_valid_backup_across_prefixes(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "marker.txt").write_text("workspace", encoding="utf-8")
    case_file = tmp_path / "cases.json"
    case_file.write_text('{"schemaVersion":1,"cases":"broken"}', encoding="utf-8")
    application_backups = tmp_path / "application-backups"
    application_backups.mkdir()
    older_restore = application_backups / (
        "pre-restore-20260724T120000000000Z.json"
    )
    newer_cases = application_backups / "cases-20260724T130000000000Z.json"
    older_restore.write_text(json.dumps(_valid_cases()), encoding="utf-8")
    newer_cases.write_text(json.dumps(_valid_cases()), encoding="utf-8")
    backup_dir = tmp_path / "backups"
    project_root = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "WORKSPACE_BACKUP_SOURCE_DIR": str(workspace),
        "WORKSPACE_BACKUP_DIR": str(backup_dir),
        "ORDER_REVIEW_CASE_FILE": str(case_file),
        "ORDER_REVIEW_CASE_BACKUP_DIR": str(application_backups),
        "ORDER_REVIEW_CASE_BACKUP_INCLUDE": "1",
        "ORDER_REVIEW_EVENT_FILE": str(tmp_path / "missing-events.jsonl"),
        "ORDER_REVIEW_SOURCE_DIR": str(project_root / "order-review" / "src"),
        "ORDER_REVIEW_PYTHON": os.environ.get(
            "ORDER_REVIEW_PYTHON",
            "/Users/chat/miniconda3/bin/python3.13",
        ),
    }

    result = subprocess.run(
        [str(project_root / "backup-workspace.sh")],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 3
    archive = next(backup_dir.glob("workspace-*.tar.gz"))
    listing = subprocess.run(
        ["tar", "tzf", str(archive)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert (
        "order-review-data/valid-case-backups/"
        "cases-20260724T130000000000Z.json"
    ) in listing
    assert (
        "order-review-data/valid-case-backups/"
        "pre-restore-20260724T120000000000Z.json"
    ) not in listing


def test_workspace_backup_marks_invalid_events_as_degraded(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "marker.txt").write_text("workspace", encoding="utf-8")
    case_file = tmp_path / "cases.json"
    case_file.write_text(json.dumps(_valid_cases()), encoding="utf-8")
    event_file = tmp_path / "recommendation-events.jsonl"
    event_file.write_text("{broken event}\n", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    project_root = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "WORKSPACE_BACKUP_SOURCE_DIR": str(workspace),
        "WORKSPACE_BACKUP_DIR": str(backup_dir),
        "ORDER_REVIEW_CASE_FILE": str(case_file),
        "ORDER_REVIEW_EVENT_FILE": str(event_file),
        "ORDER_REVIEW_SOURCE_DIR": str(project_root / "order-review" / "src"),
        "ORDER_REVIEW_PYTHON": os.environ.get(
            "ORDER_REVIEW_PYTHON",
            "/Users/chat/miniconda3/bin/python3.13",
        ),
    }

    result = subprocess.run(
        [str(project_root / "backup-workspace.sh")],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 3
    archive = next(backup_dir.glob("workspace-*.tar.gz"))
    listing = subprocess.run(
        ["tar", "tzf", str(archive)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert "order-review-data/recommendation-events.invalid.jsonl" in listing
    assert "order-review-data/ORDER_REVIEW_EVENTS_INVALID.txt" in listing
