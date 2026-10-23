"""Tests for multi-stage analysis pipeline, checkpointing, and resumability."""
from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from relationship_analyst.ai.mock_engine import MockInferenceEngine
from relationship_analyst.database.repository import Repository
from relationship_analyst.models.message import CanonicalMessage, ProjectMetadata
from relationship_analyst.pipeline.orchestrator import AnalysisPipelineOrchestrator
from relationship_analyst.pipeline.stage_b_chunks import create_chunks


def _create_sample_messages(project_id: str, count: int = 60) -> list[CanonicalMessage]:
    start = datetime(2023, 1, 1, 9, 0, 0)
    msgs = []
    for i in range(1, count + 1):
        sender = "Alex" if i % 2 == 1 else "Jordan"
        msgs.append(
            CanonicalMessage(
                id=i,
                project_id=project_id,
                source_id=str(i),
                sender=sender,
                timestamp=start + timedelta(minutes=i * 5),
                text=f"Message {i} from {sender}: discussing project plans and sharing details.",
            )
        )
    return msgs


def test_chunk_creation():
    msgs = _create_sample_messages("test_p", 100)
    chunks = create_chunks(msgs, chunk_size=30)
    assert len(chunks) == 4
    assert len(chunks[0]) == 30
    assert len(chunks[1]) == 30
    assert len(chunks[2]) == 30
    assert len(chunks[3]) == 10


def test_pipeline_execution_and_checkpointing(temp_repo: Repository):
    project_id = "test_pipe_proj"
    temp_repo.create_or_update_project(
        ProjectMetadata(
            id=project_id,
            name="Alex & Jordan Test",
            message_count=60,
            participants=["Alex", "Jordan"],
        )
    )

    msgs = _create_sample_messages(project_id, 60)
    temp_repo.insert_messages_batch(project_id, msgs)

    mock_engine = MockInferenceEngine()
    orchestrator = AnalysisPipelineOrchestrator(
        repository=temp_repo,
        mock_engine=mock_engine,
    )

    stages_seen = []

    def on_prog(stage: str, pct: float, msg: str):
        stages_seen.append(stage)

    # First run: chunk size 20 -> 3 chunks
    report = orchestrator.run_analysis(
        project_id=project_id,
        model_name="mock:test",
        selected_categories=["communication", "effort_reciprocity", "affection_warmth"],
        chunk_size=20,
        job_id="job_test_1",
        progress_cb=on_prog,
    )

    assert report is not None
    assert report.project_id == project_id
    assert "communication" in report.categories
    assert "effort_reciprocity" in report.categories
    assert "affection_warmth" in report.categories

    # Verify checkpoints were persisted in SQLite
    saved_chunks = temp_repo.get_saved_chunk_indices("job_test_1")
    assert saved_chunks == {0, 1, 2}

    # Verify report was saved in SQLite reports table
    saved_report = temp_repo.get_latest_report_for_project(project_id)
    assert saved_report is not None
    assert saved_report.project_id == project_id


def test_pipeline_resumption_skips_saved_chunks(temp_repo: Repository):
    project_id = "test_resume_proj"
    temp_repo.create_or_update_project(
        ProjectMetadata(
            id=project_id,
            name="Resume Test",
            message_count=40,
            participants=["Alex", "Jordan"],
        )
    )
    msgs = _create_sample_messages(project_id, 40)
    temp_repo.insert_messages_batch(project_id, msgs)

    mock_engine = MockInferenceEngine()
    orchestrator = AnalysisPipelineOrchestrator(
        repository=temp_repo,
        mock_engine=mock_engine,
    )

    job_id = "job_resumable_1"

    # Pre-save chunk 0 into database
    chunk_0 = msgs[:20]
    c0_result = mock_engine.analyze_chunk(0, chunk_0, ["communication"])
    temp_repo.create_job(job_id, project_id, "mock:test", ["communication"], total_chunks=2)
    temp_repo.save_chunk_checkpoint(
        job_id=job_id,
        project_id=project_id,
        chunk_index=0,
        start_msg_id=1,
        end_msg_id=20,
        start_time=chunk_0[0].timestamp.isoformat(),
        end_time=chunk_0[-1].timestamp.isoformat(),
        message_count=20,
        result=c0_result,
    )

    # Run analysis with this existing job_id
    report = orchestrator.run_analysis(
        project_id=project_id,
        model_name="mock:test",
        selected_categories=["communication"],
        chunk_size=20,
        job_id=job_id,
    )

    # Both chunk 0 and chunk 1 should be in final results
    saved_chunks = temp_repo.get_saved_chunk_indices(job_id)
    assert saved_chunks == {0, 1}
    assert report is not None


def test_pipeline_cancellation(temp_repo: Repository):
    project_id = "test_cancel_proj"
    temp_repo.create_or_update_project(
        ProjectMetadata(
            id=project_id,
            name="Cancel Test",
            message_count=40,
            participants=["Alex", "Jordan"],
        )
    )
    msgs = _create_sample_messages(project_id, 40)
    temp_repo.insert_messages_batch(project_id, msgs)

    orchestrator = AnalysisPipelineOrchestrator(repository=temp_repo)
    orchestrator.cancel()  # Signal cancellation immediately

    with pytest.raises(InterruptedError):
        orchestrator.run_analysis(
            project_id=project_id,
            model_name="mock:test",
            job_id="job_cancelled_1",
        )

    job = temp_repo.get_job("job_cancelled_1")
    assert job["stage"] == "CANCELLED"
