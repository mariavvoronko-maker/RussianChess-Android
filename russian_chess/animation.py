from __future__ import annotations

from dataclasses import dataclass

from .model import BoardState, CompoundMove, Square


@dataclass(frozen=True, slots=True)
class VisualMoveStep:
    piece_id: int
    from_square: Square
    to_square: Square
    target_friendly_piece_id: int | None = None
    captured_piece_id: int | None = None
    captured_square: Square | None = None

    @property
    def is_transfer(self) -> bool:
        return self.target_friendly_piece_id is not None


@dataclass(frozen=True, slots=True)
class StagedTransfer:
    piece_id: int
    square: Square


def is_cycle_move(move: CompoundMove) -> bool:
    return (
        not move.is_castling
        and bool(move.links)
        and move.final_destination == move.links[0].from_square
    )


def build_visual_steps(state: BoardState, move: CompoundMove) -> list[VisualMoveStep]:
    if move.is_castling:
        king_link = move.links[0]
        king = state.pieces[king_link.piece_id]
        home_rank = 0 if king.color.value == "white" else 7
        rook_from = (7, home_rank) if king_link.to_square[0] == 6 else (0, home_rank)
        rook_to = (5, home_rank) if king_link.to_square[0] == 6 else (3, home_rank)
        rook_id = state.board[rook_from]
        return [
            VisualMoveStep(king.id, king_link.from_square, king_link.to_square),
            VisualMoveStep(rook_id, rook_from, rook_to),
        ]

    steps: list[VisualMoveStep] = []
    for link in move.links:
        captured_id = link.captured_piece_id
        captured_square = None
        if captured_id is not None:
            captured_square = state.pieces[captured_id].square
        steps.append(
            VisualMoveStep(
                piece_id=link.piece_id,
                from_square=link.from_square,
                to_square=link.to_square,
                target_friendly_piece_id=link.target_friendly_piece_id,
                captured_piece_id=captured_id,
                captured_square=captured_square,
            )
        )
    return steps


def begin_visual_step(
    board: dict[Square, int],
    step: VisualMoveStep,
    staged: StagedTransfer | None,
) -> tuple[dict[Square, int], StagedTransfer | None]:
    updated = dict(board)
    if staged is not None:
        if staged.square != step.from_square:
            raise ValueError("Staged transfer does not match next step origin")
        updated.pop(step.from_square, None)
        updated[step.from_square] = staged.piece_id
        staged = None
    else:
        if updated.get(step.from_square) == step.piece_id:
            updated.pop(step.from_square, None)
    return updated, staged


def finish_visual_step(
    board: dict[Square, int],
    step: VisualMoveStep,
) -> tuple[dict[Square, int], StagedTransfer | None]:
    updated = dict(board)
    if step.is_transfer:
        return updated, StagedTransfer(step.piece_id, step.to_square)

    if step.captured_square is not None:
        updated.pop(step.captured_square, None)
    updated[step.to_square] = step.piece_id
    return updated, None


def apply_visual_step(board: dict[Square, int], step: VisualMoveStep) -> dict[Square, int]:
    if step.is_transfer:
        raise ValueError("Transfer steps must use begin_visual_step/finish_visual_step")
    updated, staged = begin_visual_step(board, step, None)
    updated, staged = finish_visual_step(updated, step)
    if staged is not None:
        raise AssertionError("Unexpected staged transfer")
    return updated


def board_after_visual_steps(state: BoardState, move: CompoundMove) -> dict[Square, int]:
    board = dict(state.board)
    staged: StagedTransfer | None = None
    for step in build_visual_steps(state, move):
        board, staged = begin_visual_step(board, step, staged)
        board, staged = finish_visual_step(board, step)
    if staged is not None:
        raise AssertionError("A complete move cannot end with an unfinished transfer")
    return board
