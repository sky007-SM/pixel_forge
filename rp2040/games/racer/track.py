# ============================================================
# Tracks: four circuits defined by closed centre lines.
#
# Built in small steps (a generator, so the loading page can animate):
#   1. Catmull-Rom spline through the control points
#   2. resample to equal spacing: dense points (~4 units) and
#      waypoints (every 3rd dense point, ~12 units)
#   3. per-waypoint direction, curvature and radius (used by the AI)
#   4. rasterise the surface map (4 bits / cell) by stamping discs:
#      wall everywhere -> grass -> kerb -> road -> markings
#
# Memory: nothing is allocated per race. TrackMem owns every buffer (the 32 KB
# surface map in 8 bands of 4 KB, the waypoint arrays, the minimap masks) and is
# created ONCE (first race), so repeated races can never fragment the heap.
# Tracks are built straight into those buffers: the spline is streamed twice
# (length, then equal-spacing resample) and only the waypoints (every ~12 units)
# are stored; stamping interpolates between them.
# ============================================================
import math
import array
import uctypes
import micropython
from games.racer import settings as S

_sqrt = math.sqrt
BANDS = 8
BAND_BYTES = 4096                 # 8 x 4096 = 256 x 256 cells x 4 bits


from games.racer.trackdefs import TRACKS


# ---------------------------------------------------------------
@micropython.viper
def disc(tab: ptr32, wx: int, wy: int, rv: int):
    # stamp a filled disc into the banded 4-bit map. rv = radius | (value << 16)
    r = rv & 0xFFFF
    val = rv >> 16
    r2 = r * r
    c0 = (wx - r) >> 2
    c1 = (wx + r) >> 2
    d0 = (wy - r) >> 2
    d1 = (wy + r) >> 2
    if c0 < 0:
        c0 = 0
    if d0 < 0:
        d0 = 0
    if c1 > 255:
        c1 = 255
    if d1 > 255:
        d1 = 255
    cy = d0
    while cy <= d1:
        py = (cy << 2) + 2 - wy
        py2 = py * py
        cx = c0
        while cx <= c1:
            px = (cx << 2) + 2 - wx
            if px * px + py2 <= r2:
                idx = (cy << 8) | cx
                bi = idx >> 1
                mp = ptr8(tab[bi >> 12])
                o = bi & 4095
                b = int(mp[o])
                if idx & 1:
                    mp[o] = (b & 15) | (val << 4)
                else:
                    mp[o] = (b & 240) | val
            cx += 1
        cy += 1


@micropython.viper
def fill_bytes(addr: int, n: int, v: int):
    p = ptr8(addr)
    i = 0
    while i < n:
        p[i] = v
        i += 1


@micropython.viper
def surf(tab: ptr32, x: int, y: int) -> int:
    # surface class at world position (x, y) in whole units
    if x < 0 or y < 0:
        return 3
    cx = x >> 2
    cy = y >> 2
    if cx > 255 or cy > 255:
        return 3
    idx = (cy << 8) | cx
    bi = idx >> 1
    mp = ptr8(tab[bi >> 12])
    b = int(mp[bi & 4095])
    if idx & 1:
        return b >> 4
    return b & 15


def _count(pts):
    n = len(pts)
    t = 0
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        m = int(_sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2) / 3.0)
        t += m if m > 4 else 4
    return t


def _samples(pts):
    """Catmull-Rom samples (about 3 units apart) of the closed loop, one (x, y) at a time."""
    n = len(pts)
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        m = int(_sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2) / 3.0)
        if m < 4:
            m = 4
        for k in range(m):
            t = k / m
            t2 = t * t
            t3 = t2 * t
            yield (0.5 * (2 * p1[0] + (p2[0] - p0[0]) * t
                          + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                          + (3 * p1[0] - p0[0] - 3 * p2[0] + p3[0]) * t3),
                   0.5 * (2 * p1[1] + (p2[1] - p0[1]) * t
                          + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                          + (3 * p1[1] - p0[1] - 3 * p2[1] + p3[1]) * t3))


class TrackMem:
    """Every buffer a track needs, allocated once for the life of the scene."""

    def __init__(self):
        tp = 0
        for d in TRACKS:
            c = _count(d.pts)
            if c > tp:
                tp = c
        self.cap_w = tp // 3 + 8                # waypoints (spline samples are ~3-3.75 units apart)
        self.bands = None

    def alloc_steps(self):
        """Generator: allocates in chunks so the loading screen keeps animating."""
        cw = self.cap_w
        self.bands = []
        self.tab = array.array("I", [0] * BANDS)
        for i in range(BANDS):
            b = bytearray(BAND_BYTES)
            self.bands.append(b)
            self.tab[i] = uctypes.addressof(b)
            if (i & 3) == 3:
                yield
        self.wx = array.array("f", [0.0] * cw)
        self.wy = array.array("f", [0.0] * cw)
        yield
        self.tx = array.array("f", [0.0] * cw)      # unit tangents
        self.ty = array.array("f", [0.0] * cw)
        self.rad = array.array("f", [0.0] * cw)     # signed turn radius (+ = right)
        yield
        self.mm_thick = bytearray(512)              # 64 x 64 minimap masks, 1 bit per pixel
        self.mm_thin = bytearray(512)
        yield


def _plot(buf, x, y):
    if 0 <= x < 64 and 0 <= y < 64:
        buf[y * 8 + (x >> 3)] |= 0x80 >> (x & 7)


class Track:
    def __init__(self, idx, mem):
        self.idx = idx
        d = TRACKS[idx]
        self.d = d
        self.name = d.name
        self.laps = d.laps
        self.theme = d.theme
        self.mem = mem
        self.tab = mem.tab
        self.wx = mem.wx
        self.wy = mem.wy
        self.tx = mem.tx
        self.ty = mem.ty
        self.rad = mem.rad
        self.nw = 0
        self.step = 12.0
        self.inv_step = 1.0 / 12.0
        self.mm_s = 1.0
        self.mm_ox = 0.0
        self.mm_oy = 0.0

    # ---- build (generator: call next() once per frame; yields progress 0..1) ----
    def build_steps(self):
        mem = self.mem
        pts = self.d.pts
        wx = mem.wx
        wy = mem.wy
        tx = mem.tx
        ty = mem.ty
        rad = mem.rad

        # -- 1. total length of the spline (streamed, nothing stored) --
        it = _samples(pts)
        first = next(it)
        px, py = first
        total = 0.0
        q = 0
        for x, y in it:
            total += _sqrt((x - px) ** 2 + (y - py) ** 2)
            px = x
            py = y
            q += 1
            if (q & 127) == 0:
                yield 0.02 + 0.10 * q / 1200
        total += _sqrt((first[0] - px) ** 2 + (first[1] - py) ** 2)
        nw = int(total / S.WP_SPACING + 0.5)
        if nw > mem.cap_w:
            raise MemoryError("track larger than its buffers")
        step = total / nw
        yield 0.12

        # -- 2. resample to equal spacing straight into the waypoint arrays --
        it = _samples(pts)
        px, py = next(it)
        wx[0] = px
        wy[0] = py
        k = 1
        target = step
        walked = 0.0
        done = False
        q = 0
        while not done:
            try:
                x, y = next(it)
            except StopIteration:
                x, y = first
                done = True
            seg = _sqrt((x - px) ** 2 + (y - py) ** 2)
            if seg > 0.0:
                while k < nw and target <= walked + seg:
                    f = (target - walked) / seg
                    wx[k] = px + (x - px) * f
                    wy[k] = py + (y - py) * f
                    k += 1
                    target = k * step
                walked += seg
            px = x
            py = y
            q += 1
            if (q & 127) == 0:
                yield 0.12 + 0.12 * q / 1200
        while k < nw:                                   # float round-off safety
            wx[k] = px
            wy[k] = py
            k += 1
        self.length = total
        self.nw = nw
        self.step = step
        self.inv_step = 1.0 / step
        yield 0.25

        # -- 3. tangents --
        for i in range(nw):
            j = (i + 1) % nw
            dx = wx[j] - wx[i]
            dy = wy[j] - wy[i]
            l = _sqrt(dx * dx + dy * dy)
            tx[i] = dx / l
            ty[i] = dy / l
        yield 0.35

        # -- 4. signed turn radius (positive = turning right on screen), smoothed over 3 points --
        for i in range(nw):                             # raw curvature, stored in rad for now
            a = (i - 1) % nw
            b = (i + 1) % nw
            v1x = wx[i] - wx[a]
            v1y = wy[i] - wy[a]
            v2x = wx[b] - wx[i]
            v2y = wy[b] - wy[i]
            rad[i] = math.atan2(v1x * v2y - v1y * v2x, v1x * v2x + v1y * v2y) / step
        prev = rad[nw - 1]
        first_c = rad[0]
        for i in range(nw):
            cur = rad[i]
            nxt = rad[i + 1] if i + 1 < nw else first_c
            k = (prev + cur + nxt) / 3.0
            prev = cur
            r = 900.0
            if k > 0.0011 or k < -0.0011:
                r = 1.0 / k
                if r > 900.0:
                    r = 900.0
                elif r < -900.0:
                    r = -900.0
            rad[i] = r
        yield 0.42

        # -- 5. surface map (stamps every ~6 units along the waypoint polyline) --
        tab = mem.tab
        for i in range(BANDS):
            fill_bytes(mem.tab[i], BAND_BYTES, 0x33)             # all wall
        yield 0.46
        rg = S.ROAD_HALF + S.KERB_W + S.GRASS_W
        rk = S.ROAD_HALF + S.KERB_W
        re = S.ROAD_HALF
        rr = S.ROAD_HALF - 2
        for cls, rv in ((S.GRASS, rg), (S.KERB, rk), (S.EDGE, re), (S.ROAD, rr)):
            v = rv | (cls << 16)
            for i in range(nw):
                j = (i + 1) % nw
                disc(tab, int(wx[i]), int(wy[i]), v)
                disc(tab, int((wx[i] + wx[j]) * 0.5), int((wy[i] + wy[j]) * 0.5), v)
            yield 0.5
        yield 0.74
        v = 3 | (S.MARK << 16)
        for i in range(nw):                          # dashed centre line (4 unit spacing)
            j = (i + 1) % nw
            dx = wx[j] - wx[i]
            dy = wy[j] - wy[i]
            for m in range(3):
                if ((i * 3 + m) & 7) < 3:
                    f = m / 3.0
                    disc(tab, int(wx[i] + dx * f), int(wy[i] + dy * f), v)
        # chequered start / finish line across the road at waypoint 0
        ux = tx[0]
        uy = ty[0]
        nx = -uy
        ny = ux
        for a in (-4, 0, 4):
            lat = -rr + 2
            while lat <= rr - 2:
                disc(tab, int(wx[0] + ux * a + nx * lat),
                     int(wy[0] + uy * a + ny * lat), 3 | (S.FINISH << 16))
                lat += 3
        yield 0.82

        # -- 6. scenery: trees on the outer grass (deterministic per track) --
        seed = 12345 + self.idx * 7919
        for i in range(2, nw - 2, 4):
            for side in (-1, 1):
                seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
                if ((seed >> 8) % 10) < 3:
                    continue
                off = (rk + 13 + ((seed >> 16) % 9)) * side
                cx = int(wx[i] - ty[i] * off)
                cy = int(wy[i] + tx[i] * off)
                if surf(tab, cx, cy) != S.GRASS:
                    continue
                disc(tab, cx, cy, 9 | (S.TREE_D << 16))
                disc(tab, cx - 1, cy - 1, 7 | (S.TREE_M << 16))
                disc(tab, cx - 3, cy - 3, 3 | (S.TREE_L << 16))
        yield 0.92

        # -- 7. minimap masks --
        self._minimap()
        yield 1.0

    def _minimap(self):
        mem = self.mem
        nw = self.nw
        wx = mem.wx
        wy = mem.wy
        minx = maxx = wx[0]
        miny = maxy = wy[0]
        for i in range(nw):
            x = wx[i]
            y = wy[i]
            if x < minx:
                minx = x
            elif x > maxx:
                maxx = x
            if y < miny:
                miny = y
            elif y > maxy:
                maxy = y
        bw = maxx - minx
        bh = maxy - miny
        sc = 56.0 / (bw if bw > bh else bh)
        ox = (64.0 - bw * sc) * 0.5 - minx * sc
        oy = (64.0 - bh * sc) * 0.5 - miny * sc
        self.mm_s = sc
        self.mm_ox = ox
        self.mm_oy = oy
        thick = mem.mm_thick
        thin = mem.mm_thin
        fill_bytes(uctypes.addressof(thick), 512, 0)
        fill_bytes(uctypes.addressof(thin), 512, 0)
        for i in range(nw):
            x = int(wx[i] * sc + ox)
            y = int(wy[i] * sc + oy)
            _plot(thin, x, y)
            for ddx in (-1, 0, 1):
                for ddy in (-1, 0, 1):
                    _plot(thick, x + ddx, y + ddy)

    # ---- queries ----
    def surface(self, x, y):
        if x < 0.0 or y < 0.0:
            return S.WALL
        return surf(self.tab, int(x), int(y))

    def grid(self, slot):
        """World position + heading of a start-grid slot (2 columns, staggered), and the
        (negative) segment counter it starts on."""
        along = 20.0 + 24.0 * (slot >> 1) + (12.0 if slot & 1 else 0.0)
        lat = 10.0 if slot & 1 else -10.0
        nw = self.nw
        pos = -along * self.inv_step                 # waypoint units behind the start line
        seg = int(pos)
        if seg > pos:
            seg -= 1                                 # floor
        f = pos - seg
        i = seg % nw
        j = (i + 1) % nw
        wx = self.wx
        wy = self.wy
        tx = self.tx[i]
        ty = self.ty[i]
        x = wx[i] + (wx[j] - wx[i]) * f - ty * lat
        y = wy[i] + (wy[j] - wy[i]) * f + tx * lat
        return x, y, math.atan2(ty, tx), seg

    def start_total(self, seg):
        """Segment counter for a car placed on (negative) segment `seg` before the line."""
        return seg

    def free(self):
        """Buffers belong to TrackMem and stay allocated; just let go of the references."""
        self.mem = None
        self.tab = None
        self.wx = self.wy = self.tx = self.ty = self.rad = None
