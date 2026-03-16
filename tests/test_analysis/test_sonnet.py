"""
Tests for Sonnet analysis phase.
"""

from engines.analysis.sonnet import build_sonnet_prompt, SONNET_SYSTEM_PROMPT


class TestBuildSonnetPrompt:
    def test_includes_project_name(self):
        prompt = build_sonnet_prompt("MyApp", "desc", "prod", {}, {}, {}, {}, {})
        assert "MyApp" in prompt

    def test_includes_sections(self):
        prompt = build_sonnet_prompt("P", "", "prod", {}, {}, {}, {}, {})
        assert "Technology Stack" in prompt
        assert "Routes & Endpoints" in prompt
        assert "Authentication System" in prompt
        assert "Database Schema" in prompt
        assert "Test strategy recommendations" in prompt

    def test_includes_tech_stack(self):
        ts = {"primary_language": "Python", "framework": "FastAPI"}
        prompt = build_sonnet_prompt("P", "", "prod", ts, {}, {}, {}, {})
        assert "Python" in prompt
        assert "FastAPI" in prompt


class TestSonnetSystemPrompt:
    def test_mentions_dual_claude(self):
        assert "DUAL CLAUDE ARCHITECTURE" in SONNET_SYSTEM_PROMPT

    def test_mentions_phase1(self):
        assert "PHASE 1" in SONNET_SYSTEM_PROMPT
