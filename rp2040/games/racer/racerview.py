# ============================================================
# ForgeRacer RACE view (scanline, same contract as every scene):
# draw() must emit exactly 240 rows through r.kick().
# Imported lazily by game.py when the first race starts, so entering the
# game (menus) costs little memory.
#
#   * ground: for every pair of screen rows the (rotated, translated)
#     camera plane is sampled into the banded 4-bit surface map by a
#     viper loop - one sample per 2x2 block, so 160 x 120 samples per
#     frame. Rotation is just an affine step vector per row. A cheap
#     hash adds grain so grass / asphalt / rock are not flat tiles.
#   * cars: indexed sprites (rotated only when the view angle changes),
#     palette blitted per row, with a real darkening shadow.
#   * HUD: translucent panels + glyph masks drawn by viper helpers, a
#     static track minimap with live car dots.
#   * The WHOLE 240-row loop runs in one viper function (draw_frame). Python is
#     very slow on the console (~10-15 us per statement), so per-row Python
#     (HUD, row dispatch) used to cost >100 ms per frame. Now the HUD is a retained
#     "display list" (int table: fills, dims, 1-bit masks, glyph lines) that
#     paint_row() interprets per row; Python only edits a few table fields per frame.
# ============================================================
import array
import uctypes
import micropython
from hardware.display import P16
from system.renderer import fill_h
from hardware.display import dma_kick  # noqa: F401  (r.kick is used at run time)
from assets.fonts import Text, Digits
from games.racer import settings as S
from games.racer import assets as A

SPR = A.SPR
_K_ANG = A.NANG / 6.283185307
_TWO_PI = 6.283185307
_BLACK = P16(S.BLACK)

M_CARS = 0x01FF                 # row mask bits: 0..8 cars
M_HUD = 0x1000
M_BANNER = 0x2000
M_OVER = 0x4000


# ---------------- viper kernels ----------------
# All kernels take plain integer addresses so they can call each other from viper code.
@micropython.viper
def ground_row(dst: int, prm: int, row: int):
    # One 320 px row for screen rows 2*row and 2*row+1 (2x2 blocks).
    # prm: 0 band-table addr, 1 palette addr, 2/3 world x/y of sample 0 (16.16, row term
    # excluded), 4/5 forward vector (16.16), 6/7 world step per sample, 8 anchor row
    d = ptr32(dst)
    p = ptr32(prm)  # T
    tab = ptr32(p[0])  # T
    pal = ptr16(p[1])
    v = 2 * row + 1 - p[8]
    wx = p[2] - v * p[4]
    wy = p[3] - v * p[5]
    dxs = p[6]
    dys = p[7]
    j = 0
    while j < 160:
        cx = (wx >> 18) & 255
        cy = (wy >> 18) & 255
        idx = (cy << 8) | cx
        bi = idx >> 1
        m = ptr8(tab[bi >> 12])
        cls = (int(m[bi & 4095]) >> ((idx & 1) << 2)) & 15
        sh = 2
        if cls == 2 or cls == 4:
            sh = 1
        n = ((cx * 5 + cy * 7 + ((cx * cy) >> 5)) >> 1) & 1
        c = int(pal[(cls << 2) | ((((cx >> sh) ^ (cy >> sh)) & 1) << 1) | n])
        d[j] = c | (c << 16)
        wx += dxs
        wy += dys
        j += 1


@micropython.viper
def blit_pal(dst: int, x0: int, src: int, pal: int):
    # 28 indexed pixels through a palette. index 0 / TRANS entries are skipped,
    # index 9 darkens the pixel underneath (shadow)
    d = ptr16(dst)
    s = ptr8(src)
    p = ptr16(pal)
    i = 0
    if x0 < 0:
        i = 0 - x0
    end = 28
    if x0 + end > 320:
        end = 320 - x0
    while i < end:
        k = int(s[i])
        if k != 0:
            if k == 9:
                v = int(d[x0 + i])
                d[x0 + i] = (((v & 0xEEEE) >> 1) | ((v & 0x1111) << 7)) & 0xFEB7
            else:
                v = int(p[k])
                if v != 1:
                    d[x0 + i] = v
        i += 1


@micropython.viper
def paint_row(dst: int, dl: int, y: int, n: int):
    # Interpret the display list for screen row y. Item (8 ints):
    #   0 kind, 1 y0, 2 y1, 3 x0, 4 a, 5 b, 6 c, 7 colour
    #   kind 0 fill     x0 .. a
    #   kind 1 dim      x0 .. a, level b (1 = 50 %, 2 = 25 %)
    #   kind 2 mask     1-bit text/shape: a = mask address, b = width, c = row bytes
    #   kind 3 glyphs   a = glyph spec address (count, step, width, row bytes, addresses)
    d = ptr16(dst)
    t = ptr32(dl)  # T
    i = 0
    while i < n:
        o = i << 3
        y0 = t[o + 1]
        if y >= y0 and y < t[o + 2]:
            kind = t[o]
            x0 = t[o + 3]
            col = t[o + 7]
            if kind == 0:
                x1 = t[o + 4]
                if x0 < 0:
                    x0 = 0
                if x1 > 320:
                    x1 = 320
                while x0 < x1:
                    d[x0] = col
                    x0 += 1
            elif kind == 1:
                x1 = t[o + 4]
                if x0 < 0:
                    x0 = 0
                if x1 > 320:
                    x1 = 320
                sh = 1
                ma = 0xEEEE
                mm = 0xFEB7
                if t[o + 5] == 2:
                    sh = 2
                    ma = 0xCCCC
                    mm = 0x7E93
                mb = 0xFFFF - ma
                lsh = 8 - sh
                while x0 < x1:
                    v = int(d[x0])
                    d[x0] = (((v & ma) >> sh) | ((v & mb) << lsh)) & mm
                    x0 += 1
            elif kind == 2:
                m = ptr8(t[o + 4] + (y - y0) * t[o + 6])
                w = t[o + 5]
                j = 0
                while j < w:
                    b = int(m[j >> 3])
                    if b == 0:
                        j = (j | 7) + 1
                    else:
                        if b & (0x80 >> (j & 7)):
                            x = x0 + j
                            if x >= 0 and x < 320:
                                d[x] = col
                        j += 1
            else:
                sp = ptr32(t[o + 4])  # T
                k = y - y0
                cn = sp[0]
                step = sp[1]
                gw = sp[2]
                rb = sp[3]
                ci = 0
                while ci < cn:
                    m = ptr8(sp[4 + ci] + k * rb)
                    gx = x0 + ci * step
                    j = 0
                    while j < gw:
                        b = int(m[j >> 3])
                        if b == 0:
                            j = (j | 7) + 1
                        else:
                            if b & (0x80 >> (j & 7)):
                                x = gx + j
                                if x >= 0 and x < 320:
                                    d[x] = col
                            j += 1
                    ci += 1
        i += 1


@micropython.viper
def draw_frame(c: ptr32, kick: object):  # T
    # The whole frame in one viper call (240 rows -> 240 kick() calls).
    # c: 0 DMA base, 1/2 ground row buffers, 3/4 scratch rows, 5 row-mask array,
    #    6 ground params, 7 cover array, 8 cover on, 9 cover row addr, 10 car count,
    #    11..14 sprite x / top / frame addr / palette addr arrays, 15 display list, 16 its length
    base = c[0]
    g0 = c[1]
    g1 = c[2]
    s0 = c[3]
    s1 = c[4]
    rowm = ptr16(c[5])
    prm = c[6]
    cov = ptr8(c[7])
    cov_on = c[8]
    cova = c[9]
    ns = c[10]
    spx = ptr32(c[11])  # T
    spt = ptr32(c[12])  # T
    spf = ptr32(c[13])  # T
    spp = ptr32(c[14])  # T
    dl = c[15]
    dln = c[16]
    k = 0
    while k < 120:
        y = k << 1
        if cov_on != 0 and cov[y] != 0 and cov[y + 1] != 0:
            kick(base, cova)
            kick(base, cova)
            k += 1
            continue
        ga = g0
        if k & 1:
            ga = g1
        ground_row(ga, prm, k)
        e = y + 2
        while y < e:
            if cov_on != 0 and cov[y] != 0:
                kick(base, cova)
            else:
                m = int(rowm[y])
                src = ga
                if m != 0:
                    dst = s0
                    if y & 1:
                        dst = s1
                    a = ptr32(ga)
                    b = ptr32(dst)
                    i = 0
                    while i < 160:
                        b[i] = a[i]
                        i += 1
                    if m & 0x1FF:
                        i = 0
                        while i < ns:
                            if m & (1 << i):
                                blit_pal(dst, spx[i], spf[i] + (y - spt[i]) * 28, spp[i])
                            i += 1
                    if m & 0x1000:
                        paint_row(dst, dl, y, dln)
                    src = dst
                kick(base, src)
            y += 1
        k += 1


@micropython.viper
def mark_rows(arr: int, y0: int, y1: int, bit: int):
    # OR `bit` into rows [y0, y1) of a 240 entry halfword mask
    p = ptr16(arr)
    if y0 < 0:
        y0 = 0
    if y1 > 240:
        y1 = 240
    while y0 < y1:
        p[y0] = int(p[y0]) | bit
        y0 += 1


@micropython.viper
def copy_h(dst: int, src: int, n: int):
    d = ptr16(dst)
    s = ptr16(src)
    i = 0
    while i < n:
        d[i] = s[i]
        i += 1


# ---------------- display list + HUD ----------------
class GlyphLine:
    """A short string drawn from shared 1-bit glyph masks (a display-list 'glyphs' item).
    spec = [count, step, glyph width, glyph row bytes, glyph mask addresses ...]"""

    def __init__(self, glyphs, scale, maxch):
        self.g = glyphs
        self.scale = scale
        self.h = 7 * scale
        self.step = 6 * scale
        self.maxch = maxch
        any_g = glyphs["0"]
        sp = array.array("i", [0] * (4 + maxch))  # Q
        sp[1] = self.step
        sp[2] = any_g.w
        sp[3] = any_g.rb
        self.spec = sp
        self.addr = uctypes.addressof(sp)
        self.txt = None
        self.set("0")

    def set(self, s):
        if s == self.txt:
            return
        self.txt = s
        sp = self.spec
        g = self.g
        n = 0
        for ch in s:
            if n >= self.maxch:
                break
            gl = g.get(ch)
            if gl is not None:
                sp[4 + n] = gl.addr
                n += 1
        sp[0] = n

    def width(self):
        return self.spec[0] * self.step - self.scale


class DisplayList:
    """Int table interpreted per row by paint_row(): 8 ints per item (see paint_row)."""
    CAP = 96

    def __init__(self):
        self.t = array.array("i", [0] * (8 * DisplayList.CAP))  # Q
        self.a = uctypes.addressof(self.t)
        self.n = 0

    def add(self, kind, y0, y1, x0, a=0, b=0, c=0, col=0):
        o = self.n << 3
        t = self.t
        t[o] = kind
        t[o + 1] = y0
        t[o + 2] = y1
        t[o + 3] = x0
        t[o + 4] = a
        t[o + 5] = b
        t[o + 6] = c
        t[o + 7] = col
        self.n += 1
        return o


class Hud:
    """Race HUD as a retained display list: translucent panels, glyph masks, minimap.
    The layout is built once; per frame only a handful of table fields are rewritten."""

    def __init__(self):
        g2 = Digits.make_glyphs(2, "0123456789:./")
        g3 = Digits.make_glyphs(3, "0123456789")
        self.l_pos = GlyphLine(g2, 2, 4)
        self.l_time = GlyphLine(g2, 2, 7)
        self.l_lap = GlyphLine(g2, 2, 5)
        self.l_kmh = GlyphLine(g3, 3, 3)
        self.t_pos = Text("POS", 1)
        self.t_time = Text("TIME", 1)
        self.t_lap = Text("LAP", 1)
        self.t_kmh = Text("KMH", 1)
        self.t_nitro = (Text("NITRO", 1), Text("NITRO READY", 1), Text("NITRO!", 1))
        self.banners = (None, Text("3", 8), Text("2", 8), Text("1", 8), Text("GO!", 7),
                        Text("WRONG WAY", 3), Text("FINISH!", 5))
        w = P16(S.WHITE)
        grey = P16(S.GREY)
        cyan = P16(S.CYAN)
        yel = P16(S.YELLOW)
        self.c_nit = (cyan, yel, P16(S.ORANGE))
        self.c_ban = (0, yel, yel, yel, P16(S.GREEN), P16(S.RED), yel)
        self.c_ban_sh = (0, _BLACK, _BLACK, _BLACK, _BLACK, w, _BLACK)
        self.c_org = P16(S.ORANGE)
        self.c_org_hi = P16(S.rgb(255, 200, 90))
        self.c_cyan_hi = P16(S.rgb(180, 240, 255))
        self.c_yel_hi = P16(S.rgb(255, 245, 160))
        self.c_cyan = cyan
        self.c_yel = yel
        self.banner = 0
        self.nstate = 0
        dl = DisplayList()
        self.dl = dl
        panels = S.HUD_PANELS

        def dim(y0, y1, x0, x1):
            if panels:
                dl.add(1, y0, y1, x0, x1, 1)

        def mask(t, x, y, col):
            return dl.add(2, y, y + t.h, x, t.addr, t.w, t.rb, col)

        def glyphs(line, x, y, col):
            so = dl.add(3, y + 1, y + 1 + line.h, x + 1, line.addr, 0, 0, _BLACK)
            mo = dl.add(3, y, y + line.h, x, line.addr, 0, 0, col)
            return so, mo

        # top panels: position / race time / lap
        dim(3, 31, 4, 76)
        dim(3, 31, 106, 214)
        dim(3, 31, 244, 316)
        dl.add(0, 3, 4, 4, 76, 0, 0, cyan)
        dl.add(0, 3, 4, 106, 214, 0, 0, yel)
        dl.add(0, 3, 4, 244, 316, 0, 0, cyan)
        mask(self.t_pos, 10, 6, grey)
        mask(self.t_time, 160 - (self.t_time.w >> 1), 6, grey)
        mask(self.t_lap, 250, 6, grey)
        glyphs(self.l_pos, 10, 14, w)
        self.o_time = glyphs(self.l_time, 112, 14, w)
        glyphs(self.l_lap, 250, 14, w)
        # minimap panel
        dim(34, 106, 244, 316)
        dl.add(0, 34, 35, 244, 316, 0, 0, cyan)
        self.o_thick = dl.add(2, 38, 102, 248, 0, 64, 8, _BLACK)
        self.o_thin = dl.add(2, 38, 102, 248, 0, 64, 8, P16(S.rgb(255, 238, 150)))
        self.o_start = dl.add(0, 0, 0, 0, 0, 0, 0, w)
        self.o_ai = []
        for i in range(8):
            self.o_ai.append(dl.add(0, 0, 0, 0, 0, 0, 0, 0))
        self.o_plw = dl.add(0, 0, 0, 0, 0, 0, 0, w)
        self.o_ply = dl.add(0, 0, 0, 0, 0, 0, 0, yel)
        # bottom panels: speed / nitro
        dim(206, 234, 4, 98)
        dim(206, 234, 196, 316)
        dl.add(0, 206, 207, 4, 98, 0, 0, yel)
        self.o_nacc = dl.add(0, 206, 207, 196, 316, 0, 0, cyan)
        glyphs(self.l_kmh, 10, 210, w)
        mask(self.t_kmh, 70, 224, grey)
        self.o_nlab = dl.add(2, 209, 216, 202, 0, 0, 0, cyan)
        dl.add(0, 220, 221, 202, 310, 0, 0, w)
        dl.add(0, 229, 230, 202, 310, 0, 0, w)
        dl.add(0, 221, 229, 202, 203, 0, 0, w)
        dl.add(0, 221, 229, 309, 310, 0, 0, w)
        dl.add(0, 221, 229, 203, 309, 0, 0, P16(S.PANEL))
        self.o_nhi = dl.add(0, 222, 223, 203, 203, 0, 0, cyan)
        self.o_nbar = dl.add(0, 223, 228, 203, 203, 0, 0, cyan)
        # banner (shadow + text), moved / recoloured on demand
        self.o_bsh = dl.add(2, 0, 0, 0, 0, 0, 0, _BLACK)
        self.o_ban = dl.add(2, 0, 0, 0, 0, 0, 0, w)
        self.n_static = dl.n

    def set_track(self, trk, mm_s, mm_ox, mm_oy):
        t = self.dl.t
        t[self.o_thick + 4] = uctypes.addressof(trk.mem.mm_thick)
        t[self.o_thin + 4] = uctypes.addressof(trk.mem.mm_thin)
        sx = 248 + int(trk.wx[0] * mm_s + mm_ox)
        sy = 38 + int(trk.wy[0] * mm_s + mm_oy)
        o = self.o_start
        t[o + 1] = sy - 1
        t[o + 2] = sy + 2
        t[o + 3] = sx - 1
        t[o + 4] = sx + 2

    def set_overlay(self, box):
        """Append a Box (rects + text masks) to the display list, or remove it (None)."""
        dl = self.dl
        dl.n = self.n_static
        if box is None:
            return
        by = box.y
        bx = box.x
        for it in box.it:
            if dl.n >= DisplayList.CAP:
                break
            if it[2] == 2:
                tx = it[4]
                dl.add(2, by + it[0], by + it[1], bx + it[3], tx.addr, tx.w, tx.rb, it[5])
            elif it[2] == 1:
                dl.add(0, by + it[0], by + it[1], bx + it[3], bx + it[3] + it[4], 0, 0, it[5])
            else:
                dl.add(0, by + it[0], by + it[1], bx + it[3], bx + it[3] + it[4], 0, 0, it[6])

    def update(self, place, total, lap, laps, kmh, ms, banner, nstate):
        self.l_pos.set("%d/%d" % (place, total))
        secs = ms // 1000
        self.l_time.set("%d:%02d.%02d" % (secs // 60, secs % 60, (ms // 10) % 100))
        self.l_lap.set("%d/%d" % (lap, laps))
        self.l_kmh.set("%d" % kmh)
        self.banner = banner
        self.nstate = nstate

    def banner_rows(self):
        """(first row, row count) of the banner, or None."""
        b = self.banner
        if not b:
            return None
        return (58 if b < 5 else 100, self.banners[b].h + 3)

    def dot(self, o, x0, x1, y0, y1, col):
        t = self.dl.t
        t[o + 1] = y0
        t[o + 2] = y1
        t[o + 3] = x0
        t[o + 4] = x1
        t[o + 7] = col

    def sync(self, meter, nitro_on, tick):
        """Rewrite the few table fields that change every frame."""
        t = self.dl.t
        # race time x (centred)
        x = 160 - (self.l_time.width() >> 1)
        so, mo = self.o_time
        t[so + 3] = x + 1
        t[mo + 3] = x
        # nitro
        ns = self.nstate
        if nitro_on:
            col = self.c_org
            hi = self.c_org_hi
        elif meter >= 0.999 and (tick >> 2) & 1:
            col = self.c_yel
            hi = self.c_yel_hi
        else:
            col = self.c_cyan
            hi = self.c_cyan_hi
        lab = self.t_nitro[ns]
        o = self.o_nlab
        t[o + 4] = lab.addr
        t[o + 5] = lab.w
        t[o + 6] = lab.rb
        t[o + 7] = self.c_nit[ns]
        t[self.o_nacc + 7] = self.c_nit[ns]
        x1 = 203 + int(meter * 106.0)
        o = self.o_nhi
        t[o + 4] = x1
        t[o + 7] = hi
        o = self.o_nbar
        t[o + 4] = x1
        t[o + 7] = col
        # banner
        b = self.banner
        ob = self.o_ban
        os_ = self.o_bsh
        if b:
            tx = self.banners[b]
            y0 = 58 if b < 5 else 100
            x0 = (320 - tx.w) >> 1
            sh = 1 if b == 5 else 2
            for o, dx, col in ((os_, sh, self.c_ban_sh[b]), (ob, 0, self.c_ban[b])):
                t[o + 1] = y0 + (sh if o == os_ else 0)
                t[o + 2] = y0 + (sh if o == os_ else 0) + tx.h
                t[o + 3] = x0 + dx
                t[o + 4] = tx.addr
                t[o + 5] = tx.w
                t[o + 6] = tx.rb
                t[o + 7] = col
        else:
            t[ob + 2] = t[ob + 1]
            t[os_ + 2] = t[os_ + 1]


# ---------------- race view ----------------
class RaceView:
    """Created once per scene; every buffer is reused from race to race."""

    def __init__(self):
        self.g0 = array.array("H", [0] * 320)
        self.g1 = array.array("H", [0] * 320)
        self.prm = array.array("i", [0] * 12)  # Q
        self.rowm = array.array("H", [0] * 240)      # per-row needs (bit mask, see M_*)
        self.rowm_a = uctypes.addressof(self.rowm)
        self.hudm = array.array("H", [0] * 240)      # static: rows the HUD touches
        self.hudm_a = uctypes.addressof(self.hudm)
        mark_rows(self.hudm_a, 3, 31, M_HUD)
        mark_rows(self.hudm_a, 34, 106, M_HUD)
        mark_rows(self.hudm_a, 206, 234, M_HUD)
        self.hud = Hud()
        self.tpal = A.new_track_pal()
        self.prm[1] = uctypes.addressof(self.tpal)
        self.prm[8] = S.CAM_ANCHOR_Y
        self.ns = 0
        self.spx = array.array("i", [0] * 12)  # Q
        self.spt = array.array("i", [0] * 12)  # Q
        self.spf = array.array("i", [0] * 12)  # Q
        self.spp = array.array("i", [0] * 12)  # Q
        # context table handed to draw_frame (addresses of everything it needs)
        c = array.array("i", [0] * 20)  # Q
        self.ctxt = c
        c[1] = uctypes.addressof(self.g0)
        c[2] = uctypes.addressof(self.g1)
        c[5] = self.rowm_a
        c[6] = uctypes.addressof(self.prm)
        c[11] = uctypes.addressof(self.spx)
        c[12] = uctypes.addressof(self.spt)
        c[13] = uctypes.addressof(self.spf)
        c[14] = uctypes.addressof(self.spp)
        c[15] = self.hud.dl.a
        self.trk = None
        self.ov = None                                 # result box (kept alive while shown)
        self.mm_s = 1.0
        self.mm_ox = 0.0
        self.mm_oy = 0.0

    def set_track(self, trk):
        self.trk = trk
        A.fill_track_pal(self.tpal, trk.theme)
        self.prm[0] = uctypes.addressof(trk.tab)
        self.mm_s = trk.mm_s
        self.mm_ox = trk.mm_ox
        self.mm_oy = trk.mm_oy
        self.hud.set_track(trk, trk.mm_s, trk.mm_ox, trk.mm_oy)
        self.set_overlay(None)

    def set_overlay(self, box):
        self.ov = box
        self.hud.set_overlay(box)

    def release(self):
        self.trk = None
        self.set_overlay(None)

    def prepare(self, cam, cars, art, meter, nitro_on, tick):
        """Per-frame set-up: camera matrix, car sprites, minimap dots, HUD fields."""
        p = self.prm
        fx = cam.fx
        fy = cam.fy
        rx16 = int(-fy * 65536.0)
        ry16 = int(fx * 65536.0)
        p[2] = int(cam.x * 65536.0) - 159 * rx16
        p[3] = int(cam.y * 65536.0) - 159 * ry16
        p[4] = int(fx * 65536.0)
        p[5] = int(fy * 65536.0)
        p[6] = 2 * rx16
        p[7] = 2 * ry16

        rowm_a = self.rowm_a
        copy_h(rowm_a, self.hudm_a, 240)
        hud = self.hud
        flick = tick & 1
        n = 0
        ha = cam.ha
        cx = cam.x
        cy = cam.y
        rx = cam.rx
        ry = cam.ry
        spx = self.spx
        spt = self.spt
        spf = self.spf
        spp = self.spp
        mms = self.mm_s
        mmx = self.mm_ox
        mmy = self.mm_oy
        o_ai = hud.o_ai
        ci = 0
        last = len(cars) - 1
        for c in cars:
            # minimap dot
            mx = 248 + int(c.x * mms + mmx)
            my = 38 + int(c.y * mms + mmy)
            if ci == last:
                hud.dot(hud.o_plw, mx - 2, mx + 3, my - 2, my + 3, P16(S.WHITE))
                hud.dot(hud.o_ply, mx - 1, mx + 2, my - 1, my + 2, P16(S.YELLOW))
            else:
                hud.dot(o_ai[ci], mx - 1, mx + 2, my - 1, my + 2, c.pal[1])
            ci += 1
            # screen sprite
            dx = c.x - cx
            dy = c.y - cy
            sx = 160.0 + dx * rx + dy * ry
            sy = S.CAM_ANCHOR_Y - (dx * fx + dy * fy)
            if sx < -16.0 or sx > 336.0 or sy < -16.0 or sy > 256.0:
                continue
            fi = int(((c.hd - ha) % _TWO_PI) * _K_ANG + 0.5) & 63
            if fi != c.fi:
                art.rotate_q(c.spr_a, fi)
                c.fi = fi
            if c.nitro_on:
                A.set_flame(c.pal, True, flick)
                c.flame = True
            elif c.flame:
                A.set_flame(c.pal, False, 0)
                c.flame = False
            lit = c.brake and c.spd > 3.0
            if lit != c.lit:
                A.set_brake(c.pal, lit)
                c.lit = lit
            spx[n] = int(sx) - A.PIV_X
            top = int(sy) - A.PIV_Y
            spt[n] = top
            spf[n] = c.spr_a
            spp[n] = A.pal_addr(c.pal)
            mark_rows(rowm_a, top, top + SPR, 1 << n)
            n += 1
        self.ns = n
        for i in range(last, 8):                       # AI dots not used in this race: zero height
            hud.dot(o_ai[i], 0, 0, 0, 0, 0)

        hud.sync(meter, nitro_on, tick)
        br = hud.banner_rows()
        if br is not None:
            mark_rows(rowm_a, br[0], br[0] + br[1], M_HUD)
        ov = self.ov
        if ov is not None:
            mark_rows(rowm_a, ov.y, ov.y + ov.h, M_HUD)

    def draw(self, r):
        c = self.ctxt
        c[0] = r.base
        c[3] = r.a0
        c[4] = r.a1
        c[7] = uctypes.addressof(r.cover)
        c[8] = 1 if r.cov_on else 0
        c[9] = r.cover_addr
        c[10] = self.ns
        c[16] = self.hud.dl.n
        draw_frame(c, r.kick)
