"""Player profiles (nickname + 4-digit PIN) and personal statistics.
Statistics are always computed from games.jsonl, so there is a single source of truth."""
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime

import storage
from referee import RANKS, rank_for, next_rank

PLAYERS_FILE = storage.DATA / "players.json"
RESERVED = {"guest", "detectivebot", "bot"}
TYPES = ["date", "number", "place", "person"]


def _load() -> dict:
    try:
        return json.loads(PLAYERS_FILE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    PLAYERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PLAYERS_FILE.write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")


def _hash(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 100_000).hex()


def check_name(name: str) -> str | None:
    """Returns an error message, or None if the name is fine."""
    name = (name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{2,19}", name):
        return "Choose a name of 3 to 20 letters or numbers."
    if name.lower() in RESERVED:
        return "This name is reserved. Choose another one."
    return None


def create_player(name: str, pin: str, favorites=()) -> tuple[bool, str]:
    name = (name or "").strip()
    err = check_name(name)
    if err:
        return False, err
    if not re.fullmatch(r"\d{4}", pin or ""):
        return False, "The PIN must be exactly 4 digits."
    data = _load()
    if name.lower() in data:
        return False, "This name is already taken. Sign in or choose another name."
    salt = secrets.token_hex(16)
    data[name.lower()] = {"name": name, "salt": salt, "pin_hash": _hash(pin, salt),
                          "favorites": list(favorites), "created": datetime.now().isoformat(timespec="seconds")}
    _save(data)
    return True, name


def check_login(name: str, pin: str) -> bool:
    p = _load().get((name or "").strip().lower())
    return bool(p) and hmac.compare_digest(p["pin_hash"], _hash(pin or "", p["salt"]))


def get_player(name: str) -> dict | None:
    p = _load().get((name or "").strip().lower())
    return {k: v for k, v in p.items() if k not in ("salt", "pin_hash")} if p else None


def set_favorites(name: str, favorites) -> None:
    data = _load()
    if name.lower() in data:
        data[name.lower()]["favorites"] = list(favorites)
        _save(data)


def stats_for(logs: list[dict], name: str) -> dict:
    """Everything the interface shows about one player."""
    mine = [l for l in logs if l.get("player") == "human"
            and str(l.get("nickname", "")).lower() == (name or "").lower()]
    played = len(mine)
    solved = sum(bool(l.get("correct")) for l in mine)
    xp = max(0, sum(int(l.get("xp", l.get("score", 0))) for l in mine))
    streak = 0
    for l in reversed(mine):
        if l.get("correct"):
            streak += 1
        else:
            break
    best = run = 0
    for l in mine:
        run = run + 1 if l.get("correct") else 0
        best = max(best, run)
    by_type = {t: [0, 0] for t in TYPES}
    by_cat: dict[str, list[int]] = {}
    for l in mine:
        for d, k in ((by_type, l.get("tamper_type")), (by_cat, l.get("category"))):
            if k is None:
                continue
            c = d.setdefault(k, [0, 0])
            c[0] += bool(l.get("correct"))
            c[1] += 1
    nxt = next_rank(xp)
    prev_at = max(t for t, n in RANKS if n == rank_for(xp))
    progress = 1.0 if nxt is None else (xp - prev_at) / (nxt[1] - prev_at)

    def avg(key):
        vals = [float(l.get(key, 0)) for l in mine]
        return sum(vals) / len(vals) if vals else 0.0

    seen = []
    for l in mine:
        if l["case_id"] in seen:
            seen.remove(l["case_id"])
        seen.append(l["case_id"])
    return {"played": played, "solved": solved, "accuracy": solved / played if played else None,
            "xp": xp, "rank": rank_for(xp), "next_rank": nxt[0] if nxt else None,
            "next_at": nxt[1] if nxt else None, "progress": max(0.0, min(1.0, progress)),
            "streak": streak, "best_streak": best, "by_type": by_type, "by_cat": by_cat,
            "avg_searches": avg("n_searches"), "avg_questions": avg("n_questions"),
            "avg_seconds": avg("seconds"), "seen_ids": seen,
            "history": [(l.get("tamper_type"), l.get("category"), bool(l.get("correct"))) for l in mine],
            "recent": list(reversed(mine))[:8]}


def weakest_type(stats: dict, min_games: int = 2) -> str | None:
    """The kind of forgery this player misses most (needs a few games)."""
    scored = [(c / n, t) for t, (c, n) in stats["by_type"].items() if n >= min_games]
    return min(scored)[1] if scored else None
