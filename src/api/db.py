"""SQLite persistence in private/app.db (override with JOB_TAILOR_DB)."""
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = os.environ.get("JOB_TAILOR_DB", str(ROOT / "private" / "app.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL, title TEXT NOT NULL,
    start_date TEXT NOT NULL DEFAULT '', end_date TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS bullets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE, text TEXT NOT NULL);
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
"""


def connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def load_profile(conn: sqlite3.Connection) -> dict:
    """Build the dict tailor() expects. IDs are prefixed PKs, so they stay stable."""
    return {
        "roles": [
            {"id": f"role_{r['id']}", "company": r["company"], "title": r["title"]}
            for r in conn.execute("SELECT * FROM roles ORDER BY id")
        ],
        **{
            table: [
                {"id": f"{prefix}_{r['id']}", "role_id": f"role_{r['role_id']}", "text": r["text"]}
                for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")
            ]
            for table, prefix in (("bullets", "bullet"), ("stories", "story"))
        },
    }
