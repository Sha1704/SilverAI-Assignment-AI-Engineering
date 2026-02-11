# app/handbook.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional
import re

from llm_base import LLMClient
from retrieve import retrieve_context


def as_text(resp) -> str:
    return getattr(resp, "text", resp)


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def clean_heading(s: str) -> str:
    s = re.sub(r"[^\w\s\-:]", "", s).strip()
    return s[:120] if s else "Section"


def get_pages_from_hit(hit: dict) -> List[int]:
    pages = hit.get("pages")
    if pages is None:
        pages = (hit.get("metadata") or {}).get("pages")
    if not pages:
        return []
    out: List[int] = []
    for p in pages:
        try:
            out.append(int(p))
        except Exception:
            pass
    return out


@dataclass
class HandbookResult:
    title: str
    outline: List[str]
    markdown: str
    words: int


def generate_outline(llm: LLMClient, topic: str) -> List[str]:
    prompt = f"""
You are creating a detailed handbook outline.

Topic: {topic}

Return ONLY a numbered outline with 12-18 sections, each as a short heading.
Example:
1. Introduction
2. Key Concepts
3. ...
"""
    text = as_text(llm.generate(prompt))

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    outline: List[str] = []

    for ln in lines:
        # accept "1. X", "1) X", "1 - X", "1: X"
        m = re.match(r"^\s*\d+\s*[\).\-\:]\s*(.+)$", ln)
        if m:
            outline.append(clean_heading(m.group(1)))

    if len(outline) < 8:
        outline = [
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
    return outline


def generate_handbook_markdown(
    llm: LLMClient,
    topic: str,
    document_id: Optional[str],
    target_words: int = 20000,
    top_k_context: int = 8,
    progress_cb: Optional[Callable[[str, float], None]] = None,
) -> HandbookResult:
    outline = generate_outline(llm, topic)

    title = f"{topic} — Handbook"
    md_parts: List[str] = [f"# {title}\n"]

    # Table of Contents
    md_parts.append("## Table of Contents\n")
    for i, h in enumerate(outline, start=1):
        anchor = re.sub(r"[^a-z0-9\- ]", "", h.lower()).replace(" ", "-")
        md_parts.append(f"{i}. [{h}](#{anchor})")
    md_parts.append("\n---\n")

    memory = ""
    total_words = word_count("\n\n".join(md_parts))

    for idx, heading in enumerate(outline, start=1):
        if progress_cb:
            progress_cb(
                f"Retrieving context for: {heading}",
                (idx - 1) / max(len(outline), 1),
            )

        context_hits = []
        if document_id:
            context_hits = retrieve_context(
                f"{topic} — {heading}",
                top_k=top_k_context,
                document_id=document_id,
            )

        allowed_pages = sorted({p for h in context_hits for p in get_pages_from_hit(h)})

        context_block = ""
        if context_hits:
            blocks: List[str] = []
            for h in context_hits:
                pages = get_pages_from_hit(h)
                sim = float(h.get("similarity", 0.0) or 0.0)
                content = h.get("content", "") or ""
                blocks.append(f"[pages={pages} sim={sim:.3f}]\n{content}".strip())
            context_block = "\n\n---\n\n".join(blocks)

        prompt = f"""
You are writing a structured handbook.

Topic: {topic}
Current section: {heading}

You MUST:
- Write in Markdown
- Include subsections (###) and bullet lists where useful
- Be detailed, practical, and explanatory
- Ground content in the provided sources when available

Citation rules:
- Cite ONLY from these pages: {allowed_pages}
- Use the format (PDF p. X)
- If sources do not support a claim, say so clearly.

Continuity notes from previous sections:
{memory[:2000]}

Source excerpts:
{context_block[:12000]}

Now write this section:
- Start with "## {heading}"
- Aim for 1200-1800 words (if possible)
"""

        if progress_cb:
            progress_cb(
                f"Generating section: {heading}",
                (idx - 0.5) / max(len(outline), 1),
            )

        section_md = as_text(llm.generate(prompt)).strip()
        if not section_md.startswith("## "):
            section_md = f"## {heading}\n\n" + section_md

        md_parts.append(section_md)
        total_words = word_count("\n\n".join(md_parts))

        # Rolling memory summary
        memory_prompt = f"""
Summarize the key points from the latest section in 6-10 bullet points, concise.

Section text:
{section_md[:12000]}
"""
        memory = as_text(llm.generate(memory_prompt)).strip()

        if progress_cb:
            progress_cb(f"Progress: {total_words} words", idx / max(len(outline), 1))

        if total_words >= target_words:
            break

    # Conclusion once
    if progress_cb:
        progress_cb("Generating final conclusion…", 1.0)

    conclusion_prompt = f"""
Write a final conclusion section in Markdown.

Topic: {topic}

Requirements:
- Start with "## Conclusion"
- Summarize the key takeaways
- Provide a short checklist of next steps
- Add a brief glossary of 8-12 terms
- End with a complete final sentence (no cutoff)
"""
    conclusion_md = as_text(llm.generate(conclusion_prompt)).strip()
    if not conclusion_md.startswith("## "):
        conclusion_md = "## Conclusion\n\n" + conclusion_md
    md_parts.append(conclusion_md)

    final_md = "\n\n".join(md_parts)
    return HandbookResult(
        title=title,
        outline=outline,
        markdown=final_md,
        words=word_count(final_md),
    )
