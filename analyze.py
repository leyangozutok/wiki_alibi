"""Analysis of the user study (weeks 13-14). Reads data/games.jsonl (+ data/survey.csv if present)
and writes clean charts (PNG, 200 dpi) and summary files to analysis/.

    pip install pandas matplotlib
    python analyze.py
    python analyze.py --logs my_games.jsonl --survey my_survey.csv --out analysis
"""
import argparse
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # no window needed
import matplotlib.pyplot as plt
import pandas as pd

NAVY, GREY, LIGHT, RED = "#2f4b7c", "#9aa3ad", "#d9dde2", "#b5524a"
RANDOM = 0.20                              # 1 clue out of 5
TYPES = ["date", "number", "place", "person"]
CONF = ["low", "medium", "high"]
SURVEY_KEYS = {"q1_enjoyed": ("enjoy", "I enjoyed the game"),
               "q2_learned": ("learn", "I learned something"),
               "q3_easy": ("easy", "The game was easy to use"),
               "q4_witness": ("witness", "The witness helped me"),
               "q5_again": ("again", "I would play again")}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#888", "axes.titlesize": 12,
                     "axes.titleweight": "normal", "axes.titlelocation": "left",
                     "figure.dpi": 100, "savefig.bbox": "tight"})


# ---------- helpers ----------
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval of a proportion (good for small samples)."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def acc(df: pd.DataFrame):
    k, n = int(df["correct"].sum()), len(df)
    lo, hi = wilson(k, n)
    return (k / n if n else 0.0), lo, hi, n


def bar_with_ci(ax, x, df, color, width=0.8, label=None):
    p, lo, hi, n = acc(df)
    ax.bar(x, p * 100, width, color=color, label=label)
    if n:
        ax.errorbar(x, p * 100, yerr=[[max(0.0, (p - lo) * 100)], [max(0.0, (hi - p) * 100)]], color="#333",
                    capsize=3, lw=1)
        ax.text(x, hi * 100 + 2, f"{p * 100:.0f}%\nn={n}", ha="center", va="bottom", fontsize=8.5)
    else:
        ax.text(x, 2, "no data", ha="center", fontsize=8.5, color="#888")


def random_line(ax):
    ax.axhline(RANDOM * 100, color=RED, ls="--", lw=1)
    ax.text(ax.get_xlim()[1], RANDOM * 100 + 1.5, "random 20%", color=RED, ha="right", fontsize=8.5)


def finish(ax, title, ylabel="Accuracy (%)"):
    ax.set_ylim(0, 128)
    ax.set_ylabel(ylabel)
    ax.set_title(title)


# ---------- charts ----------
def chart_overall(df, out):
    fig, ax = plt.subplots(figsize=(5.2, 3.8))
    for x, (name, sub, col) in enumerate([("Humans", df[df.player == "human"], NAVY),
                                          ("Detective Bot", df[df.player == "bot"], GREY)]):
        bar_with_ci(ax, x, sub, col)
    ax.bar(2, RANDOM * 100, 0.8, color=LIGHT)
    ax.text(2, RANDOM * 100 + 2, "20%", ha="center", fontsize=8.5)
    ax.set_xticks([0, 1, 2], ["Humans", "Detective Bot", "Random\nguess"])
    finish(ax, "Overall accuracy (95% interval)")
    fig.savefig(out / "1_overall_accuracy.png", dpi=200)
    plt.close(fig)


def chart_tamper(df, out):
    fig, ax = plt.subplots(figsize=(7, 3.8))
    w = 0.38
    for i, t in enumerate(TYPES):
        sub = df[df.tamper_type == t]
        bar_with_ci(ax, i - w / 2, sub[sub.player == "human"], NAVY, w, "Humans" if i == 0 else None)
        bar_with_ci(ax, i + w / 2, sub[sub.player == "bot"], GREY, w, "Detective Bot" if i == 0 else None)
    ax.set_xticks(range(4), [t.capitalize() for t in TYPES])
    ax.set_xlim(-0.6, 3.6)
    random_line(ax)
    ax.legend(frameon=False, loc="upper left", ncol=2, fontsize=9)
    finish(ax, "Accuracy by type of altered fact")
    fig.savefig(out / "2_accuracy_by_tamper_type.png", dpi=200)
    plt.close(fig)


def chart_confidence(df, out):
    h = df[df.player == "human"]
    fig, ax = plt.subplots(figsize=(5.2, 3.8))
    for i, c in enumerate(CONF):
        bar_with_ci(ax, i, h[h.confidence == c], NAVY)
    ax.set_xticks(range(3), [c.capitalize() for c in CONF])
    ax.set_xlim(-0.6, 2.6)
    random_line(ax)
    ax.set_xlabel("Confidence bet")
    finish(ax, "Does confidence predict success? (humans)")
    fig.savefig(out / "3_confidence_vs_accuracy.png", dpi=200)
    plt.close(fig)


def chart_effort(df, out):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    for ax, col, title in ((axes[0], "n_searches", "Average searches per game"),
                           (axes[1], "n_questions", "Average questions per game")):
        w = 0.38
        for i, t in enumerate(TYPES):
            sub = df[df.tamper_type == t]
            for off, who, color in ((-w / 2, "human", NAVY), (w / 2, "bot", GREY)):
                s = sub[sub.player == who][col]
                v = s.mean() if len(s) else 0
                ax.bar(i + off, v, w, color=color, label=("Humans" if who == "human" else "Detective Bot")
                       if i == 0 else None)
                if len(s):
                    ax.text(i + off, v + 0.05, f"{v:.1f}", ha="center", fontsize=8.5)
        ax.set_xticks(range(4), [t.capitalize() for t in TYPES])
        ax.set_title(title)
    axes[0].legend(frameon=False, fontsize=9)
    fig.savefig(out / "4_effort_searches_questions.png", dpi=200)
    plt.close(fig)


def chart_correct_vs_effort(df, out):
    h = df[df.player == "human"].copy()
    if h.empty:
        return
    h["searches"] = h["n_searches"].clip(upper=4).map(lambda v: "4+" if v >= 4 else str(int(v)))
    fig, ax = plt.subplots(figsize=(5.2, 3.8))
    for i, k in enumerate(["0", "1", "2", "3", "4+"]):
        bar_with_ci(ax, i, h[h.searches == k], NAVY)
    ax.set_xticks(range(5), ["0", "1", "2", "3", "4+"])
    ax.set_xlim(-0.6, 4.6)
    random_line(ax)
    ax.set_xlabel("Number of Wikipedia searches")
    finish(ax, "Does searching help? (humans)")
    fig.savefig(out / "5_searches_vs_accuracy.png", dpi=200)
    plt.close(fig)


# ---------- survey ----------
def load_survey(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df = df[~df.iloc[:, 0].astype(str).str.lower().str.startswith("example")] if len(df) else df
    cols = {}
    for key, (word, _) in SURVEY_KEYS.items():
        match = [c for c in df.columns if word in str(c).lower()]
        if match:
            cols[key] = match[0]
    if len(cols) < 5:                                  # fallback: the 5 numeric columns in order
        numeric = [c for c in df.columns if pd.to_numeric(df[c], errors="coerce").notna().any()]
        cols = dict(zip(SURVEY_KEYS, numeric[:5]))
    out = pd.DataFrame({k: pd.to_numeric(df[c], errors="coerce") for k, c in cols.items()})
    return out.dropna(how="all")


def chart_survey(sv, out):
    fig, ax = plt.subplots(figsize=(7, 3.4))
    names = [SURVEY_KEYS[k][1] for k in SURVEY_KEYS]
    means = [sv[k].mean() for k in SURVEY_KEYS]
    y = range(len(names))[::-1]
    ax.barh(list(y), means, color=NAVY, height=0.55)
    for yi, m in zip(y, means):
        ax.text(m + 0.05, yi, f"{m:.1f}", va="center", fontsize=9)
    ax.axvline(4, color=RED, ls="--", lw=1)
    ax.text(4.02, len(names) - 0.45, "goal: 4", color=RED, fontsize=8.5)
    ax.set_yticks(list(y), names)
    ax.set_xlim(1, 5.4)
    ax.set_xlabel("Average score (1 to 5)")
    ax.set_title(f"User survey (n={len(sv)})")
    fig.savefig(out / "6_survey.png", dpi=200)
    plt.close(fig)


# ---------- summary of the PDF success metrics ----------
def summary(df, sv) -> pd.DataFrame:
    rows = []
    h, b = df[df.player == "human"], df[df.player == "bot"]
    ph, loh, hih, nh = acc(h)
    pb, lob, hib, nb = acc(b)
    rows += [("Games (human / bot)", f"{nh} / {nb}", ""),
             ("Human accuracy", f"{ph:.0%}  [{loh:.0%}-{hih:.0%}]", "above 20% random?  " + ("yes" if loh > RANDOM else "not clearly")),
             ("Bot accuracy", f"{pb:.0%}  [{lob:.0%}-{hib:.0%}]" if nb else "n/a", "")]
    if nh:
        finished = h.groupby("nickname").size()
        rows.append(("Players with 6+ games", f"{int((finished >= 6).sum())} of {len(finished)}", "goal: at least 5 of 6"))
        rows.append(("Median seconds per game (humans)", f"{h.seconds.median():.0f}", ""))
        rows.append(("Mean searches / questions (humans)", f"{h.n_searches.mean():.1f} / {h.n_questions.mean():.1f}", ""))
        if "title_redactions" in h:
            rows.append(("Witness answers where the title was hidden", str(int(h.title_redactions.sum())),
                         "0 titles shown to players by design"))
    if sv is not None and len(sv):
        for k in ("q1_enjoyed", "q2_learned"):
            m = sv[k].mean()
            rows.append((f"Survey: {SURVEY_KEYS[k][1]}", f"{m:.2f} / 5", "goal: at least 4  " + ("reached" if m >= 4 else "not reached")))
    return pd.DataFrame(rows, columns=["Metric", "Value", "Note"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="data/games.jsonl")
    ap.add_argument("--survey", default="data/survey.csv")
    ap.add_argument("--out", default="analysis")
    a = ap.parse_args(argv)
    logs = Path(a.logs)
    if not logs.exists() or logs.stat().st_size == 0:
        raise SystemExit(f"No games found in {logs}. Play some games first (or download games.jsonl from the Results page).")
    df = pd.read_json(logs, lines=True)
    for col, default in (("confidence", "low"), ("n_questions", 0), ("n_searches", 0), ("seconds", 0)):
        if col not in df:
            df[col] = default
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    chart_overall(df, out); chart_tamper(df, out); chart_confidence(df, out)
    chart_effort(df, out); chart_correct_vs_effort(df, out)
    sv = load_survey(Path(a.survey))
    if sv is not None and len(sv):
        chart_survey(sv, out)
    s = summary(df, sv)
    s.to_csv(out / "summary.csv", index=False)
    (out / "summary.md").write_text(s.to_markdown(index=False) if _has_tabulate() else s.to_string(index=False), "utf-8")
    print(s.to_string(index=False))
    print(f"\nCharts and summary saved in {out}/")


def _has_tabulate() -> bool:
    try:
        import tabulate  # noqa: F401
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    main()
