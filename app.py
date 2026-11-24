"""Wiki Alibi - the game. Flow: Home (profile) -> Case (briefing, evidence, witness, archive, accusation)
-> Verdict and debrief -> next case. Progress is kept per player (see docs/ARCHITECTURE.md)."""
import datetime as dt
import os
import random
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# set_page_config MUST be the first Streamlit command
st.set_page_config(page_title="Wiki Alibi", layout="wide", initial_sidebar_state="collapsed")

# API key from Streamlit secrets (never on GitHub). Only read it if a secrets file exists.
_SECRET_FILES = [Path.home() / ".streamlit" / "secrets.toml",
                 Path(__file__).parent / ".streamlit" / "secrets.toml"]
if any(p.exists() for p in _SECRET_FILES):
    try:
        for _k in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_DAILY_LIMIT"):
            if _k in st.secrets:
                os.environ.setdefault(_k, str(st.secrets[_k]))
    except Exception:
        pass

import wiki as wikimod
from agents import persona_for, coach_note, briefing_for
from game_logic import ask, do_search, NO_MORE_QUESTIONS, NO_RESULT, SEARCH_ERROR
from picker import pick_case
from players import create_player, check_login, get_player, stats_for, weakest_type
from referee import (score_game, make_log, FREE_SEARCHES, FREE_QUESTIONS, MAX_QUESTIONS, MAX_INPUT_CHARS)
from storage import load_cases, save_log, load_logs
from story import codename, witness_identity, verdict_text, greeting
from style import inject, esc, label, progress
from wiki import get_article_html, render_page, wiki_url, WikiError

inject()
ss = st.session_state
for _k, _v in (("user", None), ("guest", False), ("game", None), ("mode", "Random case"),
               ("login_msg", ""), ("search_outcome", None)):
    ss.setdefault(_k, _v)

CASES = load_cases()
if not CASES:
    st.error("No cases found. Run `python make_demo_cases.py` or `python build_cases.py`.")
    st.stop()
CATEGORIES = sorted({r.case.category for r in CASES})


def me() -> str:
    """Name written in the game log."""
    return ss.user or "Guest"


# ====================== callbacks (they run before the page is drawn) ======================
def on_sign_in():
    name, pin = ss.get("in_name", "").strip(), ss.get("in_pin", "")
    if check_login(name, pin):
        ss.user, ss.guest, ss.login_msg, ss.game = get_player(name)["name"], False, "", None
        ss.pop("seen_session", None)
    else:
        ss.login_msg = "Unknown name or wrong PIN."


def on_create():
    ok, msg = create_player(ss.get("new_name", ""), ss.get("new_pin", ""), ss.get("new_favs", []))
    if ok:
        ss.user, ss.guest, ss.login_msg, ss.game = msg, False, "", None
        ss.pop("seen_session", None)
    else:
        ss.login_msg = msg


def on_guest():
    ss.user, ss.guest, ss.game, ss.login_msg = None, True, None, ""
    ss.pop("seen_session", None)


def on_sign_out():
    ss.user, ss.guest, ss.game, ss.login_msg = None, False, None, ""
    ss.pop("seen_session", None)


def choose_random_case() -> int:
    """Unplayed cases first; the player's favorite topics and weak spots count (see picker.py)."""
    stats = stats_for(load_logs(), ss.user) if ss.user else None
    seen = list(stats["seen_ids"]) if stats else []
    for cid in ss.get("seen_session", []):          # cases opened in this visit, even if skipped
        if cid in seen:
            seen.remove(cid)
        seen.append(cid)
    favs = (get_player(ss.user) or {}).get("favorites", []) if ss.user else []
    idx = pick_case(CASES, seen, stats["history"] if stats else [], favorites=favs)
    ss.setdefault("seen_session", []).append(CASES[idx].case.case_id)
    return idx


def start_game(mode: str):
    idx = dt.date.today().toordinal() % len(CASES) if mode == "Daily case" else choose_random_case()
    for k in ("q_input", "acc_pick", "acc_conf", "s_query"):
        ss.pop(k, None)
    ss.search_outcome = None
    ss.game = {"idx": idx, "mode": mode, "start": time.time(), "searches": 0, "questions": 0,
               "chat": [], "results": [], "queries": [], "reading": None, "read_error": None,
               "done": False, "result": None, "pick": None, "redactions": 0, "coach": None,
               "rank_up": None}


def on_ask():
    g = ss.game
    rec = CASES[g["idx"]]
    ask(g, rec.case, rec.article, ss.get("q_input", ""), persona_for(rec.case.case_id))
    ss["q_input"] = ""


def on_search():
    ss.search_outcome = do_search(ss.game, ss.get("s_query", ""), lambda q: wikimod.search_wiki(q))


def on_accuse():
    g = ss.game
    if g["done"]:
        return                                              # never log a game twice
    case = CASES[g["idx"]].case
    pick = ss.get("acc_pick", 1)
    conf = str(ss.get("acc_conf", "Low")).lower()
    before = stats_for(load_logs(), ss.user) if ss.user else None
    result = score_game(case, pick, g["searches"], g["questions"], conf)
    save_log(make_log(case, result, "human", me(), pick, g["searches"], g["questions"],
                      time.time() - g["start"], title_redactions=g.get("redactions", 0)))
    after = stats_for(load_logs(), ss.user) if ss.user else None
    g["done"], g["result"], g["pick"] = True, result, pick
    g["rank_up"] = after["rank"] if before and after["rank"] != before["rank"] else None
    g["coach"] = coach_note(case, result["correct"], g["searches"], g["questions"], g.get("queries", []),
                            ss.user or "Detective", weakest_type(after) if after else None).model_dump()


def load_article(title: str):
    g = ss.game
    g["read_error"] = None
    try:
        g["reading"] = get_article_html(title)           # (real title, html)
    except WikiError:
        g["reading"], g["read_error"] = None, f"Could not load '{title}'. Check your connection and try again."


def close_article():
    ss.game["reading"] = None


def show_html(doc: str, height: int = 560):
    if hasattr(st, "iframe"):
        st.iframe(doc, height=height)
    else:
        components.html(doc, height=height, scrolling=True)


# ====================== top bar ======================
stats = stats_for(load_logs(), ss.user) if ss.user else None
c_brand, c_badge, c_btn = st.columns([3, 4, 4])
c_brand.markdown('<div class="wa-brand">Wiki Alibi<small>THE ARCHIVE BUREAU</small></div>', unsafe_allow_html=True)
if stats:
    nxt = f'{stats["next_at"] - stats["xp"]} XP to {stats["next_rank"]}' if stats["next_rank"] else "top rank"
    c_badge.markdown(f'<div class="wa-badge"><b>{esc(ss.user)}</b> &nbsp;<span class="r">{esc(stats["rank"])}</span>'
                     f'<span class="wa-muted"> &nbsp;{stats["xp"]} XP, {nxt}</span>{progress(stats["progress"])}</div>',
                     unsafe_allow_html=True)
elif ss.guest:
    c_badge.markdown('<div class="wa-badge"><b>Guest</b><br><span class="wa-muted">Your progress is not saved. '
                     'Create a profile to keep it.</span></div>', unsafe_allow_html=True)
with c_btn:
    b1, b2, b3 = st.columns(3)
    if ss.user or ss.guest:
        if ss.game is not None:
            b1.button("New case", on_click=start_game, args=(ss.mode,), key="top_new")
        b2.page_link("pages/1_Results.py", label="Detective file")
        b3.button("Sign out", on_click=on_sign_out, key="top_out")

g = ss.game

# ====================== HOME ======================
if g is None:
    st.markdown("<br>", unsafe_allow_html=True)
    left, right = st.columns([6, 5], gap="large")
    with left:
        st.markdown('<div class="wa-hero">One fact in the file is a <em>forgery</em>.<br>Can you find it?</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="wa-lead">The Archive Bureau receives dossiers built from real Wikipedia articles. '
                    'Before they are published, a forger changes one fact. Four clues are true, one is false. '
                    'Question a witness who read the altered file, check the real archive, then name the forgery.</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="wa-steps"><span>1 Read the clues</span><span>2 Question the witness</span>'
                    '<span>3 Check Wikipedia</span><span>4 Accuse and bet</span></div>', unsafe_allow_html=True)
    with right:
        if ss.user or ss.guest:
            who = ss.user or "Guest"
            played = stats["played"] if stats else 0
            st.markdown(f'<div class="wa-hero" style="font-size:1.7rem">{esc(greeting(who, played))}</div>',
                        unsafe_allow_html=True)
            if stats and played:
                s1, s2, s3 = st.columns(3)
                for col, n, t in ((s1, f'{stats["solved"]}/{played}', "cases solved"),
                                  (s2, f'{stats["streak"]}', "current streak"),
                                  (s3, f'{stats["best_streak"]}', "best streak")):
                    col.markdown(f'<div class="wa-stat"><div class="n">{n}</div><div class="t">{t}</div></div>',
                                 unsafe_allow_html=True)
                st.write("")
            elif ss.guest:
                st.markdown('<div class="wa-muted">Playing as a guest. Your cases are counted in the Bureau '
                            'statistics, but not saved in a personal file.</div>', unsafe_allow_html=True)
            st.radio("Case mode", ["Random case", "Daily case"], key="mode", horizontal=True,
                     help="The daily case is the same for every player today.")
            st.button("Open the next case", type="primary", on_click=start_game, args=(ss.mode,))
        else:
            label("Your desk at the Bureau")
            st.radio("Access", ["Sign in", "Create profile", "Guest"], key="home_mode", horizontal=True,
                     label_visibility="collapsed")
            mode = ss.get("home_mode", "Sign in")
            if mode == "Sign in":
                with st.form("sign_in"):
                    st.text_input("Name", key="in_name", max_chars=20)
                    st.text_input("PIN (4 digits)", key="in_pin", type="password", max_chars=4)
                    st.form_submit_button("Sign in", type="primary", on_click=on_sign_in)
            elif mode == "Create profile":
                with st.form("create"):
                    st.text_input("Choose a name", key="new_name", max_chars=20)
                    st.text_input("Choose a 4-digit PIN", key="new_pin", type="password", max_chars=4)
                    st.multiselect("Favorite topics (optional, you will see them more often)", CATEGORIES,
                                   key="new_favs")
                    st.form_submit_button("Create my profile", type="primary", on_click=on_create)
                st.markdown('<div class="wa-muted">Only your name and a protected PIN are stored. '
                            'Your progress follows you every time you sign in.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="wa-muted">Try the game without a profile. Nothing is saved for you.</div>',
                            unsafe_allow_html=True)
                st.button("Continue as a guest", type="primary", on_click=on_guest)
            if ss.login_msg:
                st.error(ss.login_msg)
    st.stop()

# ====================== CASE ======================
rec = CASES[g["idx"]]
case, article = rec.case, rec.article
persona = persona_for(case.case_id)
w_name, w_desc = witness_identity(persona)
left, right = st.columns([5, 6], gap="large")

with left:
    stamp_html = ""
    if g["done"]:
        ok = g["result"]["correct"]
        stamp_html = f'<span class="wa-stamp {"ok" if ok else ""}">{"Solved" if ok else "Unsolved"}</span>'
    else:
        stamp_html = '<span class="wa-stamp">Confidential</span>'
    st.markdown(f'<div class="wa-casehead"><div><div class="wa-casenum">Case file no. {g["idx"] + 1:03d}'
                f' &nbsp;·&nbsp; {esc(case.category)}</div><div class="wa-casename">{esc(codename(case.case_id))}</div>'
                f'</div>{stamp_html}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="wa-brief">{esc(briefing_for(case, persona))}</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="wa-steps"><span>1 Read the clues</span><span>2 Question the witness</span>'
                '<span>3 Check Wikipedia</span><span>4 Accuse and bet</span></div>', unsafe_allow_html=True)

    label("Evidence")
    st.markdown("".join(f'<div class="wa-card"><span class="wa-num">{c.id}</span><span>{esc(c.text)}</span></div>'
                        for c in case.clues), unsafe_allow_html=True)
    st.markdown(f'<div class="wa-notebook">Notebook: {g["searches"]} searches ({FREE_SEARCHES} free) · '
                f'{g["questions"]}/{MAX_QUESTIONS} questions ({FREE_QUESTIONS} free)</div>', unsafe_allow_html=True)

    label("Witness")
    st.markdown(f'<div class="wa-witness"><div class="wa-avatar">{esc(w_name.split()[-1][0])}</div>'
                f'<div><b>{esc(w_name)}</b><br><span class="wa-muted">{esc(w_desc)}</span></div></div>',
                unsafe_allow_html=True)
    st.markdown("".join(
        f'<div class="wa-msg {"you" if m["role"] == "user" else "them"}">'
        f'<div class="wa-who">{"You" if m["role"] == "user" else esc(w_name)}</div>'
        f'<div class="wa-bubble">{esc(m["text"])}</div></div>' for m in g["chat"]), unsafe_allow_html=True)
    no_q = g["questions"] >= MAX_QUESTIONS or g["done"]
    with st.form("ask"):
        f1, f2 = st.columns([5, 1])
        f1.text_input("Question", key="q_input", label_visibility="collapsed", max_chars=MAX_INPUT_CHARS,
                      disabled=no_q, placeholder="Ask the witness a question")
        f2.form_submit_button("Ask", disabled=no_q, on_click=on_ask)
    if g["questions"] >= MAX_QUESTIONS:
        st.markdown(f'<div class="wa-muted">{NO_MORE_QUESTIONS}</div>', unsafe_allow_html=True)
    elif not g["chat"]:
        st.markdown('<div class="wa-muted">Careful: the witness read the altered file, so a repeated clue proves '
                    'nothing. Compare with the real archive.</div>', unsafe_allow_html=True)

    if not g["done"]:
        label("Accusation")
        with st.form("accuse"):
            st.radio("Which clue is the forgery?", [c.id for c in case.clues], key="acc_pick", horizontal=True)
            st.radio("How sure are you?", ["Low", "Medium", "High"], key="acc_conf", horizontal=True)
            st.form_submit_button("Submit accusation", type="primary", on_click=on_accuse)
        st.markdown('<div class="wa-muted">Your confidence is a bet on your XP. Low: no risk. '
                    'Medium: +15 if right, -10 if wrong. High: +30 or -25.</div>', unsafe_allow_html=True)
    else:
        r = g["result"]
        label("Verdict")
        st.markdown(f'<div class="wa-verdict">{"Case closed" if r["correct"] else "The forger walks free"}</div>',
                    unsafe_allow_html=True)
        st.markdown(esc(verdict_text(case, r["correct"], g["pick"], next(c.id for c in case.clues if c.is_false))))
        pen = r["search_penalty"] + r["question_penalty"]
        st.markdown(f'<div class="wa-muted">Score {r["score"]} · XP {r["xp"]:+d}'
                    + (f' · {pen} points lost to extra searches and questions' if pen else "") + '</div>',
                    unsafe_allow_html=True)
        if g.get("rank_up"):
            st.markdown(f'<div class="wa-up">Promotion! You are now {esc(g["rank_up"])}.</div>', unsafe_allow_html=True)
        st.markdown(f'**Original:** {esc(case.original_sentence)}  \n**Forged:** ~~{esc(case.false_sentence)}~~  \n'
                    f'Source: [{esc(case.wiki_title)}]({wiki_url(case.wiki_title)})')
        if g.get("coach"):
            st.markdown(f'<div class="wa-note"><b>Chief Inspector Vale</b>{esc(g["coach"]["summary"])}<br>'
                        f'<i>{esc(g["coach"]["tip"])}</i></div>', unsafe_allow_html=True)
        bots = [l for l in load_logs() if l.get("player") == "bot" and l.get("case_id") == case.case_id]
        if bots:
            b = bots[-1]
            kind = "random guess" if b.get("bot_mode") == "random" else "AI"
            st.markdown(f'<div class="wa-muted">The Detective Bot ({kind}) {"found" if b.get("correct") else "missed"} '
                        f'this forgery after {b.get("n_searches", 0)} searches.</div>', unsafe_allow_html=True)
        if ss.user:
            st.markdown('<div class="wa-muted">Saved in your detective file.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="wa-muted">You are a guest: create a profile next time to keep your record.</div>',
                        unsafe_allow_html=True)
        share = (f"Wiki Alibi no. {g['idx'] + 1:03d}, {dt.date.today()}\n"
                 f"{'Solved' if r['correct'] else 'Fooled'} ({case.tamper_type})\n"
                 f"Searches {g['searches']}, questions {g['questions']}, bet {r['confidence']}, score {r['score']}")
        with st.expander("Share result"):
            st.code(share, language=None)
        st.button("Next case", type="primary", on_click=start_game, args=(ss.mode,))

with right:
    label("The real archive: Wikipedia")
    with st.form("search"):
        s1, s2 = st.columns([5, 1])
        s1.text_input("Search", key="s_query", label_visibility="collapsed", max_chars=MAX_INPUT_CHARS,
                      placeholder="Search Wikipedia to check a clue", disabled=g["done"])
        s2.form_submit_button("Search", disabled=g["done"], on_click=on_search)
    outcome = ss.search_outcome
    if outcome == "empty":
        st.markdown(f'<div class="wa-muted">{NO_RESULT}</div>', unsafe_allow_html=True)
    elif outcome == "error":
        st.error(SEARCH_ERROR)
    if g.get("read_error"):
        st.error(g["read_error"])

    def results_list():
        for i, res in enumerate(g["results"]):
            c1, c2 = st.columns([8, 2])
            c1.markdown(f"**{esc(res['title'])}**<br><span class='wa-muted'>{esc(res['snippet'])}</span>",
                        unsafe_allow_html=True)
            c2.button("Open", key=f"read_{i}", on_click=load_article, args=(res["title"],))

    if g["reading"]:
        title, page = g["reading"]
        h1, h2, h3 = st.columns([5, 3, 2])
        h1.markdown(f'<div class="wa-brand" style="font-size:1.3rem">{esc(title)}</div>', unsafe_allow_html=True)
        h2.link_button("Open on Wikipedia", wiki_url(title))
        h3.button("Close", key="close_article", on_click=close_article)
        show_html(render_page(title, page), 560)
        if g["results"]:
            with st.expander("Other results"):
                results_list()
    elif g["results"]:
        results_list()
    else:
        st.markdown(f'<div class="wa-muted">Your first {FREE_SEARCHES} searches are free, each extra search costs '
                    f'5 points. Search a date, a name or a place from the clues and compare.</div>',
                    unsafe_allow_html=True)
