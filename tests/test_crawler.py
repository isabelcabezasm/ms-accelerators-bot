"""Tests for the accelerators.ms crawler and parser."""

from __future__ import annotations

from pathlib import Path

import httpx
from src.ingestion.crawler import (
    AcceleratorsCatalogCrawler,
    AcceleratorsMsParser,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    """Load a text fixture used by the crawler unit tests."""

    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_extract_bundle_url_from_homepage_snapshot() -> None:
    """Verify the homepage snapshot still exposes a module bundle URL."""

    parser = AcceleratorsMsParser()
    homepage_html = _read_fixture("accelerators_ms_homepage.html")

    bundle_url = parser.extract_bundle_url(
        homepage_html,
        "https://accelerators.ms",
    )

    assert bundle_url is not None
    assert bundle_url.startswith("https://accelerators.ms/assets/index-")
    assert bundle_url.endswith(".js")


def test_parse_bundle_catalog_returns_structured_metadata() -> None:
    """Verify the bundle parser extracts normalized accelerator metadata."""

    parser = AcceleratorsMsParser()
    bundle_source = _read_fixture("accelerators_ms_bundle_sample.js")

    accelerators = parser.parse_bundle_catalog(bundle_source)

    assert [item.name for item in accelerators] == [
        "Chat with your data",
        "Code modernization",
    ]
    assert accelerators[0].categories == [
        "Innovate with AI apps & agents",
        "Cloud & AI Platforms",
        "Chat with your data",
    ]
    assert accelerators[0].industries == ["Retail", "Healthcare"]
    assert accelerators[0].azure_services == [
        "Azure AI Search",
        "Azure Functions",
        "Azure Container Apps",
    ]
    assert accelerators[0].languages == ["Bicep", "TypeScript", "Python"]
    assert (
        accelerators[0].deployment == "Azure Container Apps + Azure Functions"
    )
    assert accelerators[1].deployment == "Azure AI Foundry template"


def test_parse_catalog_html_scrapes_server_rendered_cards() -> None:
    """Verify the HTML fallback scraper handles rendered accelerator cards."""

    parser = AcceleratorsMsParser()
    html = """
    <section>
      <article class="gsa-card">
        <div class="card-header">AI Agents</div>
        <h3>Supply chain assistant</h3>
        <p class="excerpt">
          <strong>Automate</strong> supply chain reasoning workflows.
        </p>
        <div class="products-section">
          <span>Azure AI Search</span>
          <span>Azure Container Apps</span>
        </div>
        <div class="languages-text">Python, TypeScript</div>
        <a href="https://example.com/accelerator">View</a>
      </article>
    </section>
    """

    accelerators = parser.parse_catalog_html(html, "https://accelerators.ms")

    assert len(accelerators) == 1
    assert accelerators[0].name == "Supply chain assistant"
    assert accelerators[0].categories == ["AI Agents"]
    assert (
        accelerators[0].summary
        == "**Automate** supply chain reasoning workflows."
    )
    assert accelerators[0].azure_services == [
        "Azure AI Search",
        "Azure Container Apps",
    ]
    assert accelerators[0].languages == ["Python", "TypeScript"]
    assert accelerators[0].deployment == "Azure Container Apps"


def test_crawler_retries_transient_network_errors() -> None:
    """Verify transient fetch failures are retried before the crawl fails."""

    homepage_attempts = 0
    bundle_source = _read_fixture("accelerators_ms_bundle_sample.js")
    sleep_calls: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Return mock responses for homepage and bundle requests."""

        nonlocal homepage_attempts
        if request.url.path == "/":
            homepage_attempts += 1
            if homepage_attempts == 1:
                raise httpx.ConnectError("temporary outage", request=request)
            return httpx.Response(
                200,
                text=(
                    '<html><script type="module" '
                    'src="/assets/index-sample.js"></script></html>'
                ),
                request=request,
            )

        return httpx.Response(200, text=bundle_source, request=request)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    )

    with AcceleratorsCatalogCrawler(
        client=client,
        sleep=sleep_calls.append,
    ) as crawler:
        result = crawler.crawl()

    assert homepage_attempts == 2
    assert sleep_calls == [1.0]
    assert len(result.accelerators) == 2
