from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "docs/rules"
SKILL = ROOT / "SKILL.md"
INDEX = ROOT / "docs/INDEX.md"
RULE_INDEX = RULES / "README.md"
ARCHIVED_SCRIPTS = ROOT / "docs/archive/scripts"


def _active_python_files() -> list[Path]:
    files = [*sorted((ROOT / "lib").rglob("*.py")), *sorted((ROOT / "scripts").rglob("*.py")), ROOT / "cli.py"]
    this_test = Path(__file__).resolve()
    files.extend(path for path in sorted((ROOT / "tests").glob("test_*.py")) if path.resolve() != this_test)
    return files


def test_every_permanent_child_rule_is_routed_from_all_active_entry_points() -> None:
    child_rules = sorted(path.name for path in RULES.glob("*.md") if path.name != "README.md")
    assert child_rules

    entry_texts = {
        "SKILL.md": SKILL.read_text(encoding="utf-8"),
        "docs/INDEX.md": INDEX.read_text(encoding="utf-8"),
        "docs/rules/README.md": RULE_INDEX.read_text(encoding="utf-8"),
    }

    for rule_name in child_rules:
        for entry_name, text in entry_texts.items():
            assert rule_name in text, f"{rule_name} is not routed from {entry_name}"


def test_archived_stage_scripts_cannot_reenter_active_python_paths() -> None:
    archived_names = {path.name for path in ARCHIVED_SCRIPTS.glob("*.py")}
    assert archived_names

    for path in _active_python_files():
        text = path.read_text(encoding="utf-8")
        assert "docs/archive/scripts" not in text, f"active code references archive script directory: {path.relative_to(ROOT)}"
        leaked_names = sorted(name for name in archived_names if name in text)
        assert not leaked_names, f"active code references archived stage scripts {leaked_names}: {path.relative_to(ROOT)}"
