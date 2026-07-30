"""
Prompt Builder — Phase 2.6

Manages prompt templates stored in backend/prompts/.

Each question type maps to a template file:
    factual        -> rag_answer.txt
    analytical     -> rag_answer.txt
    summarization  -> summarize.txt
    comparative    -> compare.txt

Templates use Python str.format() placeholders:
    {question}   — the user's question
    {context}    — the citation-numbered context block
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Template directory
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Question type → template file mapping
_TEMPLATE_MAP = {
    "factual": "rag_answer.txt",
    "analytical": "rag_answer.txt",
    "summarization": "summarize.txt",
    "comparative": "compare.txt",
}

# Fallback template (if file doesn't exist)
_FALLBACK_TEMPLATE = """You are a financial research analyst. Answer the question using ONLY the provided context.

RULES:
1. Only use the provided context. Never use prior knowledge.
2. Cite sources using [1], [2], etc.
3. If the context is insufficient, say so.

QUESTION:
{question}

CONTEXT:
{context}

Answer with citations."""


def _load_template(filename: str) -> str:
    """Load a prompt template file."""
    path = _PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning("Template '%s' not found, using fallback", filename)
    return _FALLBACK_TEMPLATE


def build_prompt(
    question: str,
    context_text: str,
    question_type: str = "factual",
) -> dict:
    """Build the LLM prompt from a template.

    Parameters
    ----------
    question : str
        The user's question.
    context_text : str
        The citation-numbered context block from context_builder.
    question_type : str
        Question classification (factual / analytical / summarization / comparative).

    Returns
    -------
    dict
        {
            "system": "You are a financial research analyst...",
            "user": "Based on the context, answer...",
            "template_used": "rag_answer.txt",
        }
    """
    template_file = _TEMPLATE_MAP.get(question_type, "rag_answer.txt")
    template = _load_template(template_file)

    # Fill the template
    filled = template.format(
        question=question,
        context=context_text,
    )

    # Split into system + user for chat API
    # The template IS the system prompt; the user message is minimal
    return {
        "system": filled,
        "user": f"Answer the question based on the context above.",
        "template_used": template_file,
    }
