KEY = "tetris"


def load_best(save, level):
    return save.get(KEY, "best" + str(level + 1), 0)


def submit(save, level, score):
    """Store a per-level best; the menu shows the best of all levels."""
    k = "best" + str(level + 1)
    new = score > save.get(KEY, k, 0)
    if new:
        save.set(KEY, k, score)
    top = max(save.get(KEY, "best1", 0), save.get(KEY, "best2", 0), save.get(KEY, "best3", 0))
    save.set(KEY, "best", top)
    return new
