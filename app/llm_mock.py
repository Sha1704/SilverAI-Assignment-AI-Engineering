from __future__ import annotations
import textwrap
import random
import re

class MockLLM:
    """
    Generates handbook-like filler long enough to test orchestration.
    NOT for final quality—just to reach 20k+ words reliably.
    """
    def __init__(self, seed: int = 42):
        random.seed(seed)

    def _words(self, s: str) -> int:
        return len(re.findall(r"\b\w+\b", s))

    def generate(self, prompt: str) -> str:
        teaser = prompt.strip().replace("\n", " ")[:260]

        # If outline prompt, return a real outline
        if "Return ONLY a numbered outline" in prompt:
            headings = [
                "Introduction and Goals",
                "Core Concepts and Terminology",
                "System Architecture Overview",
                "Data Ingestion and Parsing",
                "Chunking Strategy",
                "Embeddings and Vector Storage",
                "Retrieval Strategies",
                "Knowledge Graph Augmentation",
                "Prompting and Context Packing",
                "Evaluation and Metrics",
                "Deployment and Operations",
                "Security, Privacy, and Compliance",
                "Troubleshooting and Failure Modes",
                "Case Studies and Examples",
                "Future Directions",
                "Appendix",
            ]
            return "\n".join([f"{i+1}. {h}" for i, h in enumerate(headings)])

        # If summary prompt, return bullets
        if prompt.strip().lower().startswith("summarize"):
            bullets = [
                f"- Key point {i+1}: {teaser} (mock summary)."
                for i in range(8)
            ]
            return "\n".join(bullets)

        # Otherwise: section content — aim ~1500–2000 words
        paras = []
        while True:
            p = (
                f"Based on: {teaser}. This paragraph expands definitions, gives practical examples, "
                f"explains tradeoffs, and includes implementation considerations. "
                f"It is intentionally verbose to test long-form orchestration."
            )
            paras.append(textwrap.fill(p, width=100))

            # add a little variety
            if len(paras) % 5 == 0:
                paras.append("### Practical checklist (mock)\n- Step A\n- Step B\n- Step C\n")
            if len(paras) % 7 == 0:
                paras.append("### Common pitfalls (mock)\n- Pitfall 1\n- Pitfall 2\n- Pitfall 3\n")

            text = "\n\n".join(paras)
            if self._words(text) >= 1600:
                return text
