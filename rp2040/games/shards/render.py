# ============================================================
# Scanline compositor (viper) + the small image classes it draws.
#
# row(y, P) builds screen row y in a scratch row and returns its address:
#   background row -> two parallax silhouettes -> tile row -> sprites /
#   1-bit text -> effect rectangles.
# render(P) runs all 240 rows in viper (fast path). With a fade or overlay
# active the scene calls row() from Python and streams via r.kick instead.
#
# Everything is driven by one int32 block P (indices below). Values stored
# in it are >= 0; anything that can be negative has +1024 added.
#
# Sprite table entry (8 ints): x+1024, y+1024, w, h, data addr, palette
#   addr (or colour for masks), mode, 0.   mode bit0 = mirror, bit1 = 1-bit text
# Sprites are 4 bits per pixel: 0 = transparent, 1..15 index a 16-entry
# palette of P16 colours (row stride (w+1)>>1 bytes, high nibble first).
# Effect entry (6 ints): type, x+1024, y+1024, w|r, h|mode, colour
#   type 1 dithered circle, 2 dithered rect, 3 solid rect
# ============================================================
import micropython, array, uctypes
from micropython import const
from hardware.display import dma_kick

BASE = const(0)
S0 = const(1)
S1 = const(2)
BG = const(3)
COVON = const(4)
COVP = const(5)
COVA = const(6)
CAM = const(7)
MAP = const(8)
LW = const(9)
TSET = const(10)
LAVA = const(11)
NS = const(12)
TBL = const(13)
FX = const(14)
MAPON = const(15)
NFX = const(16)
FAY = const(17)
FAHP = const(18)
FAOFF = const(19)
FACOL = const(20)
FBY = const(21)
FBHP = const(22)
FBOFF = const(23)
FBCOL = const(24)
FARMAX = const(25)
PSIZE = const(32)
MAXFX = const(28)


@micropython.viper
def row(y: int, pp: int) -> int:
    P = ptr32(pp)
    da = int(P[1])
    if (y & 1) != 0:
        da = int(P[2])
    dst = ptr16(da)
    d32 = ptr32(da)
    bgp = ptr32(int(P[3]))
    src = ptr32(int(bgp[y]))
    sv = int(src[0])                       # background row = one colour (2 px packed), filled
    i = 0
    while i < 160:
        d32[i] = sv
        i += 1
    # ---- two parallax silhouettes (4 px wide steps) ----
    if y < int(P[25]):
        if y >= int(P[17]):
            hp = ptr8(int(P[18]))
            off = int(P[19])
            col = int(P[20])
            x = 0
            while x < 320:
                if y >= int(hp[((x + off) >> 2) & 127]):
                    dst[x] = col
                    dst[x + 1] = col
                    dst[x + 2] = col
                    dst[x + 3] = col
                x += 4
        if y >= int(P[21]):
            hp = ptr8(int(P[22]))
            off = int(P[23])
            col = int(P[24])
            x = 0
            while x < 320:
                if y >= int(hp[((x + off) >> 2) & 127]):
                    dst[x] = col
                    dst[x + 1] = col
                    dst[x + 2] = col
                    dst[x + 3] = col
                x += 4
    # ---- tiles ----
    if int(P[15]) != 0:
        cam = int(P[7])
        lw = int(P[9])
        mp = ptr8(int(P[8]) + (y >> 4) * lw)
        ts = int(P[10])
        ry = (y & 15) * 32
        lava = int(P[11])
        tx = cam >> 4
        sx = 0 - (cam & 15)
        n = 0
        while n < 21:
            if tx < lw:
                t = int(mp[tx])
                if t != 0:
                    if t == 5:
                        t += lava
                    if t == 8:
                        t += lava * 2
                    s = ptr16(ts + t * 512 + ry)
                    k = 0
                    if sx >= 0 and sx <= 304:
                        while k < 16:
                            v = int(s[k])
                            if v != 1:
                                dst[sx + k] = v
                            k += 1
                    else:
                        while k < 16:
                            x = sx + k
                            if x >= 0 and x < 320:
                                v = int(s[k])
                                if v != 1:
                                    dst[x] = v
                            k += 1
            tx += 1
            sx += 16
            n += 1
    # ---- sprites ----
    n = int(P[12])
    tb = ptr32(int(P[13]))
    i = 0
    while i < n:
        b = i << 3
        sy = int(tb[b + 1]) - 1024
        sh = int(tb[b + 3])
        if y >= sy and y < sy + sh:
            sx = int(tb[b]) - 1024
            w = int(tb[b + 2])
            md = int(tb[b + 6])
            k = 0
            if (md & 2) != 0:
                col = int(tb[b + 5])
                m = ptr8(int(tb[b + 4]) + (y - sy) * ((w + 7) >> 3))
                while k < w:
                    bt = int(m[k >> 3])
                    if bt == 0:
                        k = (k | 7) + 1
                    else:
                        if (bt & (0x80 >> (k & 7))) != 0:
                            x = sx + k
                            if x >= 0 and x < 320:
                                dst[x] = col
                        k += 1
            else:
                pal = ptr16(int(tb[b + 5]))
                m = ptr8(int(tb[b + 4]) + (y - sy) * ((w + 1) >> 1))
                if (md & 1) == 0:
                    while k < w:
                        bt = int(m[k >> 1])
                        if bt != 0:
                            x = sx + k
                            nb = bt >> 4
                            if nb != 0 and x >= 0 and x < 320:
                                dst[x] = pal[nb]
                            nb = bt & 15
                            if nb != 0 and x >= -1 and x < 319:
                                dst[x + 1] = pal[nb]
                        k += 2
                else:
                    while k < w:
                        kk = w - 1 - k
                        bt = int(m[kk >> 1])
                        nb = bt & 15
                        if (kk & 1) == 0:
                            nb = bt >> 4
                        x = sx + k
                        if nb != 0 and x >= 0 and x < 320:
                            dst[x] = pal[nb]
                        k += 1
        i += 1
    # ---- effect rectangles / circles ----
    nf = int(P[16])
    f = ptr32(int(P[14]))
    i = 0
    while i < nf:
        b = i * 6
        t = int(f[b])
        if t == 1:
            cx = int(f[b + 1]) - 1024
            cy = int(f[b + 2]) - 1024
            r = int(f[b + 3])
            dy = y - cy
            if dy < 0:
                dy = 0 - dy
            if dy <= r:
                q = r * r - dy * dy
                dx = 0
                while (dx + 1) * (dx + 1) <= q:
                    dx += 1
                x = cx - dx
                e = cx + dx
                col = int(f[b + 5])
                solid = int(f[b + 4])
                while x <= e:
                    if x >= 0 and x < 320:
                        if solid != 0 or ((x + y) & 1) == 0:
                            dst[x] = col
                    x += 1
        elif t >= 2:
            ry = int(f[b + 2]) - 1024
            rh = int(f[b + 4])
            if y >= ry and y < ry + rh:
                x = int(f[b + 1]) - 1024
                e = x + int(f[b + 3])
                col = int(f[b + 5])
                while x < e:
                    if x >= 0 and x < 320:
                        if t == 3 or ((x + y) & 1) == 0:
                            dst[x] = col
                    x += 1
        i += 1
    return da


@micropython.viper
def render(pp: int):
    P = ptr32(pp)
    base = int(P[0])
    covon = int(P[4])
    covp = ptr8(int(P[5]))
    cova = int(P[6])
    y = 0
    while y < 240:
        c = 0
        if covon != 0:
            c = int(covp[y])
        if c != 0:
            dma_kick(base, cova)
        else:
            dma_kick(base, row(y, pp))
        y += 1


# ------------------------------------------------------------ data classes
class Img:
    """4-bit paletted sprite: one contiguous bytearray, palette(s) in arrays.
    pa = normal palette, pw = all white (hit flash), pr = red tint (bosses).
    Rarely-changed fields are class defaults so each instance stays small."""
    dry = False
    ox = 1
    oy = 1
    pa = pw = pr = 0
    pals = None
    cols = None

    def __init__(self, w, h, dry=False):
        self.w = w
        self.h = h
        self.rb = (w + 1) >> 1
        self.buf = bytearray(1 if dry else self.rb * h)
        self.addr = uctypes.addressof(self.buf)
        self.cols = [None, None]
        if dry:
            self.dry = True


class TileSet:
    """11 tiles of 16x16 P16 pixels in one contiguous 5.6 KB block."""

    def __init__(self):
        self.buf = bytearray(11 * 512)
        self.addr = uctypes.addressof(self.buf)


class Bg:
    """Background: gradient rows (shared 1-word bands) + two silhouette height maps."""

    def __init__(self):
        self.addr = array.array("i", [0] * 240)
        self.addr_a = uctypes.addressof(self.addr)
        self.h1 = self.h2 = None          # set by art2.background()
        self.a1 = self.a2 = 0
        self.min1 = self.min2 = 0
        self.c1 = self.c2 = 0
        self.fmax = 192
