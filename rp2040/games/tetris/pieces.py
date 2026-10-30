# ============================================================
# Tetromino shapes (I O T S Z J L), 4 rotations each
# ============================================================
from games.tetris.settings import COLS

_BASE = (
    (4, ("....", "XXXX", "....", "....")),
    (2, ("XX", "XX")),
    (3, (".X.", "XXX", "...")),
    (3, (".XX", "XX.", "...")),
    (3, ("XX.", ".XX", "...")),
    (3, ("X..", "XXX", "...")),
    (3, ("..X", "XXX", "...")),
)


def _build():
    shapes = []
    spawn_x = []
    spawn_y = []
    for box, rows in _BASE:
        cells = []
        for y in range(len(rows)):
            for x in range(len(rows[y])):
                if rows[y][x] == "X":
                    cells.append((x, y))
        rots = []
        cur = cells
        for _ in range(4):
            rots.append(tuple(cur))
            if box == 2:
                continue                       # O does not change
            cur = [(box - 1 - y, x) for (x, y) in cur]
        shapes.append(tuple(rots))
        spawn_x.append((COLS - box) // 2)
        spawn_y.append(-min(c[1] for c in rots[0]))
    return tuple(shapes), tuple(spawn_x), tuple(spawn_y)


SHAPES, SPAWN_X, SPAWN_Y = _build()

# wall kick tries (dx, dy), first one that fits wins
KICKS = ((0, 0), (-1, 0), (1, 0), (0, -1), (-2, 0), (2, 0), (0, -2))


def preview_cells(p):
    """Rotation-0 cells shifted to (0,0) plus (width, height) in cells."""
    cells = SHAPES[p][0]
    mx = min(c[0] for c in cells)
    my = min(c[1] for c in cells)
    out = tuple((c[0] - mx, c[1] - my) for c in cells)
    w = max(c[0] for c in out) + 1
    h = max(c[1] for c in out) + 1
    return out, w, h
