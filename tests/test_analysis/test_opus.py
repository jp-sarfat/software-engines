"""
Tests for Opus validation phase.
"""

from engines.analysis.opus import (
    build_opus_prompt,
    _extract_json_from_text,
    OPUS_SYSTEM_PROMPT,
)


class TestExtractJsonFromText:
    def test_plain_json(self):
        result = _extract_json_from_text('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_in_markdown(self):
        text = 'Some text\n```json\n{"a": 1}\n```\nMore text'
        result = _extract_json_from_text(text)
        assert result == {"a": 1}

    def test_json_with_prefix(self):
        text = 'Here is the result: {"score": 0.95}'
        result = _extract_json_from_text(text)
        assert result["score"] == 0.95

    def test_invalid_json(self):
        result = _extract_json_from_text("not json at all")
        assert result == {}

    def test_nested_json(self):
        text = '{"outer": {"inner": 42}}'
        result = _extract_json_from_text(text)
        assert result["outer"]["inner"] == 42


class TestBuildOpusPrompt:
    def test_includes_project_name(self):
        prompt = build_opus_prompt("MyApp", "sonnet output", {}, {}, {}, {}, {})
        assert "MyApp" in prompt

    def test_includes_json_structure(self):
        prompt = build_opus_prompt("P", "raw", {}, {}, {}, {}, {})
        assert "security_analysis" in prompt
        assert "performance_analysis" in prompt
        assert "opus_confidence" in prompt

    def test_trims_sonnet_raw(self):
        long_raw = "x" * 5000
        prompt = build_opus_prompt("P", long_raw, {}, {}, {}, {}, {})
        assert len(prompt) < 5000 + 2000


class TestOpusSystemPrompt:
    def test_mentions_maximum_rigor(self):
        assert "MAXIMUM RIGOR" in OPUS_SYSTEM_PROMPT
