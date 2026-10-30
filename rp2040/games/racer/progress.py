# ============================================================
# Race progress: laps, positions, podium detection, rewards, unlocks
#
# Every car tracks `total` = number of waypoint segments travelled
# (0 = the start line, negative on the grid). It only moves one segment
# at a time, so cutting across the infield can't skip checkpoints, and
# driving backwards over the line removes progress again.
# ============================================================
from games.racer import settings as S
from games.racer import save as SV

EV_LAP = 1
EV_FINISH = 2


def init_car(c, trk, k):
    """Place the car's counters from its dense start index k."""
    c.total = trk.start_total(k)
    c.seg_t = 0.0
    c.prog = float(c.total)
    c.finished = False
    c.place = 0
    c.lap_start = 0


def update(c, trk):
    """Advance the segment counter. Returns EV_* bit flags."""
    N = trk.nw
    tot = c.total
    old = tot
    i = tot % N
    wx = trk.wx
    wy = trk.wy
    tx = trk.tx
    ty = trk.ty
    inv = trk.inv_step
    x = c.x
    y = c.y
    t = ((x - wx[i]) * tx[i] + (y - wy[i]) * ty[i]) * inv
    n = 0
    while t >= 1.0 and n < 3:
        tot += 1
        i = tot % N
        t = ((x - wx[i]) * tx[i] + (y - wy[i]) * ty[i]) * inv
        n += 1
    while t < -0.75 and n < 3:
        tot -= 1
        i = tot % N
        t = ((x - wx[i]) * tx[i] + (y - wy[i]) * ty[i]) * inv
        n += 1
    c.total = tot
    if t < 0.0:
        c.seg_t = 0.0
    elif t > 0.999:
        c.seg_t = 0.999
    else:
        c.seg_t = t
    c.prog = tot + c.seg_t
    ev = 0
    if tot > old:
        lap_new = tot // N
        if lap_new > old // N and lap_new >= 1:
            ev = EV_LAP
            if lap_new >= trk.laps:
                ev |= EV_FINISH
    return ev


def wrong_way(c, trk):
    i = c.total % trk.nw
    return c.spd > 25.0 and (c.fx * trk.tx[i] + c.fy * trk.ty[i]) < -0.3


def _key(c):
    return (1000000.0 - c.place) if c.finished else c.prog


def ranking(cars):
    r = list(cars)
    r.sort(key=_key, reverse=True)
    return r


# ---------------- rewards / unlocks ----------------
def prize_for(place):
    if 1 <= place <= 3:
        return S.PRIZES[place - 1]
    return S.PRIZE_OTHER


def podium(place):
    return 1 <= place <= 3


class Result:
    def __init__(self):
        self.place = 0
        self.prize = 0
        self.unlocked = -1          # index of newly unlocked track, or -1
        self.podium = False
        self.new_best = False
        self.race_ms = 0
        self.best_lap_ms = 0
        self.last_track = False


def apply_result(save, track_idx, place, race_ms, lap_ms, n_tracks):
    """Pay the prize, unlock the next circuit on a podium, record times."""
    r = Result()
    r.place = place
    r.race_ms = race_ms
    r.best_lap_ms = lap_ms
    r.prize = prize_for(place)
    r.podium = podium(place)
    SV.add_money(save, r.prize)
    if r.podium:
        nxt = track_idx + 1
        if nxt < n_tracks:
            if SV.unlock_track(save, nxt):
                r.unlocked = nxt
        else:
            r.last_track = True
    r.new_best = SV.submit_times(save, track_idx, race_ms, lap_ms)
    return r
