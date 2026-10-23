"""Background QThread worker for executing the multi-stage analysis pipeline."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import List, Optional

from PySide6.QtCore import QThread, Signal

from relationship_analyst.ai.mock_engine import MockInferenceEngine
from relationship_analyst.ai.ollama_client import OllamaClient
from relationship_analyst.database.repository import Repository
from relationship_analyst.models.analysis import FinalReport
from relationship_analyst.pipeline.orchestrator import AnalysisPipelineOrchestrator

logger = logging.getLogger(__name__)


class AnalysisWorker(QThread):
    """Executes analysis pipeline in background without blocking the UI."""

    progress_signal = Signal(str, float, str)  # (stage, percentage, status_msg)
    finished_signal = Signal(object)           # FinalReport
    error_signal = Signal(str)

    def __init__(
        self,
        repository: Repository,
        project_id: str,
        model_name: str,
        categories: List[str],
        chunk_size: int = 80,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        ollama_client: Optional[OllamaClient] = None,
        mock_engine: Optional[MockInferenceEngine] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.project_id = project_id
        self.model_name = model_name
        self.categories = categories
        self.chunk_size = chunk_size
        self.start_date = start_date
        self.end_date = end_date

        # Ensure real Ollama client is instantiated for any non-mock model
        if ollama_client is None and model_name != "mock:test":
            ollama_client = OllamaClient()

        self.orchestrator = AnalysisPipelineOrchestrator(
            repository=repository,
            ollama_client=ollama_client,
            mock_engine=mock_engine,
        )

    def cancel(self) -> None:
        self.orchestrator.cancel()

    def run(self) -> None:
        try:
            def on_progress(stage: str, pct: float, msg: str):
                self.progress_signal.emit(stage, pct, msg)

            report = self.orchestrator.run_analysis(
                project_id=self.project_id,
                model_name=self.model_name,
                selected_categories=self.categories,
                chunk_size=self.chunk_size,
                start_date=self.start_date,
                end_date=self.end_date,
                progress_cb=on_progress,
            )
            self.finished_signal.emit(report)

        except InterruptedError:
            self.error_signal.emit("Analysis was stopped/cancelled by user.")
        except Exception as e:
            logger.exception("Analysis pipeline error: %s", e)
            self.error_signal.emit(f"Analysis failed: {str(e)}")
