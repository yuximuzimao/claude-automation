from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data/timing/leatrix-flight-times.json"

FACTIONS = ("Horde", "Alliance")
LUA_PATH = "Leatrix_Plus/Leatrix_Plus_Flight_{faction}.lua"
TOC_PATH = "Leatrix_Plus/Leatrix_Plus.toc"
BUILD_PATH = "Leatrix_Plus/addon_version.txt"

TABLE_RE = re.compile(r"^\s*\[(\d+)\]\s*=\s*\{\s*$")
ROW_RE = re.compile(r'^\s*\["([^"]+)"\]\s*=\s*(\d+)\s*,\s*--\s*(.*)$')
VERSION_RE = re.compile(r"^##\s*Version:\s*(.+?)\s*$", re.MULTILINE)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_route_key(path_key: str) -> list[str]:
    parts = path_key.split(":")
    if len(parts) % 2:
        raise ValueError(f"invalid Leatrix path key: {path_key}")
    return [f"{parts[i]}:{parts[i + 1]}" for i in range(0, len(parts), 2)]


def _clean_comment_names(raw_comment: str, expected: int) -> list[str] | None:
    """Best-effort extraction used only to build a lookup index.

    The raw Leatrix comment is preserved verbatim for source fidelity. Some historical rows append
    reporter notes or duplicate localized names, so comments are never used as the timing key.
    """

    text = raw_comment.strip()
    # Most reporter notes are a trailing parenthesized suffix. Strip repeatedly, but never mutate
    # the preserved raw comment in the emitted route record.
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\s+\([^()]*\)\s*$", "", text)
    names = [part.strip() for part in text.split(",") if part.strip()]
    if len(names) == expected:
        return names
    # A small class of source rows repeats the final localized name once. Keep the unambiguous
    # prefix when dropping exactly one duplicate makes the arity match.
    if len(names) == expected + 1 and len(names) >= 2 and names[-1] == names[-2]:
        return names[:-1]
    return None


def parse_lua(text: str) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Counter[str]], list[dict[str, Any]]]:
    worlds: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    node_name_votes: dict[str, Counter[str]] = defaultdict(Counter)
    comment_warnings: list[dict[str, Any]] = []
    current_world: str | None = None

    for line_number, line in enumerate(text.splitlines(), 1):
        table = TABLE_RE.match(line)
        if table:
            current_world = table.group(1)
            continue
        row = ROW_RE.match(line)
        if not row:
            continue
        if current_world is None:
            raise ValueError(f"Leatrix route row before world table at line {line_number}")

        path_key, seconds_raw, raw_comment = row.groups()
        node_keys = parse_route_key(path_key)
        seconds = int(seconds_raw)
        if path_key in worlds[current_world]:
            raise ValueError(f"duplicate Leatrix route key in world {current_world}: {path_key}")

        names = _clean_comment_names(raw_comment, len(node_keys))
        if names is None:
            comment_warnings.append(
                {
                    "world_id": int(current_world),
                    "line": line_number,
                    "path_key": path_key,
                    "node_count": len(node_keys),
                    "raw_comment": raw_comment.strip(),
                }
            )
        else:
            for node_key, name in zip(node_keys, names, strict=True):
                node_name_votes[node_key][name] += 1

        worlds[current_world][path_key] = {
            "seconds": seconds,
            "raw_comment": raw_comment.strip(),
        }

    return dict(worlds), node_name_votes, comment_warnings


def build_payload(source_zip: Path) -> dict[str, Any]:
    source_bytes = source_zip.read_bytes()
    zip_sha = sha256_bytes(source_bytes)
    with zipfile.ZipFile(source_zip) as archive:
        toc_bytes = archive.read(TOC_PATH)
        build_bytes = archive.read(BUILD_PATH)
        toc_text = toc_bytes.decode("utf-8-sig", errors="strict")
        version_match = VERSION_RE.search(toc_text)
        if not version_match:
            raise ValueError("Leatrix version missing from toc")
        addon_version = version_match.group(1).strip()
        addon_build = build_bytes.decode("utf-8-sig", errors="strict").strip()

        factions: dict[str, Any] = {}
        total_routes = 0
        total_warnings = 0
        for faction in FACTIONS:
            member = LUA_PATH.format(faction=faction)
            lua_bytes = archive.read(member)
            worlds, votes, warnings = parse_lua(lua_bytes.decode("utf-8-sig", errors="strict"))
            total_routes += sum(len(routes) for routes in worlds.values())
            total_warnings += len(warnings)

            node_index: dict[str, Any] = {}
            for node_key, counter in sorted(votes.items()):
                ranked = counter.most_common()
                top_count = ranked[0][1]
                winners = sorted(name for name, count in ranked if count == top_count)
                node_index[node_key] = {
                    "preferred_name_en": winners[0] if len(winners) == 1 else None,
                    "name_votes": {name: count for name, count in ranked},
                }

            factions[faction] = {
                "source_member": member,
                "source_sha256": sha256_bytes(lua_bytes),
                "route_count": sum(len(routes) for routes in worlds.values()),
                "worlds": worlds,
                "node_index": node_index,
                "comment_warning_count": len(warnings),
                "comment_warnings": warnings,
            }

    return {
        "schema_version": 1,
        "source": {
            "addon": "Leatrix Plus",
            "addon_version": addon_version,
            "addon_build": addon_build,
            "zip_sha256": zip_sha,
            "toc_sha256": sha256_bytes(toc_bytes),
            "source_policy": "Converted project-owned timing input. Route seconds are authoritative to this imported source; comments/names are lookup metadata only.",
        },
        "summary": {
            "factions": len(FACTIONS),
            "route_count": total_routes,
            "comment_warning_count": total_warnings,
        },
        "factions": factions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Leatrix Plus static flight data into project-owned JSON.")
    parser.add_argument("--source", required=True, type=Path, help="Path to Leatrix_Plus.zip")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    payload = build_payload(args.source.expanduser().resolve())
    print(
        json.dumps(
            {
                "source": payload["source"],
                "summary": payload["summary"],
                "output": str(args.out),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
