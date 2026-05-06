"""Template-method export pipeline primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseExportPipeline(ABC):
    """Run common export steps while deferring format-specific behavior."""

    def export_to_filesystem(
        self,
        output_json: Any,
        storage_dir: str,
    ) -> dict[str, Any]:
        validated_output = self.validate_output(output_json)
        artifact = self.build_artifact(validated_output)
        persisted_artifact = self.persist_artifact(artifact, storage_dir)
        return self.format_metadata(persisted_artifact)

    @abstractmethod
    def validate_output(self, output_json: Any) -> Any:
        """Validate and return exportable output."""

    @abstractmethod
    def build_artifact(self, validated_output: Any) -> Any:
        """Build an in-memory artifact from validated output."""

    @abstractmethod
    def persist_artifact(self, artifact: Any, storage_dir: str) -> Any:
        """Persist an artifact under storage_dir."""

    @abstractmethod
    def format_metadata(self, persisted_artifact: Any) -> dict[str, Any]:
        """Return public metadata for a persisted artifact."""
