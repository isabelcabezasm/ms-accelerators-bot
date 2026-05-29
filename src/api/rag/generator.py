"""Answer generation support for the chat RAG pipeline."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from src.api.models.chat import Citation

from .exceptions import RAGError
from .query_rewriter import build_azure_openai_client, extract_message_content
from .retriever import RetrievedAccelerator, RetrievedChunk
from .settings import RagSettings, get_rag_settings

LOGGER = logging.getLogger(__name__)
ANSWER_SYSTEM_PROMPT = (
    "You answer questions about Microsoft accelerators using only the "
    "retrieved sources. Cite every factual claim with citation ids like "
    "[1]. If the sources are insufficient, say so clearly. Return valid "
    'JSON with keys "answer" and "citations".'
)


@dataclass(slots=True)
class GeneratedAnswer:
    """Represents a model-generated answer and the citations it used."""

    answer: str
    citations: list[Citation]


class AnswerGenerator:
    """Generates a grounded answer from grouped retrieval results."""

    def __init__(
        self,
        *,
        settings: RagSettings | None = None,
        openai_client: Any | None = None,
    ) -> None:
        """Initializes the answer generator with Azure OpenAI access."""

        self._settings = settings or get_rag_settings()
        self._openai_client = openai_client or build_azure_openai_client(
            self._settings
        )

    def generate_answer(
        self,
        *,
        message: str,
        rewritten_query: str,
        accelerators: list[RetrievedAccelerator],
    ) -> GeneratedAnswer:
        """Builds a cited answer from the retrieved accelerator chunks."""

        if not accelerators:
            return GeneratedAnswer(
                answer=(
                    "I could not find relevant accelerator content for that "
                    "question."
                ),
                citations=[],
            )

        prompt = self._build_user_prompt(
            message=message,
            rewritten_query=rewritten_query,
            accelerators=accelerators,
        )

        try:
            response = self._openai_client.chat.completions.create(
                model=self._settings.require_chat_deployment(),
                messages=[
                    {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=self._settings.answer_max_tokens,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            LOGGER.exception("Failed to generate a cited chat answer.")
            raise RAGError("Unable to generate a chat response.") from exc

        raw_content = extract_message_content(response)
        payload = self._parse_payload(raw_content)
        answer = str(payload.get("answer") or "").strip()
        if not answer:
            raise RAGError("Chat response did not contain an answer.")

        citation_ids = payload.get("citations", [])
        citations = self._resolve_citations(citation_ids, accelerators)
        return GeneratedAnswer(answer=answer, citations=citations)

    def _build_user_prompt(
        self,
        *,
        message: str,
        rewritten_query: str,
        accelerators: list[RetrievedAccelerator],
    ) -> str:
        """Formats grouped retrieval results into model context."""

        sections: list[str] = [
            f"Original question: {message}",
            f"Search query: {rewritten_query}",
            "Retrieved sources:",
        ]
        for accelerator in accelerators:
            sections.append(
                f"Accelerator: {accelerator.accelerator_name}\n"
                f"URL: {accelerator.url}\n"
                f"Summary: {accelerator.summary}"
            )
            for chunk in accelerator.chunks:
                sections.append(
                    f"[{chunk.citation_id}] {chunk.excerpt.strip()}"
                )

        sections.append(
            "Return JSON like "
            '{"answer": "...", "citations": [1, 2]}. '
        )
        return "\n\n".join(sections)

    def _parse_payload(self, raw_content: str) -> dict[str, Any]:
        """Parses the JSON payload returned by the chat completion."""

        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            LOGGER.exception("Chat completion did not return valid JSON.")
            raise RAGError("Chat response was not valid JSON.") from exc

        if not isinstance(payload, dict):
            raise RAGError("Chat response payload must be a JSON object.")
        return payload

    def _resolve_citations(
        self,
        citation_ids: Any,
        accelerators: list[RetrievedAccelerator],
    ) -> list[Citation]:
        """Maps model-selected citation ids to API citation models."""

        selected_ids = self._normalize_citation_ids(citation_ids)
        citation_index = {
            chunk.citation_id: chunk
            for chunk in self._iter_chunks(accelerators)
        }
        return [
            self._build_citation(citation_index[citation_id])
            for citation_id in selected_ids
            if citation_id in citation_index
        ]

    def _normalize_citation_ids(self, citation_ids: Any) -> list[int]:
        """Normalizes citation ids from JSON into unique integers."""

        if not isinstance(citation_ids, list):
            return []

        normalized_ids: list[int] = []
        for value in citation_ids:
            try:
                citation_id = int(value)
            except (TypeError, ValueError):
                continue
            if citation_id not in normalized_ids:
                normalized_ids.append(citation_id)
        return normalized_ids

    def _iter_chunks(
        self, accelerators: list[RetrievedAccelerator]
    ) -> Iterable[RetrievedChunk]:
        """Yields every retrieved chunk in grouped order."""

        for accelerator in accelerators:
            yield from accelerator.chunks

    def _build_citation(self, chunk: RetrievedChunk) -> Citation:
        """Builds an API citation model from a retrieved chunk."""

        return Citation(
            id=chunk.citation_id,
            accelerator_id=chunk.accelerator_id,
            accelerator_name=chunk.accelerator_name,
            chunk_id=chunk.chunk_id,
            url=chunk.url,
            excerpt=chunk.excerpt,
        )
