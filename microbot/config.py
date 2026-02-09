"""Configuration management for microbot.

Supports JSON config file (~/.microbot/config.json) with environment variable overrides.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".microbot"
CONFIG_FILE = CONFIG_DIR / "config.json"
DB_FILE = CONFIG_DIR / "memory.db"
SESSIONS_DIR = CONFIG_DIR / "sessions"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    """LLM provider settings."""
    provider: str = "openai"              # openai | anthropic
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class Config:
    """Top-level application configuration."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    system_prompt: str = ""
    max_history: int = 50
    tools_enabled: bool = True
    stream: bool = True
    color_theme: str = "monokai"

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    @classmethod
    def load(cls) -> "Config":
        """Load config from file then overlay environment variables."""
        config = cls()

        # --- JSON file ---------------------------------------------------
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, encoding="utf-8") as fh:
                    data = json.load(fh)
                if "llm" in data:
                    for k, v in data["llm"].items():
                        if hasattr(config.llm, k):
                            setattr(config.llm, k, v)
                for key in ("system_prompt", "max_history", "tools_enabled", "stream", "color_theme"):
                    if key in data:
                        setattr(config, key, data[key])
            except (json.JSONDecodeError, KeyError):
                pass  # Silently ignore malformed config

        # --- Environment overrides ---------------------------------------
        if os.getenv("OPENAI_API_KEY"):
            config.llm.api_key = os.getenv("OPENAI_API_KEY")
            if not config.llm.provider:
                config.llm.provider = "openai"

        if os.getenv("ANTHROPIC_API_KEY"):
            config.llm.api_key = os.getenv("ANTHROPIC_API_KEY")
            if not os.getenv("OPENAI_API_KEY"):
                config.llm.provider = "anthropic"
                if config.llm.model.startswith("gpt"):
                    config.llm.model = "claude-sonnet-4-20250514"

        env_map = {
            "MICROBOT_MODEL": "model",
            "MICROBOT_BASE_URL": "base_url",
            "MICROBOT_PROVIDER": "provider",
        }
        for env_key, attr in env_map.items():
            val = os.getenv(env_key)
            if val:
                setattr(config.llm, attr, val)

        if os.getenv("MICROBOT_TEMPERATURE"):
            try:
                config.llm.temperature = float(os.getenv("MICROBOT_TEMPERATURE"))
            except ValueError:
                pass

        return config

    def save(self) -> None:
        """Persist config to JSON file."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def ensure_dirs(self) -> None:
        """Create required directories."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    def validate(self) -> list[str]:
        """Return list of validation warnings (empty = OK)."""
        warnings: list[str] = []
        if not self.llm.api_key:
            warnings.append(
                "No API key configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY, "
                "or add it to ~/.microbot/config.json"
            )
        if self.llm.provider not in ("openai", "anthropic"):
            warnings.append(f"Unknown provider '{self.llm.provider}', expected 'openai' or 'anthropic'")
        return warnings
