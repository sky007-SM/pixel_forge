# ============================================================
# Progress: highest unlocked level (1..9), finished flag, best score.
# Same ctx.save get/set/flush interface as Flappy Bird. Flush only on a static
# screen (a flash write stalls the frame loop).
# ============================================================
KEY = "shards"


def load_level(save):
    n = save.get(KEY, "level", 1)
    return n if 1 <= n <= 9 else 1


def unlock(save, n):
    """Remember that level n is reachable. Returns True if it changed."""
    if n > 9:
        n = 9
    if n > save.get(KEY, "level", 1):
        save.set(KEY, "level", n)
        return True
    return False


def set_finished(save):
    save.set(KEY, "done", 1)


def submit_score(save, score):
    if score > save.get(KEY, "best", 0):
        save.set(KEY, "best", score)
        return True
    return False


def best(save):
    return save.get(KEY, "best", 0)
