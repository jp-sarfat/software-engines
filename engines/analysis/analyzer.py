"""
Orchestrates the full dual-Claude analysis pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from engines.claude_client import ClaudeClient, get_claude_client
from engines.analysis.models import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisStatus,
)
from engines.analysis.sonnet import run_sonnet_analysis
from engines.analysis.opus import run_opus_validation

logger = logging.getLogger(__name__)


def run_full_analysis(
    request: AnalysisRequest,
    client: ClaudeClient | None = None,
    skip_opus: bool = False,
) -> AnalysisResponse:
    """
    Run the full dual-Claude analysis pipeline.

    Phase 1 – Sonnet: comprehensive structural analysis.
    Phase 2 – Opus:   maximum-rigor validation (can be deferred).
    """
    client = client or get_claude_client()
    ts = request.technology_stack
    tech_dict: dict[str, Any] = ts.model_dump() if ts else {}

    sonnet = run_sonnet_analysis(
        client=client,
        project_name=request.project_name,
        description=request.description,
        environment=request.environment,
        tech_stack=tech_dict,
        structure=request.project_structure,
        routes=request.routes,
        auth=request.authentication,
        database=request.database_schema,
        max_tokens=request.max_tokens,
    )

    if sonnet.status == AnalysisStatus.FAILED:
        return AnalysisResponse(
            status=AnalysisStatus.PARTIAL_SUCCESS,
            project_name=request.project_name,
            sonnet_result=sonnet,
            error_message="Sonnet analysis failed",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    opus = None
    if not skip_opus:
        opus = run_opus_validation(
            client=client,
            project_name=request.project_name,
            sonnet_raw=sonnet.raw_response,
            tech_stack=tech_dict,
            structure=request.project_structure,
            routes=request.routes,
            auth=request.authentication,
            database=request.database_schema,
        )

    overall_status = AnalysisStatus.COMPLETED
    confidence = sonnet.confidence
    quality = 0.85
    if opus and opus.status == AnalysisStatus.COMPLETED:
        confidence = max(confidence, opus.opus_confidence)
        quality = opus.opus_confidence

    return AnalysisResponse(
        status=overall_status,
        project_name=request.project_name,
        sonnet_result=sonnet,
        opus_result=opus,
        quality_score=quality,
        analysis_confidence=confidence,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
