from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse


class HistoryDownloadCoordinator:
    def __init__(
        self,
        resolve_history_download_artifact,
        regenerate_history_download_artifact_after_stale_cache,
        resolve_download_filename,
        get_history_download_content_type,
        history_download_internal_error_response,
        invalid_stored_output_error_types,
        generation_error_types,
        open_file,
        logger,
    ):
        self.resolve_history_download_artifact = resolve_history_download_artifact
        self.regenerate_history_download_artifact_after_stale_cache = (
            regenerate_history_download_artifact_after_stale_cache
        )
        self.resolve_download_filename = resolve_download_filename
        self.get_history_download_content_type = get_history_download_content_type
        self.history_download_internal_error_response = (
            history_download_internal_error_response
        )
        self.invalid_stored_output_error_types = invalid_stored_output_error_types
        self.generation_error_types = generation_error_types
        self.open_file = open_file
        self.logger = logger

    def handle(self, history, owner, file_format, requested_name):
        try:
            file_name, artifact_type, safe_file_path, used_cached_artifact = (
                self.resolve_history_download_artifact(
                    history=history,
                    owner=owner,
                    file_format=file_format,
                )
            )
            try:
                file_handle = self.open_file(safe_file_path, "rb")
            except OSError:
                if not used_cached_artifact:
                    raise

                self.logger.warning(
                    "History download cache artifact missing on disk; regenerating."
                )
                file_name, artifact_type, safe_file_path = (
                    self.regenerate_history_download_artifact_after_stale_cache(
                        history=history,
                        owner=owner,
                        file_format=file_format,
                    )
                )
                file_handle = self.open_file(safe_file_path, "rb")
        except self.invalid_stored_output_error_types:
            self.logger.exception("History download failed due to invalid stored output.")
            return self.history_download_internal_error_response()
        except self.generation_error_types:
            self.logger.exception("History download failed while generating artifact.")
            return self.history_download_internal_error_response()
        except Exception:
            self.logger.exception("Unexpected error while preparing history download.")
            return self.history_download_internal_error_response()

        download_name = self.resolve_download_filename(
            requested_name=requested_name,
            default_name=file_name,
            artifact_type=artifact_type,
        )

        return FileResponse(
            file_handle,
            as_attachment=True,
            filename=download_name,
            content_type=self.get_history_download_content_type(artifact_type),
        )
