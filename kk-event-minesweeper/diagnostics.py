from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from solver import CellKind, SolveResult
from vision import Recognition

_KIND_CHAR = {
    CellKind.COVERED: "#",
    CellKind.FLAG_BOMB: "!",
    CellKind.REVEALED_KBAO: "K",
    CellKind.OPEN_EMPTY: ".",
    CellKind.CLUE_BOMB: "R",
    CellKind.CLUE_KBAO: "B",
    CellKind.CLUE_TOTAL: "Y",
}


def write_diagnostics(
    out_dir: Path,
    image_bgr: np.ndarray,
    recognition: Recognition,
    result: SolveResult | None,
) -> tuple[Path, Path]:
    """Persist the exact screenshot and a compact recognition map for support."""
    out_dir.mkdir(parents=True, exist_ok=True)
    image_path = out_dir / "last_board.png"
    text_path = out_dir / "last_recognition.txt"
    cv2.imwrite(str(image_path), image_bgr)

    lines: list[str] = []
    lines.append(f"confidence={recognition.confidence:.6f}")
    lines.append(f"unknown_cells={list(recognition.unknown_cells)}")
    if result is not None:
        lines.append(f"safe={sorted(result.safe)}")
        lines.append(f"bombs={sorted(result.bombs)}")
        lines.append(f"kbaos={sorted(result.kbaos)}")
        lines.append(f"uncertain_count={len(result.uncertain)}")
    lines.append("")
    lines.append("legend: # covered, ! bomb flag, K revealed Kbao, . empty, R/B/Y clue")

    for r, row in enumerate(recognition.board):
        parts: list[str] = []
        for cell in row:
            ch = _KIND_CHAR[cell.kind]
            if cell.value is not None:
                parts.append(f"{ch}{cell.value}")
            else:
                parts.append(f"{ch} ")
        lines.append(f"{r + 1:02d} " + " ".join(parts))

    text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return image_path, text_path
