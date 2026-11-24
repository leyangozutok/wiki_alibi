"""Builds the case library: 100 articles -> 150 cases (PDF section 2.3).
   - 1 case for each of the 100 articles
   - a 2nd case, with a DIFFERENT trick type, for 50 of them (spread over the 7 categories)
   - trick types (date, number, place, person) are kept balanced (FR2)
   - the Referee validates every case; a report with the validation rate is written

Usage:
  python build_cases.py --dry-run        show the plan, no API needed
  python build_cases.py --max 10         build the first 10 missing cases (test with a few first!)
  python build_cases.py                  build everything that is missing (resumable)
  python build_cases.py --rules          build cases WITHOUT any AI (rule-based, needs only internet)
  python build_cases.py --briefings      add an AI story introduction to cases that have none
  python build_cases.py --drop-demo      remove the hand-made demo cases at the end
"""
import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass

from agents import build_case, write_briefing, CaseBuildError
from rules_builder import build_case_rules
from llm import llm_available, LLMLimitReached, usage_today, daily_limit
from storage import load_cases, save_cases, DATA
from wiki import get_article, WikiError

TYPES = ["date", "number", "place", "person"]
SECOND_CASE_ARTICLES = 50
TARGET_RATE = 0.90


@dataclass
class Job:
    title: str
    category: str
    tamper: str
    pass_no: int          # 1 = first case of the article, 2 = second case


def read_topics(path=None) -> list[dict]:
    with open(path or DATA / "topics.csv", encoding="utf-8", newline="") as f:
        return [{"title": r["title"].strip(), "category": r["category"].strip()}
                for r in csv.DictReader(f) if r["title"].strip()]


def is_demo(rec) -> bool:
    return rec.case.case_id.startswith("demo")


def second_case_titles(topics: list[dict], n: int = SECOND_CASE_ARTICLES) -> list[str]:
    """Round robin over the categories, so the 50 second cases are spread evenly."""
    by_cat: dict[str, list[str]] = defaultdict(list)
    for t in topics:
        by_cat[t["category"]].append(t["title"])
    out, i = [], 0
    while len(out) < min(n, len(topics)):
        for titles in by_cat.values():
            if i < len(titles) and len(out) < n:
                out.append(titles[i])
        i += 1
    return out


def plan_jobs(topics: list[dict], records: list, n_second: int = SECOND_CASE_ARTICLES) -> list[Job]:
    """What is still missing, with balanced trick types. Demo cases do not count."""
    real = [r for r in records if not is_demo(r)]
    have = Counter(r.case.wiki_title for r in real)
    type_count = Counter(r.case.tamper_type for r in real)
    first_type = {}
    for r in real:
        first_type.setdefault(r.case.wiki_title, r.case.tamper_type)
    jobs = []
    for t in topics:                                              # pass 1
        if have[t["title"]] == 0:
            ty = min(TYPES, key=lambda x: (type_count[x], TYPES.index(x)))
            type_count[ty] += 1
            first_type[t["title"]] = ty
            jobs.append(Job(t["title"], t["category"], ty, 1))
    wanted = set(second_case_titles(topics, n_second))
    for t in topics:                                              # pass 2
        if t["title"] in wanted and have[t["title"]] < 2:
            options = [x for x in TYPES if x != first_type.get(t["title"])]
            ty = min(options, key=lambda x: (type_count[x], TYPES.index(x)))
            type_count[ty] += 1
            jobs.append(Job(t["title"], t["category"], ty, 2))
    return jobs


def fetch_article(title: str, article_fn, tries: int = 3, sleep: float = 2.0):
    """Wikipedia can be slow: try 3 times, then give up on this article only."""
    for k in range(tries):
        try:
            return article_fn(title)
        except WikiError:
            if k < tries - 1:
                time.sleep(sleep * (k + 1))
    raise WikiError(f"Wikipedia did not answer for '{title}'")


def run_build(jobs, records, build_fn=build_case, article_fn=get_article, save_fn=save_cases,
              max_new=None, sleep=2.0, log=print, narrator_fn=None) -> dict:
    stats = {"attempts": 0, "valid": 0, "durations": []}
    built, failed, stopped = 0, [], None
    for n, job in enumerate(jobs):
        if max_new is not None and built + len(failed) >= max_new:
            break
        try:
            article = fetch_article(job.title, article_fn, sleep=sleep)
            if not article:
                raise CaseBuildError("article not found or empty")
        except (WikiError, CaseBuildError) as e:
            failed.append({"title": job.title, "pass": job.pass_no, "reason": str(e)[:150]})
            log(f"FAIL  {job.title}: {e}")
            continue
        used = {r.case.tamper_type for r in records if r.case.wiki_title == job.title and not is_demo(r)}
        order = [job.tamper] + [x for x in TYPES if x != job.tamper]   # fallback to other tricks
        rec, last_err = None, ""
        for ty in [x for x in order if x not in used][:3]:
            try:
                rec = build_fn(job.title, article, ty, job.category, stats=stats)
                break
            except LLMLimitReached as e:
                stopped = str(e)
                break
            except CaseBuildError as e:
                last_err = str(e)[:150]
        if stopped:
            log(f"STOP  {stopped}")
            break
        if rec is None:
            failed.append({"title": job.title, "pass": job.pass_no, "reason": last_err})
            log(f"FAIL  {job.title}: {last_err}")
            continue
        if narrator_fn:
            try:
                rec.case.briefing = narrator_fn(rec.case)           # AI story introduction (Referee-checked)
            except LLMLimitReached as e:
                stopped = str(e)                                    # keep the case, the template story is used
        records.append(rec)
        save_fn(records)                                           # progress is never lost
        built += 1
        log(f"OK    [{n + 1}/{len(jobs)}] {job.title} ({rec.case.tamper_type})")
        if stopped:
            log(f"STOP  {stopped}")
            break
    attempts = stats["attempts"]
    rate = stats["valid"] / attempts if attempts else 0.0
    d = stats["durations"]
    return {"jobs_planned": len(jobs), "built": built, "failed": failed, "stopped": stopped,
            "attempts": attempts, "valid_attempts": stats["valid"], "validation_rate": round(rate, 3),
            "meets_90_percent_goal": rate >= TARGET_RATE if attempts else None,
            "avg_build_seconds": round(sum(d) / len(d), 2) if d else None,
            "total_cases": len([r for r in records if not is_demo(r)]),
            "types": dict(Counter(r.case.tamper_type for r in records if not is_demo(r))),
            "api_usage_today": usage_today()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max", type=int, default=None, help="build at most N cases in this run")
    ap.add_argument("--dry-run", action="store_true", help="only show the plan")
    ap.add_argument("--drop-demo", action="store_true", help="remove the demo cases when done")
    ap.add_argument("--rules", action="store_true", help="rule-based Case Builder, no LLM needed")
    ap.add_argument("--briefings", action="store_true", help="write missing story introductions (LLM)")
    args = ap.parse_args(argv)

    topics, records = read_topics(), load_cases()
    jobs = plan_jobs(topics, records)
    print(f"Articles: {len(topics)} | real cases so far: {sum(not is_demo(r) for r in records)} "
          f"| still to build: {len(jobs)} (target {len(topics) + SECOND_CASE_ARTICLES})")
    print("Planned trick types:", dict(Counter(j.tamper for j in jobs)))
    if args.dry_run:
        return 0
    if args.briefings:
        if not llm_available():
            print("The Narrator needs the LLM. Configure it first (see README).")
            return 1
        todo = [r for r in records if not r.case.briefing]
        for r in todo:
            try:
                r.case.briefing = write_briefing(r.case)
            except LLMLimitReached as e:
                print("STOP", e)
                break
            save_cases(records)
        print(f"Story introductions written: {sum(bool(r.case.briefing) for r in records)} / {len(records)}")
        return 0
    if not args.rules and not llm_available():
        print("\nNo LLM configured. Set LLM_PROVIDER=openai_compat, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL "
              "(see README), or use --rules to build cases without AI.")
        return 1
    if args.rules:
        print("Rule-based Case Builder: no API calls.\n")
        report = run_build(jobs, records, build_fn=build_case_rules, max_new=args.max)
    else:
        print(f"API calls allowed today: {daily_limit()} (already used: {usage_today()['calls']})\n")
        report = run_build(jobs, records, max_new=args.max, narrator_fn=write_briefing)
    if args.drop_demo and report["total_cases"] >= len(topics):
        save_cases([r for r in records if not is_demo(r)])
        print("Demo cases removed.")
    (DATA / "build_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), "utf-8")
    ok = report["meets_90_percent_goal"]
    print(f"\nBuilt {report['built']}, failed {len(report['failed'])}. "
          f"Referee validation rate: {report['validation_rate']:.0%} "
          f"({'goal reached' if ok else 'BELOW the 90% goal: improve the prompt' if ok is False else 'n/a'}). "
          f"Report: data/build_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
