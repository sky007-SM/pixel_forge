# ============================================================
# Save manager: small JSON file, written atomically, only when dirty
# ============================================================
import os
import config

try:
    import json
except ImportError:
    import ujson as json


class SaveManager:
    def __init__(self, path=None):
        self.path = path or config.SAVE_PATH
        self.data = {}
        self.dirty = False
        self._load()

    def _load(self):
        try:
            with open(self.path) as f:
                d = json.load(f)
            if isinstance(d, dict):
                self.data = d
        except Exception:
            self.data = {}

    def get(self, game, key, default=None):
        g = self.data.get(game)
        if g is None:
            return default
        return g.get(key, default)

    def set(self, game, key, value):
        g = self.data.get(game)
        if g is None:
            g = {}
            self.data[game] = g
        if g.get(key) != value:
            g[key] = value
            self.dirty = True

    def flush(self):
        """Write to disk if anything changed (a flash write can stall ~10-50 ms,
        so call it on static screens such as game over)."""
        if not self.dirty:
            return
        tmp = self.path + ".tmp"
        try:
            folder = self.path.rsplit("/", 1)[0] if "/" in self.path else ""
            if folder:
                try:
                    os.mkdir(folder)
                except OSError:
                    pass
            with open(tmp, "w") as f:
                json.dump(self.data, f)
            try:
                os.rename(tmp, self.path)
            except OSError:
                os.remove(self.path)
                os.rename(tmp, self.path)
            self.dirty = False
        except Exception as e:
            print("save failed:", e)
