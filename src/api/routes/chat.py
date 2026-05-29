"""Chat route implementing the authenticated RAG flow."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.auth import get_current_user
from src.api.models import ChatRequest, ChatResponse, UserClaims
from src.api.rag import (
    AnswerGenerator,
    HybridRetriever,
    QueryRewriter,
    RAGError,
)

LOGGER = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@lru_cache(maxsize=1)
def get_query_rewriter() -> QueryRewriter:
    """Returns a cached query rewriter dependency."""

    return QueryRewriter()


@lru_cache(maxsize=1)
def get_hybrid_retriever() -> HybridRetriever:
    """Returns a cached retriever dependency."""

    return HybridRetriever()


@lru_cache(maxsize=1)
def get_answer_generator() -> AnswerGenerator:
    """Returns a cached answer generator dependency."""

    return AnswerGenerator()


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def post_chat(
    request: ChatRequest,
    current_user: Annotated[UserClaims, Depends(get_current_user)],
    query_rewriter: Annotated[QueryRewriter, Depends(get_query_rewriter)],
    retriever: Annotated[HybridRetriever, Depends(get_hybrid_retriever)],
    generator: Annotated[AnswerGenerator, Depends(get_answer_generator)],
) -> ChatResponse:
    """Runs query rewrite, hybrid search, and answer generation."""

    conversation_id = request.conversation_id or str(uuid4())
    LOGGER.info(
        "Processing chat request for user %s with conversation %s",
        current_user.sub,
        conversation_id,
    )

    try:
        rewritten_query = query_rewriter.rewrite_query(request.message)
        accelerators = retriever.retrieve(rewritten_query)
        generated_answer = generator.generate_answer(
            message=request.message,
            rewritten_query=rewritten_query,
            accelerators=accelerators,
        )
    except RAGError as exc:
        LOGGER.exception(
            "Chat RAG flow failed for user %s and conversation %s",
            current_user.sub,
            conversation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Chat service unavailable.",
        ) from exc

    LOGGER.info(
        "Completed chat request for user %s with %d citations",
        current_user.sub,
        len(generated_answer.citations),
    )
    return ChatResponse(
        answer=generated_answer.answer,
        citations=generated_answer.citations,
        conversation_id=conversation_id,
    )
