"""SQLite persistence in private/app.db (override with JOB_TAILOR_DB)."""
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = os.environ.get("JOB_TAILOR_DB", str(ROOT / "private" / "app.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL, title TEXT NOT NULL,
    start_date TEXT NOT NULL DEFAULT '', end_date TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'experience', position INTEGER);
CREATE TABLE IF NOT EXISTS bullets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE, text TEXT NOT NULL, position INTEGER);
CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '',
    link TEXT NOT NULL DEFAULT '', text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS resume_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE, content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT, section TEXT NOT NULL, label TEXT NOT NULL, text TEXT NOT NULL,
    position INTEGER);
"""


ORDERED = ("roles", "bullets", "entries")


def _add_column(conn: sqlite3.Connection, table: str, col: str, ddl: str) -> None:
    """Add a column missing from an older DB."""
    if col in [c["name"] for c in conn.execute(f"PRAGMA table_info({table})")]:
        return
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        conn.commit()
    except sqlite3.OperationalError as e:  # another connection migrated first
        if "duplicate column" not in str(e):
            raise


def connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    # DBs from before step 7b have no kind column; their roles are all experience.
    _add_column(conn, "roles", "kind", "TEXT NOT NULL DEFAULT 'experience'")
    # Before step 7c1 there was no position; order was creation order, so position = id keeps it.
    for t in ORDERED:
        _add_column(conn, t, "position", "INTEGER")
        # Every time, not only right after the ALTER, so a crash between the two can't leave NULLs.
        conn.execute(f"UPDATE {t} SET position = id WHERE position IS NULL")
        conn.commit()
        conn.execute(f"CREATE TRIGGER IF NOT EXISTS {t}_position AFTER INSERT ON {t} WHEN NEW.position IS NULL"
                     f" BEGIN UPDATE {t} SET position = NEW.id WHERE id = NEW.id; END")
    return conn


def load_profile(conn: sqlite3.Connection) -> dict:
    """Build the dict tailor() expects. IDs are prefixed PKs, so they stay stable.
    Education never reaches the tailor, so its roles and their bullets/stories are left out."""
    return {
        "roles": [
            {"id": f"role_{r['id']}", "company": r["company"], "title": r["title"]}
            for r in conn.execute("SELECT * FROM roles WHERE kind != 'education' ORDER BY position, id")
        ],
        **{
            table: [
                {"id": f"{prefix}_{r['id']}", "role_id": f"role_{r['role_id']}", "text": r["text"]}
                for r in conn.execute(
                    f"SELECT t.* FROM {table} t JOIN roles r ON r.id = t.role_id"
                    f" WHERE r.kind != 'education' ORDER BY {order}")
            ]
            for table, prefix, order in (("bullets", "bullet", "t.position, t.id"), ("stories", "story", "t.id"))
        },
    }
