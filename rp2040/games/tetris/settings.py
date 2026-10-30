# ============================================================
# Tetris tuning. Frame counts are at 30 fps.
# ============================================================
from config import rgb

COLS = 10
ROWS = 20
CELL = 11
FRAME = 3                      # frame thickness around the grid sprite
GRID_W = COLS * CELL + 2 * FRAME     # 116
GRID_H = ROWS * CELL + 2 * FRAME     # 226
GRID_X = (320 - GRID_W) // 2         # 102
GRID_Y = (240 - GRID_H) // 2         # 7

# name, frames per row (gravity), pre-filled rows, score multiplier x10, description
LEVELS = (
    ("LEVEL 1", 28, False, 10, "SLOW FALL   CLEAN GRID"),
    ("LEVEL 2", 14, False, 15, "FAST FALL   CLEAN GRID"),
    ("LEVEL 3", 8, True, 20, "FAST FALL   MESSY GRID"),
)
GARBAGE_MIN = 6                # level 3: random rows already on the board
GARBAGE_MAX = 9

DAS = 8                        # frames before auto-repeat starts
ARR = 3                        # frames between repeats
SOFT_FRAMES = 2                # frames per row while soft dropping
LOCK_DELAY = 8                 # frames a grounded piece may still be moved
LOCK_RESETS = 10
CLEAR_FRAMES = 12              # line clear flash

LINE_SCORES = (0, 100, 300, 500, 800)
STREAK_BONUS = 50              # per extra consecutive clearing piece
SOFT_PTS = 1
HARD_PTS = 2
SCORE_CAP = 999999

# piece colours: I O T S Z J L
COLORS = (
    rgb(0, 220, 230), rgb(240, 220, 40), rgb(170, 70, 210), rgb(70, 210, 80),
    rgb(230, 60, 60), rgb(60, 100, 235), rgb(240, 150, 40),
)
