from __future__ import annotations

import json
from pathlib import Path

from .model import BoardState, Color, Piece, PieceType


def state_to_dict(state: BoardState) -> dict:
    return {
        "version": 1,
        "side_to_move": state.side_to_move.value,
        "en_passant_target": list(state.en_passant_target)
        if state.en_passant_target
        else None,
        "en_passant_pawn_id": state.en_passant_pawn_id,
        "halfmove_clock": state.halfmove_clock,
        "fullmove_number": state.fullmove_number,
        "position_history": state.position_history,
        "move_notation_history": state.move_notation_history,
        "next_piece_id": state.next_piece_id,
        "pieces": [
            {
                "id": p.id,
                "color": p.color.value,
                "kind": p.kind.value,
                "square": list(p.square) if p.square else None,
                "has_moved": p.has_moved,
            }
            for p in state.pieces.values()
        ],
    }


def state_from_dict(data: dict) -> BoardState:
    if data.get("version") != 1:
        raise ValueError("Unsupported save version")
    pieces: dict[int, Piece] = {}
    board = {}
    for raw in data["pieces"]:
        piece_id = int(raw["id"])
        if piece_id in pieces:
            raise ValueError(f"Duplicate piece id in save: {piece_id}")
        square = tuple(raw["square"]) if raw["square"] is not None else None
        piece = Piece(
            id=piece_id,
            color=Color(raw["color"]),
            kind=PieceType(raw["kind"]),
            square=square,
            has_moved=bool(raw["has_moved"]),
        )
        pieces[piece.id] = piece
        if square is not None:
            board[square] = piece.id
    state = BoardState(
        pieces=pieces,
        board=board,
        side_to_move=Color(data["side_to_move"]),
        en_passant_target=tuple(data["en_passant_target"])
        if data.get("en_passant_target")
        else None,
        en_passant_pawn_id=data.get("en_passant_pawn_id"),
        halfmove_clock=int(data.get("halfmove_clock", 0)),
        fullmove_number=int(data.get("fullmove_number", 1)),
        position_history=list(data.get("position_history", [])),
        move_notation_history=list(data.get("move_notation_history", [])),
        next_piece_id=int(data.get("next_piece_id", max(pieces, default=0) + 1)),
    )
    state.validate()
    return state


def save_game(state: BoardState, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(state_to_dict(state), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temp.replace(path)


def load_game(path: str | Path) -> BoardState:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return state_from_dict(data)


def save_game_session(
    states: list[BoardState], index: int, path: str | Path
) -> None:
    if not states:
        raise ValueError("Cannot save an empty game timeline")
    if not 0 <= index < len(states):
        raise ValueError("Timeline index is outside the saved states")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "version": 2,
        "timeline_index": index,
        "timeline": [state_to_dict(state) for state in states],
    }
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temp.replace(path)


def load_game_session(path: str | Path) -> tuple[list[BoardState], int]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") == 1:
        return [state_from_dict(data)], 0
    if data.get("version") != 2:
        raise ValueError("Unsupported save version")
    raw_timeline = data.get("timeline")
    if not isinstance(raw_timeline, list) or not raw_timeline:
        raise ValueError("Saved timeline is empty or invalid")
    states = [state_from_dict(raw) for raw in raw_timeline]
    index = int(data.get("timeline_index", len(states) - 1))
    if not 0 <= index < len(states):
        raise ValueError("Saved timeline index is invalid")
    return states, index
