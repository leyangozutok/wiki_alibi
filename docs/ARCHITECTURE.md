# Wiki Alibi: architecture and user flow

The diagrams below are written in Mermaid. GitHub draws them automatically.

## 1. User flow (what the player sees)

```mermaid
stateDiagram-v2
    [*] --> Home
    Home --> SignIn: has a profile
    Home --> CreateProfile: new player
    Home --> Guest: just trying
    SignIn --> Desk: name + PIN ok
    CreateProfile --> Desk: name, PIN, favorite topics
    Guest --> Desk
    Desk --> Case: Open the next case
    state Case {
        [*] --> Briefing
        Briefing --> Investigation
        state Investigation {
            Clues --> Witness: ask (max 5)
            Witness --> Archive: compare
            Archive --> Clues: Wikipedia (3 free searches)
        }
        Investigation --> Accusation: choose a clue + confidence bet
    }
    Accusation --> Verdict: score, XP, rank
    Verdict --> Debrief: Coach note + original sentence
    Debrief --> Case: Next case (never a repeat)
    Debrief --> DetectiveFile: Detective file
    DetectiveFile --> Desk
    Desk --> [*]: Sign out
```

What makes the game remember you: every verdict is written to `games.jsonl` with your name. Your rank, XP,
streaks, weak spots and the list of cases you already met are **computed from that log** each time you sign in.
The next case is chosen by `picker.py` among the cases you have not met, with a preference for your favorite
topics and for the kind of forgery you miss most.

## 2. Components

```mermaid
flowchart LR
    subgraph UI[Streamlit interface]
        APP[app.py: home, case, verdict]
        RES[pages/1_Results.py: Detective file]
    end
    subgraph RULES[Plain Python, no LLM]
        REF[referee.py: FR3 checks, scoring, redaction]
        GL[game_logic.py: question and search rules]
        PICK[picker.py: next case]
        PL[players.py: profiles, statistics]
        STORY[story.py: codenames, briefings, verdicts]
    end
    subgraph AGENTS[AI agents, agents.py]
        CB[Case Builder]
        NAR[Narrator: story introduction]
        INF[Informant: the witness]
        COACH[Coach: personal debrief]
        BOT[Detective Bot: baseline]
    end
    LLM[llm.py: call_llm, daily limit, usage log]
    WIKI[wiki.py: search, article, page view]
    DATA[(cases.json, games.jsonl, players.json)]
    APP --> GL --> INF
    APP --> REF
    APP --> PICK
    APP --> PL
    APP --> STORY
    APP --> COACH
    APP --> WIKI
    RES --> PL
    CB --> LLM
    NAR --> LLM
    INF --> LLM
    COACH --> LLM
    BOT --> LLM
    CB -. checked by .-> REF
    NAR -. checked by .-> REF
    APP --> DATA
    PL --> DATA
    PICK --> DATA
```

Every AI agent has an **offline fallback**, so the game is complete without the API:
the witness answers from its memory in character, the Narrator and the Coach use templates, the bot guesses at random.

## 3. One game, step by step

```mermaid
sequenceDiagram
    actor P as Player
    participant UI as app.py
    participant PK as picker.py
    participant W as Informant (witness)
    participant WK as Wikipedia
    participant R as Referee
    participant C as Coach
    participant L as games.jsonl
    P->>UI: Open the next case
    UI->>PK: seen cases, favorites, weak spots
    PK-->>UI: case (briefing, 5 clues)
    loop up to 5 questions
        P->>UI: question (max 200 characters)
        UI->>W: question + altered memory
        W-->>UI: answer (title hidden by the Referee)
    end
    loop searches (3 free)
        P->>UI: query
        UI->>WK: search (3 s timeout)
        WK-->>UI: results (not counted if it fails)
    end
    P->>UI: accusation + confidence bet
    UI->>R: score_game
    R-->>UI: score, XP
    UI->>L: save game (name, seconds, searches, questions)
    UI->>C: what the player did
    C-->>UI: summary + tip
    UI-->>P: verdict, original sentence, promotion, coach note
```

## 4. Case library: how cases are made

```mermaid
flowchart LR
    T[topics.csv: 100 titles] --> W[Wikipedia article]
    W --> B{Case Builder}
    B -->|API available| LLM[AI Case Builder]
    B -->|--rules, no API| RB[rule-based builder]
    LLM --> R[Referee FR3]
    RB --> R
    R -->|valid| N[Narrator: story introduction]
    R -->|invalid, max 2 retries, then another trick| B
    N --> C[(cases.json: 150 cases)]
```

## 5. Data model

```mermaid
classDiagram
    class Case {
        case_id
        wiki_title
        category
        tamper_type
        original_sentence
        false_sentence
        original_value
        false_value
        explanation
        briefing
    }
    class Clue { id; text; is_false }
    class CaseRecord { article }
    class GameLog {
        case_id; nickname; player
        accused_id; correct; confidence
        n_searches; n_questions; seconds
        score; xp; title_redactions; timestamp
    }
    class Player { name; favorites; pin_hash }
    CaseRecord "1" --> "1" Case
    Case "1" --> "5" Clue
    Player "1" --> "*" GameLog : name
    GameLog "*" --> "1" Case : case_id
```
Player statistics (rank, XP, streaks) are not stored: they are derived from `GameLog`.
