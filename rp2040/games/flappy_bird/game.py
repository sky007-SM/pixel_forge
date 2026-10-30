# ============================================================
# Flappy Bird scene (320x240, 30 fps)
# A / stick click = flap, Y or B = pause menu (B = menu after game over)
#
# Memory: no big pixel buffers. The background is 4 base rows plus a
# compact span list, text is 1-bit, the game-over box is drawn from
# rectangles. The whole scene needs about 8 KB.
# ============================================================
import random
from hardware.display import P16
from hardware.input import BTN_A, BTN_B, BTN_Y, BTN_SW
from system.renderer import copy_row, fill_span, blit_t, blit_m
from system.scene_manager import Scene
from games.flappy_bird import settings as S
from games.flappy_bird import assets as A
from games.flappy_bird import save as sv
import uctypes

READY = 0
PLAY = 1
DEAD = 2
_BOB = (0, 1, 2, 3, 4, 5, 5, 4, 3, 2, 1, 0, -1, -2, -3, -3, -2, -1)


class FlappyBirdScene(Scene):
    PURGE = ("games.flappy_bird",)

    def __init__(self, ctx):
        self.ctx = ctx

    def enter(self, ctx):
        for _ in self.steps(ctx):
            pass

    def steps(self, ctx):
        self.ctx = ctx
        rows, self.bg_of, self.sidx, self.sdata = A.build_bg()
        self.row_addr = [uctypes.addressof(r) for r in rows]
        self.rows = rows
        yield
        self.bird = A.build_bird()
        self.bird_addr = uctypes.addressof(self.bird)
        self.strips = A.build_strips()
        self.strip_addr = [uctypes.addressof(s) for s in self.strips]
        self.ready_a, self.ready_b = A.ready_texts()
        self.ov = None
        self.best = sv.load_best(ctx.save)
        self.score_t = A.score_text(0)
        self.reset()
        yield

    def exit(self):
        ctx = self.ctx
        ctx.audio.stop_music()
        if self.state == PLAY and self.score > 0:
            sv.submit(ctx.save, self.score)           # leaving mid-run still counts
        ctx.led.off()
        ctx.save.flush()
        self.rows = self.row_addr = self.bg_of = self.sidx = self.sdata = None
        self.bird = self.strips = self.ov = self.score_t = None
        self.ready_a = self.ready_b = None

    def restart(self):
        """Pause menu -> RESTART."""
        self.reset()

    def reset(self):
        self.ctx.audio.stop_music()
        self.state = READY
        self.bird_y = float(S.START_Y)
        self.vy = 0.0
        self.pipe_x = 320.0
        self.gap = random.randint(S.GAP_MIN, S.GAP_MAX)
        self.score = 0
        self.tick = 0
        self.dead_f = 0
        self.new_best = False
        self.flush_pending = False
        self.ov = None
        self.score_t = A.score_text(0)

    # ------------------------------------------------------------
    def update(self, dt, inp):
        ctx = self.ctx
        self.tick += 1
        pm = inp.pressed_mask
        st = self.state
        if st == DEAD:
            if pm & BTN_B:
                ctx.home()
                return
        elif pm & (BTN_B | BTN_Y):
            ctx.pause()
            return
        flap = pm & (BTN_A | BTN_SW)

        if st == READY:
            self.bird_y = float(S.START_Y + _BOB[(self.tick >> 1) % 18])
            if flap:
                self.state = PLAY
                self.vy = S.FLAP_VELOCITY
                ctx.audio.sfx("flap")
            return

        if st == DEAD:
            self.dead_f += 1
            if self.flush_pending and self.dead_f == 2:
                self.flush_pending = False
                ctx.save.flush()               # static screen: flash write is invisible
            if flap and self.dead_f >= S.DEATH_LOCKOUT:
                self.reset()
            return

        # ---- PLAY ----
        if flap:
            self.vy = S.FLAP_VELOCITY
            ctx.audio.sfx("flap")
        self.vy += S.GRAVITY * dt
        self.bird_y += self.vy * dt
        self.pipe_x -= S.PIPE_SPEED * dt

        if self.pipe_x + S.PIPE_WIDTH < 0:
            self.pipe_x = 320.0
            self.gap = random.randint(S.GAP_MIN, S.GAP_MAX)
            self.score += 1
            self.score_t = A.score_text(self.score)
            ctx.led.flash(20, 120, 20, 160)
            ctx.audio.sfx("point")

        dead = False
        if self.bird_y - S.BIRD_RADIUS < 0:
            self.bird_y = float(S.BIRD_RADIUS)
            dead = True
        if self.bird_y + S.BIRD_RADIUS >= S.GROUND_Y:
            self.bird_y = float(S.GROUND_Y - S.BIRD_RADIUS)
            dead = True
        gt = self.gap - S.PIPE_GAP // 2
        gb = self.gap + S.PIPE_GAP // 2
        if S.BIRD_X + S.BIRD_RADIUS >= self.pipe_x:
            if S.BIRD_X - S.BIRD_RADIUS <= self.pipe_x + S.PIPE_WIDTH:
                if self.bird_y - S.BIRD_RADIUS < gt or self.bird_y + S.BIRD_RADIUS > gb:
                    dead = True
        if dead:
            self._die()

    def _die(self):
        ctx = self.ctx
        self.state = DEAD
        self.dead_f = 0
        self.new_best = sv.submit(ctx.save, self.score)
        self.best = sv.load_best(ctx.save)
        self.flush_pending = self.new_best
        self.ov = A.make_gameover(self.score, self.best, self.new_best)
        ctx.led.flash(230, 30, 10, 400)
        ctx.audio.sfx("dead")
        ctx.audio.music("newbest" if self.new_best else "gameover", False)

    # ------------------------------------------------------------
    def draw(self, r):
        kick = r.kick
        base = r.base
        cov = r.cover if r.cov_on else None
        cov_addr = r.cover_addr
        st = self.state
        gap = self.gap
        gt = gap - S.PIPE_GAP // 2
        gb = gap + S.PIPE_GAP // 2
        px = int(self.pipe_x)
        by = int(self.bird_y)
        pipe_on = st != READY and px < 320 and px + S.PIPE_WIDTH > 0
        x0p = px - 3
        b_lo = by - A.BCY
        b_hi = by + A.BCY
        ov = self.ov
        ready = st == READY
        blink = ready and ((self.tick >> 3) & 1) == 0
        gy = S.GROUND_Y

        sc = self.score_t
        sc_w = sc.w << 16
        ra = self.ready_a
        ra_w = ra.w << 16
        rb = self.ready_b
        c_navy = A.NAVY
        c_white = A.WHITE
        bgo = self.bg_of
        rowa = self.row_addr
        sidx = self.sidx
        sdata = self.sdata
        strips = self.strip_addr
        top_t = A.TOP_T
        bot_t = A.BOT_T
        bird_a = self.bird_addr
        bx = S.BIRD_X - A.BCX
        bgw = A.BW * 2
        sw = A.STRIP_W
        s0 = r.s0
        s1 = r.s1
        a0 = r.a0
        a1 = r.a1

        for y in range(240):
            if cov is not None and cov[y]:
                kick(base, cov_addr)
                continue
            tp = -1
            if pipe_on and y < gy:
                if y < gt:
                    d = gt - y
                    tp = top_t[d] if d < 13 else 1
                elif y > gb:
                    e = y - gb
                    tp = bot_t[e] if e < 13 else 1
            si = sidx[y]
            has_sp = sidx[y + 1] > si
            is_bird = b_lo <= y <= b_hi
            is_txt = 8 <= y < 22
            is_ov = ov is not None and 75 <= y < 161
            is_rdy = ready and (60 <= y < 75 or (blink and 150 <= y < 157))
            if tp >= 0 or is_bird or is_txt or is_ov or is_rdy or has_sp:
                if y & 1:
                    dst = s1
                    da = a1
                else:
                    dst = s0
                    da = a0
                copy_row(dst, rowa[bgo[y]])
                if has_sp:
                    e = sidx[y + 1]
                    while si < e:
                        fill_span(dst, sdata[si], sdata[si + 1], sdata[si + 2])
                        si += 3
                if tp >= 0:
                    blit_t(dst, x0p, strips[tp], sw)
                if is_bird:
                    blit_t(dst, bx, bird_a + (y - b_lo) * bgw, A.BW)
                if is_txt:
                    blit_m(dst, 8, sc.addr + (y - 8) * sc.rb, sc_w)
                if is_rdy:
                    if y < 150:
                        k = y - 60
                        x = (320 - ra.w) >> 1
                        if k >= 1:                                  # white shadow 1 px down/right
                            blit_m(dst, x + 1, ra.addr + (k - 1) * ra.rb, ra_w | c_white)
                        if k < 14:
                            blit_m(dst, x, ra.addr + k * ra.rb, ra_w | c_navy)
                    else:
                        k = y - 150
                        blit_m(dst, (320 - rb.w) >> 1, rb.addr + k * rb.rb, (rb.w << 16) | c_navy)
                if is_ov:
                    ov.draw_row(dst, y)
                kick(base, da)
            else:
                kick(base, rowa[bgo[y]])
