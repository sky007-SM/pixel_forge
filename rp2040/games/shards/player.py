# ============================================================
# Kiro: movement, jump / double jump, melee combo, ground pound,
# fire dash and the ability meter.
#
# Controls: stick L/R = move, A = jump (A again near the apex = double jump,
# hold A for a higher jump), X = attack (X in the air = ground pound),
# Y = ability, B = pause menu.
# ============================================================
from hardware.input import BTN_A, BTN_X, BTN_Y, DIR_L, DIR_R, DIR_D
from games.shards import settings as S
from games.shards import physics as ph

# sprite frame ids
F_IDLE = 0
F_RUN0 = 2
F_JUMP = 6
F_FALL = 7
F_DASH = 8
F_PUNCH1 = 9
F_PUNCH2 = 10
F_SLASH = 11
F_POUND = 12
F_HURT = 13
SWING_SFX = ("sh_atk0", "sh_atk1", "sh_atk2")


class Meter:
    """Green -> orange -> purple layered charge bar.

    f[i] is how full tier i is (0..TIER). The lowest tier that is not full is
    charging. The highest FULL tier is what a button press releases:
    green = Rootspike, orange = Fire Dash, purple = Void Collapse."""

    def __init__(self, n, rates, carry=0):
        self.n = n
        self.rates = rates
        self.f = [carry, 0, 0]

    def add(self, amt):
        f = self.f
        i = 0
        while i < self.n:
            if f[i] < S.TIER:
                v = f[i] + amt
                f[i] = v if v < S.TIER else S.TIER
                return
            i += 1

    def tick(self):
        f = self.f
        i = 0
        while i < self.n:
            if f[i] < S.TIER:
                self.add(self.rates[i])
                return
            i += 1

    def power(self):
        k = -1
        i = 0
        while i < self.n:
            if self.f[i] >= S.TIER:
                k = i
            else:
                break
            i += 1
        return k

    def clear(self):
        f = self.f
        f[0] = 0
        f[1] = 0
        f[2] = 0

    def carry(self):
        c = 0
        i = 0
        while i < self.n:
            if self.f[i] > 0:
                c = self.f[i]
            i += 1
        return c


class Player:
    def __init__(self):
        self.w = 10
        self.h = 22
        self.hp = S.START_HP
        self.maxhp = S.START_HP
        self.coins = 0
        self.score = 0
        self.dj = False
        self.meter = None
        self.ar = [0, 0, 0, 0, 0]
        self.bcx = 0
        self.bcy = 0
        self.reset_pos(0, 0)

    def reset_pos(self, px, py):
        self.x = px << 4
        self.y = py << 4
        self.vx = 0
        self.vy = 0
        self.face = 1
        self.ground = False
        self.stand = None
        self.bumped = False
        self.drop = 0
        self.coy = 0
        self.jbuf = 0
        self.jh = False
        self.air_dj = False
        self.inv = 0
        self.hurt_t = 0
        self.atk_t = 0
        self.combo = 0
        self.combo_t = 0
        self.atk_id = 0
        self.dash = 0
        self.pound = False
        self.cast = 0
        self.chain = 0
        self.was_ground = False

    def hurt(self, g, dmg=1, from_x=None):
        if self.inv or self.dash or self.pound:
            return False
        self.hp -= dmg
        self.inv = S.INV
        self.hurt_t = 12
        if from_x is None:
            k = -self.face
        else:
            k = -1 if (self.x >> 4) + 5 < from_x else 1
        self.vx = k * 52
        self.vy = -90
        self.ground = False
        self.stand = None
        self.atk_t = 0
        self.pound = False
        self.chain = 0
        g.on_player_hurt()
        return True

    def atk_rect(self):
        """True while the melee hitbox is active; it is then in self.ar
        (x, y, w, h, dmg). One reused list: no allocation per frame."""
        t = self.atk_t
        if t < 3 or t > 7:
            return False
        px = self.x >> 4
        if self.combo == 2:
            rw = 26
            dmg = S.D_SWORD
        else:
            rw = 15
            dmg = S.D_PUNCH
        a = self.ar
        a[0] = px + self.w if self.face > 0 else px - rw
        a[1] = (self.y >> 4) + 3
        a[2] = rw
        a[3] = 15
        a[4] = dmg
        return True

    def update(self, inp, g):
        held = inp.held_mask
        pr = inp.pressed_mask
        lv = g.lv
        if self.inv:
            self.inv -= 1
        if self.hurt_t:
            self.hurt_t -= 1
        if self.drop:
            self.drop -= 1
        if self.cast:
            self.cast -= 1
        if self.atk_t:
            self.atk_t -= 1
        if self.combo_t:
            self.combo_t -= 1

        st = self.stand
        if st is not None:
            self.x += st.dx << 4
            self.y += st.dy << 4

        d = 0
        if held & DIR_R:
            d += 1
        if held & DIR_L:
            d -= 1

        if self.dash:
            self.dash -= 1
            self.vx = self.face * S.DASH_V
            self.vy = 0
            if self.dash == 0:
                self.vx = self.face * S.RUN
            if self.dash & 1:
                g.dust(self.x >> 4, (self.y >> 4) + 14, 1)
        elif self.hurt_t > 4:
            self.vy += S.GRAV
        else:
            if self.pound:
                self.vx = 0
                self.vy = S.POUND_V
            else:
                tx = d * S.RUN
                if self.atk_t > 4 and self.ground:
                    tx = d * (S.RUN >> 1)
                if d:
                    self.face = d
                    acc = S.ACC if self.ground else S.AIR_ACC
                else:
                    acc = S.FRIC if self.ground else 3
                if self.vx < tx:
                    self.vx = min(self.vx + acc, tx)
                elif self.vx > tx:
                    self.vx = max(self.vx - acc, tx)

                # ---- jump / double jump ----
                if pr & BTN_A:
                    self.jbuf = S.JBUF
                elif self.jbuf:
                    self.jbuf -= 1
                if self.ground:
                    self.coy = S.COYOTE
                    self.air_dj = False
                elif self.coy:
                    self.coy -= 1
                if self.jbuf:
                    if self.coy:
                        if self.ground and (held & DIR_D) and ph.on_oneway(self, lv):
                            self.drop = 10
                            self.y += 32
                        else:
                            self.vy = S.JUMP_V
                            self.jh = True
                            g.snd("sh_jump", 1)
                            g.dust(self.x >> 4, (self.y >> 4) + 20, 2)
                        self.coy = 0
                        self.jbuf = 0
                        self.ground = False
                        self.stand = None
                    elif self.dj and not self.air_dj and self.vy >= -S.APEX:
                        self.vy = S.DJUMP_V
                        self.jh = True
                        self.air_dj = True
                        self.jbuf = 0
                        g.snd("sh_jump2", 1)
                        g.dust(self.x >> 4, (self.y >> 4) + 20, 3)
                if self.jh and self.vy < S.JUMP_CUT and not (held & BTN_A):
                    self.vy = S.JUMP_CUT
                    self.jh = False
                self.vy += S.GRAV
                if self.vy > S.MAXFALL:
                    self.vy = S.MAXFALL

            # ---- attack / pound ----
            if pr & BTN_X:
                if not self.ground:
                    if not self.pound:
                        self.pound = True
                        g.snd("sh_pound", 1)
                elif self.atk_t <= 2:
                    if self.combo_t > 0:
                        self.combo = (self.combo + 1) % 3
                    else:
                        self.combo = 0
                    self.atk_t = 9
                    self.combo_t = 20
                    self.atk_id = g.new_aid()
                    g.snd(SWING_SFX[self.combo], 1)

            # ---- ability ----
            if pr & BTN_Y:
                k = self.meter.power()
                if k < 0:
                    g.snd("sh_denied", 1)
                else:
                    self.meter.clear()
                    self.cast = 8
                    if k == 0:
                        g.cast_spear(self)
                    elif k == 1:
                        self.dash = S.DASH_F
                        self.pound = False
                        self.atk_id = g.new_aid()
                        g.snd("sh_dash", 3)
                    else:
                        g.cast_void(self)

        vy0 = self.vy
        ph.move_body(self, lv, g.plats)

        if self.vy >= 0:
            self.jh = False
        if self.ground:
            if not self.was_ground:
                self.chain = 0
                if vy0 > 70:
                    g.dust(self.x >> 4, (self.y >> 4) + 20, 3)
            elif (self.vx > 40 or self.vx < -40) and (g.tick & 7) == 0:
                g.dust(self.x >> 4, (self.y >> 4) + 20, 1)
            if self.pound:
                self.pound = False
                g.pound_land(self)
        self.was_ground = self.ground

    def frame(self, tick):
        if self.hurt_t:
            return F_HURT
        if self.dash:
            return F_DASH
        if self.pound:
            return F_POUND
        if self.atk_t:
            return F_SLASH if self.combo == 2 else (F_PUNCH1 if self.combo == 0 else F_PUNCH2)
        if self.cast:
            return F_PUNCH1
        if not self.ground:
            return F_JUMP if self.vy < 0 else F_FALL
        if self.vx > 8 or self.vx < -8:
            return F_RUN0 + ((tick >> 1) & 3)
        return (tick >> 4) & 1
