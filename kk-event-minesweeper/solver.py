from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from z3 import Bool, If, Solver, Sum, is_true, sat


class CellKind(str, Enum):
    COVERED = "covered"
    FLAG_BOMB = "flag_bomb"
    REVEALED_KBAO = "revealed_kbao"
    OPEN_EMPTY = "open_empty"
    CLUE_BOMB = "clue_bomb"      # red
    CLUE_KBAO = "clue_kbao"      # blue
    CLUE_TOTAL = "clue_total"    # yellow: bomb + kbao


@dataclass(frozen=True)
class Cell:
    kind: CellKind
    value: int | None = None


@dataclass(frozen=True)
class SolveResult:
    safe: frozenset[tuple[int, int]]
    bombs: frozenset[tuple[int, int]]
    kbaos: frozenset[tuple[int, int]]
    uncertain: frozenset[tuple[int, int]]


def _neighbors(rows: int, cols: int, r: int, c: int) -> Iterable[tuple[int, int]]:
    for rr in range(max(0, r - 1), min(rows, r + 2)):
        for cc in range(max(0, c - 1), min(cols, c + 2)):
            if rr != r or cc != c:
                yield rr, cc


def solve_board(
    board: list[list[Cell]],
    *,
    total_bombs: int | None = 26,
    total_kbaos: int | None = 38,
) -> SolveResult:
    """Return only conclusions that are true in every legal solution.

    `safe` means definitely not a bomb and can therefore be left-clicked.
    `bombs` means definitely a bomb and should be right-clicked.
    `kbaos` is a subset of safe cells that are definitely K宝.

    Normally only covered cells touching a revealed clue are queried for certainty.
    In the endgame, when few covered cells remain, every covered cell is queried so
    the global remaining K宝 / bomb counts can resolve positions that local clues
    alone cannot. This keeps early-game solving fast without throwing away endgame
    count information.
    """
    rows = len(board)
    if rows == 0:
        raise ValueError("empty board")
    cols = len(board[0])
    if any(len(row) != cols for row in board):
        raise ValueError("ragged board")

    s = Solver()
    bomb: dict[tuple[int, int], object] = {}
    kbao: dict[tuple[int, int], object] = {}

    for r in range(rows):
        for c in range(cols):
            cell = board[r][c]
            b = Bool(f"b_{r}_{c}")
            k = Bool(f"k_{r}_{c}")
            bomb[r, c] = b
            kbao[r, c] = k
            s.add(If(b, 1, 0) + If(k, 1, 0) <= 1)

            if cell.kind == CellKind.COVERED:
                pass
            elif cell.kind == CellKind.FLAG_BOMB:
                s.add(b)
                s.add(~k)
            elif cell.kind == CellKind.REVEALED_KBAO:
                s.add(~b)
                s.add(k)
            else:
                s.add(~b)
                s.add(~k)

    clue_positions: list[tuple[int, int]] = []
    for r in range(rows):
        for c in range(cols):
            cell = board[r][c]
            if cell.kind not in {
                CellKind.CLUE_BOMB,
                CellKind.CLUE_KBAO,
                CellKind.CLUE_TOTAL,
            }:
                continue
            clue_positions.append((r, c))
            if cell.value is None:
                raise ValueError(f"missing clue value at {(r, c)}")

            ns = list(_neighbors(rows, cols, r, c))
            if cell.kind == CellKind.CLUE_BOMB:
                # Red clue means this neighborhood contains bombs only (no K宝).
                s.add(Sum([If(bomb[p], 1, 0) for p in ns]) == cell.value)
                s.add(Sum([If(kbao[p], 1, 0) for p in ns]) == 0)
            elif cell.kind == CellKind.CLUE_KBAO:
                # Blue clue means this neighborhood contains K宝 only (no bombs),
                # so every still-covered neighbor is immediately safe to left-click.
                s.add(Sum([If(kbao[p], 1, 0) for p in ns]) == cell.value)
                s.add(Sum([If(bomb[p], 1, 0) for p in ns]) == 0)
            else:
                # Yellow clue means both object types are present in this neighborhood,
                # and the displayed number is their combined total.
                bomb_sum = Sum([If(bomb[p], 1, 0) for p in ns])
                kbao_sum = Sum([If(kbao[p], 1, 0) for p in ns])
                s.add(bomb_sum + kbao_sum == cell.value)
                s.add(bomb_sum >= 1)
                s.add(kbao_sum >= 1)

    if total_bombs is not None:
        s.add(Sum([If(v, 1, 0) for v in bomb.values()]) == total_bombs)
    if total_kbaos is not None:
        s.add(Sum([If(v, 1, 0) for v in kbao.values()]) == total_kbaos)

    if s.check() != sat:
        raise ValueError("board recognition/constraints are inconsistent")

    covered = {
        (r, c)
        for r in range(rows)
        for c in range(cols)
        if board[r][c].kind == CellKind.COVERED
    }
    frontier = {
        p
        for clue in clue_positions
        for p in _neighbors(rows, cols, *clue)
        if p in covered
    }

    # Local clues are enough for most of the board. Near the end, however, the
    # global totals can force cells that are not adjacent to any currently visible
    # clue. Query all remaining covered cells once the board is small enough.
    query_cells = covered if len(covered) <= 48 else frontier

    safe: set[tuple[int, int]] = set()
    bombs: set[tuple[int, int]] = set()
    kbaos: set[tuple[int, int]] = set()
    base_model = s.model()

    def opposite_possible(expr, base_value: bool) -> bool:
        s.push()
        s.add(~expr if base_value else expr)
        ok = s.check() == sat
        s.pop()
        return ok

    for p in query_cells:
        base_is_bomb = is_true(base_model.eval(bomb[p], model_completion=True))
        if opposite_possible(bomb[p], base_is_bomb):
            continue

        if base_is_bomb:
            bombs.add(p)
            continue

        safe.add(p)
        base_is_kbao = is_true(base_model.eval(kbao[p], model_completion=True))
        if not opposite_possible(kbao[p], base_is_kbao) and base_is_kbao:
            kbaos.add(p)

    return SolveResult(
        safe=frozenset(safe),
        bombs=frozenset(bombs),
        kbaos=frozenset(kbaos),
        uncertain=frozenset(covered - safe - bombs),
    )
