"""
FastAPI router for the Analysis engine.

Endpoints:
    POST /analysis/full            – Full Sonnet + Opus dual-Claude analysis (JSON)
    POST /analysis/sonnet          – Phase 1 Sonnet only (JSON)
    POST /analysis/opus            – Phase 2 Opus validation (JSON)
    POST /analysis/sonnet/stream   – Phase 1 Sonnet streamed (text/event-stream)
    POST /analysis/opus/stream     – Phase 2 Opus streamed (text/event-stream)
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from engines.analysis.models import (
    AnalysisRequest,
    AnalysisResponse,
    OpusValidationRequest,
    OpusResult,
    SonnetResult,
)
from engines.analysis.analyzer import run_full_analysis
from engines.analysis.sonnet import run_sonnet_analysis, build_sonnet_prompt, SONNET_SYSTEM_PROMPT
from engines.analysis.opus import run_opus_validation, build_opus_prompt, OPUS_SYSTEM_PROMPT
from engines.claude_client import get_claude_client

router = APIRouter(prefix="/analysis", tags=["Codebase Analysis"])


@router.post("/full", response_model=AnalysisResponse)
async def full_analysis(req: AnalysisRequest):
    """Run the full Sonnet + Opus dual-Claude codebase analysis."""
    return run_full_analysis(req)


@router.post("/sonnet", response_model=SonnetResult)
async def sonnet_only(req: AnalysisRequest):
    """Run only Phase 1 Sonnet analysis (blocks until complete)."""
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
        max_tokens=req.max_tokens,
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
        max_tokens=req.max_tokens,
    )


def _sse_wrap(generator):
    """Wrap a text-chunk generator in SSE format for StreamingResponse."""
    for chunk in generator:
        yield f"data: {chunk}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/sonnet/stream")
async def sonnet_stream(req: AnalysisRequest):
    """Stream Phase 1 Sonnet analysis token-by-token (SSE)."""
    client = get_claude_client()
    ts = req.technology_stack
    tech_dict = ts.model_dump() if ts else {}
    prompt = build_sonnet_prompt(
        req.project_name,
        req.description,
        req.environment,
        tech_dict,
        req.project_structure,
        req.routes,
        req.authentication,
        req.database_schema,
    )
    chunks = client.stream_message(
        messages=[{"role": "user", "content": prompt}],
        system=SONNET_SYSTEM_PROMPT,
        model=client.default_model,
        max_tokens=req.max_tokens,
        temperature=0.3,
    )
    return StreamingResponse(_sse_wrap(chunks), media_type="text/event-stream")


@router.post("/opus/stream")
async def opus_stream(req: OpusValidationRequest):
    """Stream Phase 2 Opus validation token-by-token (SSE)."""
    client = get_claude_client()
    ts = req.technology_stack
    tech_dict = ts.model_dump() if ts else {}
    prompt = build_opus_prompt(
        req.project_name,
        req.sonnet_raw_response,
        tech_dict,
        req.project_structure,
        req.routes,
        req.authentication,
        req.database_schema,
    )
    chunks = client.stream_message(
        messages=[{"role": "user", "content": prompt}],
        system=OPUS_SYSTEM_PROMPT,
        model=client.advanced_model,
        max_tokens=req.max_tokens,
        temperature=0.1,
    )
    return StreamingResponse(_sse_wrap(chunks), media_type="text/event-stream")
