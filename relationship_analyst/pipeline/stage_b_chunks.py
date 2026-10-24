"""Stage B: Chunk-level interpretation with checkpointing and resumability."""
from __future__ import annotations

import logging
from typing import Callable, List, Optional

from relationship_analyst.ai.mock_engine import MockInferenceEngine
from relationship_analyst.ai.ollama_client import OllamaClient
from relationship_analyst.ai.parser import parse_and_validate
from relationship_analyst.ai.prompts import CHUNK_SYSTEM_PROMPT, build_chunk_prompt
from relationship_analyst.database.repository import Repository
from relationship_analyst.models.analysis import ChunkAnalysisResult
from relationship_analyst.models.message import CanonicalMessage, format_compact_chunk_messages

logger = logging.getLogger(__name__)


def create_chunks(
    messages: List[CanonicalMessage],
    chunk_size: int = 80,
) -> List[List[CanonicalMessage]]:
    """Divide messages chronologically into manageable chunks."""
    chunks: List[List[CanonicalMessage]] = []
    current_chunk: List[CanonicalMessage] = []

    for msg in messages:
        current_chunk.append(msg)
        if len(current_chunk) >= chunk_size:
            chunks.append(current_chunk)
            current_chunk = []

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def process_chunks(
    repository: Repository,
    job_id: str,
    project_id: str,
    chunks: List[List[CanonicalMessage]],
    categories: List[str],
    participants: List[str],
    model_name: str,
    ollama_client: Optional[OllamaClient] = None,
    mock_engine: Optional[MockInferenceEngine] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> List[ChunkAnalysisResult]:
    """
    Process chunks sequentially, skipping already-checkpointed chunks.
    Ensures resumability and safe cancellation.
    """
    saved_indices = repository.get_saved_chunk_indices(job_id)
    total_chunks = len(chunks)
    results: List[ChunkAnalysisResult] = []

    use_mock = (model_name == "mock:test")
    if not use_mock and ollama_client is None:
        ollama_client = OllamaClient()
    mock = mock_engine or MockInferenceEngine()

    for idx, chunk in enumerate(chunks):
        if is_cancelled and is_cancelled():
            logger.info("Stage B cancelled by user at chunk %d/%d", idx, total_chunks)
            break

        # Checkpoint check
        if idx in saved_indices:
            if progress_callback:
                progress_callback(idx + 1, total_chunks, f"Chunk {idx + 1}/{total_chunks} restored from checkpoint.")
            continue

        start_msg = chunk[0]
        end_msg = chunk[-1]

        if progress_callback:
            progress_callback(idx, total_chunks, f"Sending chunk {idx + 1}/{total_chunks} ({len(chunk)} msgs) to local model '{model_name}'...")

        if use_mock:
            chunk_result = mock.analyze_chunk(
                chunk_index=idx,
                messages=chunk,
                categories=categories,
            )
        else:
            messages_text = format_compact_chunk_messages(chunk)
            prompt = build_chunk_prompt(messages_text, categories, participants)
            try:
                raw_json = ollama_client.generate_json(
                    model=model_name,
                    prompt=prompt,
                    system_prompt=CHUNK_SYSTEM_PROMPT,
                    temperature=0.2,
                    num_predict=950,
                )
                chunk_result = parse_and_validate(raw_json, ChunkAnalysisResult)
                chunk_result.chunk_index = idx
                chunk_result.start_msg_id = start_msg.id or 1
                chunk_result.end_msg_id = end_msg.id or 1
                chunk_result.start_time = start_msg.timestamp.isoformat()
                chunk_result.end_time = end_msg.timestamp.isoformat()
                chunk_result.message_count = len(chunk)
            except Exception as e:
                logger.error("LLM chunk analysis failed on chunk %d: %s", idx, e)
                raise RuntimeError(
                    f"Model '{model_name}' failed analyzing chunk {idx + 1}/{total_chunks}: {str(e)}. "
                    "Analysis paused. Checkpoints have been saved and you can resume once resolved."
                ) from e

        # Persist checkpoint immediately
        repository.save_chunk_checkpoint(
            job_id=job_id,
            project_id=project_id,
            chunk_index=idx,
            start_msg_id=start_msg.id or 1,
            end_msg_id=end_msg.id or 1,
            start_time=start_msg.timestamp.isoformat(),
            end_time=end_msg.timestamp.isoformat(),
            message_count=len(chunk),
            result=chunk_result,
        )

        results.append(chunk_result)

        if progress_callback:
            progress_callback(idx + 1, total_chunks, f"Analyzed chunk {idx + 1}/{total_chunks} ({len(chunk)} msgs)")

        repository.update_job_stage(job_id, "STAGE_B_CHUNKS", completed_chunks=idx + 1)

    # Return all results from DB to include restored ones
    return repository.get_chunk_results(job_id)
