# ============================================================
# Shards of Aetheria: scene (320x240, 30 fps)
#
#   stick L/R move   A jump (A again near the top = double jump, hold = higher)
#   X attack combo / X in the air = ground pound
#   Y ability (charged meter)       B pause menu (system)
#
# 9 levels: three areas x (two courses + a boss). Courses end at a flagpole,
# bosses drop the area's shard.
#
# Memory plan: art.py and levels.py are imported only while a level is being
# built and are unloaded again; bosses.py is loaded only on boss levels;
# sprites are 4-bit. update() does logic and fills the draw tables (view.py),
# draw() only points the viper compositor at them. Level loading is a
# generator so the frame loop never stalls.
# ============================================================
import gc, sys, array, uctypes
from time import ticks_us, ticks_diff
from hardware.display import dma_kick
from hardware.input import BTN_A, BTN_B, BTN_X
from system.scene_manager import Scene
from system.dialog import make_confirm
from assets.fonts import Text
from assets import sounds
from games.shards import settings as S
from games.shards import physics as ph
from games.shards import enemies as E
from games.shards import save as sv
from games.shards.player import Player, Meter
from games.shards.play import PlayMixin, M_TITLE, M_LOAD, M_INTRO, M_PLAY, M_CLEAR, M_DEAD, M_STORY, M_END

STORY = (
    ("SHARD 1 RECOVERED", "THE WARDEN FALLS", "KIRO GAINS THE DOUBLE JUMP",
     "THE SHARD SHOWS A VOLCANO", "THE ASHEN MOUNTAINS BURN"),
    ("SHARD 2 RECOVERED", "THE TITAN CRUMBLES", "FIRE POWER IS MASTERED",
     "THE SHARD SHOWS THE VOID KING", "HE WAITS IN THE LAST TEMPLE"),
    ("THE LAST SHARD IS WHOLE", "THE HEART OF LIGHT SHINES", "AETHERIA IS RESTORED",
     "KIRO IS GUARDIAN OF AETHERIA", ""),
)
MUSIC = ("sh_forest", "sh_ash", "sh_castle")


def _imp(name):
    return __import__("games.shards." + name, None, None, ("x",))


def _drop(name):
    sys.modules.pop("games.shards." + name, None)
    pm = sys.modules.get("games.shards")
    if pm is not None:
        try:
            pm.__dict__.pop(name, None)
        except Exception:
            pass


class Pack:
    pass


class Inp:
    """This frame's input, copied in update() and consumed by the logic that runs
    while the display is streaming (see draw)."""
    held_mask = 0
    pressed_mask = 0


R = None                     # render.py (viper) and view.py are imported inside steps(),
V = None                     # so a compile error there is caught and shown on screen
M_ERR = 8
OKCH = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 :.-!?"


def _clean(s):
    out = ""
    for ch in s.upper():
        out += ch if ch in OKCH else " "
    return " ".join(out.split())[:52]


class ShardsScene(PlayMixin, Scene):
    PURGE = ("games.shards",)

    def __init__(self, ctx):
        self.ctx = ctx

    # ------------------------------------------------------------ life cycle
    def enter(self, ctx):
        for _ in self.steps(ctx):
            pass

    def steps(self, ctx):
        self.ctx = ctx
        self.mode = M_ERR
        self.errscr = None
        self.retry = 0
        try:
            for _ in self._steps(ctx):
                yield
        except Exception as e:
            self._fail(e)

    def _steps(self, ctx):
        global R, V
        R = _imp("render")
        V = _imp("view")
        m = _imp("sfx")
        m.install()
        m = None
        _drop("sfx")
        # Double-buffered draw state: the renderer reads the FRONT set while the game
        # logic (running in the DMA idle gaps) fills the BACK set; they swap each frame.
        self.P = array.array("i", [0] * R.PSIZE)
        self.tbl = array.array("i", [0] * (8 * S.MAXS))
        self.fxa = array.array("i", [0] * (6 * R.MAXFX))
        self.f_P = array.array("i", [0] * R.PSIZE)
        self.f_tbl = array.array("i", [0] * (8 * S.MAXS))
        self.f_fxa = array.array("i", [0] * (6 * R.MAXFX))
        for P_, t_, f_ in ((self.P, self.tbl, self.fxa), (self.f_P, self.f_tbl, self.f_fxa)):
            P_[R.TBL] = uctypes.addressof(t_)
            P_[R.FX] = uctypes.addressof(f_)
        self.pa = uctypes.addressof(self.P)
        self.f_pa = uctypes.addressof(self.f_P)
        self.inpx = Inp()
        self.sim = None
        self.ready = False
        self.rt = 130
        self.cost = [60] * 64
        self.ns = 0
        self.nfx = 0
        self.cov_a = 0
        self.progress = sv.load_level(ctx.save)
        self.pack = None
        self.bg = None
        self.bmod = None
        self.lv = None
        self.player = None
        self.gen = None
        self.box = None
        self.zero_map = bytearray(21 * 15)
        self.title_map = bytearray(21 * 15)
        for x in range(21):
            self.title_map[12 * 21 + x] = 1
            self.title_map[13 * 21 + x] = 2
            self.title_map[14 * 21 + x] = 2
        self.glyphs = [Text(str(i), 1) for i in range(10)] + [Text("-", 1)]
        self.tick = 0
        self.t = 0
        self.shake = 0
        self.aid = 0
        self.carry = 0
        self.new_meter = True
        self.reload_hp = 0
        self.mult = 1
        self.ui = ()
        self.flush_pending = False
        self.last_pw = -1
        self._sn = None
        self._sp = 0
        self._lock = 0
        self._lockp = 0
        self.lvn = 1
        self.cp = 0
        self.pt = []
        self.pops = []
        self.void_fx = None
        self.coin_n = -1
        self.coin_dg = ()
        self.sc_n = -1
        self.sc_dg = ()
        self.wl_n = -1
        self.wl_dg = ()
        self.wx = 0
        self.wy = 0
        self.bonus = 0
        self.title_addr = uctypes.addressof(self.title_map)
        self._clear_level()
        yield
        for _ in self._pack_gen(0, -1, (), True):
            yield
        self._title()
        yield

    def exit(self):
        ctx = self.ctx
        try:
            ctx.audio.stop_music()
            p = getattr(self, "player", None)
            if p is not None:
                sv.submit_score(ctx.save, p.score)
            ctx.led.off()
            ctx.save.flush()
        except Exception as e:
            sys.print_exception(e)
        for d in (sounds.SFX, sounds.SONGS, sounds._CACHE):
            for k in [k for k in d if k.startswith("sh_")]:
                del d[k]
        for n in ("art2", "art", "levels", "bosses", "sfx"):
            _drop(n)
        for n in ("pack", "bg", "lv", "player", "boss", "gen", "bmod", "ui", "box", "glyphs", "enemies",
                  "plats", "projs", "rifts", "blades", "ix", "iy", "ik", "dx", "dk", "ex", "P", "tbl",
                  "fxa", "zero_map", "title_map", "errscr", "f_P", "f_tbl", "f_fxa", "sim"):
            setattr(self, n, None)
        gc.collect()

    def restart(self):
        """Pause menu -> RESTART: replay the current level from its start."""
        if self.player is not None and self.mode in (M_PLAY, M_DEAD):
            self.cp = 0
            self._reload(S.START_HP, True)

    def _free_audio(self):
        """The audio engine caches every sound it has synthesised (and the songs). That cache
        grows while you play and is what starves the loader by level 1-3: drop this game's
        entries (they are rebuilt on demand)."""
        try:
            c = sounds._CACHE
            for k in [k for k in c if k.startswith("sh_")]:
                del c[k]
        except Exception:
            pass

    def _clear_level(self):
        self.enemies = []
        self.projs = []
        self.rifts = []
        self.blades = []
        self.plats = []
        self.ix = array.array("h")
        self.iy = array.array("h")
        self.ik = bytearray()
        self.dx = array.array("h")
        self.dk = bytearray()
        self.ex = []
        self.ilo = 0
        self.vi = 0
        self.vd = 0
        self.boss = None
        self.boss_done = False
        self.chase = 0
        self.chase_col = 0
        self.goal_on = False
        self.flag_y = 0
        self.pt = []
        self.pops = []
        self.void_fx = None

    def _setp(self, idx, val):
        self.P[idx] = val
        self.f_P[idx] = val

    def _zero_front(self):
        """Stop the renderer touching level memory that is about to be freed."""
        f = self.f_P
        f[R.MAPON] = 0
        f[R.NS] = 0
        f[R.NFX] = 0

    def _swap(self):
        self.P, self.f_P = self.f_P, self.P
        self.pa, self.f_pa = self.f_pa, self.pa
        self.tbl, self.f_tbl = self.f_tbl, self.tbl
        self.fxa, self.f_fxa = self.f_fxa, self.fxa
        self.ready = False

    def _bg_params(self):
        bg = self.bg
        sp = self._setp
        sp(R.BG, bg.addr_a)
        sp(R.FAY, bg.min1)
        sp(R.FAHP, bg.a1)
        sp(R.FACOL, bg.c1)
        sp(R.FBY, bg.min2)
        sp(R.FBHP, bg.a2)
        sp(R.FBCOL, bg.c2)
        sp(R.FARMAX, 192)
        sp(R.TSET, self.pack.tiles.addr)

    # ------------------------------------------------------------ art pack (generator)
    def _drop_art(self):
        for n in ("art2", "art", "artlib", "levels"):
            _drop(n)

    def _pack_gen(self, area, bk, specs, title=False):
        """Builds the sprite pack. The art modules are ALWAYS unloaded afterwards, even when
        an allocation fails half way (otherwise their code stays in RAM and every retry
        starts with less memory). title=True builds only what the title screen draws."""
        try:
            yield from self._pack_build(area, bk, specs, title)
        finally:
            self._drop_art()
            gc.collect()

    def _pack_build(self, area, bk, specs, title):
        # Biggest contiguous blocks (tileset 5.6 KB, background bands) are allocated
        # FIRST, while the heap is still unfragmented; the many small sprite
        # buffers come afterwards.
        self.bg = None
        self.pack = None
        gc.collect()
        pk = Pack()
        pk.area = area
        ts = R.TileSet()                         # 5.6 KB block first, while the heap is unfragmented
        # ---- phase 1: art.py (Kiro, enemies, boss) -- then it is unloaded again ----
        art = _imp("art")                        # also loads artlib
        pk.kiro = [None, None] if title else []
        for f in range(2 if title else 0, 6 if title else 14):
            pk.kiro.append(art.kiro(f))
            if f == 6:
                gc.collect()
                yield
        gc.collect()
        yield
        pk.en = {}
        pk.boss = None
        if not title:
            for k in art.AREA_ENEMIES[area]:
                pk.en[k] = tuple(art.ENEMY_FN[k](t) for t in range(E.SPEC[k][6]))
                yield
            if bk == 0:
                pk.boss = (art.warden(0), art.warden(1))
            elif bk == 1:
                pk.boss = (art.titan(0), art.titan(1))
            elif bk == 2:
                pk.boss = (art.king(0), art.king(1))
        art = None
        _drop("art")                             # artlib stays (art2 needs it)
        gc.collect()
        yield
        # ---- phase 2: art2.py (items, projectiles, decor, tiles, background) ----
        art2 = _imp("art2")
        pk.tiles = art2.tileset(area, ts)
        ts = None
        pk.wisp = (art2.wisp((90, 240, 120)), art2.wisp((255, 150, 40)), art2.wisp((190, 90, 255)))
        pk.sky = art2.sky(area)
        if title:
            bg = art2.background(area)
            art2 = None
            self._drop_art()
            gc.collect()
            self.pack = pk
            self.bg = bg
            self._bg_params()
            yield
            return
        gc.collect()
        yield
        pk.coin = tuple(art2.coin(f) for f in range(4))
        pk.heart = (art2.heart(True), art2.heart(False))
        pk.orb = art2.orb()
        pk.flags = (art2.flag(False), art2.flag(True))
        if bk < 0:                               # flagpole course
            pk.pole = art2.pole()
            pk.gflag = art2.goalflag()
        else:                                    # boss arena: shrine + shard
            pk.shard = art2.shard(area)
            pk.shrine = art2.shrine()
        pk.warn = art2.warn()
        gc.collect()
        yield
        pk.spear = art2.spear()
        pk.core = art2.core()
        pk.ball = art2.ball()
        pk.wave = (art2.wave(0), art2.wave(1))
        pk.rock = art2.rock()
        pk.rift = (art2.rift(False), art2.rift(True))
        pk.blade = (art2.blade(0), art2.blade(1))
        pk.decor = art2.decor(area)
        gc.collect()
        yield
        pk.plat = {}
        for k, w in specs:
            pk.plat[(k, w)] = art2.plat(k, w, area)
        bg = art2.background(area)
        art2 = None
        self._drop_art()
        gc.collect()
        self.pack = pk
        self.bg = bg
        self._bg_params()
        yield

    # ------------------------------------------------------------ sound
    def snd(self, name, pr=1):
        """Queue a sound effect: the highest priority queued in a frame wins, and a
        long important effect is not cut short by a trivial one."""
        if pr >= self._sp:
            self._sp = pr
            self._sn = name

    def _flush_snd(self):
        n = self._sn
        if self._lock:
            self._lock -= 1
        if n is not None:
            if self._lock == 0 or self._sp >= self._lockp:
                self.ctx.audio.sfx(n)
                tot = 0
                for seg in sounds.SFX[n]:
                    tot += seg[2]
                self._lock = tot // 3 + 1
                self._lockp = self._sp
            self._sn = None
            self._sp = 0

    # ------------------------------------------------------------ screens
    def _txt(self, s, scale, col, y, blink=0):
        t = Text(s, scale)
        return (t, (320 - t.w) >> 1, y, col, blink)

    def _title(self):
        self.mode = M_TITLE
        self.lv = None
        self.player = None
        self.t = 0
        ui = [self._txt("SHARDS OF", 2, V.C_GOLD, 36),
              self._txt("AETHERIA", 3, V.C_TITLE, 58),
              self._txt("A NEW GAME", 1, V.C_WHITE, 120, 1)]
        if self.progress > 1:
            n = self.progress - 1
            ui.append(self._txt("X CONTINUE " + str(n // 3 + 1) + "-" + str(n % 3 + 1), 1, V.C_WHITE, 136))
        ui.append(self._txt("B BACK", 1, V.C_DIM, 152))
        best = sv.best(self.ctx.save)
        if best:
            ui.append(self._txt("BEST " + str(best), 1, V.C_YEL, 170))
        self.ui = ui
        self.ctx.audio.music("sh_title")

    def _story(self, a):
        self.mode = M_STORY
        self.t = 0
        self._zero_front()
        self.lv = None
        self.boss = None
        ui = []
        y = 46
        for i, s in enumerate(STORY[a]):
            if s:
                ui.append(self._txt(s, 2 if i == 0 else 1, V.C_GOLD if i == 0 else V.C_WHITE, y))
                y += 28 if i == 0 else 16
        ui.append(self._txt("A CONTINUE", 1, V.C_DIM, 200, 1))
        self.ui = ui
        self.ctx.audio.stop_music()
        self.snd("sh_clear", 6)

    # ------------------------------------------------------------ level load (generator)
    def _begin(self, n, fresh=True):
        self.lvn = n
        if fresh:
            self.player = Player()
            self.new_meter = True
            self.carry = 0
        elif (n - 1) % 3 == 0:                       # new area: meter restarts from its carry
            self.new_meter = True
        else:
            self.new_meter = False
        self.cp = 0
        self._reload(0, self.new_meter)

    def _reload(self, hp, newm):
        self.reload_hp = hp
        self.new_meter = newm
        self.gen = self._load_steps(self.lvn, self.cp)
        self.mode = M_LOAD
        self.ui = [self._txt("LOADING", 2, V.C_GOLD, 100)]
        self._setp(R.MAPON, 0)
        self._zero_front()
        self.ctx.audio.stop_music()

    def _load_steps(self, n, cp):
        a = (n - 1) // 3
        sub = (n - 1) % 3
        self.lv = None
        self._clear_level()
        self.pack = None
        self.bg = None
        self.bmod = None
        _drop("bosses")
        self._free_audio()
        gc.collect()
        yield
        if sub == 2:                             # boss code is compiled FIRST: the heap is emptiest
            self.bmod = _imp("bosses")           # now, and compiling needs big temporary blocks
            gc.collect()
            yield
        m = _imp("levels")
        lv = m.build(n)
        name = m.NAMES[n - 1]
        aname = m.AREAS[a]
        m = None
        _drop("levels")
        gc.collect()
        yield
        bk = a if sub == 2 else -1
        # Items / decor become compact arrays NOW (their tuples are freed) so the level
        # data is as small as possible while the art modules are being compiled.
        n_i = len(lv.items)
        self.ix = array.array("h", [0] * n_i)
        self.iy = array.array("h", [0] * n_i)
        self.ik = bytearray(n_i)
        for i in range(n_i):
            k, tx, ty = lv.items[i]
            self.ik[i] = k
            self.ix[i] = tx * 16 + (4 if k == 0 else 3)
            self.iy[i] = ty * 16 + 4
        lv.items = None
        n_d = len(lv.decor)
        lv.decor.sort(key=lambda d: d[1])
        self.dk = bytearray(n_d)
        self.dx = array.array("h", [0] * n_d)
        for i in range(n_d):
            self.dk[i] = lv.decor[i][0]
            self.dx[i] = lv.decor[i][1]
        lv.decor = None
        gc.collect()
        yield
        specs = set()
        for pl in lv.plats:
            specs.add((pl.kind, pl.w))
        for _ in self._pack_gen(a, bk, specs):
            yield
        specs = None
        # enemies are created last, after the art code has been freed (they are the
        # biggest per-level objects)
        self.enemies = [E.Enemy(k, tx, ty) for (k, tx, ty) in lv.en]
        lv.en = None
        gc.collect()
        yield
        self.blades = lv.blades
        self.plats = lv.plats
        self.goal_on = sub != 2
        self.t = 0
        self.cp = cp
        p = self.player
        p.dj = a >= 1
        if self.new_meter or p.meter is None:
            p.meter = Meter(a + 1, S.charge_rates(a), self.carry if self.carry > 0 else 0)
        self.carry = 0
        self.last_pw = p.meter.power()
        p.hp = self.reload_hp if self.reload_hp else max(p.hp, S.START_HP)
        if p.maxhp < S.START_HP:
            p.maxhp = S.START_HP
        if p.hp > p.maxhp:
            p.maxhp = p.hp
        self.lv = lv
        self._place(cp)
        self.wx = (p.x >> 4)
        self.wy = (p.y >> 4) - 10
        self.cam = self._cam_target()
        self._setp(R.MAP, uctypes.addressof(lv.tiles))
        self._setp(R.LW, lv.lw)
        self._setp(R.MAPON, 1)
        ui = [self._txt("WORLD " + str(a + 1) + "-" + str(sub + 1), 2, V.C_GOLD, 66),
              self._txt(name, 1, V.C_WHITE, 92)]
        if sub == 0:
            ui.append(self._txt(aname, 1, V.C_ORANGE, 108))
        if a >= 1 and sub == 0:
            ui.append(self._txt("FIRE DASH UNLOCKED" if a == 1 else "VOID COLLAPSE UNLOCKED", 1, V.C_VIOLET, 124))
        self.ui = ui
        self.mode = M_INTRO
        self.t = 0
        self.retry = 0
        self.ctx.audio.music(MUSIC[a])
        self.snd("sh_start", 3)
        gc.collect()
        yield

    def _place(self, cp):
        tx, row = self.lv.cps[cp]
        p = self.player
        p.reset_pos(tx * 16 + 3, row * 16 - 22)
        p.inv = 90

    def _cam_target(self):
        lv = self.lv
        p = self.player
        t = (p.x >> 4) - 130 + (p.vx >> 1)
        if self.boss is not None:
            t = lv.arena
        m = lv.lw * 16 - 320
        if t < 0:
            t = 0
        if t > m:
            t = m
        return t

    # ------------------------------------------------------------ helpers used by other modules
    def solid_px(self, x, y):
        return ph.solid_px(self.lv, x, y)

    def support_px(self, x, y):
        return ph.support_px(self.lv, x, y)

    def hazard_px(self, x, y):
        return ph.hazard_px(self.lv, x, y)

    def ground_y(self, x, y):
        r = y >> 4
        if r < 0:
            r = 0
        lv = self.lv
        while r < 15:
            if ph.support_px(lv, x, r << 4):
                return r << 4
            r += 1
        return 0

    def new_aid(self):
        self.aid += 1
        return self.aid

    def add_proj(self, kind, x, y, vx, vy, w, h, life, grav=0):
        if len(self.projs) < 24:
            self.projs.append(E.Proj(kind, x, y, vx, vy, w, h, life, grav))

    def add_rift(self, x, y):
        if len(self.rifts) < 4:
            self.rifts.append(E.Rift(x, y))

    def dust(self, x, y, n):
        pt = self.pt
        for i in range(n):
            q = [x + 4 + i * 3 - n, y, (i - n // 2) * 3, -4, 8, V.DUST[self.pack.area if self.pack else 0]]
            if len(pt) < 10:
                pt.append(q)
            else:
                pt[(self.tick + i) % 10] = q

    def popup(self, x, y, val):
        if len(self.pops) < 6:
            self.pops.append([x, y, [ord(c) - 48 for c in str(val)], 30])

    def on_kill(self, e):
        p = self.player
        v = e.score * self.mult
        p.score += v
        self.popup(e.x + (e.w >> 1) - 8, e.y - 6, v)
        self.snd("sh_kill", 2)
        cx = e.x + (e.w >> 1)
        pt = self.pt
        for i in range(5):
            q = [cx, e.y + (e.h >> 1), (i - 2) * 5, -6 - (i & 1) * 3, 12, V.BURST]
            if len(pt) < 10:
                pt.append(q)
            else:
                pt[(self.tick + i) % 10] = q

    def on_player_hurt(self):
        self.snd("sh_hurt", 5)
        self.ctx.led.flash(230, 30, 10, 250)
        self.shake = 6
        if self.player.hp <= 0:
            self._game_over()

    # ------------------------------------------------------------ boss hooks
    def arena_change(self, kind, phase):
        lv = self.lv
        col = lv.arena >> 4
        if kind == 2:
            lv.rect(col + 8, 9, col + 10, 9, 7)
            V.recolor(self.bg, phase - 1)
            self._bg_params()
        for q in self.projs:
            q.alive = False
        self.ex.append([1, lv.arena + 150, 12 * 16 - 20])
        self.ctx.led.flash(200, 20, 120, 400)
        self.snd("sh_b_phase", 5)

    def on_boss_dying(self):
        for q in self.projs:
            q.alive = False
        self.ctx.audio.stop_music()
        self.snd("sh_b_die", 6)

    def boss_dead(self):
        lv = self.lv
        self.boss = None
        self.boss_done = True
        self.goal_on = True
        lv.goal = lv.arena + 153
        self.ex.append([1, lv.arena + 100, 12 * 16 - 20])
        self.ctx.led.flash(255, 255, 255, 500)
        self.ctx.audio.music("sh_story")

    # ------------------------------------------------------------ death / respawn
    def _game_over(self):
        if self.mode == M_DEAD:
            return
        self.mode = M_DEAD
        self.t = 0
        self.box = make_confirm("GAME OVER", "A RETRY    B MENU", "FROM LAST CHECKPOINT")
        self.ui = ()
        self.ctx.audio.stop_music()
        self.ctx.audio.music("gameover", False)

    def _fall(self):
        p = self.player
        p.hp -= 1
        self.ctx.led.flash(230, 30, 10, 300)
        self.snd("sh_fall", 5)
        if p.hp <= 0:
            self._game_over()
        elif self.chase or self.boss is not None:
            self.carry = p.meter.carry()
            self._reload(p.hp, True)
        else:
            self._place(self.cp)
            self.cam = self._cam_target()

    # ------------------------------------------------------------ update
    def update(self, dt, inp):
        """Called first in every frame while the display is idle, so it only copies the
        input and queues this frame's logic; that logic runs inside draw(), in the gaps
        while the DMA streams rows (see _draw)."""
        if self.mode == M_ERR:
            es = self.errscr
            if es is not None:
                es.update()
            if es is None or (inp.pressed_mask & (BTN_A | BTN_B)):
                self.ctx.home()
            return
        if self.sim is not None:
            self.finish_sim()
            if self.mode == M_ERR:
                return
        ix = self.inpx
        ix.held_mask = inp.held_mask
        ix.pressed_mask = inp.pressed_mask
        self.sim = self._frame(ix)
        if not S.OVERLAP:
            self.finish_sim()
            if self.ready:
                self._swap()

    def finish_sim(self):
        gen = self.sim
        self.sim = None
        if gen is None:
            return
        try:
            for _ in gen:
                pass
        except Exception as e:
            self._recover(e)

    def _recover(self, e):
        """Out of memory while loading a level: collect and try once more. Anything
        else: show the error on screen (and log it) instead of silently quitting."""
        if isinstance(e, MemoryError) and self.mode == M_LOAD and self.retry < 2:
            self.retry += 1
            self.gen = None                      # the dead generator still holds pack / level
            self.lv = None
            self.pack = None
            self.bg = None
            self.bmod = None
            self._clear_level()
            self._zero_front()
            for n in ("art2", "art", "artlib", "levels", "bosses"):
                _drop(n)
            self._free_audio()
            gc.collect()
            self.gen = self._load_steps(self.lvn, self.cp)
            return
        self._fail(e)

    def _fail(self, e):
        self.mode = M_ERR
        self.gen = None
        txt = ""
        loc = ""
        try:
            import io
            buf = io.StringIO()
            sys.print_exception(e, buf)
            txt = buf.getvalue()
            sys.print_exception(e)
            for ln in txt.split("\n"):
                if "File " in ln and '"' in ln:
                    f = ln.split('"')[1].split("/")[-1]
                    n = ln.split("line ")[1].split(",")[0] if "line " in ln else ""
                    loc = f + ":" + n
        except Exception:
            pass
        try:
            import os
            try:
                os.mkdir("data")
            except OSError:
                pass
            with open("data/shards_error.txt", "w") as fh:
                fh.write(txt or repr(e))
        except Exception:
            pass
        try:
            from system.loading import LoadingScreen
            self.errscr = LoadingScreen("SHARDS ERROR", _clean(loc + " " + type(e).__name__ + " " + str(e)))
        except Exception:
            self.errscr = None

    def _frame(self, inp):
        self.tick += 1
        m = self.mode
        pm = inp.pressed_mask
        if m == M_PLAY:
            yield from self._play(inp)
        elif m == M_INTRO:
            self.t += 1
            if self.t >= 70:
                self.ui = ()
                self.mode = M_PLAY
        elif m == M_TITLE:
            if pm & BTN_A:
                self.snd("sh_menu", 3)
                self._begin(1)
            elif (pm & BTN_X) and self.progress > 1:
                self.snd("sh_menu", 3)
                self._begin(self.progress)
            elif pm & BTN_B:
                self.ctx.home()
                return
        elif m == M_LOAD:
            try:
                next(self.gen)
            except StopIteration:
                self.gen = None
        elif m == M_CLEAR:
            self._clear(pm)
        elif m == M_DEAD:
            self.t += 1
            if self.t > 20:
                if pm & BTN_A:
                    self.box = None
                    self._reload(S.START_HP, True)
                elif pm & BTN_B:
                    self.ctx.home()
                    return
        elif m == M_STORY:
            self.t += 1
            if self.t == 2:
                if self.flush_pending:
                    self.flush_pending = False
                    self.ctx.save.flush()
                self.ctx.audio.music("sh_story")
            if self.t > 20 and (pm & BTN_A):
                self.snd("sh_menu", 3)
                if self.lvn >= 9:
                    self._ending()
                else:
                    self.lvn += 1
                    self._begin(self.lvn, False)
        else:
            self._end_screen(pm)
        self._flush_snd()
        yield
        yield from V.build(self)
        self.ready = True

    def _ending(self):
        self.mode = M_END
        self.t = 0
        self._zero_front()
        self.lv = None
        self._setp(R.MAPON, 0)
        self.ui = [self._txt("THE END", 3, V.C_GOLD, 70)]
        self.ctx.audio.stop_music()
        self.ctx.audio.music("sh_win", False)

    def _end_screen(self, pm):
        self.t += 1
        if self.t == 150:
            self.ui = list(self.ui) + [self._txt("SOMETHING STIRS IN THE DARK", 1, V.C_VIOLET, 130)]
            self.ctx.audio.music("sh_story")
        if self.t > 200 and (pm & (BTN_A | BTN_B)):
            self.ctx.home()

    def _flag_hit(self, p, py):
        """Mario-style flagpole: height of the grab decides the bonus."""
        self.mode = M_CLEAR
        self.t = 0
        h = (192 - py) // 16
        bonus = 100 + h * 100
        p.score += bonus
        self.flag_y = 70
        self.bonus = bonus
        p.vx = 0
        p.vy = 0
        p.x = (self.lv.goal - 9) << 4
        self.ctx.audio.stop_music()
        self.snd("sh_flag", 6)
        self.ui = [self._txt("COURSE CLEAR", 2, V.C_GOLD, 70),
                   self._txt("BONUS " + str(bonus), 1, V.C_WHITE, 96)]

    def _clear(self, pm):
        p = self.player
        self.t += 1
        t = self.t
        if self.flag_y < 170:
            self.flag_y += 3
        if t == 40 and self.lvn + 1 > self.progress:
            self.progress = self.lvn + 1
            sv.unlock(self.ctx.save, self.lvn + 1)
            sv.submit_score(self.ctx.save, p.score)
            self.ctx.save.flush()
        if t > 40 and self.lv is not None:
            p.x += 40
            p.face = 1
            p.ground = True
        if t >= 120:
            self.lvn += 1
            self._begin(self.lvn, False)

    def _level_done(self):
        """Boss shard collected: save, then the area's story page."""
        p = self.player
        n = self.lvn
        self.carry = p.meter.carry()
        p.score += 5000
        if sv.unlock(self.ctx.save, n + 1):
            self.flush_pending = True
        sv.submit_score(self.ctx.save, p.score)
        if n >= 9:
            sv.set_finished(self.ctx.save)
            self.flush_pending = True
        self.progress = max(self.progress, min(n + 1, 9))
        self.ctx.led.flash(255, 240, 120, 600)
        self._story((n - 1) // 3)

    # ------------------------------------------------------------ draw
    def draw(self, r):
        if self.mode == M_ERR:
            self._draw_err(r)
            return
        try:
            self._draw(r)
        except Exception as e:
            self._fail(e)
            self._draw_err(r)

    def _draw_err(self, r):
        es = self.errscr
        if es is not None:
            es.draw(r)
        else:
            for y in range(240):
                r.kick(r.base, r.cover_addr)

    def _draw(self, r):
        if self.ready:
            self._swap()
        P = self.f_P
        P[R.BASE] = r.base
        P[R.S0] = r.a0
        P[R.S1] = r.a1
        if not self.cov_a:
            self.cov_a = uctypes.addressof(r.cover)
        P[R.COVON] = 1 if r.cov_on else 0
        P[R.COVP] = self.cov_a
        P[R.COVA] = r.cover_addr
        gen = self.sim
        self.sim = None
        box = self.box if self.mode == M_DEAD else None
        if gen is None and box is None and r.kick is dma_kick:
            R.render(self.f_pa)                    # nothing to overlap: all-viper fast path
            return
        # Frame time is set by the DMA (~32 ms for 240 rows), so game logic must hide in the
        # gaps while a row streams. After composing each row we run logic slices (the
        # coroutine's steps) for as long as the previous row is still being sent, judged by
        # a running estimate of the row time (rt) and of the slice cost (pred).
        kick = r.kick
        base = r.base
        cov = r.cover if r.cov_on else None
        ca = r.cover_addr
        pa = self.f_pa
        row = R.row
        s0 = r.s0
        s1 = r.s1
        rt = self.rt
        cost = self.cost
        n = 0
        tk = ticks_us()
        for y in range(240):
            if cov is not None and cov[y]:
                kick(base, ca)
                tk = ticks_us()
                continue
            try:
                da = row(y, pa)
                if box is not None and box.y <= y < box.y + box.h:
                    box.draw_row(s1 if (y & 1) else s0, y)
            except Exception:
                da = ca
            ran = False
            if gen is not None:
                while True:
                    t1 = ticks_us()
                    el = ticks_diff(t1, tk)
                    pc = cost[n] if n < 64 else 100
                    if el + pc > rt and (ran or el + 12 > rt):
                        break                              # would starve the DMA: wait for the next row
                    ran = True                             # (one slice per row always runs: progress)
                    try:
                        next(gen)
                    except StopIteration:
                        gen = None
                        break
                    except Exception as e:
                        gen = None
                        self._recover(e)
                        break
                    if n < 64:
                        cost[n] = ticks_diff(ticks_us(), t1)
                    n += 1
            kick(base, da)
            t2 = ticks_us()
            if not ran:
                iv = ticks_diff(t2, tk)
                if 100 < iv < 220:
                    rt = (rt * 7 + iv) >> 3              # nothing ran: this is the pure row time
            tk = t2
        self.rt = rt
        while gen is not None:                         # logic that did not fit: finish it now
            try:
                next(gen)
            except StopIteration:
                gen = None
            except Exception as e:
                gen = None
                self._recover(e)