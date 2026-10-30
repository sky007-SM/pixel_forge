# ============================================================
# Scene manager + the 30 fps main loop
#
# A scene implements:
#   steps(ctx)        generator that builds its assets in small chunks (default:
#                     calls enter()); lets the loading screen keep spinning
#   update(dt, inp)   game logic, once per frame
#   draw(r)           must emit exactly 240 rows via r.kick (see renderer.py)
#   exit()            save + drop references so memory can be reclaimed
#   restart()         optional: used by the pause menu's RESTART
#
# Changing scene:  ctx.sm.goto(factory, "fade", ("LOADING", "FLAPPY BIRD"))
#   fade out -> loading screen (old scene exits, new one is built) -> fade in
# With load=None the swap happens while the screen is black (boot -> menu).
# ctx.sm.shutdown(): fade out -> "SHUTTING DOWN" screen (saves, closes the scene) ->
# fade -> full white LCD -> run() returns and main.py closes everything.
# ============================================================
import gc, sys, time
import uctypes
import config
from hardware.display import dma_wait
from system.renderer import make_row
from system import transitions
from system.loading import LoadingScreen
from system.pause import PauseMenu, RESUME, RESTART, QUIT

_IDLE = 0
_OUT = 1
_LOAD = 2
_IN = 3
_OFF = 4                # shutdown: white screen, then run() returns
_MIN_LOAD = 24          # loading screen stays at least 0.8 s (30 fps)
_MIN_SHUTDOWN = 42


def _purge(names):
    """Unload modules (and their children) so their code can be garbage collected."""
    for name in names:
        for k in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
            del sys.modules[k]
        parent = name.rpartition(".")[0]
        pm = sys.modules.get(parent) if parent else None
        if pm is not None:
            try:
                pm.__dict__.pop(name.rpartition(".")[2], None)
            except Exception:
                pass


class Scene:
    PURGE = ()               # module names to unload when the scene exits

    def enter(self, ctx):
        self.ctx = ctx

    def steps(self, ctx):
        self.enter(ctx)
        yield

    def update(self, dt, inp):
        pass

    def draw(self, r):
        raise NotImplementedError

    def exit(self):
        pass


class SceneManager:
    def __init__(self, ctx, fallback):
        self.ctx = ctx
        self.fallback = fallback        # scene class used if a scene fails to load
        self.scene = None
        self.phase = _IDLE
        self.tr = None
        self.i = 0
        self.next_factory = None
        self.kind = "fade"
        self.load_info = None
        self.loader = None
        self.gen = None
        self.load_f = 0
        self.leave_f = 0
        self.pause_menu = PauseMenu(ctx.audio)
        self.shutting = False
        self.min_load = _MIN_LOAD
        self.running = True
        self.off_f = 0
        self.white = make_row(0xFFFF)
        self.white_addr = uctypes.addressof(self.white)

    def start(self, factory):
        for attempt in (0, 1):
            try:
                sc = factory()
                for _ in sc.steps(self.ctx):
                    pass
                self.scene = sc
                return
            except MemoryError:
                sc = None
                gc.collect()
                if attempt:
                    raise

    def goto(self, factory, kind="fade", load=None):
        if self.phase == _IDLE and self.next_factory is None:
            self.next_factory = factory
            self.kind = kind
            self.load_info = load
            self.min_load = _MIN_LOAD

    def shutdown(self):
        """Close the console: save, show the shutting-down screen, then white LCD and exit."""
        if self.phase == _IDLE and self.next_factory is None:
            self.next_factory = True
            self.kind = "fade"
            self.load_info = ("SHUTTING DOWN", "SAVING AND CLOSING")
            self.min_load = _MIN_SHUTDOWN
            self.shutting = True

    def pause(self):
        if self.phase == _IDLE and not self.pause_menu.active:
            self.pause_menu.open()

    # ---- tear down the old scene and build the new one (generator: one step per frame) ----
    def _load_gen(self):
        ctx = self.ctx
        old = self.scene
        self.scene = None
        yield
        purge = old.PURGE
        try:
            old.exit()
        except Exception as e:
            sys.print_exception(e)
        old = None
        _purge(purge)                                   # drop the old scene's code too
        gc.collect()
        yield
        if self.shutting:
            ctx.audio.stop_music()
            ctx.audio.music("shutdown", False)         # after exit(), which stops the old scene's music
            try:
                ctx.save.flush()
            except Exception as e:
                sys.print_exception(e)
            ctx.led.off()
            self.next_factory = None
            return
        new = None
        for attempt in (0, 1):
            try:
                new = self.next_factory()              # imports the game module
                yield
                for _ in new.steps(ctx):
                    if gc.mem_free() < 60000:
                        gc.collect()                   # keep the heap tidy between build steps
                    yield
                break
            except MemoryError:
                new = None
                gc.collect()                           # one more try with a clean heap
                yield
            except Exception as e:
                sys.print_exception(e)
                new = None
                break
        if new is None:
            gc.collect()
            new = self.fallback(ctx)
            for _ in new.steps(ctx):
                yield
        self.next_factory = None
        gc.collect()
        self.scene = new
        if config.DEBUG_MEM:
            print("scene", type(new).__name__, "built; free heap", gc.mem_free())

    def _tick(self, dt):
        """One logic step. Returns True when frame timing should be re-synced."""
        ctx = self.ctx
        r = ctx.r
        ph = self.phase

        if ph == _IDLE:
            pm = self.pause_menu
            if pm.active:
                act = pm.update(ctx.inp)
                if act == RESUME:
                    pm.close()
                elif act == RESTART:
                    pm.close()
                    fn = getattr(self.scene, "restart", None)
                    if fn:
                        fn()
                elif act == QUIT:
                    pm.close()
                    ctx.home()
            else:
                self.scene.update(dt, ctx.inp)
            if self.next_factory is not None:
                pm.close()
                self.tr = transitions.make(self.kind)
                self.tr.begin(r)
                self.i = 0
                self.phase = _OUT
            return False

        if ph == _OUT:
            self.i += 1
            n = self.tr.frames
            self.tr.apply(r, self.i / n)
            if self.i >= n:
                if self.load_info is not None:
                    self.loader = LoadingScreen(self.load_info[0], self.load_info[1])
                    self.gen = self._load_gen()
                    self.load_f = 0
                    self.leave_f = 0
                    self.phase = _LOAD
                    r.set_fx(4)
                else:
                    for _ in self._load_gen():  # screen is black: build in one go
                        pass
                    self.i = 0
                    self.phase = _IN
                return True
            return False

        if ph == _LOAD:
            self.load_f += 1
            if self.gen is not None:
                try:
                    next(self.gen)
                except StopIteration:
                    self.gen = None
            self.loader.update()
            if self.gen is None and self.load_f >= self.min_load:
                self.leave_f += 1                   # fade the loading screen out
                lvl = self.leave_f
                if lvl > 4:
                    self.loader = None
                    self.i = 0
                    if self.shutting:
                        r.set_fx(0)
                        self.off_f = 0
                        self.phase = _OFF
                    else:
                        self.phase = _IN
                        r.set_fx(4)
                else:
                    r.set_fx(lvl)
            else:
                lvl = 4 - self.load_f              # fade the loading screen in
                r.set_fx(lvl if lvl > 0 else 0)
            return True

        if ph == _OFF:
            self.off_f += 1
            if self.off_f >= 4:               # a few white frames, then leave the loop
                self.running = False
            return False

        # _IN
        self.scene.update(dt, ctx.inp)
        self.i += 1
        n = self.tr.frames
        self.tr.apply(r, 1.0 - self.i / n)
        if self.i >= n:
            self.tr.end(r)
            self.phase = _IDLE
        return False

    def _draw(self):
        """Stream one frame: loading screen, paused game (dimmed + overlay) or the scene."""
        r = self.ctx.r
        r.begin_frame()
        ph = self.phase
        if ph == _OFF:
            kick = r.kick
            base = r.base
            wa = self.white_addr
            for y in range(240):
                kick(base, wa)
        elif ph == _LOAD:
            self.loader.draw(r)
        elif ph == _IDLE and self.pause_menu.active:
            pm = self.pause_menu
            r.set_fx(1, pm.box)                    # dim the frozen game, overlay on top
            self.scene.draw(r)
            r.set_fx(0)
        else:
            self.scene.draw(r)

    def run(self):
        ctx = self.ctx
        r = ctx.r
        base = r.base
        frame_us = 1000000 // config.TARGET_FPS
        fixed_dt = 1.0 / config.TARGET_FPS
        last = time.ticks_us()
        frames = 0
        fps_t = time.ticks_ms()
        fps_n = 0
        while self.running:
            t0 = time.ticks_us()
            dma_wait(base)
            dt_us = time.ticks_diff(t0, last)
            last = t0
            # frames are paced, so snap near-30fps timing to a fixed dt: smoother motion
            if dt_us - frame_us < 5000 and frame_us - dt_us < 5000:
                dt = fixed_dt
            else:
                dt = dt_us / 1000000.0
                if dt > 0.1:
                    dt = 0.1
            ctx.inp.update()
            ctx.led.update()
            ctx.audio.update()
            if self._tick(dt):
                last = time.ticks_us()
                t0 = last
            time.sleep_us(60)           # lets the FPGA finish its address-window commands

            self._draw()

            frames += 1
            if (frames & 15) == 0 and gc.mem_free() < config.GC_LOW_WATER:
                gc.collect()
            if config.DEBUG_FPS:
                fps_n += 1
                now = time.ticks_ms()
                if time.ticks_diff(now, fps_t) >= 1000:
                    print("FPS", fps_n, "free", gc.mem_free())
                    fps_n = 0
                    fps_t = now

            dma_wait(base)
            rest = frame_us - time.ticks_diff(time.ticks_us(), t0)
            if rest > 0:
                time.sleep_us(rest)
        dma_wait(base)                    # let the last (white) row reach the FPGA and LCD
        time.sleep_ms(60)
