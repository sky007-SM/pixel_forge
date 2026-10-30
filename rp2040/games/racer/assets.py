# ============================================================
# ForgeRacer assets: car art, palettes, sound cues.
#
# The car is drawn ONCE as a 16-colour indexed sprite (nose up, nitro
# flame at the back, soft shadow generated from the body). Each car owns
# one fixed 28x28 buffer and a 16-entry palette; the base art is rotated
# into that buffer only when the heading the camera sees changes by one
# of 64 steps (a fast viper loop). Palette tricks do the rest:
#   6 / 7  flame (transparent until nitro fires)
#   14     tail lights (dim, bright while braking)
#   9      shadow: darkens whatever is under it (handled by the blitter)
# ============================================================
import array
import math
import uctypes
import micropython
from hardware.display import P16
from games.racer import settings as S

SPR = 28                       # sprite frame is SPR x SPR indexed pixels
PIV_X = 13                     # pivot (car body centre) inside the frame
PIV_Y = 14
FRAME_BYTES = SPR * SPR
NANG = 64                      # rotation steps (5.6 degrees)
TRANS = 0x0001
SHADOW = 9

# index: 0 clear, 1 body, 2 tyre, 3 glass, 4 accent, 5 headlight, 6 flame, 7 flame core,
#        8 tyre highlight, 9 shadow, 10 body light, 11 body dark, 12 glass light,
#        13 spoiler, 14 tail light
_ART = (
    "...dBBBd...",
    "..dBbbbBd..",
    ".LdBbAbBdL.",
    "WWdBBABBdWW",
    "WwdBBABBdwW",
    "WWdBGGGBdWW",
    "WWBGgggGBWW",
    "..BGGGGGB..",
    "..BbBBBbB..",
    "..BBBABBB..",
    "..BbBABbB..",
    "..BGGGGGB..",
    "WWdBBABBdWW",
    "WwdBBABBdwW",
    "WWdBBABBdWW",
    ".KKKKKKKKK.",
    "..RdBBBdR..",
    "...FFYFF...",
    "...FYYYF...",
    "....FYF....",
    "....FYF....",
    ".....F.....",
)
_MAP = {'.': 0, 'B': 1, 'W': 2, 'G': 3, 'A': 4, 'L': 5, 'F': 6, 'Y': 7,
        'w': 8, 'b': 10, 'd': 11, 'g': 12, 'K': 13, 'R': 14}


@micropython.viper
def _rot_frame(dst: int, src: int, cs: int, sn: int):
    # dst/src: 28 x 28 index buffers. cs/sn = cos/sin(angle) * 65536.
    # Inverse maps every destination pixel into the source (rotation about the pivot).
    d = ptr8(dst)
    s = ptr8(src)
    y = 0
    while y < 28:
        dy = y - 14
        x = 0
        while x < 28:
            dx = x - 13
            sx = ((cs * dx + sn * dy + 32768) >> 16) + 13
            sy = ((cs * dy - sn * dx + 32768) >> 16) + 14
            v = 0
            if sx >= 0 and sx < 28 and sy >= 0 and sy < 28:
                v = int(s[sy * 28 + sx])
            d[y * 28 + x] = v
            x += 1
        y += 1


class CarArt:
    """The one base sprite (784 bytes) every car is rotated from."""

    def __init__(self):
        base = bytearray(FRAME_BYTES)
        for r in range(len(_ART)):
            row = _ART[r]
            for c in range(11):
                base[(r + 6) * SPR + 8 + c] = _MAP[row[c]]
        # soft drop shadow: every body pixel casts one 2 px down-right
        orig = bytes(base)
        for y in range(SPR - 2):
            for x in range(SPR - 2):
                v = orig[y * SPR + x]
                if v != 0 and v != 6 and v != 7:
                    t = (y + 2) * SPR + x + 2
                    if orig[t] == 0:
                        base[t] = SHADOW
        self.base = base
        self.addr = uctypes.addressof(base)
        self.cs = array.array("i", [0] * NANG)
        self.sn = array.array("i", [0] * NANG)
        for i in range(NANG):
            a = 6.283185307 * i / NANG
            self.cs[i] = int(math.cos(a) * 65536)
            self.sn[i] = int(math.sin(a) * 65536)

    def rotate_q(self, dst_addr, i):
        """Rotate the base art by i/NANG of a turn (clockwise on screen) into dst_addr."""
        _rot_frame(dst_addr, self.addr, self.cs[i], self.sn[i])


# ---------------- colour helpers (raw RGB565 in / out) ----------------
def shade(c, num, den):
    r = (c >> 8) & 0xF8
    g = (c >> 3) & 0xFC
    b = (c << 3) & 0xF8
    r = r * num // den
    g = g * num // den
    b = b * num // den
    if r > 255:
        r = 255
    if g > 255:
        g = 255
    if b > 255:
        b = 255
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def lighten(c):
    r = (c >> 8) & 0xF8
    g = (c >> 3) & 0xFC
    b = (c << 3) & 0xF8
    r += (255 - r) * 38 // 100
    g += (255 - g) * 38 // 100
    b += (255 - b) * 38 // 100
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


# ---------------- palettes ----------------
_TAIL_DIM = P16(S.rgb(120, 22, 22))
_TAIL_ON = P16(S.rgb(255, 60, 48))
_FO = P16(S.FLAME_O)
_FY = P16(S.FLAME_Y)
_FB = P16(S.FLAME_B)
_TYRE_HI = P16(S.rgb(70, 70, 80))
_SPOILER = P16(S.rgb(40, 40, 48))


def new_car_pal():
    return array.array("H", [TRANS] * 16)


def fill_car_pal(p, body, accent):
    """(Re)colour a car palette in place - no allocation."""
    p[0] = TRANS
    p[1] = P16(body)
    p[2] = P16(S.CAR_DARK)
    p[3] = P16(S.CAR_GLASS)
    p[4] = P16(accent)
    p[5] = P16(S.CAR_LIGHT)
    p[6] = TRANS
    p[7] = TRANS
    p[8] = _TYRE_HI
    p[9] = TRANS
    p[10] = P16(lighten(body))
    p[11] = P16(shade(body, 62, 100))
    p[12] = P16(lighten(S.CAR_GLASS))
    p[13] = _SPOILER
    p[14] = _TAIL_DIM
    p[15] = TRANS


def make_car_pal(body, accent):
    p = new_car_pal()
    fill_car_pal(p, body, accent)
    return p


def set_flame(p, on, flick):
    """Palette-swap the nitro flame on / off (flick alternates colours)."""
    if on:
        if flick:
            p[6] = _FO
            p[7] = _FY
        else:
            p[6] = _FY
            p[7] = _FB
    else:
        p[6] = TRANS
        p[7] = TRANS


def set_brake(p, on):
    p[14] = _TAIL_ON if on else _TAIL_DIM


def pal_addr(p):
    return uctypes.addressof(p)


# Track palette: index = surface class * 4 + checker bit * 2 + noise bit
# (see renderer.ground_row). Variant 1 of each noisy class is a touch darker,
# which gives grass / asphalt / rock a grainy look instead of flat tiles.
def new_track_pal():
    return array.array("H", [0] * 48)


def fill_track_pal(p, theme):
    ga, gb, ra, rb, wa, wb, tr = theme
    base = (
        (ga, gb, True),                              # 0 grass
        (ra, rb, True),                              # 1 road
        (S.KERB_A, S.KERB_B, False),                 # 2 kerb
        (wa, wb, True),                              # 3 wall / rock
        (S.BLACK, S.WHITE, False),                   # 4 start line
        (S.MARK_C, S.MARK_C, False),                 # 5 centre dashes
        (shade(tr, 55, 100), shade(tr, 55, 100), False),    # 6 tree shade
        (tr, tr, False),                             # 7 tree body
        (lighten(tr), lighten(tr), False),           # 8 tree highlight
        (S.WHITE, S.WHITE, False),                   # 9 edge line
    )
    for cls in range(10):
        a, b, noisy = base[cls]
        a2 = shade(a, 90, 100) if noisy else a
        b2 = shade(b, 90, 100) if noisy else b
        o = cls * 4
        p[o] = P16(a)
        p[o + 1] = P16(a2)
        p[o + 2] = P16(b)
        p[o + 3] = P16(b2)
    for i in range(40, 48):
        p[i] = 0


# ---------------- sound cues: (frequency Hz, milliseconds) ----------------
SFX_TICK = (520, 70)
SFX_GO = (1040, 260)
SFX_NITRO = (1500, 90)
SFX_NITRO_END = (300, 90)
SFX_NO = (190, 60)
SFX_BUMP = (140, 45)
SFX_WALL = (110, 70)
SFX_LAP = (1320, 60)
SFX_FINISH = (1760, 220)
SFX_CLICK = (760, 25)
SFX_BUY = (1200, 90)
