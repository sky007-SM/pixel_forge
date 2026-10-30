# ============================================================
# Shards of Aetheria: tuning values
# All gameplay maths is integer (no floats, no per-frame allocation).
#   Kiro: 1 px = 16 sub-pixels, speeds in sub-px / frame (30 fps)
#   enemies, shots, boss: whole pixels
# ============================================================
KEY = "shards"
FPS = 30
# Run game logic inside the display's DMA gaps (see game.draw). True = best frame rate
# (costs one frame of input latency); False = classic: logic runs before drawing.
OVERLAP = True
MAXS = 72                # sprites per frame
LEVELS = 9               # 3 areas x 3 levels (the 3rd of each area is a boss)


def rgb(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


# ---- movement: fast and snappy ----
GRAV = 9
MAXFALL = 170
RUN = 64                 # 4 px/frame = 120 px/s
ACC = 12
FRIC = 14
AIR_ACC = 8
JUMP_V = -152            # ~5 tiles high
DJUMP_V = -134
JUMP_CUT = -56
APEX = 44
COYOTE = 5
JBUF = 6
STOMP_V = -116
POUND_V = 200
DASH_V = 150             # fire dash: 10 frames x 9.4 px = ~94 px
DASH_F = 10
INV = 60

START_HP = 3
MAX_HP = 5

# ---- damage ----
D_PUNCH = 1
D_SWORD = 2
D_STOMP = 2
D_POUND = 3
D_DASH = 4               # boss only: a dash one-shots every normal enemy
D_SPEAR = 6              # boss only: Rootspike kills every normal enemy in its line
D_VOID = 14              # boss only: Void Collapse kills everything around it

SPEAR_SPEED = 12         # Rootspike: 16 frames x 12 px = 192 px max range
SPEAR_LIFE = 16
VOID_R = 80              # Void Collapse blast radius

# ---- ability meter (green -> orange -> purple) ----
TIER = 4096
CHARGE_S = ((7.0,), (4.5, 7.0), (3.0, 4.5, 7.0))     # seconds per tier, per area
ORB = TIER // 3


def charge_rates(area):
    return tuple(int(TIER / (s * FPS)) for s in CHARGE_S[area])
