from __future__ import annotations

from collections import Counter
from typing import Iterable

from .model import (
    BoardState,
    ChainLink,
    Color,
    CompoundMove,
    Piece,
    PieceType,
    PROMOTION_TYPES,
    Square,
    TRANSFER_CAPABLE,
    on_board,
)


ORTHOGONAL = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIAGONAL = ((1, 1), (1, -1), (-1, 1), (-1, -1))
KNIGHT_STEPS = (
    (1, 2),
    (2, 1),
    (2, -1),
    (1, -2),
    (-1, -2),
    (-2, -1),
    (-2, 1),
    (-1, 2),
)
KING_STEPS = ORTHOGONAL + DIAGONAL


class IllegalMove(ValueError):
    pass


def _ray_targets(
    origin: Square, directions: Iterable[tuple[int, int]], board: dict[Square, int]
) -> list[Square]:
    result: list[Square] = []
    for dx, dy in directions:
        x, y = origin
        while True:
            x += dx
            y += dy
            sq = (x, y)
            if not on_board(sq):
                break
            result.append(sq)
            if sq in board:
                break
    return result


def geometric_targets(
    piece: Piece, origin: Square, board: dict[Square, int]
) -> list[Square]:
    if piece.kind is PieceType.QUEEN:
        return _ray_targets(origin, ORTHOGONAL + DIAGONAL, board)
    if piece.kind is PieceType.ROOK:
        return _ray_targets(origin, ORTHOGONAL, board)
    if piece.kind is PieceType.BISHOP:
        return _ray_targets(origin, DIAGONAL, board)
    if piece.kind is PieceType.KNIGHT:
        return [
            (origin[0] + dx, origin[1] + dy)
            for dx, dy in KNIGHT_STEPS
            if on_board((origin[0] + dx, origin[1] + dy))
        ]
    if piece.kind is PieceType.KING:
        return [
            (origin[0] + dx, origin[1] + dy)
            for dx, dy in KING_STEPS
            if on_board((origin[0] + dx, origin[1] + dy))
        ]
    raise ValueError("Pawn targets require pawn_final_options")


def is_square_attacked(
    state: BoardState,
    square: Square,
    by_color: Color,
    board: dict[Square, int] | None = None,
) -> bool:
    board = state.board if board is None else board

    pawn_direction = 1 if by_color is Color.WHITE else -1
    for dx in (-1, 1):
        source = (square[0] - dx, square[1] - pawn_direction)
        pid = board.get(source)
        if pid is not None:
            p = state.pieces[pid]
            if p.color is by_color and p.kind is PieceType.PAWN:
                return True

    for dx, dy in KNIGHT_STEPS:
        source = (square[0] - dx, square[1] - dy)
        pid = board.get(source)
        if pid is not None:
            p = state.pieces[pid]
            if p.color is by_color and p.kind is PieceType.KNIGHT:
                return True

    for dx, dy in KING_STEPS:
        source = (square[0] - dx, square[1] - dy)
        pid = board.get(source)
        if pid is not None:
            p = state.pieces[pid]
            if p.color is by_color and p.kind is PieceType.KING:
                return True

    for directions, attackers in (
        (ORTHOGONAL, {PieceType.ROOK, PieceType.QUEEN}),
        (DIAGONAL, {PieceType.BISHOP, PieceType.QUEEN}),
    ):
        for dx, dy in directions:
            x, y = square
            while True:
                x += dx
                y += dy
                sq = (x, y)
                if not on_board(sq):
                    break
                pid = board.get(sq)
                if pid is None:
                    continue
                p = state.pieces[pid]
                if p.color is by_color and p.kind in attackers:
                    return True
                break
    return False


def in_check(
    state: BoardState, color: Color, board: dict[Square, int] | None = None
) -> bool:
    board = state.board if board is None else board
    king_square = None
    for sq, pid in board.items():
        p = state.pieces[pid]
        if p.color is color and p.kind is PieceType.KING:
            king_square = sq
            break
    if king_square is None:
        raise ValueError(f"Missing {color.value} king")
    return is_square_attacked(state, king_square, color.opposite, board)


def _legal_final_board(
    state: BoardState,
    color: Color,
    board: dict[Square, int],
    promotion_piece_id: int | None = None,
    promotion: PieceType | None = None,
) -> bool:
    if promotion_piece_id is None:
        return not in_check(state, color, board)
    old_kind = state.pieces[promotion_piece_id].kind
    state.pieces[promotion_piece_id].kind = promotion or old_kind
    try:
        return not in_check(state, color, board)
    finally:
        state.pieces[promotion_piece_id].kind = old_kind


def pawn_final_options(
    state: BoardState,
    piece: Piece,
    origin: Square,
    virtual_board: dict[Square, int],
) -> list[tuple[Square, int | None, bool, PieceType | None]]:
    direction = 1 if piece.color is Color.WHITE else -1
    start_rank = 1 if piece.color is Color.WHITE else 6
    promotion_rank = 7 if piece.color is Color.WHITE else 0
    options: list[tuple[Square, int | None, bool, PieceType | None]] = []

    one = (origin[0], origin[1] + direction)
    if on_board(one) and one not in virtual_board:
        promotions = PROMOTION_TYPES if one[1] == promotion_rank else (None,)
        for promotion in promotions:
            options.append((one, None, False, promotion))
        two = (origin[0], origin[1] + 2 * direction)
        if (
            origin[1] == start_rank
            and not piece.has_moved
            and on_board(two)
            and two not in virtual_board
        ):
            options.append((two, None, False, None))

    for dx in (-1, 1):
        dest = (origin[0] + dx, origin[1] + direction)
        if not on_board(dest):
            continue
        target_id = virtual_board.get(dest)
        if target_id is not None:
            target = state.pieces[target_id]
            if target.color is piece.color or target.kind is PieceType.KING:
                continue
            promotions = PROMOTION_TYPES if dest[1] == promotion_rank else (None,)
            for promotion in promotions:
                options.append((dest, target_id, False, promotion))
            continue
        if state.en_passant_target == dest and state.en_passant_pawn_id is not None:
            captured_id = state.en_passant_pawn_id
            captured = state.pieces.get(captured_id)
            captured_square = (dest[0], origin[1])
            if (
                captured is not None
                and captured.square == captured_square
                and virtual_board.get(captured_square) == captured_id
                and captured.color is piece.color.opposite
                and captured.kind is PieceType.PAWN
            ):
                options.append((dest, captured_id, True, None))
    return options


def _build_move(
    color: Color,
    links: list[ChainLink],
    used: set[int],
) -> CompoundMove:
    last = links[-1]
    return CompoundMove(
        color=color,
        links=tuple(links),
        used_piece_ids=frozenset(used),
        final_destination=last.to_square,
        captured_piece_id=last.captured_piece_id,
        promotion=last.promotion,
        is_castling=last.is_castling,
        is_en_passant=last.is_en_passant,
    )


def _dfs_compound(
    state: BoardState,
    active_piece: Piece,
    origin: Square,
    virtual_board: dict[Square, int],
    links: list[ChainLink],
    used: set[int],
    out: list[CompoundMove],
) -> bool:
    found = False

    if active_piece.kind is PieceType.PAWN:
        for dest, captured_id, is_ep, promotion in pawn_final_options(
            state, active_piece, origin, virtual_board
        ):
            final_board = dict(virtual_board)
            if captured_id is not None:
                captured_square = state.pieces[captured_id].square
                if captured_square is not None:
                    final_board.pop(captured_square, None)
            final_board[dest] = active_piece.id
            if not _legal_final_board(
                state, active_piece.color, final_board, active_piece.id, promotion
            ):
                continue
            link = ChainLink(
                active_piece.id,
                origin,
                dest,
                captured_piece_id=captured_id,
                promotion=promotion,
                is_en_passant=is_ep,
            )
            out.append(_build_move(active_piece.color, links + [link], used))
            found = True
        return found

    targets = geometric_targets(active_piece, origin, virtual_board)
    for dest in targets:
        target_id = virtual_board.get(dest)
        if target_id is None:
            final_board = dict(virtual_board)
            final_board[dest] = active_piece.id
            if not _legal_final_board(state, active_piece.color, final_board):
                continue
            link = ChainLink(active_piece.id, origin, dest)
            out.append(_build_move(active_piece.color, links + [link], used))
            found = True
            continue

        target = state.pieces[target_id]
        if target.color is active_piece.color.opposite:
            if target.kind is PieceType.KING:
                continue
            final_board = dict(virtual_board)
            final_board.pop(dest)
            final_board[dest] = active_piece.id
            if not _legal_final_board(state, active_piece.color, final_board):
                continue
            link = ChainLink(active_piece.id, origin, dest, captured_piece_id=target_id)
            out.append(_build_move(active_piece.color, links + [link], used))
            found = True
            continue

        if active_piece.kind not in TRANSFER_CAPABLE:
            continue
        if target.kind is PieceType.KING or target.id in used:
            continue

        next_board = dict(virtual_board)
        next_board.pop(dest)
        next_board[dest] = active_piece.id
        transfer_link = ChainLink(
            active_piece.id,
            origin,
            dest,
            target_friendly_piece_id=target.id,
        )
        branch_found = _dfs_compound(
            state,
            target,
            dest,
            next_board,
            links + [transfer_link],
            used | {target.id},
            out,
        )
        found = found or branch_found
    return found


def _castling_moves(state: BoardState, color: Color) -> list[CompoundMove]:
    try:
        king = state.king(color)
    except ValueError:
        return []
    home_rank = 0 if color is Color.WHITE else 7
    if king.square != (4, home_rank) or king.has_moved or in_check(state, color):
        return []
    result: list[CompoundMove] = []
    for rook_file, king_dest_file, empty_files, through_files in (
        (7, 6, (5, 6), (5, 6)),
        (0, 2, (1, 2, 3), (3, 2)),
    ):
        rook = state.piece_at((rook_file, home_rank))
        if (
            rook is None
            or rook.color is not color
            or rook.kind is not PieceType.ROOK
            or rook.has_moved
        ):
            continue
        if any((f, home_rank) in state.board for f in empty_files):
            continue
        castle_safe = True
        for f in through_files:
            probe = dict(state.board)
            probe.pop(king.square, None)
            probe[(f, home_rank)] = king.id
            if is_square_attacked(state, (f, home_rank), color.opposite, probe):
                castle_safe = False
                break
        if not castle_safe:
            continue
        dest = (king_dest_file, home_rank)
        link = ChainLink(king.id, king.square, dest, is_castling=True)
        result.append(
            CompoundMove(
                color=color,
                links=(link,),
                used_piece_ids=frozenset({king.id, rook.id}),
                final_destination=dest,
                is_castling=True,
            )
        )
    return result


def generate_legal_moves(
    state: BoardState, color: Color | None = None
) -> list[CompoundMove]:
    color = state.side_to_move if color is None else color
    moves: list[CompoundMove] = []
    for piece in list(state.living_pieces(color)):
        assert piece.square is not None
        virtual_board = dict(state.board)
        virtual_board.pop(piece.square)
        _dfs_compound(
            state,
            piece,
            piece.square,
            virtual_board,
            [],
            {piece.id},
            moves,
        )
    moves.extend(_castling_moves(state, color))
    unique: dict[tuple, CompoundMove] = {}
    for move in moves:
        key = tuple(
            (
                link.piece_id,
                link.from_square,
                link.to_square,
                link.target_friendly_piece_id,
                link.captured_piece_id,
                link.promotion,
                link.is_en_passant,
                link.is_castling,
            )
            for link in move.links
        )
        unique[key] = move
    return list(unique.values())


def apply_move(
    state: BoardState, move: CompoundMove, *, record_history: bool = True
) -> BoardState:
    if move.color is not state.side_to_move:
        raise IllegalMove("Wrong side to move")
    new = state.clone()
    original_kinds = {pid: state.pieces[pid].kind for pid in move.used_piece_ids}

    for pid in move.used_piece_ids:
        piece = new.pieces[pid]
        if piece.square is not None:
            new.board.pop(piece.square, None)
            piece.square = None

    if move.captured_piece_id is not None:
        captured = new.pieces[move.captured_piece_id]
        if captured.square is not None:
            new.board.pop(captured.square, None)
        captured.square = None

    if move.is_castling:
        king_id = move.links[0].piece_id
        king = new.pieces[king_id]
        home_rank = 0 if king.color is Color.WHITE else 7
        king_dest = move.final_destination
        rook_from = (7, home_rank) if king_dest[0] == 6 else (0, home_rank)
        rook_to = (5, home_rank) if king_dest[0] == 6 else (3, home_rank)
        rook_id = state.board[rook_from]
        rook = new.pieces[rook_id]
        king.square = king_dest
        rook.square = rook_to
        new.board[king_dest] = king_id
        new.board[rook_to] = rook_id
    else:
        for link in move.links:
            piece = new.pieces[link.piece_id]
            piece.square = link.to_square
            new.board[link.to_square] = piece.id

    for pid in move.used_piece_ids:
        new.pieces[pid].has_moved = True

    if move.promotion is not None:
        new.pieces[move.last_link.piece_id].kind = move.promotion

    new.en_passant_target = None
    new.en_passant_pawn_id = None
    last_piece_id = move.last_link.piece_id
    last_original_kind = original_kinds[last_piece_id]
    if last_original_kind is PieceType.PAWN:
        fr = move.last_link.from_square
        to = move.last_link.to_square
        if abs(to[1] - fr[1]) == 2:
            new.en_passant_target = (fr[0], (fr[1] + to[1]) // 2)
            new.en_passant_pawn_id = last_piece_id

    if move.is_capture or last_original_kind is PieceType.PAWN:
        new.halfmove_clock = 0
    else:
        new.halfmove_clock += 1
    if state.side_to_move is Color.BLACK:
        new.fullmove_number += 1
    new.side_to_move = state.side_to_move.opposite

    if record_history:
        from .notation import move_to_notation

        new.move_notation_history.append(move_to_notation(state, move))
    new.position_history.append(position_key(new))
    new.validate()
    return new


def position_key(state: BoardState) -> str:
    entries = []
    for square, pid in sorted(
        state.board.items(), key=lambda item: (item[0][1], item[0][0])
    ):
        p = state.pieces[pid]
        moved_relevant = (
            p.has_moved
            if p.kind in {PieceType.KING, PieceType.ROOK, PieceType.PAWN}
            else False
        )
        entries.append(
            f"{square[0]}{square[1]}:{p.color.value}:{p.kind.value}:{int(moved_relevant)}"
        )
    ep = (
        "-"
        if state.en_passant_target is None
        else f"{state.en_passant_target[0]}{state.en_passant_target[1]}"
    )
    return "|".join(entries) + f"/{state.side_to_move.value}/{ep}"


def repetition_count(state: BoardState) -> int:
    if not state.position_history:
        return 0
    key = position_key(state)
    return Counter(state.position_history)[key]


def insufficient_material(state: BoardState) -> bool:
    non_kings = [p for p in state.living_pieces() if p.kind is not PieceType.KING]
    if not non_kings:
        return True
    if len(non_kings) == 1 and non_kings[0].kind in {
        PieceType.BISHOP,
        PieceType.KNIGHT,
    }:
        return True
    if all(p.kind is PieceType.BISHOP for p in non_kings):
        square_colors = {
            (p.square[0] + p.square[1]) % 2 for p in non_kings if p.square is not None
        }
        return len(square_colors) == 1
    return False


def game_result(state: BoardState) -> str | None:
    if state.halfmove_clock >= 100:
        return "draw_50_move"
    if repetition_count(state) >= 3:
        return "draw_repetition"
    if insufficient_material(state):
        return "draw_insufficient"
    legal = generate_legal_moves(state)
    if legal:
        return None
    if in_check(state, state.side_to_move):
        return "checkmate"
    return "stalemate"
