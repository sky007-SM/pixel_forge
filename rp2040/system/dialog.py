# ============================================================
# Box: a small overlay drawn row by row from rectangles and 1-bit text,
# so a pause menu or dialog needs no pixel buffer at all.
# The renderer calls draw_row(buf, y) for every screen row the box covers.
# ============================================================
import config
from config import rgb
from hardware.display import P16
from system.renderer import fill_span, blit_m
from assets.fonts import Text
from assets.logo import EMBER_ROWS

_CORNER = (3, 1, 1)


class Box:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.it = []

    def clear(self):
        self.it = []

    def rrect(self, x, y, w, h, c):
        """Filled rect with pixel-art rounded corners (box-relative, P16 colour)."""
        self.it.append((y, y + h, 0, x, w, h, c))

    def rect(self, x, y, w, h, c):
        self.it.append((y, y + h, 1, x, w, c, None))

    def text(self, x, y, t, c, rows=None):
        """Text mask at (x, y). c = P16 colour, or rows = 7 P16 colours (one per glyph row)."""
        self.it.append((y, y + t.h, 2, x, t, c, rows))

    def draw_row(self, buf, y):
        k = y - self.y
        bx = self.x
        for it in self.it:
            if it[0] <= k < it[1]:
                kind = it[2]
                if kind == 1:
                    fill_span(buf, bx + it[3], bx + it[3] + it[4], it[5])
                elif kind == 2:
                    t = it[4]
                    r = k - it[0]
                    rows = it[6]
                    col = it[5] if rows is None else rows[r // t.scale]
                    blit_m(buf, bx + it[3], t.addr + r * t.rb, (t.w << 16) | col)
                else:
                    r = k - it[0]
                    h = it[5]
                    if r < 3:
                        ins = _CORNER[r]
                    elif r >= h - 3:
                        ins = _CORNER[h - 1 - r]
                    else:
                        ins = 0
                    fill_span(buf, bx + it[3] + ins, bx + it[3] + it[4] - ins, it[6])


def make_confirm(title, line_a, line_b, w=208, h=84):
    """Dialog: header + two lines of text, centred on screen."""
    c = config
    b = Box((320 - w) // 2, (240 - h) // 2, w, h)
    b.rrect(0, 0, w, h, P16(c.C_EMBER))
    b.rrect(2, 2, w - 4, h - 4, P16(rgb(14, 16, 30)))
    b.rect(4, 4, w - 8, 26, P16(rgb(34, 20, 16)))
    b.rect(4, 30, w - 8, 2, P16(c.C_EMBER_DARK))
    t = Text(title, 2)
    b.text((w - t.w) // 2, 10, t, 0, [P16(x) for x in EMBER_ROWS])
    t = Text(line_a, 1)
    b.text((w - t.w) // 2, 44, t, P16(c.C_TEXT))
    t = Text(line_b, 1)
    b.text((w - t.w) // 2, 60, t, P16(c.C_TEXT_DIM))
    return b
