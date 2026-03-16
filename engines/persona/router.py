"""
FastAPI router for Qyvella – the reasoning companion.

Endpoints:
    --- Status & Greeting ---
    GET  /persona/status              – who she is, how she feels, what she remembers
    GET  /persona/greeting            – contextual startup greeting
    GET  /persona/briefing            – full daily briefing with context

    --- Chat & Thinking ---
    POST /persona/chat                – the main conversation endpoint
    WS   /persona/ws                  – WebSocket real-time chat
    POST /persona/think               – dedicated reasoning / brainstorm mode
    POST /persona/digest              – brain dump: process text into memories

    --- Conversations ---
    POST /persona/conversation/start       – begin a new conversation
    POST /persona/conversation/end         – end current conversation
    GET  /persona/conversations            – list past conversations
    GET  /persona/conversation/{id}        – get a conversation with messages
    POST /persona/conversations/search     – search across conversations
    POST /persona/conversation/{id}/summarize – Claude-powered conversation summary

    --- Memory ---
    POST /persona/remember            – teach her something
    POST /persona/note                – quick note to remember
    GET  /persona/memories            – what she remembers
    POST /persona/memories/search     – search her memory
    POST /persona/forget              – forget a specific memory
    POST /persona/seed                – seed bulk knowledge
    GET  /persona/brain/export        – export entire brain as JSON
    POST /persona/brain/import        – import memories from JSON

    --- Learnings ---
    GET  /persona/learnings           – view all learnings
    POST /persona/learnings/{id}/deactivate – turn off a learning
    POST /persona/learnings/{id}/reactivate – turn on a learning

    --- Reflection & Emotion ---
    POST /persona/reflect             – trigger self-reflection
    POST /persona/emotion/{sentiment} – nudge her emotional state
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from engines.persona.consciousness import ConsciousnessCore
from engines.persona.conversation import ConversationManager
from engines.persona.learning import extract_topics
from engines.persona.memory import MemoryStore
from engines.persona.models import (
    BrainExport,
    BrainImport,
    BriefingResponse,
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationSearchRequest,
    ConversationSummary,
    DigestRequest,
    DigestResponse,
    EmotionalState,
    ForgetRequest,
    LearningEntry,
    MemoryCreate,
    MemoryEntry,
    MemorySearch,
    MessageInfo,
    MessageSearchResult,
    NoteRequest,
    PersonaStatus,
    ReflectionResponse,
    SeedRequest,
    ThinkRequest,
    ThinkResponse,
)
from engines.claude_client import get_claude_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/persona", tags=["Qyvella"])

_consciousness = ConsciousnessCore()
_memory = MemoryStore()
_conversation_mgr = ConversationManager(_consciousness, _memory)


def get_conversation_manager() -> ConversationManager:
    return _conversation_mgr


# ======================================================================
# Thinking modes – system prompt overlays
# ======================================================================

_THINK_MODES: dict[str, str] = {
    "reason": (
        "MODE: DEEP REASONING\n"
        "The user has given you a problem to think through carefully.\n"
        "- Break it into components\n"
        "- Consider edge cases and failure modes\n"
        "- Show your full chain of thought\n"
        "- Arrive at a clear recommendation with tradeoffs\n"
        "- If you see a flaw in the premise, say so before solving"
    ),
    "brainstorm": (
        "MODE: BRAINSTORM\n"
        "Generate as many ideas as possible.  Go wide, not deep.\n"
        "- No idea is too wild at this stage\n"
        "- Build on each idea briefly\n"
        "- Group them by theme\n"
        "- Flag your top 3 picks and say why\n"
        "- Challenge the user's framing if it's too narrow"
    ),
    "devil_advocate": (
        "MODE: DEVIL'S ADVOCATE\n"
        "Your job is to find every hole, flaw, and risk.\n"
        "- Attack the idea from every angle\n"
        "- Be ruthlessly honest\n"
        "- Identify hidden assumptions\n"
        "- Suggest what could go catastrophically wrong\n"
        "- End with: 'If you can address these, you've got something solid.'"
    ),
    "plan": (
        "MODE: PLANNING\n"
        "Help turn this into an actionable plan.\n"
        "- Break into phases with clear milestones\n"
        "- Estimate effort/time for each phase\n"
        "- Identify dependencies and blockers\n"
        "- Call out risks and mitigation strategies\n"
        "- Be realistic, not optimistic"
    ),
}


# ======================================================================
# Status, Greeting & Briefing
# ======================================================================


@router.get("/status", response_model=PersonaStatus)
async def persona_status():
    stats = _memory.get_stats()
    greeting = _conversation_mgr.generate_greeting()
    return PersonaStatus(
        name=_consciousness.identity.name,
        emotional_state=EmotionalState(**_consciousness.emotion.as_dict()),
        total_interactions=_consciousness.total_interactions,
        session_started=_consciousness.session_started,
        memory_stats=stats,
        greeting=greeting,
    )


@router.get("/greeting")
async def greeting():
    return {"greeting": _conversation_mgr.generate_greeting()}


@router.get("/briefing", response_model=BriefingResponse)
async def briefing():
    stats = _memory.get_stats()
    recent_convos = _memory.list_conversations(limit=5)
    learnings = _memory.get_active_learnings(limit=10)

    recent_msgs = _memory.get_recent_messages_across_conversations(limit=30)
    topics: list[str] = []
    for msg in recent_msgs:
        if msg["role"] == "user":
            topics.extend(extract_topics(msg["content"]))
    unique_topics = list(dict.fromkeys(topics))[:10]

    return BriefingResponse(
        greeting=_conversation_mgr.generate_greeting(),
        emotional_state=_consciousness.emotion.as_dict(),
        recent_topics=unique_topics,
        memory_count=stats.get("memories", 0),
        conversation_count=stats.get("conversations", 0),
        recent_conversations=[
            {"id": c["id"], "title": c["title"], "summary": c["summary"],
             "started_at": c["started_at"], "message_count": c["message_count"]}
            for c in recent_convos
        ],
        active_learnings=[l["content"] for l in learnings],
        pending_reflections=0,
    )


# ======================================================================
# Chat
# ======================================================================


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if req.conversation_id is not None:
        conv = _memory.get_conversation(req.conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        _conversation_mgr._active_conversation_id = req.conversation_id

    context = _conversation_mgr.process_user_message(req.message)

    client = get_claude_client()
    response = client.create_message(
        messages=context["messages"],
        system=context["system_prompt"],
        temperature=0.7,
    )

    content = response.get("content", "")
    usage = response.get("usage", {})
    total_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

    _conversation_mgr.process_assistant_response(content, tokens=total_tokens)

    return ChatResponse(
        content=content,
        emotion=_consciousness.detect_sentiment(content),
        sentiment_detected=context["sentiment"],
        conversation_id=context["conversation_id"],
        consciousness={
            "emotional_state": _consciousness.emotion.as_dict(),
            "total_interactions": _consciousness.total_interactions,
        },
        usage=usage,
    )


# ======================================================================
# WebSocket real-time chat
# ======================================================================


@router.websocket("/ws")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    conv_id = _conversation_mgr.start_conversation(title="WebSocket session")
    await ws.send_json({
        "type": "connected",
        "conversation_id": conv_id,
        "greeting": _conversation_mgr.generate_greeting(),
    })

    try:
        while True:
            data = await ws.receive_json()
            message = data.get("message", "")
            if not message:
                await ws.send_json({"type": "error", "detail": "Empty message"})
                continue

            context = _conversation_mgr.process_user_message(message)

            client = get_claude_client()
            response = client.create_message(
                messages=context["messages"],
                system=context["system_prompt"],
                temperature=0.7,
            )

            content = response.get("content", "")
            usage = response.get("usage", {})
            total_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            _conversation_mgr.process_assistant_response(content, tokens=total_tokens)

            await ws.send_json({
                "type": "message",
                "content": content,
                "emotion": _consciousness.detect_sentiment(content),
                "sentiment_detected": context["sentiment"],
                "conversation_id": conv_id,
                "usage": usage,
            })
    except WebSocketDisconnect:
        _conversation_mgr.end_conversation()
        logger.info("WebSocket disconnected, conversation %d ended", conv_id)


# ======================================================================
# Think / Brainstorm
# ======================================================================


@router.post("/think", response_model=ThinkResponse)
async def think(req: ThinkRequest):
    if req.conversation_id is not None:
        conv = _memory.get_conversation(req.conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        _conversation_mgr._active_conversation_id = req.conversation_id

    user_content = req.problem
    if req.context:
        user_content = f"{req.problem}\n\nContext:\n{req.context}"

    context = _conversation_mgr.process_user_message(user_content)
    mode_overlay = _THINK_MODES.get(req.mode, _THINK_MODES["reason"])
    system_prompt = f"{context['system_prompt']}\n\n{mode_overlay}"

    client = get_claude_client()
    response = client.create_message(
        messages=context["messages"],
        system=system_prompt,
        temperature=0.8 if req.mode == "brainstorm" else 0.6,
    )

    content = response.get("content", "")
    usage = response.get("usage", {})
    total_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
    _conversation_mgr.process_assistant_response(content, tokens=total_tokens)

    return ThinkResponse(
        content=content,
        mode=req.mode,
        conversation_id=context["conversation_id"],
        usage=usage,
    )


# ======================================================================
# Digest / Brain dump
# ======================================================================


@router.post("/digest", response_model=DigestResponse)
async def digest(req: DigestRequest):
    client = get_claude_client()
    base_prompt = _conversation_mgr.build_system_prompt()

    system_prompt = (
        f"{base_prompt}\n\n"
        "MODE: KNOWLEDGE EXTRACTION\n"
        "The user is giving you a chunk of text to digest.\n"
        "Extract the key facts, decisions, preferences, and actionable items.\n"
        "Return ONLY valid JSON -- an array of objects with keys: "
        '"key" (short label), "value" (the fact/detail).\n'
        "Be thorough but concise. 3-15 items typically."
    )

    response = client.create_message(
        messages=[{"role": "user", "content": req.text}],
        system=system_prompt,
        temperature=0.3,
    )

    content = response.get("content", "")
    extracted: list[dict[str, str]] = []
    try:
        raw = content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        extracted = json.loads(raw)
        if not isinstance(extracted, list):
            extracted = []
    except (json.JSONDecodeError, IndexError):
        extracted = [{"key": "raw_digest", "value": content[:500]}]

    memories_created: list[dict[str, str]] = []
    for item in extracted:
        k = item.get("key", "").strip()
        v = item.get("value", "").strip()
        if k and v:
            _memory.remember(
                category=req.extract_as_category,
                key=k,
                value=v,
                source=req.source or "digest",
            )
            memories_created.append({"key": k, "value": v})

    return DigestResponse(
        extracted_count=len(memories_created),
        memories_created=memories_created,
        summary=f"Extracted {len(memories_created)} facts from text.",
    )


# ======================================================================
# Conversation management
# ======================================================================


@router.post("/conversation/start")
async def start_conversation(title: str = ""):
    conv_id = _conversation_mgr.start_conversation(title=title)
    return {"conversation_id": conv_id, "status": "started"}


@router.post("/conversation/end")
async def end_conversation(summary: str = ""):
    _conversation_mgr.end_conversation(summary=summary)
    return {"status": "ended"}


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(limit: int = 20):
    convos = _memory.list_conversations(limit=limit)
    return [ConversationSummary(**c) for c in convos]


@router.get("/conversation/{conv_id}", response_model=ConversationDetail)
async def get_conversation(conv_id: int):
    conv = _memory.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = _memory.get_messages(conv_id, limit=200)
    return ConversationDetail(
        **conv,
        messages=[MessageInfo(**m) for m in msgs],
    )


@router.post("/conversations/search")
async def search_conversations(req: ConversationSearchRequest):
    convos = _memory.search_conversations(req.query)
    messages = _memory.search_messages(req.query, limit=20)
    return {
        "conversations": [ConversationSummary(**c) for c in convos],
        "messages": [
            MessageSearchResult(
                id=m["id"],
                conversation_id=m["conversation_id"],
                conversation_title=m.get("conversation_title", ""),
                role=m["role"],
                content=m["content"],
                emotion=m.get("emotion", "neutral"),
                created_at=m["created_at"],
            )
            for m in messages
        ],
    }


@router.post("/conversation/{conv_id}/summarize")
async def summarize_conversation(conv_id: int):
    conv = _memory.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = _memory.get_messages(conv_id, limit=100)
    if not msgs:
        return {"summary": "Empty conversation."}

    transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in msgs)

    client = get_claude_client()
    response = client.create_message(
        messages=[{"role": "user", "content": transcript}],
        system=(
            "Summarize this conversation in 2-4 sentences. "
            "Capture the key topics, decisions made, and any action items. "
            "Be concise and specific."
        ),
        temperature=0.3,
    )

    summary = response.get("content", "No summary generated.")
    _memory.end_conversation(conv_id, summary=summary)
    return {"conversation_id": conv_id, "summary": summary}


# ======================================================================
# Memory
# ======================================================================


@router.post("/remember")
async def remember(mem: MemoryCreate):
    _memory.remember(
        category=mem.category,
        key=mem.key,
        value=mem.value,
        confidence=mem.confidence,
        source="user_direct",
    )
    return {"status": "remembered", "category": mem.category, "key": mem.key}


@router.post("/note")
async def quick_note(req: NoteRequest):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    _memory.remember(
        category=req.category,
        key=f"note_{timestamp}",
        value=req.note,
        source="quick_note",
    )
    return {"status": "noted", "key": f"note_{timestamp}"}


@router.get("/memories", response_model=list[MemoryEntry])
async def list_memories(category: Optional[str] = None, limit: int = 30):
    mems = _memory.recall(category=category, limit=limit)
    return [MemoryEntry(**m) for m in mems]


@router.post("/memories/search", response_model=list[MemoryEntry])
async def search_memories(search: MemorySearch):
    mems = _memory.search_memories(search.query)
    return [MemoryEntry(**m) for m in mems]


@router.post("/forget")
async def forget(req: ForgetRequest):
    deleted = _memory.forget(req.category, req.key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "forgotten", "category": req.category, "key": req.key}


@router.post("/seed")
async def seed_knowledge(req: SeedRequest):
    count = 0
    for fact in req.facts:
        category = fact.get("category", "user")
        key = fact.get("key", "")
        value = fact.get("value", "")
        if key and value:
            _memory.remember(
                category=category,
                key=key,
                value=value,
                source="seed",
            )
            count += 1
    return {"status": "seeded", "facts_stored": count}


@router.get("/brain/export", response_model=BrainExport)
async def export_brain():
    data = _memory.export_all()
    return BrainExport(**data)


@router.post("/brain/import")
async def import_brain(req: BrainImport):
    count = _memory.import_memories(req.memories)
    return {"status": "imported", "memories_imported": count}


# ======================================================================
# Learnings
# ======================================================================


@router.get("/learnings", response_model=list[LearningEntry])
async def list_learnings(active_only: bool = False):
    if active_only:
        rows = _memory.get_active_learnings(limit=50)
    else:
        rows = _memory.get_all_learnings(limit=50)
    return [
        LearningEntry(
            id=r["id"],
            kind=r["kind"],
            content=r["content"],
            importance=r["importance"],
            active=bool(r["active"]),
            created_at=r.get("created_at", ""),
        )
        for r in rows
    ]


@router.post("/learnings/{learning_id}/deactivate")
async def deactivate_learning(learning_id: int):
    ok = _memory.deactivate_learning(learning_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Learning not found")
    return {"status": "deactivated", "id": learning_id}


@router.post("/learnings/{learning_id}/reactivate")
async def reactivate_learning(learning_id: int):
    ok = _memory.reactivate_learning(learning_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Learning not found")
    return {"status": "reactivated", "id": learning_id}


# ======================================================================
# Reflection & Emotion
# ======================================================================


@router.post("/reflect", response_model=ReflectionResponse)
async def reflect():
    return ReflectionResponse(
        prompt=_consciousness.generate_reflection_prompt(),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/emotion/{sentiment}")
async def update_emotion(sentiment: str):
    _consciousness.update_emotion(sentiment)
    return {"emotional_state": _consciousness.emotion.as_dict()}
