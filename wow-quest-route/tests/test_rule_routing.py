from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "docs/rules"
SKILL = ROOT / "SKILL.md"
INDEX = ROOT / "docs/INDEX.md"
RULE_INDEX = RULES / "README.md"


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
