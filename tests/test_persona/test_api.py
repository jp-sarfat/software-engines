"""
Tests for Qyvella's API endpoints.
"""

import json


class TestStatusAndGreeting:
    def test_status(self, client):
        resp = client.get("/persona/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Qyvella"
        assert "emotional_state" in data
        assert "memory_stats" in data
        assert "greeting" in data

    def test_greeting(self, client):
        resp = client.get("/persona/greeting")
        assert resp.status_code == 200
        data = resp.json()
        assert "greeting" in data
        assert len(data["greeting"]) > 10

    def test_briefing(self, client):
        resp = client.get("/persona/briefing")
        assert resp.status_code == 200
        data = resp.json()
        assert "greeting" in data
        assert "emotional_state" in data
        assert "recent_topics" in data
        assert "memory_count" in data
        assert "conversation_count" in data
        assert "recent_conversations" in data
        assert "active_learnings" in data
        assert isinstance(data["recent_topics"], list)


class TestChat:
    def test_chat_returns_response(self, client):
        resp = client.post("/persona/chat", json={"message": "Hello Qyvella"})
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "conversation_id" in data
        assert "emotion" in data
        assert "sentiment_detected" in data

    def test_chat_empty_message(self, client):
        resp = client.post("/persona/chat", json={"message": ""})
        assert resp.status_code == 422

    def test_chat_creates_conversation(self, client):
        resp = client.post("/persona/chat", json={"message": "First message"})
        assert resp.status_code == 200
        conv_id = resp.json()["conversation_id"]
        assert isinstance(conv_id, int)
        assert conv_id > 0

    def test_chat_with_nonexistent_conversation(self, client):
        resp = client.post(
            "/persona/chat",
            json={"message": "Hello", "conversation_id": 99999}
        )
        assert resp.status_code == 404


class TestThink:
    def test_think_reason_mode(self, client):
        resp = client.post("/persona/think", json={
            "problem": "Should I use microservices or a monolith?",
            "mode": "reason",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert data["mode"] == "reason"
        assert "conversation_id" in data

    def test_think_brainstorm_mode(self, client):
        resp = client.post("/persona/think", json={
            "problem": "Ideas for a new side project",
            "mode": "brainstorm",
        })
        assert resp.status_code == 200
        assert resp.json()["mode"] == "brainstorm"

    def test_think_devil_advocate_mode(self, client):
        resp = client.post("/persona/think", json={
            "problem": "I want to rewrite everything in Rust",
            "mode": "devil_advocate",
        })
        assert resp.status_code == 200
        assert resp.json()["mode"] == "devil_advocate"

    def test_think_plan_mode(self, client):
        resp = client.post("/persona/think", json={
            "problem": "Build an AI companion",
            "mode": "plan",
        })
        assert resp.status_code == 200
        assert resp.json()["mode"] == "plan"

    def test_think_with_context(self, client):
        resp = client.post("/persona/think", json={
            "problem": "How should I structure this?",
            "context": "Building a FastAPI app with SQLite and Claude integration",
            "mode": "reason",
        })
        assert resp.status_code == 200

    def test_think_invalid_mode(self, client):
        resp = client.post("/persona/think", json={
            "problem": "test",
            "mode": "invalid_mode",
        })
        assert resp.status_code == 422

    def test_think_empty_problem(self, client):
        resp = client.post("/persona/think", json={
            "problem": "",
            "mode": "reason",
        })
        assert resp.status_code == 422


class TestDigest:
    def test_digest_returns_response(self, client):
        resp = client.post("/persona/digest", json={
            "text": "Jp prefers Python for backend work. He is building a quantum computing bridge. His timezone is UTC+2.",
            "source": "test",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "extracted_count" in data
        assert "memories_created" in data
        assert "summary" in data

    def test_digest_too_short(self, client):
        resp = client.post("/persona/digest", json={"text": "short"})
        assert resp.status_code == 422

    def test_digest_custom_category(self, client):
        resp = client.post("/persona/digest", json={
            "text": "The project uses FastAPI with SQLite for persistence and Claude for AI.",
            "extract_as_category": "project_info",
        })
        assert resp.status_code == 200


class TestConversationManagement:
    def test_start_conversation(self, client):
        resp = client.post("/persona/conversation/start?title=Test")
        assert resp.status_code == 200
        data = resp.json()
        assert "conversation_id" in data
        assert data["status"] == "started"

    def test_end_conversation(self, client):
        client.post("/persona/conversation/start")
        resp = client.post("/persona/conversation/end")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ended"

    def test_list_conversations(self, client):
        resp = client.get("/persona/conversations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_conversation_not_found(self, client):
        resp = client.get("/persona/conversation/99999")
        assert resp.status_code == 404

    def test_search_conversations(self, client):
        resp = client.post(
            "/persona/conversations/search",
            json={"query": "test"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "conversations" in data
        assert "messages" in data

    def test_summarize_conversation_not_found(self, client):
        resp = client.post("/persona/conversation/99999/summarize")
        assert resp.status_code == 404


class TestMemory:
    def test_remember(self, client):
        resp = client.post("/persona/remember", json={
            "category": "user",
            "key": "test_pref",
            "value": "Testing memory",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "remembered"

    def test_list_memories(self, client):
        client.post("/persona/remember", json={
            "category": "user",
            "key": "name",
            "value": "Jp",
        })
        resp = client.get("/persona/memories?category=user")
        assert resp.status_code == 200

    def test_search_memories(self, client):
        client.post("/persona/remember", json={
            "category": "user",
            "key": "language",
            "value": "Python",
        })
        resp = client.post("/persona/memories/search", json={"query": "Python"})
        assert resp.status_code == 200

    def test_quick_note(self, client):
        resp = client.post("/persona/note", json={
            "note": "Remember to refactor the quantum bridge",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "noted"

    def test_quick_note_custom_category(self, client):
        resp = client.post("/persona/note", json={
            "note": "Deploy to production Friday",
            "category": "todo",
        })
        assert resp.status_code == 200

    def test_forget(self, client):
        client.post("/persona/remember", json={
            "category": "test",
            "key": "to_forget",
            "value": "This should be forgotten",
        })
        resp = client.post("/persona/forget", json={
            "category": "test",
            "key": "to_forget",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "forgotten"

    def test_forget_not_found(self, client):
        resp = client.post("/persona/forget", json={
            "category": "nonexistent",
            "key": "nope",
        })
        assert resp.status_code == 404

    def test_seed_knowledge(self, client):
        resp = client.post("/persona/seed", json={
            "facts": [
                {"category": "user", "key": "name", "value": "Jp van Zyl"},
                {"category": "user", "key": "timezone", "value": "UTC+2"},
                {"category": "user", "key": "main_language", "value": "Python"},
            ]
        })
        assert resp.status_code == 200
        assert resp.json()["facts_stored"] == 3

    def test_seed_skips_incomplete(self, client):
        resp = client.post("/persona/seed", json={
            "facts": [
                {"category": "user", "key": "name", "value": "Jp"},
                {"key": "no_value"},
                {"category": "user", "value": "no_key"},
            ]
        })
        assert resp.status_code == 200
        assert resp.json()["facts_stored"] == 1

    def test_export_brain(self, client):
        client.post("/persona/remember", json={
            "category": "test",
            "key": "export_test",
            "value": "This should be in the export",
        })
        resp = client.get("/persona/brain/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "memories" in data
        assert "learnings" in data
        assert "reflections" in data
        assert "exported_at" in data

    def test_import_brain(self, client):
        resp = client.post("/persona/brain/import", json={
            "memories": [
                {"category": "imported", "key": "item1", "value": "Value 1"},
                {"category": "imported", "key": "item2", "value": "Value 2"},
            ]
        })
        assert resp.status_code == 200
        assert resp.json()["memories_imported"] == 2


class TestLearnings:
    def test_list_learnings_empty(self, client):
        resp = client.get("/persona/learnings")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_deactivate_learning_not_found(self, client):
        resp = client.post("/persona/learnings/99999/deactivate")
        assert resp.status_code == 404

    def test_reactivate_learning_not_found(self, client):
        resp = client.post("/persona/learnings/99999/reactivate")
        assert resp.status_code == 404


class TestReflectionAndEmotion:
    def test_reflect(self, client):
        resp = client.post("/persona/reflect")
        assert resp.status_code == 200
        data = resp.json()
        assert "prompt" in data
        assert "timestamp" in data

    def test_update_emotion(self, client):
        resp = client.post("/persona/emotion/positive")
        assert resp.status_code == 200
        data = resp.json()
        assert "emotional_state" in data
        assert "curiosity" in data["emotional_state"]
        assert "focus" in data["emotional_state"]
