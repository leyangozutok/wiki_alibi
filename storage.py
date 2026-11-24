"""JSON / JSONL storage (no database server needed)."""
import json
from pathlib import Path
from models import CaseRecord

DATA = Path(__file__).parent / "data"
CASES_FILE = DATA / "cases.json"
LOG_FILE = DATA / "games.jsonl"


def load_cases() -> list[CaseRecord]:
    if not CASES_FILE.exists():
        return []
    return [CaseRecord.model_validate(x) for x in json.loads(CASES_FILE.read_text("utf-8"))]


def save_cases(records: list[CaseRecord]) -> None:
    CASES_FILE.write_text(json.dumps([r.model_dump() for r in records], indent=1,
                                     ensure_ascii=False), "utf-8")


def save_log(game: dict, path: Path | None = None) -> None:
    path = path or LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(game, ensure_ascii=False) + "\n")


def load_logs(path: Path | None = None) -> list[dict]:
    path = path or LOG_FILE
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text("utf-8").splitlines() if l.strip()]
