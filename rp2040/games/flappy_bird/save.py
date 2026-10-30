KEY = "flappy_bird"


def load_best(save):
    return save.get(KEY, "best", 0)


def submit(save, score):
    """Store the score if it is a new best. Returns True when it is."""
    if score > save.get(KEY, "best", 0):
        save.set(KEY, "best", score)
        return True
    return False
