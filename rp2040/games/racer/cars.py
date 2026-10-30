# ============================================================
# Cars: the six car definitions + the per-race car state (cars are pooled:
# the scene creates nine once and re-assigns them every race)
# ============================================================
import math
from games.racer import settings as S
from games.racer.settings import rgb


class CarSpec:
    """Static handling profile of one car model.

    accel  units/s^2 at standstill (falls off towards vmax)
    vmax   top speed in units/s
    turn   max yaw rate in rad/s
    grip   how fast sideways velocity is killed (1/s) - low = slidey
    brake  deceleration under braking
    nitro  nitro power multiplier (boost strength)
    mass   collision weight
    """

    def __init__(self, name, price, accel, vmax, turn, grip, brake, nitro,
                 mass, body, accent, blurb):
        self.name = name
        self.price = price
        self.accel = accel
        self.vmax = vmax
        self.turn = turn
        self.grip = grip
        self.brake = brake
        self.nitro = nitro
        self.mass = mass
        self.body = body
        self.accent = accent
        self.blurb = blurb


CARS = (
    CarSpec("ROOKIE", 0,
            170.0, 168.0, 2.50, 6.5, 260.0, 1.00, 1.0,
            rgb(60, 120, 255), rgb(240, 240, 255),
            "BALANCED AND EASY"),
    CarSpec("SWIFT", 1200,
            235.0, 152.0, 2.70, 7.0, 285.0, 0.90, 0.9,
            rgb(255, 205, 30), rgb(40, 40, 50),
            "QUICK OUT OF CORNERS"),
    CarSpec("DRIFTER", 1800,
            175.0, 174.0, 3.20, 3.0, 255.0, 1.00, 0.9,
            rgb(170, 70, 230), rgb(255, 140, 220),
            "LOOSE, SLIDES EASILY"),
    CarSpec("BRUISER", 2600,
            225.0, 182.0, 1.90, 6.0, 235.0, 1.00, 1.7,
            rgb(230, 70, 40), rgb(255, 200, 60),
            "HEAVY, HOLDS SPEED"),
    CarSpec("PHANTOM", 3800,
            165.0, 206.0, 2.20, 5.5, 255.0, 1.65,  1.0,
            rgb(60, 70, 90), rgb(60, 230, 255),
            "TOP SPEED, MEAN NITRO"),
    CarSpec("APEX", 6500,
            245.0, 224.0, 2.95, 8.5, 320.0, 1.45, 1.1,
            rgb(250, 250, 250), rgb(255, 190, 30),
            "THE ULTIMATE MACHINE"),
)

# normalisation maxima for the garage stat bars
STAT_MAX = (250.0, 230.0, 3.3, 9.0, 1.7)         # accel, vmax, turn, grip, nitro
STAT_NAMES = ("ACCEL", "SPEED", "TURN", "GRIP", "NITRO")


def stats_of(sp):
    """0..1 fractions in STAT_NAMES order."""
    v = (sp.accel, sp.vmax, sp.turn, sp.grip, sp.nitro)
    out = []
    for i in range(5):
        f = v[i] / STAT_MAX[i]
        out.append(1.0 if f > 1.0 else f)
    return out


class Car:
    """Everything that changes during a race for one car."""

    def __init__(self, spec, slot, is_player=False):
        self.spec = spec
        self.slot = slot
        self.is_player = is_player
        self.pal = None            # sprite palette (allocated once by the scene)
        self.spr = None            # rotated sprite buffer (allocated once by the scene)
        self.spr_a = 0
        self.fi = -1               # rotation step currently baked into spr
        self.lit = False           # tail lights currently bright
        self.reset(0.0, 0.0, 0.0)

    def assign(self, spec, slot, is_player):
        self.spec = spec
        self.slot = slot
        self.is_player = is_player
        self.fi = -1
        self.lit = False

    def reset(self, x, y, hd):
        self.x = x
        self.y = y
        self.px = x
        self.py = y
        self.hd = hd
        self.fx = math.cos(hd)
        self.fy = math.sin(hd)
        self.vx = 0.0
        self.vy = 0.0
        self.spd = 0.0             # forward speed
        self.lat = 0.0             # sideways speed
        # inputs (player: from switches, AI: from the driver)
        self.steer = 0.0
        self.throttle = False
        self.brake = False
        self.nitro_req = False
        # nitro
        self.nitro_on = False
        self.nitro_meter = S.NITRO_START
        self.nitro_fired = False   # one-shot event for the scene (sfx)
        self.nitro_ended = False
        self.surf = S.ROAD
        self.bump = 0.0            # one-shot collision strength
        # progress
        self.total = 0             # waypoint segments travelled (0 = start line)
        self.seg_t = 0.0
        self.prog = 0.0
        self.finished = False
        self.place = 0
        self.finish_ms = 0
        self.lap_start = 0
        self.best_lap = 0
        self.stuck = 0.0
        self.wrong = 0.0
        self.flame = False
        self.rail = False          # far from the player: cheap on-rails driving
