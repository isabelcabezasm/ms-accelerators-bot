"""Crawler and parser for the accelerators.ms catalog."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from os import getenv
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify

from src.ingestion.models import AcceleratorMetadata, CrawlResult
from src.ingestion.snapshot import BlobSnapshotClient

LOGGER = logging.getLogger(__name__)
DEFAULT_CATALOG_URL = "https://accelerators.ms"
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_RETRY_COUNT = 3
DEFAULT_BACKOFF_SECONDS = 1.0


class CatalogSchemaError(ValueError):
    """Raised when accelerators.ms no longer matches parser expectations."""


class CatalogFetchError(RuntimeError):
    """Raised when the crawler cannot fetch accelerators.ms content."""


class AcceleratorsMsParser:
    """Parse accelerators.ms homepage and catalog bundle payloads."""

    def extract_bundle_url(self, html: str, page_url: str) -> str | None:
        """Extract the module bundle URL from the homepage HTML."""

        soup = BeautifulSoup(html, "html.parser")
        # The catalog currently ships as a client-side bundle referenced here.
        module_script = soup.select_one('script[type="module"][src]')
        if module_script is None:
            return None

        source = module_script.get("src")
        if not isinstance(source, str) or not source.strip():
            return None

        return urljoin(page_url, source)

    def parse_bundle_catalog(
        self,
        bundle_source: str,
    ) -> list[AcceleratorMetadata]:
        """Parse the embedded accelerator array from the JavaScript bundle."""

        records = self._extract_catalog_records(bundle_source)
        accelerators = [
            self._build_metadata(record) for record in records if record
        ]
        if not accelerators:
            msg = "Bundle payload did not include accelerator records."
            raise CatalogSchemaError(msg)
        return accelerators

    def parse_catalog_html(
        self,
        html: str,
        page_url: str,
    ) -> list[AcceleratorMetadata]:
        """Scrape server-rendered accelerator cards as a fallback path."""

        soup = BeautifulSoup(html, "html.parser")
        selectors = (
            ".gsa-card",
            ".featured-item",
            "[data-accelerator-card]",
            "article",
        )
        cards: list[Tag] = []
        for selector in selectors:
            cards.extend(
                tag for tag in soup.select(selector) if tag not in cards
            )

        accelerators = [
            accelerator
            for card in cards
            if (accelerator := self._parse_html_card(card, page_url))
            is not None
        ]
        if not accelerators:
            msg = "No accelerator cards were found in the catalog HTML."
            raise CatalogSchemaError(msg)
        return accelerators

    def _extract_catalog_records(
        self,
        bundle_source: str,
    ) -> list[dict[str, Any]]:
        """Locate and parse the catalog array from the bundled JavaScript."""

        anchor = bundle_source.find('accelerator:"')
        if anchor == -1:
            msg = "Bundle no longer contains accelerator records."
            raise CatalogSchemaError(msg)

        matches = list(
            re.finditer(
                r"const\s+[A-Za-z_$][\w$]*\s*=", bundle_source[:anchor]
            )
        )
        for match in reversed(matches):
            start = self._skip_whitespace(bundle_source, match.end())
            if start >= len(bundle_source) or bundle_source[start] != "[":
                continue

            parser = _JavaScriptLiteralParser(bundle_source[start:])
            try:
                value, _ = parser.parse_with_consumed()
            except CatalogSchemaError:
                continue

            if self._looks_like_catalog(value):
                return value

        msg = "Unable to locate the bundled accelerator array."
        raise CatalogSchemaError(msg)

    @staticmethod
    def _skip_whitespace(text: str, index: int) -> int:
        """Advance past inline whitespace in the bundle source."""

        while index < len(text) and text[index].isspace():
            index += 1
        return index

    @staticmethod
    def _looks_like_catalog(value: Any) -> bool:
        """Check whether a parsed value matches the catalog record schema."""

        if not isinstance(value, list) or not value:
            return False

        first_item = value[0]
        return isinstance(first_item, dict) and "accelerator" in first_item

    def _build_metadata(self, record: dict[str, Any]) -> AcceleratorMetadata:
        """Normalize one raw bundle record into the crawler output model."""

        name = self._require_string(record, "accelerator")
        url = self._require_string(record, "githubUrl")
        summary = self._clean_text(self._require_string(record, "excerpt"))
        services = self._string_list(record.get("productsAndServices"))
        foundry_template = self._optional_string(
            record.get("foundryTemplateName")
        )

        return AcceleratorMetadata(
            name=name,
            url=url,
            summary=summary,
            categories=self._build_categories(record),
            industries=self._string_list(record.get("industries")),
            azure_services=services,
            languages=self._string_list(record.get("programmingLanguages")),
            deployment=self._derive_deployment(services, foundry_template),
        )

    def _parse_html_card(
        self,
        card: Tag,
        page_url: str,
    ) -> AcceleratorMetadata | None:
        """Extract metadata from one server-rendered fallback card."""

        title_node = card.select_one("[title]") or card.find(
            ["h2", "h3", "h4"]
        )
        if title_node is None:
            return None

        name = self._clean_text(title_node.get_text(" ", strip=True))
        if not name:
            return None

        link = card.find("a", href=True)
        href = link.get("href") if link is not None else None
        if not isinstance(href, str) or not href.strip():
            return None

        excerpt_node = card.select_one(".excerpt") or card.find("p")
        excerpt_html = str(excerpt_node) if excerpt_node is not None else ""
        summary = self._clean_text(markdownify(excerpt_html))

        category_text = self._clean_text(
            self._get_node_text(card.select_one(".card-header"))
        )
        categories = [category_text] if category_text else []
        services = self._collect_chip_text(card, ".products-section span")
        languages = self._split_languages(
            self._get_node_text(card.select_one(".languages-text"))
        )

        return AcceleratorMetadata(
            name=name,
            url=urljoin(page_url, href),
            summary=summary,
            categories=categories,
            industries=[],
            azure_services=services,
            languages=languages,
            deployment=self._derive_deployment(services, None),
        )

    def _build_categories(self, record: dict[str, Any]) -> list[str]:
        """Combine source taxonomy fields into a stable category list."""

        categories = self._string_list(record.get("solutionPlays"))
        categories.extend(self._string_list(record.get("solutionAreas")))
        technical_pattern = self._optional_string(
            record.get("technicalPattern")
        )
        if technical_pattern:
            categories.append(technical_pattern)
        return self._dedupe_preserving_order(categories)

    @staticmethod
    def _derive_deployment(
        services: list[str],
        foundry_template: str | None,
    ) -> str | None:
        """Infer a deployment model from source services and template hints."""

        if foundry_template:
            return "Azure AI Foundry template"
        if (
            "Azure Container Apps" in services
            and "Azure Functions" in services
        ):
            return "Azure Container Apps + Azure Functions"
        if "Azure Container Apps" in services:
            return "Azure Container Apps"
        if "Azure App Service" in services:
            return "Azure App Service"
        if any("Fabric" in service for service in services):
            return "Microsoft Fabric"
        return None

    @staticmethod
    def _get_node_text(node: Tag | None) -> str:
        """Read visible text from an optional BeautifulSoup node."""

        return node.get_text(" ", strip=True) if node is not None else ""

    def _collect_chip_text(self, card: Tag, selector: str) -> list[str]:
        """Collect deduplicated text values from chip-like HTML elements."""

        values = [
            self._clean_text(node.get_text(" ", strip=True))
            for node in card.select(selector)
        ]
        return self._dedupe_preserving_order(
            value for value in values if value
        )

    def _string_list(self, value: Any) -> list[str]:
        """Normalize a JavaScript array into a clean Python string list."""

        if not isinstance(value, list):
            return []

        items = [
            self._clean_text(item) for item in value if isinstance(item, str)
        ]
        return self._dedupe_preserving_order(item for item in items if item)

    def _split_languages(self, value: str) -> list[str]:
        """Convert a comma-delimited language string into a list."""

        parts = [self._clean_text(item) for item in value.split(",")]
        return self._dedupe_preserving_order(item for item in parts if item)

    @staticmethod
    def _require_string(record: dict[str, Any], key: str) -> str:
        """Read a required string field and fail loudly when it is missing."""

        value = record.get(key)
        if not isinstance(value, str):
            msg = f"Catalog record is missing required string field: {key}"
            raise CatalogSchemaError(msg)
        return value

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        """Normalize optional string fields from the bundle payload."""

        if not isinstance(value, str):
            return None
        cleaned = AcceleratorsMsParser._clean_text(value)
        return cleaned or None

    @staticmethod
    def _clean_text(value: str) -> str:
        """Collapse bundle and HTML whitespace into stable text output."""

        cleaned = value.replace("\u200b", " ")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    @staticmethod
    def _dedupe_preserving_order(values: Any) -> list[str]:
        """Remove duplicates while keeping the source ordering intact."""

        seen: set[str] = set()
        results: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            results.append(value)
        return results


class AcceleratorsCatalogCrawler:
    """Fetch and parse the accelerators.ms catalog with retry handling."""

    def __init__(
        self,
        *,
        catalog_url: str = DEFAULT_CATALOG_URL,
        parser: AcceleratorsMsParser | None = None,
        client: httpx.Client | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_RETRY_COUNT,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        snapshot_client: BlobSnapshotClient | None = None,
    ) -> None:
        """Configure the crawler transport, retries, and parser hooks."""

        self.catalog_url = catalog_url
        self.parser = parser or AcceleratorsMsParser()
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.sleep = sleep
        self.snapshot_client = snapshot_client
        self._owns_client = client is None
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=timeout_seconds,
            headers={
                "User-Agent": (
                    "ms-accelerators-bot/0.1 "
                    "(+https://github.com/isabelcabezasm/ms-accelerators-bot)"
                )
            },
        )

    @classmethod
    def from_environment(cls) -> AcceleratorsCatalogCrawler:
        """Build a crawler using optional snapshot storage configuration."""

        storage_account_url = getenv("ACCELERATORS_STORAGE_ACCOUNT_URL")
        snapshot_client = None
        if storage_account_url:
            snapshot_client = BlobSnapshotClient(
                storage_account_url=storage_account_url
            )
        return cls(snapshot_client=snapshot_client)

    def crawl(self) -> CrawlResult:
        """Fetch accelerators.ms and return normalized accelerator metadata."""

        homepage_html = self._get_text(self.catalog_url)
        self._save_catalog_snapshot(homepage_html)
        bundle_url = self.parser.extract_bundle_url(
            homepage_html, self.catalog_url
        )

        accelerators: list[AcceleratorMetadata] = []
        if bundle_url:
            bundle_source = self._get_text(bundle_url)
            try:
                accelerators = self.parser.parse_bundle_catalog(bundle_source)
            except CatalogSchemaError:
                LOGGER.warning(
                    "Bundle parsing failed; falling back to HTML scraping.",
                    exc_info=True,
                )

        if not accelerators:
            accelerators = self.parser.parse_catalog_html(
                homepage_html,
                self.catalog_url,
            )

        return CrawlResult(
            source_url=self.catalog_url,
            bundle_url=bundle_url,
            accelerators=accelerators,
        )

    def close(self) -> None:
        """Close the owned HTTP client when the crawler is no longer used."""

        if self._owns_client:
            self.client.close()

    def __enter__(self) -> AcceleratorsCatalogCrawler:
        """Return the crawler as a context manager resource."""

        return self

    def __exit__(self, *_: object) -> None:
        """Close owned transport resources on context manager exit."""

        self.close()

    def _get_text(self, url: str) -> str:
        """Fetch text content with retries for transient network failures."""

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as error:
                last_error = error
                if attempt == self.max_retries or not self._is_retryable(
                    error
                ):
                    break

                delay = self.backoff_seconds * (2 ** (attempt - 1))
                LOGGER.warning(
                    "Retrying %s after attempt %s/%s failed: %s",
                    url,
                    attempt,
                    self.max_retries,
                    error,
                )
                self.sleep(delay)

        msg = f"Failed to fetch {url} after {self.max_retries} attempts."
        raise CatalogFetchError(msg) from last_error

    @staticmethod
    def _is_retryable(error: httpx.HTTPError) -> bool:
        """Identify transient HTTP errors that should trigger a retry."""

        if isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            return status_code in {408, 429} or 500 <= status_code < 600
        return isinstance(
            error,
            (
                httpx.ConnectError,
                httpx.NetworkError,
                httpx.ReadError,
                httpx.TimeoutException,
                httpx.RemoteProtocolError,
            ),
        )

    def _save_catalog_snapshot(self, homepage_html: str) -> None:
        """Persist the homepage HTML snapshot when storage is configured."""

        if self.snapshot_client is None:
            return

        try:
            self.snapshot_client.save_catalog_html(
                accelerator_name="accelerators-ms-catalog",
                html_content=homepage_html,
            )
        except Exception:  # pragma: no cover - defensive telemetry path.
            LOGGER.warning(
                "Failed to persist accelerators.ms HTML snapshot.",
                exc_info=True,
            )


@dataclass(slots=True)
class _JavaScriptLiteralParser:
    """Parse the limited JavaScript literal syntax used by the catalog."""

    source: str
    index: int = 0

    def parse_with_consumed(self) -> tuple[Any, int]:
        """Parse one JavaScript literal and report how much text was used."""

        value = self._parse_value()
        self._skip_whitespace()
        return value, self.index

    def _parse_value(self) -> Any:
        """Dispatch to the correct parser for the next JavaScript token."""

        self._skip_whitespace()
        if self.index >= len(self.source):
            raise CatalogSchemaError("Unexpected end of JavaScript payload.")

        current = self.source[self.index]
        if current == "{":
            return self._parse_object()
        if current == "[":
            return self._parse_array()
        if current in {'"', "'"}:
            return self._parse_string(current)
        if current == "`":
            return self._parse_template_string()
        if current == "!":
            return self._parse_bang_literal()
        if current.isdigit() or current == "-":
            return self._parse_number()
        return self._parse_identifier_value()

    def _parse_object(self) -> dict[str, Any]:
        """Parse a JavaScript object literal with identifier keys."""

        result: dict[str, Any] = {}
        self.index += 1
        while True:
            self._skip_whitespace()
            if self._peek("}"):
                self.index += 1
                return result

            key = self._parse_key()
            self._skip_whitespace()
            self._expect(":")
            result[key] = self._parse_value()
            self._skip_whitespace()
            if self._peek(","):
                self.index += 1
                continue
            if self._peek("}"):
                self.index += 1
                return result
            raise CatalogSchemaError("Malformed object literal in bundle.")

    def _parse_array(self) -> list[Any]:
        """Parse a JavaScript array literal."""

        result: list[Any] = []
        self.index += 1
        while True:
            self._skip_whitespace()
            if self._peek("]"):
                self.index += 1
                return result

            result.append(self._parse_value())
            self._skip_whitespace()
            if self._peek(","):
                self.index += 1
                continue
            if self._peek("]"):
                self.index += 1
                return result
            raise CatalogSchemaError("Malformed array literal in bundle.")

    def _parse_key(self) -> str:
        """Parse one object key from the JavaScript payload."""

        self._skip_whitespace()
        current = self.source[self.index]
        if current in {'"', "'"}:
            return self._parse_string(current)

        start = self.index
        while self.index < len(self.source):
            current = self.source[self.index]
            if current.isalnum() or current in {"_", "$"}:
                self.index += 1
                continue
            break

        if start == self.index:
            raise CatalogSchemaError("Expected an object key in bundle.")
        return self.source[start : self.index]

    def _parse_string(self, quote: str) -> str:
        """Parse a quoted JavaScript string with escape handling."""

        escapes = {
            "\\": "\\",
            '"': '"',
            "'": "'",
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "b": "\b",
            "f": "\f",
            "/": "/",
        }
        self.index += 1
        characters: list[str] = []
        while self.index < len(self.source):
            current = self.source[self.index]
            if current == quote:
                self.index += 1
                return "".join(characters)
            if current == "\\":
                self.index += 1
                if self.index >= len(self.source):
                    break
                escaped = self.source[self.index]
                if escaped == "u":
                    code_point = self.source[self.index + 1 : self.index + 5]
                    if len(code_point) != 4:
                        raise CatalogSchemaError("Invalid unicode escape.")
                    characters.append(chr(int(code_point, 16)))
                    self.index += 5
                    continue
                characters.append(escapes.get(escaped, escaped))
                self.index += 1
                continue
            characters.append(current)
            self.index += 1
        raise CatalogSchemaError("Unterminated string literal in bundle.")

    def _parse_template_string(self) -> str:
        """Parse the backtick strings used for multiline use-case text."""

        self.index += 1
        characters: list[str] = []
        while self.index < len(self.source):
            current = self.source[self.index]
            if current == "`":
                self.index += 1
                return "".join(characters)
            if current == "\\":
                self.index += 1
                if self.index >= len(self.source):
                    break
                characters.append(self.source[self.index])
                self.index += 1
                continue
            if current == "$" and self._peek("${", offset=0):
                msg = (
                    "Template interpolation is not supported in catalog data."
                )
                raise CatalogSchemaError(msg)
            characters.append(current)
            self.index += 1
        raise CatalogSchemaError("Unterminated template string in bundle.")

    def _parse_bang_literal(self) -> bool:
        """Parse minified boolean expressions like !0 and !1."""

        self._expect("!")
        if self._peek("0"):
            self.index += 1
            return True
        if self._peek("1"):
            self.index += 1
            return False
        raise CatalogSchemaError("Unexpected bang literal in bundle.")

    def _parse_number(self) -> int | float:
        """Parse integer and floating-point numbers from the payload."""

        start = self.index
        while self.index < len(self.source):
            current = self.source[self.index]
            if current.isdigit() or current in {"-", ".", "e", "E", "+"}:
                self.index += 1
                continue
            break
        raw_number = self.source[start : self.index]
        return (
            float(raw_number)
            if any(ch in raw_number for ch in ".eE")
            else int(raw_number)
        )

    def _parse_identifier_value(self) -> Any:
        """Parse identifier-like literals such as null and true."""

        start = self.index
        while self.index < len(self.source):
            current = self.source[self.index]
            if current.isalnum() or current in {"_", "$"}:
                self.index += 1
                continue
            break

        identifier = self.source[start : self.index]
        if identifier == "true":
            return True
        if identifier == "false":
            return False
        if identifier in {"null", "undefined"}:
            return None
        if identifier:
            return identifier
        raise CatalogSchemaError("Unexpected token in bundle payload.")

    def _skip_whitespace(self) -> None:
        """Skip insignificant whitespace between JavaScript tokens."""

        while (
            self.index < len(self.source) and self.source[self.index].isspace()
        ):
            self.index += 1

    def _expect(self, token: str) -> None:
        """Require the next token and advance the cursor."""

        if not self._peek(token):
            msg = f"Expected {token!r} at position {self.index}."
            raise CatalogSchemaError(msg)
        self.index += len(token)

    def _peek(self, token: str, *, offset: int = 0) -> bool:
        """Check whether the next characters match the expected token."""

        start = self.index + offset
        return self.source.startswith(token, start)
