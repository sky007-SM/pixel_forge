# ============================================================
# Menu preview art (104 x 78), drawn with rectangles on demand into ONE shared buffer
# ============================================================
from config import rgb
from hardware.display import P16
from system.renderer import Sprite

TW = 104
TH = 78


def _c(r, g, b):
    return P16(rgb(r, g, b))


def _flappy(s):
    s.rect(0, 0, TW, 34, _c(70, 190, 235))
    s.rect(0, 34, TW, 28, _c(112, 208, 240))
    s.rect(0, 62, TW, 10, _c(160, 226, 244))
    s.rect(82, 7, 12, 12, _c(255, 224, 70))
    s.rect(80, 9, 16, 8, _c(255, 224, 70))
    s.rect(10, 18, 26, 7, _c(255, 255, 255))
    s.rect(16, 14, 14, 6, _c(255, 255, 255))
    s.rect(50, 30, 20, 6, _c(255, 255, 255))
    s.rect(54, 26, 10, 5, _c(255, 255, 255))
    dk, md, lt = _c(40, 110, 24), _c(90, 190, 50), _c(150, 235, 90)
    s.rect(64, 0, 20, 24, dk)
    s.rect(67, 0, 4, 22, lt)
    s.rect(72, 0, 8, 22, md)
    s.rect(61, 22, 26, 8, dk)
    s.rect(63, 24, 22, 4, md)
    s.rect(64, 50, 20, 22, dk)
    s.rect(67, 56, 4, 16, lt)
    s.rect(72, 56, 8, 16, md)
    s.rect(61, 46, 26, 8, dk)
    s.rect(63, 48, 22, 4, md)
    s.rect(0, 72, TW, 6, _c(230, 200, 120))
    s.rect(0, 70, TW, 3, _c(110, 200, 60))
    s.rect(18, 36, 20, 16, _c(24, 24, 60))
    s.rect(20, 38, 16, 12, _c(255, 224, 40))
    s.rect(20, 43, 8, 5, _c(252, 128, 0))
    s.rect(30, 39, 5, 5, _c(255, 255, 255))
    s.rect(33, 41, 2, 2, _c(0, 0, 0))
    s.rect(36, 43, 8, 4, _c(252, 128, 0))


def _tet(s):
    s.rect(0, 0, TW, TH, _c(12, 14, 26))
    s.rect(16, 2, 66, 74, _c(60, 70, 110))
    s.rect(18, 4, 62, 70, _c(8, 10, 20))
    pal = {
        "c": (0, 220, 230), "y": (240, 220, 40), "p": (170, 70, 210),
        "g": (70, 210, 80), "r": (230, 60, 60), "b": (60, 90, 230), "o": (240, 150, 40),
    }

    def cell(cx, cy, k):
        r, g, b = pal[k]
        x = 20 + cx * 6
        y = 6 + cy * 6
        s.rect(x, y, 6, 6, _c(r, g, b))
        s.rect(x, y, 6, 1, _c(min(255, r + 70), min(255, g + 70), min(255, b + 70)))
        s.rect(x, y, 1, 6, _c(min(255, r + 40), min(255, g + 40), min(255, b + 40)))
        s.rect(x + 5, y + 1, 1, 5, _c(r // 2, g // 2, b // 2))
        s.rect(x + 1, y + 5, 5, 1, _c(r // 2, g // 2, b // 2))

    grid = (
        "          ", "   ppp    ", "    p     ", "          ", "          ",
        "          ", "      gg  ", "  oo ggyy ", "rroo cccyy", "brrggbbcpp",
        "bbggggbbpp",
    )
    for ry in range(len(grid)):
        line = grid[ry]
        for rx in range(10):
            if line[rx] != " ":
                cell(rx, ry, line[rx])
    s.rect(88, 6, 12, 28, _c(30, 34, 60))
    for yy in (10, 16, 22):
        s.rect(90, yy, 8, 4, _c(0, 220, 230))


def _racer(s):
    s.rect(0, 0, TW, 30, _c(255, 150, 70))
    s.rect(0, 12, TW, 18, _c(255, 190, 90))
    s.rect(70, 8, 16, 16, _c(255, 236, 140))
    for i in range(18):
        s.rect(6 + i, 30 - i - 4, 36 - 2 * i if 36 - 2 * i > 0 else 1, 1, _c(120, 60, 110))
    for i in range(14):
        s.rect(52 + i, 30 - i - 3, 40 - 2 * i if 40 - 2 * i > 0 else 1, 1, _c(150, 70, 110))
    s.rect(0, 30, TW, 2, _c(40, 150, 70))
    cx = 52
    for y in range(32, TH):
        t = (y - 32) * 100 // (TH - 33)
        half = 3 + (t * 44) // 100
        band = ((y * 3) // 7) & 1
        s.rect(0, y, TW, 1, _c(40, 150, 70) if band else _c(30, 125, 56))
        rb = half + 3 + t // 25
        s.rect(cx - rb, y, rb * 2, 1, _c(235, 235, 235) if band else _c(220, 40, 40))
        s.rect(cx - half, y, half * 2, 1, _c(96, 98, 108) if band else _c(84, 86, 96))
        if band:
            lw = 1 + t // 30
            s.rect(cx - lw // 2, y, lw, 1, _c(240, 240, 240))
    s.rect(40, 60, 24, 12, _c(220, 30, 40))
    s.rect(42, 56, 20, 6, _c(180, 20, 30))
    s.rect(44, 57, 16, 4, _c(150, 220, 250))
    s.rect(38, 68, 6, 6, _c(20, 20, 24))
    s.rect(60, 68, 6, 6, _c(20, 20, 24))
    s.rect(42, 62, 4, 2, _c(255, 240, 150))
    s.rect(58, 62, 4, 2, _c(255, 240, 150))


def _plat(s):
    s.rect(0, 0, TW, 40, _c(92, 148, 252))
    s.rect(0, 40, TW, 22, _c(140, 190, 255))
    s.rect(8, 10, 24, 6, _c(255, 255, 255))
    s.rect(12, 6, 14, 5, _c(255, 255, 255))
    s.rect(64, 16, 22, 6, _c(255, 255, 255))
    for i in range(14):
        s.rect(60 + i, 62 - i * 2, 30 - 2 * i, 2, _c(50, 150, 70))
    for i in range(10):
        s.rect(0 + i, 62 - i * 2, 34 - 2 * i, 2, _c(70, 170, 80))
    s.rect(0, 62, TW, 16, _c(176, 96, 48))
    s.rect(0, 60, TW, 4, _c(90, 200, 60))
    for x in range(0, TW, 13):
        s.rect(x, 66, 12, 1, _c(130, 64, 30))
        s.rect(x + 6, 72, 12, 1, _c(130, 64, 30))
    s.rect(10, 40, 26, 6, _c(200, 90, 40))
    s.rect(10, 40, 26, 1, _c(240, 150, 80))
    s.rect(56, 28, 30, 6, _c(200, 90, 40))
    s.rect(56, 28, 30, 1, _c(240, 150, 80))
    for cx, cy in ((18, 30), (66, 18), (74, 18)):
        s.rect(cx, cy, 6, 8, _c(255, 214, 40))
        s.rect(cx + 2, cy + 1, 2, 6, _c(255, 245, 150))
    s.rect(44, 46, 10, 14, _c(40, 80, 220))
    s.rect(44, 42, 10, 6, _c(250, 200, 160))
    s.rect(43, 40, 12, 3, _c(220, 40, 40))
    s.rect(50, 44, 2, 2, _c(0, 0, 0))
    s.rect(44, 58, 4, 3, _c(120, 60, 20))
    s.rect(50, 58, 4, 3, _c(120, 60, 20))
    s.rect(80, 52, 10, 8, _c(150, 80, 40))
    s.rect(82, 54, 2, 2, _c(255, 255, 255))
    s.rect(86, 54, 2, 2, _c(255, 255, 255))


_DRAW = (_flappy, _tet, _racer, _plat)


def new():
    """The one shared preview buffer (TW x TH, banded so it needs no big block)."""
    return Sprite(TW, TH, 0)


def build_into(s, index):
    """Draw game `index`'s preview into the shared buffer (about 5 ms)."""
    _DRAW[index](s)
