# ============================================================
# RGB LED (PWM). Steady base colour + short decaying flashes.
# update() once per frame; it only touches the PWM when needed.
# ============================================================
import time
from machine import Pin, PWM
import config


class RGBLed:
    def __init__(self):
        self._low = config.RGB_LED_ACTIVE_LOW
        self._pwm = []
        for p in (config.RGB_LED_R_PIN, config.RGB_LED_G_PIN, config.RGB_LED_B_PIN):
            pw = PWM(Pin(p))
            pw.freq(1000)
            self._pwm.append(pw)
        self._base = (0, 0, 0)
        self._fl = (0, 0, 0)
        self._fl_t0 = 0
        self._fl_ms = 0
        self._cur = (-1, -1, -1)
        self.enabled = True
        self.update()

    def set_base(self, r, g, b):
        self._base = (r, g, b)

    def flash(self, r, g, b, ms=250):
        self._fl = (r, g, b)
        self._fl_t0 = time.ticks_ms()
        self._fl_ms = ms

    def off(self):
        self._base = (0, 0, 0)
        self._fl_ms = 0

    def update(self):
        br, bg, bb = self._base
        if self._fl_ms:
            e = time.ticks_diff(time.ticks_ms(), self._fl_t0)
            if e >= self._fl_ms:
                self._fl_ms = 0
            else:
                k = 256 - (e << 8) // self._fl_ms
                fr, fg, fb = self._fl
                br = max(br, (fr * k) >> 8)
                bg = max(bg, (fg * k) >> 8)
                bb = max(bb, (fb * k) >> 8)
        if not self.enabled:
            br = bg = bb = 0
        cur = (br, bg, bb)
        if cur != self._cur:
            self._cur = cur
            for pw, v in zip(self._pwm, cur):
                d = v * 257
                pw.duty_u16(65535 - d if self._low else d)
