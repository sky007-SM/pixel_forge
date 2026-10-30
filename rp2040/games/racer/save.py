# ============================================================
# Persistence: money, unlocked tracks, owned cars, best times.
# Only plain ints are stored (same style as the Flappy Bird save).
#   tracks / cars are bit masks, times are milliseconds (0 = none).
# ============================================================
from games.racer import settings as S

KEY = S.KEY


def money(save):
    return save.get(KEY, "money", S.START_MONEY)


def add_money(save, amount):
    m = money(save) + amount
    save.set(KEY, "money", m)
    if m > save.get(KEY, "best", 0):
        save.set(KEY, "best", m)               # the console menu shows this as BEST
    return m


def spend(save, amount):
    m = money(save)
    if m < amount:
        return False
    save.set(KEY, "money", m - amount)
    return True


def tracks_mask(save):
    return save.get(KEY, "tracks", 1) | 1


def track_unlocked(save, i):
    return (tracks_mask(save) >> i) & 1 == 1


def unlock_track(save, i):
    """Returns True if the track was newly unlocked (never relocks)."""
    m = tracks_mask(save)
    if (m >> i) & 1:
        return False
    save.set(KEY, "tracks", m | (1 << i))
    return True


def cars_mask(save):
    return save.get(KEY, "cars", 1) | 1


def owns_car(save, i):
    return (cars_mask(save) >> i) & 1 == 1


def buy_car(save, i, price):
    if owns_car(save, i):
        return True
    if not spend(save, price):
        return False
    save.set(KEY, "cars", cars_mask(save) | (1 << i))
    return True


def selected_car(save):
    i = save.get(KEY, "car", 0)
    return i if owns_car(save, i) else 0


def select_car(save, i):
    save.set(KEY, "car", i)


def best_time(save, track):
    return save.get(KEY, "best%d" % track, 0)


def best_lap(save, track):
    return save.get(KEY, "lap%d" % track, 0)


def submit_times(save, track, race_ms, lap_ms):
    """Returns True when the race time is a new best."""
    new_best = False
    b = best_time(save, track)
    if race_ms > 0 and (b == 0 or race_ms < b):
        save.set(KEY, "best%d" % track, race_ms)
        new_best = True
    b = best_lap(save, track)
    if lap_ms > 0 and (b == 0 or lap_ms < b):
        save.set(KEY, "lap%d" % track, lap_ms)
    return new_best
