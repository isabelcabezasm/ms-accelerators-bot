"""Tests for the blob snapshot ingestion client."""

from __future__ import annotations

from datetime import date
from typing import cast

import pytest
import src.ingestion.snapshot as snapshot_module
from azure.core.credentials import TokenCredential
from azure.storage.blob import BlobServiceClient
from src.ingestion.snapshot import (
    AcceleratorSnapshot,
    BlobSnapshotClient,
)


class FakeBlobClient:
    """Capture blob uploads without calling Azure."""

    def __init__(self, container: str, blob: str) -> None:
        """Store the target blob path for assertions."""

        self.container = container
        self.blob = blob
        self.url = f"https://example.blob.core.windows.net/{container}/{blob}"
        self.uploads: list[dict[str, object]] = []

    def upload_blob(
        self,
        content: str,
        *,
        overwrite: bool,
        content_settings: object,
    ) -> None:
        """Record the upload payload and blob settings."""

        self.uploads.append(
            {
                "content": content,
                "overwrite": overwrite,
                "content_type": getattr(
                    content_settings,
                    "content_type",
                    None,
                ),
            }
        )


class FakeContainerClient:
    """Track container creation calls for assertions."""

    def __init__(self) -> None:
        """Initialize the creation counter."""

        self.create_calls = 0

    def create_container(self) -> None:
        """Record a container creation request."""

        self.create_calls += 1


class FakeBlobServiceClient:
    """Provide fake container and blob clients for the tests."""

    def __init__(self) -> None:
        """Initialize the fake Azure Blob service client."""

        self.container_client = FakeContainerClient()
        self.blob_clients: dict[tuple[str, str], FakeBlobClient] = {}

    def get_container_client(self, container: str) -> FakeContainerClient:
        """Return the fake container client for the requested container."""

        assert container == "raw-snapshots"
        return self.container_client

    def get_blob_client(self, container: str, blob: str) -> FakeBlobClient:
        """Return a fake blob client keyed by container and blob."""

        key = (container, blob)
        if key not in self.blob_clients:
            self.blob_clients[key] = FakeBlobClient(container, blob)
        return self.blob_clients[key]


def test_slugify_accelerator_name_normalizes_special_characters() -> None:
    """Verify accelerator names become lowercase hyphenated slugs."""

    slug = BlobSnapshotClient.slugify_accelerator_name(
        "  Azure AI / Search! Accelerator  "
    )

    assert slug == "azure-ai-search-accelerator"


def test_save_catalog_html_uses_date_partitioned_blob_paths() -> None:
    """Verify HTML snapshots land in the expected dated blob path."""

    service_client = FakeBlobServiceClient()
    snapshot_client = BlobSnapshotClient(
        storage_account_url="https://example.blob.core.windows.net",
        credential=cast(TokenCredential, object()),
        service_client=cast(BlobServiceClient, service_client),
    )

    result = snapshot_client.save_catalog_html(
        accelerator_name="My Accelerator",
        html_content="<html>hello</html>",
        snapshot_date=date(2026, 5, 29),
    )

    assert result.container_name == "raw-snapshots"
    assert result.blob_name == "2026-05-29/my-accelerator/catalog.html"
    blob_client = service_client.blob_clients[
        (
            "raw-snapshots",
            "2026-05-29/my-accelerator/catalog.html",
        )
    ]
    assert blob_client.uploads == [
        {
            "content": "<html>hello</html>",
            "overwrite": True,
            "content_type": "text/html; charset=utf-8",
        }
    ]
    assert service_client.container_client.create_calls == 1


def test_save_accelerator_snapshot_requires_content() -> None:
    """Verify empty snapshot requests fail fast with a clear error."""

    snapshot_client = BlobSnapshotClient(
        storage_account_url="https://example.blob.core.windows.net",
        credential=cast(TokenCredential, object()),
        service_client=cast(BlobServiceClient, FakeBlobServiceClient()),
    )

    with pytest.raises(ValueError, match="At least one snapshot payload"):
        snapshot_client.save_accelerator_snapshot("Accelerator")


@pytest.mark.asyncio
async def test_save_snapshots_batch_uploads_html_and_markdown() -> None:
    """Verify batch uploads save all requested HTML and markdown files."""

    service_client = FakeBlobServiceClient()
    snapshot_client = BlobSnapshotClient(
        storage_account_url="https://example.blob.core.windows.net",
        credential=cast(TokenCredential, object()),
        service_client=cast(BlobServiceClient, service_client),
    )

    uploads = await snapshot_client.save_snapshots_batch(
        [
            AcceleratorSnapshot(
                accelerator_name="Copilot Accelerator",
                catalog_html="<html>catalog</html>",
                readme_markdown="# Copilot",
                snapshot_date=date(2026, 5, 29),
            )
        ]
    )

    uploaded_blob_names = {upload.blob_name for upload in uploads}

    assert uploaded_blob_names == {
        "2026-05-29/copilot-accelerator/catalog.html",
        "2026-05-29/copilot-accelerator/readme.md",
    }


def test_client_uses_default_credential_and_env_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the client defaults to managed identity configuration."""

    captured: dict[str, object] = {}
    fake_credential = object()

    class CapturingBlobServiceClient:
        """Capture BlobServiceClient construction arguments."""

        def __init__(self, account_url: str, credential: object) -> None:
            """Store constructor arguments for later assertions."""

            captured["account_url"] = account_url
            captured["credential"] = credential

    monkeypatch.setenv(
        "ACCELERATORS_STORAGE_ACCOUNT_URL",
        "https://managed.blob.core.windows.net",
    )
    monkeypatch.setattr(
        snapshot_module,
        "DefaultAzureCredential",
        lambda: fake_credential,
    )
    monkeypatch.setattr(
        snapshot_module,
        "BlobServiceClient",
        CapturingBlobServiceClient,
    )

    snapshot_client = BlobSnapshotClient()
    _ = snapshot_client.service_client

    assert captured == {
        "account_url": "https://managed.blob.core.windows.net",
        "credential": fake_credential,
    }
