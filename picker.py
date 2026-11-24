"""Smarter 'random case': never repeats until everything was played, keeps a good mix,
leans towards the player's favorite topics and trains the kind of forgery they miss most."""
import random
from collections import Counter


def pick_case(cases, seen_ids, history, rng=random, favorites=()) -> int:
    """cases: list of CaseRecord. seen_ids: case_ids this player already got (oldest first).
    history: [(tamper_type, category) or (tamper_type, category, correct), ...] oldest first.
    favorites: categories the player likes (they are twice as likely)."""
    n = len(cases)
    if n <= 1:
        return 0
    seen = set(seen_ids)
    pool = [i for i, r in enumerate(cases) if r.case.case_id not in seen]
    if not pool:                                              # everything played: restart
        recent = set(seen_ids[-min(3, n - 1):])
        pool = [i for i, r in enumerate(cases) if r.case.case_id not in recent]
    recent_h = history[-8:]
    types = Counter(h[0] for h in recent_h)
    cats = Counter(h[1] for h in recent_h)
    score = {}                                                # accuracy by type (needs the 3rd item)
    for h in history:
        if len(h) >= 3:
            c = score.setdefault(h[0], [0, 0])
            c[0] += bool(h[2])
            c[1] += 1
    fav = set(favorites)
    weights = []
    for i in pool:
        c = cases[i].case
        w = 1 / ((1 + types[c.tamper_type]) * (1 + cats[c.category]))      # variety
        if c.category in fav:
            w *= 2                                                          # personal taste
        if c.tamper_type in score:
            ok, tot = score[c.tamper_type]
            w *= 1.5 - (ok + 1) / (tot + 2)                                 # train weak spots
        weights.append(w)
    return rng.choices(pool, weights=weights)[0]
