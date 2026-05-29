"""Shared Azure client factories and placeholders."""

from typing import Any


class AzureClients:
    """Store Azure SDK client placeholders for future wiring."""

    def __init__(self) -> None:
        """Initialize the placeholder client container."""

        self.search: Any | None = None
        self.openai: Any | None = None
        self.cosmos: Any | None = None


def create_azure_clients() -> AzureClients:
    """Return placeholder Azure clients until service wiring is added."""

    return AzureClients()
