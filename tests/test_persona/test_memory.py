"""
Tests for Qyvella's persistent memory store.
"""

import tempfile
from pathlib import Path

import pytest

from engines.persona.memory import MemoryStore


@pytest.fixture()
def store(tmp_path):
    return MemoryStore(db_path=tmp_path / "test_qyvella.db")


class TestConversations:
    def test_start_conversation(self, store):
        conv_id = store.start_conversation(title="Test chat")
        assert isinstance(conv_id, int)
        assert conv_id > 0

    def test_get_active_conversation(self, store):
        conv_id = store.start_conversation(title="Active")
        active = store.get_active_conversation()
        assert active is not None
        assert active["id"] == conv_id
        assert active["title"] == "Active"

    def test_end_conversation(self, store):
        conv_id = store.start_conversation()
        store.end_conversation(conv_id, summary="Talked about coding")
        conv = store.get_conversation(conv_id)
        assert conv["ended_at"] is not None
        assert conv["summary"] == "Talked about coding"

    def test_no_active_after_end(self, store):
        conv_id = store.start_conversation()
        store.end_conversation(conv_id)
        active = store.get_active_conversation()
        assert active is None

    def test_list_conversations(self, store):
        store.start_conversation(title="First")
        store.start_conversation(title="Second")
        convos = store.list_conversations(limit=10)
        assert len(convos) == 2
        assert convos[0]["title"] == "Second"

    def test_get_nonexistent_conversation(self, store):
        assert store.get_conversation(9999) is None


class TestMessages:
    def test_add_and_get_messages(self, store):
        conv_id = store.start_conversation()
        store.add_message(conv_id, "user", "Hello Qyvella")
        store.add_message(conv_id, "assistant", "Hey there!")
        msgs = store.get_messages(conv_id)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_message_order(self, store):
        conv_id = store.start_conversation()
        store.add_message(conv_id, "user", "First")
        store.add_message(conv_id, "assistant", "Second")
        store.add_message(conv_id, "user", "Third")
        msgs = store.get_messages(conv_id)
        assert msgs[0]["content"] == "First"
        assert msgs[2]["content"] == "Third"

    def test_message_with_emotion(self, store):
        conv_id = store.start_conversation()
        store.add_message(conv_id, "user", "This is exciting!", emotion="excited")
        msgs = store.get_messages(conv_id)
        assert msgs[0]["emotion"] == "excited"

    def test_total_message_count(self, store):
        conv_id = store.start_conversation()
        store.add_message(conv_id, "user", "One")
        store.add_message(conv_id, "assistant", "Two")
        assert store.total_message_count() == 2

    def test_recent_messages_across_conversations(self, store):
        c1 = store.start_conversation()
        store.add_message(c1, "user", "Conv 1 msg")
        store.end_conversation(c1)
        c2 = store.start_conversation()
        store.add_message(c2, "user", "Conv 2 msg")
        recent = store.get_recent_messages_across_conversations(limit=10)
        assert len(recent) == 2

    def test_update_conversation_stats(self, store):
        conv_id = store.start_conversation()
        store.add_message(conv_id, "user", "Hello")
        store.add_message(conv_id, "assistant", "Hi")
        store.update_conversation_stats(conv_id, tokens=150)
        conv = store.get_conversation(conv_id)
        assert conv["message_count"] == 2
        assert conv["total_tokens"] == 150


class TestMemories:
    def test_remember_and_recall(self, store):
        store.remember("user", "name", "Jp")
        mems = store.recall(category="user")
        assert len(mems) == 1
        assert mems[0]["key"] == "name"
        assert mems[0]["value"] == "Jp"

    def test_upsert_memory(self, store):
        store.remember("user", "language", "Python")
        store.remember("user", "language", "Python and Ruby")
        mems = store.recall(category="user")
        assert len(mems) == 1
        assert "Ruby" in mems[0]["value"]

    def test_recall_all_categories(self, store):
        store.remember("user", "name", "Jp")
        store.remember("topic", "current_project", "AI companion")
        mems = store.recall()
        assert len(mems) == 2

    def test_recall_about_user(self, store):
        store.remember("user", "timezone", "UTC+2")
        store.remember("topic", "coding", "Loves Python")
        user_mems = store.recall_about_user()
        assert len(user_mems) == 1
        assert user_mems[0]["category"] == "user"

    def test_search_memories(self, store):
        store.remember("user", "language", "Python is the best")
        store.remember("topic", "project", "Building a robot")
        results = store.search_memories("Python")
        assert len(results) >= 1
        assert any("Python" in r["value"] for r in results)

    def test_search_no_results(self, store):
        store.remember("user", "name", "Jp")
        results = store.search_memories("nonexistent_xyz")
        assert results == []

    def test_memory_confidence(self, store):
        store.remember("user", "skill", "Python expert", confidence=0.9)
        mems = store.recall(category="user")
        assert mems[0]["confidence"] == 0.9


class TestLearnings:
    def test_add_learning(self, store):
        lid = store.add_learning("user_feedback", "Prefers concise answers", importance=0.8)
        assert isinstance(lid, int)

    def test_get_active_learnings(self, store):
        store.add_learning("user_feedback", "Be more direct", importance=0.9)
        store.add_learning("observation", "Works late at night", importance=0.5)
        learnings = store.get_active_learnings()
        assert len(learnings) == 2
        assert learnings[0]["importance"] >= learnings[1]["importance"]


class TestReflections:
    def test_add_reflection(self, store):
        rid = store.add_reflection(
            prompt="What have I learned?",
            response="I've learned to be more concise.",
            insights=["conciseness", "directness"],
        )
        assert isinstance(rid, int)

    def test_get_recent_reflections(self, store):
        store.add_reflection("Prompt 1", "Response 1")
        store.add_reflection("Prompt 2", "Response 2")
        refs = store.get_recent_reflections(limit=5)
        assert len(refs) == 2


class TestForget:
    def test_forget_memory(self, store):
        store.remember("user", "to_forget", "Bye")
        assert store.forget("user", "to_forget") is True
        mems = store.recall(category="user")
        assert all(m["key"] != "to_forget" for m in mems)

    def test_forget_nonexistent(self, store):
        assert store.forget("user", "nope") is False

    def test_forget_by_id(self, store):
        store.remember("user", "byid", "test")
        mems = store.recall(category="user")
        mid = mems[0]["id"]
        assert store.forget_by_id(mid) is True
        assert store.forget_by_id(mid) is False


class TestExportImport:
    def test_export(self, store):
        store.remember("user", "name", "Jp")
        store.add_learning("obs", "something")
        data = store.export_all()
        assert len(data["memories"]) == 1
        assert len(data["learnings"]) == 1
        assert "exported_at" in data

    def test_import_memories(self, store):
        items = [
            {"category": "user", "key": "a", "value": "1"},
            {"category": "user", "key": "b", "value": "2"},
        ]
        count = store.import_memories(items)
        assert count == 2
        mems = store.recall(category="user")
        assert len(mems) == 2

    def test_import_skips_invalid(self, store):
        items = [
            {"category": "user", "key": "ok", "value": "yes"},
            {"category": "", "key": "", "value": ""},
            {"key": "no_cat"},
        ]
        count = store.import_memories(items)
        assert count == 1


class TestSearchMessages:
    def test_search_messages(self, store):
        c = store.start_conversation(title="Search test")
        store.add_message(c, "user", "Help me with Python")
        store.add_message(c, "assistant", "Sure, what do you need?")
        results = store.search_messages("Python")
        assert len(results) >= 1
        assert "Python" in results[0]["content"]

    def test_search_messages_no_results(self, store):
        c = store.start_conversation()
        store.add_message(c, "user", "Hello")
        assert store.search_messages("nonexistent_xyz") == []

    def test_search_conversations(self, store):
        c = store.start_conversation(title="Quantum discussion")
        store.add_message(c, "user", "Let's talk about quantum")
        results = store.search_conversations("quantum")
        assert len(results) >= 1


class TestLearningManagement:
    def test_deactivate_learning(self, store):
        lid = store.add_learning("obs", "test", importance=0.5)
        assert store.deactivate_learning(lid) is True
        active = store.get_active_learnings()
        assert all(l["id"] != lid for l in active)

    def test_reactivate_learning(self, store):
        lid = store.add_learning("obs", "test", importance=0.5)
        store.deactivate_learning(lid)
        assert store.reactivate_learning(lid) is True
        active = store.get_active_learnings()
        assert any(l["id"] == lid for l in active)

    def test_get_all_learnings(self, store):
        lid = store.add_learning("obs", "active one", importance=0.5)
        lid2 = store.add_learning("obs", "inactive one", importance=0.3)
        store.deactivate_learning(lid2)
        all_l = store.get_all_learnings()
        assert len(all_l) == 2
        active = store.get_active_learnings()
        assert len(active) == 1

    def test_deactivate_nonexistent(self, store):
        assert store.deactivate_learning(99999) is False


class TestStats:
    def test_empty_stats(self, store):
        stats = store.get_stats()
        assert stats["conversations"] == 0
        assert stats["messages"] == 0
        assert stats["memories"] == 0

    def test_populated_stats(self, store):
        conv_id = store.start_conversation()
        store.add_message(conv_id, "user", "Hello")
        store.remember("user", "name", "Jp")
        store.add_learning("observation", "Something")
        stats = store.get_stats()
        assert stats["conversations"] == 1
        assert stats["messages"] == 1
        assert stats["memories"] == 1
        assert stats["learnings"] == 1
