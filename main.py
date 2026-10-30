# ============================================================
# PIXEL FORGE - entry point
#
# Boot order is chosen so the FPGA's ~700 ms LCD initialisation
# overlaps with importing modules and building the boot assets.
# ============================================================
import gc, sys, time
gc.collect()
import config
from hardware.display import Display


class Context:
    """Shared services handed to every scene."""
    disp = r = inp = led = audio = save = sm = None
    menu_factory = None

    def home(self):
        """Back to the main menu (used by games)."""
        self.sm.goto(self.menu_factory, "fade", ("LEAVING GAME", "SAVING PROGRESS"))

    def pause(self):
        """Open the pause menu (RESUME / RESTART / QUIT)."""
        self.sm.pause()

    def shutdown(self):
        """Save, show SHUTTING DOWN, turn the LCD white, then exit the program."""
        self.sm.shutdown()


def _boot_factory(ctx, menu_cls):
    def make():
        from system.boot import BootScene          # imported here so it can be unloaded later
        return BootScene(ctx, menu_cls)
    return make


def main():
    disp = Display()
    disp.start()            # flash FPGA + start PIO/DMA; the FPGA boots in the background

    from hardware.input import Input
    from hardware.led import RGBLed
    from hardware.audio import Audio
    from system.renderer import Renderer
    from system.save_manager import SaveManager
    from system.scene_manager import SceneManager
    from system.menu import MenuScene

    ctx = Context()
    ctx.disp = disp
    ctx.r = Renderer(disp)
    ctx.inp = Input()
    ctx.led = RGBLed()
    ctx.audio = Audio()
    ctx.save = SaveManager()
    ctx.menu_factory = lambda: MenuScene(ctx)
    ctx.sm = SceneManager(ctx, MenuScene)

    ctx.sm.start(_boot_factory(ctx, MenuScene))        # builds the boot art
    gc.collect()
    disp.wait_ready()                                  # usually already ready
    ctx.sm.run()                                       # returns after a shutdown

    # ---- powered down: white LCD is already on screen ----
    ctx.audio.off()
    ctx.led.off()
    ctx.led.update()
    disp.stop()
    print("Pixel Forge: shut down")


try:
    main()
except KeyboardInterrupt:
    raise
except Exception as e:
    sys.print_exception(e)
    try:
        from hardware.led import RGBLed
        led = RGBLed()
        led.set_base(255, 0, 0)
        led.update()
    except Exception:
        pass
