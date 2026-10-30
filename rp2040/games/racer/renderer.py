# ============================================================
# ForgeRacer MENU renderer (scanline, same contract as every scene):
# draw() must emit exactly 240 rows through r.kick().
# A Page (rectangles + 1-bit text + magnified car previews) is drawn over
# 8 background bands. The race view / HUD live in racerview.py and are only
# imported when the first race starts.
# ============================================================
import uctypes
import micropython
from system.renderer import copy_row, make_row
from system.dialog import Box
from games.racer import settings as S
from games.racer import assets as A

SPR = A.SPR


@micropython.viper
def blit_pal3(dst: ptr16, x0: int, src: int, pal: int):
    # same, magnified 3x horizontally (the caller repeats each source row 3x); no shadow
    s = ptr8(src)
    p = ptr16(pal)
    i = 0
    while i < 28:
        k = int(s[i])
        if k != 0 and k != 9:
            v = int(p[k])
            if v != 1:
                x = x0 + i * 3
                if x >= 0 and x < 318:
                    dst[x] = v
                    dst[x + 1] = v
                    dst[x + 2] = v
        i += 1


# ---------------- menu pages ----------------
class Page(Box):
    """Full-screen list of rectangles / 1-bit text / magnified car previews.
    `hit` marks the rows that hold anything, so empty rows go straight to the DMA."""

    def __init__(self):
        Box.__init__(self, 0, 0, 320, 240)
        self.hit = bytearray(240)
        self.cl = []

    def clear(self):
        Box.clear(self)
        for i in range(240):
            self.hit[i] = 0
        self.cl = []

    def _mark(self, y0, y1):
        if y0 < 0:
            y0 = 0
        if y1 > 240:
            y1 = 240
        h = self.hit
        for y in range(y0, y1):
            h[y] = 1

    def rect(self, x, y, w, h, c):
        Box.rect(self, x, y, w, h, c)
        self._mark(y, y + h)

    def text(self, x, y, t, c, rows=None):
        Box.text(self, x, y, t, c, rows)
        self._mark(y, y + t.h)

    def car(self, x, y, frame_addr, pal_addr):
        self.cl.append((x, y, frame_addr, pal_addr))
        self._mark(y, y + SPR * 3)

    def draw_row(self, buf, y):
        Box.draw_row(self, buf, y)
        for c in self.cl:
            if c[1] <= y < c[1] + SPR * 3:
                blit_pal3(buf, c[0], c[2] + ((y - c[1]) // 3) * SPR, c[3])


class MenuView:
    def __init__(self):
        self.page = Page()
        self.bands = [make_row(c) for c in S.MENU_BG]
        n = len(self.bands)
        self.bga = [uctypes.addressof(self.bands[(y * n) // 240]) for y in range(240)]

    def clear(self):
        self.page.clear()

    def draw(self, r):
        kick = r.kick
        base = r.base
        cov = r.cover if r.cov_on else None
        cov_addr = r.cover_addr
        page = self.page
        hit = page.hit
        bga = self.bga
        s0 = r.s0
        s1 = r.s1
        a0 = r.a0
        a1 = r.a1
        for y in range(240):
            if cov is not None and cov[y]:
                kick(base, cov_addr)
                continue
            if hit[y]:
                if y & 1:
                    dst = s1
                    da = a1
                else:
                    dst = s0
                    da = a0
                copy_row(dst, bga[y])
                page.draw_row(dst, y)
                kick(base, da)
            else:
                kick(base, bga[y])


