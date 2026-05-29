"""Query rewriting support for the chat RAG pipeline."""

from __future__ import annotations

import logging
from typing import Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from .exceptions import RAGError
from .settings import RagSettings, get_rag_settings

LOGGER = logging.getLogger(__name__)
OPENAI_SCOPE = "https://cognitiveservices.azure.com/.default"
REWRITE_SYSTEM_PROMPT = (
    "You rewrite user questions into concise Azure AI Search queries. "
    "Preserve proper nouns, product names, and domain-specific wording. "
    "Return only the rewritten query text without extra commentary."
)


def build_azure_openai_client(settings: RagSettings) -> AzureOpenAI:
    """Builds an Azure OpenAI client using managed identity."""

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, OPENAI_SCOPE)
    return AzureOpenAI(
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.require_openai_endpoint(),
        azure_ad_token_provider=token_provider,
    )


def extract_message_content(response: Any) -> str:
    """Extracts a text payload from an Azure OpenAI chat response."""

    choices = getattr(response, "choices", [])
    if not choices:
        return ""

    message = getattr(choices[0], "message", None)
    if message is None:
        return ""

    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if text:
                parts.append(text)
        return "\n".join(parts)

    return ""


class QueryRewriter:
    """Rewrites incoming questions into search-optimized queries."""

    def __init__(
        self,
        *,
        settings: RagSettings | None = None,
        openai_client: AzureOpenAI | Any | None = None,
    ) -> None:
        """Initializes the rewriter with settings and an OpenAI client."""

        self._settings = settings or get_rag_settings()
        self._openai_client = openai_client or build_azure_openai_client(
            self._settings
        )

    def rewrite_query(self, message: str) -> str:
        """Returns a condensed search query for the supplied message."""

        try:
            response = self._openai_client.chat.completions.create(
                model=self._settings.require_chat_deployment(),
                messages=[
                    {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
                    {"role": "user", "content": message},
                ],
                temperature=0,
                max_tokens=self._settings.rewrite_max_tokens,
            )
        except Exception as exc:
            LOGGER.exception("Failed to rewrite chat query.")
            raise RAGError("Unable to rewrite query.") from exc

        rewritten_query = extract_message_content(response).strip()
        return rewritten_query or message
