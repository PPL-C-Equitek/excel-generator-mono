from __future__ import annotations

from abc import ABC, abstractmethod


class ArtifactFormatStrategy(ABC):
    format_name = ""

    @abstractmethod
    def export_storage_dir(self):
        raise NotImplementedError

    @abstractmethod
    def resolve_history_content_type(self, artifact_type):
        raise NotImplementedError

    @abstractmethod
    def export_to_filesystem(self, output_json):
        raise NotImplementedError

    @abstractmethod
    def resolve_direct_download(self, identifier):
        raise NotImplementedError


class CsvFormatStrategy(ArtifactFormatStrategy):
    format_name = "csv"

    def __init__(
        self,
        storage_dir,
        export_to_filesystem,
        resolve_direct_download,
    ):
        self._storage_dir = storage_dir
        self._export_to_filesystem = export_to_filesystem
        self._resolve_direct_download = resolve_direct_download

    def export_storage_dir(self):
        return self._storage_dir

    def resolve_history_content_type(self, artifact_type):
        if artifact_type == "zip":
            return "application/zip"
        return "text/csv"

    def export_to_filesystem(self, output_json):
        return self._export_to_filesystem(
            output_json=output_json,
            storage_dir=self.export_storage_dir(),
        )

    def resolve_direct_download(self, identifier):
        return self._resolve_direct_download(
            file_id=identifier,
            storage_dir=self.export_storage_dir(),
        )


class ExcelFormatStrategy(ArtifactFormatStrategy):
    format_name = "xlsx"

    def __init__(
        self,
        storage_dir,
        export_to_filesystem,
        resolve_direct_download,
    ):
        self._storage_dir = storage_dir
        self._export_to_filesystem = export_to_filesystem
        self._resolve_direct_download = resolve_direct_download

    def export_storage_dir(self):
        return self._storage_dir

    def resolve_history_content_type(self, artifact_type):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def export_to_filesystem(self, output_json):
        return self._export_to_filesystem(
            output_json=output_json,
            storage_dir=self.export_storage_dir(),
        )

    def resolve_direct_download(self, identifier):
        return self._resolve_direct_download(
            export_id=identifier,
            storage_dir=self.export_storage_dir(),
        )


class ArtifactFormatRegistry:
    def __init__(self, strategies):
        self._strategies = {
            strategy.format_name: strategy for strategy in strategies
        }

    def get(self, format_name):
        return self._strategies[format_name]
