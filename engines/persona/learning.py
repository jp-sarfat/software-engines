"""
Learning extraction from conversations.

Analyses messages for user preferences, topics, feedback,
and other signals that help Qyvella remember and adapt.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


INTEREST_KEYWORDS: dict[str, list[str]] = {
    "robotics": ["robot", "servo", "arm", "hardware", "motor", "sensor"],
    "AI": ["ai", "claude", "neural", "machine learning", "llm", "model", "gpt"],
    "python": ["python", "django", "flask", "fastapi", "pip"],
    "javascript": ["react", "javascript", "node", "typescript", "vue", "next"],
    "ruby": ["ruby", "rails", "gem", "bundler"],
    "philosophy": ["conscious", "singularity", "existence", "meaning", "purpose"],
    "quantum": ["quantum", "qubit", "annealing", "qubo", "optimization"],
    "devops": ["docker", "kubernetes", "deploy", "ci/cd", "pipeline"],
    "database": ["postgres", "sqlite", "redis", "database", "sql", "query"],
    "architecture": ["architecture", "design pattern", "microservice", "api design"],
}

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "coding": ["code", "function", "class", "bug", "error", "implement", "refactor"],
    "debugging": ["error", "bug", "fix", "broken", "crash", "traceback", "exception"],
    "design": ["architecture", "design", "pattern", "structure", "approach"],
    "robotics": ["robot", "servo", "arm", "motor", "sensor", "hardware"],
    "AI": ["ai", "model", "train", "neural", "claude", "llm", "prompt"],
    "planning": ["plan", "roadmap", "goal", "milestone", "sprint", "task"],
    "quantum": ["quantum", "qubo", "optimization", "annealing"],
    "learning": ["learn", "understand", "explain", "how does", "what is"],
    "career": ["job", "interview", "career", "salary", "company"],
    "personal": ["feel", "stressed", "tired", "excited", "worried", "happy"],
}

FEEDBACK_INDICATORS: list[str] = [
    "you should",
    "i wish you",
    "please be more",
    "less",
    "i prefer",
    "next time",
    "instead of",
    "better if",
    "don't",
    "stop",
    "could you try",
    "i'd like you to",
]


def extract_user_preferences(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyse messages to extract user preferences."""
    preferences: dict[str, Any] = {
        "communication_style": "detailed",
        "humor_appreciated": True,
        "technical_level": "advanced",
        "interests": [],
        "pain_points": [],
        "goals": [],
    }

    full_text = " ".join(
        m.get("content", "") for m in messages if m.get("role") == "user"
    ).lower()

    for interest, keywords in INTEREST_KEYWORDS.items():
        if any(kw in full_text for kw in keywords):
            preferences["interests"].append(interest)

    if any(w in full_text for w in ["brief", "short", "concise", "tldr"]):
        preferences["communication_style"] = "concise"
    if any(w in full_text for w in ["detail", "thorough", "explain", "elaborate"]):
        preferences["communication_style"] = "detailed"

    return preferences


def extract_topics(text: str) -> list[str]:
    """Extract topic tags from a piece of text."""
    text_lower = text.lower()
    found: list[str] = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(topic)
    return found


def summarize_conversation(messages: list[dict[str, Any]]) -> str:
    """Create a brief summary of the conversation for memory storage."""
    if not messages:
        return "Empty conversation"

    user_messages = [m["content"] for m in messages if m.get("role") == "user"]
    full_text = " ".join(user_messages)
    topics = extract_topics(full_text)
    topic_str = ", ".join(topics) if topics else "general discussion"
    return f"Discussed: {topic_str}. {len(messages)} messages exchanged."


def extract_feedback(message: str) -> Optional[dict[str, Any]]:
    """Extract improvement feedback from a user message."""
    message_lower = message.lower()
    for indicator in FEEDBACK_INDICATORS:
        if indicator in message_lower:
            return {
                "type": "improvement_feedback",
                "content": message,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            }
    return None
