# Wiki Alibi: technical updates since the Week 8 proposal

*Text for the final report (section "Changes from the proposal"). Statuses reflect the code as delivered.
Items marked "to measure" need the real API and the user study.*

## 1. Summary

The architecture of the proposal is unchanged: one Python Referee (no LLM), three agents (Case Builder,
Informant, Detective Bot), Streamlit, Pydantic, Wikipedia API, JSON/JSONL storage. The prototype of week 8
(hard-coded clues) became a complete game, with every functional requirement FR1 to FR10 implemented and
tested. The LLM is isolated behind one function, `call_llm`, with a fully working offline mode, so the project
does not depend on the date the API is given.

| Requirement | Status | Where |
|---|---|---|
| FR1 case with 5 clues (4 true, 1 false) | Done | `agents.build_case`, `models.py` |
| FR2 balanced trick types and categories | Done | `build_cases.plan_jobs` |
| FR3 Referee checks (a-d) | Done, tested | `referee.validate_case` |
| FR4 title hidden, 5 clues shown | Done | `app.py` |
| FR5 Informant, max 5 questions, only from witness text | Done, tested | `agents.ask_witness`, `game_logic.ask` |
| FR6 search tool, top 5, counted | Done, tested | `wiki.py`, `game_logic.do_search` |
| FR7 accusation, debrief, score | Done, tested | `referee.score_game`, `app.py` |
| FR8 every game logged | Done | `storage.save_log` |
| FR9 Detective Bot | Done (3 searches max); random baseline offline | `agents.bot_play`, `run_bot.py` |
| FR10 results page | Done, plus offline analysis script | `pages/1_Results.py`, `analyze.py` |

## 2. Changes to the data schema

- `Case` has two new fields, **`original_value`** and **`false_value`** (for example "1911" and "1921").
  They make rule FR3(d) exact: the original value must be in the article, the new value must not.
- `category` was added to each case (used for balance and for the analysis).
- Each stored case keeps its **article text**, so the witness memory can be rebuilt offline.
- The game log has two more fields: `player` (human or bot) and `title_redactions`
  (how many witness answers needed a title to be hidden). Fields of the proposal are kept
  (`case_id`, `category`, `tamper_type`, accused clue, `correct`, searches, questions, `seconds`, time stamp).

## 3. Architecture changes

- **`llm.py` is the single LLM entry point.** Settings come from environment variables or Streamlit secrets.
  Mock mode is the default and is fully functional.
- **Daily API limit** (`LLM_DAILY_LIMIT`, default 500 calls) as promised in the non-functional requirements.
  Calls and tokens are recorded per day, so the real cost per case can be measured (to measure).
- **`game_logic.py`** holds the behavior rules of section 2.4 as pure functions, so they are unit tested.
- **`build_cases.py`** builds 150 cases from 100 articles (one per article, plus a second case with a different
  trick for 50 articles), resumes after interruption, skips articles when Wikipedia times out, retries with
  another trick type, and writes a validation report (goal: 90%, to measure).
- **`analyze.py`** produces the charts of the study (95% Wilson intervals, because samples are small).
- **Smarter random case** (`picker.py`): no repeated case until all were played, and trick types and categories
  played recently are less likely, so each player sees a varied set.

## 4. Interface decisions

- One page, two columns: the investigation (clues, witness, accusation) on the left, Wikipedia on the right.
  Reason: a detective compares what the clues and the witness say with the source at the same time.
- Sober, mature look: no emojis, no tabs, no sidebar, thin lines, short texts. The results page uses the same style.
- Wikipedia articles are shown with a Wikipedia-like layout (the rendered HTML of the article, with scripts removed),
  because the real site cannot be embedded in a frame. A link opens the real page.
- Compatible with Streamlit 1.32 and later. The results charts are drawn without pandas or pyarrow, which removes a
  dependency problem seen on a student computer.
- All game state is in `st.session_state` and the forms avoid nested buttons (the week 8 prototype had a nested
  "Submit" button that would reset on every click).

## 5. New features (beyond the proposal)

| Feature | Why |
|---|---|
| **Confidence bet** (low, medium, high: XP bonus if right, penalty if wrong) and **ranks** | Adds risk and progress; the log shows whether confidence predicts success (a new research question) |
| **Daily case** with a shareable result text | A common case for all players, easy to compare in the pilot |
| **Witness personality** (nervous, proud, chatty, grumpy) | Style only; the facts never change |
| **Title redaction** `[REDACTED]` | See section 6 |
| Wikipedia-style article view | Faster verification, closer to real fact-checking |

## 6. Deviations from the proposal

1. **Title leaks in witness answers are hidden, not blocked.** The proposal said the Referee blocks the answer and the
   witness says "I do not remember". With names like "Gustave Eiffel" this removed useful answers, so the Referee now
   replaces the title words by `[REDACTED]`. The success metric ("no article title appears in witness answers")
   is still true by design; `title_redactions` in the log shows how often it was needed.
2. **Wikipedia timeout.** Search has a 3 second timeout and is not counted when it fails, as specified. Loading a full
   article page uses a longer timeout (8 seconds), because the page is larger.
3. **Offline fallback.** If the LLM fails or the daily limit is reached, the witness answers "I do not remember."
   and the game continues; cases are built in advance, so the game never needs the LLM to start.

## 7. Known limits of the Referee

- **Non-numeric true facts are not verified.** FR3(c) checks every year and number of the true clues against the
  article, but a true clue about a place, a name or a relation can only be trusted from the Case Builder
  (prompt: "use only facts of the article"). A wrong "true" clue is therefore possible; it is a known risk.
- The title check is word-based (full title and its distinctive words). A clue that describes the topic without
  the title words is not detected as a leak.
- Only the first 6,000 characters of each article are used; the Wikipedia article can change over time
  (articles are cached to keep cases stable).
- The false value must not appear in the article, which keeps the altered fact checkable but can exclude
  alterations such as swapping two values that both exist in the text.
- The Streamlit Community Cloud disk is temporary: the game log must be downloaded during the user study.
- With a small pilot (5 to 6 players), accuracy intervals are wide; results are indicative.

## 8. Testing

104 automatic tests run offline (fake Wikipedia and fake LLM). They cover: all Referee checks, scoring with free
allowances and penalties, the three confidence levels, the title redaction, the witness prompt (it never contains
the `is_false` label, the original sentence or the explanation), the 5-question limit in the code and in the
interface, counting rules for searches, the 200-character limit, the daily API limit, case builder retries,
the 150-case plan (balanced and spread over the 7 categories), the picker, log fields, the analysis charts and the
Streamlit pages.

## 9. Still to do with the real API and users (to measure)

- Referee validation rate of generated cases (goal at least 90%) and average build time (goal under 10 s).
- Cost per case (goal under 0.01 USD) from `data/llm_usage.json`.
- Informant answer time (goal under 5 s).
- Human accuracy versus the 20% random level, human versus Detective Bot, accuracy by trick type, confidence versus
  success, and the survey goals (at least 4 out of 5 for "I enjoyed" and "I learned"), with `analyze.py`.


## 10. Second round of changes (after playing the first version)

Playing the first version showed six problems. Each one led to a change.

| Problem seen | Cause | Change |
|---|---|---|
| The same cases came back | Only 4 cases, and the game forgot the player at every visit | 19 hand-made cases; **player profiles** (name + hashed PIN); the next case is chosen among cases not met yet |
| The game was impersonal | No notion of a player | Profile with favorite topics; rank, XP, streaks; the picker trains the kind of forgery the player misses most; personal **Detective file** |
| The witness answered randomly | Offline mode returned any sentence | Offline witness that understands the kind of question (when, where, who, how many), speaks in character and says "I do not remember" when it does not know; the real AI replaces it |
| The AI role felt small | The AI only played the witness | Two new AI tasks that do not change the game: the **Narrator** (story introduction, checked by the Referee) and the **Coach** (personal debrief after the verdict, based on what the player really did) |
| Weak storytelling | Only facts and buttons | Story layer: the Archive Bureau, case codenames, a briefing for each case, named witnesses, verdict and promotion messages |
| Interface too neutral, results page unclear, top of the page cut | Plain style; results written for the study, not for the player | Warm "case file" look, evidence cards, chat bubbles, stamps; Detective file with plain explanations and "How does the Detective Bot work?"; fixed top margin |

New and changed design points to mention in the report:

- **Profiles.** Name and a 4-digit PIN stored as a salted PBKDF2 hash (the PIN is never stored). Statistics are derived
  from `games.jsonl`, so there is one source of truth. This stores slightly more than "only nicknames" (the proposal),
  but no personal data. It is a classroom-level login, not secure authentication.
- **Narrator agent.** It never sees the article: it only receives the category and the witness. The Referee still checks
  its text (no title, no fact of the case) and a neutral text replaces it if the check fails, also at play time.
- **Coach agent.** Runs after the verdict, so it can talk about the case freely. Player search queries are given to it as
  data only. If the AI fails, a template that depends on the player's behavior is used.
- **Offline Case Builder** (`rules_builder.py`, `build_cases.py --rules`). A second Case Builder without AI, so a full
  library of cases exists before the API. It passes through the same Referee; the AI builder remains the main one.
- **Offline fallbacks everywhere.** Every agent works without the API, which also makes the tests fast and free.
- **Known limits added:** profiles and logs are lost if the hosting disk is erased; the offline witness is not a
  language model; the rule-based builder gives less natural clues than the AI.

The architecture and the user flow are drawn in `docs/ARCHITECTURE.md` (Mermaid diagrams).
