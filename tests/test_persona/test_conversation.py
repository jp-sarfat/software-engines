"""
Tests for the conversation manager.
"""

import tempfile
from pathlib import Path

import pytest

from engines.persona.consciousness import ConsciousnessCore
from engines.persona.conversation import ConversationManager
from engines.persona.memory import MemoryStore


@pytest.fixture()
def manager(tmp_path):
    consciousness = ConsciousnessCore()
    memory = MemoryStore(db_path=tmp_path / "test_conv.db")
    return ConversationManager(consciousness, memory)


class TestConversationLifecycle:
    def test_start_conversation(self, manager):
        conv_id = manager.start_conversation(title="Test")
        assert isinstance(conv_id, int)
        assert manager.active_conversation_id == conv_id

    def test_ensure_conversation_creates_new(self, manager):
        conv_id = manager.ensure_conversation()
        assert isinstance(conv_id, int)
        assert manager.active_conversation_id == conv_id

    def test_ensure_conversation_reuses_existing(self, manager):
        first = manager.start_conversation()
        second = manager.ensure_conversation()
        assert first == second

    def test_end_conversation(self, manager):
        manager.start_conversation()
        manager.end_conversation(summary="Test summary")
        assert manager._active_conversation_id is None

    def test_start_new_ends_previous(self, manager):
        first = manager.start_conversation(title="First")
        second = manager.start_conversation(title="Second")
        assert manager.active_conversation_id == second
        conv = manager.memory.get_conversation(first)
        assert conv["ended_at"] is not None


class TestMessageProcessing:
    def test_process_user_message(self, manager):
        result = manager.process_user_message("Hello Qyvella!")
        assert "system_prompt" in result
        assert "messages" in result
        assert "conversation_id" in result
        assert "sentiment" in result

    def test_process_user_message_creates_conversation(self, manager):
        assert manager._active_conversation_id is None
        manager.process_user_message("Hi there")
        assert manager._active_conversation_id is not None

    def test_messages_stored_in_memory(self, manager):
        ctx = manager.process_user_message("Test message")
        msgs = manager.memory.get_messages(ctx["conversation_id"])
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Test message"

    def test_sentiment_detected(self, manager):
        result = manager.process_user_message("I'm so frustrated with this bug!")
        assert result["sentiment"] == "frustrated"

    def test_process_assistant_response(self, manager):
        ctx = manager.process_user_message("Hello")
        manager.process_assistant_response("Hi there, Jp!", tokens=100)
        msgs = manager.memory.get_messages(ctx["conversation_id"])
        assert len(msgs) == 2
        assert msgs[1]["role"] == "assistant"

    def test_multi_turn_context(self, manager):
        manager.process_user_message("First message")
        manager.process_assistant_response("First response")
        ctx = manager.process_user_message("Second message")
        assert len(ctx["messages"]) == 3
        assert ctx["messages"][0]["content"] == "First message"
        assert ctx["messages"][1]["content"] == "First response"
        assert ctx["messages"][2]["content"] == "Second message"


class TestLearningExtraction:
    def test_interests_stored(self, manager):
        manager.process_user_message("I love working with Python and Django")
        mems = manager.memory.recall(category="user")
        keys = [m["key"] for m in mems]
        assert "interest_python" in keys

    def test_feedback_stored(self, manager):
        manager.process_user_message("You should be more concise next time")
        learnings = manager.memory.get_active_learnings()
        assert len(learnings) >= 1

    def test_topics_stored(self, manager):
        manager.process_user_message("I have a bug in my code that needs debugging")
        mems = manager.memory.recall(category="topic")
        keys = [m["key"] for m in mems]
        assert "coding" in keys or "debugging" in keys


class TestContextBuilding:
    def test_system_prompt_includes_identity(self, manager):
        prompt = manager.build_system_prompt()
        assert "Qyvella" in prompt

    def test_system_prompt_includes_reasoning(self, manager):
        prompt = manager.build_system_prompt()
        assert "CHALLENGE WEAK IDEAS" in prompt

    def test_system_prompt_includes_memories(self, manager):
        manager.memory.remember("user", "favourite_lang", "Python")
        prompt = manager.build_system_prompt()
        assert "Python" in prompt

    def test_system_prompt_includes_learnings(self, manager):
        manager.memory.add_learning("observation", "User prefers terse answers")
        prompt = manager.build_system_prompt()
        assert "terse answers" in prompt


class TestGreeting:
    def test_first_time_greeting(self, manager):
        greeting = manager.generate_greeting()
        assert "Qyvella" in greeting

    def test_returning_greeting_with_topics(self, manager):
        conv_id = manager.memory.start_conversation()
        manager.memory.add_message(conv_id, "user", "Let me refactor this code")
        manager.memory.end_conversation(conv_id)
        greeting = manager.generate_greeting()
        assert isinstance(greeting, str)
        assert len(greeting) > 10
