"""Stage D: Final Synthesis across all relationship categories."""
from __future__ import annotations

import json
import logging
from typing import Callable, List, Optional
import uuid

from relationship_analyst.ai.mock_engine import MockInferenceEngine
from relationship_analyst.ai.ollama_client import OllamaClient
from relationship_analyst.ai.parser import parse_and_validate
from relationship_analyst.ai.prompts import (
    SYNTHESIS_SYSTEM_PROMPT,
    build_overall_synthesis_prompt,
    build_single_category_prompt,
    build_synthesis_prompt,
)
from relationship_analyst.config import CATEGORIES
from relationship_analyst.database.repository import Repository
from relationship_analyst.models.analysis import (
    CategoryReport,
    ChunkAnalysisResult,
    FinalReport,
    OverallSynthesisResult,
    TemporalPeriodSummary,
)
from relationship_analyst.models.statistics import DeterministicStats
from relationship_analyst.pipeline.validator import validate_report_evidence

logger = logging.getLogger(__name__)


def synthesize_final_report(
    repository: Repository,
    job_id: str,
    project_id: str,
    project_name: str,
    deterministic_stats: DeterministicStats,
    temporal_summaries: List[TemporalPeriodSummary],
    chunk_results: List[ChunkAnalysisResult],
    categories: List[str],
    model_name: str,
    ollama_client: Optional[OllamaClient] = None,
    mock_engine: Optional[MockInferenceEngine] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> FinalReport:
    """
    Synthesize complete relationship report, validating all cited evidence against SQLite.
    When using a local LLM, synthesizes the overall dynamic and individual categories
    in bounded, fast sub-requests to avoid CPU timeout errors.
    """
    use_mock = (model_name == "mock:test")
    if not use_mock and ollama_client is None:
        ollama_client = OllamaClient()
    mock = mock_engine or MockInferenceEngine()

    total_steps = len(categories) + 2

    if use_mock:
        if progress_callback:
            progress_callback(1, total_steps, "Synthesizing final findings across categories...")
        report = mock.synthesize_report(
            project_id=project_id,
            project_name=project_name,
            deterministic_stats=deterministic_stats,
            temporal_summaries=temporal_summaries,
            chunk_results=chunk_results,
            categories=categories,
        )
    else:
        stats_text = deterministic_stats.summary_text()
        temporal_text = json.dumps([s.model_dump() for s in temporal_summaries], indent=2)

        # Collect all observations from Stage B
        all_obs = []
        for cr in chunk_results:
            all_obs.extend(cr.observations)

        current_step = 1

        if progress_callback:
            progress_callback(current_step, total_steps, "Synthesizing overall relationship dynamic...")

        # 1. Overall assessment and trajectory timeline
        sample_obs_lines = []
        for o in all_obs[:40]:
            ev_str = "; ".join(f'"{e.quote}" (#{e.message_id})' for e in o.evidence if e.quote)
            sample_obs_lines.append(f"- [{o.category}] {o.claim} (Focus: {o.participant_focus}) | {ev_str}")
        obs_text_sample = "\n".join(sample_obs_lines)

        overall_prompt = build_overall_synthesis_prompt(
            project_name=project_name,
            deterministic_stats_text=stats_text,
            temporal_summaries_text=temporal_text,
            observations_text=obs_text_sample,
        )

        try:
            raw_overall = ollama_client.generate_json(
                model=model_name,
                prompt=overall_prompt,
                system_prompt=SYNTHESIS_SYSTEM_PROMPT,
                temperature=0.25,
            )
            overall_res = parse_and_validate(raw_overall, OverallSynthesisResult)
        except Exception as e:
            logger.warning("Overall synthesis call failed, using default summary: %s", e)
            overall_res = OverallSynthesisResult(
                overall_assessment=f"Conversational pattern analysis for {project_name} across {len(categories)} relationship dimensions.",
                coverage_summary=f"Analysis of {len(chunk_results)} message chunks covering {len(temporal_summaries)} time periods.",
            )

        # 2. Category-by-category synthesis
        category_reports = {}
        for idx, cat_key in enumerate(categories):
            if is_cancelled and is_cancelled():
                logger.info("Stage D cancelled by user at category %s", cat_key)
                break

            current_step += 1
            cat_info = CATEGORIES.get(cat_key, {})
            cat_title = cat_info.get("title", cat_key)
            cat_desc = cat_info.get("description", "")

            if progress_callback:
                progress_callback(
                    current_step,
                    total_steps,
                    f"Synthesizing category: {cat_title} ({idx + 1}/{len(categories)})...",
                )

            # Get observations specific to this category
            cat_obs = [o for o in all_obs if o.category == cat_key]
            if not cat_obs:
                cat_obs = all_obs[:8]  # Contextual fallback

            cat_obs_lines = []
            for o in cat_obs[:25]:
                ev_str = "; ".join(f'"{e.quote}" (msg #{e.message_id} by {e.sender})' for e in o.evidence if e.quote)
                cat_obs_lines.append(f"- {o.claim} (Sentiment: {o.sentiment}, Focus: {o.participant_focus}) | Quotes: {ev_str}")
            cat_obs_text = "\n".join(cat_obs_lines)

            cat_prompt = build_single_category_prompt(
                category_key=cat_key,
                category_title=cat_title,
                category_description=cat_desc,
                project_name=project_name,
                stats_text=stats_text,
                temporal_text=temporal_text,
                observations_text=cat_obs_text,
            )

            try:
                raw_cat_json = ollama_client.generate_json(
                    model=model_name,
                    prompt=cat_prompt,
                    system_prompt=SYNTHESIS_SYSTEM_PROMPT,
                    temperature=0.2,
                )
                cat_report = parse_and_validate(raw_cat_json, CategoryReport)
                cat_report.category_id = cat_key
                cat_report.category_title = cat_title
                category_reports[cat_key] = cat_report
            except Exception as e:
                logger.error("Failed to synthesize category %s: %s", cat_key, e)
                # Create a graceful fallback category report from available observations
                category_reports[cat_key] = CategoryReport(
                    category_id=cat_key,
                    category_title=cat_title,
                    concise_assessment=f"Observations for {cat_title} gathered from {len(cat_obs)} conversational exchanges.",
                    supporting_observations=[o.claim for o in cat_obs[:5] if o.claim],
                    confidence_level="Low",
                    confidence_justification="Automated synthesis encountered an issue; raw observations preserved.",
                    limitations="Limited direct evidence in chat extract.",
                )

        report = FinalReport(
            project_id=project_id,
            project_name=project_name,
            model_used=model_name,
            coverage_summary=overall_res.coverage_summary,
            overall_assessment=overall_res.overall_assessment,
            categories=category_reports,
            trajectory_timeline=overall_res.trajectory_timeline,
            deterministic_stats=deterministic_stats.model_dump(),
        )

    if progress_callback:
        progress_callback(total_steps, total_steps, "Validating citations against message database...")

    # Validate all citations against SQLite database
    report = validate_report_evidence(report, repository)

    # Save to SQLite
    report_id = f"rep_{uuid.uuid4().hex[:12]}"
    repository.save_report(report_id, job_id, report)
    repository.update_job_stage(job_id, "COMPLETED")

    return report
