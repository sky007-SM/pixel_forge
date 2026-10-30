# ============================================================
# Enemies, projectiles, rift zones and blade hazards (whole pixels).
#
# Forest  : Slime (patrols, stompable), Thorn Mushroom (spiky: never stomp it),
#           Shadow Bat (sine flight, dives)
# Mountain: Ember Spirit (shoots), Stone Guardian (armoured), Lava Hawk (fast,
#           tracks you)
# Castle  : Void Stalker (teleports), Rift Wraith (danger zones + volleys),
#           Dread Knight (charge + shockwaves)
# Ground walkers turn around at walls, ledges AND spike / lava tiles.
# ============================================================
import math
from games.shards import physics as ph

SLIME = 0
MUSH = 1
BAT = 2
EMBER = 3
GUARD = 4
HAWK = 5
STALK = 6
WRAITH = 7
KNIGHT = 8

#      w   h  hp stomp armor score frames
SPEC = (
    (16, 10, 1, 1, 0, 100, 2),
    (16, 17, 2, 0, 0, 150, 2),
    (20, 12, 1, 1, 0, 200, 3),
    (14, 24, 2, 0, 0, 250, 3),
    (26, 27, 4, 1, 1, 400, 2),
    (24, 16, 2, 1, 0, 300, 3),
    (16, 28, 3, 1, 0, 350, 2),
    (26, 20, 3, 0, 0, 450, 2),
    (22, 30, 6, 0, 1, 600, 2),
)
GROUND = (SLIME, MUSH, GUARD, STALK, KNIGHT)
SIN = tuple(int(10 * math.sin(i * math.pi / 16)) for i in range(32))

PK_SPEAR = 0
PK_VOID = 1
PK_FIRE = 2
PK_SHADOW = 3
PK_WAVE = 4
PK_ROCK = 5
PK_SEED = 6


def aim(dx, dy, sp):
    n = abs(dx)
    if abs(dy) > n:
        n = abs(dy)
    if n == 0:
        return sp, 0
    vx = (abs(dx) * sp) // n
    vy = (abs(dy) * sp) // n
    return (vx if dx >= 0 else -vx), (vy if dy >= 0 else -vy)


class Enemy:
    def __init__(self, kind, tx, ty):
        w, h, hp, st, ar, sc, nf = SPEC[kind]
        self.kind = kind
        self.w = w
        self.h = h
        self.hp = hp
        self.stomp = st
        self.armor = ar
        self.score = sc
        self.nf = nf
        self.x = tx * 16 + ((16 - w) >> 1)
        self.y = ty * 16 - h if kind in GROUND else ty * 16
        self.hx = self.x
        self.hy = self.y
        self.base = self.x
        self.dir = -1
        self.vx = 0
        self.vy = 0
        self.t = 0
        self.t2 = 0
        self.st = 0
        self.alive = True
        self.flash = 0
        self.aid = -1
        self.vis = True
        self.harm = True
        self.fr = 0
        self.cd = 40 + (tx * 7) % 60

    def hit(self, dmg, g):
        if not self.alive:
            return
        if self.armor:
            dmg -= self.armor
            if dmg < 1:
                dmg = 1
        self.hp -= dmg
        self.flash = 6
        if self.hp <= 0:
            self.kill(g)
        else:
            g.snd("sh_hit", 2)

    def kill(self, g):
        if self.alive:
            self.alive = False
            g.on_kill(self)

    # ---- behaviour ----
    def update(self, g):
        if self.flash:
            self.flash -= 1
        self.t += 1
        k = self.kind
        if k == SLIME:
            self._patrol(g, 1)
        elif k == MUSH:
            self._patrol(g, 2)
        elif k == GUARD:
            self._patrol(g, 2)
        elif k == BAT:
            self._bat(g, 3)
        elif k == HAWK:
            self._bat(g, 6)
        elif k == EMBER:
            self._ember(g)
        elif k == STALK:
            self._stalk(g)
        elif k == WRAITH:
            self._wraith(g)
        else:
            self._knight(g)

    def _blocked(self, g, d):
        ax = self.x + (self.w if d > 0 else -1)
        y = self.y
        if g.solid_px(ax, y + (self.h >> 1)):
            return True
        if g.hazard_px(ax, y + self.h - 3):
            return True                         # never walk into spikes / lava
        return not g.support_px(ax, y + self.h + 1)

    def _patrol(self, g, every):
        if self.t % every == 0:
            if self._blocked(g, self.dir):
                self.dir = -self.dir
            else:
                self.x += self.dir
        self.fr = (self.t >> 3) & 1

    def _bat(self, g, spd):
        """Sine patrol; when the player is near below it winds up (blinks), dives, returns.
        spd 3 = Shadow Bat, 6 = Lava Hawk (hunts from further away)."""
        p = g.player
        pcx = (p.x >> 4) + 5
        pcy = (p.y >> 4) + 11
        st = self.st
        cx = self.x + (self.w >> 1)
        cy = self.y + (self.h >> 1)
        self.fr = (self.t >> 2) % self.nf
        if st == 0:
            fast = spd > 3
            if fast:
                if abs(pcx - self.hx) < 260:
                    self.hx += (pcx - self.hx) // 24
                self.hy += ((pcy - 70) - self.hy) // 30
                if self.hy < 40:
                    self.hy = 40
            else:
                self.hx += self.dir
                if abs(self.hx - self.base) > 60:
                    self.dir = -self.dir
            self.x = self.hx + SIN[(self.t >> 1) & 31]
            self.y = self.hy + (SIN[(self.t + 8) & 31] >> 1)
            self.cd -= 1
            reach = 200 if fast else 110
            if self.cd <= 0 and abs(pcx - cx) < reach and pcy > cy - 10:
                self.st = 1
                self.t2 = 10
        elif st == 1:
            self.t2 -= 1
            self.vis = (self.t2 & 2) == 0
            if self.t2 <= 0:
                self.vis = True
                self.vx, self.vy = aim(pcx - cx, pcy - cy, spd)
                self.st = 2
                self.t2 = 28
                g.snd("sh_dive", 1)
        elif st == 2:
            self.x += self.vx
            self.y += self.vy
            self.t2 -= 1
            if self.t2 <= 0 or self.y > 200:
                self.st = 3
        else:
            dx = self.hx - self.x
            dy = self.hy - self.y
            if abs(dx) < 4 and abs(dy) < 4:
                self.st = 0
                self.cd = 70 if spd > 3 else 100
            else:
                vx, vy = aim(dx, dy, 3)
                self.x += vx
                self.y += vy

    def _ember(self, g):
        p = g.player
        pcx = (p.x >> 4) + 5
        pcy = (p.y >> 4) + 11
        cx = self.x + 7
        cy = self.y + 12
        self.dir = 1 if pcx > cx else -1
        d = abs(pcx - cx)
        if d > 120:
            self.x += self.dir
        elif d < 60:
            self.x -= self.dir
        self.y = self.hy + (SIN[(self.t >> 1) & 31] >> 1)
        self.fr = (self.t >> 2) % self.nf
        self.cd -= 1
        if self.cd <= 0 and d < 220 and abs(pcy - cy) < 140:
            vx, vy = aim(pcx - cx, pcy - cy, 3)
            g.add_proj(PK_FIRE, cx - 4, cy - 4, vx, vy, 8, 8, 90)
            g.snd("sh_shoot", 1)
            self.cd = 80

    def _stalk(self, g):
        p = g.player
        pcx = (p.x >> 4) + 5
        st = self.st
        self.t2 += 1
        if st == 0:
            self.vis = True
            self.harm = True
            self.dir = 1 if pcx > self.x else -1
            self.fr = 0
            if self.t2 > 60 and abs(pcx - self.x) < 190:
                self.st = 1
                self.t2 = 0
        elif st == 1:                       # vanish
            self.vis = False
            self.harm = False
            if self.t2 >= 14:
                nx = pcx - p.face * 48 - (self.w >> 1)
                gy = g.ground_y(nx + (self.w >> 1), (p.y >> 4) + 8)
                if gy and nx > 8:
                    self.x = nx
                    self.y = gy - self.h
                self.dir = 1 if pcx > self.x else -1
                self.st = 2
                self.t2 = 0
                g.snd("sh_tele", 2)
        elif st == 2:                       # reappear (telegraph)
            self.vis = (self.t2 & 2) == 0
            self.harm = False
            self.fr = 1
            if self.t2 >= 18:
                self.vis = True
                self.harm = True
                self.st = 3
                self.t2 = 0
        else:                               # lunge
            if not self._blocked(g, self.dir):
                self.x += self.dir * 4
            self.fr = (self.t >> 2) & 1
            if self.t2 >= 16:
                self.st = 0
                self.t2 = 0

    def _wraith(self, g):
        p = g.player
        pcx = (p.x >> 4) + 5
        self.dir = 1 if pcx > self.x else -1
        if abs(pcx - self.x) > 50:
            self.x += self.dir
        self.y = self.hy + SIN[(self.t >> 1) & 31]
        self.fr = (self.t >> 3) & 1
        self.cd -= 1
        if self.cd <= 0 and abs(pcx - self.x) < 220:
            self.cd = 100
            if self.st == 0:
                gy = g.ground_y(pcx, (p.y >> 4) + 8)
                if gy:
                    g.add_rift(pcx - 14, gy - 12)
                    g.snd("sh_rift", 2)
            else:
                cy = self.y + 10
                for off in (-1, 0, 1):
                    vx, vy = aim(pcx - self.x, (p.y >> 4) + 10 - cy + off * 14, 3)
                    g.add_proj(PK_SHADOW, self.x + 9, cy - 4, vx, vy, 8, 8, 100)
                g.snd("sh_shoot", 1)
            self.st = 1 - self.st

    def _knight(self, g):
        p = g.player
        pcx = (p.x >> 4) + 5
        st = self.st
        self.t2 += 1
        if st == 0:
            self._patrol(g, 1)
            near = abs(pcx - self.x) < 200 and abs((p.y >> 4) - self.y) < 40
            toward = (pcx > self.x) == (self.dir > 0)
            if near and toward and self.t2 > 45:
                self.st = 1
                self.t2 = 0
        elif st == 1:                       # wind-up
            self.fr = 1
            if self.t2 >= 22:
                self.st = 2
                self.t2 = 0
                g.snd("sh_charge", 2)
        elif st == 2:                       # charge
            self.fr = (self.t >> 1) & 1
            if self._blocked(g, self.dir) or self.t2 >= 36:
                self.st = 3
                self.t2 = 0
                g.add_proj(PK_WAVE, self.x + self.w, self.y + self.h - 14, 4, 0, 14, 14, 60)
                g.add_proj(PK_WAVE, self.x - 14, self.y + self.h - 14, -4, 0, 14, 14, 60)
                g.snd("sh_wave", 3)
            else:
                self.x += self.dir * 5
        else:                               # recover
            self.fr = 0
            if self.t2 >= 36:
                self.st = 0
                self.t2 = 0


class Proj:
    def __init__(self, kind, x, y, vx, vy, w, h, life, grav=0):
        self.kind = kind
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.w = w
        self.h = h
        self.life = life
        self.grav = grav
        self.t = 0
        self.alive = True
        self.fr = 0

    def update(self):
        self.t += 1
        self.x += self.vx
        self.y += self.vy
        if self.grav and (self.t & 1):
            self.vy += self.grav
        self.fr = (self.t >> 2) & 1
        self.life -= 1
        if self.life <= 0:
            self.alive = False


class Rift:
    """Ground danger zone: telegraphs for 36 frames, then hurts."""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.w = 28
        self.h = 12
        self.t = 0
        self.alive = True

    def update(self):
        self.t += 1
        if self.t > 130:
            self.alive = False

    def active(self):
        return self.t > 36


class Blade:
    """Sliding saw. Axis 0 = horizontal between lo..hi, 1 = vertical."""

    def __init__(self, axis, x, y, lo, hi, v):
        self.axis = axis
        self.x = x
        self.y = y
        self.w = 16
        self.h = 16
        self.lo = lo
        self.hi = hi
        self.v = v
        self.dis = 0
        self.t = 0

    def update(self):
        self.t += 1
        if self.dis:
            self.dis -= 1
            return
        if self.axis == 0:
            self.x += self.v
            if self.x <= self.lo or self.x >= self.hi:
                self.v = -self.v
        else:
            self.y += self.v
            if self.y <= self.lo or self.y >= self.hi:
                self.v = -self.v
