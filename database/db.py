"""Small SQLite repository for imported job records."""
import json
import sqlite3
from datetime import datetime, timezone
from config import DATABASE_PATH


def connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize():
    with connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, record TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")


def replace_jobs(records, source, columns=None):
    with connect() as conn:
        conn.execute("DELETE FROM jobs")
        conn.executemany("INSERT INTO jobs(record) VALUES (?)", [(json.dumps(r, default=str),) for r in records])
        conn.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('source',?)", (source,))
        conn.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('refreshed_at',?)", (datetime.now(timezone.utc).isoformat(),))
        if columns is not None:
            conn.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('source_columns',?)", (json.dumps(columns),))


def get_jobs():
    with connect() as conn:
        return [json.loads(row[0]) for row in conn.execute("SELECT record FROM jobs ORDER BY id")]

def job_count():
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]


def get_source():
    with connect() as conn:
        row = conn.execute("SELECT value FROM metadata WHERE key='source'").fetchone()
        return row[0] if row else None

def get_refreshed_at():
    with connect() as conn:
        row = conn.execute("SELECT value FROM metadata WHERE key='refreshed_at'").fetchone()
        return row[0] if row else None

def get_source_columns():
    with connect() as conn:
        row = conn.execute("SELECT value FROM metadata WHERE key='source_columns'").fetchone()
        return json.loads(row[0]) if row else []
