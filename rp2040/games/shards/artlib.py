# ============================================================
# ARTLIB (transient): drawing helpers shared by art.py and art2.py. Split out so the
# sprite code of art.py can be unloaded before art2.py is compiled (lower peak RAM).
#
# Helpers mirror simple pygame calls (R rect, P polygon, EL ellipse, LN line).
# Each image auto-assigns up to 13 colours; fin() builds its three palettes
# (normal, white hit-flash, red warning tint) and a 1 px dark outline.
# ============================================================
import math, array, micropython
from hardware.display import P16
from games.shards import settings as S
from games.shards.render import Img

OUT = (18, 10, 28)
WHITE = (240, 240, 255)
GOLD = (246, 192, 66)
CYAN = (75, 230, 240)
RED = (245, 65, 75)
BLK = (10, 12, 25)


# ------------------------------------------------------------ nibble drawing (viper)
@micropython.viper
def _rect4(addr: int, rb: int, xywh: int, idx: int):
    b = ptr8(addr)
    x0 = xywh & 127
    y0 = (xywh >> 7) & 127
    w = (xywh >> 14) & 127
    h = (xywh >> 21) & 127
    y = y0
    while y < y0 + h:
        x = x0
        while x < x0 + w:
            o = y * rb + (x >> 1)
            v = int(b[o])
            if (x & 1) == 0:
                b[o] = (v & 15) | (idx << 4)
            else:
                b[o] = (v & 240) | idx
            x += 1
        y += 1


@micropython.viper
def _get4(addr: int, rb: int, xy: int) -> int:
    b = ptr8(addr)
    x = xy & 255
    v = int(b[(xy >> 8) * rb + (x >> 1)])
    if (x & 1) == 0:
        return v >> 4
    return v & 15


@micropython.viper
def _set4(addr: int, rb: int, xy: int, idx: int):
    b = ptr8(addr)
    x = xy & 255
    o = (xy >> 8) * rb + (x >> 1)
    v = int(b[o])
    if (x & 1) == 0:
        b[o] = (v & 15) | (idx << 4)
    else:
        b[o] = (v & 240) | idx


@micropython.viper
def _outline4(addr: int, rb: int, wh: int):
    # transparent pixels touching a real pixel become colour 1 (marked 15 first)
    w = wh & 255
    h = wh >> 8
    y = 0
    while y < h:
        x = 0
        while x < w:
            if int(_get4(addr, rb, x | (y << 8))) == 0:
                hit = 0
                if x > 0:
                    v = int(_get4(addr, rb, (x - 1) | (y << 8)))
                    if v != 0 and v != 15:
                        hit = 1
                if x < w - 1:
                    v = int(_get4(addr, rb, (x + 1) | (y << 8)))
                    if v != 0 and v != 15:
                        hit = 1
                if y > 0:
                    v = int(_get4(addr, rb, x | ((y - 1) << 8)))
                    if v != 0 and v != 15:
                        hit = 1
                if y < h - 1:
                    v = int(_get4(addr, rb, x | ((y + 1) << 8)))
                    if v != 0 and v != 15:
                        hit = 1
                if hit != 0:
                    _set4(addr, rb, x | (y << 8), 15)
            x += 1
        y += 1
    y = 0
    while y < h:
        x = 0
        while x < w:
            if int(_get4(addr, rb, x | (y << 8))) == 15:
                _set4(addr, rb, x | (y << 8), 1)
            x += 1
        y += 1


# ------------------------------------------------------------ pygame-like helpers
def ci(s, c):
    cols = s.cols
    for i in range(2, len(cols)):
        if cols[i] == c:
            return i
    if len(cols) < 15:
        cols.append(c)
        return len(cols) - 1
    best = 2
    bd = 1 << 30
    for i in range(2, 15):
        d = (cols[i][0] - c[0]) ** 2 + (cols[i][1] - c[1]) ** 2 + (cols[i][2] - c[2]) ** 2
        if d < bd:
            bd = d
            best = i
    return best


def R(s, c, x, y, w, h):
    x += s.ox
    y += s.oy
    if x < 0:
        w += x
        x = 0
    if y < 0:
        h += y
        y = 0
    if x + w > s.w:
        w = s.w - x
    if y + h > s.h:
        h = s.h - y
    if w <= 0 or h <= 0:
        return
    i = ci(s, c)
    if not s.dry:
        _rect4(s.addr, s.rb, x | (y << 7) | (w << 14) | (h << 21), i)


def P(s, c, pts):
    n = len(pts)
    y0 = int(min(p[1] for p in pts))
    y1 = int(max(p[1] for p in pts))
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            if (ay <= yc < by) or (by <= yc < ay):
                xs.append(ax + (yc - ay) * (bx - ax) / (by - ay))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            x0 = int(xs[j] + 0.5)
            x1 = int(xs[j + 1] + 0.99)
            if x1 > x0:
                R(s, c, x0, y, x1 - x0, 1)


def EL(s, c, x, y, w, h):
    rx = w / 2.0
    ry = h / 2.0
    cx = x + rx
    cy = y + ry
    for yy in range(y, y + h):
        dy = (yy + 0.5 - cy) / ry
        if -1 < dy < 1:
            dx = rx * math.sqrt(1 - dy * dy)
            x0 = int(cx - dx + 0.5)
            x1 = int(cx + dx + 0.5)
            if x1 > x0:
                R(s, c, x0, yy, x1 - x0, 1)


def LN(s, c, a, b, w=1):
    x0, y0 = int(a[0]), int(a[1])
    x1, y1 = int(b[0]), int(b[1])
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        R(s, c, x0, y0, w, w)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def img(w, h, dry=False):
    """New image with room for a 1 px outline around a w x h drawing."""
    return Img(w + 2, h + 2, dry)


def mkpal(cols, mode=0):
    pal = array.array("H", [0] * 16)
    for i in range(2, len(cols)):
        c = cols[i]
        if mode == 1:
            c = (255, 255, 255)
        elif mode == 2:
            c = (c[0] + (255 - c[0]) * 6 // 10, c[1] * 4 // 10, c[2] * 4 // 10)
        pal[i] = P16(S.rgb(c[0], c[1], c[2]))
    pal[1] = P16(S.rgb(OUT[0], OUT[1], OUT[2])) if mode != 2 else P16(S.rgb(90, 10, 10))
    return pal


def pal_addr(pal):
    import uctypes
    return uctypes.addressof(pal)


_WP = {}                                    # all-white (hit flash) palettes, shared per colour count


def fin(s, outline=True, red=False):
    cols = s.cols
    cols[1] = OUT
    p0 = mkpal(cols, 0)
    n = len(cols)
    p1 = _WP.get(n)
    if p1 is None:
        p1 = _WP[n] = mkpal(cols, 1)
    p2 = mkpal(cols, 2) if red else p0          # red warning tint: bosses only
    s.cols = None                           # drawing is finished: free the colour list
    cols = None
    s.pals = [p0, p1, p2]
    s.pa = pal_addr(p0)
    s.pw = pal_addr(p1)
    s.pr = pal_addr(p2)
    if outline and not s.dry:
        _outline4(s.addr, s.rb, s.w | (s.h << 8))
    return s


def extra_pals(s, lists):
    """More palettes for one image (colour lists replace slots 2..). Returns addresses."""
    out = []
    for cl in lists:
        cols = [None, OUT] + list(cl)
        p = mkpal(cols, 0)
        s.pals.append(p)
        out.append(pal_addr(p))
    return tuple(out)


def px(s, c, x, y):
    R(s, c, x, y, 1, 1)


