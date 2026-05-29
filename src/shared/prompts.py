"""Shared prompt templates for retrieval and answer generation."""

from typing import Final

DEFAULT_SYSTEM_PROMPT: Final[str] = (
    "You are the Microsoft Accelerators Finder. Ground every answer "
    "in retrieved accelerator data and cite the relevant sources."
)
QUERY_REWRITE_PROMPT_TEMPLATE: Final[str] = (
    "Rewrite the user question for hybrid search. Preserve intent, "
    "add useful Microsoft accelerator synonyms, and return only the "
    "query."
)
ANSWER_PROMPT_TEMPLATE: Final[str] = (
    "Answer the user with a short recommendation, a ranked list of "
    "accelerators, and citations to the accelerator and repository "
    "URLs."
)


def get_prompt_templates() -> dict[str, str]:
    """Return the scaffold prompt templates keyed by use case."""

    return {
        "system": DEFAULT_SYSTEM_PROMPT,
        "query_rewrite": QUERY_REWRITE_PROMPT_TEMPLATE,
        "answer": ANSWER_PROMPT_TEMPLATE,
    }
