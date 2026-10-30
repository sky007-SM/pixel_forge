# ============================================================
# 5x7 bitmap font + text sprite renderer
# ============================================================
import uctypes
from system.renderer import blit_m

FONT = {
    "A": (14, 17, 17, 31, 17, 17, 17), "B": (30, 17, 17, 30, 17, 17, 30),
    "C": (14, 17, 16, 16, 16, 17, 14), "D": (30, 17, 17, 17, 17, 17, 30),
    "E": (31, 16, 16, 30, 16, 16, 31), "F": (31, 16, 16, 30, 16, 16, 16),
    "G": (14, 17, 16, 23, 17, 17, 14), "H": (17, 17, 17, 31, 17, 17, 17),
    "I": (31, 4, 4, 4, 4, 4, 31),      "J": (7, 2, 2, 2, 2, 18, 12),
    "K": (17, 18, 20, 24, 20, 18, 17), "L": (16, 16, 16, 16, 16, 16, 31),
    "M": (17, 27, 21, 21, 17, 17, 17), "N": (17, 25, 25, 21, 19, 19, 17),
    "O": (14, 17, 17, 17, 17, 17, 14), "P": (30, 17, 17, 30, 16, 16, 16),
    "Q": (14, 17, 17, 17, 21, 18, 13), "R": (30, 17, 17, 30, 20, 18, 17),
    "S": (15, 16, 16, 14, 1, 1, 30),   "T": (31, 4, 4, 4, 4, 4, 4),
    "U": (17, 17, 17, 17, 17, 17, 14), "V": (17, 17, 17, 17, 17, 10, 4),
    "W": (17, 17, 17, 21, 21, 27, 17), "X": (17, 17, 10, 4, 10, 17, 17),
    "Y": (17, 17, 10, 4, 4, 4, 4),     "Z": (31, 1, 2, 4, 8, 16, 31),
    "0": (14, 17, 19, 21, 25, 17, 14), "1": (4, 12, 4, 4, 4, 4, 14),
    "2": (14, 17, 1, 2, 4, 8, 31),     "3": (30, 1, 1, 14, 1, 1, 30),
    "4": (2, 6, 10, 18, 31, 2, 2),     "5": (31, 16, 16, 30, 1, 1, 30),
    "6": (14, 16, 16, 30, 17, 17, 14), "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14), "9": (14, 17, 17, 15, 1, 1, 14),
    ":": (0, 4, 4, 0, 4, 4, 0),        " ": (0, 0, 0, 0, 0, 0, 0),
    ".": (0, 0, 0, 0, 0, 12, 12),      "-": (0, 0, 0, 31, 0, 0, 0),
    "!": (4, 4, 4, 4, 4, 0, 4),        "?": (14, 17, 1, 2, 4, 0, 4),
    "/": (1, 1, 2, 4, 8, 16, 16),      ">": (16, 8, 4, 2, 4, 8, 16),
    "<": (1, 2, 4, 8, 4, 2, 1),        "+": (0, 4, 4, 31, 4, 4, 0),
    "'": (4, 4, 8, 0, 0, 0, 0),        "%": (24, 25, 2, 4, 8, 19, 3),
    "=": (0, 0, 31, 0, 31, 0, 0),
}
_BLANK = FONT[" "]


def text_width(text, scale=1):
    return len(text) * 6 * scale - scale if text else 0


class Text:
    """Text stored as a 1-bit-per-pixel mask (16x smaller than a colour sprite).

    Draw one row with:  blit_m(dst, x, t.addr + k * t.rb, (t.w << 16) | colour)
    where k is the row inside the text and colour is a P16 value, so one mask
    serves any colour (bright / dim / gradient rows)."""

    def __init__(self, text, scale=1):
        n = len(text)
        w = text_width(text, scale)
        self.w = w
        self.h = 7 * scale
        self.scale = scale
        self.rb = (w + 7) >> 3
        self.buf = bytearray(self.rb * self.h)
        self.addr = uctypes.addressof(self.buf)
        buf = self.buf
        rb = self.rb
        for i in range(n):
            g = FONT.get(text[i], _BLANK)
            gx0 = i * 6 * scale
            for gy in range(7):
                bits = g[gy]
                if not bits:
                    continue
                for gx in range(5):
                    if bits & (16 >> gx):
                        x0 = gx0 + gx * scale
                        for sy in range(scale):
                            o = (gy * scale + sy) * rb
                            for sx in range(scale):
                                x = x0 + sx
                                buf[o + (x >> 3)] |= 0x80 >> (x & 7)

    def row(self, k, x, dst, colour):
        blit_m(dst, x, self.addr + k * self.rb, (self.w << 16) | colour)


class Digits:
    """Number display without allocation: one 1-bit mask per glyph, drawn row by row.
    Glyphs: 0-9 and X. draw(dst, x, k, colour) draws row k of the current value."""

    @staticmethod
    def make_glyphs(scale, chars="0123456789X"):
        """The 11 glyph masks (0-9, X) for one scale; share one set between fields."""
        g = {}
        for ch in chars:
            g[ch] = Text(ch, scale)
        return g
    
    def set_text(self, text_string):
        """Directly sets the text to be displayed, respecting the maximum character limit."""
        self.value = -1  # Reset numerical value tracking
        self.txt = text_string[:self.maxch]

    
    def __init__(self, scale, maxch, prefix="", glyphs=None):
        self.scale = scale
        self.glyph = glyphs if glyphs is not None else Digits.make_glyphs(scale)
        self.step = 6 * scale
        self.maxch = maxch
        self.prefix = prefix
        self.w = maxch * self.step - scale
        self.h = 7 * scale
        self.value = -1
        self.txt = ""
        self.set(0)

    def set(self, v):
        if v != self.value:
            self.value = v
            self.txt = (self.prefix + str(v))[:self.maxch]

    def draw(self, dst, x, k, colour):
        step = self.step
        gl = self.glyph
        for ch in self.txt:
            g = gl[ch]
            blit_m(dst, x, g.addr + k * g.rb, (g.w << 16) | colour)
            x += step
