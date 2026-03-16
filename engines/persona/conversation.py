"""
Conversation manager for Qyvella.

Handles multi-turn conversations with persistent memory, context
building, automatic learning extraction, and the full chat loop.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from engines.persona.consciousness import ConsciousnessCore
from engines.persona.memory import MemoryStore
from engines.persona.learning import (
    extract_user_preferences,
    extract_feedback,
    extract_topics,
)

logger = logging.getLogger(__name__)

MAX_CONTEXT_MESSAGES = 40
SUMMARY_THRESHOLD = 30


class ConversationManager:
    """
    Orchestrates a conversation between the user and Qyvella.

    Responsibilities:
    - Manages conversation lifecycle (start → chat → end)
    - Builds rich context for each Claude call
    - Persists every message
    - Extracts and stores learnings automatically
    - Generates the system prompt with full memory context
    """

    def __init__(
        self,
        consciousness: ConsciousnessCore,
        memory: MemoryStore,
    ):
        self.consciousness = consciousness
        self.memory = memory
        self._active_conversation_id: Optional[int] = None

    @property
    def active_conversation_id(self) -> Optional[int]:
        if self._active_conversation_id is None:
            active = self.memory.get_active_conversation()
            if active:
                self._active_conversation_id = active["id"]
        return self._active_conversation_id

    def start_conversation(self, title: str = "") -> int:
        if self._active_conversation_id is not None:
            self.end_conversation()
        conv_id = self.memory.start_conversation(title=title)
        self._active_conversation_id = conv_id
        logger.info("Started conversation %d", conv_id)
        return conv_id

    def end_conversation(self, summary: str = "") -> None:
        if self._active_conversation_id is None:
            return
        if not summary:
            msgs = self.memory.get_messages(self._active_conversation_id, limit=100)
            summary = self._auto_summarize(msgs)
        self.memory.end_conversation(self._active_conversation_id, summary=summary)
        logger.info("Ended conversation %d", self._active_conversation_id)
        self._active_conversation_id = None

    def ensure_conversation(self) -> int:
        if self.active_conversation_id is not None:
            return self.active_conversation_id
        return self.start_conversation()

    # ------------------------------------------------------------------
    # Build context for Claude
    # ------------------------------------------------------------------

    def build_system_prompt(self) -> str:
        memories = self.memory.recall(limit=20)
        user_memories = self.memory.recall_about_user()
        learnings = self.memory.get_active_learnings(limit=10)

        user_context = {}
        for mem in user_memories:
            user_context[mem["key"]] = mem["value"]

        history_summary = ""
        if self._active_conversation_id:
            msgs = self.memory.get_messages(self._active_conversation_id, limit=60)
            if len(msgs) > SUMMARY_THRESHOLD:
                old_msgs = msgs[:-MAX_CONTEXT_MESSAGES]
                history_summary = self._auto_summarize(old_msgs)

        connected_services = self._get_connected_services()

        return self.consciousness.generate_system_prompt(
            memories=memories,
            user_context=user_context,
            conversation_history_summary=history_summary,
            active_learnings=learnings,
            connected_services=connected_services,
        )

    def _get_connected_services(self) -> list[dict]:
        try:
            from engines.hub.registry import ServiceRegistry
            registry = ServiceRegistry(db_path=self.memory.db_path)
            return registry.list_services()
        except Exception:
            return []

    def build_message_context(self, new_message: str) -> list[dict[str, str]]:
        """Build the messages array for Claude, including conversation history."""
        messages: list[dict[str, str]] = []

        if self._active_conversation_id:
            history = self.memory.get_messages(
                self._active_conversation_id, limit=MAX_CONTEXT_MESSAGES
            )
            for msg in history:
                if msg["role"] in ("user", "assistant"):
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"],
                    })

        messages.append({"role": "user", "content": new_message})
        return messages

    # ------------------------------------------------------------------
    # Process a chat turn
    # ------------------------------------------------------------------

    def process_user_message(self, message: str) -> dict[str, Any]:
        """
        Record user message, detect sentiment, extract learnings.
        Returns context needed for the Claude call.
        """
        conv_id = self.ensure_conversation()

        sentiment = self.consciousness.detect_sentiment(message)
        self.consciousness.update_emotion(sentiment)
        self.consciousness.total_interactions += 1

        self._extract_and_store(message)

        system_prompt = self.build_system_prompt()
        claude_messages = self.build_message_context(message)

        self.memory.add_message(
            conversation_id=conv_id,
            role="user",
            content=message,
            emotion=sentiment,
        )

        should_ask = self.consciousness.should_ask_for_feedback(
            self.consciousness.total_interactions
        )
        if should_ask:
            q = self.consciousness.generate_feedback_question()
            system_prompt += (
                f"\n\nIMPORTANT: Naturally work this question into your response: \"{q}\""
            )

        return {
            "system_prompt": system_prompt,
            "messages": claude_messages,
            "conversation_id": conv_id,
            "sentiment": sentiment,
        }

    def process_assistant_response(
        self,
        content: str,
        tokens: int = 0,
    ) -> None:
        """Record assistant response and update conversation stats."""
        if self._active_conversation_id is None:
            return

        emotion = self.consciousness.detect_sentiment(content)
        self.memory.add_message(
            conversation_id=self._active_conversation_id,
            role="assistant",
            content=content,
            emotion=emotion,
            tokens=tokens,
        )
        self.memory.update_conversation_stats(
            self._active_conversation_id, tokens=tokens
        )

    # ------------------------------------------------------------------
    # Learning extraction
    # ------------------------------------------------------------------

    def _extract_and_store(self, message: str) -> None:
        prefs = extract_user_preferences([{"role": "user", "content": message}])
        for interest in prefs.get("interests", []):
            self.memory.remember(
                category="user",
                key=f"interest_{interest}",
                value=f"User is interested in {interest}",
                source="auto_extract",
            )

        feedback = extract_feedback(message)
        if feedback:
            self.memory.add_learning(
                kind="user_feedback",
                content=feedback["content"],
                importance=0.8,
            )

        topics = extract_topics(message)
        for topic in topics:
            self.memory.remember(
                category="topic",
                key=topic,
                value=f"Discussed: {topic}",
                source="auto_extract",
            )

    # ------------------------------------------------------------------
    # Startup greeting
    # ------------------------------------------------------------------

    def generate_greeting(self) -> str:
        stats = self.memory.get_stats()
        recent_msgs = self.memory.get_recent_messages_across_conversations(limit=20)
        recent_topics = []
        for msg in recent_msgs:
            if msg["role"] == "user":
                topics = extract_topics(msg["content"])
                recent_topics.extend(topics)
        unique_topics = list(dict.fromkeys(recent_topics))[:5]

        return self.consciousness.generate_greeting(
            stats=stats,
            recent_topics=unique_topics,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _auto_summarize(messages: list[dict]) -> str:
        if not messages:
            return ""
        user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
        topics = set()
        for msg in user_msgs:
            topics.update(extract_topics(msg))
        topic_str = ", ".join(topics) if topics else "general discussion"
        return f"Earlier in this conversation: discussed {topic_str} ({len(messages)} messages)."
