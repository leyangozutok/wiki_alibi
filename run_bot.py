"""Detective Bot plays every case and writes to the log (player = bot). Usage: python run_bot.py"""
import time
from agents import bot_play
from referee import score_game, make_log
from storage import load_cases, save_log

recs = load_cases()
hits = 0
for rec in recs:
    t0 = time.time()
    guess, n = bot_play(rec)
    res = score_game(rec.case, guess.accused_id, n, 0, guess.confidence)
    log = make_log(rec.case, res, "bot", "DetectiveBot", guess.accused_id, n, 0, time.time() - t0)
    log["bot_mode"] = "random" if guess.reason in ("random baseline", "fallback") else "ai"
    save_log(log)
    hits += res["correct"]
    print(rec.case.case_id, rec.case.wiki_title, "OK" if res["correct"] else "miss", f"({n} searches)")
print(f"Bot accuracy: {hits}/{len(recs)}")
