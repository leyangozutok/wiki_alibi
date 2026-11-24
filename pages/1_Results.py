"""Detective file: YOUR record (if you have a profile) and the Bureau statistics (everybody).
No pandas / pyarrow needed."""
import csv
import io
import json
from collections import defaultdict

import streamlit as st

st.set_page_config(page_title="Wiki Alibi - Detective file", layout="wide", initial_sidebar_state="collapsed")

from players import stats_for, weakest_type
from storage import load_logs, LOG_FILE
from story import TYPE_WORDS
from style import inject, esc, label, bar, progress

inject()
ss = st.session_state
user, guest = ss.get("user"), ss.get("guest")
logs = load_logs()
TYPES = ["date", "number", "place", "person"]


def pct(c, n):
    return 100 * c / n if n else 0.0


def tally(rows, key):
    out = defaultdict(lambda: [0, 0])
    for r in rows:
        out[key(r)][0] += bool(r.get("correct"))
        out[key(r)][1] += 1
    return out


def stat(col, big, small):
    col.markdown(f'<div class="wa-stat"><div class="n">{esc(big)}</div><div class="t">{esc(small)}</div></div>',
                 unsafe_allow_html=True)


# ---------------- top bar ----------------
c1, c2 = st.columns([8, 3])
c1.markdown('<div class="wa-brand">Detective file<small>WIKI ALIBI · THE ARCHIVE BUREAU</small></div>',
            unsafe_allow_html=True)
try:
    c2.page_link("app.py", label="Back to the game")
except Exception:
    c2.markdown('<a href="/" target="_self">Back to the game</a>', unsafe_allow_html=True)

# ---------------- YOUR record ----------------
label("Your record")
if user:
    s = stats_for(logs, user)
    if s["played"] == 0:
        st.markdown(f'<div class="wa-explain"><b>{esc(user)}, your file is empty for now.</b><br>'
                    'A case is written in your file when you press <b>Submit accusation</b>. '
                    'Cases you skip with "New case" are not recorded. Solve your first case and come back.</div>',
                    unsafe_allow_html=True)
    else:
        nxt = f'{s["next_at"] - s["xp"]} XP to reach {s["next_rank"]}' if s["next_rank"] else "You reached the top rank"
        st.markdown(f'<div class="wa-badge"><b>{esc(user)}</b> &nbsp;<span class="r">{esc(s["rank"])}</span> '
                    f'<span class="wa-muted">&nbsp;{s["xp"]} XP · {nxt}</span>{progress(s["progress"])}</div>',
                    unsafe_allow_html=True)
        st.write("")
        a, b, c, d = st.columns(4)
        stat(a, f'{s["solved"]} / {s["played"]}', "cases solved")
        stat(b, f'{s["accuracy"] * 100:.0f}%', "accuracy (luck alone gives 20%)")
        stat(c, str(s["streak"]), f'current streak (best: {s["best_streak"]})')
        stat(d, f'{s["avg_seconds"]:.0f} s', "average time per case")

        label("What fools you")
        rows = "".join(bar(TYPE_WORDS[t].capitalize(), pct(*s["by_type"][t]),
                           f'{pct(*s["by_type"][t]):.0f}%  ({s["by_type"][t][0]}/{s["by_type"][t][1]})'
                           if s["by_type"][t][1] else "not met yet", "me") for t in TYPES)
        st.markdown(rows, unsafe_allow_html=True)
        weak = weakest_type(s)
        st.markdown(f'<div class="wa-muted" style="margin-top:.5rem">'
                    + (f'Your hardest forgery so far: <b>{TYPE_WORDS[weak]}</b>. The game will offer you more of them '
                       f'so you can train.' if weak else 'Play at least 2 cases of each kind and the game will '
                                                          'train your weakest spot.') + '</div>', unsafe_allow_html=True)

        label("Your bets")
        mine = [l for l in logs if l.get("player") == "human" and str(l.get("nickname", "")).lower() == user.lower()]
        conf = tally(mine, lambda r: r.get("confidence", "low"))
        st.markdown("".join(bar(k.capitalize() + " confidence", pct(*conf[k]),
                                f'{pct(*conf[k]):.0f}%  ({conf[k][0]}/{conf[k][1]})' if conf[k][1] else "never used",
                                "me") for k in ("low", "medium", "high")), unsafe_allow_html=True)
        st.markdown('<div class="wa-muted" style="margin-top:.5rem">A good detective is more accurate when '
                    'more confident. If the bars go up from low to high, your instinct is reliable.</div>',
                    unsafe_allow_html=True)

        label("Recent cases")
        body = "".join(
            f'<tr><td>{esc(str(l.get("timestamp", ""))[5:16].replace("T", " "))}</td>'
            f'<td><span class="wa-tag {"ok" if l.get("correct") else "no"}">'
            f'{"Solved" if l.get("correct") else "Missed"}</span></td>'
            f'<td>{esc(TYPE_WORDS.get(l.get("tamper_type"), ""))}</td><td>{esc(l.get("category", ""))}</td>'
            f'<td>{esc(l.get("n_searches", 0))}</td><td>{esc(l.get("n_questions", 0))}</td>'
            f'<td>{esc(l.get("score", 0))}</td></tr>' for l in s["recent"])
        st.markdown('<table class="wa-table"><tr><th>When</th><th>Result</th><th>Forged</th><th>Category</th>'
                    '<th>Searches</th><th>Questions</th><th>Score</th></tr>' + body + '</table>',
                    unsafe_allow_html=True)
elif guest:
    st.markdown('<div class="wa-explain"><b>You are playing as a guest.</b><br>Create a profile on the home page '
                'to keep a personal file: rank, streaks, your weak spots and a game that adapts to you.</div>',
                unsafe_allow_html=True)
else:
    st.markdown('<div class="wa-explain"><b>Sign in on the game page to see your file.</b><br>'
                'The statistics of the whole Bureau are below.</div>', unsafe_allow_html=True)

# ---------------- the Bureau ----------------
label("The Bureau: all detectives")
humans = [l for l in logs if l.get("player") == "human"]
bots = [l for l in logs if l.get("player") == "bot"]
if not logs:
    st.markdown('<div class="wa-muted">No case has been recorded yet.</div>', unsafe_allow_html=True)
else:
    hc, bc = sum(bool(l.get("correct")) for l in humans), sum(bool(l.get("correct")) for l in bots)
    st.markdown(
        bar("Humans", pct(hc, len(humans)), f"{pct(hc, len(humans)):.0f}%  ({hc}/{len(humans)})", "all")
        + bar("Detective Bot", pct(bc, len(bots)), f"{pct(bc, len(bots)):.0f}%  ({bc}/{len(bots)})" if bots else "has not played", "bot")
        + bar("Pure luck", 20, "20%", "rand"), unsafe_allow_html=True)

    h, b = tally(humans, lambda r: r.get("tamper_type")), tally(bots, lambda r: r.get("tamper_type"))
    label("Which forgeries are the hardest?")
    html = ""
    for t in TYPES:
        if h[t][1]:
            html += bar(TYPE_WORDS[t].capitalize(), pct(*h[t]), f"{pct(*h[t]):.0f}%  ({h[t][0]}/{h[t][1]})", "all")
        if b[t][1]:
            html += bar("", pct(*b[t]), f"{pct(*b[t]):.0f}%  ({b[t][0]}/{b[t][1]})", "bot")
    st.markdown(html or '<div class="wa-muted">Not enough games yet.</div>', unsafe_allow_html=True)
    st.markdown('<div class="wa-muted">Dark bars: humans. Grey bars: the Detective Bot.</div>', unsafe_allow_html=True)

mode = (bots[-1].get("bot_mode") if bots else None)
now = ("The bot is in <b>random mode</b> for now: it guesses, so it finds the forgery about 1 time in 5. "
       "That is the line every human should beat." if mode == "random" else
       "The bot currently uses the AI." if mode == "ai" else
       "The bot has not played yet. Run <code>python run_bot.py</code> to let it play every case.")
label("How does the Detective Bot work?")
st.markdown('<div class="wa-explain"><b>The Detective Bot is a computer rival.</b> It plays the same cases as you, '
            'so we can see who finds the forgery most often: a human, a machine, or pure luck.'
            '<ol><li>It reads the 5 clues.</li><li>It chooses up to 3 Wikipedia searches, like you.</li>'
            '<li>It reads the best articles, names the forgery and places its bet.</li></ol>'
            f'{now}</div>', unsafe_allow_html=True)

# ---------------- export ----------------
with st.expander("Export the data (for the user study)"):
    st.markdown(f'<div class="wa-muted">{len(logs)} games recorded in <code>{esc(LOG_FILE.name)}</code>. '
                'On a hosted app this file can be erased when the app restarts: download it after each session.</div>',
                unsafe_allow_html=True)
    if logs:
        buf = io.StringIO()
        keys = sorted({k for l in logs for k in l})
        w = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(logs)
        d1, d2, _ = st.columns([2, 2, 6])
        d1.download_button("Download CSV", buf.getvalue(), "games.csv", "text/csv")
        d2.download_button("Download JSONL", "\n".join(json.dumps(x, ensure_ascii=False) for x in logs),
                           "games.jsonl", "application/jsonl")
