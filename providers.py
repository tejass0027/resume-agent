"""Registry of supported LLM providers for resume screening.

Every provider module (claude_client, gemini_client, openai_client) exposes
the same interface - DEFAULT_MODEL and an async run_batch(...) with an
identical signature - so the UI can treat them interchangeably.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType

import claude_client
import gemini_client
import openai_client


@dataclass(frozen=True)
class Provider:
    module: ModuleType
    key_label: str
    key_help: str


PROVIDERS: dict[str, Provider] = {
    "Gemini": Provider(
        module=gemini_client,
        key_label="Google AI (Gemini) API Key",
        key_help=(
            "Used only for this session's requests. Never stored or logged. "
            "Get one free at aistudio.google.com/apikey."
        ),
    ),
    "Claude": Provider(
        module=claude_client,
        key_label="Anthropic API Key",
        key_help=(
            "Used only for this session's requests. Never stored or logged. "
            "Get one at console.anthropic.com/settings/keys."
        ),
    ),
    "ChatGPT": Provider(
        module=openai_client,
        key_label="OpenAI API Key",
        key_help=(
            "Used only for this session's requests. Never stored or logged. "
            "Get one at platform.openai.com/api-keys."
        ),
    ),
}
