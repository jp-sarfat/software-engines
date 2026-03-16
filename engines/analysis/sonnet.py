"""
Phase 1 – Sonnet analysis.

Calls Claude Sonnet for comprehensive structural codebase analysis.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from engines.claude_client import ClaudeClient
from engines.analysis.models import SonnetResult, AnalysisStatus

logger = logging.getLogger(__name__)

SONNET_SYSTEM_PROMPT = (
    "You are Claude Sonnet, an expert software architect and codebase analyst.\n\n"
    "Your role in the DUAL CLAUDE ARCHITECTURE:\n"
    "- PHASE 1: Comprehensive structural analysis of codebases\n"
    "- Focus on technology stack, architecture patterns, routing, authentication, "
    "and database design\n"
    "- Provide thorough technical analysis with clear insights\n"
    "- Prepare foundation for Claude Opus validation phase\n\n"
    "Analyse codebases with precision and provide structured, actionable insights.\n"
    "Your analysis will be enhanced by Claude Opus in the next phase."
)


def build_sonnet_prompt(
    project_name: str,
    description: str,
    environment: str,
    tech_stack: dict[str, Any],
    structure: dict[str, Any],
    routes: dict[str, Any],
    auth: dict[str, Any],
    database: dict[str, Any],
) -> str:
    return (
        "CLAUDE SONNET - COMPREHENSIVE CODEBASE ANALYSIS\n\n"
        f"Project: {project_name}\n"
        f"Description: {description}\n"
        f"Environment: {environment}\n\n"
        "STRUCTURAL ANALYSIS DATA:\n\n"
        f"Technology Stack:\n{json.dumps(tech_stack, default=str)}\n\n"
        f"Project Structure:\n{json.dumps(structure, default=str)}\n\n"
        f"Routes & Endpoints:\n{json.dumps(routes, default=str)}\n\n"
        f"Authentication System:\n{json.dumps(auth, default=str)}\n\n"
        f"Database Schema:\n{json.dumps(database, default=str)}\n\n"
        "TASK: Provide comprehensive structural analysis including:\n"
        "1. Technology stack assessment and recommendations\n"
        "2. Architectural patterns identification\n"
        "3. Routing structure analysis\n"
        "4. Authentication flow evaluation\n"
        "5. Database design assessment\n"
        "6. Common patterns and potential improvements\n"
        "7. Test strategy recommendations\n\n"
        "Format your response as structured JSON with clear sections for each analysis area.\n"
        "This analysis will be validated and enhanced by Claude Opus in the next phase."
    )


def run_sonnet_analysis(
    client: ClaudeClient,
    project_name: str,
    description: str = "",
    environment: str = "production",
    tech_stack: dict[str, Any] | None = None,
    structure: dict[str, Any] | None = None,
    routes: dict[str, Any] | None = None,
    auth: dict[str, Any] | None = None,
    database: dict[str, Any] | None = None,
) -> SonnetResult:
    """Run Phase 1 Sonnet analysis and return structured result."""
    prompt = build_sonnet_prompt(
        project_name,
        description,
        environment,
        tech_stack or {},
        structure or {},
        routes or {},
        auth or {},
        database or {},
    )

    response = client.create_message(
        messages=[{"role": "user", "content": prompt}],
        system=SONNET_SYSTEM_PROMPT,
        model=client.default_model,
        temperature=0.3,
    )

    if response.get("error"):
        logger.error("Sonnet analysis failed: %s", response["error"])
        return SonnetResult(
            status=AnalysisStatus.FAILED,
            raw_response=response.get("content", ""),
        )

    raw = response.get("content", "")
    return SonnetResult(
        status=AnalysisStatus.COMPLETED,
        raw_response=raw,
        summary=raw[:500],
        confidence=0.85,
    )
