"""Normalize, chunk, embed, and upsert accelerator documents."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

import tiktoken
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.ingestion.search_client import AcceleratorSearchClient
from src.shared.models import AcceleratorChunk, AcceleratorDocument

EMBEDDING_DEPLOYMENT_NAME = "text-embedding-3-large"
EMBEDDING_BATCH_SIZE = 16
TOKEN_ENCODING_NAME = "cl100k_base"


class PipelineResult(BaseModel):
    """Summarize a pipeline run for logging and monitoring."""

    normalized_documents: int = Field(ge=0)
    changed_documents: int = Field(ge=0)
    skipped_documents: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    embedded_chunks: int = Field(ge=0)
    upserted_chunks: int = Field(ge=0)


class PipelineSettings(BaseSettings):
    """Load Azure OpenAI settings for the ingestion pipeline."""

    model_config = SettingsConfigDict(
        env_prefix="ACCELERATORS_",
        extra="ignore",
    )

    openai_endpoint: str | None = Field(default=None)
    openai_api_version: str = Field(default="2024-10-21")
    openai_embedding_deployment: str = Field(
        default=EMBEDDING_DEPLOYMENT_NAME
    )


class IngestionPipeline:
    """Coordinate normalization, chunking, embedding, and upserts."""

    def __init__(
        self,
        *,
        search_client: AcceleratorSearchClient | None = None,
        openai_client: AzureOpenAI | Any | None = None,
        settings: PipelineSettings | None = None,
    ) -> None:
        """Create the pipeline with injectable Azure dependencies."""

        self._settings = settings or PipelineSettings()
        self._search_client = search_client or AcceleratorSearchClient()
        self._openai_client = openai_client or self._create_openai_client()
        self._encoding = tiktoken.get_encoding(TOKEN_ENCODING_NAME)

    def normalize(
        self,
        raw_data: Mapping[str, Any] | object,
    ) -> AcceleratorDocument:
        """Normalize crawler output into the shared accelerator schema."""

        return normalize(raw_data)

    def chunk(
        self,
        document: AcceleratorDocument,
        *,
        max_tokens: int = 500,
        overlap: int = 50,
    ) -> list[AcceleratorChunk]:
        """Split a normalized document into overlapping token chunks."""

        return chunk(
            document,
            max_tokens=max_tokens,
            overlap=overlap,
            encoding=self._encoding,
        )

    def embed(
        self,
        chunks: Sequence[AcceleratorChunk],
    ) -> list[AcceleratorChunk]:
        """Generate Azure OpenAI embeddings for the provided chunks."""

        if not chunks:
            return []

        embedded_chunks: list[AcceleratorChunk] = []
        for batch in _batch_chunks(chunks, EMBEDDING_BATCH_SIZE):
            response = self._openai_client.embeddings.create(
                model=self._settings.openai_embedding_deployment,
                input=[chunk_item.content for chunk_item in batch],
            )
            for chunk_item, embedding in zip(
                batch,
                response.data,
                strict=True,
            ):
                embedded_chunks.append(
                    chunk_item.model_copy(
                        update={
                            "content_vector": list(embedding.embedding),
                        }
                    )
                )
        return embedded_chunks

    def upsert(self, chunks: Sequence[AcceleratorChunk]) -> None:
        """Ensure the Search index exists and upsert embedded chunks."""

        if not chunks:
            return

        self._search_client.ensure_index()
        self._search_client.upsert_chunks(chunks)

    def run(
        self,
        accelerators: Sequence[Mapping[str, Any] | object],
    ) -> PipelineResult:
        """Run the full normalize-to-search pipeline for many inputs."""

        normalized_documents = [self.normalize(item) for item in accelerators]
        self._search_client.ensure_index()
        change_result = self._search_client.detect_changes(
            normalized_documents
        )

        changed_chunks: list[AcceleratorChunk] = []
        for document in change_result.changed_documents:
            changed_chunks.extend(self.chunk(document))

        embedded_chunks = self.embed(changed_chunks)
        if embedded_chunks:
            self._search_client.upsert_chunks(embedded_chunks)

        return PipelineResult(
            normalized_documents=len(normalized_documents),
            changed_documents=len(change_result.changed_documents),
            skipped_documents=change_result.skipped_documents,
            chunk_count=len(changed_chunks),
            embedded_chunks=len(embedded_chunks),
            upserted_chunks=len(embedded_chunks),
        )

    def _create_openai_client(self) -> AzureOpenAI:
        """Create an Azure OpenAI client using managed identity."""

        if self._settings.openai_endpoint is None:
            message = "ACCELERATORS_OPENAI_ENDPOINT must be configured."
            raise ValueError(message)

        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential,
            "https://cognitiveservices.azure.com/.default",
        )
        return AzureOpenAI(
            azure_endpoint=self._settings.openai_endpoint,
            api_version=self._settings.openai_api_version,
            azure_ad_token_provider=token_provider,
        )



def normalize(raw_data: Mapping[str, Any] | object) -> AcceleratorDocument:
    """Normalize raw crawler output into the PRD document schema."""

    name = _normalize_text(
        _get_first_value(raw_data, ("name", "title"), default="")
    )
    identifier = _normalize_identifier(
        _get_first_value(raw_data, ("id", "slug"), default=""),
        name=name,
    )
    document = AcceleratorDocument(
        id=identifier,
        name=name,
        url=str(_get_first_value(raw_data, ("url", "accelerator_url"))),
        github_url=_optional_string(
            _get_first_value(raw_data, ("github_url", "repo_url"))
        ),
        summary=_normalize_text(
            _get_first_value(
                raw_data,
                ("summary", "short_description", "description"),
                default="",
            )
        ),
        long_description=_normalize_long_text(
            _get_first_value(
                raw_data,
                ("long_description", "readme", "content", "body"),
                default="",
            )
        ),
        categories=_normalize_list(
            _get_first_value(raw_data, ("categories",), default=[])
        ),
        industries=_normalize_list(
            _get_first_value(raw_data, ("industries",), default=[])
        ),
        azure_services=_normalize_list(
            _get_first_value(raw_data, ("azure_services",), default=[])
        ),
        languages=_normalize_list(
            _get_first_value(raw_data, ("languages",), default=[])
        ),
        deployment=_normalize_list(
            _get_first_value(raw_data, ("deployment",), default=[])
        ),
        last_updated=_get_first_value(
            raw_data,
            ("last_updated", "updated_at"),
            default=None,
        ),
        stars=_normalize_int(
            _get_first_value(
                raw_data,
                ("stars", "stargazers_count"),
                default=0,
            )
        ),
    )
    content_hash = _compute_content_hash(document)
    return document.model_copy(update={"content_hash": content_hash})



def chunk(
    document: AcceleratorDocument,
    *,
    max_tokens: int = 500,
    overlap: int = 50,
    encoding: tiktoken.Encoding | None = None,
) -> list[AcceleratorChunk]:
    """Split a document into overlapping chunks using token counts."""

    if max_tokens <= 0:
        raise ValueError("max_tokens must be greater than zero.")
    if overlap < 0:
        raise ValueError("overlap must be zero or greater.")
    if overlap >= max_tokens:
        raise ValueError("overlap must be smaller than max_tokens.")

    tokenizer = encoding or tiktoken.get_encoding(TOKEN_ENCODING_NAME)
    source_text = (
        document.long_description or document.summary or document.name
    )
    segments = _split_into_segments(source_text, max_tokens, tokenizer)
    chunk_texts = _assemble_chunks(
        segments,
        max_tokens=max_tokens,
        overlap=overlap,
        encoding=tokenizer,
    )
    if not chunk_texts:
        chunk_texts = [document.name]

    chunks: list[AcceleratorChunk] = []
    for chunk_index, chunk_text in enumerate(chunk_texts):
        chunk_id = _build_chunk_id(document.id, chunk_index)
        chunks.append(
            AcceleratorChunk(
                chunk_id=chunk_id,
                parent_id=document.id,
                chunk_index=chunk_index,
                name=document.name,
                summary=document.summary,
                content=chunk_text,
                url=document.url,
                github_url=document.github_url,
                categories=document.categories,
                industries=document.industries,
                azure_services=document.azure_services,
                languages=document.languages,
                deployment=document.deployment,
                last_updated=document.last_updated,
                stars=document.stars,
                content_hash=document.content_hash,
            )
        )
    return chunks



def _get_first_value(
    raw_data: Mapping[str, Any] | object,
    field_names: Sequence[str],
    *,
    default: Any = None,
) -> Any:
    """Return the first matching attribute or key from raw crawler output."""

    for field_name in field_names:
        if isinstance(raw_data, Mapping) and field_name in raw_data:
            return raw_data[field_name]
        if hasattr(raw_data, field_name):
            return getattr(raw_data, field_name)
    return default



def _normalize_identifier(raw_identifier: Any, *, name: str) -> str:
    """Return a stable accelerator identifier with a slug fallback."""

    if isinstance(raw_identifier, str) and raw_identifier.strip():
        return raw_identifier.strip()

    slug_source = name or "accelerator"
    slug = re.sub(r"[^a-z0-9]+", "-", slug_source.lower()).strip("-")
    return f"accelerator-{slug or 'item'}"



def _optional_string(value: Any) -> str | None:
    """Return a stripped string or ``None`` for blank values."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None



def _normalize_text(value: Any) -> str:
    """Collapse noisy whitespace in short text fields."""

    text = str(value or "")
    return " ".join(text.split())



def _normalize_long_text(value: Any) -> str:
    """Normalize README content while preserving paragraph boundaries."""

    text = str(value or "")
    paragraphs = re.split(r"\n\s*\n", text)
    cleaned_paragraphs = [
        " ".join(paragraph.split())
        for paragraph in paragraphs
        if paragraph.strip()
    ]
    return "\n\n".join(cleaned_paragraphs)



def _normalize_list(value: Any) -> list[str]:
    """Normalize list-like metadata into de-duplicated string values."""

    if value is None:
        return []

    raw_items: list[Any]
    if isinstance(value, str):
        raw_items = re.split(r"[,;\n]", value)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        raw_items = list(value)
    else:
        raw_items = [value]

    normalized_items: list[str] = []
    for item in raw_items:
        normalized_item = _normalize_text(item)
        if normalized_item and normalized_item not in normalized_items:
            normalized_items.append(normalized_item)
    return normalized_items



def _normalize_int(value: Any) -> int:
    """Convert numeric metadata to an integer with a safe default."""

    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0



def _compute_content_hash(document: AcceleratorDocument) -> str:
    """Hash the normalized document payload for change detection."""

    payload = document.model_dump(mode="json", exclude={"content_hash"})
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()



def _split_into_segments(
    text: str,
    max_tokens: int,
    encoding: tiktoken.Encoding,
) -> list[str]:
    """Split text on paragraphs first, then sentences, then tokens."""

    if not text.strip():
        return []

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]
    segments: list[str] = []
    for paragraph in paragraphs:
        if _token_count(paragraph, encoding) <= max_tokens:
            segments.append(paragraph)
            continue
        segments.extend(
            _split_large_paragraph(paragraph, max_tokens, encoding)
        )
    return segments



def _split_large_paragraph(
    paragraph: str,
    max_tokens: int,
    encoding: tiktoken.Encoding,
) -> list[str]:
    """Split oversized paragraphs into sentence-aware subsegments."""

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph)
        if sentence.strip()
    ]
    if not sentences:
        return _split_by_tokens(paragraph, max_tokens, encoding)

    segments: list[str] = []
    current_sentences: list[str] = []
    for sentence in sentences:
        if _token_count(sentence, encoding) > max_tokens:
            if current_sentences:
                segments.append(" ".join(current_sentences))
                current_sentences = []
            segments.extend(_split_by_tokens(sentence, max_tokens, encoding))
            continue

        candidate_sentences = current_sentences + [sentence]
        candidate_text = " ".join(candidate_sentences)
        if (
            current_sentences
            and _token_count(candidate_text, encoding) > max_tokens
        ):
            segments.append(" ".join(current_sentences))
            current_sentences = [sentence]
            continue
        current_sentences = candidate_sentences

    if current_sentences:
        segments.append(" ".join(current_sentences))
    return segments



def _split_by_tokens(
    text: str,
    max_tokens: int,
    encoding: tiktoken.Encoding,
) -> list[str]:
    """Split very large text spans into fixed token windows."""

    tokens = encoding.encode(text)
    return [
        encoding.decode(tokens[index : index + max_tokens]).strip()
        for index in range(0, len(tokens), max_tokens)
        if encoding.decode(tokens[index : index + max_tokens]).strip()
    ]



def _assemble_chunks(
    segments: Sequence[str],
    *,
    max_tokens: int,
    overlap: int,
    encoding: tiktoken.Encoding,
) -> list[str]:
    """Pack segments into overlapping chunks bounded by token counts."""

    if not segments:
        return []

    chunk_texts: list[str] = []
    current_segments: list[str] = []
    for segment in segments:
        candidate_segments = current_segments + [segment]
        candidate_text = _join_segments(candidate_segments)
        if (
            current_segments
            and _token_count(candidate_text, encoding) > max_tokens
        ):
            finalized_chunk = _join_segments(current_segments)
            chunk_texts.append(finalized_chunk)
            overlap_text = _build_overlap_text(
                finalized_chunk,
                overlap,
                encoding,
            )
            current_segments = _seed_next_chunk(
                overlap_text,
                segment,
                max_tokens=max_tokens,
                encoding=encoding,
            )
            continue
        current_segments = candidate_segments

    if current_segments:
        chunk_texts.append(_join_segments(current_segments))
    return chunk_texts



def _join_segments(segments: Sequence[str]) -> str:
    """Join segments while preserving paragraph-style spacing."""

    return "\n\n".join(segment for segment in segments if segment.strip())



def _build_overlap_text(
    chunk_text: str,
    overlap: int,
    encoding: tiktoken.Encoding,
) -> str:
    """Return the trailing token overlap to prepend to the next chunk."""

    if overlap == 0:
        return ""
    tokens = encoding.encode(chunk_text)
    return encoding.decode(tokens[-overlap:])



def _seed_next_chunk(
    overlap_text: str,
    segment: str,
    *,
    max_tokens: int,
    encoding: tiktoken.Encoding,
) -> list[str]:
    """Fit overlap text plus the next segment within the chunk budget."""

    if not overlap_text:
        return [segment]

    overlap_tokens = encoding.encode(overlap_text)
    segment_tokens = encoding.encode(segment)
    separator_tokens = encoding.encode("\n\n")
    available_tokens = max(
        max_tokens - len(segment_tokens) - len(separator_tokens),
        0,
    )
    if available_tokens == 0:
        return [segment]

    seeded_tokens = (
        overlap_tokens[-available_tokens:]
        + separator_tokens
        + segment_tokens
    )
    return [encoding.decode(seeded_tokens)]



def _token_count(text: str, encoding: tiktoken.Encoding) -> int:
    """Return the token count for the provided text span."""

    return len(encoding.encode(text))



def _build_chunk_id(parent_id: str, chunk_index: int) -> str:
    """Build a deterministic chunk identifier from parent and position."""

    digest = hashlib.sha256(
        f"{parent_id}:{chunk_index}".encode()
    ).hexdigest()
    return f"chunk-{digest}"



def _batch_chunks(
    chunks: Sequence[AcceleratorChunk],
    batch_size: int,
) -> list[list[AcceleratorChunk]]:
    """Split chunk sequences into Azure OpenAI embedding batches."""

    return [
        list(chunks[index : index + batch_size])
        for index in range(0, len(chunks), batch_size)
    ]
