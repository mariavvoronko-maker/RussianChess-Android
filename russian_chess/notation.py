from __future__ import annotations

from .model import BoardState, CompoundMove, PIECE_LETTERS, square_name


def move_to_notation(state: BoardState, move: CompoundMove) -> str:
    if move.is_castling:
        return "O-O" if move.final_destination[0] == 6 else "O-O-O"
    parts: list[str] = []
    for index, link in enumerate(move.links):
        piece = state.pieces[link.piece_id]
        prefix = f"{PIECE_LETTERS[piece.kind]}{square_name(link.from_square)}"
        if link.is_transfer:
            parts.append(prefix + ">")
            continue
        separator = "x" if link.captured_piece_id is not None else "-"
        final = prefix + separator + square_name(link.to_square)
        if link.promotion is not None:
            final += "=" + PIECE_LETTERS[link.promotion]
        if link.is_en_passant:
            final += " e.p."
        parts.append(final)
    compact = ""
    for i, part in enumerate(parts):
        if i == 0:
            compact = part
        elif parts[i - 1].endswith(">"):
            compact += part
        else:
            compact += part
    return compact
