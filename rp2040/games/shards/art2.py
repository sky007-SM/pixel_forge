# ============================================================
# ART part 2 (transient): items, projectiles, decor, tiles, background.
# Uses the drawing helpers from artlib.py (unloaded together with it).
# ============================================================
import math, array
from hardware.display import P16
from system.renderer import fill_h
from games.shards import settings as S
from games.shards.render import Bg
from games.shards.artlib import (R, P, EL, LN, img, fin, extra_pals, mkpal, pal_addr,
                              OUT, WHITE, GOLD, CYAN, RED, BLK)


# ------------------------------------------------------------ items, projectiles, misc
def coin(f):
    s = img(8, 9)
    w = (8, 6, 2, 6)[f]
    x = 4 - w // 2
    R(s, GOLD, x, 0, w, 9)
    if w > 2:
        R(s, (255, 246, 160), x, 1, max(1, w // 3), 6)
        R(s, (190, 130, 30), x + w - 1, 2, 1, 6)
    return fin(s)


def heart(full):
    s = img(9, 8)
    c = RED if full else (70, 30, 45)
    for rx, ry, rw, rh in ((1, 0, 3, 3), (5, 0, 3, 3), (0, 1, 9, 3), (1, 4, 7, 2), (2, 6, 5, 1), (3, 7, 3, 1)):
        R(s, c, rx, ry, rw, rh)
    if full:
        R(s, (255, 180, 180), 2, 1, 2, 1)
    return fin(s)


def orb():
    s = img(10, 10)
    EL(s, (40, 150, 200), 0, 0, 10, 10)
    EL(s, CYAN, 1, 1, 8, 8)
    EL(s, WHITE, 3, 2, 3, 3)
    return fin(s)


def wisp(col):
    s = img(10, 10)
    EL(s, col, 0, 0, 10, 10)
    EL(s, (col[0] // 2 + 120, col[1] // 2 + 120, col[2] // 2 + 120), 2, 2, 6, 6)
    EL(s, WHITE, 3, 3, 3, 3)
    return fin(s, False)


def flag(on):
    s = img(12, 24)
    R(s, (140, 140, 170), 5, 4, 2, 20)
    R(s, (96, 96, 120), 3, 21, 6, 3)
    c = (80, 225, 115) if on else (110, 110, 140)
    EL(s, c, 2, 0, 8, 8)
    EL(s, WHITE if on else (170, 170, 190), 3, 1, 3, 3)
    return fin(s)


def pole():
    s = img(6, 124)
    R(s, (210, 214, 230), 2, 6, 2, 118)
    R(s, (140, 146, 170), 3, 6, 1, 118)
    EL(s, GOLD, 0, 0, 6, 6)
    R(s, (255, 246, 160), 1, 1, 2, 2)
    return fin(s)


def goalflag():
    s = img(18, 12)
    P(s, RED, [(0, 0), (17, 5), (0, 11)])
    P(s, (255, 130, 130), [(1, 1), (10, 5), (1, 5)])
    R(s, WHITE, 3, 4, 2, 3)
    return fin(s)


def shard(area):
    col = ((90, 240, 120), (255, 150, 40), (190, 90, 255))[area]
    s = img(14, 18)
    for y in range(18):
        hw = 7 - abs(y - 9) * 7 // 9
        R(s, col, 7 - hw, y, 2 * hw, 1)
    R(s, WHITE, 6, 4, 2, 6)
    return fin(s)


def shrine():
    s = img(32, 24)
    st, sd = (120, 120, 134), (86, 86, 100)
    R(s, st, 2, 4, 6, 20)
    R(s, st, 24, 4, 6, 20)
    R(s, sd, 0, 0, 32, 5)
    R(s, sd, 8, 18, 16, 6)
    return fin(s)


def warn():
    s = img(6, 10)
    R(s, RED, 2, 0, 2, 6)
    R(s, RED, 2, 8, 2, 2)
    return fin(s)


def spear():
    s = img(28, 7)
    R(s, (120, 80, 44), 0, 2, 22, 3)
    R(s, (170, 120, 70), 0, 2, 22, 1)
    P(s, (90, 210, 100), [(20, 0), (27, 3), (20, 6)])
    R(s, WHITE, 22, 3, 3, 1)
    R(s, (60, 170, 80), 0, 0, 3, 7)
    return fin(s)


def core():
    s = img(12, 12)
    EL(s, (150, 60, 220), 0, 0, 12, 12)
    EL(s, (210, 140, 255), 2, 2, 8, 8)
    EL(s, BLK, 4, 4, 4, 4)
    return fin(s)


def ball():
    """8x8 orb with 6 palettes: fire a/b, shadow a/b, seed a/b."""
    s = img(8, 8)
    EL(s, (255, 120, 30), 0, 0, 8, 8)
    EL(s, (255, 232, 120), 2, 2, 4, 4)
    fin(s)
    s.alt = extra_pals(s, [[(255, 120, 30), (255, 232, 120)], [(255, 200, 60), (255, 255, 220)],
                            [(70, 20, 130), (200, 90, 255)], [(120, 50, 190), (240, 180, 255)],
                            [(70, 170, 70), (200, 255, 150)], [(110, 210, 90), (240, 255, 200)]])
    return s


def wave(f):
    s = img(14, 14)
    EL(s, (150, 60, 220), 0, 0, 14 - f, 14 - f)
    EL(s, (230, 170, 255), 3, 4, 8 - f, 10 - f)
    return fin(s)


def rock():
    s = img(14, 14)
    P(s, (96, 56, 50), [(0, 8), (3, 0), (12, 1), (14, 9), (10, 14), (2, 13)])
    LN(s, (255, 150, 40), (5, 3), (9, 9))
    R(s, (140, 90, 80), 2, 2, 4, 2)
    return fin(s)


def rift(act):
    s = img(30, 14)
    if act:
        for i in range(0, 28, 4):
            h = 6 + (i * 5) % 7
            R(s, (150, 60, 230), i, 14 - h, 3, h)
            R(s, (240, 170, 255), i + 1, 14 - h, 1, h // 2)
    else:
        R(s, (200, 90, 255), 0, 12, 28, 2)
        R(s, (200, 90, 255), 0, 2, 1, 10)
        R(s, (200, 90, 255), 27, 2, 1, 10)
    return fin(s)


def blade(f):
    s = img(16, 16)
    EL(s, (190, 200, 215), 0, 0, 16, 16)
    EL(s, (80, 80, 96), 5, 5, 6, 6)
    if f:
        R(s, (230, 235, 250), 0, 7, 16, 2)
    else:
        R(s, (230, 235, 250), 7, 0, 2, 16)
    return fin(s)


def sky(area):
    s = img(28, 28)
    col = (((255, 226, 90), (255, 250, 190)), ((255, 110, 40), (255, 190, 100)),
           ((225, 225, 245), (250, 250, 255)))[area]
    EL(s, col[0], 0, 0, 28, 28)
    EL(s, col[1], 5, 5, 14, 14)
    if area == 2:
        EL(s, (14, 8, 30), 9, 2, 22, 22)
    return fin(s, False)


def plat(kind, w, area):
    s = img(w, 10)
    if kind == 2:
        for x in range(0, w, 8):
            R(s, (150, 100, 50), x, 0, 7, 8)
            R(s, (190, 140, 80), x, 0, 7, 2)
            R(s, (96, 60, 36), x, 6, 7, 2)
    elif kind == 3:
        R(s, (120, 70, 200), 0, 0, w, 8)
        R(s, (200, 150, 255), 0, 0, w, 2)
        R(s, (80, 40, 150), 0, 6, w, 2)
    else:
        c = (((156, 104, 58), (200, 142, 82), (96, 60, 36)), ((74, 42, 42), (130, 70, 56), (255, 150, 40)),
             ((104, 108, 160), (160, 166, 214), (150, 120, 255)))[area]
        R(s, c[0], 0, 0, w, 8)
        R(s, c[1], 0, 0, w, 2)
        R(s, c[2], 0, 6, w, 2)
        for x in range(6, w - 4, 14):
            R(s, c[2], x, 3, 2, 2)
    return fin(s)


# ------------------------------------------------------------ decor (per area: 4 kinds, some animated)
def decor(area):
    out = []
    if area == 0:
        s = img(16, 12)
        R(s, (238, 216, 178), 3, 6, 4, 6)
        EL(s, (210, 64, 44), 0, 0, 10, 8)
        R(s, WHITE, 2, 2, 2, 2)
        R(s, WHITE, 6, 3, 2, 2)
        R(s, (238, 216, 178), 12, 8, 3, 4)
        EL(s, (232, 96, 56), 10, 4, 7, 5)
        out.append((fin(s),))
        s = img(6, 14)
        LN(s, (60, 150, 52), (2, 13), (2, 4))
        for dx, dy in ((0, 0), (4, 0), (2, -2), (2, 2)):
            R(s, (255, 168, 60), dx, 2 + dy, 2, 2)
        R(s, (255, 232, 90), 2, 2, 2, 2)
        out.append((fin(s),))
        s = img(10, 8)
        for dx, h in ((0, 5), (2, 8), (4, 6), (6, 4), (8, 5)):
            LN(s, (86, 170, 56), (dx, 7), (dx + (1 if h > 5 else 0), 7 - h))
        out.append((fin(s),))
        s = img(14, 14)
        R(s, (170, 112, 60), 0, 0, 14, 14)
        R(s, (110, 70, 40), 0, 0, 14, 2)
        R(s, (110, 70, 40), 0, 12, 14, 2)
        R(s, (110, 70, 40), 0, 0, 2, 14)
        R(s, (110, 70, 40), 12, 0, 2, 14)
        LN(s, (110, 70, 40), (1, 1), (12, 12))
        out.append((fin(s),))
    elif area == 1:
        s = img(16, 12)
        P(s, (74, 40, 42), [(0, 12), (3, 3), (10, 1), (15, 12)])
        LN(s, (255, 150, 40), (6, 2), (8, 9))
        out.append((fin(s),))
        fr = []
        for f in (0, 1):
            s = img(8, 20)
            R(s, (74, 52, 50), 2, 6, 3, 14)
            P(s, (255, 150, 40), [(0, 6), (3, 0 + f), (7, 6)])
            P(s, (255, 232, 120), [(2, 6), (3, 2 + f), (5, 6)])
            fr.append(fin(s))
        out.append(tuple(fr))
        s = img(14, 22)
        LN(s, (60, 30, 30), (6, 21), (6, 4), 2)
        LN(s, (60, 30, 30), (6, 12), (1, 4))
        LN(s, (60, 30, 30), (6, 8), (12, 1))
        out.append((fin(s),))
        s = img(10, 24)
        R(s, (132, 72, 62), 0, 4, 8, 20)
        P(s, (132, 72, 62), [(0, 4), (3, 0), (5, 3), (8, 1), (8, 4)])
        R(s, (84, 44, 40), 2, 6, 2, 18)
        out.append((fin(s),))
    else:
        fr = []
        for f in (0, 1):
            s = img(14, 20)
            R(s, (70, 64, 110), 2, 12, 10, 8)
            R(s, (98, 92, 152), 4, 9, 6, 3)
            EL(s, (255, 176, 50) if f else (255, 140, 40), 3, 0, 8, 10)
            EL(s, (255, 240, 170), 5, 3, 4, 4)
            fr.append(fin(s))
        out.append(tuple(fr))
        s = img(12, 16)
        P(s, (90, 140, 255), [(0, 16), (3, 2), (6, 16)])
        P(s, (150, 196, 255), [(5, 16), (8, 7), (11, 16)])
        out.append((fin(s),))
        s = img(10, 14)
        EL(s, (90, 96, 140), 0, 2, 10, 12)
        R(s, (120, 126, 176), 2, 0, 6, 3)
        out.append((fin(s),))
        s = img(10, 22)
        R(s, (110, 70, 140), 4, 0, 2, 22)
        P(s, (176, 52, 80), [(0, 2), (10, 2), (10, 16), (5, 12), (0, 16)])
        R(s, GOLD, 4, 6, 2, 2)
        out.append((fin(s),))
    return out


# ------------------------------------------------------------ tiles
TH = (((84, 190, 76), (52, 150, 60), (122, 84, 52), (96, 64, 40), (120, 120, 130), (80, 80, 92),
       (200, 205, 215), (255, 120, 30), (255, 190, 50), (150, 100, 50)),
      ((110, 70, 66), (240, 110, 40), (70, 44, 44), (50, 30, 32), (100, 72, 72), (60, 40, 42),
       (200, 190, 190), (255, 90, 20), (255, 180, 40), (130, 90, 70)),
      ((96, 84, 130), (130, 116, 170), (62, 54, 90), (44, 38, 66), (84, 74, 114), (50, 44, 74),
       (190, 180, 230), (150, 40, 200), (220, 90, 255), (110, 90, 160)))


def tileset(area, ts):
    top, top2, fill, fill2, brick, mort, spk, l1, l2, wood = [P16(S.rgb(*c)) for c in TH[area]]
    base = ts.addr
    fill_h(base, 0, 11 * 256, 1)

    def T(t, x, y, w, h, c):
        if x < 0:
            w += x
            x = 0
        if x + w > 16:
            w = 16 - x
        if w <= 0:
            return
        for yy in range(y, min(y + h, 16)):
            fill_h(base + t * 512 + yy * 32, x, w, c)

    T(1, 0, 0, 16, 16, fill)
    T(1, 0, 0, 16, 5, top)
    T(1, 0, 4, 16, 1, top2)
    for x in (1, 4, 7, 10, 13):
        T(1, x, 5, 1, 1, top2)
    T(2, 0, 0, 16, 16, fill)
    for x, y in ((2, 3), (9, 6), (5, 11), (12, 13), (13, 2)):
        T(2, x, y, 2, 1, fill2)
    T(3, 0, 0, 16, 16, brick)
    T(3, 0, 7, 16, 1, mort)
    T(3, 0, 15, 16, 1, mort)
    T(3, 7, 0, 1, 7, mort)
    T(3, 3, 8, 1, 7, mort)
    T(3, 11, 8, 1, 7, mort)
    for tip in (3, 8, 13):
        for y in range(6, 16):
            hw = (y - 6) // 3
            T(4, tip - hw, y, 2 * hw + 1, 1, spk)
    for t, ph in ((5, 0), (6, 8)):
        T(t, 0, 0, 16, 16, l1)
        T(t, 0, 0, 16, 3, l2)
        for x in range(0, 16, 4):
            T(t, (x + ph) % 16, 3, 2, 2, l2)
        T(t, (5 + ph) % 14, 9, 2, 1, l2)
    T(7, 0, 0, 16, 5, wood)
    T(7, 0, 0, 16, 1, top2 if area == 2 else P16(S.rgb(190, 140, 80)))
    T(7, 0, 4, 16, 1, fill2)
    qd = P16(S.rgb(120, 70, 20))
    qm = P16(S.rgb(255, 210, 80))
    ql = P16(S.rgb(255, 240, 160))
    qk = P16(S.rgb(150, 90, 24))
    for t, hi in ((8, 0), (10, 1)):                  # ? block, two shine frames
        T(t, 0, 0, 16, 16, qd)
        T(t, 1, 1, 14, 14, qm)
        T(t, 1, 1, 14, 1, ql)
        T(t, 1, 1, 1, 14, ql)
        T(t, 2 + hi * 8, 2, 3, 2, ql)
        for (x, y, w, h) in ((5, 4, 6, 2), (9, 6, 2, 2), (7, 8, 3, 2), (7, 12, 2, 2)):
            T(t, x, y, w, h, qk)
        T(t, 0, 0, 1, 1, qm)
    T(9, 0, 0, 16, 16, qd)
    T(9, 1, 1, 14, 14, P16(S.rgb(150, 110, 80)))
    T(9, 1, 1, 14, 1, P16(S.rgb(190, 150, 110)))
    for (x, y) in ((2, 2), (12, 2), (2, 12), (12, 12)):
        T(9, x, y, 2, 2, qd)
    return ts


# ------------------------------------------------------------ background
SKY = ((((96, 170, 230), (200, 236, 242)), (110, 170, 196), (56, 124, 116), (36, 56, 46)),
       (((150, 44, 28), (255, 214, 112)), (196, 96, 52), (110, 48, 42), (44, 20, 24)),
       (((22, 14, 62), (120, 84, 190)), (64, 46, 118), (44, 30, 90), (14, 8, 30)))


def _hills(area, layer):
    h = bytearray(128)
    for i in range(128):
        if layer == 0:                      # far
            if area == 0:
                v = 118 + int(14 * math.sin(i * math.pi / 32) + 8 * math.sin(i * math.pi / 12.8))
            elif area == 1:
                k = (i * 3) % 48
                v = 70 + (k if k < 24 else 48 - k) * 3
            else:
                v = 150
                if (i // 6) % 2 == 0:
                    v = 96 + (i // 6) % 5 * 8
        else:                               # near
            if area == 0:
                k = (i * 5) % 32
                v = 150 + (k if k < 16 else 32 - k) * -2 + 16
            elif area == 1:
                k = (i * 7) % 40
                v = 150 + abs(k - 20)
            else:
                v = 168
                if (i // 5) % 3 == 0:
                    v = 140
                if i % 10 == 3:
                    v -= 14
        h[i] = max(40, min(200, v))
    return h


def background(area):
    top_hor, c1, c2, earth = SKY[area]
    top, hor = top_hor
    bg = Bg()
    cache = {}
    bands = 7
    bg.bands = [None] * 8
    for y in range(240):
        b = bands if y >= 192 else y * bands // 192
        a = cache.get(b)
        if a is None:
            if b == bands:
                col = earth
            else:
                t = b * 1000 // (bands - 1)
                col = tuple(top[i] + (hor[i] - top[i]) * t // 1000 for i in range(3))
            a = array.array("H", [P16(S.rgb(col[0], col[1], col[2]))] * 2)   # 2 px = 1 word
            cache[b] = a
            bg.bands[b] = a
        bg.addr[y] = pal_addr(a)
    cache = None
    bg.h1 = _hills(area, 0)
    bg.h2 = _hills(area, 1)
    bg.a1 = pal_addr(bg.h1)
    bg.a2 = pal_addr(bg.h2)
    bg.min1 = min(bg.h1)
    bg.min2 = min(bg.h2)
    bg.c1 = P16(S.rgb(*c1))
    bg.c2 = P16(S.rgb(*c2))
    return bg
