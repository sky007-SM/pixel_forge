# ============================================================
# Main menu: game list on the left, big preview on the right.
# Static rows go straight to the DMA; only rows that hold the
# list / preview / text are composed.
#
# Memory: text is stored as 1-bit masks and only ONE preview buffer
# exists (it is redrawn when the selection changes), so the whole
# menu needs about 20 KB.
# ============================================================
import os
import config
from hardware.display import P16
from hardware.input import BTN_A, BTN_B, BTN_SW
from system.renderer import make_row, fill_span, copy_row, blit_m, blit_o
from system.scene_manager import Scene
from system.dialog import make_confirm
from assets.fonts import Text
from assets.logo import make_wordmark, EMBER_ROWS, SHADOW
from assets import thumbnails
import uctypes

# (title, module, class, save key, tagline)
GAMES = (
    ("FLAPPY BIRD", "games.flappy_bird.game", "FlappyBirdScene", "flappy_bird", "TAP TO FLY"),
    ("TETRIS", "games.tetris.game", "TetrisScene", "tetris", "STACK AND CLEAR"),
    ("FORGERACER", "games.racer.game", "RacerScene", "racer", "BEAT THE CLOCK"),
    ("SHARDS OF AETHERIA", "games.shards.game", "ShardsScene", "platformer", "RUN AND JUMP"),
)

ENT_Y0 = 44
ENT_STEP = 40
ENT_H = 32
LIST_X = 8
LIST_R = 168
FR_X = 188
FR_R = 300
TH_X = 192
HDR_Y = 10
FOOT_Y = 226


def _exists(mod):
    path = mod.replace(".", "/")
    for ext in (".py", ".mpy"):
        try:
            os.stat(path + ext)
            return True
        except OSError:
            pass
    return False


def _loader(ctx, mod, cls):
    def make():
        m = __import__(mod, None, None, (cls,))
        return getattr(m, cls)(ctx)
    return make


def _pulse_table():
    t = []
    e0 = config.C_EMBER_DARK
    e1 = config.C_EMBER_HOT
    for i in range(16):
        k = i if i < 8 else 15 - i            # 0..7..0
        r0, g0, b0 = (e0 >> 11) & 31, (e0 >> 5) & 63, e0 & 31
        r1, g1, b1 = (e1 >> 11) & 31, (e1 >> 5) & 63, e1 & 31
        r = r0 + (r1 - r0) * k // 7
        g = g0 + (g1 - g0) * k // 7
        b = b0 + (b1 - b0) * k // 7
        t.append(P16((r << 11) | (g << 5) | b))
    return tuple(t)


class MenuScene(Scene):
    def __init__(self, ctx):
        self.ctx = ctx

    def enter(self, ctx):
        for _ in self.steps(ctx):
            pass

    def steps(self, ctx):
        """Built in small chunks so the loading screen can keep animating."""
        self.ctx = ctx
        c = config
        n = len(GAMES)
        self.sel = ctx.save.get("system", "last", 0) % n
        self.bar_y = float(ENT_Y0 + ENT_STEP * self.sel)
        self.tick = 0
        self.toast = 0
        self.confirm = False
        self.music_on = False
        self.dialog = make_confirm("SHUT DOWN?", "PRESS A TO SHUT DOWN", "PRESS B TO CANCEL")

        self.bg = (make_row(c.C_BG0), make_row(c.C_BG1))
        self.bg_addr = (uctypes.addressof(self.bg[0]), uctypes.addressof(self.bg[1]))
        # ember rule under the header: dark -> bright -> dark
        self.line = make_row(c.C_EMBER_DARK)
        self.line_addr = uctypes.addressof(self.line)
        fill_span(self.line, 40, 280, P16(c.C_EMBER))
        fill_span(self.line, 100, 220, P16(c.C_EMBER_HOT))
        yield

        self.wm = make_wordmark()
        self.wm_rows = tuple(P16(x) for x in EMBER_ROWS)
        self.wm_shadow = P16(SHADOW)
        self.ver = Text("V1.0", 1)
        self.hint = Text("UP/DOWN SELECT   A PLAY   B POWER", 1)
        self.soon = Text("NOT INSTALLED YET", 1)
        self.names = [Text(g[0], 2) for g in GAMES]
        self.descs = [Text(g[4], 1) for g in GAMES]
        self.bests = [Text("BEST " + str(ctx.save.get(g[3], "best", 0))[:5], 2) for g in GAMES]
        self.counts = [Text(str(i + 1) + "/" + str(n), 1) for i in range(n)]
        yield

        self.thumb = thumbnails.new()              # one shared preview buffer
        self.thumb_idx = self.sel
        thumbnails.build_into(self.thumb, self.sel)
        self.pulse = _pulse_table()
        self.bar_col = P16(c.C_PANEL_HI)
        self.panel = P16(c.C_PANEL)
        self.dimc = P16(c.C_TEXT_DIM)
        self.c_text = P16(c.C_TEXT)
        self.c_hot = P16(c.C_EMBER_HOT)
        self.c_ember = P16(c.C_EMBER)
        yield

    def exit(self):
        self.ctx.audio.stop_music()
        self.ctx.save.set("system", "last", self.sel)
        self.ctx.save.flush()
        self.names = self.descs = self.bests = self.counts = None
        self.thumb = self.dialog = self.wm = None

    # ------------------------------------------------------------
    def update(self, dt, inp):
        ctx = self.ctx
        au = ctx.audio
        self.tick += 1
        if not self.music_on:
            self.music_on = True
            au.music("menu", True)                 # idle loop
        pm = inp.pressed_mask

        if self.confirm:                           # shutdown question is open
            if pm & BTN_A:
                self.confirm = False
                ctx.shutdown()
            elif pm & BTN_B:
                self.confirm = False
                au.sfx("back")
            return

        n = len(GAMES)
        dy = inp.nav_y
        if dy:
            self.sel = (self.sel + dy) % n
            ctx.led.flash(40, 18, 0, 140)
            au.sfx("move")
        if self.thumb_idx != self.sel:             # redraw the shared preview (about 5 ms)
            self.thumb_idx = self.sel
            thumbnails.build_into(self.thumb, self.sel)
        target = float(ENT_Y0 + ENT_STEP * self.sel)
        d = target - self.bar_y
        if -0.6 < d < 0.6:
            self.bar_y = target
        else:
            self.bar_y += d * 0.5
        if self.toast:
            self.toast -= 1
        if pm & (BTN_A | BTN_SW):
            g = GAMES[self.sel]
            if _exists(g[1]):
                ctx.led.flash(255, 120, 20, 300)
                au.sfx("select")
                ctx.sm.goto(_loader(ctx, g[1], g[2]), "fade", ("LOADING", g[0]))
            else:
                self.toast = 60
                ctx.led.flash(120, 10, 0, 200)
                au.sfx("error")
        elif pm & BTN_B:
            self.confirm = True
            au.sfx("pause")

    # ------------------------------------------------------------
    def draw(self, r):
        confirm = self.confirm
        if confirm:
            r.set_fx(1, self.dialog)              # dim the menu, question on top
        kick = r.kick
        base = r.base
        cov = r.cover if r.cov_on else None
        cov_addr = r.cover_addr
        bga = self.bg_addr
        s0 = r.s0
        s1 = r.s1
        a0 = r.a0
        a1 = r.a1
        line_addr = self.line_addr
        sel = self.sel
        by = int(self.bar_y)
        pul = self.pulse[(self.tick >> 1) & 15]
        bar_col = self.bar_col
        panel = self.panel
        dimc = self.dimc
        c_text = self.c_text
        names = self.names
        th = self.thumb
        thr = th.ra
        best = self.bests[sel]
        desc = self.descs[sel]
        wm = self.wm
        wm_rows = self.wm_rows
        wm_sh = self.wm_shadow
        ver = self.ver
        foot = self.soon if self.toast else self.hint
        cnt = self.counts[sel]
        hdr_end = HDR_Y + wm.h + 1
        ver_x = 320 - 12 - ver.w
        cnt_x = 320 - 8 - cnt.w

        for y in range(240):
            if cov is not None and cov[y]:
                kick(base, cov_addr)
                continue
            if y == 30 or y == 31:
                kick(base, line_addr)
                continue
            hdr = HDR_Y <= y < hdr_end
            body = 44 <= y < 196
            fut = FOOT_Y <= y < FOOT_Y + 7
            if not (hdr or body or fut):
                kick(base, bga[y & 1])
                continue
            if y & 1:
                dst = s1
                da = a1
            else:
                dst = s0
                da = a0
            copy_row(dst, bga[y & 1])

            if hdr:
                k = y - HDR_Y
                if k >= 1:                                    # drop shadow (1 px down/right)
                    blit_m(dst, 13, wm.addr + (k - 1) * wm.rb, (wm.w << 16) | wm_sh)
                if k < wm.h:
                    blit_m(dst, 12, wm.addr + k * wm.rb, (wm.w << 16) | wm_rows[k >> 1])
                if 13 <= y < 20:
                    blit_m(dst, ver_x, ver.addr + (y - 13) * ver.rb, (ver.w << 16) | dimc)
            elif fut:
                k = y - FOOT_Y
                blit_m(dst, 8, foot.addr + k * foot.rb, (foot.w << 16) | dimc)
                blit_m(dst, cnt_x, cnt.addr + k * cnt.rb, (cnt.w << 16) | dimc)
            else:
                k = y - 44
                if by <= y < by + ENT_H:
                    fill_span(dst, LIST_X, LIST_R, bar_col)
                    fill_span(dst, LIST_X, LIST_X + 4, pul)
                i = k // ENT_STEP
                m = k - i * ENT_STEP
                if m < ENT_H:
                    if 9 <= m < 23:
                        e = names[i]
                        blit_m(dst, 30, e.addr + (m - 9) * e.rb,
                               (e.w << 16) | (c_text if i == sel else dimc))
                    if 13 <= m < 19:
                        fill_span(dst, 16, 22, pul if i == sel else dimc)
                if y < 130:
                    if y < 46 or y >= 128:
                        fill_span(dst, FR_X, FR_R, pul)
                    else:
                        fill_span(dst, FR_X, FR_X + 2, pul)
                        fill_span(dst, FR_R - 2, FR_R, pul)
                        if y < 48 or y >= 126:
                            fill_span(dst, FR_X + 2, FR_R - 2, panel)
                        else:
                            blit_o(dst, TH_X, thr[y - 48], 104)
                elif 138 <= y < 152:
                    blit_m(dst, FR_X, best.addr + (y - 138) * best.rb, (best.w << 16) | self.c_hot)
                elif 160 <= y < 167:
                    blit_m(dst, FR_X, desc.addr + (y - 160) * desc.rb, (desc.w << 16) | dimc)
            kick(base, da)
        if confirm:
            r.set_fx(0)
