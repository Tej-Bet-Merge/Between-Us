"""SQLite database schema and initialization."""
from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA cache_size = -64000;

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    source_file_path TEXT,
    source_format TEXT,
    file_size_bytes INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    participants TEXT DEFAULT '[]',
    start_date TEXT,
    end_date TEXT,
    status TEXT DEFAULT 'imported'
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    sender_id TEXT,
    timestamp TEXT NOT NULL,
    text TEXT DEFAULT '',
    reply_to_id TEXT,
    media_type TEXT,
    is_system INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE (project_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_proj_time ON messages (project_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_proj_sender ON messages (project_id, sender);
CREATE INDEX IF NOT EXISTS idx_messages_proj_source ON messages (project_id, source_id);
CREATE INDEX IF NOT EXISTS idx_messages_proj_id ON messages (project_id, id);

CREATE TABLE IF NOT EXISTS analysis_jobs (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    selected_categories TEXT NOT NULL,
    stage TEXT NOT NULL,
    total_chunks INTEGER DEFAULT 0,
    completed_chunks INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error_message TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chunk_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    start_msg_id INTEGER NOT NULL,
    end_msg_id INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    message_count INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (job_id, chunk_index),
    FOREIGN KEY (job_id) REFERENCES analysis_jobs(job_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS temporal_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    period_label TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (job_id, period_label),
    FOREIGN KEY (job_id) REFERENCES analysis_jobs(job_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    model_used TEXT NOT NULL,
    report_json TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS custom_categories (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);
"""


def init_db(db_path: Path | str) -> None:
    """Initialize SQLite database with schema and pragmas and cleanly close."""
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
