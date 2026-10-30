# ============================================================
# PWM audio: one voice, music + sound effects, never blocks.
#
# A 100 Hz timer ticks a tiny sequencer (about 20 us per tick, and only
# touches the PWM when the note changes), so it costs the render loop
# nothing. GPIO22/23 share a PWM slice, so both pins play the same pitch.
# Sound effects take the voice over from the music; the music keeps
# counting silently underneath and carries on afterwards.
#
# Nothing is touched while AUDIO_ENABLED is False. Wire the amp/speaker,
# then set AUDIO_ENABLED = True in config.py.
#
# API (all calls return immediately):
#   music("menu", loop=True)   stop_music()   sfx("flap")   beep(freq, ms)
#   set_volume(0..4)           off()
# ============================================================
import random
import config
from assets import sounds

TICK_MS = 10
_VOL = (0, 5000, 12000, 21000, 32768)        # PWM duty out of 65535 (square wave)
_STOP = ()
FREQ = sounds.FREQ


class Audio:
    def __init__(self, hw=True):
        self.vol = config.AUDIO_VOLUME
        self.enabled = bool(config.AUDIO_ENABLED and self.vol > 0)
        self._m_req = None           # mailbox: written by the game, read by the tick
        self._s_req = None
        self.m_song = None
        self.m_i = 0
        self.m_left = 0
        self.m_freq = 0
        self.m_loop = False
        self.s_eff = None
        self.s_si = 0
        self.s_left = 0
        self.s_t = 0
        self.s_n = 1
        self.s_f0 = 0
        self.s_f1 = 0
        self.s_k = 0
        self.s_f = 0
        self.cur = 0
        self.pwm = None
        self.timer = None
        if self.enabled and hw:
            self._start_hw()

    # ---------------- hardware ----------------
    def _start_hw(self):
        from machine import Pin, PWM, Timer
        pw = []
        for p in (config.AUDIO_LEFT_PIN, config.AUDIO_RIGHT_PIN):
            w = PWM(Pin(p))
            w.freq(1000)
            w.duty_u16(0)
            pw.append(w)
        self.pwm = pw
        self.timer = Timer(-1)
        self.timer.init(period=TICK_MS, mode=Timer.PERIODIC, callback=self._cb)

    def _cb(self, t):
        self.tick()

    def _out(self, f):
        pw = self.pwm
        if pw is None:
            return
        if f <= 0:
            pw[0].duty_u16(0)
            pw[1].duty_u16(0)
        else:
            pw[0].freq(f)
            d = _VOL[self.vol]
            pw[0].duty_u16(d)
            pw[1].duty_u16(d)

    # ---------------- public API ----------------
    def music(self, name, loop=True):
        if self.enabled:
            self._m_req = (sounds.song(name), loop)

    def stop_music(self):
        if self.enabled:
            self._m_req = _STOP

    def sfx(self, name):
        if self.enabled:
            self._s_req = sounds.SFX[name]

    def beep(self, freq=880, ms=60):
        if self.enabled:
            t = ms // TICK_MS
            self._s_req = ((freq, freq, t if t > 0 else 1, 0),)

    def set_volume(self, v):
        self.vol = 0 if v < 0 else (4 if v > 4 else v)
        self.cur = -1                         # force the next tick to re-apply the duty

    def update(self):
        pass                                  # kept for the main loop; the timer does the work

    def off(self):
        self.enabled = False
        if self.timer is not None:
            self.timer.deinit()
            self.timer = None
        if self.pwm is not None:
            for w in self.pwm:
                w.duty_u16(0)
                w.deinit()
            self.pwm = None

    # ---------------- sequencer (runs every TICK_MS) ----------------
    def tick(self):
        req = self._m_req
        if req is not None:
            self._m_req = None
            if req == _STOP:
                self.m_song = None
                self.m_freq = 0
            else:
                self.m_song = req[0]
                self.m_loop = req[1]
                self.m_i = 0
                self.m_left = 0
                self.m_freq = 0
        req = self._s_req
        if req is not None:
            self._s_req = None
            self.s_eff = req
            self.s_si = 0
            self.s_left = 0

        song = self.m_song
        if song is not None:
            self.m_left -= 1
            if self.m_left <= 0:
                i = self.m_i
                if i >= len(song):
                    if self.m_loop:
                        i = 0
                    else:
                        self.m_song = None
                        self.m_freq = 0
                        i = -1
                if i >= 0:
                    self.m_freq = FREQ[song[i]]
                    self.m_left = song[i + 1]
                    self.m_i = i + 2

        eff = self.s_eff
        if eff is not None:
            if self.s_left <= 0:
                if self.s_si >= len(eff):
                    self.s_eff = None
                    self.s_f = 0
                    eff = None
                else:
                    seg = eff[self.s_si]
                    self.s_si += 1
                    self.s_f0 = seg[0]
                    self.s_f1 = seg[1]
                    self.s_n = seg[2]
                    self.s_left = seg[2]
                    self.s_k = seg[3]
                    self.s_t = 0
            if eff is not None:
                k = self.s_k
                if k == 0:
                    f = self.s_f0 + (self.s_f1 - self.s_f0) * self.s_t // self.s_n
                elif k == 1:
                    f = self.s_f0 + random.getrandbits(12) % (self.s_f1 - self.s_f0 + 1)
                else:
                    f = 0
                self.s_f = f
                self.s_t += 1
                self.s_left -= 1

        if self.s_eff is not None:
            f = self.s_f
        else:
            f = self.m_freq
        if f != self.cur:
            self.cur = f
            self._out(f)
