# ============================================================
# AI rivals (up to 8). A Driver fills in the same inputs the player's
# switches do (steer / throttle / brake / nitro) and the car then runs
# through the normal physics - no cheating on handling.
#
#   racing line   waypoint a few steps ahead + a lane offset
#   corner speed  from the waypoint radius and this car's own turn rate,
#                 with a braking-distance lookahead
#   overtaking    shifts lane away from a slower car that is just ahead
#   nitro         fired on straights once the meter is full
#   rubber band   gentle speed trim so the pack stays close to the player
#   recovery      puts a stuck car back on the centre line
# ============================================================
import math
import random
from games.racer import settings as S
from games.racer import progress as PR

_sqrt = math.sqrt


class Driver:
    def __init__(self, car, trk, skill, nitro_p):
        self.car = car
        self.trk = trk
        self.skill = skill
        self.nitro_p = nitro_p                 # chance per think on a straight
        self.pref = random.uniform(-9.0, 9.0)  # personal lane
        self.lane = self.pref
        self.lane_t = self.pref
        self.rb = 1.0
        sp = car.spec
        self.c2 = S.STEER_LOSS / sp.vmax
        self.c1 = 0.86 * sp.turn * (0.9 + 0.1 * skill)
        self.k4 = 4.0 * self.c2 * self.c1
        self.inv2c2 = 1.0 / (2.0 * self.c2)
        self.dec = sp.brake * 0.68
        self.lim = S.ROAD_HALF - 11.0

    def vcorner(self, R):
        return (_sqrt(1.0 + self.k4 * R) - 1.0) * self.inv2c2

    def think(self, cars, ref_prog, dt):
        """dt = time since the last think (the scene calls this every 2nd frame)."""
        c = self.car
        trk = self.trk
        N = trk.nw
        i = c.total % N
        spd = c.spd
        sp = c.spec
        wx = trk.wx
        wy = trk.wy
        rad = trk.rad

        # ---- rubber band from the gap to the player (in waypoints) ----
        gap = ref_prog - c.prog
        rb = 1.0 + gap * 0.0016
        if rb > 1.08:
            rb = 1.08
        elif rb < 0.97:
            rb = 0.97
        self.rb = rb

        # ---- lane: personal line, apex bias, avoid slower cars ----
        la = 2 + int(spd * 0.032)
        j = (i + la) % N
        lane_t = self.pref
        r4 = rad[(i + 4) % N]
        if -260.0 < r4 < 260.0:
            lane_t = 10.0 if r4 > 0.0 else -10.0      # inside of the corner
        fx = c.fx
        fy = c.fy
        for o in cars:
            if o is c:
                continue
            dx = o.x - c.x
            dy = o.y - c.y
            fw = dx * fx + dy * fy
            if fw < 3.0 or fw > 52.0:
                continue
            lt = -dx * fy + dy * fx                   # + = they are on my right
            if lt < 15.0 and lt > -15.0:
                lane_t = self.lane - 17.0 if lt > 0.0 else self.lane + 17.0
                if lt > -2.0 and lt < 2.0 and self.lane > 0.0:
                    lane_t = self.lane - 17.0
                break
        if lane_t > self.lim:
            lane_t = self.lim
        elif lane_t < -self.lim:
            lane_t = -self.lim
        step = 40.0 * dt
        d = lane_t - self.lane
        if d > step:
            d = step
        elif d < -step:
            d = -step
        self.lane += d

        # ---- steering towards the lane point ahead ----
        lane = self.lane
        tx = wx[j] - trk.ty[j] * lane - c.x
        ty = wy[j] + trk.tx[j] * lane - c.y
        dist = _sqrt(tx * tx + ty * ty) + 0.001
        cross = (fx * ty - fy * tx) / dist
        dot = (fx * tx + fy * ty) / dist
        if dot < 0.0:
            st = 1.0 if cross >= 0.0 else -1.0
        else:
            gain = 2.8 - spd * 0.004
            st = cross * gain
            if st > 1.0:
                st = 1.0
            elif st < -1.0:
                st = -1.0
        c.steer = st

        # ---- target speed from the corners ahead ----
        vmax = sp.vmax
        if c.nitro_on:
            vmax = vmax * (1.0 + S.NITRO_VMAX * sp.nitro)
        tv = vmax
        dd = 0.0
        for a in (1, 3, 5, 7, 9, 12):
            dd = a * S.WP_SPACING
            ra = rad[(i + a) % N]
            v = self.vcorner(ra if ra > 0.0 else -ra)
            v = _sqrt(v * v + 2.0 * self.dec * dd)
            if v < tv:
                tv = v
        tv *= self.skill * self.rb
        if c.surf == S.GRASS:
            tv *= 0.7
        err = spd - tv
        if err > 4.0:
            c.throttle = False
            c.brake = err > 11.0
        else:
            c.throttle = True
            c.brake = False

        # ---- nitro on a clear straight ----
        if (self.nitro_p > 0.0 and c.nitro_meter >= 0.999 and not c.nitro_on
                and spd > 0.45 * vmax and abs(rad[(i + 5) % N]) > 350.0
                and abs(rad[(i + 10) % N]) > 260.0 and random.random() < self.nitro_p):
            c.nitro_req = True

        # ---- recovery ----
        if spd < 12.0:
            c.stuck += dt
            if c.stuck > 1.6:
                self.recover()
        else:
            c.stuck = 0.0

    def rails(self, ref_prog, dt):
        """Cheap driving for a car far from the player (invisible): follow the centre line at
        the speed the corner ahead allows. Returns the same PR.EV_* flags as progress.update."""
        c = self.car
        trk = self.trk
        N = trk.nw
        old = c.total
        i = old % N
        sp = c.spec
        rb = 1.0 + (ref_prog - c.prog) * 0.0016
        if rb > 1.08:
            rb = 1.08
        elif rb < 0.97:
            rb = 0.97
        tv = self.vcorner(abs(trk.rad[(i + 3) % N]))
        if tv > sp.vmax:
            tv = sp.vmax
        tv *= self.skill * rb
        d = tv - c.spd
        up = sp.accel * dt
        dn = sp.brake * 0.55 * dt
        if d > up:
            d = up
        elif d < -dn:
            d = -dn
        c.spd += d
        c.seg_t += c.spd * dt / S.WP_SPACING
        tot = c.total
        while c.seg_t >= 1.0:
            c.seg_t -= 1.0
            tot += 1
        c.total = tot
        i = tot % N
        lane = self.pref
        t = c.seg_t
        st = t * trk.step
        c.x = trk.wx[i] + trk.tx[i] * st - trk.ty[i] * lane
        c.y = trk.wy[i] + trk.ty[i] * st + trk.tx[i] * lane
        c.px = c.x
        c.py = c.y
        c.fx = trk.tx[i]
        c.fy = trk.ty[i]
        c.prog = tot + t
        ev = 0
        if tot > old:
            lap_new = tot // N
            if lap_new > old // N and lap_new >= 1:
                ev = PR.EV_LAP
                if lap_new >= trk.laps:
                    ev |= PR.EV_FINISH
        return ev

    def sleep(self):
        self.car.rail = True

    def wake(self):
        """Back to full physics from where the rails put the car."""
        c = self.car
        c.rail = False
        c.hd = math.atan2(c.fy, c.fx)
        c.vx = c.fx * c.spd
        c.vy = c.fy * c.spd
        c.lat = 0.0
        c.stuck = 0.0
        self.lane = self.pref

    def recover(self):
        """Back onto the centre line, pointing along the track."""
        c = self.car
        trk = self.trk
        i = c.total % trk.nw
        c.x = trk.wx[i]
        c.y = trk.wy[i]
        c.px = c.x
        c.py = c.y
        c.hd = math.atan2(trk.ty[i], trk.tx[i])
        c.fx = trk.tx[i]
        c.fy = trk.ty[i]
        c.vx = 0.0
        c.vy = 0.0
        c.spd = 0.0
        c.lat = 0.0
        c.stuck = 0.0
        self.lane = 0.0


def pick_specs(n, pool):
    """Random car models for the AI from the track's pool."""
    out = []
    for _ in range(n):
        out.append(random.choice(pool))
    return out
