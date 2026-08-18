from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path("russian_chess/assets/pieces")
OUT.mkdir(parents=True, exist_ok=True)
SIZE = 192
SS = 4
C = SIZE * SS

WHITE = (248, 248, 241, 255)
BLACK = (16, 18, 22, 255)
INK = (17, 18, 20, 255)
LIGHT = (244, 244, 238, 255)


def sc(v):
    return int(round(v * SS))


def box(x0, y0, x1, y1):
    return tuple(sc(v) for v in (x0, y0, x1, y1))


def pts(seq):
    return [(sc(x), sc(y)) for x, y in seq]


def piece_canvas():
    im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def style(color):
    if color == "white":
        return WHITE, INK, sc(2.6), INK
    return BLACK, None, 0, LIGHT


def poly(d, p, fill, outline=None, width=0):
    d.polygon(pts(p), fill=fill)
    if outline and width:
        d.line(pts(p + [p[0]]), fill=outline, width=width, joint="curve")


def rr(d, b, r, fill, outline=None, width=0):
    d.rounded_rectangle(box(*b), radius=sc(r), fill=fill, outline=outline, width=width)


def ell(d, b, fill, outline=None, width=0):
    d.ellipse(box(*b), fill=fill, outline=outline, width=width)


def line(d, p, fill, width):
    d.line(pts(p), fill=fill, width=sc(width), joint="curve")


def base(d, fill, outline, ow, detail):
    rr(d, (39, 145, 153, 166), 7, fill, outline, ow)
    rr(d, (30, 163, 162, 177), 6, fill, outline, ow)
    if detail != outline:
        line(d, [(43, 155), (149, 155)], detail, 2)


def finish(im):
    return im.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def draw_pawn(color):
    im, d = piece_canvas(); fill, out, ow, detail = style(color)
    ell(d, (73, 38, 119, 84), fill, out, ow)
    rr(d, (65, 76, 127, 96), 10, fill, out, ow)
    poly(d, [(70, 92), (122, 92), (136, 145), (56, 145)], fill, out, ow)
    base(d, fill, out, ow, detail)
    return finish(im)


def draw_rook(color):
    im, d = piece_canvas(); fill, out, ow, detail = style(color)
    poly(d, [(46, 38), (69, 38), (69, 52), (85, 52), (85, 38), (107, 38), (107, 52), (123, 52), (123, 38), (146, 38), (142, 72), (50, 72)], fill, out, ow)
    rr(d, (50, 68, 142, 86), 5, fill, out, ow)
    poly(d, [(58, 82), (134, 82), (128, 145), (64, 145)], fill, out, ow)
    rr(d, (55, 133, 137, 149), 5, fill, out, ow)
    base(d, fill, out, ow, detail)
    if color == "black":
        line(d, [(61, 76), (131, 76)], detail, 2)
        line(d, [(68, 135), (124, 135)], detail, 2)
    return finish(im)


def draw_bishop(color):
    im, d = piece_canvas(); fill, out, ow, detail = style(color)
    ell(d, (88, 30, 104, 46), fill, out, ow)
    poly(d, [(96, 39), (71, 68), (66, 91), (77, 113), (115, 113), (126, 91), (121, 68)], fill, out, ow)
    rr(d, (70, 104, 122, 121), 7, fill, out, ow)
    poly(d, [(75, 117), (117, 117), (128, 145), (64, 145)], fill, out, ow)
    base(d, fill, out, ow, detail)
    line(d, [(84, 82), (108, 62)], detail, 4.0)
    return finish(im)


def draw_knight(color):
    im, d = piece_canvas(); fill, out, ow, detail = style(color)
    poly(d, [(63, 144), (132, 144), (126, 119), (130, 88), (117, 54), (100, 38), (92, 55), (74, 46), (78, 67), (60, 83), (48, 105), (52, 119), (70, 121)], fill, out, ow)
    ell(d, (45, 95, 79, 123), fill, out, ow)
    line(d, [(72, 118), (91, 110), (106, 96), (112, 80)], fill, 12)
    if color == "white":
        line(d, [(72, 118), (91, 110), (106, 96), (112, 80)], out, 2.6)
    ell(d, (91, 62, 99, 70), detail)
    ell(d, (55, 106, 61, 112), detail)
    if color == "black":
        line(d, [(112, 49), (126, 78), (128, 112)], detail, 2.5)
    rr(d, (57, 139, 139, 158), 6, fill, out, ow)
    rr(d, (48, 155, 148, 174), 7, fill, out, ow)
    return finish(im)


def draw_queen(color):
    im, d = piece_canvas(); fill, out, ow, detail = style(color)
    balls = [(51, 43), (75, 31), (96, 25), (117, 31), (141, 43)]
    for x, y in balls:
        ell(d, (x - 7, y - 7, x + 7, y + 7), fill, out, ow)
    poly(d, [(48, 48), (63, 95), (129, 95), (144, 48), (118, 75), (96, 34), (74, 75)], fill, out, ow)
    rr(d, (63, 88, 129, 106), 7, fill, out, ow)
    poly(d, [(69, 102), (123, 102), (130, 145), (62, 145)], fill, out, ow)
    base(d, fill, out, ow, detail)
    if color == "black":
        line(d, [(69, 96), (123, 96)], detail, 2)
        line(d, [(71, 141), (121, 141)], detail, 2)
    return finish(im)


def draw_king(color):
    im, d = piece_canvas(); fill, out, ow, detail = style(color)
    rr(d, (89, 20, 103, 54), 4, fill, out, ow)
    rr(d, (78, 30, 114, 44), 4, fill, out, ow)
    ell(d, (56, 50, 136, 116), fill, out, ow)
    rr(d, (64, 105, 128, 123), 8, fill, out, ow)
    poly(d, [(72, 119), (120, 119), (128, 145), (64, 145)], fill, out, ow)
    base(d, fill, out, ow, detail)
    if color == "black":
        line(d, [(68, 113), (124, 113)], detail, 2)
    return finish(im)


DRAW = {
    "king": draw_king,
    "queen": draw_queen,
    "rook": draw_rook,
    "bishop": draw_bishop,
    "knight": draw_knight,
    "pawn": draw_pawn,
}

for color in ("white", "black"):
    for name, fn in DRAW.items():
        fn(color).save(OUT / f"{color}_{name}.png", optimize=True)

print(f"Generated {len(DRAW) * 2} chess piece PNGs in {OUT}")
