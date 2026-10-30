# ============================================================
# Loading / leaving screen: rotating pixel spinner + text.
# Shown by the scene manager while a scene is torn down and the next
# one is built in small steps, so the spinner keeps turning.
# The spinner is drawn row by row from 12 squares (no pixel buffer);
# the text is 1-bit, so the whole screen costs about 1 KB.
# ============================================================
import math
import config
from config import rgb
from hardware.display import P16
from system.renderer import make_row, copy_row, fill_span, blit_m
from assets.fonts import Text, text_width
import uctypes

CX = 160
CY = 108
TITLE_Y = 146
SUB_Y = 170
_N = 12
_R = 17

_TAIL = (rgb(255, 224, 110), rgb(255, 170, 44), rgb(232, 112, 28),
         rgb(166, 72, 24), rgb(104, 50, 22), rgb(64, 36, 24))
_IDLE = rgb(34, 28, 32)


class LoadingScreen:
    def __init__(self, title, sub=""):
        c = config
        self.bg = make_row(c.C_BG0)
        self.bg_addr = uctypes.addressof(self.bg)
        self.dx = []
        self.dy = []
        for k in range(_N):
            a = k * 2 * math.pi / _N - math.pi / 2
            self.dx.append(CX + int(round(_R * math.cos(a))))
            self.dy.append(CY + int(round(_R * math.sin(a))))
        self.tail = [P16(x) for x in _TAIL]
        self.idle = P16(_IDLE)
        self.cols = [self.idle] * _N
        self.titles = [Text(title + "." * n, 2) for n in range(4)]
        self.title_x = (320 - text_width(title + "...", 2)) // 2
        self.sub = Text(sub, 1) if sub else None
        self.c_text = P16(c.C_TEXT)
        self.c_dim = P16(c.C_TEXT_DIM)
        self.tick = 0
        self._paint()

    def _paint(self):
        head = (self.tick >> 1) % _N
        n = len(self.tail)
        cols = self.cols
        for k in range(_N):
            d = (head - k) % _N
            cols[k] = self.tail[d] if d < n else self.idle

    def update(self):
        self.tick += 1
        if (self.tick & 1) == 0:
            self._paint()

    def draw(self, r):
        kick = r.kick
        base = r.base
        bg = self.bg_addr
        dx = self.dx
        dy = self.dy
        cols = self.cols
        title = self.titles[(self.tick >> 3) & 3]
        tx = self.title_x
        sub = self.sub
        c_text = self.c_text
        c_dim = self.c_dim
        s0 = r.s0
        s1 = r.s1
        a0 = r.a0
        a1 = r.a1
        y0 = CY - _R - 2
        y1 = CY + _R + 3
        for y in range(240):
            in_sp = y0 <= y < y1
            in_t = TITLE_Y <= y < TITLE_Y + 14
            in_s = sub is not None and SUB_Y <= y < SUB_Y + 7
            if not (in_sp or in_t or in_s):
                kick(base, bg)
                continue
            if y & 1:
                dst = s1
                da = a1
            else:
                dst = s0
                da = a0
            copy_row(dst, bg)
            if in_sp:
                for k in range(_N):
                    yy = dy[k]
                    if yy - 2 <= y <= yy + 2:
                        fill_span(dst, dx[k] - 2, dx[k] + 3, cols[k])
            elif in_t:
                blit_m(dst, tx, title.addr + (y - TITLE_Y) * title.rb, (title.w << 16) | c_text)
            else:
                blit_m(dst, (320 - sub.w) >> 1, sub.addr + (y - SUB_Y) * sub.rb, (sub.w << 16) | c_dim)
            kick(base, da)
