# ============================================================
# Arcade physics: driving model, nitro overdrive, collisions
#
# The car keeps a world-space velocity and a heading. Every frame the
# velocity is split into forward / sideways parts, the engine, brakes and
# grip act on those, and the parts are recombined. Grip decides how fast
# the sideways part dies, so low-grip cars slide naturally.
# ============================================================
import math
from games.racer import settings as S

_sin = math.sin
_cos = math.cos
_sqrt = math.sqrt
_PI = math.pi
_TWO_PI = 2.0 * math.pi


def step_car(c, dt, trk):
    sp = c.spec

    # ---- nitro as its own driving state ----
    on = c.nitro_on
    if c.nitro_req:
        c.nitro_req = False
        if (not on) and c.nitro_meter >= 0.999:
            on = True
            c.nitro_on = True
            c.nitro_fired = True
    if on:
        c.nitro_meter -= dt / S.NITRO_TIME
        if c.nitro_meter <= 0.0:                # drained: back to normal driving
            c.nitro_meter = 0.0
            c.nitro_on = False
            c.nitro_ended = True
            on = False
    else:
        if c.spd > S.NITRO_MIN_SPEED and c.surf != S.GRASS:
            m = c.nitro_meter + dt * S.NITRO_RECHARGE
            c.nitro_meter = 1.0 if m > 1.0 else m

    # ---- surface ----
    cls = trk.surface(c.x, c.y)
    c.surf = cls
    vmax = sp.vmax
    acc = sp.accel
    grip = sp.grip * S.SURF_GRIP[cls]
    steer_loss = S.STEER_LOSS
    if on:
        pw = sp.nitro
        vmax = vmax * (1.0 + S.NITRO_VMAX * pw)
        acc = acc * (1.0 + S.NITRO_ACC * pw)
        grip = grip * S.NITRO_GRIP
        steer_loss = S.NITRO_STEER_LOSS
    vm_s = vmax * S.SURF_VMAX[cls]

    # ---- steering: yaw rate depends on speed ----
    vx = c.vx
    vy = c.vy
    vf0 = vx * c.fx + vy * c.fy
    sv = vf0 if vf0 >= 0.0 else -vf0
    low = sv * (1.0 / S.STEER_LOW_SPEED)
    if low > 1.0:
        low = 1.0
    yaw = c.steer * sp.turn * low / (1.0 + steer_loss * sv / sp.vmax)
    if on:
        yaw *= S.NITRO_STEER_GAIN
    if vf0 < 0.0:
        yaw = -yaw
    hd = c.hd + yaw * dt
    if hd > _PI:
        hd -= _TWO_PI
    elif hd < -_PI:
        hd += _TWO_PI
    c.hd = hd
    fx = _cos(hd)
    fy = _sin(hd)
    c.fx = fx
    c.fy = fy

    # ---- split velocity (heading may have rotated under it -> slide) ----
    vf = vx * fx + vy * fy
    vs = vy * fx - vx * fy

    # ---- longitudinal forces ----
    if on:
        # overdrive: full throttle regardless of the switch
        a = acc * (1.0 - vf / vm_s)
        if a > 0.0:
            vf += a * dt
        if c.brake and vf > 0.0:
            vf -= sp.brake * S.NITRO_BRAKE * dt
    elif c.brake:
        if vf > 2.0:
            vf -= sp.brake * dt
            if vf < 0.0:
                vf = 0.0
        else:
            vf -= S.REVERSE_ACC * dt
            if vf < -S.REVERSE_MAX:
                vf = -S.REVERSE_MAX
    elif c.throttle:
        if vf < 0.0:
            vf += sp.brake * dt
        else:
            a = acc * (1.0 - vf / vm_s)
            if a > 0.0:
                vf += a * dt
    else:
        vf -= vf * S.ROLL * dt
    if vf > vm_s:
        vf -= (vf - vm_s) * S.OVERSPEED * dt

    # ---- lateral grip ----
    g = grip * dt
    if g > 0.95:
        g = 0.95
    vs -= vs * g
    avs = vs if vs >= 0.0 else -vs
    if vf > 0.0:
        vf -= avs * S.SLIDE_DRAG * dt
        if vf < 0.0:
            vf = 0.0

    c.spd = vf
    c.lat = vs
    c.vx = fx * vf - fy * vs
    c.vy = fy * vf + fx * vs
    c.px = c.x
    c.py = c.y
    c.x += c.vx * dt
    c.y += c.vy * dt


def collide_cars(cars):
    """Circle vs circle, mass weighted, with a little bounce."""
    n = len(cars)
    r2 = 2.0 * S.CAR_R
    r2sq = r2 * r2
    for i in range(n):
        a = cars[i]
        for j in range(i + 1, n):
            b = cars[j]
            dx = b.x - a.x
            if dx > r2 or dx < -r2:
                continue
            dy = b.y - a.y
            if dy > r2 or dy < -r2:
                continue
            d2 = dx * dx + dy * dy
            if d2 >= r2sq:
                continue
            if d2 < 0.0001:
                dx = 1.0
                dy = 0.0
                d = 1.0
            else:
                d = _sqrt(d2)
            nx = dx / d
            ny = dy / d
            pen = r2 - d
            ma = a.spec.mass
            mb = b.spec.mass
            tot = ma + mb
            wa = mb / tot
            wb = ma / tot
            a.x -= nx * pen * wa
            a.y -= ny * pen * wa
            b.x += nx * pen * wb
            b.y += ny * pen * wb
            rvn = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
            if rvn < 0.0:
                j_imp = -(1.0 + S.CAR_BOUNCE) * rvn / (1.0 / ma + 1.0 / mb)
                a.vx -= j_imp * nx / ma
                a.vy -= j_imp * ny / ma
                b.vx += j_imp * nx / mb
                b.vy += j_imp * ny / mb
                s = -rvn
                if s > a.bump:
                    a.bump = s
                if s > b.bump:
                    b.bump = s


def resolve_walls(c, trk):
    """Push a car out of wall cells and bounce / scrub its velocity."""
    if S.ROADLIKE[c.surf]:
        return                       # on the road: walls and trees are far away
    surf = trk.surface
    R = S.CAR_R - 1.0
    x = c.x
    y = c.y
    solid = S.SOLID
    tx = 0.0
    ty = 0.0
    hit = False
    for _ in range(5):
        nx = 0.0
        ny = 0.0
        if solid[surf(x - R, y)]:
            nx += 1.0
        if solid[surf(x + R, y)]:
            nx -= 1.0
        if solid[surf(x, y - R)]:
            ny += 1.0
        if solid[surf(x, y + R)]:
            ny -= 1.0
        if nx == 0.0 and ny == 0.0:
            if solid[surf(x, y)]:          # tunnelled: go back to last good spot
                x = c.px
                y = c.py
                c.vx *= 0.3
                c.vy *= 0.3
                hit = True
            break
        hit = True
        l = _sqrt(nx * nx + ny * ny)
        nx /= l
        ny /= l
        if tx == 0.0 and ty == 0.0:
            tx = nx
            ty = ny
        x += nx * 2.0
        y += ny * 2.0
    if not hit:
        return
    c.x = x
    c.y = y
    vn = c.vx * tx + c.vy * ty
    if vn < 0.0:
        k = (1.0 + S.WALL_BOUNCE) * vn
        c.vx -= k * tx
        c.vy -= k * ty
        c.vx *= S.WALL_SCRUB
        c.vy *= S.WALL_SCRUB
        if -vn > c.bump:
            c.bump = -vn
    # keep the cached forward speed consistent for the HUD / AI
    c.spd = c.vx * c.fx + c.vy * c.fy
