"""
Phase 2 – Opus validation.

Calls Claude Opus for maximum-rigor validation of the Sonnet analysis.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from engines.claude_client import ClaudeClient
from engines.analysis.models import OpusResult, AnalysisStatus

logger = logging.getLogger(__name__)

OPUS_SYSTEM_PROMPT = (
    "You are Claude Opus providing MAXIMUM RIGOR validation of a codebase analysis. "
    "Focus on deep insights, security implications, architecture quality, and "
    "strategic recommendations with unprecedented depth and accuracy."
)


def _extract_json_from_text(text: str) -> dict[str, Any]:
    """Extract a JSON object from text that may include markdown fences."""
    md_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if md_match:
        candidate = md_match.group(1)
    elif "{" in text:
        start = text.index("{")
        depth, end = 0, start
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth == 0:
                end = i
                break
        candidate = text[start : end + 1]
    else:
        candidate = text

    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        return {}


def build_opus_prompt(
    project_name: str,
    sonnet_raw: str,
    tech_stack: dict[str, Any],
    structure: dict[str, Any],
    routes: dict[str, Any],
    auth: dict[str, Any],
    database: dict[str, Any],
) -> str:
    trimmed_sonnet = sonnet_raw[:2000]
    return (
        "RESPOND ONLY WITH VALID JSON. NO OTHER TEXT OR EXPLANATIONS.\n\n"
        "Validate this codebase analysis with maximum rigor:\n\n"
        f"Project: {project_name}\n"
        f"Technology: {json.dumps(tech_stack, default=str)[:300]}\n\n"
        f"Sonnet Analysis: {trimmed_sonnet}\n\n"
        "Return ONLY this JSON structure (no other text):\n"
        "{\n"
        '  "security_analysis": {"vulnerabilities": [], "recommendations": []},\n'
        '  "performance_analysis": {"bottlenecks": [], "optimizations": []},\n'
        '  "architecture_quality": {"strengths": [], "concerns": [], "improvements": []},\n'
        '  "technical_debt": {"high_priority": [], "medium_priority": []},\n'
        '  "strategic_recommendations": {"immediate": [], "long_term": []},\n'
        '  "opus_confidence": 0.95,\n'
        '  "validation_summary": "Executive summary"\n'
        "}"
    )


def run_opus_validation(
    client: ClaudeClient,
    project_name: str,
    sonnet_raw: str,
    tech_stack: dict[str, Any] | None = None,
    structure: dict[str, Any] | None = None,
    routes: dict[str, Any] | None = None,
    auth: dict[str, Any] | None = None,
    database: dict[str, Any] | None = None,
) -> OpusResult:
    """Run Phase 2 Opus validation and return structured result."""
    prompt = build_opus_prompt(
        project_name,
        sonnet_raw,
        tech_stack or {},
        structure or {},
        routes or {},
        auth or {},
        database or {},
    )

    response = client.create_message(
        messages=[{"role": "user", "content": prompt}],
        system=OPUS_SYSTEM_PROMPT,
        model=client.advanced_model,
        temperature=0.1,
        max_tokens=4000,
    )

    if response.get("error"):
        logger.error("Opus validation failed: %s", response["error"])
        return OpusResult(status=AnalysisStatus.FAILED, raw_response="")

    raw = response.get("content", "")
    data = _extract_json_from_text(raw)

    return OpusResult(
        status=AnalysisStatus.COMPLETED,
        raw_response=raw,
        security_analysis=data.get("security_analysis", {}),
        performance_analysis=data.get("performance_analysis", {}),
        architecture_quality=data.get("architecture_quality", {}),
        technical_debt=data.get("technical_debt", {}),
        strategic_recommendations=data.get("strategic_recommendations", {}),
        opus_confidence=data.get("opus_confidence", 0.95),
        validation_summary=data.get("validation_summary", ""),
    )
