"""Blob storage snapshot helpers for ingestion crawls."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from os import getenv

from azure.core.credentials import TokenCredential
from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings


@dataclass(frozen=True, slots=True)
class AcceleratorSnapshot:
    """Represent the raw files collected for one accelerator."""

    accelerator_name: str
    catalog_html: str | None = None
    readme_markdown: str | None = None
    snapshot_date: date | None = None


@dataclass(frozen=True, slots=True)
class SnapshotBlob:
    """Describe a saved blob so callers can trace upload locations."""

    container_name: str
    blob_name: str
    url: str


class BlobSnapshotClient:
    """Persist raw crawl snapshots to Azure Blob Storage."""

    def __init__(
        self,
        storage_account_url: str | None = None,
        container_name: str = "raw-snapshots",
        credential: TokenCredential | None = None,
        service_client: BlobServiceClient | None = None,
    ) -> None:
        """Configure the blob client with managed identity defaults."""

        resolved_url = (
            storage_account_url
            or getenv("ACCELERATORS_STORAGE_ACCOUNT_URL")
        )
        if not resolved_url:
            msg = "ACCELERATORS_STORAGE_ACCOUNT_URL must be configured."
            raise ValueError(msg)

        self.storage_account_url = resolved_url
        self.container_name = container_name
        self.credential = credential or DefaultAzureCredential()
        self._service_client = service_client
        self._container_ready = False

    @property
    def service_client(self) -> BlobServiceClient:
        """Return the Azure Blob service client for this storage account."""

        if self._service_client is None:
            self._service_client = BlobServiceClient(
                account_url=self.storage_account_url,
                credential=self.credential,
            )
        return self._service_client

    def save_catalog_html(
        self,
        accelerator_name: str,
        html_content: str,
        snapshot_date: date | None = None,
    ) -> SnapshotBlob:
        """Save catalog HTML for a crawler run."""

        blob_name = self._build_blob_name(
            accelerator_name=accelerator_name,
            snapshot_date=snapshot_date,
            file_name="catalog.html",
        )
        return self._upload_text(
            blob_name=blob_name,
            content=html_content,
            content_type="text/html; charset=utf-8",
        )

    def save_readme_markdown(
        self,
        accelerator_name: str,
        markdown_content: str,
        snapshot_date: date | None = None,
    ) -> SnapshotBlob:
        """Save README markdown for one accelerator."""

        blob_name = self._build_blob_name(
            accelerator_name=accelerator_name,
            snapshot_date=snapshot_date,
            file_name="readme.md",
        )
        return self._upload_text(
            blob_name=blob_name,
            content=markdown_content,
            content_type="text/markdown; charset=utf-8",
        )

    def save_accelerator_snapshot(
        self,
        accelerator_name: str,
        catalog_html: str | None = None,
        readme_markdown: str | None = None,
        snapshot_date: date | None = None,
    ) -> list[SnapshotBlob]:
        """Save all raw snapshot files available for one accelerator."""

        uploads: list[SnapshotBlob] = []
        if catalog_html is not None:
            uploads.append(
                self.save_catalog_html(
                    accelerator_name=accelerator_name,
                    html_content=catalog_html,
                    snapshot_date=snapshot_date,
                )
            )
        if readme_markdown is not None:
            uploads.append(
                self.save_readme_markdown(
                    accelerator_name=accelerator_name,
                    markdown_content=readme_markdown,
                    snapshot_date=snapshot_date,
                )
            )
        if uploads:
            return uploads

        msg = "At least one snapshot payload must be provided."
        raise ValueError(msg)

    async def save_snapshots_batch(
        self,
        snapshots: Sequence[AcceleratorSnapshot],
    ) -> list[SnapshotBlob]:
        """Save many accelerator snapshots concurrently."""

        if not snapshots:
            return []

        tasks = [
            asyncio.to_thread(
                self.save_accelerator_snapshot,
                snapshot.accelerator_name,
                snapshot.catalog_html,
                snapshot.readme_markdown,
                snapshot.snapshot_date,
            )
            for snapshot in snapshots
        ]
        results = await asyncio.gather(*tasks)
        return [item for group in results for item in group]

    @staticmethod
    def slugify_accelerator_name(accelerator_name: str) -> str:
        """Normalize accelerator names into URL-safe storage paths."""

        normalized_name = accelerator_name.strip().lower()
        normalized_name = re.sub(r"[^a-z0-9]+", "-", normalized_name)
        normalized_name = re.sub(r"-+", "-", normalized_name)
        normalized_name = normalized_name.strip("-")
        return normalized_name or "unknown-accelerator"

    def _build_blob_name(
        self,
        accelerator_name: str,
        snapshot_date: date | None,
        file_name: str,
    ) -> str:
        """Construct a date-partitioned blob path for a snapshot file."""

        resolved_date = snapshot_date or self._current_snapshot_date()
        slug = self.slugify_accelerator_name(accelerator_name)
        return f"{resolved_date.isoformat()}/{slug}/{file_name}"

    @staticmethod
    def _current_snapshot_date() -> date:
        """Return the current UTC date for blob partitioning."""

        return datetime.now(UTC).date()

    def _ensure_container(self) -> None:
        """Create the snapshot container on first use if needed."""

        if self._container_ready:
            return

        container_client = self.service_client.get_container_client(
            self.container_name
        )
        try:
            container_client.create_container()
        except ResourceExistsError:
            pass

        self._container_ready = True

    def _upload_text(
        self,
        blob_name: str,
        content: str,
        content_type: str,
    ) -> SnapshotBlob:
        """Upload text content to Azure Blob Storage."""

        self._ensure_container()
        blob_client = self.service_client.get_blob_client(
            container=self.container_name,
            blob=blob_name,
        )
        blob_client.upload_blob(
            content,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return SnapshotBlob(
            container_name=self.container_name,
            blob_name=blob_name,
            url=blob_client.url,
        )
