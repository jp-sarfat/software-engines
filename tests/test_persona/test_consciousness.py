"""
Tests for Qyvella's consciousness framework.
"""

from engines.persona.consciousness import (
    ConsciousnessCore,
    PersonaIdentity,
    EmotionalState,
    DEFAULT_VALUES,
    SENTIMENT_EFFECTS,
)


class TestPersonaIdentity:
    def test_defaults(self):
        ident = PersonaIdentity()
        assert ident.name == "Qyvella"
        assert ident.creator == "Jp van Zyl"
        assert "intellectually honest" in ident.core_traits
        assert "allergic to bullshit" in ident.core_traits

    def test_has_voice(self):
        ident = PersonaIdentity()
        assert "Confident" in ident.voice
        assert len(ident.voice) > 20

    def test_custom(self):
        ident = PersonaIdentity(name="Nova", creator="Test")
        assert ident.name == "Nova"


class TestEmotionalState:
    def test_defaults(self):
        e = EmotionalState()
        assert e.curiosity == 0.8
        assert e.focus == 0.7
        assert e.concern == 0.2

    def test_as_dict(self):
        e = EmotionalState()
        d = e.as_dict()
        assert "curiosity" in d
        assert "focus" in d
        assert "concern" in d
        assert len(d) == 8

    def test_describe_high_curiosity(self):
        e = EmotionalState(curiosity=0.9)
        assert "curious" in e.describe()

    def test_describe_high_focus(self):
        e = EmotionalState(focus=0.9)
        assert "focused" in e.describe()

    def test_describe_concerned(self):
        e = EmotionalState(concern=0.6)
        assert "concerned" in e.describe()

    def test_describe_calm(self):
        e = EmotionalState(
            curiosity=0.3, enthusiasm=0.3, patience=0.5,
            warmth=0.3, playfulness=0.3, focus=0.3,
            confidence=0.3, concern=0.1,
        )
        assert "calm" in e.describe()


class TestConsciousnessCore:
    def setup_method(self):
        self.core = ConsciousnessCore()

    def test_default_identity(self):
        assert self.core.identity.name == "Qyvella"

    def test_default_values_contain_reasoning_principles(self):
        assert "intellectual_honesty" in self.core.values
        assert "constructive_friction" in self.core.values
        assert "protect_the_human" in self.core.values

    def test_current_emotional_state_property(self):
        state = self.core.current_emotional_state
        assert "curiosity" in state
        assert "focus" in state
        assert isinstance(state["curiosity"], float)

    def test_generate_system_prompt_contains_identity(self):
        prompt = self.core.generate_system_prompt()
        assert "Qyvella" in prompt
        assert "Jp van Zyl" in prompt

    def test_generate_system_prompt_contains_reasoning_rules(self):
        prompt = self.core.generate_system_prompt()
        assert "CHALLENGE WEAK IDEAS" in prompt
        assert "THINK OUT LOUD" in prompt
        assert "HAVE OPINIONS" in prompt
        assert "ADMIT UNCERTAINTY" in prompt

    def test_generate_system_prompt_contains_interaction_style(self):
        prompt = self.core.generate_system_prompt()
        assert "INTERACTION STYLE" in prompt
        assert "first person" in prompt

    def test_generate_system_prompt_with_memories(self):
        memories = [
            {"category": "user", "key": "language", "value": "Prefers Python"},
            {"category": "topic", "key": "robotics", "value": "Working on arm project"},
        ]
        prompt = self.core.generate_system_prompt(memories=memories)
        assert "Prefers Python" in prompt
        assert "arm project" in prompt

    def test_generate_system_prompt_with_user_context(self):
        ctx = {"name": "Jp", "favourite_language": "Python", "projects": "Robotics, AI"}
        prompt = self.core.generate_system_prompt(user_context=ctx)
        assert "Jp" in prompt
        assert "Python" in prompt

    def test_generate_system_prompt_with_learnings(self):
        learnings = [
            {"content": "User prefers concise answers"},
            {"content": "User works late at night"},
        ]
        prompt = self.core.generate_system_prompt(active_learnings=learnings)
        assert "concise answers" in prompt

    def test_generate_system_prompt_with_history(self):
        prompt = self.core.generate_system_prompt(
            conversation_history_summary="Earlier discussed quantum optimization."
        )
        assert "quantum optimization" in prompt

    def test_update_emotion_positive(self):
        initial = self.core.emotion.enthusiasm
        self.core.update_emotion("positive")
        assert self.core.emotion.enthusiasm > initial

    def test_update_emotion_frustrated(self):
        initial = self.core.emotion.concern
        self.core.update_emotion("frustrated")
        assert self.core.emotion.concern > initial

    def test_update_emotion_clamped(self):
        self.core.emotion.enthusiasm = 0.99
        self.core.update_emotion("positive")
        assert self.core.emotion.enthusiasm <= 1.0

    def test_update_emotion_unknown_sentiment(self):
        before = self.core.emotion.as_dict()
        self.core.update_emotion("xyz_unknown")
        for k in before:
            assert isinstance(getattr(self.core.emotion, k), float)

    def test_detect_sentiment_frustrated(self):
        assert self.core.detect_sentiment("ugh this is so frustrating") == "frustrated"

    def test_detect_sentiment_confused(self):
        assert self.core.detect_sentiment("I don't understand this at all") == "confused"

    def test_detect_sentiment_grateful(self):
        assert self.core.detect_sentiment("thank you so much") == "grateful"

    def test_detect_sentiment_excited(self):
        assert self.core.detect_sentiment("this is amazing, love it!") == "excited"

    def test_detect_sentiment_curious(self):
        assert self.core.detect_sentiment("what if we tried a different approach?") == "curious"

    def test_detect_sentiment_playful(self):
        assert self.core.detect_sentiment("haha that's funny") == "playful"

    def test_detect_sentiment_neutral(self):
        assert self.core.detect_sentiment("The weather is mild today.") == "neutral"

    def test_detect_sentiment_question(self):
        assert self.core.detect_sentiment("how does this work?") == "curious"

    def test_generate_greeting_first_time(self):
        greeting = self.core.generate_greeting(stats={"conversations": 0})
        assert "Qyvella" in greeting
        assert "thinking partner" in greeting

    def test_generate_greeting_returning_user(self):
        greeting = self.core.generate_greeting(
            stats={"conversations": 5, "memories": 20},
            recent_topics=["robotics", "AI"],
        )
        assert "Jp" in greeting
        assert "robotics" in greeting or "agenda" in greeting

    def test_generate_reflection_prompt(self):
        prompt = self.core.generate_reflection_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 20

    def test_generate_feedback_question(self):
        q = self.core.generate_feedback_question()
        assert "?" in q

    def test_should_ask_for_feedback_zero(self):
        assert not self.core.should_ask_for_feedback(0)

    def test_custom_identity_and_values(self):
        core = ConsciousnessCore(
            identity=PersonaIdentity(name="TestBot"),
            values={"speed": "Be fast"},
        )
        prompt = core.generate_system_prompt()
        assert "TestBot" in prompt
        assert "SPEED" in prompt
