# ============================================================
# Level generator (transient module: built, then unloaded).
#
# 9 levels = 3 areas x 3. Each level is assembled from segments (flat runs,
# gaps, spike runs, hills, ledge paths, ? block rows and area hazards) with
# a fixed seed, so a level is identical every time but costs almost no code
# or RAM. The third level of each area ends in a boss arena; the others end
# at a flagpole.
#
#  1-1 Sprout Trail      1-2 Mushroom Hollow     1-3 Thornwood Warden  (boss)
#  2-1 Cinder Path       2-2 Collapsing Tunnel   2-3 Magma Titan       (boss)
#  3-1 Castle Gate       3-2 Rift Halls          3-3 The Void King     (boss)
# ============================================================
from games.shards import enemies as E
from games.shards.physics import Level, Plat

NAMES = ("SPROUT TRAIL", "MUSHROOM HOLLOW", "THE THORNWOOD WARDEN",
         "CINDER PATH", "THE COLLAPSING TUNNEL", "THE MAGMA TITAN",
         "CASTLE GATE", "THE RIFT HALLS", "THE VOID KING")
AREAS = ("THE WHISPERING FOREST", "THE ASHEN MOUNTAINS", "THE VOID KINGS CASTLE")
RUN = (96, 126, 44, 116, 140, 44, 130, 156, 44)
GROUND = ((E.SLIME, E.MUSH), (E.GUARD,), (E.STALK, E.KNIGHT))
AIR = ((E.BAT,), (E.EMBER, E.HAWK), (E.WRAITH,))
DENS = (48, 58, 56)


class Rng:
    def __init__(self, s):
        self.s = s & 0x7FFFFFFF

    def n(self, k):
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return (self.s >> 8) % k


def build(n):
    a = (n - 1) // 3
    sub = (n - 1) % 3
    boss = sub == 2
    r = Rng(n * 7919 + 17)
    run = RUN[n - 1]
    lw = run + (20 if boss else 14)
    lv = Level(lw, a)
    G = lv.ground
    gnd = GROUND[a]
    air = AIR[a]
    dens = DENS[sub]
    esc = a == 1 and sub == 1
    stop = run - (44 if esc else 0)
    hearts = [0]

    def coins(x0, x1, row):
        for x in range(x0, x1 + 1):
            lv.items.append((0, x, row))

    def arc(x, w, base):
        for i in range(w):
            up = (1 if 0 < i < w - 1 else 0) + (1 if w // 2 - 1 <= i <= w // 2 else 0)
            lv.items.append((0, x + i, base - up))

    def spawn(x, L, top, force=False):
        if L >= 6 and (force or r.n(100) < dens):
            lv.en.append((gnd[r.n(len(gnd))], x + L // 2, top))
        if r.n(100) < dens // 2:
            lv.en.append((air[r.n(len(air))], x + 2 + r.n(max(1, L - 3)), 6 + r.n(3)))

    def decor(x, L):
        for _ in range(1 + r.n(2)):
            lv.decor.append((r.n(4), x * 16 + r.n(max(1, L * 16 - 20)), 192))

    def qblocks(x0):
        lv.put(x0, 8, 8)
        lv.put(x0 + 1, 8, 3)
        lv.put(x0 + 2, 8, 8)

    def flat(x, L, top=12):
        G(x, x + L - 1, top)

    G(0, 13)
    x = 14
    last_cp = 0
    prev_gap = True
    while x < stop:
        k = r.n(100)
        seg = 0
        if not prev_gap:
            seg = 1 if k >= 24 else 0
            if k >= 44:
                seg = 2
            if k >= 56:
                seg = 3
            if k >= 68:
                seg = 4
            if k >= 80:
                seg = 5
        prev_gap = False
        if seg == 0:                                    # ---- flat run
            L = 6 + r.n(5)
            flat(x, L)
            spawn(x, L, 12)
            if r.n(100) < 45:
                coins(x + 1, x + L - 2, 10)
            if L >= 8 and r.n(100) < 40:
                qblocks(x + 2)
            if hearts[0] < 2 and r.n(100) < 12:
                hearts[0] += 1
                lv.items.append((1, x + L // 2, 10))
            decor(x, L)
            if x - last_cp >= 36:
                lv.cps.append((x + L // 2, 12))
                last_cp = x
            x += L
        elif seg == 1:                                  # ---- gap
            gp = 3 + r.n(2) + (r.n(2) if a else 0)
            if a:
                lv.rect(x, 13, x + gp - 1, 14, 5)
            elif gp >= 4:
                lv.rect(x + gp // 2 - 1, 10, x + gp // 2, 10, 7)
            arc(x, gp, 9)
            x += gp
            prev_gap = True
        elif seg == 2:                                  # ---- spike run
            L = 8
            flat(x, L)
            ns = 2 + r.n(2)
            lv.rect(x + 3, 11, x + 2 + ns, 11, 4)
            arc(x + 2, ns + 2, 9)
            if r.n(100) < dens:
                lv.en.append((gnd[0], x + L - 2, 12))
            decor(x, L)
            x += L
        elif seg == 3:                                  # ---- hill
            h = 1 + r.n(2)
            L = 5 + r.n(3)
            flat(x, L, 12 - h)
            spawn(x, L, 12 - h)
            coins(x + 1, x + L - 2, 12 - h - 3)
            x += L
        elif seg == 4:                                  # ---- ledge path
            L = 9
            flat(x, L)
            lv.rect(x + 1, 9, x + 3, 9, 7)
            lv.rect(x + 5, 9, x + 7, 9, 7)
            coins(x + 1, x + 3, 8)
            coins(x + 5, x + 7, 8)
            if r.n(100) < 55:
                lv.items.append((2, x + 6, 7))
            spawn(x, L, 12)
            x += L
        else:                                           # ---- area special
            if a == 0:
                flat(x, 8)
                qblocks(x + 2)
                lv.put(x + 5, 8, 8)
                coins(x + 1, x + 6, 10)
                spawn(x, 8, 12)
                x += 8
            else:
                pick = r.n(3)
                if pick == 0 and a == 1:                # collapsing bridge
                    lv.rect(x, 13, x + 4, 14, 5)
                    lv.plats.append(Plat(2, x * 16, 12 * 16, 5 * 16))
                    x += 5
                    prev_gap = True
                elif pick == 1 or (pick == 0 and a == 2 and False):
                    lv.rect(x, 13, x + 5, 14, 5)        # moving platform
                    lv.plats.append(Plat(0, x * 16, 10 * 16, 48, x * 16, (x + 3) * 16, 2))
                    x += 6
                    prev_gap = True
                elif a == 1:                            # rockfall
                    flat(x, 9)
                    for i in (2, 5, 7):
                        lv.rocks.append(((x + i) * 16 + 1, 80, i * 17))
                    spawn(x, 9, 12, True)
                    x += 9
                elif pick == 0:                         # blinking crystal platforms
                    lv.rect(x, 13, x + 6, 14, 5)
                    lv.plats.append(Plat(3, (x + 1) * 16, 10 * 16, 32, ph=0))
                    lv.plats.append(Plat(3, (x + 4) * 16, 10 * 16, 32, ph=45))
                    x += 7
                    prev_gap = True
                else:                                   # blade corridor
                    flat(x, 10)
                    lv.blades.append(E.Blade(0, (x + 1) * 16, 176, (x + 1) * 16, (x + 8) * 16, 2 + r.n(2)))
                    spawn(x, 10, 12)
                    x += 10
    if esc:
        lv.escape = x * 16
        while x < run:
            k = r.n(100)
            if k < 55 or prev_gap:
                L = 6 + r.n(3)
                flat(x, L)
                lv.rocks.append(((x + 3) * 16 + 1, 70, r.n(60)))
                coins(x + 1, x + L - 2, 10)
                x += L
                prev_gap = False
            else:
                gp = 3 + r.n(2)
                lv.rect(x, 13, x + gp - 1, 14, 5)
                arc(x, gp, 9)
                x += gp
                prev_gap = True
    G(x, lw - 1)
    if boss:
        lv.arena = run * 16
        lv.cps.append((run - 5, 12))
        lv.rect(run + 3, 9, run + 5, 9, 7)
        lv.rect(run + 14, 9, run + 16, 9, 7)
        lv.items.append((1, run + 9, 11))
    else:
        lv.goal = (lw - 8) * 16
        lv.cps.append((lw - 18, 12))
    lv.cps = [c for i, c in enumerate(lv.cps) if i == 0 or c[0] > lv.cps[0][0] + 12]
    lv.cps.sort()
    lv.items.sort(key=lambda t: t[1])
    return lv
