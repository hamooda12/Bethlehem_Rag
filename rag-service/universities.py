import re
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

INDEX_DIR = Path("chroma_db")
SEEDS = (
    ("birzeit", "جامعة بيرزيت"),
    ("aaup", "الجامعة العربية الأمريكية"),
)


@contextmanager
def registry():
    INDEX_DIR.mkdir(exist_ok=True)
    with closing(sqlite3.connect(INDEX_DIR / "universities.sqlite3", timeout=10)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS universities (id TEXT PRIMARY KEY, name TEXT NOT NULL)")
        db.executemany("INSERT OR IGNORE INTO universities VALUES (?, ?)", SEEDS)
        yield db


def list_universities():
    with registry() as db:
        return [{"id": key, "name": name} for key, name in db.execute(
            "SELECT id, name FROM universities ORDER BY id"
        )]


def university_name(university_id):
    with registry() as db:
        row = db.execute("SELECT name FROM universities WHERE id = ?", (university_id,)).fetchone()
    return row[0] if row else None


def create_university(university_id, name):
    name = name.strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", university_id) or not 1 <= len(name) <= 120:
        raise ValueError("Invalid university ID or name")
    if any(ord(char) < 32 for char in name):
        raise ValueError("Invalid university name")
    with registry() as db:
        result = db.execute("INSERT OR IGNORE INTO universities VALUES (?, ?)", (university_id, name))
        if not result.rowcount:
            return None
    return {"id": university_id, "name": name}
