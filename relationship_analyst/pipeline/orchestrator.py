"""Pipeline Orchestrator coordinating all stages with cancellation and checkpoint resumption."""
from __future__ import annotations

from datetime import datetime
import logging
import time
from typing import Callable, List, Optional
import uuid

from relationship_analyst.ai.mock_engine import MockInferenceEngine
from relationship_analyst.ai.ollama_client import OllamaClient
from relationship_analyst.config import CATEGORY_KEYS, DEFAULT_CHUNK_SIZE
from relationship_analyst.database.repository import Repository
from relationship_analyst.models.analysis import FinalReport
from relationship_analyst.pipeline.stage_a_stats import calculate_deterministic_stats
from relationship_analyst.pipeline.stage_b_chunks import create_chunks, process_chunks
from relationship_analyst.pipeline.stage_c_temporal import aggregate_temporal_periods
from relationship_analyst.pipeline.stage_d_synthesis import synthesize_final_report

logger = logging.getLogger(__name__)


class AnalysisPipelineOrchestrator:
    """Manages the full multi-stage relationship analysis lifecycle."""

    def __init__(
        self,
        repository: Repository,
        ollama_client: Optional[OllamaClient] = None,
        mock_engine: Optional[MockInferenceEngine] = None,
    ):
        self.repository = repository
        self.ollama_client = ollama_client or OllamaClient()
        self.mock_engine = mock_engine or MockInferenceEngine()
        self._cancelled = False

    def reset_cancellation(self) -> None:
        """Reset cancellation flag before a new run."""
        self._cancelled = False

    def cancel(self) -> None:
        """Signal safe cancellation."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run_analysis(
        self,
        project_id: str,
        model_name: str,
        selected_categories: Optional[List[str]] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        job_id: Optional[str] = None,
        progress_cb: Optional[Callable[[str, float, str], None]] = None,
    ) -> FinalReport:
        """
        Execute full staged pipeline.
        progress_cb: callback(stage_name, progress_percentage, description)
        """
        categories = selected_categories or CATEGORY_KEYS

        project = self.repository.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        # Check or resume existing Job
        if not job_id:
            resumable = self.repository.get_resumable_job_for_project(project_id)
            if resumable:
                job_id = resumable["job_id"]
                logger.info("Resuming existing job %s for project %s at stage %s", job_id, project_id, resumable.get("stage"))
            else:
                job_id = f"job_{uuid.uuid4().hex[:12]}"

        if not self.repository.get_job(job_id):
            total_msgs = self.repository.count_messages(project_id, exclude_system=True)
            est_chunks = max(1, (total_msgs + chunk_size - 1) // chunk_size)
            self.repository.create_job(
                job_id=job_id,
                project_id=project_id,
                model_name=model_name,
                categories=categories,
                total_chunks=est_chunks,
            )

        start_time = time.time()

        # ================= STAGE A: DETERMINISTIC STATISTICS =================
        if self._cancelled:
            self._handle_cancel(job_id)
            raise InterruptedError("Analysis cancelled by user.")

        if progress_cb:
            progress_cb("Stage A: Deterministic Statistics", 5.0, "Calculating conversational metrics...")

        self.repository.update_job_stage(job_id, "STAGE_A_STATS")
        det_stats = calculate_deterministic_stats(
            self.repository, project_id, start_date=start_date, end_date=end_date
        )

        # ================= STAGE B: CHUNK-LEVEL INTERPRETATION =================
        if self._cancelled:
            self._handle_cancel(job_id)
            raise InterruptedError("Analysis cancelled by user.")

        if progress_cb:
            progress_cb("Stage B: Chunk Interpretation", 15.0, "Fetching chronological messages...")

        messages = self.repository.get_messages_paginated(
            project_id=project_id,
            limit=1000000,
            offset=0,
            start_date=start_date,
            end_date=end_date,
            exclude_system=True,
        )

        chunks = create_chunks(messages, chunk_size=chunk_size)
        total_chunks = len(chunks)
        participants = self.repository.get_project_participants(project_id)

        def stage_b_progress(completed: int, total: int, msg: str):
            pct = 15.0 + (55.0 * (completed / max(1, total)))
            if progress_cb:
                progress_cb("Stage B: Chunk Interpretation", pct, msg)

        chunk_results = process_chunks(
            repository=self.repository,
            job_id=job_id,
            project_id=project_id,
            chunks=chunks,
            categories=categories,
            participants=participants,
            model_name=model_name,
            ollama_client=self.ollama_client,
            mock_engine=self.mock_engine,
            is_cancelled=self.is_cancelled,
            progress_callback=stage_b_progress,
        )

        if self._cancelled:
            self._handle_cancel(job_id)
            raise InterruptedError("Analysis cancelled by user.")

        # ================= STAGE C: TEMPORAL AGGREGATION =================
        if progress_cb:
            progress_cb("Stage C: Temporal Aggregation", 72.0, "Synthesizing chronological periods...")

        self.repository.update_job_stage(job_id, "STAGE_C_TEMPORAL")

        def stage_c_progress(completed: int, total: int, msg: str):
            pct = 72.0 + (16.0 * (completed / max(1, total)))
            if progress_cb:
                progress_cb("Stage C: Temporal Aggregation", pct, msg)

        temporal_summaries = aggregate_temporal_periods(
            repository=self.repository,
            job_id=job_id,
            project_id=project_id,
            chunk_results=chunk_results,
            deterministic_stats=det_stats,
            categories=categories,
            model_name=model_name,
            ollama_client=self.ollama_client,
            mock_engine=self.mock_engine,
            is_cancelled=self.is_cancelled,
            progress_callback=stage_c_progress,
        )

        if self._cancelled:
            self._handle_cancel(job_id)
            raise InterruptedError("Analysis cancelled by user.")

        # ================= STAGE D: FINAL SYNTHESIS =================
        if progress_cb:
            progress_cb("Stage D: Final Synthesis", 90.0, "Generating multi-category relationship review...")

        self.repository.update_job_stage(job_id, "STAGE_D_SYNTHESIS")

        def stage_d_progress(step: int, total: int, msg: str):
            pct = 90.0 + (10.0 * (step / total))
            if progress_cb:
                progress_cb("Stage D: Final Synthesis", pct, msg)

        report = synthesize_final_report(
            repository=self.repository,
            job_id=job_id,
            project_id=project_id,
            project_name=project.name,
            deterministic_stats=det_stats,
            temporal_summaries=temporal_summaries,
            chunk_results=chunk_results,
            categories=categories,
            model_name=model_name,
            ollama_client=self.ollama_client,
            mock_engine=self.mock_engine,
            is_cancelled=self.is_cancelled,
            progress_callback=stage_d_progress,
        )

        elapsed = time.time() - start_time
        logger.info("Pipeline completed in %.2f seconds for project %s", elapsed, project_id)

        if progress_cb:
            progress_cb("Completed", 100.0, f"Analysis finished in {elapsed:.1f}s.")

        return report

    def _handle_cancel(self, job_id: str) -> None:
        self.repository.update_job_stage(job_id, "CANCELLED", error_message="Cancelled by user.")
