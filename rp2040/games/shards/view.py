# ============================================================
# View: turns the game state into the renderer's sprite / effect tables
# (called once per frame from update). Resident, but only functions.
# ============================================================
from hardware.display import P16
from games.shards import settings as S
from games.shards import render as R
from games.shards import enemies as E
from games.shards.player import F_FALL


def _c(r, g, b):
    return P16(S.rgb(r, g, b))


C_GOLD = _c(255, 240, 160)
C_WHITE = _c(255, 255, 255)
C_DIM = _c(200, 200, 200)
C_SHADOW = _c(30, 20, 20)
C_ORANGE = _c(255, 190, 90)
C_VIOLET = _c(200, 160, 255)
C_YEL = _c(255, 226, 90)
C_TITLE = _c(255, 210, 80)
DUST = (_c(200, 170, 120), _c(170, 110, 100), _c(170, 160, 210))
BURST = _c(255, 240, 160)
AMB = (_c(255, 250, 200), _c(255, 160, 60), _c(200, 130, 255))
M_BORDER = (_c(90, 240, 120), _c(255, 150, 40), _c(190, 90, 255))
M_BG = _c(24, 20, 36)
M_FILL = (_c(60, 200, 90), _c(255, 150, 40), _c(190, 90, 255))
BAR_OUT = _c(22, 18, 34)
BAR_BG = _c(60, 20, 40)
BAR_FG = _c(200, 40, 80)
FX_VOID = _c(150, 60, 220)
# Void King phases 2 and 3 repaint the castle sky (in place, no art import needed)
VOID = (((30, 0, 40), (110, 20, 70), (70, 30, 100), (44, 16, 70), (14, 4, 24)),
        ((40, 0, 10), (160, 20, 30), (110, 30, 50), (70, 14, 34), (24, 4, 12)))


def recolor(bg, var):
    top, hor, c1, c2, earth = VOID[var - 1]
    for b in range(8):
        if b == 7:
            col = earth
        else:
            t = b * 1000 // 6
            col = (top[0] + (hor[0] - top[0]) * t // 1000, top[1] + (hor[1] - top[1]) * t // 1000,
                   top[2] + (hor[2] - top[2]) * t // 1000)
        v = P16(S.rgb(col[0], col[1], col[2]))
        a = bg.bands[b]
        a[0] = v
        a[1] = v
    bg.c1 = P16(S.rgb(c1[0], c1[1], c1[2]))
    bg.c2 = P16(S.rgb(c2[0], c2[1], c2[2]))


def spr(g, s, x, y, fl=0, pal=0):
    n = g.ns
    if n < S.MAXS and x + s.w > 0 and x < 320:
        b = n << 3
        t = g.tbl
        t[b] = x + 1024
        t[b + 1] = y + 1024
        t[b + 2] = s.w
        t[b + 3] = s.h
        t[b + 4] = s.addr
        t[b + 5] = pal if pal else s.pa
        t[b + 6] = fl
        g.ns = n + 1


def mask(g, tx, x, y, col):
    n = g.ns
    if n < S.MAXS:
        b = n << 3
        t = g.tbl
        t[b] = x + 1024
        t[b + 1] = y + 1024
        t[b + 2] = tx.w
        t[b + 3] = tx.h
        t[b + 4] = tx.addr
        t[b + 5] = col
        t[b + 6] = 2
        g.ns = n + 1


def fx(g, typ, x, y, w, h, col):
    n = g.nfx
    if n < R.MAXFX:
        b = n * 6
        f = g.fxa
        f[b] = typ
        f[b + 1] = x + 1024
        f[b + 2] = y + 1024
        f[b + 3] = w
        f[b + 4] = h
        f[b + 5] = col
        g.nfx = n + 1


def digits(g, dg, x, y, col):
    gl = g.glyphs
    for d in dg:
        mask(g, gl[d], x, y, col)
        x += 6


def ui(g):
    tick = g.tick
    for tx, x, y, col, bl in g.ui:
        if not bl or ((tick >> 3) & 1) == 0:
            mask(g, tx, x + 1, y + 1, C_SHADOW)
            mask(g, tx, x, y, col)


def ambient(g, c, area):
    tick = g.tick
    col = AMB[area]
    for i in range(4):
        x = (i * 83 + tick * (i + 1) - c // (i + 3)) % 320
        y = 40 + (i * 47) % 110 + (E.SIN[(tick + i * 9) & 31] >> 1)
        fx(g, 3, x, y, 2, 2, col)


def build(g):
    g.ns = 0
    g.nfx = 0
    P = g.P
    a = g.pack
    tick = g.tick
    P[R.LAVA] = (tick >> 4) & 1
    lv = g.lv
    bg = g.bg
    if lv is None or a is None:
        m = g.mode
        P[R.LW] = 21
        P[R.CAM] = 0
        if m == 0 and a is not None:                      # title: running Kiro on a scrolling ground
            P[R.MAPON] = 1
            P[R.MAP] = g.title_addr
            P[R.CAM] = (tick * 3) & 15
            P[R.FAOFF] = tick >> 1
            P[R.FBOFF] = tick
            spr(g, a.sky, 250, 24)
            spr(g, a.kiro[2 + ((tick >> 1) & 3)], 50, 165)
            ox = 36 + (E.SIN[(tick >> 2) & 31] >> 1)
            spr(g, a.wisp[(tick >> 5) % 3], ox, 160 + (E.SIN[(tick >> 1) & 31] >> 2))
        else:
            P[R.MAPON] = 0
            P[R.MAP] = g.pa
            P[R.FAOFF] = tick >> 2
            P[R.FBOFF] = tick >> 1
            if a is not None and m != 1:
                spr(g, a.sky, 250, 24)
        ui(g)
        P[R.NS] = g.ns
        P[R.NFX] = g.nfx
        return
    c = g.cam
    if g.shake:
        g.shake -= 1
        c += (tick & 3) - 1
        if c < 0:
            c = 0
    P[R.CAM] = c
    P[R.FAOFF] = c >> 2
    P[R.FBOFF] = c >> 1
    spr(g, a.sky, 250, 24)
    # ---- decor (sorted by x) ----
    dx = g.dx
    dk = g.dk
    dec = a.decor
    n_d = len(dx)
    i = g.vd
    while i > 0 and dx[i - 1] > c - 24:
        i -= 1
    while i < n_d and dx[i] < c - 24:
        i += 1
    g.vd = i
    while i < n_d:
        x = dx[i] - c
        if x > 320:
            break
        fr = dec[dk[i]]
        im = fr[(tick >> 3) % len(fr)]
        spr(g, im, x, 193 - im.h)
        i += 1
    yield
    for pl in g.plats:
        k = pl.kind
        if k == 3 and (not pl.on or (pl.warn and (tick & 2))):
            continue
        if k == 2 and pl.st >= 2:
            continue
        ox = (1 if (tick & 1) else -1) if (k == 2 and pl.st == 1) else 0
        spr(g, a.plat[(k, pl.w)], pl.x - c + ox - 1, pl.y - 1)
    cps = lv.cps
    for i in range(1, len(cps)):
        x = cps[i][0] * 16 + 2 - c
        if -16 < x < 320:
            spr(g, a.flags[1 if i <= g.cp else 0], x, cps[i][1] * 16 - 24)
    if lv.goal and g.goal_on:
        if lv.arena:
            bob = E.SIN[(tick >> 1) & 31] >> 2
            spr(g, a.shrine, lv.goal - 9 - c, 168)
            spr(g, a.shard, lv.goal - c, 140 + bob)
        else:
            gx = lv.goal - c
            spr(g, a.pole, gx - 1, 62)
            fy = g.flag_y if g.mode == 4 else 70
            spr(g, a.gflag, gx + 5, fy)
    # ---- items ----
    ix = g.ix
    iy = g.iy
    ik = g.ik
    n_i = len(ix)
    i = g.vi
    while i > 0 and ix[i - 1] > c - 12:
        i -= 1
    while i < n_i and ix[i] < c - 12:
        i += 1
    g.vi = i
    fr4 = (tick >> 2) & 3
    while i < n_i:
        x = ix[i] - c
        if x > 320:
            break
        k = ik[i]
        if k == 0:
            spr(g, a.coin[fr4], x, iy[i])
        elif k == 1:
            spr(g, a.heart[0], x, iy[i])
        elif k == 2:
            spr(g, a.orb, x, iy[i])
        i += 1
    for it in g.ex:
        if it[0] == 1:
            spr(g, a.heart[0], it[1] - c, it[2])
        else:
            spr(g, a.orb, it[1] - c, it[2])
    t = g.t
    for rx, per, phs in lv.rocks:
        if -16 < rx - c < 320 and (t + phs) % per >= per - 24 and (tick & 2):
            spr(g, a.warn, rx + 4 - c, 2)
    yield
    for e in g.enemies:
        if e.alive and e.vis and -40 < e.x - c < 340:
            fr = a.en[e.kind]
            im = fr[e.fr % len(fr)]
            spr(g, im, e.x + (e.w >> 1) - (im.w >> 1) - c, e.y + e.h - im.h + 1,
                1 if e.dir < 0 else 0, im.pw if e.flash else 0)
    yield
    for r in g.rifts:
        im = a.rift[1 if r.active() else 0]
        spr(g, im, r.x - c - 1, r.y + r.h - im.h + 1)
    for b in g.blades:
        if not b.dis or (tick & 2):
            spr(g, a.blade[(b.t >> 1) & 1], b.x - c - 1, b.y - 1)
    for q in g.projs:
        k = q.kind
        x = q.x - c
        if k == E.PK_SPEAR:
            spr(g, a.spear, x - 1, q.y - 1, 1 if q.vx < 0 else 0)
        elif k == E.PK_VOID:
            spr(g, a.core, x - 1, q.y - 1)
        elif k == E.PK_WAVE:
            spr(g, a.wave[q.fr], x - 1, q.y - 1, 1 if q.vx < 0 else 0)
        elif k == E.PK_ROCK:
            spr(g, a.rock, x - 1, q.y - 1)
        else:
            idx = (0 if k == E.PK_FIRE else (2 if k == E.PK_SHADOW else 4)) + q.fr
            spr(g, a.ball, x - 1, q.y - 1, 0, a.ball.alt[idx])
    bs = g.boss
    if bs is not None:
        im = a.boss[(g.tick >> 4) & 1]
        if bs.vis:
            if bs.kind == 2:
                pa, pw, pr = im.phase[bs.phase - 1]
            else:
                pa, pw, pr = im.pa, im.pw, im.pr
            pal = pw if (bs.flash and (bs.flash & 2)) else (pr if bs.warn and (tick & 2) == 0 else pa)
            spr(g, im, bs.x + (bs.w >> 1) - (im.w >> 1) - c, bs.y + bs.h - im.h + 1,
                1 if bs.face < 0 else 0, pal)
        if bs.warn and (tick & 2) == 0:
            spr(g, a.warn, bs.x + (bs.w >> 1) - 3 - c, bs.y - 14)
        for i in range(bs.nx):
            if tick & 2:
                spr(g, a.warn, bs.xs[i] + 4 - c, 2)
        for k in range(bs.nf):
            f = bs.fxl[k]
            fx(g, f[0], f[1] - c, f[2], f[3], f[4], f[5])
    yield
    p = g.player
    m = g.mode
    # wisp companion: colour = the tier that is ready (or charging)
    mt = p.meter
    pw_ = mt.power()
    ti = pw_ if pw_ >= 0 else 0
    if pw_ < 0:
        for i in range(mt.n):
            if mt.f[i] < S.TIER:
                ti = i
                break
    spr(g, a.wisp[ti], g.wx - 5 - c, g.wy - 5)
    if not (p.inv and (tick & 2) and p.hurt_t == 0 and m == 3):
        fr = p.frame(tick) if m != 4 else (F_FALL if g.t < 40 else 2 + ((tick >> 1) & 3))
        spr(g, a.kiro[fr], (p.x >> 4) - 10 - c, (p.y >> 4) - 5, 1 if p.face < 0 else 0)
    yield
    # ---- effects ----
    for q in g.pt:
        fx(g, 3, q[0] - c, q[1], 2, 2, q[5])
    for q in g.pops:
        x = q[0] - c
        for d in q[2]:
            mask(g, g.glyphs[d], x, q[1], C_YEL)
            x += 6
    ambient(g, c, a.area)
    vf = g.void_fx
    if vf is not None:
        r = 8 + vf[2] * 7
        if vf[2] > 10:
            r = 78 - (vf[2] - 10) * 14
        fx(g, 1, vf[0] - c, vf[1], r, 0, FX_VOID)
        fx(g, 1, vf[0] - c, vf[1], r >> 1, 1, C_WHITE)
    yield
    hud(g)
    ui(g)
    P[R.NS] = g.ns
    P[R.NFX] = g.nfx


def hud(g):
    p = g.player
    a = g.pack
    for i in range(p.maxhp):
        spr(g, a.heart[0 if i < p.hp else 1], 4 + i * 11, 4)
    spr(g, a.coin[0], 4, 16)
    if p.coins != g.coin_n:
        g.coin_n = p.coins
        g.coin_dg = [ord(ch) - 48 for ch in str(p.coins)]
    digits(g, g.coin_dg, 15, 17, C_YEL)
    if p.score != g.sc_n:
        g.sc_n = p.score
        s = str(p.score)
        g.sc_dg = [ord(ch) - 48 for ch in ("000000" + s)[-6:]]
    digits(g, g.sc_dg, 278, 18, C_WHITE)
    if g.lvn != g.wl_n:
        g.wl_n = g.lvn
        n = g.lvn - 1
        g.wl_dg = [n // 3 + 1, 10, n % 3 + 1]
    digits(g, g.wl_dg, 150, 4, C_DIM)
    # ability meter: green -> orange -> purple layered bar (effect rects)
    m = p.meter
    T = S.TIER
    n = m.n
    pwr = m.power()
    fx(g, 3, 250, 4, 66, 11, M_BORDER[n - 1])
    fx(g, 3, 251, 5, 64, 9, M_BG)
    full = 0
    for i in range(n):
        w = m.f[i] * 64 // T
        if w:
            fx(g, 3, 251, 5, w, 9, M_FILL[i])
        if i == pwr:
            full = w
    if pwr >= 0 and (g.tick >> 3) & 1:
        fx(g, 3, 251, 5, full, 2, 0xFFFF)
    bs = g.boss
    if bs is not None and bs.st != 10:
        fx(g, 3, 95, 28, 130, 8, BAR_OUT)
        fx(g, 3, 96, 29, 128, 6, BAR_BG)
        w = bs.hp * 128 // bs.maxhp
        if w:
            fx(g, 3, 96, 29, w, 6, BAR_FG)
