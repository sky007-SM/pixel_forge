# ============================================================
# PIXELFORGE wordmark colours + the small header text used by the menu.
# (The big boot art lives in system/boot.py so it can be unloaded after boot.)
# ============================================================
from config import rgb
from assets.fonts import Text

TEXT = "PIXELFORGE"
EMBER_ROWS = (
    rgb(255, 232, 120), rgb(255, 206, 76), rgb(255, 168, 40), rgb(255, 128, 24),
    rgb(238, 98, 24), rgb(206, 66, 28), rgb(168, 44, 30),
)
SHADOW = rgb(46, 18, 12)


def make_wordmark():
    """Header wordmark, 2x scale: a text mask; draw it with EMBER_ROWS and SHADOW colours."""
    return Text(TEXT, 2)
