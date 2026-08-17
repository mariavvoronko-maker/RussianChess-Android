from __future__ import annotations

from .model import BoardState, Color, Piece, PieceType, Square


BACK_RANK = (
    PieceType.ROOK,
    PieceType.KNIGHT,
    PieceType.BISHOP,
    PieceType.QUEEN,
    PieceType.KING,
    PieceType.BISHOP,
    PieceType.KNIGHT,
    PieceType.ROOK,
)


def initial_state() -> BoardState:
    pieces: dict[int, Piece] = {}
    board: dict[Square, int] = {}
    pid = 1
    for color, back_rank, pawn_rank in (
        (Color.WHITE, 0, 1),
        (Color.BLACK, 7, 6),
    ):
        for file_idx, kind in enumerate(BACK_RANK):
            piece = Piece(pid, color, kind, (file_idx, back_rank), False)
            pieces[pid] = piece
            board[piece.square] = pid
            pid += 1
        for file_idx in range(8):
            piece = Piece(pid, color, PieceType.PAWN, (file_idx, pawn_rank), False)
            pieces[pid] = piece
            board[piece.square] = pid
            pid += 1
    state = BoardState(pieces=pieces, board=board, next_piece_id=pid)
    from .rules import position_key

    state.position_history.append(position_key(state))
    return state


def empty_state(side_to_move: Color = Color.WHITE) -> BoardState:
    return BoardState(pieces={}, board={}, side_to_move=side_to_move, next_piece_id=1)


def add_piece(
    state: BoardState,
    color: Color,
    kind: PieceType,
    square: Square,
    *,
    has_moved: bool = False,
    piece_id: int | None = None,
) -> Piece:
    if square in state.board:
        raise ValueError(f"Square {square} is occupied")
    pid = state.next_piece_id if piece_id is None else piece_id
    if pid in state.pieces:
        raise ValueError(f"Duplicate piece id {pid}")
    piece = Piece(pid, color, kind, square, has_moved)
    state.pieces[pid] = piece
    state.board[square] = pid
    state.next_piece_id = max(state.next_piece_id, pid + 1)
    return piece
