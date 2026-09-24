from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .route_dependencies import ROOT


GENERATED_ROOT = ROOT / "data" / "generated" / "route-lifecycle"
MANIFEST_PATH = GENERATED_ROOT / "manifest.json"
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

PROFILE_ARTIFACT_OWNERS = {
    "replay": "route_replay",
    "movement": "route_movement",
    "service-context": "route_service_context",
    "timing": "route_timing",
    "xp": "route_xp",
    "economy": "route_economy",
    "review-trigger": "route_review_trigger",
    "display": "route_display",
    "publisher": "route_publisher_payload",
}
PROGRAM_ARTIFACT_OWNERS = {
    "continuity": "route_continuity",
    "movement": "route_movement",
    "service-context": "route_service_context",
    "timing": "route_timing",
    "xp": "route_xp",
    "economy": "route_economy",
    "review-trigger": "route_review_trigger",
}


class GeneratedArtifactError(RuntimeError):
    """Raised when a generated Route Lifecycle artifact is missing or tampered with."""


def _validate_identity(scope_kind: str, scope_id: str, artifact_kind: str, owner: str) -> None:
    if scope_kind not in {"profiles", "programs"}:
        raise GeneratedArtifactError(f"invalid generated artifact scope: {scope_kind}")
    if not _SAFE_ID_RE.fullmatch(scope_id):
        raise GeneratedArtifactError(f"unsafe generated artifact scope id: {scope_id!r}")
    owners = PROFILE_ARTIFACT_OWNERS if scope_kind == "profiles" else PROGRAM_ARTIFACT_OWNERS
    expected_owner = owners.get(artifact_kind)
    if expected_owner is None:
        raise GeneratedArtifactError(
            f"artifact kind {artifact_kind!r} is not registered for {scope_kind}"
        )
    if owner != expected_owner:
        raise GeneratedArtifactError(
            f"{scope_kind}/{scope_id}/{artifact_kind} must be written by {expected_owner}, got {owner}"
        )


def artifact_path(scope_kind: str, scope_id: str, artifact_kind: str) -> Path:
    owners = PROFILE_ARTIFACT_OWNERS if scope_kind == "profiles" else PROGRAM_ARTIFACT_OWNERS
    _validate_identity(scope_kind, scope_id, artifact_kind, owners.get(artifact_kind, ""))
    return GENERATED_ROOT / scope_kind / scope_id / f"{artifact_kind}.json"


def _manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {
            "schema_version": 1,
            "generated_only": True,
            "artifacts": {},
        }
    try:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GeneratedArtifactError("generated artifact manifest is unreadable") from exc
    if (
        payload.get("schema_version") != 1
        or payload.get("generated_only") is not True
        or not isinstance(payload.get("artifacts"), dict)
    ):
        raise GeneratedArtifactError("generated artifact manifest contract is invalid")
    return payload


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_bytes(data)
    temp.replace(path)


def write_generated_artifact(
    *,
    scope_kind: str,
    scope_id: str,
    artifact_kind: str,
    owner: str,
    payload: dict[str, Any],
) -> Path:
    """Write one disposable derived artifact through the single approved store.

    Generated artifacts are never authoritative business inputs. Downstream consumers must use
    read_generated_artifact so direct/manual edits are detected by the manifest hash.
    """

    _validate_identity(scope_kind, scope_id, artifact_kind, owner)
    if not isinstance(payload, dict):
        raise GeneratedArtifactError("generated artifact payload must be a JSON object")

    identity_key = "profile_id" if scope_kind == "profiles" else "program_id"
    payload_identity = payload.get(identity_key)
    if payload_identity is not None and str(payload_identity) != scope_id:
        raise GeneratedArtifactError(
            f"payload {identity_key}={payload_identity!r} does not match scope id {scope_id!r}"
        )

    path = artifact_path(scope_kind, scope_id, artifact_kind)
    data = _json_bytes(payload)
    _atomic_write(path, data)

    manifest = _manifest()
    relative = path.relative_to(GENERATED_ROOT).as_posix()
    manifest["artifacts"][relative] = {
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "artifact_kind": artifact_kind,
        "owner": owner,
        "sha256": _sha256(data),
        "input_fingerprint": payload.get("input_fingerprint"),
    }
    _atomic_write(MANIFEST_PATH, _json_bytes(manifest))
    return path


def read_generated_artifact(
    *,
    scope_kind: str,
    scope_id: str,
    artifact_kind: str,
) -> dict[str, Any]:
    """Read a current derived artifact and fail if it was edited outside the approved writer."""

    owners = PROFILE_ARTIFACT_OWNERS if scope_kind == "profiles" else PROGRAM_ARTIFACT_OWNERS
    owner = owners.get(artifact_kind, "")
    _validate_identity(scope_kind, scope_id, artifact_kind, owner)

    path = artifact_path(scope_kind, scope_id, artifact_kind)
    if not path.exists():
        raise GeneratedArtifactError(f"generated artifact missing: {path}")

    manifest = _manifest()
    relative = path.relative_to(GENERATED_ROOT).as_posix()
    record = manifest["artifacts"].get(relative)
    if not isinstance(record, dict):
        raise GeneratedArtifactError(f"generated artifact is not registered in manifest: {relative}")

    data = path.read_bytes()
    actual_hash = _sha256(data)
    if record.get("sha256") != actual_hash:
        raise GeneratedArtifactError(
            f"generated artifact hash mismatch for {relative}; direct/manual edits are forbidden"
        )
    if record.get("owner") != owner:
        raise GeneratedArtifactError(
            f"generated artifact owner mismatch for {relative}: {record.get('owner')!r}"
        )

    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeneratedArtifactError(f"generated artifact JSON invalid: {relative}") from exc
    if not isinstance(payload, dict):
        raise GeneratedArtifactError(f"generated artifact must contain a JSON object: {relative}")
    return payload
