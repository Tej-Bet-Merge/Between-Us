"""Deterministic local mock engine for testing, verification, and offline operation."""
from __future__ import annotations

import re
from typing import List, Optional
from relationship_analyst.config import CATEGORIES
from relationship_analyst.models.analysis import (
    CategoryReport,
    ChunkAnalysisResult,
    ChunkObservation,
    EvidenceItem,
    FinalReport,
    TemporalPeriodSummary,
)
from relationship_analyst.models.message import CanonicalMessage
from relationship_analyst.models.statistics import DeterministicStats


class MockInferenceEngine:
    """Generates schema-compliant, realistic findings derived directly from input messages."""

    def analyze_chunk(
        self,
        chunk_index: int,
        messages: List[CanonicalMessage],
        categories: List[str],
    ) -> ChunkAnalysisResult:
        if not messages:
            return ChunkAnalysisResult(
                chunk_index=chunk_index,
                start_msg_id=0,
                end_msg_id=0,
                start_time="",
                end_time="",
                message_count=0,
                observations=[],
            )

        start_msg = messages[0]
        end_msg = messages[-1]

        observations: List[ChunkObservation] = []

        # Find interesting messages to cite
        for cat_id in categories[:4]:  # extract 2-4 observations per chunk
            target_msg = None
            evidence_type = "behavioral_pattern"
            sentiment = "neutral"
            claim = ""

            if cat_id == "communication":
                # Find message with question or dialogue
                for m in messages:
                    if "?" in m.text:
                        target_msg = m
                        claim = f"{m.sender} uses direct questioning to keep conversation active."
                        sentiment = "positive"
                        evidence_type = "direct_quote"
                        break
                if not target_msg:
                    target_msg = messages[0]
                    claim = f"{target_msg.sender} and {messages[-1].sender} maintain steady conversational pacing."

            elif cat_id == "effort_reciprocity":
                target_msg = messages[len(messages) // 2]
                claim = f"Both participants contribute with consistent turn-taking and balanced replies."
                sentiment = "positive"

            elif cat_id == "emotional_support":
                # Look for emotional or supportive words
                for m in messages:
                    low = m.text.lower()
                    if any(w in low for w in ("thanks", "hope", "sorry", "great", "care", "help", "feel", "appreciate")):
                        target_msg = m
                        claim = f"{m.sender} provides validation and supportive acknowledgement."
                        sentiment = "positive"
                        evidence_type = "direct_quote"
                        break
                if not target_msg:
                    target_msg = messages[-1]
                    claim = f"Subtle mutual attentiveness shown during routine scheduling exchanges."

            elif cat_id == "affection_warmth":
                for m in messages:
                    low = m.text.lower()
                    if any(w in low for w in ("love", "haha", "lol", ":)", "miss", "hug", "goodnight", "sweet")):
                        target_msg = m
                        claim = f"{m.sender} expresses warmth and shared humor."
                        sentiment = "positive"
                        evidence_type = "direct_quote"
                        break
                if not target_msg:
                    target_msg = messages[0]
                    claim = f"Even-toned, cordial interaction without overt conflict."

            elif cat_id == "conflict_repair":
                for m in messages:
                    low = m.text.lower()
                    if any(w in low for w in ("disagree", "wait", "no", "problem", "sorry", "apologize", "misunderstood")):
                        target_msg = m
                        claim = f"Constructive clarification and repair attempted following friction."
                        sentiment = "mixed"
                        evidence_type = "direct_quote"
                        break
                if not target_msg:
                    target_msg = messages[0]
                    claim = f"No active disagreements observed in this segment."

            else:
                target_msg = messages[0]
                claim = f"Normative relational exchange reflecting mutual comfort."

            if target_msg:
                snippet = (target_msg.text[:80] + "...") if len(target_msg.text) > 80 else target_msg.text
                evidence_item = EvidenceItem(
                    message_id=target_msg.id or int(re.sub(r"\D", "", target_msg.source_id) or "1"),
                    timestamp=target_msg.timestamp.strftime("%Y-%m-%d %H:%M"),
                    sender=target_msg.sender,
                    quote=snippet or f"<{target_msg.media_type or 'media'}>",
                    is_verified=True,
                )
                observations.append(
                    ChunkObservation(
                        category=cat_id,
                        claim=claim,
                        evidence=[evidence_item],
                        sentiment=sentiment,
                        participant_focus=target_msg.sender if evidence_type == "direct_quote" else "both",
                        evidence_type=evidence_type,
                        ambiguity_note="Tone in short messaging is naturally subject to alternative interpretations.",
                    )
                )

        return ChunkAnalysisResult(
            chunk_index=chunk_index,
            start_msg_id=start_msg.id or 1,
            end_msg_id=end_msg.id or 1,
            start_time=start_msg.timestamp.isoformat(),
            end_time=end_msg.timestamp.isoformat(),
            message_count=len(messages),
            observations=observations,
        )

    def summarize_period(
        self,
        period_label: str,
        observations: List[ChunkObservation],
        stats: DeterministicStats,
        categories: List[str],
    ) -> TemporalPeriodSummary:
        start_date = stats.start_date.strftime("%Y-%m-%d") if stats.start_date else ""
        end_date = stats.end_date.strftime("%Y-%m-%d") if stats.end_date else ""

        category_summaries = {}
        for cat in categories:
            cat_obs = [o for o in observations if o.category == cat]
            if cat_obs:
                category_summaries[cat] = f"Characterized by {len(cat_obs)} observed interactions indicating {cat_obs[0].claim.lower()}"
            else:
                category_summaries[cat] = f"Steady baseline communication with stable patterns."

        key_evidence: List[EvidenceItem] = []
        for o in observations[:5]:
            key_evidence.extend(o.evidence)

        return TemporalPeriodSummary(
            period_label=period_label,
            start_date=start_date,
            end_date=end_date,
            message_count=stats.total_messages,
            category_summaries=category_summaries,
            recurring_patterns=[
                "Prompt responses during working hours followed by relaxed evening exchanges.",
                "Mutual initiation of daily topics and shared plans.",
            ],
            notable_shifts=[
                "Communication cadence stabilized into a predictable rhythm.",
            ],
            key_evidence=key_evidence[:6],
        )

    def synthesize_report(
        self,
        project_id: str,
        project_name: str,
        deterministic_stats: DeterministicStats,
        temporal_summaries: List[TemporalPeriodSummary],
        chunk_results: List[ChunkAnalysisResult],
        categories: List[str],
    ) -> FinalReport:
        # Collect all observations
        all_obs = []
        for c in chunk_results:
            all_obs.extend(c.observations)

        cat_reports = {}
        for cat in categories:
            cat_obs = [o for o in all_obs if o.category == cat]
            cat_title = CATEGORIES.get(cat, {}).get("title", cat.replace("_", " ").title())

            # Collect evidence
            ev_list: List[EvidenceItem] = []
            for o in cat_obs:
                ev_list.extend(o.evidence)

            supporting_obs = [o.claim for o in cat_obs[:5]] or [
                f"Consistently demonstrates cooperative conversational alignment."
            ]

            temporal_desc = (
                "Early exchanges established conversational norms; sustained consistency was maintained across subsequent months."
            )
            both_desc = (
                "Both participants demonstrate active investment, sharing conversational load and responding to cues."
            )
            contra_desc = (
                "Periodic brief or delayed responses occurred during busy intervals, but these did not signify relational breakdown."
            )

            cat_reports[cat] = CategoryReport(
                category_id=cat,
                category_title=cat_title,
                concise_assessment=f"Active, stable dynamics with mutual engagement observed across the timeline.",
                supporting_observations=supporting_obs,
                dated_evidence=ev_list[:8],
                temporal_patterns=temporal_desc,
                both_participants_dynamics=both_desc,
                contradictory_evidence=contra_desc,
                confidence_level="High" if len(ev_list) >= 3 else "Medium",
                confidence_justification=f"Derived from {len(cat_obs)} distinct chunk observations and verified message citations.",
                limitations="Analysis is bounded by available exported text messages and does not capture voice/in-person interactions.",
            )

        trajectory_timeline = []
        for s in temporal_summaries:
            trajectory_timeline.append(
                {
                    "period": s.period_label,
                    "summary": f"{s.recurring_patterns[0] if s.recurring_patterns else 'Consistent communication'}",
                    "closeness_level": "High",
                }
            )

        p_names = list(deterministic_stats.participants.keys())
        p_str = " and ".join(p_names) if p_names else "the participants"

        overall = (
            f"The analyzed conversation between {p_str} reflects a healthy, collaborative, and emotionally attentive relationship. "
            f"Over {deterministic_stats.total_messages:,} messages, both participants demonstrated consistent responsiveness, "
            f"mutual reciprocity in initiating conversations, and the ability to resolve minor uncertainties smoothly. "
            f"Communication volume shows healthy engagement patterns without signs of destructive conflict or unilateral withdrawal."
        )

        return FinalReport(
            project_id=project_id,
            project_name=project_name,
            model_used="Deterministic Mock Engine",
            coverage_summary=f"Analyzed {deterministic_stats.total_messages:,} messages across {len(chunk_results)} message chunks.",
            is_complete_run=True,
            deterministic_stats=deterministic_stats.model_dump(),
            overall_assessment=overall,
            categories=cat_reports,
            trajectory_timeline=trajectory_timeline,
        )
