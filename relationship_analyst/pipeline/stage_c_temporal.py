"""Stage C: Temporal Aggregation into chronological periods."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
import logging
from typing import Callable, Dict, List, Optional

from relationship_analyst.ai.mock_engine import MockInferenceEngine
from relationship_analyst.ai.ollama_client import OllamaClient
from relationship_analyst.ai.parser import parse_and_validate
from relationship_analyst.ai.prompts import TEMPORAL_SYSTEM_PROMPT, build_temporal_prompt
from relationship_analyst.database.repository import Repository
from relationship_analyst.models.analysis import (
    ChunkAnalysisResult,
    ChunkObservation,
    EvidenceItem,
    TemporalPeriodSummary,
)
from relationship_analyst.models.statistics import DeterministicStats

logger = logging.getLogger(__name__)


def aggregate_temporal_periods(
    repository: Repository,
    job_id: str,
    project_id: str,
    chunk_results: List[ChunkAnalysisResult],
    deterministic_stats: DeterministicStats,
    categories: List[str],
    model_name: str,
    ollama_client: Optional[OllamaClient] = None,
    mock_engine: Optional[MockInferenceEngine] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> List[TemporalPeriodSummary]:
    """
    Group observations chronologically (monthly/quarterly) and synthesize temporal summaries.
    """
    # Group chunk results into monthly or quarterly buckets based on start_time
    period_buckets: Dict[str, List[ChunkObservation]] = defaultdict(list)
    period_ranges: Dict[str, Dict[str, str]] = {}

    for cr in chunk_results:
        # Determine period key (YYYY-MM or YYYY-QX)
        try:
            dt = datetime.fromisoformat(cr.start_time)
            period_key = dt.strftime("%Y-%m")
        except Exception:
            period_key = "General Timeline"

        period_buckets[period_key].extend(cr.observations)

        if period_key not in period_ranges:
            period_ranges[period_key] = {"start": cr.start_time, "end": cr.end_time}
        else:
            period_ranges[period_key]["end"] = cr.end_time

    # Check already saved temporal summaries
    existing_summaries = {s.period_label: s for s in repository.get_temporal_summaries(job_id)}
    periods = sorted(period_buckets.keys())
    total_periods = len(periods)
    summaries: List[TemporalPeriodSummary] = []

    use_mock = (model_name == "mock:test")
    if not use_mock and ollama_client is None:
        ollama_client = OllamaClient()
    mock = mock_engine or MockInferenceEngine()

    for idx, period_key in enumerate(periods):
        if is_cancelled and is_cancelled():
            logger.info("Stage C cancelled by user at period %s", period_key)
            break

        if period_key in existing_summaries:
            summaries.append(existing_summaries[period_key])
            if progress_callback:
                progress_callback(idx + 1, total_periods, f"Period {period_key} restored from checkpoint.")
            continue

        obs_list = period_buckets[period_key]
        p_range = period_ranges.get(period_key, {"start": "", "end": ""})

        if use_mock:
            summary = mock.summarize_period(
                period_label=period_key,
                observations=obs_list,
                stats=deterministic_stats,
                categories=categories,
            )
        else:
            obs_dict_list = [o.model_dump() for o in obs_list[:25]]
            obs_json = json.dumps(obs_dict_list, indent=2)
            stats_text = deterministic_stats.summary_text()
            prompt = build_temporal_prompt(period_key, obs_json, categories, stats_text)

            try:
                raw_json = ollama_client.generate_json(
                    model=model_name,
                    prompt=prompt,
                    system_prompt=TEMPORAL_SYSTEM_PROMPT,
                    temperature=0.2,
                )
                summary = parse_and_validate(raw_json, TemporalPeriodSummary)
                summary.period_label = period_key
                summary.start_date = p_range["start"]
                summary.end_date = p_range["end"]
                summary.message_count = sum(1 for cr in chunk_results if period_key in cr.start_time)
            except Exception as e:
                logger.error("LLM temporal summary failed for %s: %s", period_key, e)
                raise RuntimeError(
                    f"Model '{model_name}' failed summarizing period '{period_key}': {str(e)}. "
                    "Ensure Ollama is running properly."
                ) from e

        repository.save_temporal_summary(
            job_id=job_id,
            project_id=project_id,
            period_label=period_key,
            start_date=summary.start_date,
            end_date=summary.end_date,
            result=summary,
        )
        summaries.append(summary)

        if progress_callback:
            progress_callback(idx + 1, total_periods, f"Aggregated period {period_key} ({idx + 1}/{total_periods})")

    return summaries
