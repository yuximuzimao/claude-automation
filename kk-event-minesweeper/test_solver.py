from solver import Cell, CellKind, solve_board


def c(kind, value=None):
    return Cell(kind, value)


def test_red_zero_makes_neighbor_safe():
    board = [
        [c(CellKind.CLUE_BOMB, 0), c(CellKind.COVERED)],
        [c(CellKind.OPEN_EMPTY), c(CellKind.OPEN_EMPTY)],
    ]
    result = solve_board(board, total_bombs=None, total_kbaos=None)
    assert result.safe == {(0, 1)}
    assert result.bombs == frozenset()


def test_flagged_bomb_satisfies_red_one():
    board = [
        [c(CellKind.CLUE_BOMB, 1), c(CellKind.FLAG_BOMB)],
        [c(CellKind.OPEN_EMPTY), c(CellKind.COVERED)],
    ]
    result = solve_board(board, total_bombs=None, total_kbaos=None)
    assert (1, 1) in result.safe
    assert not result.bombs


def test_blue_one_forces_kbao():
    board = [
        [c(CellKind.CLUE_KBAO, 1), c(CellKind.COVERED)],
        [c(CellKind.OPEN_EMPTY), c(CellKind.OPEN_EMPTY)],
    ]
    result = solve_board(board, total_bombs=None, total_kbaos=None)
    assert result.safe == {(0, 1)}
    assert result.kbaos == {(0, 1)}


def test_blue_clue_makes_all_covered_neighbors_safe_even_when_kbao_identity_unknown():
    board = [
        [c(CellKind.CLUE_KBAO, 1), c(CellKind.COVERED)],
        [c(CellKind.OPEN_EMPTY), c(CellKind.COVERED)],
    ]
    result = solve_board(board, total_bombs=None, total_kbaos=None)
    assert result.safe == {(0, 1), (1, 1)}
    assert result.kbaos == frozenset()
    assert result.bombs == frozenset()


def test_yellow_two_with_known_kbao_forces_remaining_object_to_bomb():
    board = [
        [c(CellKind.CLUE_TOTAL, 2), c(CellKind.REVEALED_KBAO)],
        [c(CellKind.COVERED), c(CellKind.OPEN_EMPTY)],
    ]
    result = solve_board(board, total_bombs=None, total_kbaos=None)
    assert result.bombs == {(1, 0)}
    assert result.safe == frozenset()


def test_yellow_two_with_known_bomb_forces_remaining_object_to_kbao():
    board = [
        [c(CellKind.CLUE_TOTAL, 2), c(CellKind.FLAG_BOMB)],
        [c(CellKind.COVERED), c(CellKind.OPEN_EMPTY)],
    ]
    result = solve_board(board, total_bombs=None, total_kbaos=None)
    assert result.safe == {(1, 0)}
    assert result.kbaos == {(1, 0)}
    assert result.bombs == frozenset()


def test_ambiguous_pair_stays_unmarked():
    board = [
        [c(CellKind.CLUE_BOMB, 1), c(CellKind.COVERED)],
        [c(CellKind.OPEN_EMPTY), c(CellKind.COVERED)],
    ]
    result = solve_board(board, total_bombs=None, total_kbaos=None)
    assert result.safe == frozenset()
    assert result.bombs == frozenset()
    assert result.uncertain == {(0, 1), (1, 1)}


def test_non_frontier_cells_are_never_false_positive():
    board = [[c(CellKind.COVERED) for _ in range(4)] for _ in range(4)]
    board[0][0] = c(CellKind.CLUE_BOMB, 0)
    result = solve_board(board, total_bombs=1, total_kbaos=1)
    assert {(0, 1), (1, 0), (1, 1)} <= result.safe
    assert (3, 3) in result.uncertain


def test_endgame_global_count_can_force_remote_kbao():
    board = [
        [c(CellKind.OPEN_EMPTY), c(CellKind.OPEN_EMPTY)],
        [c(CellKind.OPEN_EMPTY), c(CellKind.COVERED)],
    ]
    result = solve_board(board, total_bombs=0, total_kbaos=1)
    assert result.safe == {(1, 1)}
    assert result.kbaos == {(1, 1)}


if __name__ == "__main__":
    test_red_zero_makes_neighbor_safe()
    test_flagged_bomb_satisfies_red_one()
    test_blue_one_forces_kbao()
    test_blue_clue_makes_all_covered_neighbors_safe_even_when_kbao_identity_unknown()
    test_yellow_two_with_known_kbao_forces_remaining_object_to_bomb()
    test_yellow_two_with_known_bomb_forces_remaining_object_to_kbao()
    test_ambiguous_pair_stays_unmarked()
    test_non_frontier_cells_are_never_false_positive()
    test_endgame_global_count_can_force_remote_kbao()
    print("solver tests passed")
