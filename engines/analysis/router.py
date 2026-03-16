"""
FastAPI router for the Analysis engine.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from engines.analysis.models import (
    AnalysisRequest,
    AnalysisResponse,
    OpusValidationRequest,
    OpusResult,
)
from engines.analysis.analyzer import run_full_analysis
from engines.analysis.sonnet import run_sonnet_analysis
from engines.analysis.opus import run_opus_validation
from engines.analysis.models import SonnetResult
from engines.claude_client import get_claude_client

router = APIRouter(prefix="/analysis", tags=["Codebase Analysis"])


@router.post("/full", response_model=AnalysisResponse)
async def full_analysis(req: AnalysisRequest):
    """Run the full Sonnet + Opus dual-Claude codebase analysis."""
    return run_full_analysis(req)


@router.post("/sonnet", response_model=SonnetResult)
async def sonnet_only(req: AnalysisRequest):
    """Run only Phase 1 Sonnet analysis."""
    client = get_claude_client()
    ts = req.technology_stack
    tech_dict = ts.model_dump() if ts else {}
    return run_sonnet_analysis(
        client=client,
        project_name=req.project_name,
        description=req.description,
        environment=req.environment,
        tech_stack=tech_dict,
        structure=req.project_structure,
        routes=req.routes,
        auth=req.authentication,
        database=req.database_schema,
    )


@router.post("/opus", response_model=OpusResult)
async def opus_validation(req: OpusValidationRequest):
    """Run Phase 2 Opus validation on existing Sonnet results."""
    client = get_claude_client()
    ts = req.technology_stack
    tech_dict = ts.model_dump() if ts else {}
    return run_opus_validation(
        client=client,
        project_name=req.project_name,
        sonnet_raw=req.sonnet_raw_response,
        tech_stack=tech_dict,
        structure=req.project_structure,
        routes=req.routes,
        auth=req.authentication,
        database=req.database_schema,
    )
