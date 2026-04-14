from django.http import FileResponse
from django.utils._os import safe_join


class BaseDirectDownloadHandler:
    def __init__(
        self,
        strategy,
        resolve_download_filename,
        open_file,
    ):
        self.strategy = strategy
        self.resolve_download_filename = resolve_download_filename
        self.open_file = open_file

    def resolve_artifact(self, requested_id):
        return self.strategy.resolve_direct_download(requested_id)

    def build_response(self, artifact, requested_name):
        safe_file_path = safe_join(
            self.strategy.export_storage_dir(),
            artifact["file_name"],
        )
        file_handle = self.open_file(safe_file_path, "rb")
        download_name = self.resolve_download_filename(
            requested_name=requested_name,
            default_name=artifact["file_name"],
            artifact_type=artifact["artifact_type"],
        )

        return FileResponse(
            file_handle,
            as_attachment=True,
            filename=download_name,
            content_type=artifact["content_type"],
        )


class CsvDirectDownloadHandler(BaseDirectDownloadHandler):
    pass


class ExcelDirectDownloadHandler(BaseDirectDownloadHandler):
    pass
