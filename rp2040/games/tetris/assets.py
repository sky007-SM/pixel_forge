# ============================================================
# Tetris art. Nothing big is kept in memory:
#   * 8 block sprites (11x11, 242 bytes each) + a ghost outline
#   * 14 pre-drawn 116 px lines of the empty playfield (frame + cell pattern)
# The board itself is drawn straight from the 10x20 colour array each frame.
# ============================================================
import array
import config
from config import rgb
from hardware.display import P16
from system.renderer import Sprite, TRANS
from system.dialog import Box
from assets.fonts import Text
from games.tetris import settings as S

CELL = S.CELL
COLS = S.COLS
ROWS = S.ROWS
FR = S.FRAME


def _mix(raw, k):
    """Lighten (k > 0) or darken (k < 0) an RGB565 colour, k in -255..255."""
    r = (raw >> 11) & 31
    g = (raw >> 5) & 63
    b = raw & 31
    if k >= 0:
        r += (31 - r) * k // 255
        g += (63 - g) * k // 255
        b += (31 - b) * k // 255
    else:
        r = r * (255 + k) // 255
        g = g * (255 + k) // 255
        b = b * (255 + k) // 255
    return (r << 11) | (g << 5) | b


def make_block(raw):
    s = Sprite(CELL, CELL, 0)
    s.rect(0, 0, 11, 11, P16(_mix(raw, -170)))
    s.rect(1, 1, 9, 9, P16(raw))
    s.rect(1, 1, 9, 1, P16(_mix(raw, 120)))
    s.rect(1, 1, 1, 9, P16(_mix(raw, 90)))
    s.rect(9, 2, 1, 8, P16(_mix(raw, -90)))
    s.rect(2, 9, 8, 1, P16(_mix(raw, -90)))
    s.rect(3, 3, 2, 2, P16(_mix(raw, 200)))
    return s


def make_blocks():
    """Index 0 unused, 1..7 piece colours."""
    return [None] + [make_block(c) for c in S.COLORS]


def make_ghost():
    s = Sprite(CELL, CELL, TRANS)
    c = P16(rgb(96, 104, 140))
    s.rect(0, 0, 11, 1, c)
    s.rect(0, 10, 11, 1, c)
    s.rect(0, 0, 1, 11, c)
    s.rect(10, 0, 1, 11, c)
    return s


def make_strips():
    """strips[0..2] = top frame lines (outer, mid, inner); strips[3..13] = the 11 lines of an
    empty cell row, frame sides included. Bottom frame lines reuse strips[2], [1], [0]."""
    w = S.GRID_W
    c_out = P16(config.C_EMBER_DARK)
    c_mid = P16(config.C_EMBER)
    c_in = P16(rgb(60, 26, 12))
    empty = P16(rgb(8, 10, 18))
    line = P16(rgb(17, 21, 36))
    strips = []
    top0 = array.array("H", [c_out] * w)                       # nested frame: outer / mid / inner
    top1 = array.array("H", [c_mid] * w)
    top1[0] = c_out
    top1[w - 1] = c_out
    top2 = array.array("H", [c_in] * w)
    top2[0] = c_out
    top2[1] = c_mid
    top2[w - 2] = c_mid
    top2[w - 1] = c_out
    strips.append(top0)
    strips.append(top1)
    strips.append(top2)
    for m in range(CELL):
        a = array.array("H", [empty] * w)
        a[0] = c_out
        a[1] = c_mid
        a[2] = c_in
        a[w - 3] = c_in
        a[w - 2] = c_mid
        a[w - 1] = c_out
        for cx in range(COLS):
            x0 = FR + cx * CELL
            if m == CELL - 1:
                for xx in range(CELL):
                    a[x0 + xx] = line
            else:
                a[x0 + CELL - 1] = line
        strips.append(a)
    return strips


def make_backgrounds():
    """plain row, panel row (both side strips), panel edge row."""
    from system.renderer import make_row, fill_span
    c = config
    plain = make_row(c.C_BG0)
    panel = make_row(c.C_BG0)
    edge = make_row(c.C_BG0)
    pc = P16(c.C_PANEL)
    ec = P16(c.C_EMBER_DARK)
    for (x0, x1) in ((8, 97), (224, 313)):
        fill_span(panel, x0, x1, pc)
        fill_span(panel, x0, x0 + 1, ec)
        fill_span(panel, x1 - 1, x1, ec)
        fill_span(edge, x0, x1, ec)
    return plain, panel, edge


def make_box(w, h, lines):
    """Centred message box. lines = [(text, scale, rgb565 colour, y)]."""
    c = config
    b = Box((320 - w) // 2, (240 - h) // 2, w, h)
    b.rect(0, 0, w, h, P16(c.C_EMBER))
    b.rect(2, 2, w - 4, h - 4, P16(c.C_BG0))
    for (text, scale, color, y) in lines:
        t = Text(text, scale)
        b.text((w - t.w) // 2, y, t, P16(color))
    return b
