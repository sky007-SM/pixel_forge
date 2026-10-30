# ============================================================
# Track definitions (pure data: control points, laps, rivals, themes).
# Kept apart from track.py so the menus can list tracks without importing
# the track builder.
# ============================================================
from games.racer import settings as S


class TrackDef:
    def __init__(self, name, pts, laps, n_ai, skill, pool, theme, blurb):
        self.name = name
        self.pts = pts              # closed loop of (x, y); pts[0] sits on the start straight
        self.laps = laps
        self.n_ai = n_ai            # opponents (max 8)
        self.skill = skill          # (min, max) AI skill
        self.pool = pool            # indices into CARS the AI may drive
        self.theme = theme          # grassA, grassB, roadA, roadB, wallA, wallB
        self.blurb = blurb


def _t(grass, road, wall, tree):
    return (grass[0], grass[1], road[0], road[1], wall[0], wall[1], tree)


rgb = S.rgb

TRACKS = (
    TrackDef("SUNNY LOOP",
             ((420, 850), (700, 845), (860, 790), (900, 640), (850, 490),
              (740, 420), (650, 330), (520, 220), (340, 190), (200, 250),
              (150, 400), (190, 540), (160, 690), (210, 800), (300, 845)),
             3, 5, (0.86, 0.95), (0, 1),
             _t((rgb(60, 160, 70), rgb(54, 148, 64)),
                (rgb(92, 94, 100), rgb(86, 88, 94)),
                (rgb(70, 74, 86), rgb(60, 64, 76)),
                rgb(40, 122, 52)),
             "WIDE AND FRIENDLY"),
    TrackDef("HARBOR RUN",
             ((460, 885), (700, 880), (860, 845), (935, 730), (890, 610),
              (760, 580), (690, 470), (770, 370), (880, 290), (850, 170),
              (700, 125), (560, 185), (470, 290), (340, 300), (230, 360),
              (165, 480), (225, 590), (175, 700), (170, 800), (250, 870),
              (350, 885)),
             3, 6, (0.91, 0.99), (0, 1, 2, 3),
             _t((rgb(214, 190, 120), rgb(204, 178, 108)),
                (rgb(98, 100, 108), rgb(90, 92, 100)),
                (rgb(60, 80, 110), rgb(50, 68, 96)),
                rgb(96, 128, 62)),
             "CHICANES BY THE DOCKS"),
    TrackDef("PINE PASS",
             ((430, 905), (700, 900), (860, 850), (915, 735), (840, 635),
              (700, 650), (600, 580), (610, 470), (730, 430), (860, 380),
              (905, 260), (810, 160), (660, 135), (550, 205), (490, 320),
              (370, 395), (240, 400), (160, 500), (190, 630), (150, 730),
              (190, 830), (290, 885)),
             3, 7, (0.95, 1.02), (1, 2, 3, 4),
             _t((rgb(36, 110, 60), rgb(30, 98, 54)),
                (rgb(84, 86, 94), rgb(78, 80, 88)),
                (rgb(60, 62, 70), rgb(50, 52, 60)),
                rgb(24, 86, 54)),
             "HAIRPINS AND SWEEPERS"),
    TrackDef("NEON SPEEDWAY",
             ((440, 905), (680, 900), (870, 860), (935, 740), (870, 630),
              (710, 625), (600, 560), (650, 450), (800, 400), (900, 320),
              (890, 200), (780, 135), (640, 150), (530, 250), (420, 205),
              (310, 140), (190, 170), (130, 270), (170, 380), (290, 430),
              (330, 540), (250, 620), (130, 690), (120, 800), (200, 870),
              (320, 895)),
             4, 8, (0.99, 1.05), (2, 3, 4, 5),
             _t((rgb(24, 24, 52), rgb(20, 20, 44)),
                (rgb(56, 58, 76), rgb(50, 52, 70)),
                (rgb(100, 40, 120), rgb(80, 30, 100)),
                rgb(160, 70, 210)),
             "FAST, TIGHT, RELENTLESS"),
)



