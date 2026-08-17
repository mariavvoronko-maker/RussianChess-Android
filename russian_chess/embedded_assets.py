from __future__ import annotations

import base64
import io
import math
import struct
import wave
import zlib

SIZE = 192


def _png_bytes(kind: str, white: bool) -> bytes:
    w = h = SIZE
    pix = bytearray(w * h * 4)
    fill = (246, 246, 239, 255) if white else (18, 20, 24, 255)
    edge = (18, 18, 20, 255)

    def put(x: int, y: int, c):
        if 0 <= x < w and 0 <= y < h:
            i = (y * w + x) * 4
            pix[i:i+4] = bytes(c)

    def rect(x0, y0, x1, y1, c):
        for y in range(max(0, y0), min(h, y1)):
            for x in range(max(0, x0), min(w, x1)):
                i = (y*w+x)*4
                pix[i:i+4] = bytes(c)

    def circle(cx, cy, r, c):
        rr = r*r
        for y in range(max(0, cy-r), min(h, cy+r+1)):
            dy = (y-cy)*(y-cy)
            for x in range(max(0, cx-r), min(w, cx+r+1)):
                if (x-cx)*(x-cx)+dy <= rr:
                    put(x, y, c)

    def poly(points, c):
        ys = [p[1] for p in points]
        for y in range(max(0, min(ys)), min(h-1, max(ys))+1):
            xs = []
            for i, p1 in enumerate(points):
                p2 = points[(i+1) % len(points)]
                if p1[1] == p2[1]:
                    continue
                if min(p1[1], p2[1]) <= y < max(p1[1], p2[1]):
                    x = p1[0] + (y-p1[1])*(p2[0]-p1[0])/(p2[1]-p1[1])
                    xs.append(x)
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2]):
                rect(math.ceil(a), y, math.floor(b)+1, y+1, c)

    def outline_rect(x0, y0, x1, y1, t=3):
        if white:
            rect(x0-t, y0-t, x1+t, y1+t, edge)
        rect(x0, y0, x1, y1, fill)

    def outline_circle(cx, cy, r, t=3):
        if white:
            circle(cx, cy, r+t, edge)
        circle(cx, cy, r, fill)

    def outline_poly(points, t=3):
        if white:
            for dx, dy in ((-t,0),(t,0),(0,-t),(0,t),(-2,-2),(2,2),(-2,2),(2,-2)):
                poly([(x+dx, y+dy) for x, y in points], edge)
        poly(points, fill)

    outline_rect(40,154,152,172,3)
    outline_rect(50,139,142,154,3)

    if kind == 'pawn':
        outline_rect(72,91,120,141,3)
        outline_circle(96,70,24,3)
    elif kind == 'rook':
        outline_rect(58,68,134,140,3)
        outline_rect(55,50,75,73,3)
        outline_rect(86,50,106,73,3)
        outline_rect(117,50,137,73,3)
    elif kind == 'knight':
        outline_poly([(60,140),(132,140),(118,111),(126,72),(102,42),(91,59),(72,47),(76,73),(55,97)],3)
        outline_circle(105,65,9,2)
        circle(109,63,2,edge if white else (230,230,225,255))
    elif kind == 'bishop':
        outline_rect(70,101,122,141,3)
        outline_circle(96,75,28,3)
        for k in range(-2,3):
            for x in range(86,111):
                y = 55 + (x-86) + k
                put(x, y, edge if white else (245,245,240,255))
    elif kind == 'queen':
        outline_rect(65,91,127,141,3)
        outline_poly([(65,96),(57,58),(78,79),(86,48),(96,78),(108,47),(115,79),(137,58),(127,96)],3)
        for cx, cy in ((57,55),(86,45),(108,44),(137,55)):
            outline_circle(cx,cy,8,2)
    elif kind == 'king':
        outline_rect(67,91,125,141,3)
        outline_circle(96,82,28,3)
        outline_rect(91,35,101,67,3)
        outline_rect(78,45,114,55,3)

    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw.extend(pix[y*w*4:(y+1)*w*4])

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag+data) & 0xffffffff)

    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(bytes(raw), 9)) +
            chunk(b'IEND', b''))


def _wav_bytes(freq: float, duration: float, volume: float) -> bytes:
    rate = 22050
    count = int(rate * duration)
    frames = bytearray()
    for i in range(count):
        env = max(0.0, 1.0-i/count)**2
        sample = int(32767*volume*env*math.sin(2*math.pi*freq*i/rate))
        frames.extend(struct.pack('<h', sample))
    out = io.BytesIO()
    with wave.open(out, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(frames)
    return out.getvalue()


ASSETS_B64 = {}
for color, white in [('white', True), ('black', False)]:
    for kind in ('king','queen','rook','bishop','knight','pawn'):
        ASSETS_B64[f'pieces/{color}_{kind}.png'] = base64.b64encode(_png_bytes(kind, white)).decode('ascii')
ASSETS_B64['sounds/move.wav'] = base64.b64encode(_wav_bytes(520.0, 0.075, 0.38)).decode('ascii')
ASSETS_B64['sounds/capture.wav'] = base64.b64encode(_wav_bytes(330.0, 0.11, 0.46)).decode('ascii')
