# ============================================================
# Chase camera: follows the car's HEADING (not the world axes).
#
# The camera looks along its heading `ha` ("up" on screen = forward).
# ha eases towards the car heading, so the view swings smoothly through
# corners instead of snapping. The view centre sits ahead of the car by
# a speed dependent look-ahead, which pushes the car to the lower part
# of the screen at speed. HUD is drawn in screen space, so it stays upright.
# ============================================================
import math
from games.racer import settings as S

_PI = math.pi
_TWO_PI = 2.0 * math.pi


class Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.ha = 0.0
        self.lead = 0.0
        self._trig()

    def _trig(self):
        self.fx = math.cos(self.ha)      # screen-up direction in the world
        self.fy = math.sin(self.ha)
        self.rx = -self.fy               # screen-right direction in the world
        self.ry = self.fx

    def snap(self, car):
        self.ha = car.hd
        self.lead = 0.0
        self._trig()
        self.x = car.x
        self.y = car.y

    def update(self, car, dt):
        d = car.hd - self.ha
        while d > _PI:
            d -= _TWO_PI
        while d < -_PI:
            d += _TWO_PI
        k = S.CAM_TURN_K
        spd = car.spd if car.spd >= 0.0 else -car.spd
        if spd < 30.0:                   # nearly stopped: don't spin the view
            k *= 0.4 + spd * 0.02
        step = d * k * dt
        mx = S.CAM_MAX_YAW * dt
        if step > mx:
            step = mx
        elif step < -mx:
            step = -mx
        self.ha += step
        if self.ha > _PI:
            self.ha -= _TWO_PI
        elif self.ha < -_PI:
            self.ha += _TWO_PI
        self._trig()
        want = car.spd * S.CAM_LEAD_K
        if want < 0.0:
            want = 0.0
        elif want > S.CAM_LEAD_MAX:
            want = S.CAM_LEAD_MAX
        a = 3.0 * dt
        if a > 1.0:
            a = 1.0
        self.lead += (want - self.lead) * a
        self.x = car.x + self.fx * self.lead
        self.y = car.y + self.fy * self.lead

    def to_screen(self, wx, wy):
        dx = wx - self.x
        dy = wy - self.y
        return (160.0 + dx * self.rx + dy * self.ry,
                S.CAM_ANCHOR_Y - (dx * self.fx + dy * self.fy))
