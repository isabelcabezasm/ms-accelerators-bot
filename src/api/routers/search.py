"""Search route for hybrid Azure AI Search queries."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import get_search_service
from src.api.models import SearchResponse
from src.api.rate_limit import enforce_rate_limit
from src.api.search_service import SearchService, SearchServiceError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search"])


@router.get(
    "/search",
    response_model=SearchResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
def search(
    q: Annotated[
        str,
        Query(
            min_length=1,
            description="Search query string.",
        ),
    ],
    search_service: Annotated[
        SearchService,
        Depends(get_search_service),
    ],
    top: Annotated[
        int,
        Query(
            ge=1,
            le=20,
            description="Maximum number of ranked results to return.",
        ),
    ] = 5,
) -> SearchResponse:
    """Return ranked hybrid search results for the provided query."""

    normalized_query = q.strip()
    if not normalized_query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query must not be empty.",
        )

    try:
        results = search_service.search(normalized_query, top)
    except SearchServiceError as error:
        logger.exception("Search endpoint failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Search service is unavailable.",
        ) from error

    return SearchResponse(query=normalized_query, top=top, results=results)
