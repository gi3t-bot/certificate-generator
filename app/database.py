import sqlite3, os
from datetime import datetime

# =====================================================================
# DATABASE CONFIGURATION
# =====================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "certificates.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    # creating the tables if they don't already exist
    conn = get_conn()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id         TEXT    PRIMARY KEY,
            status     TEXT    NOT NULL DEFAULT 'processing',
            total      INTEGER NOT NULL DEFAULT 0,
            success    INTEGER NOT NULL DEFAULT 0,
            failed     INTEGER NOT NULL DEFAULT 0,
            created_at TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS certificates (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id    TEXT    NOT NULL,
            name      TEXT    NOT NULL,
            course    TEXT    NOT NULL DEFAULT '',
            date_text TEXT    NOT NULL DEFAULT '',
            status    TEXT    NOT NULL DEFAULT 'pending',
            error_msg TEXT,
            file_path TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        );
    """)

    conn.commit()
    conn.close()
