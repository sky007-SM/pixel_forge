# ============================================================
# Transitions. Each one has begin(r), apply(r, t) with t = 0 (clear)
# .. 1 (fully hidden), and end(r).
#
#   Fade     real brightness steps 100 -> 50 -> 25 -> 12 % -> black
#   Shutter  rows close in from top and bottom
#   Blinds   venetian-blind slats
#
# Fade works on any scene because it is applied to the finished rows by
# the renderer. Shutter / Blinds use the coverage mask instead.
# ============================================================
from system.renderer import cover_rows, cover_blinds


def ease(t):
    return t * t * (3.0 - 2.0 * t)


class Fade:
    frames = 8

    def begin(self, r):
        pass

    def apply(self, r, t):
        lvl = int(t * 5)
        r.set_fx(lvl if lvl < 4 else 4)

    def end(self, r):
        r.set_fx(0)


class Shutter:
    frames = 9

    def begin(self, r):
        r.cov_on = True

    def apply(self, r, t):
        cover_rows(r.cover, int(ease(t) * 120 + 0.5))

    def end(self, r):
        r.cov_on = False


class Blinds:
    frames = 9

    def begin(self, r):
        r.cov_on = True

    def apply(self, r, t):
        cover_blinds(r.cover, int(ease(t) * 8 + 0.5))

    def end(self, r):
        r.cov_on = False


def make(kind):
    if kind == "blinds":
        return Blinds()
    if kind == "shutter":
        return Shutter()
    return Fade()
