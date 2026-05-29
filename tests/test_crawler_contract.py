"""Live contract tests for the accelerators.ms source catalog."""

from __future__ import annotations

import pytest
from src.ingestion.crawler import AcceleratorsCatalogCrawler


@pytest.mark.contract
def test_accelerators_ms_contract_has_expected_shape() -> None:
    """Fail loudly if accelerators.ms changes its published catalog shape."""

    with AcceleratorsCatalogCrawler() as crawler:
        result = crawler.crawl()

    assert result.bundle_url is not None, (
        "accelerators.ms no longer exposes a module bundle URL on the home "
        "page."
    )
    assert len(result.accelerators) >= 10, (
        "accelerators.ms returned fewer accelerators than expected."
    )
    assert all(item.name for item in result.accelerators), (
        "Catalog contains an accelerator without a name."
    )
    assert all(item.summary for item in result.accelerators), (
        "Catalog contains an accelerator without a summary."
    )
    assert all(item.categories for item in result.accelerators), (
        "Catalog contains an accelerator without categories."
    )
    assert all(item.azure_services for item in result.accelerators), (
        "Catalog contains an accelerator without services metadata."
    )
    assert all(item.languages for item in result.accelerators), (
        "Catalog contains an accelerator without language metadata."
    )
