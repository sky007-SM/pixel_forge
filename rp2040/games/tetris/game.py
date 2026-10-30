# ============================================================
# Tetris scene (320x240, 30 fps), three levels, score-attack
#
# Stick left/right = move   stick down = soft drop
# A / stick up = rotate     X = rotate back    B = hard drop    Y = pause menu
#
# Memory: about 6 KB. The playfield is drawn straight from the board array
# (pre-drawn empty lines + one 11-pixel blit per filled cell), text is 1-bit.
# ============================================================
import random
import config
from hardware.display import P16
from hardware.input import BTN_A, BTN_B, BTN_X, BTN_Y, BTN_SW, DIR_L, DIR_R, DIR_U, DIR_D
from system.renderer import make_row, copy_row, fill_span, blit_o, blit_m, blit_t
from system.scene_manager import Scene
from assets.fonts import Text, Digits
from assets.logo import EMBER_ROWS
from games.tetris import settings as S
from games.tetris.pieces import SHAPES, SPAWN_X, SPAWN_Y, KICKS, preview_cells
from games.tetris.board import Board
from games.tetris import assets as A
from games.tetris import save as sv
import uctypes

SEL = 0
PLAY = 1
CLEAR = 2
DEAD = 4

COLS = S.COLS
ROWS = S.ROWS
CELL = S.CELL
GX0 = S.GRID_X + S.FRAME           # first cell column (pixels)
GY0 = S.GRID_Y + S.FRAME           # first cell row (pixels)
_START = BTN_A | BTN_SW


class TetrisScene(Scene):
    PURGE = ("games.tetris",)

    def __init__(self, ctx):
        self.ctx = ctx

    # ------------------------------------------------------------
    def enter(self, ctx):
        for _ in self.steps(ctx):
            pass

    def steps(self, ctx):
        self.ctx = ctx
        c = config
        self.state = SEL
        self.tick = 0
        self.lv = ctx.save.get("tetris", "last", 0) % len(S.LEVELS)
        self.board = Board()
        self.blocks = A.make_blocks()
        self.blk = [0] + [b.addr for b in self.blocks[1:]]      # 11x11 = 242 B, one band
        self.ghost = A.make_ghost()
        self.strips = A.make_strips()
        self.strip_a = [uctypes.addressof(s) for s in self.strips]
        yield
        self.plain, self.panel, self.edge = A.make_backgrounds()
        self.plain_a = uctypes.addressof(self.plain)
        self.panel_a = uctypes.addressof(self.panel)
        self.edge_a = uctypes.addressof(self.edge)
        self.pmask = [0] * ROWS
        self.gmask = [0] * ROWS
        self.nx = ()                                           # next-piece cells: (x, y, colour)

        # ---- side panel: labels (Text) and number fields (Digits), drawn row by row ----
        g2 = Digits.make_glyphs(2)                 # one glyph set shared by all scale-2 fields
        g3 = Digits.make_glyphs(3)
        self.f_score = Digits(2, 6, "", g2)
        self.f_best = Digits(2, 6, "", g2)
        self.f_lines = Digits(2, 4, "", g2)
        self.f_level = Digits(2, 1, "", g2)
        self.f_streak = Digits(3, 3, "X", g3)
        self.f_max = Digits(2, 3, "", g2)
        self.f_pieces = Digits(2, 4, "", g2)
        hot = P16(c.C_EMBER_HOT)
        txt = P16(c.C_TEXT)
        dim = P16(c.C_TEXT_DIM)
        # (x, y, object, colour, is_digits)
        defs = [
            (14, 14, Text("SCORE", 1), dim, 0), (14, 24, self.f_score, hot, 1),
            (14, 48, Text("BEST", 1), dim, 0), (14, 58, self.f_best, txt, 1),
            (14, 82, Text("LINES", 1), dim, 0), (14, 92, self.f_lines, txt, 1),
            (14, 116, Text("LEVEL", 1), dim, 0), (14, 126, self.f_level, txt, 1),
            (14, 170, Text("A ROTATE", 1), dim, 0), (14, 182, Text("B DROP", 1), dim, 0),
            (14, 194, Text("X ROTATE", 1), dim, 0), (14, 206, Text("Y PAUSE", 1), dim, 0),
            (230, 14, Text("NEXT", 1), dim, 0),
            (230, 100, Text("STREAK", 1), dim, 0), (230, 110, self.f_streak, hot, 1),
            (230, 158, Text("MAX STREAK", 1), dim, 0), (230, 168, self.f_max, txt, 1),
            (230, 192, Text("PIECES", 1), dim, 0), (230, 202, self.f_pieces, txt, 1),
        ]
        self.sx = [d[0] for d in defs]
        self.sy = [d[1] for d in defs]
        self.so = [d[2] for d in defs]
        self.sc = [d[3] for d in defs]
        self.sk = [d[4] for d in defs]
        ri = [[] for _ in range(240)]
        for i in range(len(defs)):
            for yy in range(defs[i][1], defs[i][1] + defs[i][2].h):
                ri[yy].append(i)
        self.rowi = [tuple(x) if x else () for x in ri]
        self.c_ed = P16(c.C_EMBER_DARK)

        # streak meter colours (dark -> hot)
        self.meter_off = P16(c.C_BG0)
        self.meter_on = []
        e0 = c.C_EMBER_DARK
        e1 = c.C_EMBER_HOT
        for i in range(6):
            r0, g0, b0 = (e0 >> 11) & 31, (e0 >> 5) & 63, e0 & 31
            r1, g1, b1 = (e1 >> 11) & 31, (e1 >> 5) & 63, e1 & 31
            k = i + 1
            self.meter_on.append(P16(((r0 + (r1 - r0) * k // 6) << 11) |
                                     ((g0 + (g1 - g0) * k // 6) << 5) |
                                     (b0 + (b1 - b0) * k // 6)))
        yield

        # ---- level select art ----
        self.title = Text("TETRIS", 4)
        self.title_rows = [P16(x) for x in EMBER_ROWS]
        self.title_sh = P16(config.rgb(46, 18, 12))
        self.sub = Text("SELECT LEVEL", 1)
        self.hint = Text("UP/DOWN SELECT   A START   B BACK", 1)
        self.opt_name = [Text(L[0], 2) for L in S.LEVELS]
        self.opt_desc = [Text(L[4], 1) for L in S.LEVELS]
        self.opt_best = None
        self._build_bests()
        self.pulse = P16(c.C_EMBER)
        self.bar_col = P16(c.C_PANEL_HI)
        self.c_text = txt
        self.c_dim = dim
        self.c_hot = hot
        self.bgrow = make_row(c.C_BG0)
        self.bgrow_a = uctypes.addressof(self.bgrow)

        self.ovl = None
        self.flush_pending = False
        self.clear_rows = ()
        self.clear_mask = 0
        self.clear_t = 0
        self.bag = []
        self.dirx = 0
        self.das = 0
        self.soft = 0
        self.dead_f = 0
        self.score = 0
        yield

    def restart(self):
        """Pause menu -> RESTART: same level, fresh board."""
        if self.state != SEL:
            self._start(self.lv)

    def exit(self):
        if self.state in (PLAY, CLEAR) and self.score > 0:
            sv.submit(self.ctx.save, self.lv, self.score)     # leaving mid-run still counts
        self.ctx.save.set("tetris", "last", self.lv)
        self.ctx.save.flush()
        self.ctx.led.off()
        self.board = self.blocks = self.ghost = self.strips = None
        self.so = self.rowi = self.ovl = None

    def _build_bests(self):
        s_ = self.ctx.save
        self.opt_best = [Text("BEST " + str(sv.load_best(s_, i)), 1) for i in range(len(S.LEVELS))]

    # ------------------------------------------------------------
    # game flow
    # ------------------------------------------------------------
    def _bag_next(self):
        if not self.bag:
            b = [0, 1, 2, 3, 4, 5, 6]
            for i in range(6, 0, -1):
                j = random.randint(0, i)
                b[i], b[j] = b[j], b[i]
            self.bag = b
        return self.bag.pop()

    def _start(self, lv):
        self.lv = lv
        L = S.LEVELS[lv]
        self.gravity = L[1]
        self.mult = L[3]
        self.board.clear()
        if L[2]:
            self.board.fill_random(random.randint(S.GARBAGE_MIN, S.GARBAGE_MAX))
        self.score = 0
        self.lines = 0
        self.streak = 0
        self.maxstreak = 0
        self.pieces = 0
        self.best = sv.load_best(self.ctx.save, lv)
        self.bag = []
        self.next_p = self._bag_next()
        self.ovl = None
        self.dirx = 0
        self.das = 0
        self.f_level.set(lv + 1)
        self.clear_mask = 0
        self.clear_rows = ()
        self.state = PLAY
        self._spawn()
        self._sync()

    def _spawn(self):
        p = self.next_p
        self.cur = p
        self.rot = 0
        self.px = SPAWN_X[p]
        self.py = SPAWN_Y[p]
        self.next_p = self._bag_next()
        cells, w, h = preview_cells(self.next_p)
        ox = 230 + (76 - w * CELL) // 2
        oy = 24 + (56 - h * CELL) // 2
        self.nx = tuple((ox + x * CELL, oy + y * CELL, self.next_p + 1) for (x, y) in cells)
        self.fall = 0
        self.lock_t = 0
        self.resets = 0
        self.soft = 0
        self.pieces += 1
        if not self.board.fits(SHAPES[p][0], self.px, self.py):
            self._die()

    def _sync(self):
        self.f_score.set(self.score)
        self.f_best.set(self.best if self.best > self.score else self.score)
        self.f_lines.set(self.lines)
        self.f_streak.set(self.streak)
        self.f_max.set(self.maxstreak)
        self.f_pieces.set(self.pieces)

    def _add(self, pts):
        s = self.score + pts
        self.score = s if s < S.SCORE_CAP else S.SCORE_CAP

    def _nudge(self):
        # a successful move/rotate while resting gives the player a little more time
        if self.lock_t and self.resets < S.LOCK_RESETS:
            self.lock_t = 0
            self.resets += 1

    def _move(self, dx):
        if self.board.fits(SHAPES[self.cur][self.rot], self.px + dx, self.py):
            self.px += dx
            self._nudge()

    def _rotate(self, d):
        nr = (self.rot + d) & 3
        shape = SHAPES[self.cur][nr]
        for (dx, dy) in KICKS:
            if self.board.fits(shape, self.px + dx, self.py + dy):
                self.rot = nr
                self.px += dx
                self.py += dy
                self._nudge()
                return

    def _lock(self):
        board = self.board
        board.lock(SHAPES[self.cur][self.rot], self.px, self.py, self.cur + 1)
        rows = board.full_rows()
        if rows:
            n = len(rows)
            self.streak += 1
            if self.streak > self.maxstreak:
                self.maxstreak = self.streak
            pts = S.LINE_SCORES[n] * self.mult // 10
            if self.streak > 1:
                pts += S.STREAK_BONUS * (self.streak - 1) * self.mult // 10
            self._add(pts)
            self.lines += n
            self.clear_rows = rows
            m = 0
            for r in rows:
                m |= 1 << r
            self.clear_mask = m
            self.clear_t = S.CLEAR_FRAMES
            self.state = CLEAR
            self.ctx.led.flash(20 + 50 * n, 100 + 30 * n, 20, 250)
            self.ctx.audio.beep(660 + 110 * n, 60)
        else:
            self.streak = 0
            self._spawn()
        self._sync()

    def _die(self):
        ctx = self.ctx
        self.state = DEAD
        self.dead_f = 0
        new = sv.submit(ctx.save, self.lv, self.score)
        self.best = sv.load_best(ctx.save, self.lv)
        self.flush_pending = True
        c = config
        self.ovl = A.make_box(126, 82, [
            ("GAME OVER", 2, c.C_RED, 8),
            ("SCORE " + str(self.score), 1, c.C_TEXT, 30),
            ("NEW BEST!" if new else "BEST " + str(self.best), 1, c.C_EMBER_HOT, 42),
            ("A RETRY   X LEVELS", 1, c.C_TEXT_DIM, 58),
            ("B MENU", 1, c.C_TEXT_DIM, 68),
        ])
        ctx.led.flash(230, 30, 10, 400)
        ctx.audio.sfx("dead")
        self._sync()

    def _to_select(self):
        self.state = SEL
        self.ovl = None
        self._build_bests()

    # ------------------------------------------------------------
    def update(self, dt, inp):
        self.tick += 1
        st = self.state
        if st == PLAY:
            self._upd_play(inp)
        elif st == CLEAR:
            self._upd_clear()
        elif st == SEL:
            self._upd_select(inp)
        else:
            self._upd_dead(inp)

    def _upd_select(self, inp):
        n = len(S.LEVELS)
        if inp.nav_y:
            self.lv = (self.lv + inp.nav_y) % n
            self.ctx.led.flash(40, 18, 0, 120)
            self.ctx.audio.sfx("move")
        pm = inp.pressed_mask
        if pm & _START:
            self.ctx.audio.sfx("select")
            self._start(self.lv)
        elif pm & BTN_B:
            self.ctx.home()

    def _upd_dead(self, inp):
        self.dead_f += 1
        if self.flush_pending and self.dead_f == 2:
            self.flush_pending = False
            self.ctx.save.flush()
        pm = inp.pressed_mask
        if pm & BTN_B:
            self.ctx.home()
        elif self.dead_f >= 12:
            if pm & _START:
                self._start(self.lv)
            elif pm & BTN_X:
                self._to_select()

    def _upd_clear(self):
        self.clear_t -= 1
        if self.clear_t > 0:
            return
        for r in self.clear_rows:               # ascending order keeps indices valid
            self.board.remove_row(r)
        self.clear_rows = ()
        self.clear_mask = 0
        self.state = PLAY
        self._spawn()
        self._sync()

    def _upd_play(self, inp):
        pm = inp.pressed_mask
        hm = inp.held_mask
        board = self.board
        if pm & BTN_Y:
            self.ctx.pause()
            return

        if pm & (BTN_A | DIR_U):
            self._rotate(1)
        elif pm & BTN_X:
            self._rotate(-1)

        if pm & BTN_B:                           # hard drop
            gy = board.drop_y(SHAPES[self.cur][self.rot], self.px, self.py)
            self._add(S.HARD_PTS * (gy - self.py))
            self.py = gy
            self._lock()
            return

        dx = (1 if hm & DIR_R else 0) - (1 if hm & DIR_L else 0)
        if dx != self.dirx:
            self.dirx = dx
            self.das = 0
            if dx:
                self._move(dx)
        elif dx:
            self.das += 1
            if self.das >= S.DAS and (self.das - S.DAS) % S.ARR == 0:
                self._move(dx)

        shape = SHAPES[self.cur][self.rot]
        grounded = not board.fits(shape, self.px, self.py + 1)
        if hm & DIR_D:
            self.soft += 1
            if self.soft >= S.SOFT_FRAMES:
                self.soft = 0
                if not grounded:
                    self.py += 1
                    self._add(S.SOFT_PTS)
        else:
            self.soft = 0
            self.fall += 1
            if self.fall >= self.gravity:
                self.fall = 0
                if not grounded:
                    self.py += 1
        grounded = not board.fits(shape, self.px, self.py + 1)
        if grounded:
            self.lock_t += 1
            if self.lock_t >= S.LOCK_DELAY:
                self._lock()
                return
        else:
            self.lock_t = 0
        self._sync()

    # ------------------------------------------------------------
    # drawing
    # ------------------------------------------------------------
    def draw(self, r):
        if self.state == SEL:
            self._draw_select(r)
        else:
            self._draw_game(r)

    def _draw_select(self, r):
        kick = r.kick
        base = r.base
        cov = r.cover if r.cov_on else None
        cov_addr = r.cover_addr
        bg = self.bgrow_a
        s0 = r.s0
        s1 = r.s1
        a0 = r.a0
        a1 = r.a1
        sel = self.lv
        title = self.title
        t_rows = self.title_rows
        t_sh = self.title_sh
        sub = self.sub
        hint = self.hint
        pul = self.pulse
        bar = self.bar_col
        names = self.opt_name
        desc = self.opt_desc
        best = self.opt_best
        c_text = self.c_text
        c_dim = self.c_dim
        c_hot = self.c_hot
        tx = (320 - title.w) >> 1
        sx = (320 - sub.w) >> 1
        hx = (320 - hint.w) >> 1
        pulse_on = ((self.tick >> 3) & 1) == 0
        for y in range(240):
            if cov is not None and cov[y]:
                kick(base, cov_addr)
                continue
            k = y - 88
            i = k // 44 if k >= 0 else -1
            m = k - i * 44 if i >= 0 else 0
            in_opt = 0 <= i < 3 and m < 34
            in_title = 20 <= y < 20 + title.h + 3
            in_sub = 64 <= y < 71
            in_hint = 224 <= y < 231
            if not (in_opt or in_title or in_sub or in_hint):
                kick(base, bg)
                continue
            if y & 1:
                dst = s1
                da = a1
            else:
                dst = s0
                da = a0
            copy_row(dst, bg)
            if in_title:
                kt = y - 20
                if kt >= 3:
                    blit_m(dst, tx + 3, title.addr + (kt - 3) * title.rb, (title.w << 16) | t_sh)
                if kt < title.h:
                    blit_m(dst, tx, title.addr + kt * title.rb, (title.w << 16) | t_rows[kt >> 2])
            elif in_sub:
                blit_m(dst, sx, sub.addr + (y - 64) * sub.rb, (sub.w << 16) | c_dim)
            elif in_hint:
                blit_m(dst, hx, hint.addr + (y - 224) * hint.rb, (hint.w << 16) | c_dim)
            else:
                if i == sel:
                    fill_span(dst, 50, 270, bar)
                    fill_span(dst, 50, 54, pul if pulse_on else bar)
                e = names[i]
                if 5 <= m < 19:
                    blit_m(dst, 64, e.addr + (m - 5) * e.rb, (e.w << 16) | (c_text if i == sel else c_dim))
                if 22 <= m < 29:
                    d = desc[i]
                    blit_m(dst, 64, d.addr + (m - 22) * d.rb, (d.w << 16) | c_dim)
                if 8 <= m < 15:
                    b = best[i]
                    blit_m(dst, 262 - b.w, b.addr + (m - 8) * b.rb, (b.w << 16) | c_hot)
            kick(base, da)

    def _draw_game(self, r):
        kick = r.kick
        base = r.base
        cov = r.cover if r.cov_on else None
        cov_addr = r.cover_addr
        st = self.state
        board = self.board
        rows = board.rows
        pmask = self.pmask
        gmask = self.gmask
        for i in range(ROWS):
            pmask[i] = 0
            gmask[i] = 0
        cur_blk = 0
        if st == PLAY:
            shape = SHAPES[self.cur][self.rot]
            px = self.px
            py = self.py
            gy = board.drop_y(shape, px, py)
            for (x, y) in shape:
                ry = py + y
                if 0 <= ry < ROWS:
                    pmask[ry] |= 1 << (px + x)
                ry = gy + y
                if 0 <= ry < ROWS:
                    gmask[ry] |= 1 << (px + x)
            cur_blk = self.blk[self.cur + 1]
        clear_mask = self.clear_mask
        flash = P16(config.C_TEXT) if ((self.clear_t >> 1) & 1) else P16(config.C_EMBER_HOT)
        plain = self.plain_a
        panel = self.panel_a
        edge = self.edge_a
        strips = self.strip_a
        gx = S.GRID_X
        gyy = S.GRID_Y
        gh = S.GRID_H
        gw = S.GRID_W
        blk = self.blk
        ghost_a = self.ghost.addr
        sx = self.sx
        sy = self.sy
        so = self.so
        sc = self.sc
        sk = self.sk
        rowi = self.rowi
        ovl = self.ovl
        nx = self.nx
        c_ed = self.c_ed
        streak = self.streak
        meter_on = self.meter_on
        meter_off = self.meter_off
        s0 = r.s0
        s1 = r.s1
        a0 = r.a0
        a1 = r.a1
        for y in range(240):
            if cov is not None and cov[y]:
                kick(base, cov_addr)
                continue
            if y < gyy or y >= gyy + gh:
                kick(base, plain)
                continue
            if y & 1:
                dst = s1
                da = a1
            else:
                dst = s0
                da = a0
            if y == gyy or y == gyy + gh - 1:
                copy_row(dst, edge)
            else:
                copy_row(dst, panel)

            # ---- playfield line: pre-drawn empty line, then filled cells, ghost, piece ----
            L = y - gyy
            if L < 3:
                blit_o(dst, gx, strips[L], gw)
            elif L >= gh - 3:
                blit_o(dst, gx, strips[gh - 1 - L], gw)
            else:
                i = L - 3
                rr = i // CELL
                m = i - rr * CELL
                blit_o(dst, gx, strips[3 + m], gw)
                if (clear_mask >> rr) & 1:
                    fill_span(dst, GX0, GX0 + COLS * CELL, flash)
                else:
                    row = rows[rr]
                    for c in range(COLS):
                        v = row[c]
                        if v:
                            blit_o(dst, GX0 + c * CELL, blk[v] + m * 22, CELL)
                    gm = gmask[rr]
                    if gm:
                        for c in range(COLS):
                            if (gm >> c) & 1:
                                blit_t(dst, GX0 + c * CELL, ghost_a + m * 22, CELL)
                    pm = pmask[rr]
                    if pm:
                        for c in range(COLS):
                            if (pm >> c) & 1:
                                blit_o(dst, GX0 + c * CELL, cur_blk + m * 22, CELL)

            # ---- side panels ----
            for i in rowi[y]:
                o = so[i]
                if sk[i]:
                    o.draw(dst, sx[i], y - sy[i], sc[i])
                else:
                    k = y - sy[i]
                    blit_m(dst, sx[i], o.addr + k * o.rb, (o.w << 16) | sc[i])
            if 24 <= y < 80:                                     # next piece box
                if y == 24 or y == 79:
                    fill_span(dst, 230, 306, c_ed)
                else:
                    fill_span(dst, 230, 231, c_ed)
                    fill_span(dst, 305, 306, c_ed)
                for cell in nx:
                    if cell[1] <= y < cell[1] + CELL:
                        blit_o(dst, cell[0], blk[cell[2]] + (y - cell[1]) * 22, CELL)
            if 138 <= y < 147:                                   # streak meter
                for i in range(6):
                    fill_span(dst, 230 + i * 13, 241 + i * 13,
                              meter_on[i] if i < streak else meter_off)
            if ovl is not None and ovl.y <= y < ovl.y + ovl.h:
                ovl.draw_row(dst, y)
            kick(base, da)
