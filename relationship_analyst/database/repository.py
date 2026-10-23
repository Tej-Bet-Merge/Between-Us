"""Database repository for projects, messages, checkpoints, and reports."""
from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

from relationship_analyst.config import DATA_DIR, DB_FILE_NAME
from relationship_analyst.database.schema import init_db
from relationship_analyst.models.analysis import (
    ChunkAnalysisResult,
    FinalReport,
    TemporalPeriodSummary,
)
from relationship_analyst.models.message import CanonicalMessage, ProjectMetadata


class Repository:
    """Encapsulates SQLite operations with WAL concurrency and safe resource handling."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else (DATA_DIR / DB_FILE_NAME)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        init_db(self.db_path)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    # ------------------ Projects ------------------

    def create_or_update_project(self, project: ProjectMetadata) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO projects (
                    id, name, created_at, source_file_path, source_format,
                    file_size_bytes, message_count, participants, start_date, end_date, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    source_file_path = excluded.source_file_path,
                    source_format = excluded.source_format,
                    file_size_bytes = excluded.file_size_bytes,
                    message_count = excluded.message_count,
                    participants = excluded.participants,
                    start_date = excluded.start_date,
                    end_date = excluded.end_date,
                    status = excluded.status;
                """,
                (
                    project.id,
                    project.name,
                    project.created_at.isoformat(),
                    project.source_file_path,
                    project.source_format,
                    project.file_size_bytes,
                    project.message_count,
                    json.dumps(project.participants),
                    project.start_date.isoformat() if project.start_date else None,
                    project.end_date.isoformat() if project.end_date else None,
                    project.status,
                ),
            )
            conn.commit()

    def get_project(self, project_id: str) -> Optional[ProjectMetadata]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not row:
                return None
            return ProjectMetadata(
                id=row["id"],
                name=row["name"],
                created_at=datetime.fromisoformat(row["created_at"]),
                source_file_path=row["source_file_path"],
                source_format=row["source_format"],
                file_size_bytes=row["file_size_bytes"] or 0,
                message_count=row["message_count"] or 0,
                participants=json.loads(row["participants"] or "[]"),
                start_date=datetime.fromisoformat(row["start_date"]) if row["start_date"] else None,
                end_date=datetime.fromisoformat(row["end_date"]) if row["end_date"] else None,
                status=row["status"] or "imported",
            )

    def list_projects(self) -> List[ProjectMetadata]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
            projects = []
            for row in rows:
                projects.append(
                    ProjectMetadata(
                        id=row["id"],
                        name=row["name"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        source_file_path=row["source_file_path"],
                        source_format=row["source_format"],
                        file_size_bytes=row["file_size_bytes"] or 0,
                        message_count=row["message_count"] or 0,
                        participants=json.loads(row["participants"] or "[]"),
                        start_date=datetime.fromisoformat(row["start_date"]) if row["start_date"] else None,
                        end_date=datetime.fromisoformat(row["end_date"]) if row["end_date"] else None,
                        status=row["status"] or "imported",
                    )
                )
            return projects

    def delete_project(self, project_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()

    # ------------------ Messages ------------------

    def insert_messages_batch(self, project_id: str, messages: List[CanonicalMessage]) -> int:
        if not messages:
            return 0
        now = datetime.utcnow().isoformat()
        records = [
            (
                project_id,
                msg.source_id,
                msg.sender,
                msg.sender_id,
                msg.timestamp.isoformat(),
                msg.text,
                msg.reply_to_id,
                msg.media_type,
                1 if msg.is_system else 0,
                json.dumps(msg.metadata),
            )
            for msg in messages
        ]
        with self._get_connection() as conn:
            # Auto-ensure project exists
            conn.execute(
                "INSERT OR IGNORE INTO projects (id, name, created_at) VALUES (?, ?, ?)",
                (project_id, project_id, now),
            )
            cursor = conn.executemany(
                """
                INSERT OR IGNORE INTO messages (
                    project_id, source_id, sender, sender_id, timestamp,
                    text, reply_to_id, media_type, is_system, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                records,
            )
            inserted = cursor.rowcount
            conn.commit()
            return inserted

    def count_messages(self, project_id: str, exclude_system: bool = False) -> int:
        query = "SELECT COUNT(*) FROM messages WHERE project_id = ?"
        params: List[Any] = [project_id]
        if exclude_system:
            query += " AND is_system = 0"
        with self._get_connection() as conn:
            return conn.execute(query, params).fetchone()[0]

    def get_project_participants(self, project_id: str) -> List[str]:
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT sender FROM messages
                WHERE project_id = ? AND is_system = 0 AND sender IS NOT NULL AND sender != ''
                GROUP BY sender
                ORDER BY COUNT(*) DESC
                """,
                (project_id,),
            ).fetchall()
            return [r[0] for r in rows]

    def get_date_range(self, project_id: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM messages WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if not row or not row[0]:
                return None, None
            return datetime.fromisoformat(row[0]), datetime.fromisoformat(row[1])

    def get_messages_paginated(
        self,
        project_id: str,
        limit: int = 100,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        exclude_system: bool = True,
    ) -> List[CanonicalMessage]:
        query = "SELECT * FROM messages WHERE project_id = ?"
        params: List[Any] = [project_id]
        if exclude_system:
            query += " AND is_system = 0"
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        query += " ORDER BY timestamp ASC, id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_message(r) for r in rows]

    def get_all_messages_for_stats(
        self,
        project_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[CanonicalMessage]:
        query = "SELECT id, project_id, source_id, sender, sender_id, timestamp, text, reply_to_id, media_type, is_system FROM messages WHERE project_id = ?"
        params: List[Any] = [project_id]
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        query += " ORDER BY timestamp ASC, id ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                CanonicalMessage(
                    id=r["id"],
                    project_id=r["project_id"],
                    source_id=r["source_id"],
                    sender=r["sender"],
                    sender_id=r["sender_id"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                    text=r["text"] or "",
                    reply_to_id=r["reply_to_id"],
                    media_type=r["media_type"],
                    is_system=bool(r["is_system"]),
                    metadata={},
                )
                for r in rows
            ]

    def get_messages_by_ids(self, project_id: str, ids: List[int]) -> List[CanonicalMessage]:
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        query = f"SELECT * FROM messages WHERE project_id = ? AND id IN ({placeholders})"
        with self._get_connection() as conn:
            rows = conn.execute(query, [project_id, *ids]).fetchall()
            return [self._row_to_message(r) for r in rows]

    def get_message_context(
        self, project_id: str, message_id: int, before: int = 3, after: int = 3
    ) -> List[CanonicalMessage]:
        with self._get_connection() as conn:
            target = conn.execute(
                "SELECT timestamp FROM messages WHERE project_id = ? AND id = ?",
                (project_id, message_id),
            ).fetchone()
            if not target:
                return []
            target_ts = target[0]

            before_rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE project_id = ? AND (timestamp < ? OR (timestamp = ? AND id < ?))
                ORDER BY timestamp DESC, id DESC LIMIT ?
                """,
                (project_id, target_ts, target_ts, message_id, before),
            ).fetchall()

            curr_row = conn.execute(
                "SELECT * FROM messages WHERE project_id = ? AND id = ?",
                (project_id, message_id),
            ).fetchall()

            after_rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE project_id = ? AND (timestamp > ? OR (timestamp = ? AND id > ?))
                ORDER BY timestamp ASC, id ASC LIMIT ?
                """,
                (project_id, target_ts, target_ts, message_id, after),
            ).fetchall()

            all_rows = list(reversed(before_rows)) + list(curr_row) + list(after_rows)
            return [self._row_to_message(r) for r in all_rows]

    # ------------------ Jobs & Checkpoints ------------------

    def create_job(
        self,
        job_id: str,
        project_id: str,
        model_name: str,
        categories: List[str],
        total_chunks: int,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO projects (id, name, created_at) VALUES (?, ?, ?)",
                (project_id, project_id, now),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO analysis_jobs (
                    job_id, project_id, model_name, selected_categories,
                    stage, total_chunks, completed_chunks, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (job_id, project_id, model_name, json.dumps(categories), "STAGE_A_STATS", total_chunks, now, now),
            )
            conn.commit()

    def update_job_stage(
        self,
        job_id: str,
        stage: str,
        completed_chunks: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            if completed_chunks is not None:
                conn.execute(
                    """
                    UPDATE analysis_jobs
                    SET stage = ?, completed_chunks = ?, updated_at = ?, error_message = ?
                    WHERE job_id = ?
                    """,
                    (stage, completed_chunks, now, error_message, job_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE analysis_jobs
                    SET stage = ?, updated_at = ?, error_message = ?
                    WHERE job_id = ?
                    """,
                    (stage, now, error_message, job_id),
                )
            conn.commit()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row:
                return None
            return dict(row)

    def get_resumable_job_for_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Find the latest unfinished job that already has checkpoints to resume from."""
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT aj.*, COUNT(cc.chunk_index) as chunk_count
                FROM analysis_jobs aj
                LEFT JOIN chunk_checkpoints cc ON aj.job_id = cc.job_id
                WHERE aj.project_id = ? AND aj.stage != 'COMPLETED'
                GROUP BY aj.job_id
                ORDER BY chunk_count DESC, aj.updated_at DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if row and (row["chunk_count"] > 0 or row["stage"] != "STAGE_A_STATS"):
                return dict(row)
            return None

    def save_chunk_checkpoint(
        self,
        job_id: str,
        project_id: str,
        chunk_index: int,
        start_msg_id: int,
        end_msg_id: int,
        start_time: str,
        end_time: str,
        message_count: int,
        result: ChunkAnalysisResult,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO chunk_checkpoints (
                    job_id, project_id, chunk_index, start_msg_id, end_msg_id,
                    start_time, end_time, message_count, result_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    project_id,
                    chunk_index,
                    start_msg_id,
                    end_msg_id,
                    start_time,
                    end_time,
                    message_count,
                    result.model_dump_json(),
                    now,
                ),
            )
            conn.commit()

    def get_saved_chunk_indices(self, job_id: str) -> Set[int]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT chunk_index FROM chunk_checkpoints WHERE job_id = ?", (job_id,)
            ).fetchall()
            return {r[0] for r in rows}

    def get_chunk_results(self, job_id: str) -> List[ChunkAnalysisResult]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT result_json FROM chunk_checkpoints WHERE job_id = ? ORDER BY chunk_index ASC",
                (job_id,),
            ).fetchall()
            return [ChunkAnalysisResult.model_validate_json(r[0]) for r in rows]

    def save_temporal_summary(
        self,
        job_id: str,
        project_id: str,
        period_label: str,
        start_date: str,
        end_date: str,
        result: TemporalPeriodSummary,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO temporal_summaries (
                    job_id, project_id, period_label, start_date, end_date, result_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, project_id, period_label, start_date, end_date, result.model_dump_json(), now),
            )
            conn.commit()

    def get_temporal_summaries(self, job_id: str) -> List[TemporalPeriodSummary]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT result_json FROM temporal_summaries WHERE job_id = ? ORDER BY start_date ASC",
                (job_id,),
            ).fetchall()
            return [TemporalPeriodSummary.model_validate_json(r[0]) for r in rows]

    # ------------------ Reports ------------------

    def save_report(self, report_id: str, job_id: str, report: FinalReport) -> None:
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO reports (
                    id, project_id, job_id, generated_at, model_used, report_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (report_id, report.project_id, job_id, now, report.model_used, report.model_dump_json()),
            )
            conn.commit()

    def get_report(self, report_id: str) -> Optional[FinalReport]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT report_json FROM reports WHERE id = ?", (report_id,)).fetchone()
            if not row:
                return None
            return FinalReport.model_validate_json(row[0])

    def get_latest_report_for_project(self, project_id: str) -> Optional[FinalReport]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT report_json FROM reports WHERE project_id = ? ORDER BY generated_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            if not row:
                return None
            return FinalReport.model_validate_json(row[0])

    # ------------------ Helpers ------------------

    def _row_to_message(self, row: sqlite3.Row) -> CanonicalMessage:
        return CanonicalMessage(
            id=row["id"],
            project_id=row["project_id"],
            source_id=row["source_id"],
            sender=row["sender"],
            sender_id=row["sender_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            text=row["text"] or "",
            reply_to_id=row["reply_to_id"],
            media_type=row["media_type"],
            is_system=bool(row["is_system"]),
            metadata=json.loads(row["metadata"] or "{}"),
        )
