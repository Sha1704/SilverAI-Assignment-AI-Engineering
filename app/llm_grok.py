# app/llm_grok.py
from __future__ import annotations

import os

from openai import OpenAI
from openai import PermissionDeniedError, APIError, RateLimitError

from llm_base import LLMClient

# Optional dotenv support
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


class GrokLLM(LLMClient):
    """
    xAI Grok via OpenAI-compatible client.
    Requires: XAI_API_KEY (or GROK_API_KEY)
    Optional: GROK_MODEL, GROK_MAX_TOKENS
    """
    def __init__(self):
        api_key = os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")
        if not api_key:
            raise RuntimeError("Missing XAI_API_KEY (or GROK_API_KEY) in environment")

        self.client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        self.model = os.getenv("GROK_MODEL", "grok-4-1-fast-reasoning")
        self.max_tokens = int(os.getenv("GROK_MAX_TOKENS", "4000"))

    def generate(self, prompt: str) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Answer using the provided sources. Cite pages like (PDF p. 3)."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=self.max_tokens,
            )
            return (resp.choices[0].message.content or "").strip()

        except PermissionDeniedError as e:
            raise RuntimeError(
                "Grok API call failed (403 PermissionDenied). "
                "Check that your xAI account/team has API access and billing/credits enabled."
            ) from e

        except RateLimitError as e:
            raise RuntimeError(
                "Grok API rate-limited. Slow down requests or raise your limits/plan."
            ) from e

        except APIError as e:
            raise RuntimeError(
                f"Grok API error: {e}"
            ) from e
