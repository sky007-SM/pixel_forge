# ============================================================
# ForgeRacer scene: menus, race state machine, input coordination.
#
# Controls (race):  A = accelerator (hold)   B = brake (hold)
#                   X = nitro (one press)    Y = pause menu
#                   joystick left / right = proportional steering
# Menus:            stick = move, A = select / buy, B = back
#
# Console integration: pause / restart / quit use the system pause menu,
# loading uses the scene manager's loading screen. Memory: the menus are light;
# the first race imports the race modules and allocates every buffer it needs
# (track map + arrays, nine cars with sprite buffers, race view) ONCE, then
# reuses them for every later race, so playing any number of races cannot
# fragment the heap. Distant rivals drive "on rails"
# (opponents.Driver.rails) to keep the CPU budget. The race clock follows
# real time, so it stays correct even if a frame runs long.
# ============================================================
import gc
import sys
import time
import math
import random
import uctypes
from hardware.display import P16
from hardware.input import BTN_A, BTN_B, BTN_X, BTN_Y
from system.scene_manager import Scene
from system.dialog import Box
from assets.fonts import Text
from games.racer import settings as S
from games.racer import assets as A
from games.racer import save as SV
from games.racer.cars import CARS, Car, STAT_NAMES, stats_of
from games.racer.trackdefs import TRACKS
from games.racer import renderer as RV

# Race code is imported lazily when the first race starts (compiling it all at
# once when the game opens needs a lot of heap). Names are bound by _load_code().
PR = PH = OP = Track = TrackMem = Camera = RW = None


def _imp(name):
    return __import__(name, None, None, ("*",))      # returns the submodule itself


def _load_code():
    """Generator: imports the race modules one per step."""
    global PR, PH, OP, Track, TrackMem, Camera, RW
    PR = _imp("games.racer.progress")
    yield
    PH = _imp("games.racer.physics")
    yield
    OP = _imp("games.racer.opponents")
    yield
    Camera = _imp("games.racer.camera").Camera
    yield
    tm = _imp("games.racer.track")
    Track = tm.Track
    TrackMem = tm.TrackMem
    yield
    RW = _imp("games.racer.racerview")
    yield


MAIN = 0
GARAGE = 1
TRACKS_ST = 2
LOAD = 3
COUNT = 4
RACE = 5
RESULT = 6

_AI_COLORS = (S.rgb(230, 60, 60), S.rgb(60, 200, 90), S.rgb(255, 150, 30),
              S.rgb(40, 200, 210), S.rgb(230, 90, 190), S.rgb(150, 150, 160),
              S.rgb(120, 90, 50), S.rgb(255, 235, 90), S.rgb(90, 90, 230))
_MAIN_ITEMS = ("RACE", "GARAGE", "EXIT")
_LOD2 = S.LOD_R * S.LOD_R


def _money(n):
    # the console font has no "$" or ","; amounts are shown as plain numbers with a label
    return "%d" % n


def _ms(ms):
    ms = int(ms)
    return "%d:%02d.%02d" % (ms // 60000, (ms // 1000) % 60, (ms // 10) % 100)


def _ord(n):
    if n == 1:
        return "1ST"
    if n == 2:
        return "2ND"
    if n == 3:
        return "3RD"
    return "%dTH" % n


def _memlog(tag):
    """With PROFILE on: print the free heap after a load stage (shows where memory goes)."""
    if S.PROFILE:
        gc.collect()
        print("racer mem %-22s free %d" % (tag, gc.mem_free()))


class RacerScene(Scene):
    PURGE = ("games.racer",)

    def __init__(self, ctx):
        self.ctx = ctx

    # ------------------------------------------------------------
    def enter(self, ctx):
        for _ in self.steps(ctx):
            pass

    def steps(self, ctx):
        self.ctx = ctx
        self.released = False
        self.art = A.CarArt()
        yield
        self.menu = RV.MenuView()
        self.view = None                       # created by the first race (see _build_gen)
        self.mem = None
        self.pool = None
        self.cam = None
        yield
        self.trk = None
        self.gen = None
        self.load_p = 0.0
        self.cars = []
        self.live = []
        self.ai = []
        self.player = None
        self.pdrv = None
        self.tick = 0
        self.state = MAIN
        self.msel = 0
        self.gsel = SV.selected_car(ctx.save)
        self.tsel = 0
        self.msg = ""
        self.msg_t = 0.0
        self.flush_pending = False
        self.result = None
        self.order = []
        self.bump_cd = 0.0
        self.prev_pal = None
        self.race_ms = 0.0
        self.tidx = 0
        self.t_frame = 0
        self.prof = [0, 0, 0, 0, 0]
        self._refresh_save()
        self._page()
        gc.collect()
        _memlog("scene ready")
        yield

    def exit(self):
        self.ctx.led.off()
        self.ctx.save.flush()
        self._free_race()
        self.art = self.menu = self.cam = self.view = self.mem = self.pool = None
        self.trk = None

    def restart(self):
        """Pause menu -> RESTART: same track, fresh grid."""
        if self.trk is not None and self.state in (COUNT, RACE, RESULT):
            self._setup_cars()

    def _refresh_save(self):
        sv = self.ctx.save
        self.money = SV.money(sv)
        self.car_sel = SV.selected_car(sv)

    def _free_race(self):
        """Let go of the race (the big buffers stay allocated for the next one)."""
        if self.trk is not None:
            self.trk.free()
        self.trk = None
        self.gen = None
        self.cars = []
        self.live = []
        self.ai = []
        self.player = None
        self.pdrv = None
        if self.view is not None:
            self.view.release()
        gc.collect()

    def _bail(self, msg):
        """Something went wrong (e.g. low memory): drop back to the track list instead of crashing."""
        try:
            self._free_race()
        except Exception as e:
            sys.print_exception(e)
        gc.collect()
        self.state = TRACKS_ST
        self.msg = msg
        self.msg_t = 3.0
        self._refresh_save()
        self._page()

    # ------------------------------------------------------------
    # menu pages (rebuilt only when something changes)
    # ------------------------------------------------------------
    def _t(self, s, x, y, scale, color, center=False, shadow=True):
        t = Text(s, scale)
        if center:
            x = (320 - t.w) >> 1
        pg = self.menu.page
        if shadow:
            pg.text(x + 1, y + 1, t, P16(S.BLACK))
        pg.text(x, y, t, P16(color))

    def _r(self, x, y, w, h, color):
        self.menu.page.rect(x, y, w, h, P16(color))

    def _page(self):
        m = self.menu
        m.clear()
        st = self.state
        sv = self.ctx.save
        t = self._t
        r = self._r
        if st == MAIN:
            t(S.NAME, 0, 22, 4, S.YELLOW, True)
            r(40, 62, 240, 3, S.ORANGE)
            t("CASH " + _money(self.money), 0, 74, 2, S.GREEN, True)
            for i in range(3):
                y = 112 + i * 34
                if i == self.msel:
                    r(70, y - 6, 180, 28, S.PANEL2)
                    r(70, y - 6, 4, 28, S.YELLOW)
                t(_MAIN_ITEMS[i], 0, y, 2, S.WHITE if i == self.msel else S.GREY, True)
            t("STICK MOVE   A SELECT   B EXIT", 0, 224, 1, S.GREY, True)
        elif st == GARAGE:
            sp = CARS[self.gsel]
            t("GARAGE", 0, 6, 2, S.YELLOW, True)
            t("<", 14, 34, 3, S.WHITE)
            t(">", 290, 34, 3, S.WHITE)
            t(sp.name, 0, 34, 3, S.WHITE, True)
            r(12, 62, 96, 96, S.PANEL2)
            r(12, 62, 96, 3, S.CYAN)
            self.prev_pal = A.make_car_pal(sp.body, sp.accent)
            m.page.car(18, 70, self.art.addr, A.pal_addr(self.prev_pal))
            fr = stats_of(sp)
            for i in range(5):
                y = 70 + i * 16
                t(STAT_NAMES[i], 116, y, 1, S.WHITE)
                r(176, y, 104, 9, S.PANEL2)
                w = int(fr[i] * 100)
                if w > 0:
                    r(178, y + 2, w, 5, S.CYAN if fr[i] < 0.9 else S.YELLOW)
            owned = SV.owns_car(sv, self.gsel)
            if owned and self.gsel == self.car_sel:
                t("SELECTED", 0, 158, 2, S.GREEN, True)
            elif owned:
                t("OWNED - A TO SELECT", 0, 158, 2, S.WHITE, True)
            else:
                col = S.GREEN if self.money >= sp.price else S.RED
                t("A TO BUY FOR " + _money(sp.price), 0, 158, 2, col, True)
            t(sp.blurb, 0, 184, 1, S.GREY, True)
            t("CASH " + _money(self.money), 0, 200, 2, S.GREEN, True)
            if self.msg_t > 0.0:
                t(self.msg, 0, 216, 1, S.RED, True)
            else:
                t("STICK L/R  A OK  B BACK", 0, 224, 1, S.GREY, True)
        elif st == TRACKS_ST:
            d = TRACKS[self.tsel]
            unlocked = SV.track_unlocked(sv, self.tsel)
            t("SELECT TRACK", 0, 6, 2, S.YELLOW, True)
            t("<", 14, 56, 3, S.WHITE)
            t(">", 290, 56, 3, S.WHITE)
            t("TRACK %d" % (self.tsel + 1), 0, 40, 1, S.GREY, True)
            t(d.name, 0, 56, 3, S.WHITE if unlocked else S.GREY, True)
            t(d.blurb, 0, 88, 1, S.GREY, True)
            for i in range(4):
                col = S.GREEN if SV.track_unlocked(sv, i) else S.DGREY
                if i == self.tsel:
                    r(124 + i * 24 - 2, 108, 20, 14, S.WHITE)
                r(124 + i * 24, 110, 16, 10, col)
            if self.msg_t > 0.0:
                t(self.msg, 0, 206, 1, S.RED, True)
            if unlocked:
                t("%d LAPS   %d RIVALS" % (d.laps, d.n_ai), 0, 134, 2, S.WHITE, True)
                b = SV.best_time(sv, self.tsel)
                t("BEST " + (_ms(b) if b else "--"), 0, 160, 2, S.CYAN, True)
                t("CAR: " + CARS[self.car_sel].name, 0, 186, 1, S.GREY, True)
                t("A START   B BACK", 0, 224, 1, S.GREY, True)
            else:
                t("LOCKED", 0, 140, 3, S.RED, True)
                t("FINISH TOP 3 ON TRACK %d" % self.tsel, 0, 176, 1, S.WHITE, True)
                t("B BACK", 0, 224, 1, S.GREY, True)
        else:                                          # LOAD: building the track
            t("BUILDING TRACK", 0, 96, 2, S.YELLOW, True)
            r(80, 130, 160, 10, S.PANEL2)
            w = int(self.load_p * 156.0)
            if w > 0:
                r(82, 132, w, 6, S.ORANGE)
            t(TRACKS[self.tidx].name, 0, 156, 1, S.GREY, True)

    # ------------------------------------------------------------
    def _steer_input(self, inp):
        a = inp.ax / 1000.0
        mag = a if a >= 0.0 else -a
        dz = S.STEER_DEADZONE
        if mag < dz:
            return 0.0
        mag = (mag - dz) / (1.0 - dz)
        if mag > 1.0:
            mag = 1.0
        e = S.STEER_EXPO
        mag = mag * (1.0 - e) + mag * mag * e
        return mag if a > 0.0 else -mag

    def update(self, dt, inp):
        if self.released:
            return
        self.t_frame = time.ticks_us()
        try:
            self._update(dt, inp)
        except MemoryError:
            gc.collect()
            print("racer: out of memory, free heap", gc.mem_free())
            if self.state >= LOAD:
                self._bail("LOW MEMORY - TRY AGAIN")
        except Exception as e:
            sys.print_exception(e)
            if self.state >= LOAD:
                self._bail("RACE ERROR - SEE CONSOLE")
        # never let a garbage collection happen while the picture is being sent
        if self.state >= COUNT and gc.mem_free() < S.GC_MIN:
            gc.collect()
        if S.PROFILE:
            self.prof[0] += time.ticks_diff(time.ticks_us(), self.t_frame)

    def _update(self, dt, inp):
        ctx = self.ctx
        self.tick += 1
        if self.msg_t > 0.0:
            self.msg_t -= dt
            if self.msg_t <= 0.0 and self.state in (GARAGE, TRACKS_ST):
                self._page()
        if self.flush_pending and self.state in (MAIN, GARAGE, TRACKS_ST, RESULT):
            self.flush_pending = False
            ctx.save.flush()            # static screen: the flash write is invisible
        st = self.state
        if st <= TRACKS_ST:
            self._menu_update(inp)
        elif st == LOAD:
            self._load_update()
        elif st == COUNT:
            self._count_update(dt)
        else:
            self._race_update(dt, inp)

    # ---------------- menus ----------------
    def _menu_update(self, inp):
        ctx = self.ctx
        st = self.state
        nx = inp.nav_x
        ny = inp.nav_y
        a = inp.pressed_mask & BTN_A
        b = inp.pressed_mask & BTN_B
        if st == MAIN:
            if ny:
                self.msel = (self.msel + ny) % 3
                ctx.audio.beep(*A.SFX_CLICK)
                self._page()
            elif a:
                ctx.audio.beep(*A.SFX_CLICK)
                if self.msel == 0:
                    self.state = TRACKS_ST
                elif self.msel == 1:
                    self.state = GARAGE
                    self.gsel = self.car_sel
                else:
                    ctx.home()
                    return
                self._page()
            elif b:
                ctx.home()
        elif st == GARAGE:
            if nx:
                self.gsel = (self.gsel + nx) % len(CARS)
                ctx.audio.beep(*A.SFX_CLICK)
                self._page()
            elif a:
                sv = ctx.save
                sp = CARS[self.gsel]
                if SV.owns_car(sv, self.gsel):
                    SV.select_car(sv, self.gsel)
                    ctx.audio.beep(*A.SFX_CLICK)
                elif SV.buy_car(sv, self.gsel, sp.price):
                    SV.select_car(sv, self.gsel)
                    ctx.audio.beep(*A.SFX_BUY)
                    self.flush_pending = True
                else:
                    self.msg = "NOT ENOUGH MONEY"
                    self.msg_t = 1.5
                    ctx.audio.beep(*A.SFX_NO)
                self._refresh_save()
                self._page()
            elif b:
                self.state = MAIN
                self._page()
        else:
            if nx:
                self.tsel = (self.tsel + nx) % len(TRACKS)
                ctx.audio.beep(*A.SFX_CLICK)
                self._page()
            elif a and SV.track_unlocked(ctx.save, self.tsel):
                self._begin_load()
            elif a:
                ctx.audio.beep(*A.SFX_NO)
            elif b:
                self.state = MAIN
                self._page()

    # ---------------- race setup ----------------
    def _begin_load(self):
        """Start loading: one small step per frame (the page shows a progress bar)."""
        self.menu.clear()
        self.tidx = self.tsel
        self.gen = self._build_gen()
        self.load_p = 0.0
        self.state = LOAD
        self._page()

    def _build_gen(self):
        """Generator: race code, one-time buffers (first race only), then the track itself."""
        if PR is None or RW is None:
            for _ in _load_code():
                gc.collect()
                yield 0.03
            _memlog("race code imported")
        if self.view is None:
            self.view = RW.RaceView()          # persistent: reused by every race
            self.cam = Camera()
            yield 0.05
        if self.mem is None:
            gc.collect()
            mem = TrackMem()
            for _ in mem.alloc_steps():        # map bands + track arrays, once
                yield 0.06
            self.mem = mem
        if self.pool is None:
            pool = []                          # nine cars, each with sprite buffer + palette
            for i in range(9):
                c = Car(CARS[0], i)
                c.spr = bytearray(A.FRAME_BYTES)
                c.spr_a = uctypes.addressof(c.spr)
                c.pal = A.new_car_pal()
                pool.append(c)
            self.pool = pool
            gc.collect()
            _memlog("buffers allocated")
            yield 0.08
        self.trk = Track(self.tidx, self.mem)
        for p in self.trk.build_steps():
            yield 0.10 + 0.90 * p
        _memlog("track built")

    def _load_update(self):
        try:
            self.load_p = next(self.gen)
        except StopIteration:
            self.gen = None
            gc.collect()
            self.view.set_track(self.trk)
            self.menu.clear()
            self._setup_cars()
            return
        if (self.tick & 1) == 0:
            self._page()

    def _setup_cars(self):
        """Create the grid from the car pool (also used by RESTART: the track stays built)."""
        trk = self.trk
        d = trk.d
        n_ai = d.n_ai
        pool = self.pool
        specs = OP.pick_specs(n_ai, d.pool)
        pspec = CARS[self.car_sel]
        colors = [c for c in _AI_COLORS if c != pspec.body]
        cars = []
        drivers = []
        for s in range(n_ai):
            sp = CARS[specs[s]]
            c = pool[s]
            c.assign(sp, s, False)
            x, y, h, k = trk.grid(s)
            c.reset(x, y, h)
            PR.init_car(c, trk, k)
            A.fill_car_pal(c.pal, colors[s % len(colors)], S.rgb(30, 30, 40))
            cars.append(c)
            drivers.append(OP.Driver(c, trk, random.uniform(d.skill[0], d.skill[1]),
                                     0.012 + 0.012 * self.tidx))
        pl = pool[n_ai]
        pl.assign(pspec, n_ai, True)
        x, y, h, k = trk.grid(n_ai)
        pl.reset(x, y, h)
        PR.init_car(pl, trk, k)
        A.fill_car_pal(pl.pal, pspec.body, pspec.accent)
        cars.append(pl)                     # player last = drawn on top
        self.cars = cars
        self.live = list(cars)
        self.ai = drivers
        self.player = pl
        self.pdrv = OP.Driver(pl, trk, 0.85, 0.0)
        self.order = list(reversed(cars))
        self.cam.snap(pl)
        self.race_ms = 0.0
        self.count_t = S.COUNTDOWN
        self.last_n = 0
        self.go_t = 0.0
        self.fin_t = 0.0
        self.finished_n = 0
        self.wrong_t = 0.0
        self.result = None
        self.view.set_overlay(None)
        self.state = COUNT
        self._cam_and_view(dt=1.0 / 30.0)

    def _count_update(self, dt):
        ctx = self.ctx
        self.count_t -= dt
        n = int(self.count_t) + 1
        if n > 3:
            n = 3
        if self.count_t <= 0.0:
            self.state = RACE
            self.go_t = 0.9
            ctx.audio.beep(*A.SFX_GO)
            ctx.led.flash(20, 200, 20, 300)
        elif n != self.last_n:
            self.last_n = n
            ctx.audio.beep(*A.SFX_TICK)
        self._cam_and_view(dt)

    # ---------------- the race itself ----------------
    def _race_update(self, dt, inp):
        ctx = self.ctx
        if dt > 0.1:
            dt = 0.1
        real_dt = dt
        pl = self.player
        trk = self.trk
        cars = self.cars
        st = self.state

        if st == RACE and not pl.finished and (inp.pressed_mask & BTN_Y):
            ctx.pause()                     # system pause menu: RESUME / RESTART / QUIT
            return
        if st == RESULT and (inp.pressed_mask & BTN_A):
            ctx.audio.beep(*A.SFX_CLICK)
            nxt = min(self.tidx + 1, len(TRACKS) - 1)
            go_next = (self.result is not None and self.result.podium and
                       SV.track_unlocked(ctx.save, nxt))
            self._free_race()
            self._refresh_save()
            self.state = TRACKS_ST
            self.tsel = nxt if go_next else self.tidx
            self._page()
            return

        # ---- player input (switches + stick) ----
        if not pl.finished:
            pl.steer = self._steer_input(inp)
            pl.throttle = bool(inp.held_mask & BTN_A)
            pl.brake = bool(inp.held_mask & BTN_B)
            if inp.pressed_mask & BTN_X:
                if pl.nitro_meter >= 0.999 and not pl.nitro_on:
                    pl.nitro_req = True
                else:
                    ctx.audio.beep(*A.SFX_NO)
            if pl.throttle and pl.spd < 8.0 and not pl.nitro_on:
                pl.stuck += dt
                if pl.stuck > 2.5:
                    self.pdrv.recover()
            else:
                pl.stuck = 0.0

        t = self.tick
        ref = pl.prog
        every = S.AI_EVERY

        # ---- level of detail: far rivals drive on rails, near ones get full physics ----
        px = pl.x
        py = pl.y
        ai = self.ai
        changed = False
        for k in range(len(ai)):
            if ((t + k) % 3) != 0:
                continue
            d = ai[k]
            c = d.car
            dx = c.x - px
            dy = c.y - py
            d2 = dx * dx + dy * dy
            if c.rail:
                if d2 < _LOD_WAKE and not c.finished:
                    d.wake()
                    changed = True
            elif d2 > _LOD_SLEEP or c.finished:
                d.sleep()
                changed = True
        if changed:
            self.live = [c for c in cars if not c.rail]
        live = self.live

        # ---- AI (throttled, staggered) ----
        for k in range(len(ai)):
            d = ai[k]
            if not d.car.rail and ((t + k) % every) == 0:
                d.think(live, ref, every * dt)
        if pl.finished and (t % every) == 0:
            self.pdrv.think(live, ref, every * dt)

        # ---- physics (awake cars only); a long frame is split in two for stability ----
        sub = 2 if dt > 0.045 else 1
        sdt = dt / sub
        for _ in range(sub):
            for c in live:
                PH.step_car(c, sdt, trk)
            PH.collide_cars(live)
            for c in live:
                PH.resolve_walls(c, trk)

        # ---- progress / laps / finish ----
        self.race_ms += real_dt * 1000.0
        now = int(self.race_ms)
        for c in cars:
            if c.rail:
                continue
            self._progress(c, PR.update(c, trk), now, pl)
        for d in ai:
            if d.car.rail:
                self._progress(d.car, d.rails(ref, dt), now, pl)

        # ---- feedback events ----
        if pl.nitro_fired:
            ctx.audio.beep(*A.SFX_NITRO)
            ctx.led.flash(40, 120, 255, 500)
        if pl.nitro_ended:
            ctx.audio.beep(*A.SFX_NITRO_END)
        self.bump_cd -= dt
        if pl.bump > 35.0 and self.bump_cd <= 0.0:
            ctx.audio.beep(*A.SFX_BUMP)
            self.bump_cd = 0.25
        for c in live:
            c.nitro_fired = False
            c.nitro_ended = False
            c.bump = 0.0

        if (t & 3) == 0:
            self.order = PR.ranking(cars)
        if not pl.finished:
            if PR.wrong_way(pl, trk):
                self.wrong_t += dt
            else:
                self.wrong_t = 0.0
        if self.go_t > 0.0:
            self.go_t -= dt

        if pl.finished and st == RACE:
            self.fin_t += dt
            if self.fin_t >= S.FINISH_DELAY:
                self._show_results()

        self._cam_and_view(real_dt)

    def _progress(self, c, ev, now, pl):
        if ev & PR.EV_LAP:
            lt = now - c.lap_start
            c.lap_start = now
            if c.best_lap == 0 or lt < c.best_lap:
                c.best_lap = lt
            if c is pl and not (ev & PR.EV_FINISH):
                self.ctx.audio.beep(*A.SFX_LAP)
                self.ctx.led.flash(20, 120, 20, 160)
        if (ev & PR.EV_FINISH) and not c.finished:
            self.finished_n += 1
            c.finished = True
            c.place = self.finished_n
            c.finish_ms = now
            if c is pl:
                self._player_finished()

    def _player_finished(self):
        ctx = self.ctx
        pl = self.player
        self.result = PR.apply_result(ctx.save, self.tidx, pl.place, pl.finish_ms,
                                      pl.best_lap, len(TRACKS))
        self._refresh_save()
        ctx.audio.beep(*A.SFX_FINISH)
        ctx.led.flash(255, 200, 0, 600)
        pl.steer = 0.0
        pl.throttle = False
        pl.brake = False

    def _show_results(self):
        """Build the results box. With very little memory left the box is skipped (the
        FINISH banner stays and A still continues) instead of crashing."""
        r = self.result
        gc.collect()
        b = None
        for _ in (0, 1):
            try:
                b = self._results_box(r)
                break
            except MemoryError:
                b = None
                gc.collect()
        self.view.set_overlay(b)
        self.state = RESULT
        self.flush_pending = True

    def _results_box(self, r):
        w = 250
        h = 116
        b = Box((320 - w) >> 1, 56, w, h)
        b.rect(0, 0, w, h, P16(S.YELLOW if r.podium else S.GREY))
        b.rect(4, 4, w - 8, h - 8, P16(S.PANEL))
        lines = [("RACE FINISHED", 2, S.YELLOW, 8),
                 ("POSITION  " + _ord(r.place), 2, S.WHITE, 28),
                 ("PRIZE  " + _money(r.prize) + " CASH", 2, S.GREEN, 48)]
        if r.unlocked >= 0:
            lines.append(("TRACK %d UNLOCKED!" % (r.unlocked + 1), 1, S.CYAN, 70))
        elif r.last_track:
            lines.append(("ALL TRACKS COMPLETE!", 1, S.CYAN, 70))
        elif not r.podium:
            lines.append(("TOP 3 NEEDED TO UNLOCK", 1, S.GREY, 70))
        lines.append(("TIME " + _ms(r.race_ms) + ("  NEW BEST!" if r.new_best else ""), 1,
                      S.ORANGE if r.new_best else S.WHITE, 84))
        lines.append(("A CONTINUE", 1, S.GREY, 100))
        for s, sc, col, y in lines:
            t = Text(s, sc)
            b.text((w - t.w) >> 1, y, t, P16(col))
        return b

    def _cam_and_view(self, dt=1.0 / 30.0):
        t0 = time.ticks_us() if S.PROFILE else 0
        pl = self.player
        self.cam.update(pl, dt)
        trk = self.trk
        N = trk.nw
        kmh = int((pl.spd if pl.spd > 0.0 else -pl.spd) * S.KMH)
        kmh = (kmh >> 1) << 1
        lap = pl.total // N + 1
        if lap < 1:
            lap = 1
        elif lap > trk.laps:
            lap = trk.laps
        place = 1
        for i in range(len(self.order)):
            if self.order[i] is pl:
                place = i + 1
                break
        if self.state == COUNT:
            n = int(self.count_t) + 1
            banner = 4 - (n if n <= 3 else 3)
        elif self.go_t > 0.0:
            banner = 4
        elif pl.finished:
            banner = 6
        elif self.wrong_t > 0.6 and (self.tick >> 3) & 1:
            banner = 5
        else:
            banner = 0
        if pl.nitro_on:
            ns = 2
        elif pl.nitro_meter >= 0.999:
            ns = 1
        else:
            ns = 0
        self.view.hud.update(place, len(self.cars), lap, trk.laps, kmh,
                             int(self.race_ms) if self.state != COUNT else 0, banner, ns)
        self.view.prepare(self.cam, self.cars, self.art, pl.nitro_meter, pl.nitro_on, self.tick)
        if S.PROFILE:
            self.prof[1] += time.ticks_diff(time.ticks_us(), t0)

    # ------------------------------------------------------------
    def draw(self, r):
        if self.released:
            kick = r.kick
            base = r.base
            ca = r.cover_addr
            y = 0
            while y < 240:                      # plain background while the scene fades out
                kick(base, ca)
                y += 1
            return
        if self.state >= COUNT:
            t0 = time.ticks_us() if S.PROFILE else 0
            self.view.draw(r)
            if S.PROFILE:
                self.prof[2] += time.ticks_diff(time.ticks_us(), t0)
            # Float maths leaves garbage every frame. Collect it here, while the last rows are
            # still streaming, and only if the frame is ahead of schedule: a short predictable
            # pause instead of a random long one in the middle of the next frame.
            if (gc.mem_free() < S.GC_FREE and
                    time.ticks_diff(time.ticks_us(), self.t_frame) < S.GC_SLACK_US):
                t1 = time.ticks_us() if S.PROFILE else 0
                gc.collect()
                if S.PROFILE:
                    self.prof[3] += time.ticks_diff(time.ticks_us(), t1)
            if S.PROFILE:
                p = self.prof
                p[4] += 1
                if p[4] >= 60:
                    n = p[4]
                    print("racer us/frame: update", p[0] // n, "prepare", p[1] // n,
                          "draw", p[2] // n, "gc", p[3] // n, "free", gc.mem_free())
                    self.prof = [0, 0, 0, 0, 0]
        else:
            self.menu.draw(r)
        # The console is switching scenes (QUIT from the pause menu, EXIT...): hand every big
        # buffer back NOW, during the fade-out, so its loading screen has memory to work with.
        if getattr(self.ctx.sm, "next_factory", None) is not None:
            self._release_all()

    def _release_all(self):
        self.released = True
        self.cars = []
        self.live = []
        self.ai = []
        self.player = None
        self.pdrv = None
        self.trk = None
        self.gen = None
        self.result = None
        self.order = []
        self.art = self.menu = self.cam = self.view = self.mem = self.pool = None
        self.prev_pal = None
        gc.collect()


_LOD_WAKE = S.LOD_R * S.LOD_R * 0.64
_LOD_SLEEP = S.LOD_R * S.LOD_R * 1.56
