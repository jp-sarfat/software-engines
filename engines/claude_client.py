"""
Shared Claude API client used by both Persona and Analysis engines.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Generator, Optional

import httpx

from engines.config import get_settings

logger = logging.getLogger(__name__)

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


class ClaudeClient:
    """
    Thin wrapper around the Anthropic Messages API.

    Supports:
    - Synchronous messaging with tool use
    - Streaming responses
    - Rate-limit retry with exponential back-off
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        advanced_model: Optional[str] = None,
        max_tokens: int = 8000,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.anthropic_api_key
        self.default_model = default_model or settings.claude_default_model
        self.advanced_model = advanced_model or settings.claude_advanced_model
        self.max_tokens = max_tokens

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def create_message(
        self,
        messages: list[dict[str, str]],
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        tools: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        if not self.is_configured:
            return {
                "error": "Claude API not configured",
                "content": "Anthropic API key is missing.",
            }

        model = model or self.default_model
        max_tokens = max_tokens or self.max_tokens

        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }

        return self._call_with_retry(payload, headers, max_retries=5)

    def _call_with_retry(
        self,
        payload: dict,
        headers: dict,
        max_retries: int = 5,
    ) -> dict[str, Any]:
        for attempt in range(1, max_retries + 1):
            try:
                with httpx.Client(timeout=180) as client:
                    resp = client.post(_ANTHROPIC_URL, json=payload, headers=headers)

                if resp.status_code == 429:
                    wait = 30 * (2 ** (attempt - 1))
                    logger.warning("Rate limited – waiting %ds (attempt %d)", wait, attempt)
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                return self._parse_response(resp.json())

            except httpx.HTTPStatusError as exc:
                logger.error("Claude API HTTP error: %s", exc)
                if attempt == max_retries:
                    return {"error": str(exc), "content": ""}
            except httpx.RequestError as exc:
                logger.error("Claude API request error: %s", exc)
                if attempt == max_retries:
                    return {"error": str(exc), "content": ""}
                time.sleep(10)

        return {"error": "Max retries exceeded", "content": ""}

    def stream_message(
        self,
        messages: list[dict[str, str]],
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> Generator[str, None, None]:
        """Yield text chunks from a streaming Claude response."""
        if not self.is_configured:
            yield "Anthropic API key is missing."
            return

        model = model or self.default_model
        max_tokens = max_tokens or self.max_tokens

        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
            "stream": True,
        }
        if system:
            payload["system"] = system

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }

        try:
            with httpx.Client(timeout=180) as client:
                with client.stream("POST", _ANTHROPIC_URL, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if line.startswith("data: "):
                            chunk = line[6:]
                            if chunk.strip() == "[DONE]":
                                break
                            try:
                                event = json.loads(chunk)
                                if event.get("type") == "content_block_delta":
                                    text = event.get("delta", {}).get("text", "")
                                    if text:
                                        yield text
                            except json.JSONDecodeError:
                                continue
        except Exception as exc:
            logger.error("Claude streaming error: %s", exc)
            yield f"\n[Error: {exc}]"

    @staticmethod
    def _parse_response(data: dict) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": data.get("id", ""),
            "model": data.get("model", ""),
            "role": data.get("role", "assistant"),
            "content": "",
            "tool_calls": [],
            "usage": {
                "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                "output_tokens": data.get("usage", {}).get("output_tokens", 0),
            },
        }
        for block in data.get("content", []):
            if block.get("type") == "text":
                result["content"] += block.get("text", "")
            elif block.get("type") == "tool_use":
                result["tool_calls"].append(
                    {
                        "id": block["id"],
                        "name": block["name"],
                        "input": block["input"],
                    }
                )
        return result


_client: Optional[ClaudeClient] = None


def get_claude_client() -> ClaudeClient:
    global _client
    if _client is None:
        _client = ClaudeClient()
    return _client
