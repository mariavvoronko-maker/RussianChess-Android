from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


Square = tuple[int, int]  # file 0..7, rank 0..7 (rank 0 is White's home rank)


class Color(str, Enum):
    WHITE = "white"
    BLACK = "black"

    @property
    def opposite(self) -> "Color":
        return Color.BLACK if self is Color.WHITE else Color.WHITE


class PieceType(str, Enum):
    KING = "king"
    QUEEN = "queen"
    ROOK = "rook"
    BISHOP = "bishop"
    KNIGHT = "knight"
    PAWN = "pawn"


TRANSFER_CAPABLE = {
    PieceType.QUEEN,
    PieceType.ROOK,
    PieceType.BISHOP,
    PieceType.KNIGHT,
}

PROMOTION_TYPES = (
    PieceType.QUEEN,
    PieceType.ROOK,
    PieceType.BISHOP,
    PieceType.KNIGHT,
)


@dataclass(slots=True)
class Piece:
    id: int
    color: Color
    kind: PieceType
    square: Square | None
    has_moved: bool = False

    def clone(self) -> "Piece":
        return Piece(self.id, self.color, self.kind, self.square, self.has_moved)


@dataclass(frozen=True, slots=True)
class ChainLink:
    piece_id: int
    from_square: Square
    to_square: Square
    target_friendly_piece_id: int | None = None
    captured_piece_id: int | None = None
    promotion: PieceType | None = None
    is_en_passant: bool = False
    is_castling: bool = False

    @property
    def is_transfer(self) -> bool:
        return self.target_friendly_piece_id is not None

    @property
    def is_final(self) -> bool:
        return not self.is_transfer


@dataclass(frozen=True, slots=True)
class CompoundMove:
    color: Color
    links: tuple[ChainLink, ...]
    used_piece_ids: frozenset[int]
    final_destination: Square
    captured_piece_id: int | None = None
    promotion: PieceType | None = None
    is_castling: bool = False
    is_en_passant: bool = False

    @property
    def first_piece_id(self) -> int:
        return self.links[0].piece_id

    @property
    def last_link(self) -> ChainLink:
        return self.links[-1]

    @property
    def is_capture(self) -> bool:
        return self.captured_piece_id is not None

    def destination_sequence(self) -> tuple[Square, ...]:
        return tuple(link.to_square for link in self.links)


@dataclass(slots=True)
class BoardState:
    pieces: dict[int, Piece]
    board: dict[Square, int]
    side_to_move: Color = Color.WHITE
    en_passant_target: Square | None = None
    en_passant_pawn_id: int | None = None
    halfmove_clock: int = 0
    fullmove_number: int = 1
    position_history: list[str] = field(default_factory=list)
    move_notation_history: list[str] = field(default_factory=list)
    next_piece_id: int = 33

    def clone(self) -> "BoardState":
        return BoardState(
            pieces={pid: piece.clone() for pid, piece in self.pieces.items()},
            board=dict(self.board),
            side_to_move=self.side_to_move,
            en_passant_target=self.en_passant_target,
            en_passant_pawn_id=self.en_passant_pawn_id,
            halfmove_clock=self.halfmove_clock,
            fullmove_number=self.fullmove_number,
            position_history=list(self.position_history),
            move_notation_history=list(self.move_notation_history),
            next_piece_id=self.next_piece_id,
        )

    def piece_at(self, square: Square) -> Piece | None:
        pid = self.board.get(square)
        return self.pieces.get(pid) if pid is not None else None

    def king(self, color: Color) -> Piece:
        for piece in self.pieces.values():
            if (
                piece.square is not None
                and piece.color is color
                and piece.kind is PieceType.KING
            ):
                return piece
        raise ValueError(f"No {color.value} king on board")

    def living_pieces(self, color: Color | None = None) -> Iterable[Piece]:
        for piece in self.pieces.values():
            if piece.square is None:
                continue
            if color is None or piece.color is color:
                yield piece

    def validate(self) -> None:
        occupied: dict[Square, int] = {}
        king_counts = {Color.WHITE: 0, Color.BLACK: 0}
        for pid, piece in self.pieces.items():
            if piece.id != pid:
                raise ValueError(
                    f"Piece dictionary key {pid} does not match piece.id {piece.id}"
                )
            if piece.square is None:
                continue
            if not on_board(piece.square):
                raise ValueError(f"Piece {pid} is outside the board: {piece.square}")
            if piece.square in occupied:
                raise ValueError(
                    f"Two pieces on {piece.square}: {occupied[piece.square]} and {pid}"
                )
            occupied[piece.square] = pid
            if piece.kind is PieceType.KING:
                king_counts[piece.color] += 1
        if occupied != self.board:
            raise ValueError("Board mapping and piece squares are inconsistent")
        if king_counts != {Color.WHITE: 1, Color.BLACK: 1}:
            raise ValueError(
                f"A valid game needs exactly one king of each color: {king_counts}"
            )
        if self.en_passant_target is not None:
            if (
                not on_board(self.en_passant_target)
                or self.en_passant_target in self.board
            ):
                raise ValueError("Invalid en passant target")
            if self.en_passant_pawn_id is None:
                raise ValueError("En passant target has no pawn id")
        if self.en_passant_pawn_id is not None:
            pawn = self.pieces.get(self.en_passant_pawn_id)
            if pawn is None or pawn.square is None or pawn.kind is not PieceType.PAWN:
                raise ValueError("Invalid en passant pawn")
            if pawn.color is not self.side_to_move.opposite:
                raise ValueError(
                    "En passant pawn must belong to the side that moved last"
                )


def on_board(square: Square) -> bool:
    return 0 <= square[0] < 8 and 0 <= square[1] < 8


FILES = "abcdefgh"


def square_name(square: Square) -> str:
    return f"{FILES[square[0]]}{square[1] + 1}"


def parse_square(name: str) -> Square:
    if len(name) != 2 or name[0] not in FILES or name[1] not in "12345678":
        raise ValueError(f"Invalid square: {name}")
    return FILES.index(name[0]), int(name[1]) - 1


PIECE_LETTERS = {
    PieceType.KING: "K",
    PieceType.QUEEN: "Q",
    PieceType.ROOK: "R",
    PieceType.BISHOP: "B",
    PieceType.KNIGHT: "N",
    PieceType.PAWN: "P",
}
