"""
Shared configuration for all engines.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    claude_default_model: str = Field(
        default="claude-sonnet-4-20250514", alias="CLAUDE_DEFAULT_MODEL"
    )
    claude_advanced_model: str = Field(
        default="claude-opus-4-0", alias="CLAUDE_ADVANCED_MODEL"
    )

    quantum_mode: str = Field(default="local", alias="QUANTUM_MODE")
    quantum_provider: str = Field(default="local", alias="QUANTUM_PROVIDER")
    quantum_budget_usd: float = Field(default=100.0, alias="QUANTUM_BUDGET_USD")
    quantum_fallback: str = Field(
        default="simulated_annealing", alias="QUANTUM_FALLBACK"
    )

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
