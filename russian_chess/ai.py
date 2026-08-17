from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from .model import BoardState, Color, CompoundMove, PieceType
from .rules import (
    apply_move,
    generate_legal_moves,
    in_check,
    insufficient_material,
    position_key,
    repetition_count,
)


MATE_SCORE = 1_000_000
INF = 10_000_000
PIECE_VALUE = {
    PieceType.PAWN: 100,
    PieceType.KNIGHT: 320,
    PieceType.BISHOP: 330,
    PieceType.ROOK: 500,
    PieceType.QUEEN: 900,
    PieceType.KING: 0,
}


class SearchStopped(Exception):
    pass


@dataclass(slots=True)
class TTEntry:
    depth: int
    score: int
    flag: str
    best_signature: tuple | None


@dataclass(slots=True)
class SearchInfo:
    depth: int = 0
    nodes: int = 0
    score: int = 0
    elapsed: float = 0.0


def move_signature(move: CompoundMove) -> tuple:
    return tuple(
        (
            link.piece_id,
            link.from_square,
            link.to_square,
            link.target_friendly_piece_id,
            link.captured_piece_id,
            link.promotion.value if link.promotion else None,
            link.is_en_passant,
            link.is_castling,
        )
        for link in move.links
    )


def evaluate_white(state: BoardState) -> int:
    score = 0
    bishops = {Color.WHITE: 0, Color.BLACK: 0}
    pawns_by_file = {Color.WHITE: [0] * 8, Color.BLACK: [0] * 8}
    for piece in state.living_pieces():
        assert piece.square is not None
        sign = 1 if piece.color is Color.WHITE else -1
        value = PIECE_VALUE[piece.kind]
        score += sign * value
        x, y = piece.square
        center_distance = abs(3.5 - x) + abs(3.5 - y)
        if piece.kind in {PieceType.KNIGHT, PieceType.BISHOP, PieceType.QUEEN}:
            score += sign * int(12 - center_distance * 2)
        if piece.kind is PieceType.BISHOP:
            bishops[piece.color] += 1
        if piece.kind is PieceType.PAWN:
            pawns_by_file[piece.color][x] += 1
            advancement = y if piece.color is Color.WHITE else 7 - y
            score += sign * advancement * 8
            if advancement >= 5:
                score += sign * (advancement - 4) * 25
        if piece.kind in {PieceType.KNIGHT, PieceType.BISHOP} and not piece.has_moved:
            score -= sign * 8
        if piece.kind is PieceType.KING:
            if x in (2, 6):
                score += sign * 25

    for color in (Color.WHITE, Color.BLACK):
        sign = 1 if color is Color.WHITE else -1
        if bishops[color] >= 2:
            score += sign * 25
        for count in pawns_by_file[color]:
            if count > 1:
                score -= sign * 15 * (count - 1)
        files = pawns_by_file[color]
        for f, count in enumerate(files):
            if (
                count
                and (f == 0 or files[f - 1] == 0)
                and (f == 7 or files[f + 1] == 0)
            ):
                score -= sign * 10 * count

    if in_check(state, Color.WHITE):
        score -= 35
    if in_check(state, Color.BLACK):
        score += 35
    return score


def _variant_move_bonus(state: BoardState, moves: list[CompoundMove]) -> int:
    bonus = min(len(moves), 100) * 2
    chain_moves: list[CompoundMove] = []
    for move in moves:
        chain_length = len(move.links) - 1
        if chain_length <= 0:
            if move.promotion is not None:
                bonus += PIECE_VALUE[move.promotion] // 25
            continue
        chain_moves.append(move)
        bonus += chain_length * 4
        last_piece = state.pieces[move.last_link.piece_id]
        if last_piece.kind is PieceType.PAWN:
            bonus += 7
            direction = 1 if last_piece.color is Color.WHITE else -1
            progress = (
                move.final_destination[1] - move.last_link.from_square[1]
            ) * direction
            bonus += max(0, progress) * 3
        if move.is_capture:
            bonus += 12
        if move.promotion is not None:
            bonus += 25 + PIECE_VALUE[move.promotion] // 20

    forcing = sorted(
        chain_moves,
        key=lambda m: (m.promotion is not None, m.is_capture, len(m.links)),
        reverse=True,
    )[:4]
    for move in forcing:
        child = apply_move(state, move, record_history=False)
        if in_check(child, child.side_to_move):
            bonus += 14
            if move.is_capture:
                bonus += 6
    return bonus


def evaluate_for_side(
    state: BoardState, legal_moves: list[CompoundMove] | None = None
) -> int:
    white_score = evaluate_white(state)
    base = white_score if state.side_to_move is Color.WHITE else -white_score
    moves = generate_legal_moves(state) if legal_moves is None else legal_moves
    return base + _variant_move_bonus(state, moves)


class SearchEngine:
    def __init__(self) -> None:
        self.tt: dict[str, TTEntry] = {}
        self.deadline = 0.0
        self.stop_event: threading.Event | None = None
        self.nodes = 0
        self.info = SearchInfo()

    def _check_time(self) -> None:
        if time.monotonic() >= self.deadline or (
            self.stop_event is not None and self.stop_event.is_set()
        ):
            raise SearchStopped

    def choose_move(
        self,
        state: BoardState,
        time_limit: float = 2.0,
        stop_event: threading.Event | None = None,
        max_depth: int = 8,
    ) -> CompoundMove | None:
        start = time.monotonic()
        self.deadline = start + max(0.05, time_limit)
        self.stop_event = stop_event
        self.nodes = 0
        root_moves = generate_legal_moves(state)
        if not root_moves:
            return None
        best_move = root_moves[0]
        best_score = -INF
        previous_best_sig = None

        for depth in range(1, max_depth + 1):
            ordered = self._order_moves(state, root_moves, previous_best_sig)
            alpha, beta = -INF, INF
            iteration_best = ordered[0]
            iteration_score = -INF
            completed = False
            try:
                for move in ordered:
                    self._check_time()
                    child = apply_move(state, move, record_history=False)
                    score = -self._negamax(child, depth - 1, -beta, -alpha, 1)
                    if score > iteration_score:
                        iteration_score = score
                        iteration_best = move
                        best_move = iteration_best
                        best_score = iteration_score
                    alpha = max(alpha, score)
                completed = True
            except SearchStopped:
                if iteration_score > -INF:
                    self.info = SearchInfo(
                        depth - 1, self.nodes, best_score, time.monotonic() - start
                    )
                break
            if completed:
                best_move = iteration_best
                best_score = iteration_score
                previous_best_sig = move_signature(best_move)
                self.info = SearchInfo(
                    depth, self.nodes, best_score, time.monotonic() - start
                )
        self.info.elapsed = time.monotonic() - start
        return best_move

    def _is_draw(self, state: BoardState) -> bool:
        return (
            state.halfmove_clock >= 100
            or repetition_count(state) >= 3
            or insufficient_material(state)
        )

    def _negamax(
        self, state: BoardState, depth: int, alpha: int, beta: int, ply: int
    ) -> int:
        self.nodes += 1
        self._check_time()
        if self._is_draw(state):
            return 0
        if depth <= 0:
            return self._quiescence(state, alpha, beta, ply, qdepth=0)

        key = f"{position_key(state)}|h={state.halfmove_clock}|r={repetition_count(state)}"
        original_alpha = alpha
        entry = self.tt.get(key)
        if entry is not None and entry.depth >= depth:
            if entry.flag == "exact":
                return entry.score
            if entry.flag == "lower":
                alpha = max(alpha, entry.score)
            elif entry.flag == "upper":
                beta = min(beta, entry.score)
            if alpha >= beta:
                return entry.score

        moves = generate_legal_moves(state)
        if not moves:
            return -MATE_SCORE + ply if in_check(state, state.side_to_move) else 0

        best_score = -INF
        best_sig = entry.best_signature if entry else None
        for move in self._order_moves(state, moves, best_sig):
            child = apply_move(state, move, record_history=False)
            score = -self._negamax(child, depth - 1, -beta, -alpha, ply + 1)
            if score > best_score:
                best_score = score
                best_sig = move_signature(move)
            alpha = max(alpha, score)
            if alpha >= beta:
                break

        flag = "exact"
        if best_score <= original_alpha:
            flag = "upper"
        elif best_score >= beta:
            flag = "lower"
        self.tt[key] = TTEntry(depth, best_score, flag, best_sig)
        return best_score

    def _quiescence(
        self, state: BoardState, alpha: int, beta: int, ply: int, qdepth: int
    ) -> int:
        self.nodes += 1
        self._check_time()
        if self._is_draw(state):
            return 0

        moves = generate_legal_moves(state)
        if not moves:
            return -MATE_SCORE + ply if in_check(state, state.side_to_move) else 0

        checked = in_check(state, state.side_to_move)
        if checked:
            candidates = moves
        else:
            stand_pat = evaluate_for_side(state, moves)
            if stand_pat >= beta:
                return beta
            alpha = max(alpha, stand_pat)
            if qdepth >= 4:
                return alpha
            candidates = [m for m in moves if m.is_capture or m.promotion is not None]

        for move in self._order_moves(state, candidates, None)[:24]:
            child = apply_move(state, move, record_history=False)
            score = -self._quiescence(child, -beta, -alpha, ply + 1, qdepth + 1)
            if score >= beta:
                return beta
            alpha = max(alpha, score)
        return alpha

    def _order_moves(
        self,
        state: BoardState,
        moves: list[CompoundMove],
        preferred_signature: tuple | None,
    ) -> list[CompoundMove]:
        def score(move: CompoundMove) -> int:
            s = 0
            if (
                preferred_signature is not None
                and move_signature(move) == preferred_signature
            ):
                s += 1_000_000
            if move.captured_piece_id is not None:
                victim = state.pieces[move.captured_piece_id]
                attacker = state.pieces[move.last_link.piece_id]
                s += (
                    100_000 + 10 * PIECE_VALUE[victim.kind] - PIECE_VALUE[attacker.kind]
                )
            if move.promotion is not None:
                s += 80_000 + PIECE_VALUE[move.promotion]
            s += (len(move.links) - 1) * 40
            return s

        return sorted(moves, key=score, reverse=True)
