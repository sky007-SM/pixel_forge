# ============================================================
# Renderer: scanline helpers shared by every scene.
#
# A scene draws a frame by walking y = 0..239 and, for each row,
# either pointing the DMA at a ready-made row (static) or building
# the row in a scratch buffer (copy_row + fill/blit) first. The DMA
# streams row y while the CPU builds row y+1, so drawing is
# overlapped with the transfer.
#
# All colours handed to these helpers are P16 (see display.P16).
# Viper functions take at most 4 arguments.
# ============================================================
import array, uctypes, micropython
import config
from hardware.display import P16, dma_kick, dma_wait

W = config.DISPLAY_WIDTH
H = config.DISPLAY_HEIGHT
TRANS = 0x0001               # transparent key used by sprites


@micropython.viper
def copy_row(dst: ptr32, src: int):
    s = ptr32(src)
    i = 0
    while i < 160:
        dst[i] = s[i]
        i += 1


@micropython.viper
def fill_row(dst: ptr32, v: int):
    w = v | (v << 16)
    i = 0
    while i < 160:
        dst[i] = w
        i += 1


@micropython.viper
def fill_span(dst: ptr16, x0: int, x1: int, v: int):
    # fill pixels [x0, x1) of a 320 px row, clipped
    if x0 < 0:
        x0 = 0
    if x1 > 320:
        x1 = 320
    while x0 < x1:
        dst[x0] = v
        x0 += 1


@micropython.viper
def fill_h(addr: int, x: int, n: int, v: int):
    # fill n pixels from x at a raw halfword address (sprite building)
    p = ptr16(addr)
    i = x
    e = x + n
    while i < e:
        p[i] = v
        i += 1


@micropython.viper
def blit_t(dst: ptr16, x0: int, src: int, n: int):
    # copy n pixels to dst[x0:], skipping TRANS pixels, clipped to the row
    s = ptr16(src)
    i = 0
    if x0 < 0:
        i = 0 - x0
    end = n
    if x0 + end > 320:
        end = 320 - x0
    while i < end:
        v = int(s[i])
        if v != 1:
            dst[x0 + i] = v
        i += 1


@micropython.viper
def blit_o(dst: ptr16, x0: int, src: int, n: int):
    # opaque copy, clipped
    s = ptr16(src)
    i = 0
    if x0 < 0:
        i = 0 - x0
    end = n
    if x0 + end > 320:
        end = 320 - x0
    while i < end:
        dst[x0 + i] = s[i]
        i += 1


@micropython.viper
def blit_n(dst: int, src: int, n: int):
    # raw copy between buffers, skipping TRANS, no clipping (sprite building)
    d = ptr16(dst)
    s = ptr16(src)
    i = 0
    while i < n:
        v = int(s[i])
        if v != 1:
            d[i] = v
        i += 1


@micropython.viper
def blit_m(dst: ptr16, x0: int, src: int, cn: int):
    # draw a 1-bit-per-pixel mask row in one colour. cn = (width << 16) | P16 colour.
    n = cn >> 16
    col = cn & 0xFFFF
    m = ptr8(src)
    i = 0
    if x0 < 0:
        i = 0 - x0
    end = n
    if x0 + end > 320:
        end = 320 - x0
    while i < end:
        b = int(m[i >> 3])
        if b == 0:
            i = (i | 7) + 1                  # empty byte: skip 8 pixels
        else:
            if b & (0x80 >> (i & 7)):
                dst[x0 + i] = col
            i += 1


@micropython.viper
def cover_rows(cov: ptr8, n: int):
    # shutter: rows < n and rows >= 240 - n are covered
    y = 0
    while y < 240:
        if y < n or y >= 240 - n:
            cov[y] = 1
        else:
            cov[y] = 0
        y += 1


@micropython.viper
def cover_blinds(cov: ptr8, th: int):
    # venetian blinds: in every 8-row slat, th rows are covered
    y = 0
    while y < 240:
        if (y & 7) < th:
            cov[y] = 1
        else:
            cov[y] = 0
        y += 1


@micropython.viper
def dim_row(dst: ptr16, sh: int, ma: int, mm: int):
    # darken a row of P16 pixels in place: each channel >> sh (1 = 50 %, 2 = 25 %, 3 = 12 %).
    # Works directly on the nibble-swapped pixel format (checked against all 65536 colours).
    mb = 0xFFFF - ma
    lsh = 8 - sh
    i = 0
    while i < 320:
        v = int(dst[i])
        dst[i] = (((v & ma) >> sh) | ((v & mb) << lsh)) & mm
        i += 1


# (shift, source mask, result mask) for fade levels 1..3
_DIM = ((1, 0xEEEE, 0xFEB7), (2, 0xCCCC, 0x7E93), (3, 0x8888, 0x3E81))


def make_row(raw_color):
    """A 320 px row filled with one RGB565 colour."""
    return array.array("H", [P16(raw_color)] * W)


BAND = 4096                  # largest single allocation made for pixel data


class Sprite:
    """w x h block of P16 pixels, TRANS by default (transparent).

    Pixel rows live in bands of at most BAND bytes, so no large contiguous block is
    ever needed (a fragmented heap cannot make a big sprite fail). Always address
    rows through ra[y] (row start addresses), never addr + y * stride."""

    def __init__(self, w, h, fill=TRANS):
        stride = w * 2
        per = BAND // stride
        if per < 1:
            per = 1
        self.w = w
        self.h = h
        self.stride = stride
        self.bufs = []
        ra = []
        y = 0
        while y < h:
            n = per if h - y > per else h - y
            buf = bytearray(n * stride)
            a = uctypes.addressof(buf)
            self.bufs.append(buf)
            if fill:
                fill_h(a, 0, n * w, fill)
            for k in range(n):
                ra.append(a + k * stride)
            y += n
        self.ra = ra
        self.addr = ra[0]

    def rect(self, x, y, w, h, c):
        """Fill a rectangle (P16 colour), clipped to the sprite."""
        if x < 0:
            w += x
            x = 0
        if y < 0:
            h += y
            y = 0
        if x + w > self.w:
            w = self.w - x
        if y + h > self.h:
            h = self.h - y
        if w <= 0 or h <= 0:
            return
        ra = self.ra
        for yy in range(y, y + h):
            fill_h(ra[yy], x, w, c)

    def stamp(self, other, x, y):
        ra = self.ra
        oa = other.ra
        for k in range(other.h):
            blit_n(ra[y + k] + x * 2, oa[k], other.w)


class Renderer:
    """Owns the scratch rows and the per-frame post effects.

    Scenes must emit rows with `kick = r.kick; kick(r.base, addr)` (not dma_kick
    directly) so fades and the pause overlay can be applied to any scene."""

    def __init__(self, disp):
        self.disp = disp
        self.base = disp.base
        self.s0 = array.array("H", [0] * W)
        self.s1 = array.array("H", [0] * W)
        self.a0 = uctypes.addressof(self.s0)
        self.a1 = uctypes.addressof(self.s1)
        # transition mask: a scene must stream cover_addr for rows where cover[y] is set
        self.cover = bytearray(H)
        self.cov_on = False
        self.cover_row = make_row(config.C_BG0)
        self.cover_addr = uctypes.addressof(self.cover_row)
        # post-effect buffers (fade / dim / overlay)
        self.f0 = array.array("H", [0] * W)
        self.f1 = array.array("H", [0] * W)
        self.fa0 = uctypes.addressof(self.f0)
        self.fa1 = uctypes.addressof(self.f1)
        self.kick = dma_kick
        self.fx_level = 0
        self.ov = None               # overlay object: .y, .h, .draw_row(buf, y)
        self._y = 0

    def wait(self):
        dma_wait(self.base)

    def begin_frame(self):
        self._y = 0

    def set_fx(self, level=0, overlay=None):
        """level: 0 off, 1..3 darker (50/25/12 %), 4 black. overlay: object drawn on top."""
        self.fx_level = level
        self.ov = overlay
        self.kick = self._fx_kick if (level or overlay is not None) else dma_kick

    def _fx_kick(self, base, addr):
        y = self._y
        self._y = y + 1
        lvl = self.fx_level
        if lvl >= 4:
            dma_kick(base, self.cover_addr)
            return
        if y & 1:
            buf = self.f1
            ba = self.fa1
        else:
            buf = self.f0
            ba = self.fa0
        copy_row(buf, addr)
        if lvl:
            d = _DIM[lvl - 1]
            dim_row(buf, d[0], d[1], d[2])
        ov = self.ov
        if ov is not None and ov.y <= y < ov.y + ov.h:
            ov.draw_row(buf, y)
        dma_kick(base, ba)
