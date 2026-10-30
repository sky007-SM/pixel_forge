# ============================================================
# Boot scene: molten anvil, rising embers, PIXELFORGE wordmark and a
# loading bar over a warm radial glow. No button needed: it fades in,
# holds ~3 s while the bar fills, then fades into the menu.
#
# Memory: only the anvil is a pixel buffer (13 KB, in 4 KB bands). The
# title is a 1-bit mask, embers and the bar are drawn from rectangles,
# and this whole module is unloaded after boot (PURGE).
# ============================================================
import math, random, uctypes
import config
from config import rgb
from hardware.display import P16
from system.renderer import Sprite, make_row, fill_span, fill_h, copy_row, blit_t, blit_m
from system.scene_manager import Scene
from system.transitions import ease

PURGE = ("system.boot",)

ANV_X = 108
ANV_Y = 70
TITLE_Y = 142
BAR_X = 70
BAR_Y = 190
BAR_W = 180
GLOW_CX = 160
GLOW_CY = 112

F_BAR0 = 8                   # frames at 30 fps
F_BAR1 = 98                  # bar full (~3 s after it starts)
F_END = 104                  # then fade into the menu


def _lerp(a, b, k, n):
    return a + (b - a) * k // n


def _mix(c0, c1, k, n):
    return (_lerp(c0[0], c1[0], k, n), _lerp(c0[1], c1[1], k, n), _lerp(c0[2], c1[2], k, n))


def _p(t):
    return P16(rgb(t[0], t[1], t[2]))


# ------------------------------------------------------------
# Anvil icon (104 x 64): flat-shaded rows, molten gold -> orange on the face
# and horn, cooling into charcoal; bevels on the body.
# ------------------------------------------------------------
ANV_W = 104
ANV_H = 64
_CX = 66
_GLOW = (
    (255, 238, 160), (255, 214, 92), (255, 190, 62), (255, 160, 42),
    (255, 128, 28), (232, 100, 30), (188, 80, 34), (140, 64, 40),
    (104, 56, 54), (84, 64, 80), (68, 70, 86), (56, 60, 74),
)


def _anvil_spans():
    sp = [None] * ANV_H
    for y in range(4, 16):                         # horn + top face
        if y <= 11:
            xl = 30 - 4 * (y - 4)
        else:
            xl = (6, 13, 21, 30)[y - 12]
        sp[y] = (xl, 98)
    for y in range(16, 43):                        # lip + waist
        hw = 15 + ((y - 32) * (y - 32) * 13) // 256
        if y < 18:
            hw = 30
        sp[y] = (_CX - hw, _CX + hw)
    for y in range(43, 51):                        # foot
        hw = 20 + (y - 43)
        sp[y] = (_CX - hw, _CX + hw)
    for y in range(51, 62):                        # base plate
        sp[y] = (_CX - 34, _CX + 34)
    return sp


def make_anvil():
    s = Sprite(ANV_W, ANV_H)
    ra = s.ra
    sp = _anvil_spans()
    body_hi = (84, 90, 108)
    body_lo = (34, 36, 46)
    for y in range(ANV_H):
        if sp[y] is None:
            continue
        x0, x1 = sp[y]
        n = x1 - x0 + 1
        a = ra[y]
        if y < 16:
            c = _p(_GLOW[y - 4])
            if 6 <= y <= 12:                       # dithered cooling rows
                c2 = _p(_GLOW[y - 3])
                x = x0
                while x <= x1:
                    cc = c if ((x >> 1) + y) & 1 == 0 else c2
                    fill_h(a, x, 2 if x + 1 <= x1 else 1, cc)
                    x += 2
            else:
                fill_h(a, x0, n, c)
        else:
            c3 = _mix(body_hi, body_lo, y - 16, 45)
            if y == 16:
                c3 = (150, 158, 176)               # steel edge under the molten face
            elif y == 17:
                c3 = (40, 42, 52)                  # shadow under the lip
            fill_h(a, x0, n, _p(c3))
            if y >= 18:
                lite = _mix(c3, (170, 178, 196), 1, 3)
                fill_h(a, x0, 2, _p(lite))                                  # left bevel
                fill_h(a, x0 + 2, 1, _p(_mix(c3, (170, 178, 196), 1, 8)))
                fill_h(a, x1 - 1, 2, _p(_mix(c3, (10, 10, 14), 1, 2)))      # right shade
                if 21 <= y <= 40:                  # specular streak on the waist
                    fill_h(a, _CX - 9, 2, _p(_mix(c3, (190, 198, 214), 1, 4)))
            if y == 51:
                fill_h(a, x0, n, _p((120, 128, 146)))                       # base plate top edge
            if y == 61:
                fill_h(a, x0, n, _p((18, 18, 24)))                          # bottom edge
    for y in range(4, 16):
        x0, x1 = sp[y]
        fill_h(ra[y], x1 - 1, 2, _p(_mix(_GLOW[y - 4], (20, 12, 8), 1, 4)))
    return s


# ------------------------------------------------------------
# Wordmark: bold chamfered 7x10-cell glyphs as a 1-bit mask (about 1 KB)
# ------------------------------------------------------------
_TEXT = "PIXELFORGE"
_G = {
    "P": ("#######", "#######", "##...##", "##...##", "#######", "#######", "##.....", "##.....", "##.....", "##....."),
    "I": ("##", "##", "##", "##", "##", "##", "##", "##", "##", "##"),
    "X": ("##....##", ".##..##.", ".##..##.", "..####..", "...##...", "...##...", "..####..", ".##..##.", ".##..##.", "##....##"),
    "E": ("######", "######", "##....", "##....", "#####.", "#####.", "##....", "##....", "######", "######"),
    "L": ("##....", "##....", "##....", "##....", "##....", "##....", "##....", "##....", "######", "######"),
    "F": ("######", "######", "##....", "##....", "#####.", "#####.", "##....", "##....", "##....", "##...."),
    "O": ("#######", "#######", "##...##", "##...##", "##...##", "##...##", "##...##", "##...##", "#######", "#######"),
    "R": ("######.", "#######", "##...##", "##...##", "######.", "######.", "##..##.", "##...##", "##...##", "##...##"),
    "G": ("#######", "#######", "##.....", "##.....", "##.####", "##.####", "##...##", "##...##", "#######", "#######"),
}
_DIRS = ((-1, -1), (1, -1), (-1, 1), (1, 1))
_TS = 3                        # glyph scale
_GAP = 2                       # cells between letters


def _glyph(rows):
    h = len(rows)
    w = len(rows[0])
    g = [[1 if ch == "#" else 0 for ch in r] for r in rows]

    def f(x, y):
        return 1 if (0 <= x < w and 0 <= y < h and g[y][x]) else 0

    def inb(x, y):
        return 0 <= x < w and 0 <= y < h

    out = [r[:] for r in g]
    for y in range(h):
        for x in range(w):
            for dx, dy in _DIRS:
                if g[y][x]:
                    # outer corner of a stroke at least 3 cells long both ways: cut it
                    if (not f(x + dx, y) and not f(x, y + dy) and
                            f(x - dx, y) and f(x - 2 * dx, y) and f(x, y - dy) and f(x, y - 2 * dy)):
                        out[y][x] = 0
                else:
                    # inner corner of a counter at least 3 cells wide and tall: fill it
                    if (f(x + dx, y) and f(x, y + dy) and f(x + dx, y + dy) and
                            inb(x - 2 * dx, y) and inb(x, y - 2 * dy) and
                            not f(x - dx, y) and not f(x - 2 * dx, y) and
                            not f(x, y - dy) and not f(x, y - 2 * dy)):
                        out[y][x] = 1
    return out


class _Mask:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.rb = (w + 7) >> 3
        self.buf = bytearray(self.rb * h)
        self.addr = uctypes.addressof(self.buf)

    def fill(self, x, y, w, h):
        buf = self.buf
        rb = self.rb
        for yy in range(y, y + h):
            o = yy * rb
            for xx in range(x, x + w):
                buf[o + (xx >> 3)] |= 0x80 >> (xx & 7)


def make_title():
    glyphs = [_glyph(_G[ch]) for ch in _TEXT]
    cells_w = sum(len(g[0]) for g in glyphs) + _GAP * (len(glyphs) - 1)
    m = _Mask(cells_w * _TS, 10 * _TS)
    cx = 0
    for g in glyphs:
        for gy in range(10):
            row = g[gy]
            gx = 0
            wg = len(row)
            while gx < wg:
                if row[gx]:
                    e = gx
                    while e < wg and row[e]:
                        e += 1
                    m.fill((cx + gx) * _TS, gy * _TS, (e - gx) * _TS, _TS)
                    gx = e
                else:
                    gx += 1
        cx += len(g[0]) + _GAP
    return m


_TOP = (255, 228, 124)
_BOT = (232, 146, 34)


# ------------------------------------------------------------
# Embers: square pixels that burst up from the anvil face, shrink and get
# hotter (gold -> pale) as they rise, with a growing glow halo. Drawn from
# rectangles each row, so they need no pixel layer.
# ------------------------------------------------------------
_SIN = (0, 6, 11, 14, 16, 14, 11, 6, 0, -6, -11, -14, -16, -14, -11, -6)
_CORE = ((255, 128, 30), (255, 176, 52), (255, 214, 96), (255, 238, 160))
_HALO = ((64, 28, 14), (96, 42, 16), (126, 58, 20), (150, 72, 26))


class Embers:
    def __init__(self, x_lo, x_hi, base_y, n=24):
        self.n = n
        self.x_lo = x_lo
        self.x_hi = x_hi
        self.base_y = base_y
        self.core = [_p(c) for c in _CORE]
        self.halo = [_p(c) for c in _HALO]
        self.x0 = [0] * n
        self.vy = [0] * n
        self.life = [1] * n
        self.age = [0] * n
        self.amp = [0] * n
        self.ph = [0] * n
        self.ex = [0] * n          # current screen position / size / colours
        self.ey = [-99] * n
        self.es = [0] * n
        self.ec = [0] * n
        self.eh = [0] * n
        for i in range(n):
            self._spawn(i)
            self.age[i] = random.randint(0, self.life[i] - 1)

    def _spawn(self, i):
        self.x0[i] = random.randint(self.x_lo, self.x_hi)
        self.vy[i] = random.randint(16, 30)
        self.life[i] = random.randint(40, 72)
        self.age[i] = 0
        self.amp[i] = random.randint(0, 5)
        self.ph[i] = random.randint(0, 15)

    def update(self):
        for i in range(self.n):
            a = self.age[i] + 1
            if a >= self.life[i]:
                self._spawn(i)
                self.ey[i] = -99
                continue
            self.age[i] = a
            t = a * 100 // self.life[i]
            self.ey[i] = self.base_y - (a * self.vy[i]) // 16
            self.ex[i] = self.x0[i] + (_SIN[(a + self.ph[i]) & 15] * self.amp[i]) // 16
            size = 5 if t < 12 else (4 if t < 28 else (3 if t < 50 else (2 if t < 75 else 1)))
            k = 0 if t < 25 else (1 if t < 50 else (2 if t < 75 else 3))
            self.es[i] = size
            self.ec[i] = self.core[k]
            self.eh[i] = self.halo[k] if (size >= 2 or k >= 2) else 0


def make_rings(cx, cy, rx, ry, n=7):
    """Concentric glow ellipses (outer -> inner): per-row half widths as bytes + colours."""
    hws = []
    cols = []
    c0 = (14, 14, 26)
    c1 = (96, 46, 18)
    for i in range(n):
        f = (n - i) / n
        a = int(rx * f)
        b = int(ry * f)
        hw = bytearray(240)
        for y in range(240):
            dy = y - cy
            if dy < 0:
                dy = -dy
            if dy <= b and b:
                v = int(a * math.sqrt(1.0 - (dy * dy) / (b * b)))
                hw[y] = v if v < 255 else 255
        hws.append(hw)
        cc = _mix(c0, c1, i + 1, n + 1)
        cols.append(P16(rgb(cc[0], cc[1], cc[2])))
    return hws, cols


_BAR_INSET = (3, 1, 0, 0, 0, 0, 1, 3)


class BootScene(Scene):
    PURGE = PURGE

    def __init__(self, ctx, next_scene):
        self.ctx = ctx
        self._next = next_scene

    def enter(self, ctx):
        self.ctx = ctx
        c = config
        self.f = 0
        self.left = False
        self.anvil = make_anvil()                       # biggest allocation first
        self.bg = make_row(c.C_BG0)
        self.bg_addr = uctypes.addressof(self.bg)
        self.ring_hw, self.ring_col = make_rings(GLOW_CX, GLOW_CY, 170, 120)
        self.title = make_title()
        self.tx = (320 - self.title.w - 3) >> 1
        n = 10 * _TS
        self.t_rows = [_p(_mix(_TOP, _BOT, y, n - 1)) for y in range(n)]
        self.t_shadow = _p((62, 28, 10))
        self.embers = Embers(138, 206, ANV_Y + 2)
        # loading bar colours: row 1 highlight, rows 2-5 body, row 6 shade; 12 gradient segments
        c0 = (255, 206, 70)
        c1 = (255, 108, 24)
        self.bar_seg = []
        for rt in range(3):
            row = []
            for j in range(12):
                col = _mix(c0, c1, j, 11)
                if rt == 0:
                    col = _mix(col, (255, 244, 190), 1, 2)
                elif rt == 2:
                    col = _mix(col, (120, 40, 10), 1, 3)
                row.append(_p(col))
            self.bar_seg.append(row)
        self.bar_edge = _p((70, 46, 30))
        self.bar_body = _p((26, 20, 24))
        ctx.r.set_fx(4)

    def update(self, dt, inp):
        f = self.f + 1
        self.f = f
        r = self.ctx.r
        self.embers.update()
        if f == 3:                               # anvil strike, then the start-up tune
            au = self.ctx.audio
            au.sfx("clang")
            au.music("boot", False)
        lvl = 4 - (f >> 1)                      # fade in over ~8 frames
        r.set_fx(lvl if lvl > 0 else 0)
        v = f * 5 if f < 36 else 180
        self.ctx.led.set_base(v, v // 4, 0)
        if f >= F_END and not self.left:
            self.left = True
            self.ctx.sm.goto(lambda: self._next(self.ctx), "fade", None)

    def exit(self):
        self.ctx.led.off()
        self.ctx.r.set_fx(0)
        self.anvil = self.title = self.embers = self.ring_hw = None
        self.bar_seg = self.t_rows = None

    def draw(self, r):
        kick = r.kick
        base = r.base
        f = self.f
        bg = self.bg_addr
        ring_hw = self.ring_hw
        ring_col = self.ring_col
        n_ring = len(ring_hw)
        an = self.anvil
        anr = an.ra
        ti = self.title
        ti_rb = ti.rb
        ti_w = ti.w << 16
        t_rows = self.t_rows
        t_sh = self.t_shadow
        tx = self.tx
        em = self.embers
        ex = em.ex
        ey = em.ey
        es = em.es
        ec = em.ec
        eh = em.eh
        ne = em.n
        bar_seg = self.bar_seg
        b_edge = self.bar_edge
        b_body = self.bar_body
        if f <= F_BAR0:
            p = 0.0
        elif f >= F_BAR1:
            p = 1.0
        else:
            p = ease((f - F_BAR0) / (F_BAR1 - F_BAR0))
        fw = int(BAR_W * p)
        s0 = r.s0
        s1 = r.s1
        a0 = r.a0
        a1 = r.a1
        for y in range(240):
            if y & 1:
                dst = s1
                da = a1
            else:
                dst = s0
                da = a0
            copy_row(dst, bg)
            for i in range(n_ring):
                hw = ring_hw[i][y]
                if y & 1:
                    hw -= 2                  # offset odd rows: dithers the ring edges
                if hw > 0:
                    fill_span(dst, GLOW_CX - hw, GLOW_CX + hw, ring_col[i])
            if y < ANV_Y + 6:
                for i in range(ne):          # embers
                    y0 = ey[i]
                    sz = es[i]
                    if y0 - 1 <= y <= y0 + sz:
                        h = eh[i]
                        if h:
                            fill_span(dst, ex[i] - 1, ex[i] + sz + 1, h)
                        if y0 <= y < y0 + sz:
                            fill_span(dst, ex[i], ex[i] + sz, ec[i])
            if ANV_Y <= y < ANV_Y + 64:
                blit_t(dst, ANV_X, anr[y - ANV_Y], 104)
            if TITLE_Y <= y < TITLE_Y + 33:
                k = y - TITLE_Y
                if k >= 3:
                    blit_m(dst, tx + 3, ti.addr + (k - 3) * ti_rb, ti_w | t_sh)
                if k < 30:
                    blit_m(dst, tx, ti.addr + k * ti_rb, ti_w | t_rows[k])
            if BAR_Y <= y < BAR_Y + 8:
                k = y - BAR_Y
                ins = _BAR_INSET[k]
                x0 = BAR_X + ins
                x1 = BAR_X + BAR_W - ins
                if k == 0 or k == 7:
                    fill_span(dst, x0, x1, b_edge)
                else:
                    fill_span(dst, x0, x1, b_body)
                    fill_span(dst, x0, x0 + 1, b_edge)
                    fill_span(dst, x1 - 1, x1, b_edge)
                    if fw:
                        seg = bar_seg[0 if k == 1 else (2 if k == 6 else 1)]
                        lo = ins + 1
                        hi = BAR_W - ins - 1
                        j = 0
                        while j < 12:
                            sx = j * 15
                            if sx >= fw:
                                break
                            ex_ = sx + 15
                            if ex_ > fw:
                                ex_ = fw
                            a_ = sx if sx > lo else lo
                            b_ = ex_ if ex_ < hi else hi
                            if b_ > a_:
                                fill_span(dst, BAR_X + a_, BAR_X + b_, seg[j])
                            j += 1
            kick(base, da)
