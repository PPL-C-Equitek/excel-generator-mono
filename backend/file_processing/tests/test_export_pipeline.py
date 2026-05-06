from django.test import SimpleTestCase

from file_processing.services.export_pipeline import (
    BaseExportPipeline,
    CsvExportPipeline,
    ExcelExportPipeline,
)


class RecordingExportPipeline(BaseExportPipeline):
    def __init__(self):
        self.calls = []

    def validate_output(self, output_json):
        self.calls.append(("validate_output", output_json))
        return {"validated": output_json}

    def build_artifact(self, validated_output):
        self.calls.append(("build_artifact", validated_output))
        return {"content": b"export-content", "type": "custom"}

    def persist_artifact(self, artifact, storage_dir):
        self.calls.append(("persist_artifact", artifact, storage_dir))
        return {"file_name": "export.custom", "size_bytes": len(artifact["content"])}

    def format_metadata(self, persisted_artifact):
        self.calls.append(("format_metadata", persisted_artifact))
        return {
            "file_name": persisted_artifact["file_name"],
            "size_bytes": persisted_artifact["size_bytes"],
            "artifact_type": "custom",
        }


class BaseExportPipelineTest(SimpleTestCase):
    def test_export_to_filesystem_runs_template_steps_in_order(self):
        pipeline = RecordingExportPipeline()
        output_json = {"document_info": {}, "summary": {}, "content_data": []}

        result = pipeline.export_to_filesystem(output_json, "/tmp/exports")

        self.assertEqual(
            pipeline.calls,
            [
                ("validate_output", output_json),
                ("build_artifact", {"validated": output_json}),
                (
                    "persist_artifact",
                    {"content": b"export-content", "type": "custom"},
                    "/tmp/exports",
                ),
                (
                    "format_metadata",
                    {"file_name": "export.custom", "size_bytes": 14},
                ),
            ],
        )
        self.assertEqual(
            result,
            {
                "file_name": "export.custom",
                "size_bytes": 14,
                "artifact_type": "custom",
            },
        )


class ConcreteExportPipelineContractTest(SimpleTestCase):
    def test_csv_export_pipeline_is_base_export_pipeline(self):
        pipeline = CsvExportPipeline()

        self.assertIsInstance(pipeline, BaseExportPipeline)

    def test_excel_export_pipeline_is_base_export_pipeline(self):
        pipeline = ExcelExportPipeline()

        self.assertIsInstance(pipeline, BaseExportPipeline)
