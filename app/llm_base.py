from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class LLMResponse:
    text: str
    usage: Optional[Dict[str, Any]] = None   # tokens, latency, etc (optional)


class LLMClient:
    """
    Base interface for any LLM backend (Mock now, Grok later).
    Keep this stable so swapping providers is one-file change.
    """
    def generate(self, prompt: str, *, max_tokens: Optional[int] = None) -> LLMResponse:
        raise NotImplementedError("LLMClient.generate must be implemented")
