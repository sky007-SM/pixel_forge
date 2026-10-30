# ============================================================
# Area bosses (loaded only on boss levels).
#   kind 0  Thornwood Warden  (forest)   swing, slam, seed volley, charge
#   kind 1  Magma Titan       (mountain) slam, fireball fan, rock rain, charge
#   kind 2  The Void King     (castle)   3 phases: sword / void / final form
#
# Every attack is  telegraph (warn flag, "!" icon, flashing palette, sound)
#               -> active    (harmful rects)
#               -> recovery  (vulnerable)
# The Void King's final form is only exposed in the stagger after his beam:
# jump it, stand on the floating ledges, or Fire Dash through it.
# Harmful rects and effect rects live in preallocated lists refilled each frame.
# ============================================================
from hardware.display import P16
from games.shards import enemies as E

INTRO = 0
IDLE = 1
SWING = 2
CHARGE = 3
SLAM = 4
TELE = 5
VOLLEY = 6
BEAM = 7
RAIN = 8
TRANS = 9
DEAD = 10

#       w   h  hp  phase2 phase3
SPEC = ((36, 54, 24, 12, 0), (40, 54, 30, 15, 0), (34, 70, 40, 20, 8))
SEQ = (
    ((SWING, SLAM, VOLLEY, CHARGE, SLAM), (CHARGE, VOLLEY, SWING, SLAM, VOLLEY)),
    ((SLAM, VOLLEY, RAIN, CHARGE), (RAIN, SLAM, VOLLEY, RAIN, CHARGE)),
    ((SWING, CHARGE, SLAM, SWING, SLAM, CHARGE),
     (SWING, TELE, VOLLEY, CHARGE, TELE, SLAM, VOLLEY),
     (BEAM, SLAM, VOLLEY, TELE, BEAM, CHARGE, VOLLEY, TELE)),
)
SHOT = (E.PK_SEED, E.PK_FIRE, E.PK_SHADOW)

C_RED = P16(0xF800)
C_MAG = P16(0xF81F)
C_VIO = P16(0xA01F)
C_ORG = P16(0xFC00)


class Boss:
    def __init__(self, kind, ax, fy):
        w, h, hp, p2, p3 = SPEC[kind]
        self.kind = kind
        self.ax = ax
        self.fy = fy
        self.w = w
        self.h = h
        self.x = ax + 320 - 70
        self.y = fy - h
        self.hp = hp
        self.maxhp = hp
        self.p2 = p2
        self.p3 = p3
        self.phase = 1
        self.last = 3 if p3 else 2
        self.st = INTRO
        self.s = 0
        self.u = 0
        self.t = 0
        self.face = -1
        self.vul = False
        self.warn = False
        self.vis = True
        self.flash = 0
        self.n = 0
        self.nxt = SWING
        self.aid = -1
        self.rects = [[0, 0, 0, 0], [0, 0, 0, 0]]
        self.nr = 0
        self.fxl = [[0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]]
        self.nf = 0
        self.xs = [0, 0, 0, 0, 0]
        self.nx = 0
        self.done = False

    # ---------------- helpers ----------------
    def T(self, n):
        return n if self.phase < self.last else (n * 3) >> 2

    def _rect(self, x, y, w, h):
        r = self.rects[self.nr]
        r[0] = x
        r[1] = y
        r[2] = w
        r[3] = h
        self.nr += 1

    def _fxr(self, t, x, y, w, h, col):
        f = self.fxl[self.nf]
        f[0] = t
        f[1] = x
        f[2] = y
        f[3] = w
        f[4] = h
        f[5] = col
        self.nf += 1

    def _bounds(self):
        return self.ax + 16, self.ax + 320 - 16 - self.w

    def _clamp(self):
        lo, hi = self._bounds()
        if self.x < lo:
            self.x = lo
        if self.x > hi:
            self.x = hi

    def _set(self, st):
        self.st = st
        self.s = 0
        self.u = 0
        self.warn = False
        self.vul = False
        self.vis = True
        self.nr = 0
        self.nf = 0
        self.nx = 0

    def _idle(self):
        self._set(IDLE)
        self.n += 1
        seq = SEQ[self.kind][self.phase - 1]
        self.nxt = seq[self.n % len(seq)]
        self.y = self.fy - self.h

    def _face(self, pcx):
        self.face = 1 if pcx > self.x + (self.w >> 1) else -1

    def exposed_rule(self):
        return not (self.kind == 2 and self.phase == 3)

    def frame(self):
        """0 idle, 1 warning (red tint), 2 crystal exposed (King final form)."""
        if self.warn:
            return 1
        if self.vul and self.kind == 2 and self.phase == 3:
            return 2
        return 0

    # ---------------- damage in ----------------
    def hurt(self, dmg, g, aid=0):
        if self.st == TRANS or self.st == DEAD or self.st == INTRO:
            return 0
        if aid and aid == self.aid:
            return 0
        if not self.vul:
            g.snd("sh_block", 2)
            return 0
        self.aid = aid
        self.hp -= dmg
        self.flash = 8
        g.snd("sh_hit", 2)
        if self.hp <= 0:
            self.hp = 0
            self._set(DEAD)
            g.on_boss_dying()
        elif self.phase == 1 and self.hp <= self.p2:
            self._set(TRANS)
        elif self.phase == 2 and self.p3 and self.hp <= self.p3:
            self._set(TRANS)
        return dmg

    # ---------------- per frame ----------------
    def update(self, g):
        p = g.player
        pcx = (p.x >> 4) + 5
        self.t += 1
        if self.flash:
            self.flash -= 1
        self.nr = 0
        self.nf = 0
        st = self.st
        if st == INTRO:
            self._face(pcx)
            if self.t == 1:
                g.snd("sh_b_intro", 5)
            if self.t >= 80:
                self._idle()
        elif st == IDLE:
            self.u += 1
            self._face(pcx)
            self.vul = self.exposed_rule()
            dist = abs(pcx - (self.x + (self.w >> 1)))
            if self.nxt == SWING and dist > 56 and self.u < 70:
                self.x += self.face * 2
                self._clamp()
            elif self.u >= self.T(30):
                self._set(self.nxt)
        elif st == SWING:
            self._swing(g, pcx)
        elif st == CHARGE:
            self._charge(g, pcx)
        elif st == SLAM:
            self._slam(g, pcx)
        elif st == TELE:
            self._tele(g, pcx)
        elif st == VOLLEY:
            self._volley(g, pcx)
        elif st == BEAM:
            self._beam(g, pcx)
        elif st == RAIN:
            self._rain(g, pcx)
        elif st == TRANS:
            self.u += 1
            self.vis = (self.u & 4) == 0 or self.u > 60
            if self.u == 1:
                self.phase += 1
                g.arena_change(self.kind, self.phase)
            if self.u >= 70:
                self._idle()
        else:
            self.u += 1
            self.vis = (self.u & 2) == 0
            if self.u >= 70 and not self.done:
                self.done = True
                self.vis = False
                g.boss_dead()

    def _tel(self, g, pcx, u, face_until):
        self.warn = True
        if u == 1:
            g.snd("sh_b_warn", 3)
        if u < face_until:
            self._face(pcx)

    def _swing(self, g, pcx):
        s = self.s
        self.u += 1
        u = self.u
        if s == 0:
            self._tel(g, pcx, u, 10)
            if u >= self.T(22):
                self.s = 1
                self.u = 0
                self.warn = False
                g.snd("sh_b_swing", 3)
        elif s == 1:
            reach = 46
            x0 = self.x + self.w - 4 if self.face > 0 else self.x - reach + 4
            self._rect(x0, self.y + 6, reach, self.h - 18)
            self._fxr(2, x0, self.y + 6, reach, self.h - 18, C_RED)
            if u >= 6:
                self.s = 2
                self.u = 0
        else:
            self.vul = self.exposed_rule()
            if u >= self.T(28):
                self._idle()

    def _charge(self, g, pcx):
        s = self.s
        self.u += 1
        u = self.u
        if s == 0:
            self._tel(g, pcx, u, 14)
            if u >= self.T(26):
                self.s = 1
                self.u = 0
                self.warn = False
                g.snd("sh_charge", 3)
        elif s == 1:
            self.x += self.face * 6
            self._rect(self.x, self.y + 4, self.w, self.h - 4)
            lo, hi = self._bounds()
            if self.x <= lo or self.x >= hi or u >= 44:
                wall = self.x <= lo or self.x >= hi
                self._clamp()
                self.s = 2
                self.u = -14 if wall else 0
                g.shake = 8
                g.snd("sh_b_slam", 4)
        else:
            self.vul = self.exposed_rule()
            if u >= self.T(34):
                self._idle()

    def _slam(self, g, pcx):
        s = self.s
        self.u += 1
        u = self.u
        if s == 0:
            self._tel(g, pcx, u, 0)
            if u >= self.T(18):
                self.s = 1
                self.u = 0
                self.warn = False
        elif s == 1:
            if u < 4:
                self._face(pcx)
            hgt = (u * (16 - u) * 36) >> 6
            self.y = self.fy - self.h - hgt
            if u < 12:
                self.x += self.face * 3
            self._clamp()
            if u >= 16:
                self.y = self.fy - self.h
                cx = self.x + (self.w >> 1)
                g.add_proj(E.PK_WAVE, cx + 8, self.fy - 14, 4, 0, 14, 14, 80)
                g.add_proj(E.PK_WAVE, cx - 22, self.fy - 14, -4, 0, 14, 14, 80)
                g.shake = 10
                g.snd("sh_b_slam", 4)
                self.s = 2
                self.u = 0
        else:
            self.vul = self.exposed_rule()
            if u >= self.T(28):
                self._idle()

    def _tele(self, g, pcx):
        s = self.s
        self.u += 1
        u = self.u
        if s == 0:
            self.vis = False
            if u == 1:
                g.snd("sh_tele", 3)
            if u >= 14:
                nx = pcx - g.player.face * 60 - (self.w >> 1)
                self.x = nx
                self._clamp()
                if abs(pcx - (self.x + (self.w >> 1))) < 30:
                    lo, hi = self._bounds()
                    self.x = lo + 8 if pcx > self.ax + 160 else hi - 8
                self._face(pcx)
                self.s = 1
                self.u = 0
        else:
            self.vis = (u & 2) == 0
            self.warn = True
            if u >= 8:
                self._set(SWING)
                self._face(pcx)
                self.u = self.T(22) - 12

    def _volley(self, g, pcx):
        s = self.s
        self.u += 1
        u = self.u
        if s == 0:
            self._tel(g, pcx, u, 12)
            if u >= self.T(24):
                cx = self.x + (self.w >> 1)
                f = self.face
                if self.kind == 2 and self.phase == 3:
                    vys = (-3, -1, 1, 3)
                elif self.phase >= 2 and self.kind == 1:
                    vys = (-3, -1, 0, 1, 3)
                else:
                    vys = (-2, 0, 2)
                sh = SHOT[self.kind]
                for vy in vys:
                    g.add_proj(sh, cx - 4, self.y + 16, f * 3, vy, 8, 8, 120)
                g.snd("sh_shoot", 3)
                self.s = 1
                self.u = 0
                self.warn = False
        else:
            self.vul = self.exposed_rule()
            if u >= self.T(30):
                self._idle()

    def _rain(self, g, pcx):
        s = self.s
        self.u += 1
        u = self.u
        if s == 0:
            self._tel(g, pcx, u, 0)
            if u == 1:
                lo, hi = self._bounds()
                for i in range(5):
                    self.xs[i] = lo + 10 + i * ((hi - lo) // 4) + ((pcx + i * 37) % 24)
                self.nx = 5
            if u >= self.T(36):
                for i in range(5):
                    g.add_proj(E.PK_ROCK, self.xs[i], -16, 0, 3, 14, 14, 90, 1)
                g.snd("sh_rock", 2)
                self.nx = 0
                self.s = 1
                self.u = 0
                self.warn = False
        else:
            self.vul = True
            if u >= self.T(50):
                self._idle()

    def _beam(self, g, pcx):
        s = self.s
        self.u += 1
        u = self.u
        by = self.fy - 20
        if s == 0:
            self.warn = True
            if u == 1:
                g.snd("sh_b_beam0", 4)
            if u < 18:
                self._face(pcx)
            x0, w0 = self._beam_span()
            if (u & 4) == 0:
                self._fxr(3, x0, by + 7, w0, 2, C_MAG)
            if u >= self.T(44):
                self.s = 1
                self.u = 0
                self.warn = False
                g.snd("sh_b_beam1", 4)
        elif s == 1:
            x0, w0 = self._beam_span()
            self._rect(x0, by, w0, 16)
            self._fxr(2, x0, by - 3, w0, 22, C_VIO)
            self._fxr(3, x0, by + 4, w0, 8, 0xFFFF)
            g.shake = 2
            if u >= 36:
                self.s = 2
                self.u = 0
        else:
            self.vul = True
            if u >= 70:
                self._idle()

    def _beam_span(self):
        if self.face > 0:
            x0 = self.x + self.w
            return x0, self.ax + 320 - x0
        return self.ax, self.x - self.ax
