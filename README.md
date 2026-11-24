# Wiki Alibi

A detective game where one clue in the case file is false, and you must prove it with Wikipedia.
Course project: *Introduction to Engineering Design* (AI agent proposal, PRD + TRD).

Each case comes from a real Wikipedia article: 5 clues, 4 true and 1 altered (a date, a number, a place or a
person). You can question a witness (an AI agent that remembers the *altered* version), search Wikipedia,
then accuse a clue. The score is computed by plain Python code, never by an LLM.

## 1. Quick start (works offline, no API needed)

```
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Nineteen hand-made cases are included. In this **mock mode** (no API) the witness answers from its memory, in
character, the Narrator and the Coach use templates, and the Detective Bot guesses at random (the 20% baseline).
Wikipedia search needs an internet connection; everything else works offline.

**Profiles.** On the home page create a profile (a name and a 4-digit PIN) to keep your progress: rank, XP, streaks,
your weak spots and the cases you already met. You can also play as a guest. See `docs/ARCHITECTURE.md` for the
flow of the game (diagrams).

## 2. Project structure

| File | Role |
|------|------|
| `app.py` | Streamlit interface: home (profiles), case (investigation / Wikipedia), verdict and debrief |
| `pages/1_Results.py` | **Detective file**: your record, your weak spots, the Bureau statistics, how the bot works (no pandas needed) |
| `style.py`, `story.py` | Look of the pages / storytelling texts (codenames, briefings, verdicts, coach templates) |
| `players.py` | Profiles (name + hashed PIN) and personal statistics computed from the log |
| `rules_builder.py` | Case Builder **without AI** (for `build_cases.py --rules`) |
| `models.py` | Pydantic schemas (`Case`, `LLMCase`, `WitnessAnswer`, `BotGuess`) |
| `referee.py` | **Referee, plain Python**: case validation (FR3 a-d), title redaction, scoring, ranks, log record |
| `game_logic.py` | Behavior rules: 5-question limit, search counting, Wikipedia timeout (PDF 2.4) |
| `agents.py` | Case Builder, **Narrator** (story introduction), Informant (witness), **Coach** (personal debrief), Detective Bot |
| `llm.py` | **The only file that talks to an LLM** (`call_llm`), mock mode, daily call limit, usage log |
| `wiki.py` | Wikipedia client: search (3 s timeout), article cache, Wikipedia-style page view |
| `picker.py` | Next case: no repeat until all are played, favorite topics, trains your weak spots |
| `storage.py` | `cases.json`, `games.jsonl` |
| `build_cases.py` | Builds 150 cases from 100 articles, with a validation report |
| `run_bot.py` | Detective Bot plays every case |
| `analyze.py` | Charts and summary for the user study (pandas + matplotlib) |
| `survey_questions.md`, `data/survey_template.csv` | The 5-question survey |
| `docs/UPDATES_vs_WEEK8.md` | Technical changes since the week 8 proposal (for the final report) |
| `docs/ARCHITECTURE.md` | Diagrams: user flow, components, sequence of a game, data model |
| `tests/` | 104 automatic tests |

Data: `data/topics.csv` (100 titles, 7 categories), `data/cases.json` (cases + article text),
`data/articles/` (cached articles), `data/games.jsonl` (one line per game).

## 3. Connect the teacher's API

Only `llm.py` talks to the LLM. By default it speaks the OpenAI-compatible `/chat/completions` format
(JSON mode). Configure it with 5 settings:

| Setting | Meaning |
|---------|---------|
| `LLM_PROVIDER` | `mock` (default, offline) or `openai_compat` |
| `LLM_API_KEY` | your key |
| `LLM_BASE_URL` | default `https://api.openai.com/v1`, or the endpoint given by the teacher |
| `LLM_MODEL` | default `gpt-4o-mini`, or the model given by the teacher |
| `LLM_DAILY_LIMIT` | maximum API calls per day (default 500) |

**Option A, secrets file (recommended):** copy `.streamlit/secrets.toml.example` to
`.streamlit/secrets.toml` and fill it in. This file is in `.gitignore`.

**Option B, environment variables (Windows PowerShell):**
```
$env:LLM_PROVIDER="openai_compat"; $env:LLM_API_KEY="..."; $env:LLM_MODEL="..."
```
The `build_cases.py` and `run_bot.py` scripts read environment variables, so use option B (or set the
variables in the same terminal) for them.

If the teacher's API is **not** OpenAI-compatible, change only the body of `call_llm()` in `llm.py`
(the request and the way the answer text is read). It must keep returning a Python `dict`
and raise `LLMUnavailable` on any problem. Nothing else in the project needs to change.
Calls are counted in `data/llm_usage.json` (calls, tokens, seconds per day): use it to measure the
real cost per case for your report.

## 4. Generate the 150 cases

```
python build_cases.py --dry-run     # shows the plan (no API needed)
python build_cases.py --rules       # builds cases WITHOUT any AI: only needs internet (Wikipedia)
python build_cases.py --max 5       # with the API: test with 5 cases first, then check them in the game
python build_cases.py               # with the API: builds everything missing (safe to stop and restart)
python build_cases.py --briefings   # with the API: adds an AI story introduction to cases that have none
```
`--rules` is the way to get a full library today, before the teacher's API: it uses real sentences of each article
and changes one fact (a year, a number, a place or a name). Its clues are less natural than the AI ones, but they
are checked by the same Referee. When the API arrives, run it again to add AI-written cases.
- 1 case for each of the 100 articles, plus a second case (different trick) for 50 of them, spread over the
  7 categories. Trick types stay balanced.
- Every case goes through the Referee (FR3). A failed case is rebuilt (max 2 retries), then with another
  trick type. Wikipedia timeouts only skip that article. Progress is saved after each case.
- `data/build_report.json` gives the **validation rate** (goal: at least 90%), average build time,
  failures and API usage. Add `--drop-demo` at the end to remove the 4 demo cases.

## 5. Tests

```
python -m pip install -r requirements-dev.txt
python -m pytest
```
104 tests. They cover every Referee rule, scoring and the confidence bet, the 5-question limit, search counting
(empty search counted, Wikipedia timeout not counted), the 200-character limit, the daily API limit,
the case builder retries, the 150-case plan, the picker, the logs, mock mode, the analysis and the
Streamlit pages. They run offline with fake Wikipedia and fake LLM answers.

## 6. User study and analysis (weeks 13-14)

1. Players play, then fill the Google Form (`survey_questions.md`).
2. Download the log from the **Results** page (JSONL) and put it in `data/games.jsonl`; save the Forms
   answers as `data/survey.csv`.
3. Run the bot: `python run_bot.py`.
4. `python analyze.py` writes 6 charts and `summary.csv` in `analysis/`: accuracy humans vs bot vs random
   (with 95% intervals), by trick type, confidence vs success, searches and questions, survey.
   The summary also checks the success metrics of the proposal.

## 7. Deploy on Streamlit Community Cloud

1. Put the folder on GitHub (public repo is fine: the key is not in the code, `.gitignore` protects it).
2. On share.streamlit.io, "New app", choose the repo, main file `app.py`.
3. In Advanced settings > Secrets, paste the content of `.streamlit/secrets.toml.example` with your real key.
4. Share the link with your friends.

**Important:** the disk of Streamlit Community Cloud is temporary. If the app restarts, `games.jsonl` **and the
profiles** (`players.json`) can be lost, and players would have to create their profile again. During the user
study, download the log from the Detective file page (Export) after each session and keep the study short.
For a permanent solution, the files can be replaced later by a small database (Google Sheets, Supabase...).
Keep a local copy of the app as a backup for the demo.

## 8. Troubleshooting

- `ModuleNotFoundError: pydantic`: use the same Python for everything: `python -m pip install -r requirements.txt`
  then `python -m streamlit run app.py`.
- `pyarrow requires NumPy 2.0`: only the analysis scripts use pandas. The app does not use pyarrow.
  Fix with `python -m pip install --upgrade numpy` (or `pip install "pyarrow<20"`).
- The app works with Streamlit 1.32 and later.
- If a cached Wikipedia page looks wrong, delete `data/articles_html/` and `data/articles/`.

## 9. Known limits

- The Referee checks numbers and years in the true clues, but it **cannot verify** non-numeric true facts
  (places, names, relations). It relies on the Case Builder and on the instruction to use only the article.
- Cases use only the first 6,000 characters of each article.
- The title check is word-based: a hint that does not use the title words is not detected.
- Profiles are a simple name + PIN system for a class project, not a secure login: do not reuse a real password.
- The offline witness only knows how to look up the sentence that matches your question. The real AI will answer
  in free language.
- The study is a small pilot (5 to 6 friends): results are indicative, not statistical proof.
