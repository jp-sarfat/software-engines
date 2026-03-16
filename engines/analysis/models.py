"""
Pydantic models for the Analysis engine API.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class TechStack(BaseModel):
    primary_language: Optional[str] = None
    framework: Optional[str] = None
    database: list[str] = []
    frontend: list[str] = []
    deployment: list[str] = []
    testing: list[str] = []
    build_tools: list[str] = []


class AnalysisRequest(BaseModel):
    project_name: str = Field(..., min_length=1)
    description: str = ""
    environment: str = "production"
    technology_stack: Optional[TechStack] = None
    project_structure: dict[str, Any] = {}
    routes: dict[str, Any] = {}
    authentication: dict[str, Any] = {}
    database_schema: dict[str, Any] = {}


class SonnetResult(BaseModel):
    status: AnalysisStatus = AnalysisStatus.COMPLETED
    raw_response: str = ""
    summary: str = ""
    structural_insights: dict[str, Any] = {}
    test_recommendations: list[str] = []
    common_patterns: list[str] = []
    potential_issues: list[str] = []
    confidence: float = 0.85


class OpusResult(BaseModel):
    status: AnalysisStatus = AnalysisStatus.COMPLETED
    raw_response: str = ""
    security_analysis: dict[str, Any] = {}
    performance_analysis: dict[str, Any] = {}
    architecture_quality: dict[str, Any] = {}
    technical_debt: dict[str, Any] = {}
    strategic_recommendations: dict[str, Any] = {}
    opus_confidence: float = 0.95
    validation_summary: str = ""


class AnalysisResponse(BaseModel):
    status: AnalysisStatus
    project_name: str
    ai_architecture: str = "Dual Claude (Sonnet + Opus)"
    sonnet_result: Optional[SonnetResult] = None
    opus_result: Optional[OpusResult] = None
    quality_score: float = 0.0
    analysis_confidence: float = 0.0
    generated_at: str = ""
    error_message: Optional[str] = None


class OpusValidationRequest(BaseModel):
    """Trigger Opus validation on an existing Sonnet analysis."""
    project_name: str
    sonnet_raw_response: str
    technology_stack: Optional[TechStack] = None
    project_structure: dict[str, Any] = {}
    routes: dict[str, Any] = {}
    authentication: dict[str, Any] = {}
    database_schema: dict[str, Any] = {}
