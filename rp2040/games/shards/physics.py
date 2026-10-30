# ============================================================
# Physics: tile collision, one-way tiles, ? blocks, moving / collapsing /
# disappearing platforms, hazard probes, and the Level container.
#
# Bodies: x, y (sub-pixels, top-left), w, h (px), vx, vy (sub-px/frame).
# Map: bytearray, row-major, 15 rows of lv.lw tiles.
# Tile ids: 0 air, 1 ground top, 2 ground fill, 3 brick, 4 spikes, 5/6 lava,
#           7 one-way ledge, 8 ? block, 9 used block, 10 ? block (shine frame)
# ============================================================
SOLID = 1
HAZ = 2
ONEWAY = 4
LAVA = 8
#        0  1  2  3  4  5  6  7  8  9  10
TF = bytes((0, 1, 1, 1, 2, 8, 8, 4, 1, 1, 1, 0, 0, 0, 0, 0))


class Level:
    def __init__(self, lw, area):
        self.lw = lw
        self.area = area
        self.tiles = bytearray(lw * 15)
        self.plats = []
        self.en = []            # (kind, tile col, row)
        self.items = []         # (kind, tile col, row)   0 coin 1 heart 2 orb
        self.cps = [(3, 12)]    # (tile col, floor row)
        self.blades = []
        self.rocks = []         # (px x, period, phase)
        self.decor = []         # (kind, px x, floor px y)
        self.goal = 0
        self.arena = 0
        self.escape = 0

    def theme_boss(self):
        return self.arena != 0

    def put(self, x, y, t):
        if 0 <= x < self.lw and 0 <= y < 15:
            self.tiles[y * self.lw + x] = t

    def rect(self, x0, y0, x1, y1, t):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, t)

    def ground(self, x0, x1, top=12):
        self.rect(x0, top, x1, top, 1)
        self.rect(x0, top + 1, x1, 14, 2)


def tile(lv, tx, ty):
    if tx < 0 or tx >= lv.lw:
        return 1
    if ty < 0 or ty >= 15:
        return 0
    return lv.tiles[ty * lv.lw + tx]


def solid_px(lv, x, y):
    return TF[tile(lv, x >> 4, y >> 4)] & SOLID


def support_px(lv, x, y):
    return TF[tile(lv, x >> 4, y >> 4)] & 5


def hazard_px(lv, x, y):
    return TF[tile(lv, x >> 4, y >> 4)] & 10


def on_oneway(b, lv):
    t = tile(lv, ((b.x >> 4) + (b.w >> 1)) >> 4, ((b.y >> 4) + b.h) >> 4)
    f = TF[t]
    return (f & ONEWAY) and not (f & SOLID)


def move_body(b, lv, plats):
    w = b.w
    h = b.h
    vx = b.vx
    x = b.x + vx
    if vx:
        py = b.y >> 4
        r = py >> 4
        r1 = (py + h - 1) >> 4
        if vx > 0:
            tx = (((x >> 4) + w - 1)) >> 4
            while r <= r1:
                if TF[tile(lv, tx, r)] & SOLID:
                    x = ((tx << 4) - w) << 4
                    b.vx = 0
                    break
                r += 1
        else:
            tx = (x >> 4) >> 4
            while r <= r1:
                if TF[tile(lv, tx, r)] & SOLID:
                    x = ((tx + 1) << 4) << 4
                    b.vx = 0
                    break
                r += 1
    b.x = x
    vy = b.vy
    y = b.y + vy
    px0 = x >> 4
    c0 = px0 >> 4
    c1 = (px0 + w - 1) >> 4
    b.ground = False
    b.stand = None
    b.bumped = False
    if vy >= 0:
        old_b = (b.y >> 4) + h
        new_b = (y >> 4) + h
        r = (old_b + 15) >> 4
        land = -1
        while (r << 4) <= new_b:
            c = c0
            while c <= c1:
                f = TF[tile(lv, c, r)]
                if f & 5:
                    if (f & SOLID) or not b.drop:
                        land = r << 4
                        break
                c += 1
            if land >= 0:
                break
            r += 1
        st = None
        for p in plats:
            if p.on and px0 + w > p.x and px0 < p.x + p.w:
                if old_b <= p.y <= new_b and (land < 0 or p.y < land):
                    land = p.y
                    st = p
        if land >= 0:
            y = (land - h) << 4
            b.vy = 0
            b.ground = True
            b.stand = st
    else:
        top = y >> 4
        if top >= 0:
            r = top >> 4
            mid = (px0 + (w >> 1)) >> 4
            c = c0
            while c <= c1:
                if TF[tile(lv, c, r)] & SOLID:
                    y = ((r + 1) << 4) << 4
                    b.vy = 0
                    b.bumped = True
                    b.bcx = mid if tile(lv, mid, r) == 8 else c
                    b.bcy = r
                    break
                c += 1
    b.y = y


def touch_hazard(b, lv):
    """0 = none, 1 = spikes, 2 = lava / void."""
    px = b.x >> 4
    py = b.y >> 4
    bot = py + b.h
    c0 = px >> 4
    c1 = (px + b.w - 1) >> 4
    r0 = py >> 4
    r1 = (bot - 1) >> 4
    hit = 0
    r = r0
    while r <= r1:
        c = c0
        while c <= c1:
            f = TF[tile(lv, c, r)]
            if f & HAZ:
                if bot > (r << 4) + 8 and hit < 1:
                    hit = 1
            elif f & LAVA:
                if bot > (r << 4) + 4:
                    hit = 2
            c += 1
        r += 1
    return hit


class Plat:
    """Top-solid platform. kind 0 moves in x, 1 moves in y,
    2 collapses after being stood on, 3 blinks in and out."""

    def __init__(self, kind, x, y, w, a=0, b=0, v=1, ph=0, on_t=70, off_t=40):
        self.kind = kind
        self.x = x
        self.y = y
        self.w = w
        self.ox = x
        self.oy = y
        self.a = a
        self.b = b
        self.v = v
        self.on = True
        self.dx = 0
        self.dy = 0
        self.t = ph
        self.st = 0
        self.on_t = on_t
        self.off_t = off_t
        self.warn = False
        self.touch = False

    def reset(self):
        self.x = self.ox
        self.y = self.oy
        self.st = 0
        self.on = True
        self.touch = False

    def update(self):
        k = self.kind
        self.dx = 0
        self.dy = 0
        if k == 0:
            nx = self.x + self.v
            if nx <= self.a:
                nx = self.a
                self.v = abs(self.v)
            elif nx >= self.b:
                nx = self.b
                self.v = -abs(self.v)
            self.dx = nx - self.x
            self.x = nx
        elif k == 1:
            ny = self.y + self.v
            if ny <= self.a:
                ny = self.a
                self.v = abs(self.v)
            elif ny >= self.b:
                ny = self.b
                self.v = -abs(self.v)
            self.dy = ny - self.y
            self.y = ny
        elif k == 2:
            st = self.st
            self.t += 1
            if st == 0:
                if self.touch:
                    self.st = 1
                    self.t = 0
            elif st == 1:
                if self.t >= 24:
                    self.st = 2
                    self.on = False
                    self.t = 0
            elif st == 2:
                self.y += 5
                if self.t > 50:
                    self.st = 3
                    self.t = 0
            else:
                if self.t > 140:
                    self.reset()
            self.touch = False
        else:
            self.t += 1
            ph = self.t % (self.on_t + self.off_t)
            self.on = ph < self.on_t
            self.warn = self.on and ph >= self.on_t - 18
