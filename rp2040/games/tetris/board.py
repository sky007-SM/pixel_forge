# ============================================================
# Board: 10 x 20 grid of colour indices (0 = empty, 1..7 = pieces)
# ============================================================
import random
from games.tetris.settings import COLS, ROWS


class Board:
    def __init__(self):
        self.rows = [bytearray(COLS) for _ in range(ROWS)]

    def clear(self):
        for r in self.rows:
            for c in range(COLS):
                r[c] = 0

    def fits(self, shape, px, py):
        rows = self.rows
        for (x, y) in shape:
            cx = px + x
            cy = py + y
            if cx < 0 or cx >= COLS or cy >= ROWS:
                return False
            if cy >= 0 and rows[cy][cx]:
                return False
        return True

    def drop_y(self, shape, px, py):
        while self.fits(shape, px, py + 1):
            py += 1
        return py

    def lock(self, shape, px, py, color):
        rows = self.rows
        for (x, y) in shape:
            cy = py + y
            if cy >= 0:
                rows[cy][px + x] = color

    def full_rows(self):
        out = []
        for r in range(ROWS):
            if all(self.rows[r]):                 # no empty cell (bytearray has no int 'in' on MicroPython)
                out.append(r)
        return out

    def remove_row(self, r):
        self.rows.pop(r)
        self.rows.insert(0, bytearray(COLS))

    def fill_random(self, n):
        """Level 3: n random rows at the bottom, each with holes, never a full row."""
        for i in range(n):
            row = self.rows[ROWS - 1 - i]
            while True:
                filled = 0
                for c in range(COLS):
                    if random.getrandbits(8) < 168:           # ~65 % dense
                        row[c] = random.randint(1, 7)
                        filled += 1
                    else:
                        row[c] = 0
                if 5 <= filled <= COLS - 1:
                    break
