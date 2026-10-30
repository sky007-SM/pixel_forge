# ============================================================
# Tunes and sound effects for the PWM audio engine.
#
# Songs are written as text:  NOTE[/units]   e.g.  "C5 E5/2 -/1"
#   NOTE = A-G, optional # or b, octave 2..7 ("C5", "F#4", "Bb5");  "-" = rest
#   /n   = length in units (default 1); a unit is `unit` ticks of 10 ms
# They are converted once (on first use) into compact bytes: note, ticks, ...
#
# Sound effects are tuples of segments (f_start, f_end, ticks, kind):
#   kind 0 = tone / pitch slide, 1 = noise (random pitch between f_start..f_end),
#   kind 2 = silence
# ============================================================

_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _freq_table():
    t = [0]
    for n in range(1, 97):                       # note 1 = C2 (65 Hz)
        t.append(int(440 * 2 ** ((n + 35 - 69) / 12) + 0.5))
    return tuple(t)


FREQ = _freq_table()


def note_num(tok):
    n = _BASE[tok[0]]
    i = 1
    if tok[i] == "#":
        n += 1
        i += 1
    elif tok[i] == "b":
        n -= 1
        i += 1
    return (int(tok[i:]) - 2) * 12 + n + 1


def _emit(out, n, ticks):
    while ticks > 255:
        out.append(n)
        out.append(255)
        ticks -= 255
    if ticks > 0:
        out.append(n)
        out.append(ticks)


def build(text, unit, gap=1):
    out = bytearray()
    for tok in text.split():
        if "/" in tok:
            name, d = tok.split("/")
            d = int(d)
        else:
            name, d = tok, 1
        ticks = d * unit
        if name == "-":
            _emit(out, 0, ticks)
        else:
            n = note_num(name)
            if ticks > gap + 1:                  # small gap so repeated notes stay distinct
                _emit(out, n, ticks - gap)
                _emit(out, 0, gap)
            else:
                _emit(out, n, ticks)
    return bytes(out)


# name: (unit ticks, gap ticks, notes)
SONGS = {
    # console start-up: anvil strike (sfx) then a rising arpeggio, about 3 s
    "boot": (10, 1,
             "-/4 C5 E5 G5 C6/2 G5 C6 E6 G6/2 E6 G6 C7/3 -/1 G6 C7 E7/9"),
    # idle menu loop, 120 bpm, 32 s: Am F C G progression, two 8-bar sections
    "menu": (25, 2,
             "E5/2 A5/2 G5 E5 C5/2   F5/2 A5/2 G5 F5 C5/2   E5/2 G5/2 E5 D5 C5/2   D5/2 G5/2 B5 A5 G5/2 "
             "A5/2 C6/2 B5 A5 E5/2   A5/2 F5/2 G5 A5 C6/2   G5/2 E5 G5 C6/2 E6 D6   B5/2 G5/2 D5/2 -/2 "
             "C6 B5 A5/2 E5/2 A5/2   A5 G5 F5/2 C5/2 F5/2   G5 F5 E5/2 G5/2 C6/2   B5 A5 G5/2 D5/2 G5/2 "
             "E6/2 C6/2 A5/2 C6/2   F6/2 C6/2 A5/2 F5/2   G5/2 C6/2 E6/2 G6/2   D6/2 B5/2 G5/2 -/2"),
    "shutdown": (9, 1, "G6 E6 C6 G5 E5/2 C5/5"),
    "gameover": (8, 1, "-/5 E5/2 D5/2 C5/6"),
    "newbest": (8, 1, "-/5 C5 E5 G5 C6/2 G5 C6/6"),
}

_CACHE = {}


def song(name):
    s = _CACHE.get(name)
    if s is None:
        d = SONGS[name]
        s = build(d[2], d[0], d[1])
        _CACHE[name] = s
    return s


SFX = {
    "move": ((1320, 1320, 2, 0),),
    "select": ((880, 880, 3, 0), (1320, 1320, 6, 0)),
    "back": ((880, 880, 3, 0), (587, 587, 6, 0)),
    "error": ((196, 196, 4, 0), (0, 0, 2, 2), (196, 196, 6, 0)),
    "pause": ((988, 988, 3, 0), (1319, 1319, 4, 0)),
    "flap": ((330, 820, 6, 0),),
    "point": ((1047, 1047, 4, 0), (1568, 1568, 12, 0)),
    "dead": ((300, 1100, 6, 1), (0, 0, 3, 2), (700, 90, 26, 0)),
    "clang": ((1200, 3200, 4, 1), (2637, 2600, 8, 0), (2637, 2300, 14, 0)),
}
