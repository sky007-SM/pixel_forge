# ============================================================
# Flappy Bird art: shared background rows, bird sprite, pipe strips
# ============================================================
import array, math
from hardware.display import P16
from system.renderer import TRANS
from system.dialog import Box
from assets.fonts import Text
from games.flappy_bird import settings as S

W = 320
H = 240
SKY = P16(S.SKY)
WHITE = P16(S.WHITE)
BLACK = P16(S.BLACK)
NAVY = P16(S.NAVY)
YELLOW = P16(S.YELLOW)
ORANGE = P16(S.ORANGE)
GREEN = P16(S.GREEN)
DARKGREEN = P16(S.DARKGREEN)
LIGHTGREEN = P16(S.LIGHTGREEN)
SOIL = P16(S.SOIL)
SAND = P16(S.SAND)
TRIM = P16(S.TRIM)

BW = 30                 # bird sprite size, centre at (BCX, BCY)
BH = 25
BCX = 13
BCY = 12
STRIP_W = S.PIPE_WIDTH + 7

# pipe row type by distance from the gap edge (1..12); >= 13 is type 1
TOP_T = (0, 0, 0, 0, 0, 1, 1, 2, 3, 3, 3, 2, 2)
BOT_T = (0, 0, 0, 0, 0, 0, 1, 2, 3, 3, 3, 2, 2)


# ---- small pixel-domain helpers (start-up only) ----
def _hl(buf, bw, x0, x1, c):
    if x0 < 0:
        x0 = 0
    if x1 >= bw:
        x1 = bw - 1
    for x in range(x0, x1 + 1):
        buf[x] = c


def _ell(buf, bw, y, cx, cy, rx, ry, c):
    dy = y - cy
    if dy < 0:
        dy = -dy
    if dy > ry:
        return
    r = 1.0 - (dy * dy) / (ry * ry)
    if r < 0.0:
        r = 0.0
    dx = int(rx * math.sqrt(r))
    _hl(buf, bw, cx - dx, cx + dx, c)


def _sp_ell(sp, y, cx, cy, rx, ry, c):
    dy = y - cy
    if dy < 0:
        dy = -dy
    if dy > ry:
        return
    r = 1.0 - (dy * dy) / (ry * ry)
    if r < 0.0:
        r = 0.0
    dx = int(rx * math.sqrt(r))
    sp.append((cx - dx, cx + dx, c))


def build_bg():
    """Static background without full-size row buffers (about 3 KB instead of 30 KB):
      rows   4 base rows: 0 sky, 1 grass edge, 2 trim, 3 sand
      base   bytearray(240): which base row each screen row starts from
      sidx   array(241): offsets into sdata; sdata holds (x0, x1_exclusive, colour) triples
    A row is built as copy_row(base) + fill_span for each triple."""
    rows = [array.array("H", [c] * W) for c in (SKY, GREEN, TRIM, SAND)]
    base = bytearray(H)
    flat = []
    idx = array.array("H", [0] * (H + 1))
    for y in range(H):
        base[y] = 3 if y >= 210 else (2 if y >= 205 else (1 if y >= S.GROUND_Y else 0))
        sp = []
        _sp_ell(sp, y, 276, 35, 17, 17, YELLOW)
        _sp_ell(sp, y, 48, 88, 19, 10, WHITE)
        _sp_ell(sp, y, 64, 83, 14, 13, WHITE)
        _sp_ell(sp, y, 80, 89, 18, 9, WHITE)
        _sp_ell(sp, y, 205, 91, 17, 9, WHITE)
        _sp_ell(sp, y, 220, 85, 13, 12, WHITE)
        _sp_ell(sp, y, 234, 91, 16, 8, WHITE)
        if y >= 211 and y % 13 == 0:
            sp.append((12, 27, SOIL))
            sp.append((73, 91, SOIL))
            sp.append((145, 160, SOIL))
            sp.append((210, 226, SOIL))
            sp.append((280, 300, SOIL))
        idx[y] = len(flat)
        for (x0, x1, c) in sp:
            if x0 < 0:
                x0 = 0
            if x1 > W - 1:
                x1 = W - 1
            flat.append(x0)
            flat.append(x1 + 1)
            flat.append(c)
    idx[H] = len(flat)
    return rows, base, idx, array.array("H", flat)


def build_bird():
    spr = array.array("H", [TRANS] * (BW * BH))
    buf = array.array("H", [TRANS] * BW)
    R = S.BIRD_RADIUS
    for k in range(BH):
        dy = k - BCY
        for i in range(BW):
            buf[i] = TRANS
        _ell(buf, BW, dy, BCX, 0, R + 3, R + 2, NAVY)
        _ell(buf, BW, dy, BCX, 0, R, R - 2, YELLOW)
        _ell(buf, BW, dy, BCX - 4, 3, 6, 3, ORANGE)
        _ell(buf, BW, dy, BCX - 4, 2, 5, 2, YELLOW)
        _ell(buf, BW, dy, BCX + 6, -4, 3, 3, WHITE)
        _ell(buf, BW, dy, BCX + 7, -4, 1, 1, BLACK)
        if -1 <= dy <= 2:
            _hl(buf, BW, BCX + 10, BCX + 16, ORANGE)
        o = k * BW
        for i in range(BW):
            spr[o + i] = buf[i]
    return spr


def _rect(buf, bw, y, x0, x1, y0, y1, c):
    if y0 <= y <= y1:
        _hl(buf, bw, x0, x1, c)


def _pipe_px(buf, bw, y, px, gt, gb):
    w = S.PIPE_WIDTH
    gy = S.GROUND_Y
    _rect(buf, bw, y, px, px + w, 0, gt - 1, DARKGREEN)
    _rect(buf, bw, y, px + 5, px + w - 5, 0, gt - 5, GREEN)
    _rect(buf, bw, y, px + 5, px + 10, 0, gt - 5, LIGHTGREEN)
    _rect(buf, bw, y, px - 3, px + w + 3, gt - 12, gt - 7, DARKGREEN)
    _rect(buf, bw, y, px, px + w, gt - 10, gt - 8, GREEN)
    _rect(buf, bw, y, px, px + w, gb + 1, gy - 1, DARKGREEN)
    _rect(buf, bw, y, px + 5, px + w - 5, gb + 6, gy - 1, GREEN)
    _rect(buf, bw, y, px + 5, px + 10, gb + 6, gy - 1, LIGHTGREEN)
    _rect(buf, bw, y, px - 3, px + w + 3, gb + 7, gb + 12, DARKGREEN)
    _rect(buf, bw, y, px, px + w, gb + 8, gb + 10, GREEN)


def build_strips():
    """4 pipe row types, 55 px wide (px-3 .. px+51):
    0 body edge only, 1 body + highlight, 2 cap, 3 cap + stripe."""
    strips = []
    for y in (98, 0, 88, 90):               # sampled with gt = 100, gb = 150
        s = array.array("H", [TRANS] * STRIP_W)
        _pipe_px(s, STRIP_W, y, 3, 100, 150)
        strips.append(s)
    return strips


# ---- text masks and the game-over box ----
def score_text(score):
    return Text("SCORE: " + str(score), 2)


def ready_texts():
    return Text("GET READY", 2), Text("PRESS A TO FLAP", 1)


OV_X, OV_Y, OV_W, OV_H = 42, 75, 237, 86


def make_gameover(score, best, new_best):
    """Game-over box drawn from rectangles and 1-bit text (no pixel buffer)."""
    b = Box(OV_X, OV_Y, OV_W, OV_H)
    b.rect(0, 0, OV_W, OV_H, YELLOW)
    b.rect(5, 5, OV_W - 10, OV_H - 10, WHITE)
    t = Text("GAME OVER", 2)
    b.text((OV_W - t.w) // 2, 7, t, NAVY)
    t = Text("SCORE: " + str(score), 2)
    b.text((OV_W - t.w) // 2, 29, t, BLACK)
    t = Text(("NEW BEST: " if new_best else "BEST: ") + str(best), 2)
    b.text((OV_W - t.w) // 2, 47, t, ORANGE if new_best else BLACK)
    t = Text("A RETRY    B MENU", 1)
    b.text((OV_W - t.w) // 2, 69, t, P16(0x7BEF))
    return b
