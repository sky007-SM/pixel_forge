# ============================================================
# Gameplay half of the scene (a mixin): per-frame play logic, collisions,
# abilities, pick-ups and the ? blocks. Split from game.py so no single file
# is huge (smaller peak RAM when each module is compiled / imported).
# ============================================================
from hardware.input import BTN_B
from games.shards import settings as S
from games.shards import physics as ph
from games.shards import enemies as E

M_TITLE = 0
M_LOAD = 1
M_INTRO = 2
M_PLAY = 3
M_CLEAR = 4
M_DEAD = 5
M_STORY = 6
M_END = 7

READY_SFX = ("sh_ready0", "sh_ready1", "sh_ready2")


def ov(ax, ay, aw, ah, bx, by, bw, bh):
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


class PlayMixin:
    # ------------------------------------------------------------ abilities
    def cast_spear(self, p):
        """Rootspike: a piercing spear. Kills every normal enemy along its line,
        stopping after SPEAR_LIFE frames (192 px) or at a wall / boss."""
        px = p.x >> 4
        x = px + p.w if p.face > 0 else px - 28
        self.add_proj(E.PK_SPEAR, x, (p.y >> 4) + 8, p.face * S.SPEAR_SPEED, 0, 28, 7, S.SPEAR_LIFE)
        self.snd("sh_spike", 3)
        self.ctx.led.flash(40, 200, 40, 200)

    def cast_void(self, p):
        px = p.x >> 4
        x = px + p.w if p.face > 0 else px - 12
        self.add_proj(E.PK_VOID, x, (p.y >> 4) + 4, p.face * 5, -6, 12, 12, 40, 1)
        self.snd("sh_void", 3)

    def _explode(self, cx, cy):
        """Void Collapse: the strongest power. Wipes every enemy, shot, rock, rift and
        blade inside a large blast; badly hurts bosses. Platforms are untouched."""
        r2 = S.VOID_R * S.VOID_R
        for e in self.enemies:
            if e.alive:
                dx = e.x + (e.w >> 1) - cx
                dy = e.y + (e.h >> 1) - cy
                if dx * dx + dy * dy < r2:
                    e.kill(self)
        for q in self.projs:
            if q.kind >= E.PK_FIRE:
                dx = q.x - cx
                dy = q.y - cy
                if dx * dx + dy * dy < r2:
                    q.alive = False
        for r in self.rifts:
            dx = r.x - cx
            dy = r.y - cy
            if dx * dx + dy * dy < r2:
                r.alive = False
        for b in self.blades:
            dx = b.x - cx
            dy = b.y - cy
            if dx * dx + dy * dy < r2:
                b.dis = 200
        bs = self.boss
        if bs is not None:
            dx = bs.x + (bs.w >> 1) - cx
            dy = bs.y + (bs.h >> 1) - cy
            if dx * dx + dy * dy < r2 + 1600:
                bs.hurt(S.D_VOID, self, self.new_aid())
        self.void_fx = [cx, cy, 0]
        self.shake = 9
        self.snd("sh_boom", 4)
        self.ctx.led.flash(150, 40, 220, 300)

    def pound_land(self, p):
        px = p.x >> 4
        x = px - 26
        w = p.w + 52
        y = (p.y >> 4) + p.h - 12
        aid = self.new_aid()
        for e in self.enemies:
            if e.alive and ov(x, y, w, 16, e.x, e.y, e.w, e.h):
                e.hit(S.D_POUND, self)
        bs = self.boss
        if bs is not None and ov(x, y, w, 16, bs.x, bs.y, bs.w, bs.h):
            bs.hurt(S.D_POUND, self, aid)
        self.shake = 5
        self.dust(px - 8, (p.y >> 4) + 20, 4)
        self.snd("sh_land", 2)

    # ------------------------------------------------------------ gameplay
    def _bump(self, tx, ty):
        lv = self.lv
        t = ph.tile(lv, tx, ty)
        if t == 8:
            lv.put(tx, ty, 9)
            p = self.player
            h = (tx * 7 + ty * 3) % 10
            if h == 0:
                self.ex.append([1, tx * 16 + 3, (ty - 1) * 16 + 4])
                self.snd("sh_qblock", 2)
            elif h < 3:
                self.ex.append([2, tx * 16 + 3, (ty - 1) * 16 + 3])
                self.snd("sh_qblock", 2)
            else:
                p.coins += 1
                p.score += 100
                self.popup(tx * 16, ty * 16 - 12, 100)
                self.snd("sh_coin", 2)
        elif t == 3 or t == 9:
            self.snd("sh_bump", 1)

    def _pickup(self, k):
        p = self.player
        if k == 0:
            p.coins += 1
            p.score += 50
            self.snd("sh_coin", 1)
            if p.coins % 100 == 0 and p.hp < S.MAX_HP:
                p.hp += 1
                if p.hp > p.maxhp:
                    p.maxhp = p.hp
                self.snd("sh_heart", 2)
        elif k == 1:
            if p.hp < S.MAX_HP:
                p.hp += 1
                if p.hp > p.maxhp:
                    p.maxhp = p.hp
            p.score += 200
            self.snd("sh_heart", 2)
        else:
            p.meter.add(S.ORB)
            p.score += 200
            self.snd("sh_orb", 2)

    def _play(self, inp):
        p = self.player
        lv = self.lv
        if inp.pressed_mask & BTN_B:
            self.ctx.pause()
            return
        self.t += 1
        t = self.t
        for pl in self.plats:
            pl.update()
            if pl.kind == 2 and pl.st == 1 and pl.t == 0:
                self.snd("sh_collapse", 2)
        if p.stand is not None:
            p.stand.touch = True
        p.update(inp, self)
        if self.mode != M_PLAY:
            return
        yield
        if p.bumped:
            self._bump(p.bcx, p.bcy)
        mt = p.meter
        mt.tick()
        pw = mt.power()
        if pw > self.last_pw:
            self.snd(READY_SFX[pw], 2)
        self.last_pw = pw
        px = p.x >> 4
        py = p.y >> 4

        hz = ph.touch_hazard(p, lv)
        if hz == 2 or p.y > 290 * 16:
            self._fall()
            return
        if hz == 1:
            p.hurt(self, 1)
            if self.mode != M_PLAY:
                return

        cps = lv.cps
        i = self.cp + 1
        if i < len(cps) and px >= cps[i][0] * 16:
            self.cp = i
            self.snd("sh_cp", 2)
            self.ctx.led.flash(40, 200, 80, 200)

        if lv.escape and px >= lv.escape and not self.chase:
            self.chase = lv.escape - 200
            self.chase_col = self.chase >> 4
            self.shake = 4
            self.snd("sh_collapse", 3)
        if self.chase:
            self.chase += 2
            while self.chase_col < (self.chase >> 4):
                lv.rect(self.chase_col, 0, self.chase_col, 14, 5)
                self.chase_col += 1
            if t & 7 == 0:
                self.shake = 3
                if t & 15 == 0:
                    self.snd("sh_rumble", 1)
            if px < self.chase:
                self._fall()
                return

        if lv.arena and self.boss is None and not self.boss_done and px >= lv.arena + 40:
            bk = lv.area
            self.boss = self.bmod.Boss(bk, lv.arena, 12 * 16)
            lv.rect(lv.arena >> 4, 0, lv.arena >> 4, 11, 3)
            self.ctx.audio.music("sh_boss2" if bk == 2 else "sh_boss")

        cam = self.cam
        atk = p.ar if p.atk_rect() else None
        dashing = p.dash

        for e in self.enemies:
            if not e.alive:
                continue
            if e.x < cam - 96 or e.x > cam + 416:
                continue
            e.update(self)
            yield
            if atk is not None and e.aid != p.atk_id and ov(atk[0], atk[1], atk[2], atk[3], e.x, e.y, e.w, e.h):
                e.aid = p.atk_id
                e.hit(atk[4], self)
                if not e.alive:
                    continue
            if dashing and ov(px - 6, py - 2, p.w + 12, p.h + 4, e.x, e.y, e.w, e.h):
                e.kill(self)                         # Fire Dash one-shots every enemy
                continue
            if e.harm and e.vis and ov(px, py, p.w, p.h, e.x, e.y, e.w, e.h):
                if p.pound or dashing:
                    pass
                elif p.vy > 0 and e.stomp and py + p.h - e.y <= 12:
                    self.mult = 1 << min(p.chain, 3)
                    p.chain += 1
                    e.hit(S.D_STOMP, self)
                    self.mult = 1
                    p.vy = S.STOMP_V
                    p.jh = False
                    p.air_dj = False
                    p.ground = False
                    self.snd("sh_stomp" if p.chain < 2 else "sh_chain", 3)
                else:
                    p.hurt(self, 1, e.x + (e.w >> 1))
                    if self.mode != M_PLAY:
                        return

        yield
        for b in self.blades:
            b.update()
            if not b.dis and ov(px, py, p.w, p.h, b.x, b.y, b.w, b.h):
                p.hurt(self, 1, b.x + 8)
        j = 0
        rf = self.rifts
        while j < len(rf):
            r = rf[j]
            r.update()
            if r.alive and r.active() and ov(px, py, p.w, p.h, r.x, r.y, r.w, r.h):
                p.hurt(self, 1, r.x + 14)
            if r.alive:
                j += 1
            else:
                rf.pop(j)
        for rx, per, phs in lv.rocks:
            if abs(rx - px) < 220 and (t + phs) % per == per - 1:
                self.add_proj(E.PK_ROCK, rx, -16, 0, 2, 14, 14, 120, 1)
        if self.mode != M_PLAY:
            return

        yield
        bs = self.boss
        if bs is not None:
            bs.update(self)
            bs = self.boss
        if bs is not None:
            if bs.vis and bs.st != 10:
                if atk is not None and ov(atk[0], atk[1], atk[2], atk[3], bs.x, bs.y, bs.w, bs.h):
                    bs.hurt(atk[4], self, p.atk_id)
                if dashing and ov(px - 6, py - 2, p.w + 12, p.h + 4, bs.x, bs.y, bs.w, bs.h):
                    bs.hurt(S.D_DASH, self, p.atk_id)
                if p.vy > 0 and bs.vul and ov(px, py, p.w, p.h, bs.x, bs.y, bs.w, 14) and py + p.h - bs.y <= 18:
                    if bs.hurt(S.D_STOMP, self, self.new_aid()):
                        p.vy = S.STOMP_V
                        p.jh = False
                        p.air_dj = False
                        p.ground = False
            for k in range(bs.nr):
                r = bs.rects[k]
                if ov(px, py, p.w, p.h, r[0], r[1], r[2], r[3]):
                    p.hurt(self, 1, r[0] + (r[2] >> 1))
            if self.mode != M_PLAY:
                return

        pr = self.projs
        j = 0
        while j < len(pr):
            q = pr[j]
            q.update()
            if q.alive and not self._proj_hit(q, p, px, py):
                q.alive = False
            yield
            if q.alive:
                j += 1
            else:
                pr.pop(j)
        if self.mode != M_PLAY:
            return

        yield
        # ---- pick-ups: sorted arrays walked through a sliding window ----
        ix = self.ix
        iy = self.iy
        ik = self.ik
        n_i = len(ix)
        lo = self.ilo
        while lo > 0 and ix[lo - 1] > px - 30:
            lo -= 1
        while lo < n_i and ix[lo] < px - 30:
            lo += 1
        self.ilo = lo
        while lo < n_i and ix[lo] < px + 30:
            k = ik[lo]
            if k != 255:
                sz = 8 if k == 0 else 10
                if ov(px, py, p.w, p.h, ix[lo], iy[lo], sz, sz + 1):
                    ik[lo] = 255
                    self._pickup(k)
            lo += 1
        ex = self.ex
        j = 0
        while j < len(ex):
            it = ex[j]
            if ov(px, py, p.w, p.h, it[1], it[2], 10, 10):
                self._pickup(it[0])
                ex.pop(j)
            else:
                j += 1

        # ---- goal: flagpole or the boss shard ----
        if self.goal_on and lv.goal:
            if lv.theme_boss():
                if ov(px, py, p.w, p.h, lv.goal - 4, 150, 24, 42):
                    self._level_done()
                    return
            elif ov(px, py, p.w, p.h, lv.goal, 64, 6, 130):
                self._flag_hit(p, py)
                return

        # ---- camera ----
        d = self._cam_target() - self.cam
        if -4 < d < 4:
            self.cam += d
        else:
            d >>= 2
            if d > 12:
                d = 12
            elif d < -12:
                d = -12
            self.cam += d
        # wisp companion
        self.wx += ((px + 5 - p.face * 14) - self.wx) >> 2
        self.wy += ((py - 8 + (E.SIN[(self.tick >> 2) & 31] >> 1)) - self.wy) >> 2
        # particles / popups / void flash
        pt = self.pt
        j = 0
        while j < len(pt):
            q = pt[j]
            q[0] += q[2] >> 2
            q[1] += q[3] >> 2
            q[3] += 1
            q[4] -= 1
            if q[4] <= 0:
                pt.pop(j)
            else:
                j += 1
        j = 0
        pp = self.pops
        while j < len(pp):
            q = pp[j]
            q[1] -= 1
            q[3] -= 1
            if q[3] <= 0:
                pp.pop(j)
            else:
                j += 1
        vf = self.void_fx
        if vf is not None:
            vf[2] += 1
            if vf[2] > 14:
                self.void_fx = None

    def _proj_hit(self, q, p, px, py):
        k = q.kind
        lv = self.lv
        cx = q.x + (q.w >> 1)
        cy = q.y + (q.h >> 1)
        if k == E.PK_SPEAR:
            if ph.solid_px(lv, cx + (14 if q.vx > 0 else -14), cy):
                return False
            for e in self.enemies:
                if e.alive and ov(q.x, q.y, q.w, q.h, e.x, e.y, e.w, e.h):
                    e.kill(self)                     # pierces: keeps flying through the line
                    self.snd("sh_impale", 3)
            bs = self.boss
            if bs is not None and bs.vis and ov(q.x, q.y, q.w, q.h, bs.x, bs.y, bs.w, bs.h):
                bs.hurt(S.D_SPEAR, self, self.new_aid())
                return False
            return True
        if k == E.PK_VOID:
            hit = q.t >= 36 or ph.solid_px(lv, cx, cy + 6)
            if not hit:
                for e in self.enemies:
                    if e.alive and ov(q.x, q.y, q.w, q.h, e.x, e.y, e.w, e.h):
                        hit = True
                        break
            bs = self.boss
            if not hit and bs is not None and ov(q.x, q.y, q.w, q.h, bs.x, bs.y, bs.w, bs.h):
                hit = True
            if hit:
                self._explode(cx, cy)
                return False
            return True
        if k != E.PK_WAVE and k != E.PK_ROCK and ph.solid_px(lv, cx, cy):
            return False
        if k == E.PK_ROCK and (q.y > 0 and ph.solid_px(lv, cx, q.y + q.h)):
            self.snd("sh_rock", 1)
            return False
        if k == E.PK_WAVE and ph.solid_px(lv, cx + (9 if q.vx > 0 else -9), cy):
            return False
        if q.y > 250:
            return False
        if ov(q.x, q.y, q.w, q.h, px, py, p.w, p.h):
            if p.hurt(self, 1, cx):
                return k == E.PK_WAVE
            return True
        return True

