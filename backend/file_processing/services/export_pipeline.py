"""Template-method export pipeline primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable


def _require_dependency(dependency: Any, name: str) -> Any:
    if dependency is None:
        raise RuntimeError(f"{name} dependency is not configured.")
    return dependency


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


class CsvExportPipeline(BaseExportPipeline):
    """CSV-specific pipeline strategy."""

    def __init__(
        self,
        *,
        token_generator: Callable[[], str] | None = None,
        now_provider: Callable[[], str] | None = None,
        sanitization_policy: Any = None,
        filename_policy: Any = None,
        validate_output: Callable[[Any], Any] | None = None,
        map_output: Callable[[Any], Any] | None = None,
        build_download_artifact: Callable[..., dict[str, Any]] | None = None,
        resolve_storage_dir: Callable[[str, type[Exception]], str] | None = None,
        resolve_export_token: Callable[
            [Callable[[], str] | None, type[Exception]],
            str,
        ]
        | None = None,
        build_safe_file_path: Callable[[str, str, type[Exception]], str] | None = None,
        resolve_created_at: Callable[
            [Callable[[], str] | None, type[Exception]],
            str,
        ]
        | None = None,
        error_class: type[Exception] = RuntimeError,
        open_file: Callable[..., Any] = open,
        file_id_prefix: str = "csv_",
        file_name_prefix: str = "export_",
    ) -> None:
        self._token_generator = token_generator
        self._now_provider = now_provider
        self._sanitization_policy = sanitization_policy
        self._filename_policy = filename_policy
        self._validate_output = validate_output
        self._map_output = map_output
        self._build_download_artifact = build_download_artifact
        self._resolve_storage_dir = resolve_storage_dir
        self._resolve_export_token = resolve_export_token
        self._build_safe_file_path = build_safe_file_path
        self._resolve_created_at = resolve_created_at
        self._error_class = error_class
        self._open_file = open_file
        self._file_id_prefix = file_id_prefix
        self._file_name_prefix = file_name_prefix

    def validate_output(self, output_json: Any) -> Any:
        validate_output = _require_dependency(
            self._validate_output,
            "validate_output",
        )
        return validate_output(output_json)

    def build_artifact(self, validated_output: Any) -> Any:
        map_output = _require_dependency(self._map_output, "map_output")
        build_download_artifact = _require_dependency(
            self._build_download_artifact,
            "build_download_artifact",
        )
        mapped_output = map_output(validated_output)
        return build_download_artifact(
            mapped_output,
            sanitization_policy=self._sanitization_policy,
            filename_policy=self._filename_policy,
        )

    def persist_artifact(self, artifact: Any, storage_dir: str) -> Any:
        resolve_storage_dir = _require_dependency(
            self._resolve_storage_dir,
            "resolve_storage_dir",
        )
        resolve_export_token = _require_dependency(
            self._resolve_export_token,
            "resolve_export_token",
        )
        build_safe_file_path = _require_dependency(
            self._build_safe_file_path,
            "build_safe_file_path",
        )
        resolve_created_at = _require_dependency(
            self._resolve_created_at,
            "resolve_created_at",
        )

        base_dir = resolve_storage_dir(storage_dir, self._error_class)
        token = resolve_export_token(self._token_generator, self._error_class)
        extension = "zip" if artifact["type"] == "zip" else "csv"
        file_name = f"{self._file_name_prefix}{token}.{extension}"
        file_path = build_safe_file_path(base_dir, file_name, self._error_class)

        try:
            with self._open_file(file_path, "wb") as destination:
                destination.write(artifact["content"])
        except OSError as exc:
            raise self._error_class("Failed to save generated CSV artifact.") from exc

        return {
            "file_id": f"{self._file_id_prefix}{token}",
            "file_name": file_name,
            "artifact_type": artifact["type"],
            "size_bytes": len(artifact["content"]),
            "created_at": resolve_created_at(
                self._now_provider,
                self._error_class,
            ),
        }

    def format_metadata(self, persisted_artifact: Any) -> dict[str, Any]:
        return persisted_artifact


class ExcelExportPipeline(BaseExportPipeline):
    """Excel-specific pipeline strategy."""

    def __init__(
        self,
        *,
        token_generator: Callable[[], str] | None = None,
        now_provider: Callable[[], str] | None = None,
        sanitization_policy: Any = None,
        validate_output: Callable[[Any], Any] | None = None,
        map_output: Callable[[Any], Any] | None = None,
        build_download_artifact: Callable[..., dict[str, Any]] | None = None,
        resolve_storage_dir: Callable[[str, type[Exception]], str] | None = None,
        resolve_export_token: Callable[
            [Callable[[], str] | None, type[Exception]],
            str,
        ]
        | None = None,
        build_safe_file_path: Callable[[str, str, type[Exception]], str] | None = None,
        resolve_created_at: Callable[
            [Callable[[], str] | None, type[Exception]],
            str,
        ]
        | None = None,
        error_class: type[Exception] = RuntimeError,
        open_file: Callable[..., Any] = open,
        file_id_prefix: str = "xlsx_",
        file_name_prefix: str = "export_",
        file_extension: str = "xlsx",
        artifact_type: str = "xlsx",
    ) -> None:
        self._token_generator = token_generator
        self._now_provider = now_provider
        self._sanitization_policy = sanitization_policy
        self._validate_output = validate_output
        self._map_output = map_output
        self._build_download_artifact = build_download_artifact
        self._resolve_storage_dir = resolve_storage_dir
        self._resolve_export_token = resolve_export_token
        self._build_safe_file_path = build_safe_file_path
        self._resolve_created_at = resolve_created_at
        self._error_class = error_class
        self._open_file = open_file
        self._file_id_prefix = file_id_prefix
        self._file_name_prefix = file_name_prefix
        self._file_extension = file_extension
        self._artifact_type = artifact_type

    def validate_output(self, output_json: Any) -> Any:
        validate_output = _require_dependency(
            self._validate_output,
            "validate_output",
        )
        return validate_output(output_json)

    def build_artifact(self, validated_output: Any) -> Any:
        map_output = _require_dependency(self._map_output, "map_output")
        build_download_artifact = _require_dependency(
            self._build_download_artifact,
            "build_download_artifact",
        )
        mapped_output = map_output(validated_output)
        return build_download_artifact(
            mapped_output,
            sanitization_policy=self._sanitization_policy,
        )

    def persist_artifact(self, artifact: Any, storage_dir: str) -> Any:
        resolve_storage_dir = _require_dependency(
            self._resolve_storage_dir,
            "resolve_storage_dir",
        )
        resolve_export_token = _require_dependency(
            self._resolve_export_token,
            "resolve_export_token",
        )
        build_safe_file_path = _require_dependency(
            self._build_safe_file_path,
            "build_safe_file_path",
        )
        resolve_created_at = _require_dependency(
            self._resolve_created_at,
            "resolve_created_at",
        )

        base_dir = resolve_storage_dir(storage_dir, self._error_class)
        token = resolve_export_token(self._token_generator, self._error_class)
        file_name = f"{self._file_name_prefix}{token}.{self._file_extension}"
        file_path = build_safe_file_path(base_dir, file_name, self._error_class)

        try:
            with self._open_file(file_path, "wb") as destination:
                destination.write(artifact["content"])
        except OSError as exc:
            raise self._error_class("Failed to save generated Excel artifact.") from exc

        return {
            "file_id": f"{self._file_id_prefix}{token}",
            "file_name": file_name,
            "artifact_type": self._artifact_type,
            "size_bytes": len(artifact["content"]),
            "created_at": resolve_created_at(
                self._now_provider,
                self._error_class,
            ),
        }

    def format_metadata(self, persisted_artifact: Any) -> dict[str, Any]:
        return persisted_artifact
