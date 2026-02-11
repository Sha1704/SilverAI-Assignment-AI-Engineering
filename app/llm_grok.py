# app/llm_grok.py
from __future__ import annotations
import os
from dotenv import load_dotenv
from openai import OpenAI
from openai import PermissionDeniedError

load_dotenv()

class GrokLLM:
    def __init__(self):
        api_key = os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")
        if not api_key:
            raise RuntimeError("Missing XAI_API_KEY (or GROK_API_KEY) in .env")

        self.client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        self.model = os.getenv("GROK_MODEL", "grok-4-1-fast-reasoning")

    def generate(self, prompt: str) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Answer using the provided sources."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=2500,
            )
            return resp.choices[0].message.content or ""
        except PermissionDeniedError as e:
            # xAI returns 403 when team has no credits/licensing
            raise RuntimeError(
                "Grok API call failed (403). Your xAI team likely has no credits/licenses enabled yet. "
                "Enable billing/credits in the xAI console for this team, then retry."
            ) from e
