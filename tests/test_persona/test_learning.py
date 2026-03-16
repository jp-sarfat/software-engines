"""
Tests for learning extraction.
"""

from engines.persona.learning import (
    extract_user_preferences,
    extract_topics,
    summarize_conversation,
    extract_feedback,
)


class TestExtractUserPreferences:
    def test_detects_robotics_interest(self):
        msgs = [{"role": "user", "content": "I love working on my robot arm"}]
        prefs = extract_user_preferences(msgs)
        assert "robotics" in prefs["interests"]

    def test_detects_python_interest(self):
        msgs = [{"role": "user", "content": "Can you help with my Django project?"}]
        prefs = extract_user_preferences(msgs)
        assert "python" in prefs["interests"]

    def test_detects_quantum_interest(self):
        msgs = [{"role": "user", "content": "I'm working on quantum optimization"}]
        prefs = extract_user_preferences(msgs)
        assert "quantum" in prefs["interests"]

    def test_no_interests_detected(self):
        msgs = [{"role": "user", "content": "Hello there"}]
        prefs = extract_user_preferences(msgs)
        assert prefs["interests"] == []

    def test_ignores_assistant_messages(self):
        msgs = [
            {"role": "assistant", "content": "I know about robots"},
            {"role": "user", "content": "Tell me about cooking"},
        ]
        prefs = extract_user_preferences(msgs)
        assert "robotics" not in prefs["interests"]

    def test_multiple_interests(self):
        msgs = [{"role": "user", "content": "I use python and react with AI models"}]
        prefs = extract_user_preferences(msgs)
        assert "python" in prefs["interests"]
        assert "AI" in prefs["interests"]

    def test_concise_style(self):
        msgs = [{"role": "user", "content": "Please be brief and concise"}]
        prefs = extract_user_preferences(msgs)
        assert prefs["communication_style"] == "concise"

    def test_detailed_style(self):
        msgs = [{"role": "user", "content": "Please elaborate in detail"}]
        prefs = extract_user_preferences(msgs)
        assert prefs["communication_style"] == "detailed"


class TestExtractTopics:
    def test_coding_topic(self):
        topics = extract_topics("help me refactor this code")
        assert "coding" in topics

    def test_debugging_topic(self):
        topics = extract_topics("I'm getting a traceback error")
        assert "debugging" in topics

    def test_ai_topic(self):
        topics = extract_topics("How do I train this neural model?")
        assert "AI" in topics

    def test_planning_topic(self):
        topics = extract_topics("Let's plan the roadmap for this sprint")
        assert "planning" in topics

    def test_no_topics(self):
        topics = extract_topics("hello there")
        assert topics == []

    def test_multiple_topics(self):
        topics = extract_topics("I have a bug in my AI model code")
        assert "coding" in topics
        assert "debugging" in topics
        assert "AI" in topics


class TestSummarizeConversation:
    def test_empty_messages(self):
        assert summarize_conversation([]) == "Empty conversation"

    def test_coding_topic(self):
        msgs = [{"role": "user", "content": "Help me with python code"}]
        summary = summarize_conversation(msgs)
        assert "coding" in summary

    def test_robotics_topic(self):
        msgs = [{"role": "user", "content": "My servo is broken"}]
        summary = summarize_conversation(msgs)
        assert "robotics" in summary

    def test_general_discussion(self):
        msgs = [{"role": "user", "content": "Good morning, nice to see you"}]
        summary = summarize_conversation(msgs)
        assert "general discussion" in summary

    def test_message_count(self):
        msgs = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ]
        summary = summarize_conversation(msgs)
        assert "2 messages" in summary


class TestExtractFeedback:
    def test_detects_feedback(self):
        fb = extract_feedback("You should be more concise")
        assert fb is not None
        assert fb["type"] == "improvement_feedback"

    def test_detects_preference(self):
        fb = extract_feedback("I prefer shorter answers")
        assert fb is not None

    def test_detects_stop(self):
        fb = extract_feedback("Please stop adding emojis")
        assert fb is not None

    def test_no_feedback(self):
        fb = extract_feedback("Tell me about quantum computing")
        assert fb is None

    def test_case_insensitive(self):
        fb = extract_feedback("NEXT TIME please be faster")
        assert fb is not None
