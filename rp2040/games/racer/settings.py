# ============================================================
# ForgeRacer - constants and tuning (pure data, no hardware)
#
# Colours are raw RGB565 (like the Flappy Bird settings). The
# renderer converts them with P16() where it needs pixel values.
# ============================================================
def rgb(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


KEY = "racer"                   # save namespace
NAME = "FORGERACER"

# ---------------- world / map ----------------
# The track is rasterised into a 256 x 256 cell map, 4 bits per cell,
# 4 world units per cell -> a 1024 x 1024 unit world in 32 KB.
CELL_SH = 2
MAP_N = 256
MAP_BYTES = (MAP_N * MAP_N) >> 1
WORLD = MAP_N << CELL_SH

# surface classes (value stored in the map, 0..15)
GRASS = 0
ROAD = 1
KERB = 2
WALL = 3
FINISH = 4
MARK = 5
TREE_D = 6                      # scenery trees: three stacked discs (dark / mid / light)
TREE_M = 7
TREE_L = 8
EDGE = 9                        # white edge line between road and kerb

ROAD_HALF = 26                  # half road width (units)
KERB_W = 5                      # kerb strip each side
GRASS_W = 26                    # grass run-off before the wall
WP_SPACING = 12.0               # distance between AI / progress waypoints

#            grass road  kerb  wall  fin   mark  treeD treeM treeL edge  (10..15 unused)
SURF_VMAX = (0.52, 1.00, 0.96, 0.30, 1.00, 1.00, 0.30, 0.30, 0.30, 1.00, 1, 1, 1, 1, 1, 1)
SURF_GRIP = (0.50, 1.00, 0.90, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1, 1, 1, 1, 1, 1)
SOLID = (False, False, False, True, False, False, True, True, True, False,
         False, False, False, False, False, False)      # classes a car bounces off
# classes that are at least ~29 units from any wall or tree (wall checks are skipped there)
ROADLIKE = (False, True, False, False, True, True, False, False, False, True,
            False, False, False, False, False, False)

# ---------------- camera ----------------
CAM_ANCHOR_Y = 136              # screen row the camera centre maps to
CAM_LEAD_K = 0.20               # look-ahead units per unit/s of speed
CAM_LEAD_MAX = 42.0
CAM_TURN_K = 5.5                # heading follow rate (1/s)
CAM_MAX_YAW = 6.0               # rad/s cap, stops violent spins
ROT_FRAMES = 32                 # rotated sprite frames per car

# ---------------- controls ----------------
STEER_DEADZONE = 0.05           # extra dead zone on top of Input's own
STEER_EXPO = 0.5                # 0 = linear, 1 = fully quadratic response

# ---------------- driving model ----------------
CAR_R = 6.5                     # collision radius
STEER_LOW_SPEED = 45.0          # below this speed steering is scaled down
STEER_LOSS = 0.65               # high speed steering reduction
ROLL = 0.55                     # coasting drag (1/s)
OVERSPEED = 1.8                 # bleed-off rate above the top speed (1/s)
SLIDE_DRAG = 1.5                # speed lost while sliding sideways
REVERSE_ACC = 130.0
REVERSE_MAX = 50.0
CAR_BOUNCE = 0.35
WALL_BOUNCE = 0.30
WALL_SCRUB = 0.82
KMH = 1.1                       # units/s -> displayed km/h

# ---------------- nitro ----------------
NITRO_TIME = 5.5                # seconds of a full meter
NITRO_VMAX = 0.30               # top speed bonus  (x car nitro power)
NITRO_ACC = 2.2                 # acceleration bonus (x car nitro power)
NITRO_GRIP = 0.85               # slightly looser while boosting
NITRO_STEER_GAIN = 1.25         # twitchier steering
NITRO_STEER_LOSS = 0.30         # less high-speed steering damping
NITRO_BRAKE = 0.30              # braking effectiveness during boost
NITRO_RECHARGE = 1.0 / 24.0     # meter per second of clean driving
NITRO_MIN_SPEED = 40.0          # no recharge below this speed
NITRO_START = 1.0

# ---------------- CPU budget (MicroPython floats are slow, so rivals are throttled) ----------------
AI_EVERY = 4                    # a rival "thinks" every Nth frame (staggered)
LOD_R = 210.0                   # rivals farther than this from the player drive "on rails"

# ---------------- diagnostics / frame pacing ----------------
PROFILE = True                 # True: print average update / prepare / draw / gc times every 2 s
GC_SLACK_US = 21000             # collect garbage after drawing only if the frame used less than this
GC_FREE = 60000                 # ...and only when the free heap is below this
GC_MIN = 12000                  # below this a collection runs BEFORE drawing, never during it (tearing)
HUD_PANELS = True               # translucent HUD panels (set False to save ~1 ms per frame)

# ---------------- race rules ----------------
COUNTDOWN = 3.4                 # seconds before GO
FINISH_DELAY = 1.8              # seconds before the results box
PRIZES = (1000, 700, 450)       # 1st, 2nd, 3rd
PRIZE_OTHER = 150
START_MONEY = 0

# ---------------- colours ----------------
BLACK = rgb(0, 0, 0)
WHITE = rgb(255, 255, 255)
NAVY = rgb(20, 30, 80)
YELLOW = rgb(255, 214, 0)
ORANGE = rgb(255, 130, 20)
RED = rgb(220, 40, 40)
GREEN = rgb(60, 200, 80)
CYAN = rgb(60, 210, 255)
GREY = rgb(130, 130, 140)
DGREY = rgb(60, 60, 70)
PANEL = rgb(18, 22, 40)
PANEL2 = rgb(34, 42, 72)

KERB_A = rgb(215, 40, 40)
KERB_B = rgb(240, 240, 240)
MARK_C = rgb(235, 235, 200)

CAR_DARK = rgb(24, 24, 30)
CAR_GLASS = rgb(150, 220, 255)
CAR_LIGHT = rgb(255, 250, 190)
FLAME_O = rgb(255, 120, 10)
FLAME_Y = rgb(255, 240, 120)
FLAME_B = rgb(120, 200, 255)

# menu background bands (top -> bottom)
MENU_BG = (rgb(14, 18, 44), rgb(18, 24, 56), rgb(22, 30, 68), rgb(26, 36, 80),
           rgb(22, 30, 68), rgb(18, 24, 56), rgb(14, 18, 44), rgb(10, 12, 30))
