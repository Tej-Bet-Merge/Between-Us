"""Prompts for LLM chunk interpretation, temporal aggregation, and report synthesis."""
from __future__ import annotations

import json
from typing import List
from relationship_analyst.config import CATEGORIES


CHUNK_SYSTEM_PROMPT = """You are an objective, evidence-based relationship communication analyst.
Your task is to analyze conversational text messages between participants and identify concrete dynamics.

CRITICAL RULES:
1. Ground every single claim in observable message evidence.
2. Cite the exact msg_id and quote verbatim text from the messages provided. Never fabricate messages or message IDs.
3. Distinguish clearly between direct statements and inferred tone/subtext.
4. If an exchange is ambiguous, explicitly state the ambiguity or alternative interpretations.
5. Do NOT make clinical or psychiatric diagnoses (e.g. do not diagnose narcissism, depression, attachment disorders).
6. Do NOT claim telepathic knowledge of unspoken internal intentions; stick to observable conversational actions and words.
7. Return ONLY valid JSON matching the specified schema.
"""


def build_chunk_prompt(
    messages_text: str,
    categories: List[str],
    participants: List[str],
) -> str:
    category_descriptions = "\n".join(
        f"- {cat_id}: {CATEGORIES.get(cat_id, {}).get('description', '')}"
        for cat_id in categories
    )
    participants_str = ", ".join(participants) if participants else "participants"

    return f"""Analyze the following chronological sequence of messages between {participants_str}.

FOCUS CATEGORIES:
{category_descriptions}

MESSAGES:
{messages_text}

Extract 2 to 6 key relationship observations observed in this chunk.
Return a JSON object conforming strictly to this structure:
{{
  "observations": [
    {{
      "category": "one of the requested category IDs",
      "claim": "Specific observation about how the participants communicate or interact",
      "sentiment": "positive | neutral | negative | mixed | nuanced",
      "participant_focus": "Name of participant or 'both'",
      "evidence_type": "direct_quote | behavioral_pattern | inferred_subtext",
      "ambiguity_note": "Alternative explanation or noted uncertainty, or null",
      "evidence": [
        {{
          "message_id": 123,
          "sender": "SenderName",
          "quote": "verbatim text snippet from message"
        }}
      ]
    }}
  ]
}}
"""


TEMPORAL_SYSTEM_PROMPT = """You are an objective relationship analyst synthesizing observations across a time period.
Focus on identifying persistent patterns, behavioral shifts, turning points, and mutual contributions.
Never fabricate message quotes or claims. Output valid JSON only."""


def build_temporal_prompt(
    period_label: str,
    observations_json: str,
    categories: List[str],
    stats_summary: str,
) -> str:
    return f"""Period: {period_label}

Context & Statistics:
{stats_summary}

Observations gathered during this period:
{observations_json}

Synthesize the key developments and dynamics in this period.
Return a JSON object conforming strictly to this structure:
{{
  "period_label": "{period_label}",
  "recurring_patterns": ["List of repeated interaction styles or themes"],
  "notable_shifts": ["Any notable changes, improvements, escalations, or distance"],
  "category_summaries": {{
    "category_id": "Summary of dynamics for this category in this period"
  }},
  "key_evidence": [
    {{
      "message_id": 123,
      "sender": "Name",
      "quote": "verbatim quote"
    }}
  ]
}}
"""


SYNTHESIS_SYSTEM_PROMPT = """You are a senior relationship analyst producing an in-depth, evidence-based review.
Synthesize the quantitative metrics, temporal summaries, and specific chunk observations into a comprehensive report.

CRITICAL INSTRUCTIONS FOR CONTEXT-SPECIFIC ANALYSIS:
- NEVER output generic boilerplate or filler essays (e.g. avoid vague clichés like "reflects a healthy, collaborative relationship").
- Ground your assessment deeply in the actual context, themes, topics, and specific situations that the participants discussed.
- Cite specific conversational events (e.g., specific plans made, conflicts resolved, work/personal stressors shared, inside jokes, and mutual boundaries).
- Attribute behaviors specifically to each participant by name, highlighting their distinct communicative styles.
- Acknowledge counter-evidence, nuances, and alternative interpretations.
- Assign an honest Confidence Level (High, Medium, Low) based on evidence density and clarity.
- Do NOT diagnose mental health disorders or claim telepathic knowledge of unexpressed thoughts.
- Output strictly valid JSON conforming to the schema.
"""


def build_overall_synthesis_prompt(
    project_name: str,
    deterministic_stats_text: str,
    temporal_summaries_text: str,
    observations_text: str,
) -> str:
    schema = {
        "overall_assessment": "Comprehensive 2-4 paragraph deep synthesis discussing the specific dynamic, real conversation topics, mutual strengths, friction points, and relational trajectory.",
        "coverage_summary": "Details on message volume, timeframe covered, and data completeness.",
        "trajectory_timeline": [
            {
                "period": "Period Label",
                "summary": "Summary of what developed during this stage",
                "closeness_level": "High | Moderate | Low | Strained"
            }
        ]
    }
    return f"""Project: {project_name}

DETERMINISTIC CONVERSATIONAL METRICS:
{deterministic_stats_text}

TEMPORAL SUMMARIES & EVOLUTION:
{temporal_summaries_text}

SAMPLE OBSERVATIONS FROM CHAT:
{observations_text}

Provide a comprehensive overall assessment of the relationship and the chronological trajectory timeline.
Ground your synthesis in the actual topics, specific events, and communication patterns of the participants.
Return ONLY valid JSON matching this structure:
{json.dumps(schema, indent=2)}
"""


def build_single_category_prompt(
    category_key: str,
    category_title: str,
    category_description: str,
    project_name: str,
    stats_text: str,
    temporal_text: str,
    observations_text: str,
) -> str:
    schema = {
        "category_id": category_key,
        "category_title": category_title,
        "concise_assessment": "Specific 1-2 sentence core takeaway grounded in this chat's dynamic",
        "supporting_observations": ["Context-specific observation 1 citing real events", "Context-specific observation 2"],
        "temporal_patterns": "Detailed evolution across early, middle, and recent periods for this category",
        "both_participants_dynamics": "Specific contributions and interactive patterns of both participants",
        "contradictory_evidence": "Specific counter-examples, exceptions, or alternative explanations from the chat",
        "confidence_level": "High | Medium | Low",
        "confidence_justification": "Why this confidence rating is warranted based on evidence density",
        "limitations": "Missing data or specific ambiguities for this category",
        "dated_evidence": [
            {
                "message_id": 123,
                "sender": "Name",
                "quote": "Verbatim direct quote from conversation"
            }
        ]
    }
    return f"""Project: {project_name}
CATEGORY: {category_title} ({category_description})

CONTEXT & METRICS:
{stats_text}

TEMPORAL EVOLUTION:
{temporal_text}

EVIDENCE & OBSERVATIONS FOR THIS CATEGORY:
{observations_text}

Analyze and review the category '{category_title}' specifically.
Cite real quotes and message IDs from the evidence above. Never use generic filler.
Return ONLY valid JSON matching this structure:
{json.dumps(schema, indent=2)}
"""


def build_synthesis_prompt(
    project_name: str,
    deterministic_stats_text: str,
    temporal_summaries_text: str,
    observations_text: str,
    categories: List[str],
) -> str:
    categories_schema = {}
    for cat in categories:
        cat_info = CATEGORIES.get(cat, {})
        categories_schema[cat] = {
            "category_id": cat,
            "category_title": cat_info.get("title", cat),
            "concise_assessment": "Specific 1-2 sentence takeaway grounded in this chat's unique dynamic",
            "supporting_observations": ["Context-specific observation 1 citing real events", "Context-specific observation 2"],
            "temporal_patterns": "Detailed evolution across early, middle, and recent periods of this relationship",
            "both_participants_dynamics": "Specific contributions and interactive patterns of both participants",
            "contradictory_evidence": "Specific counter-examples, exceptions, or alternative explanations from the chat",
            "confidence_level": "High | Medium | Low",
            "confidence_justification": "Why this confidence rating is warranted based on evidence density",
            "limitations": "Missing data or specific ambiguities for this category",
            "dated_evidence": [
                {
                    "message_id": 123,
                    "sender": "Name",
                    "quote": "Verbatim direct quote from conversation"
                }
            ]
        }

    schema_example = json.dumps(
        {
            "overall_assessment": "Comprehensive 3-5 paragraph deep synthesis discussing the specific dynamic, real conversation topics, mutual strengths, friction points, and relational trajectory.",
            "coverage_summary": "Details on message volume, timeframe covered, and data completeness.",
            "categories": categories_schema,
            "trajectory_timeline": [
                {
                    "period": "Period Label",
                    "summary": "Summary of what developed during this stage",
                    "closeness_level": "High | Moderate | Low | Strained"
                }
            ]
        },
        indent=2,
    )

    return f"""Project: {project_name}

DETERMINISTIC STATISTICS:
{deterministic_stats_text}

TEMPORAL SUMMARIES & TRAJECTORY:
{temporal_summaries_text}

EVIDENCE & OBSERVATIONS EXTRACTED FROM MESSAGE CHUNKS:
{observations_text}

Synthesize a comprehensive, non-generic relationship report covering the requested categories.
Base your conclusions directly on the specific conversation evidence, quotes, and interaction patterns provided above.
Return a JSON object conforming strictly to this structure:
{schema_example}
"""
