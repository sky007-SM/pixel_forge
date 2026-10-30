# ============================================================
# Pause menu: small rounded overlay (RESUME / RESTART / QUIT) drawn over
# the dimmed game. The game is frozen, not unloaded. Opened with
# ctx.sm.pause(); the scene manager feeds it input and draws it.
# Drawn from rectangles + 1-bit text: no pixel buffer is kept.
# ============================================================
import config
from config import rgb
from hardware.display import P16
from hardware.input import BTN_A, BTN_B, BTN_Y, BTN_SW
from system.dialog import Box
from assets.fonts import Text
from assets.logo import EMBER_ROWS

W = 152
H = 124
RESUME = 1
RESTART = 2
QUIT = 3
_OPTS = ("RESUME", "RESTART", "QUIT")


class PauseMenu:
    def __init__(self, audio=None):
        self.audio = audio
        self.active = False
        self.sel = 0
        self.box = Box((320 - W) // 2, (240 - H) // 2, W, H)
        c = config
        self.head = Text("PAUSED", 2)
        self.opts = [Text(t, 2) for t in _OPTS]
        self.hint = Text("A SELECT    Y BACK", 1)
        self.c_head = [P16(x) for x in EMBER_ROWS]
        self.c_edge = P16(c.C_EMBER)
        self.c_body = P16(rgb(14, 16, 30))
        self.c_band = P16(rgb(34, 20, 16))
        self.c_line = P16(c.C_EMBER_DARK)
        self.c_bar = P16(c.C_PANEL_HI)
        self.c_on = P16(c.C_TEXT)
        self.c_off = P16(c.C_TEXT_DIM)
        self._build()

    def open(self):
        self.active = True
        self.sel = 0
        self._build()
        if self.audio:
            self.audio.sfx("pause")

    def close(self):
        self.active = False

    def _build(self):
        b = self.box
        b.clear()
        b.rrect(0, 0, W, H, self.c_edge)
        b.rrect(2, 2, W - 4, H - 4, self.c_body)
        b.rect(4, 4, W - 8, 24, self.c_band)
        b.rect(4, 28, W - 8, 2, self.c_line)
        b.text((W - self.head.w) // 2, 9, self.head, 0, self.c_head)
        for i in range(3):
            y = 36 + i * 24
            if i == self.sel:
                b.rect(8, y, W - 16, 20, self.c_bar)
                b.rect(8, y, 3, 20, self.c_edge)
                b.text(22, y + 3, self.opts[i], self.c_on)
            else:
                b.text(22, y + 3, self.opts[i], self.c_off)
        b.text((W - self.hint.w) // 2, H - 14, self.hint, self.c_off)

    def update(self, inp):
        """Returns 0 (nothing), RESUME, RESTART or QUIT."""
        au = self.audio
        if inp.nav_y:
            self.sel = (self.sel + inp.nav_y) % 3
            self._build()
            if au:
                au.sfx("move")
        pm = inp.pressed_mask
        if pm & (BTN_Y | BTN_B):
            if au:
                au.sfx("back")
            return RESUME
        if pm & (BTN_A | BTN_SW):
            if au:
                au.sfx("select")
            return (RESUME, RESTART, QUIT)[self.sel]
        return 0
