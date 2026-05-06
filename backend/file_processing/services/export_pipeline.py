"""Template-method export pipeline primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ExportPipelineDependencies:
    validate_output: Callable[[Any], Any] | None = None
    map_output: Callable[[Any], Any] | None = None
    build_download_artifact: Callable[..., dict[str, Any]] | None = None
    resolve_storage_dir: Callable[[str, type[Exception]], str] | None = None
    resolve_export_token: Callable[
        [Callable[[], str] | None, type[Exception]],
        str,
    ] | None = None
    build_safe_file_path: Callable[[str, str, type[Exception]], str] | None = None
    resolve_created_at: Callable[
        [Callable[[], str] | None, type[Exception]],
        str,
    ] | None = None
    error_class: type[Exception] = RuntimeError
    open_file: Callable[..., Any] = open


@dataclass(frozen=True)
class ExportRuntimeOptions:
    token_generator: Callable[[], str] | None = None
    now_provider: Callable[[], str] | None = None
    sanitization_policy: Any = None
    filename_policy: Any = None


@dataclass(frozen=True)
class ExportNamingConfig:
    file_id_prefix: str
    file_name_prefix: str = "export_"
    file_extension: str | None = None
    artifact_type: str | None = None


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


class FilesystemExportPipeline(BaseExportPipeline):
    """Shared filesystem behavior for format-specific export pipelines."""

    def __init__(
        self,
        *,
        dependencies: ExportPipelineDependencies | None = None,
        runtime_options: ExportRuntimeOptions | None = None,
        naming: ExportNamingConfig,
    ) -> None:
        self._dependencies = dependencies or ExportPipelineDependencies()
        self._runtime_options = runtime_options or ExportRuntimeOptions()
        self._naming = naming

    def validate_output(self, output_json: Any) -> Any:
        validate_output = _require_dependency(
            self._dependencies.validate_output,
            "validate_output",
        )
        return validate_output(output_json)

    def _map_output(self, validated_output: Any) -> Any:
        map_output = _require_dependency(
            self._dependencies.map_output,
            "map_output",
        )
        return map_output(validated_output)

    def _build_download_artifact(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        build_download_artifact = _require_dependency(
            self._dependencies.build_download_artifact,
            "build_download_artifact",
        )
        return build_download_artifact(*args, **kwargs)

    def _persist_artifact(
        self,
        artifact: Any,
        storage_dir: str,
        *,
        extension: str,
        artifact_type: str,
        error_message: str,
    ) -> dict[str, Any]:
        resolve_storage_dir = _require_dependency(
            self._dependencies.resolve_storage_dir,
            "resolve_storage_dir",
        )
        resolve_export_token = _require_dependency(
            self._dependencies.resolve_export_token,
            "resolve_export_token",
        )
        build_safe_file_path = _require_dependency(
            self._dependencies.build_safe_file_path,
            "build_safe_file_path",
        )
        resolve_created_at = _require_dependency(
            self._dependencies.resolve_created_at,
            "resolve_created_at",
        )

        error_class = self._dependencies.error_class
        token = resolve_export_token(
            self._runtime_options.token_generator,
            error_class,
        )
        file_name = f"{self._naming.file_name_prefix}{token}.{extension}"
        base_dir = resolve_storage_dir(storage_dir, error_class)
        file_path = build_safe_file_path(base_dir, file_name, error_class)

        try:
            with self._dependencies.open_file(file_path, "wb") as destination:
                destination.write(artifact["content"])
        except OSError as exc:
            raise error_class(error_message) from exc

        return {
            "file_id": f"{self._naming.file_id_prefix}{token}",
            "file_name": file_name,
            "artifact_type": artifact_type,
            "size_bytes": len(artifact["content"]),
            "created_at": resolve_created_at(
                self._runtime_options.now_provider,
                error_class,
            ),
        }

    def format_metadata(self, persisted_artifact: Any) -> dict[str, Any]:
        return persisted_artifact


class CsvExportPipeline(FilesystemExportPipeline):
    """CSV-specific pipeline strategy."""

    def __init__(
        self,
        *,
        dependencies: ExportPipelineDependencies | None = None,
        runtime_options: ExportRuntimeOptions | None = None,
        naming: ExportNamingConfig | None = None,
    ) -> None:
        super().__init__(
            dependencies=dependencies,
            runtime_options=runtime_options,
            naming=naming or ExportNamingConfig(file_id_prefix="csv_"),
        )

    def build_artifact(self, validated_output: Any) -> Any:
        mapped_output = self._map_output(validated_output)
        return self._build_download_artifact(
            mapped_output,
            sanitization_policy=self._runtime_options.sanitization_policy,
            filename_policy=self._runtime_options.filename_policy,
        )

    def persist_artifact(self, artifact: Any, storage_dir: str) -> Any:
        extension = "zip" if artifact["type"] == "zip" else "csv"
        return self._persist_artifact(
            artifact,
            storage_dir,
            extension=extension,
            artifact_type=artifact["type"],
            error_message="Failed to save generated CSV artifact.",
        )


class ExcelExportPipeline(FilesystemExportPipeline):
    """Excel-specific pipeline strategy."""

    def __init__(
        self,
        *,
        dependencies: ExportPipelineDependencies | None = None,
        runtime_options: ExportRuntimeOptions | None = None,
        naming: ExportNamingConfig | None = None,
    ) -> None:
        super().__init__(
            dependencies=dependencies,
            runtime_options=runtime_options,
            naming=naming
            or ExportNamingConfig(
                file_id_prefix="xlsx_",
                file_extension="xlsx",
                artifact_type="xlsx",
            ),
        )

    def build_artifact(self, validated_output: Any) -> Any:
        mapped_output = self._map_output(validated_output)
        return self._build_download_artifact(
            mapped_output,
            sanitization_policy=self._runtime_options.sanitization_policy,
        )

    def persist_artifact(self, artifact: Any, storage_dir: str) -> Any:
        return self._persist_artifact(
            artifact,
            storage_dir,
            extension=self._naming.file_extension or "xlsx",
            artifact_type=self._naming.artifact_type or "xlsx",
            error_message="Failed to save generated Excel artifact.",
        )
