# ============================================================
# Buttons (A/B/X/Y), joystick (2x ADC + switch)
#
# Call update() once per frame. Press events are also latched by
# GPIO interrupts, so a tap shorter than one frame is never lost.
# ============================================================
import time, array
from machine import Pin, ADC
import config

BTN_A = 1
BTN_B = 2
BTN_X = 4
BTN_Y = 8
BTN_SW = 16          # joystick push
DIR_L = 32
DIR_R = 64
DIR_U = 128
DIR_D = 256

_ON = 600            # stick -> digital direction thresholds (of +-1000)
_OFF = 400
_REP_FIRST = 320     # menu auto-repeat (ms)
_REP_NEXT = 110


class Input:
    def __init__(self):
        low_b = config.BUTTON_ACTIVE_LOW
        low_s = config.JOYSTICK_ACTIVE_LOW
        pb = Pin.PULL_UP if low_b else Pin.PULL_DOWN
        ps = Pin.PULL_UP if low_s else Pin.PULL_DOWN
        self._pins = (
            Pin(config.BUTTON_A_PIN, Pin.IN, pb),
            Pin(config.BUTTON_B_PIN, Pin.IN, pb),
            Pin(config.BUTTON_X_PIN, Pin.IN, pb),
            Pin(config.BUTTON_Y_PIN, Pin.IN, pb),
            Pin(config.JOYSTICK_SW_PIN, Pin.IN, ps),
        )
        self._bits = (BTN_A, BTN_B, BTN_X, BTN_Y, BTN_SW)
        self._low = (low_b, low_b, low_b, low_b, low_s)
        self._state = [0, 0, 0, 0, 0]
        self._accept = array.array("i", [0] * 5)    # last accepted change (ms)
        self._lat = array.array("i", [0])           # IRQ-latched press bits
        self._lat_t = array.array("i", [0] * 5)
        for i in range(5):
            trig = Pin.IRQ_FALLING if self._low[i] else Pin.IRQ_RISING
            self._pins[i].irq(trigger=trig, handler=self._make_irq(i))

        self._ax = ADC(Pin(config.JOYSTICK_X_PIN))
        self._ay = ADC(Pin(config.JOYSTICK_Y_PIN))
        self._cx = 32768
        self._cy = 32768
        self.calibrate()

        self.held_mask = 0
        self.pressed_mask = 0
        self.released_mask = 0
        self.ax = 0          # -1000..1000
        self.ay = 0
        self.nav_x = 0       # -1/0/+1 events with auto-repeat (menus)
        self.nav_y = 0
        self._rep = [0, 0]
        self._rep_t = [0, 0]
        self._dirs = 0

    def _make_irq(self, i):
        bit = self._bits[i]
        lat = self._lat
        lt = self._lat_t
        deb = config.BUTTON_DEBOUNCE_MS

        def handler(pin):
            now = time.ticks_ms()
            if time.ticks_diff(now, lt[i]) >= deb:
                lat[0] |= bit
                lt[i] = now
        return handler

    def calibrate(self):
        sx = 0
        sy = 0
        for _ in range(16):
            sx += self._ax.read_u16()
            sy += self._ay.read_u16()
        self._cx = sx >> 4
        self._cy = sy >> 4

    @staticmethod
    def _axis(raw, center, invert):
        d = raw - center
        if invert:
            d = -d
        dz = config.JOYSTICK_DEADZONE
        if -dz < d < dz:
            return 0
        d = d - dz if d > 0 else d + dz
        v = d * 1000 // (32767 - dz)
        if v > 1000:
            return 1000
        if v < -1000:
            return -1000
        return v

    def update(self):
        now = time.ticks_ms()
        deb = config.BUTTON_DEBOUNCE_MS
        prev = self.held_mask
        held = 0
        st = self._state
        acc = self._accept
        for i in range(5):
            v = 1 if (self._pins[i].value() == 0) == self._low[i] else 0
            if v != st[i] and time.ticks_diff(now, acc[i]) >= deb:
                st[i] = v
                acc[i] = now
            if st[i]:
                held |= self._bits[i]

        lat = self._lat[0]
        self._lat[0] = 0
        pressed = (held & ~prev) | (lat & ~prev)

        # joystick axes -> digital directions (with hysteresis)
        ax = self._axis(self._ax.read_u16(), self._cx, config.JOYSTICK_INVERT_X)
        ay = self._axis(self._ay.read_u16(), self._cy, config.JOYSTICK_INVERT_Y)
        self.ax = ax
        self.ay = ay
        d = self._dirs
        d = self._hyst(d, DIR_R, ax > 0, ax)
        d = self._hyst(d, DIR_L, ax < 0, -ax)
        d = self._hyst(d, DIR_D, ay > 0, ay)
        d = self._hyst(d, DIR_U, ay < 0, -ay)
        dir_prev = self._dirs
        self._dirs = d
        held |= d
        pressed |= d & ~dir_prev

        self.pressed_mask = pressed
        self.released_mask = prev & ~held
        self.held_mask = held

        # menu navigation events with auto-repeat
        self.nav_x = self._nav(0, d & DIR_R, d & DIR_L, pressed & (DIR_R | DIR_L), now)
        self.nav_y = self._nav(1, d & DIR_D, d & DIR_U, pressed & (DIR_D | DIR_U), now)

    @staticmethod
    def _hyst(d, bit, positive, mag):
        if positive and mag >= _ON:
            return d | bit
        if (not positive) or mag < _OFF:
            return d & ~bit
        return d

    def _nav(self, k, plus, minus, fresh, now):
        s = 1 if plus else (-1 if minus else 0)
        if s == 0:
            self._rep[k] = 0
            return 0
        if fresh or self._rep[k] != s:
            self._rep[k] = s
            self._rep_t[k] = time.ticks_add(now, _REP_FIRST)
            return s
        if time.ticks_diff(now, self._rep_t[k]) >= 0:
            self._rep_t[k] = time.ticks_add(now, _REP_NEXT)
            return s
        return 0

    def pressed(self, mask):
        return (self.pressed_mask & mask) != 0

    def held(self, mask):
        return (self.held_mask & mask) != 0

    def released(self, mask):
        return (self.released_mask & mask) != 0
