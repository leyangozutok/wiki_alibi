# Wiki Alibi - User survey (Google Forms)

Create one Google Form, section "Wiki Alibi: your opinion" (about 1 minute).
Each question 1 to 5, type: **Linear scale**, 1 = "Strongly disagree", 5 = "Strongly agree", required.

| # | Question (exact text) | CSV column |
|---|------------------------|------------|
| 1 | I enjoyed the game. | `q1_enjoyed` |
| 2 | I learned something new while playing. | `q2_learned` |
| 3 | The game was easy to understand and use. | `q3_easy` |
| 4 | The witness helped me in my investigation. | `q4_witness` |
| 5 | I would play again or recommend the game to a friend. | `q5_again` |

Optional, short answer: **"Any comment? (what was confusing, what would you change?)"** -> `comment`

Also ask (short answer, required): **"Your nickname in the game"** -> `player`
(so you can link survey answers to the games in `games.jsonl`; use nicknames only, no real names).

## Goals from the proposal (section 2.4)
- Average of question 1 and question 2 at least **4 out of 5**.
- At least **5 of 6** friends finish all 6 cases.

## From Google Forms to `analyze.py`
1. In Google Forms: Responses > "Link to Sheets" > File > Download > CSV.
2. Save it as `data/survey.csv`. The analysis finds the five question columns by their words
   (enjoy, learn, easy, witness, again), so you do not need to rename them.
   An empty template with clean column names is in `data/survey_template.csv`.
3. Run `python analyze.py`: chart `analysis/6_survey.png` and the survey goals in `analysis/summary.csv`.
