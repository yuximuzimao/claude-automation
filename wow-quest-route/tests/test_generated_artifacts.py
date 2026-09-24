from __future__ import annotations

from pathlib import Path

import pytest

import lib.generated_artifacts as store
from lib.generated_artifacts import GeneratedArtifactError


def _use_temp_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "route-lifecycle"
    monkeypatch.setattr(store, "GENERATED_ROOT", root)
    monkeypatch.setattr(store, "MANIFEST_PATH", root / "manifest.json")


def test_generated_store_round_trip_and_manifest_owner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    payload = {
        "kind": "route_display",
        "profile_id": "demo-profile",
        "input_fingerprint": "abc123",
        "steps": [],
    }

    path = store.write_generated_artifact(
        scope_kind="profiles",
        scope_id="demo-profile",
        artifact_kind="display",
        owner="route_display",
        payload=payload,
    )

    assert path.exists()
    assert store.read_generated_artifact(
        scope_kind="profiles",
        scope_id="demo-profile",
        artifact_kind="display",
    ) == payload

    manifest = store._manifest()
    record = manifest["artifacts"]["profiles/demo-profile/display.json"]
    assert record["owner"] == "route_display"
    assert record["input_fingerprint"] == "abc123"
    assert record["sha256"]


def test_direct_edit_is_rejected_on_next_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    path = store.write_generated_artifact(
        scope_kind="profiles",
        scope_id="demo-profile",
        artifact_kind="timing",
        owner="route_timing",
        payload={"kind": "profile", "profile_id": "demo-profile", "status": "pass"},
    )

    path.write_text('{"profile_id":"demo-profile","status":"manually-fixed"}\n', encoding="utf-8")

    with pytest.raises(GeneratedArtifactError, match="direct/manual edits are forbidden"):
        store.read_generated_artifact(
            scope_kind="profiles",
            scope_id="demo-profile",
            artifact_kind="timing",
        )


def test_wrong_owner_cannot_write_generated_artifact(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_store(monkeypatch, tmp_path)

    with pytest.raises(GeneratedArtifactError, match="must be written by route_timing"):
        store.write_generated_artifact(
            scope_kind="profiles",
            scope_id="demo-profile",
            artifact_kind="timing",
            owner="route_display",
            payload={"profile_id": "demo-profile"},
        )


def test_review_trigger_artifacts_have_a_single_registered_owner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    profile_payload = {
        "kind": "profile",
        "profile_id": "demo-profile",
        "target_id": "demo-profile",
        "status": "requirements",
        "input_fingerprint": "review-profile",
    }
    program_payload = {
        "kind": "program",
        "program_id": "demo-program",
        "target_id": "demo-program",
        "status": "requirements",
        "input_fingerprint": "review-program",
    }

    store.write_generated_artifact(
        scope_kind="profiles",
        scope_id="demo-profile",
        artifact_kind="review-trigger",
        owner="route_review_trigger",
        payload=profile_payload,
    )
    store.write_generated_artifact(
        scope_kind="programs",
        scope_id="demo-program",
        artifact_kind="review-trigger",
        owner="route_review_trigger",
        payload=program_payload,
    )

    assert store.read_generated_artifact(
        scope_kind="profiles", scope_id="demo-profile", artifact_kind="review-trigger"
    ) == profile_payload
    assert store.read_generated_artifact(
        scope_kind="programs", scope_id="demo-program", artifact_kind="review-trigger"
    ) == program_payload


def test_payload_identity_must_match_scope(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_store(monkeypatch, tmp_path)

    with pytest.raises(GeneratedArtifactError, match="does not match scope id"):
        store.write_generated_artifact(
            scope_kind="profiles",
            scope_id="demo-profile",
            artifact_kind="movement",
            owner="route_movement",
            payload={"profile_id": "another-profile"},
        )


def test_generated_store_path_literal_is_owned_only_by_store_module() -> None:
    root = Path(__file__).resolve().parents[1]
    literal = '"data" / "generated" / "route-lifecycle"'
    offenders: list[str] = []
    for base in (root / "lib", root / "scripts"):
        for path in base.glob("*.py"):
            if path.name == "generated_artifacts.py":
                continue
            if literal in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(root)))
    assert offenders == [], f"direct generated-store path ownership leaked: {offenders}"
