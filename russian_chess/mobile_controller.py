from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .model import BoardState, Color, CompoundMove, PieceType, Square, square_name
from .notation import move_to_notation
from .persistence import load_game_session, save_game_session
from .rules import apply_move, game_result, generate_legal_moves, geometric_targets, in_check
from .setup import initial_state
from .timeline import GameTimeline

PIECE_NAMES = {
    PieceType.KING: "король",
    PieceType.QUEEN: "ферзь",
    PieceType.ROOK: "ладья",
    PieceType.BISHOP: "слон",
    PieceType.KNIGHT: "конь",
    PieceType.PAWN: "пешка",
}


@dataclass(slots=True)
class TapResult:
    kind: str
    move: CompoundMove | None = None
    promotion_moves: tuple[CompoundMove, ...] = ()


class MobileGameController:
    """UI-agnostic controller used by the Android/Kivy frontend."""

    def __init__(self) -> None:
        self.state: BoardState = initial_state()
        self.timeline = GameTimeline.from_state(self.state)
        self.legal_moves: list[CompoundMove] = generate_legal_moves(self.state)
        self.mode = "ai"
        self.difficulty = "medium"
        self.human_color = Color.WHITE
        self.status_message = "Белые начинают"
        self.selected_piece_id: int | None = None
        self.prefix: list[Square] = []
        self.candidates: list[CompoundMove] = []

    def new_game(self, *, mode: str = "ai", difficulty: str = "medium") -> None:
        if mode not in {"ai", "local"}:
            raise ValueError("Unsupported game mode")
        if difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("Unsupported difficulty")
        self.state = initial_state()
        self.timeline.reset(self.state)
        self.mode = mode
        self.difficulty = difficulty
        self.legal_moves = generate_legal_moves(self.state)
        self.cancel_chain()
        self.status_message = "Белые начинают"

    @property
    def is_reviewing(self) -> bool:
        return self.timeline.is_reviewing

    @property
    def can_review_back(self) -> bool:
        return self.timeline.can_back

    @property
    def can_review_forward(self) -> bool:
        return self.timeline.can_forward

    def is_human_turn(self) -> bool:
        if self.timeline.is_reviewing:
            return False
        return self.mode == "local" or self.state.side_to_move is self.human_color

    def tap_square(self, square: Square) -> TapResult:
        if self.timeline.is_reviewing or not self.is_human_turn() or game_result(self.state):
            return TapResult("blocked")

        if self.selected_piece_id is None:
            piece = self.state.piece_at(square)
            if piece is None or piece.color is not self.state.side_to_move:
                return TapResult("ignored")
            candidates = [m for m in self.legal_moves if m.first_piece_id == piece.id]
            if not candidates:
                self.status_message = "У этой фигуры нет законных полных ходов"
                return TapResult("unavailable")
            self.selected_piece_id = piece.id
            self.candidates = candidates
            self.prefix = []
            self.status_message = f"Выбрана: {PIECE_NAMES[piece.kind]} {square_name(square)}"
            return TapResult("selected")

        depth = len(self.prefix)
        matching = [
            m for m in self.candidates
            if len(m.destination_sequence()) > depth
            and m.destination_sequence()[depth] == square
        ]
        if not matching:
            piece = self.state.piece_at(square)
            if piece is not None and piece.color is self.state.side_to_move:
                self.cancel_chain()
                return self.tap_square(square)
            return TapResult("ignored")

        self.prefix.append(square)
        self.candidates = matching
        complete = [m for m in matching if len(m.destination_sequence()) == len(self.prefix)]
        longer = [m for m in matching if len(m.destination_sequence()) > len(self.prefix)]
        if complete and not longer:
            promotions = tuple(m for m in complete if m.promotion is not None)
            if len(complete) > 1 and promotions:
                return TapResult("promotion", promotion_moves=tuple(complete))
            move = complete[0]
            self.commit_move(move)
            return TapResult("committed", move=move)

        active_id = self.current_active_piece_id()
        if active_id is not None:
            piece = self.state.pieces[active_id]
            location = self.prefix[-1]
            self.status_message = (
                f"Ход передан: активна {PIECE_NAMES[piece.kind]} на {square_name(location)}"
            )
        return TapResult("continued")

    def commit_move(self, move: CompoundMove) -> str:
        if self.timeline.is_reviewing:
            raise RuntimeError("Cannot commit while reviewing history")
        notation = move_to_notation(self.state, move)
        self.state = apply_move(self.state, move)
        self.timeline.append(self.state)
        self.legal_moves = generate_legal_moves(self.state)
        self.cancel_chain()
        result = game_result(self.state)
        if result:
            self.status_message = self.result_text(result)
        elif in_check(self.state, self.state.side_to_move):
            self.status_message = f"{notation}. Шах!"
        else:
            self.status_message = notation
        return notation

    def commit_promotion(self, moves: tuple[CompoundMove, ...], kind: PieceType) -> CompoundMove:
        for move in moves:
            if move.promotion is kind:
                self.commit_move(move)
                return move
        raise ValueError("Promotion choice is not available")

    def cancel_chain(self) -> None:
        self.selected_piece_id = None
        self.prefix = []
        self.candidates = []

    def current_active_piece_id(self) -> int | None:
        if self.selected_piece_id is None:
            return None
        if not self.prefix:
            return self.selected_piece_id
        if not self.candidates:
            return None
        sample = self.candidates[0]
        previous = sample.links[len(self.prefix) - 1]
        return previous.target_friendly_piece_id

    def next_links(self):
        depth = len(self.prefix)
        return [m.links[depth] for m in self.candidates if len(m.links) > depth]

    def preview_board(self) -> tuple[dict[Square, int], int | None]:
        board = dict(self.state.board)
        if self.selected_piece_id is None or not self.prefix:
            return board, self.selected_piece_id
        sample = self.candidates[0]
        active_id = self.selected_piece_id
        first_piece = self.state.pieces[active_id]
        if first_piece.square is not None:
            board.pop(first_piece.square, None)
        for index in range(len(self.prefix)):
            link = sample.links[index]
            target_id = link.target_friendly_piece_id
            board.pop(link.to_square, None)
            board[link.to_square] = link.piece_id
            active_id = target_id
        return board, active_id

    def active_overlay(self) -> tuple[int, Square] | None:
        if not self.prefix:
            return None
        active_id = self.current_active_piece_id()
        if active_id is None:
            return None
        return active_id, self.prefix[-1]

    def unavailable_friendly_targets(self) -> set[Square]:
        board, active_id = self.preview_board()
        if active_id is None:
            return set()
        piece = self.state.pieces[active_id]
        if piece.kind not in {
            PieceType.QUEEN,
            PieceType.ROOK,
            PieceType.BISHOP,
            PieceType.KNIGHT,
        }:
            return set()
        origin = self.prefix[-1] if self.prefix else piece.square
        if origin is None:
            return set()
        reachable = set(geometric_targets(piece, origin, board))
        legal_next = {link.to_square for link in self.next_links()}
        unavailable: set[Square] = set()
        for target in reachable - legal_next:
            target_id = board.get(target)
            if target_id is not None and self.state.pieces[target_id].color is piece.color:
                unavailable.add(target)
        return unavailable

    def review_back(self) -> bool:
        if not self.timeline.can_back:
            return False
        self.state = self.timeline.back()
        self.legal_moves = []
        self.cancel_chain()
        count = len(self.state.move_notation_history)
        self.status_message = (
            f"Просмотр после хода {count}" if count else "Начальная позиция"
        )
        return True

    def review_forward(self) -> bool:
        if not self.timeline.can_forward:
            return False
        self.state = self.timeline.forward()
        self.cancel_chain()
        if self.timeline.is_reviewing:
            self.legal_moves = []
            self.status_message = f"Просмотр после хода {len(self.state.move_notation_history)}"
        else:
            self.legal_moves = generate_legal_moves(self.state)
            result = game_result(self.state)
            if result:
                self.status_message = self.result_text(result)
            elif self.state.move_notation_history:
                self.status_message = f"Текущая позиция: {self.state.move_notation_history[-1]}"
            else:
                self.status_message = "Белые начинают"
        return True

    def save(self, path: str | Path) -> None:
        save_game_session(self.timeline.states, self.timeline.index, path)

    def load(self, path: str | Path) -> None:
        states, index = load_game_session(path)
        self.timeline = GameTimeline(states=[s.clone() for s in states], index=index)
        self.state = self.timeline.current()
        self.cancel_chain()
        self.legal_moves = [] if self.timeline.is_reviewing else generate_legal_moves(self.state)
        self.status_message = "Партия загружена"

    @staticmethod
    def result_text(result: str) -> str:
        return {
            "checkmate": "Мат",
            "stalemate": "Пат",
            "draw_50_move": "Ничья: правило 50 ходов",
            "draw_repetition": "Ничья: троекратное повторение",
            "draw_insufficient": "Ничья: недостаточно материала",
        }.get(result, result)
