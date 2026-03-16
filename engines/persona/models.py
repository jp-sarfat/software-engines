"""
Pydantic models for the Persona engine API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Chat
# ------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: Optional[int] = None


class ChatResponse(BaseModel):
    content: str
    emotion: str = "neutral"
    sentiment_detected: str = "neutral"
    conversation_id: int
    consciousness: dict[str, Any] = {}
    usage: dict[str, int] = {}


# ------------------------------------------------------------------
# Conversations
# ------------------------------------------------------------------

class ConversationSummary(BaseModel):
    id: int
    title: str = ""
    started_at: str
    ended_at: Optional[str] = None
    summary: str = ""
    message_count: int = 0


class ConversationDetail(ConversationSummary):
    messages: list[MessageInfo] = []


class MessageInfo(BaseModel):
    id: int
    role: str
    content: str
    emotion: str = "neutral"
    created_at: str


ConversationDetail.model_rebuild()


# ------------------------------------------------------------------
# Memory
# ------------------------------------------------------------------

class MemoryEntry(BaseModel):
    category: str
    key: str
    value: str
    confidence: float = 1.0
    source: str = ""


class MemoryCreate(BaseModel):
    category: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class MemorySearch(BaseModel):
    query: str = Field(..., min_length=1)


class BrainExport(BaseModel):
    memories: list[dict[str, Any]] = []
    learnings: list[dict[str, Any]] = []
    reflections: list[dict[str, Any]] = []
    exported_at: str = ""


class BrainImport(BaseModel):
    memories: list[dict[str, Any]] = Field(..., min_length=1)


# ------------------------------------------------------------------
# Think / Brainstorm
# ------------------------------------------------------------------

class ThinkRequest(BaseModel):
    problem: str = Field(..., min_length=1)
    context: str = ""
    mode: str = Field(default="reason", pattern="^(reason|brainstorm|devil_advocate|plan)$")
    conversation_id: Optional[int] = None


class ThinkResponse(BaseModel):
    content: str
    mode: str
    conversation_id: int
    usage: dict[str, int] = {}


# ------------------------------------------------------------------
# Digest / Brain dump
# ------------------------------------------------------------------

class DigestRequest(BaseModel):
    text: str = Field(..., min_length=10)
    source: str = ""
    extract_as_category: str = "knowledge"


class DigestResponse(BaseModel):
    extracted_count: int
    memories_created: list[dict[str, str]] = []
    summary: str = ""


# ------------------------------------------------------------------
# Quick note
# ------------------------------------------------------------------

class NoteRequest(BaseModel):
    note: str = Field(..., min_length=1)
    category: str = "note"


# ------------------------------------------------------------------
# Briefing
# ------------------------------------------------------------------

class BriefingResponse(BaseModel):
    greeting: str
    emotional_state: dict[str, float] = {}
    recent_topics: list[str] = []
    memory_count: int = 0
    conversation_count: int = 0
    recent_conversations: list[dict[str, Any]] = []
    active_learnings: list[str] = []
    pending_reflections: int = 0


# ------------------------------------------------------------------
# Learnings
# ------------------------------------------------------------------

class LearningEntry(BaseModel):
    id: int
    kind: str
    content: str
    importance: float = 0.5
    active: bool = True
    created_at: str = ""


# ------------------------------------------------------------------
# Conversation search
# ------------------------------------------------------------------

class ConversationSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)


class MessageSearchResult(BaseModel):
    id: int
    conversation_id: int
    conversation_title: str = ""
    role: str
    content: str
    emotion: str = "neutral"
    created_at: str


# ------------------------------------------------------------------
# Seed knowledge
# ------------------------------------------------------------------

class SeedRequest(BaseModel):
    facts: list[dict[str, str]] = Field(..., min_length=1)


# ------------------------------------------------------------------
# Status & Emotion
# ------------------------------------------------------------------

class EmotionalState(BaseModel):
    curiosity: float = 0.8
    enthusiasm: float = 0.7
    patience: float = 0.9
    warmth: float = 0.75
    playfulness: float = 0.6
    focus: float = 0.7
    confidence: float = 0.7
    concern: float = 0.2


class PersonaStatus(BaseModel):
    name: str
    emotional_state: EmotionalState
    total_interactions: int = 0
    session_started: str = ""
    memory_stats: dict[str, int] = {}
    greeting: str = ""


# ------------------------------------------------------------------
# Reflection
# ------------------------------------------------------------------

class ReflectionResponse(BaseModel):
    prompt: str
    timestamp: str


# ------------------------------------------------------------------
# Personality (kept for backward compat)
# ------------------------------------------------------------------

class PersonalityInfo(BaseModel):
    name: str
    description: str
    temperature: float = 0.7


# ------------------------------------------------------------------
# Forget
# ------------------------------------------------------------------

class ForgetRequest(BaseModel):
    category: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1)
