import os
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"
DB_PATH = os.getenv("SURFLOG_DB_PATH", str(BASE_DIR / "surflog.db"))


def ensure_surf_logs_columns(conn: sqlite3.Connection) -> None:
    table_exists = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'surf_logs'
        """
    ).fetchone()

    if not table_exists:
        return

    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(surf_logs)").fetchall()
    }

    if "session_rating" not in columns:
        conn.execute("ALTER TABLE surf_logs ADD COLUMN session_rating REAL")
    if "session_start_time" not in columns:
        conn.execute("ALTER TABLE surf_logs ADD COLUMN session_start_time TEXT")
    if "session_end_time" not in columns:
        conn.execute("ALTER TABLE surf_logs ADD COLUMN session_end_time TEXT")


def init_db() -> None:
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Missing schema file: {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema_sql)
        ensure_surf_logs_columns(conn)
        conn.commit()
    finally:
        conn.close()

    print(f"Database initialized successfully at: {DB_PATH}")


if __name__ == "__main__":
    init_db()
