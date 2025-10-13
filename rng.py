# rng.py
import random

def weighted_choice(items):
    # items: list[tuple[item, weight]]
    total = sum(w for _, w in items)
    r = random.uniform(0, total)
    upto = 0.0
    for item, weight in items:
        if upto + weight >= r:
            return item
        upto += weight
    return items[-1][0]
