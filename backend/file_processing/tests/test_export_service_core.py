import os
import tempfile
import json
import pytest

from file_processing.services import export_service as es


def sample_valid_output():
    return {
        "document_info": {"source_type": "PDF", "filename": "doc.pdf"},
        "summary": {"pages": 1},
        "content_data": [
            {"table_name": "T1", "headers": ["a", "b"], "rows": [{"a": "1", "b": "2"}]}
        ],
    }


def test_validate_and_map_and_generate_csv():
    payload = sample_valid_output()
    validated = es.validate_output_llm(payload)
    assert isinstance(validated, dict)

    mapped = es.map_output_csv(validated)
    assert "sheets" in mapped and isinstance(mapped["sheets"], list)

    csv_artifact = es.generate_csv_download_artifact(mapped)
    assert csv_artifact["type"] in ("csv", "zip")


def test_export_csv_to_filesystem(tmp_path):
    payload = sample_valid_output()
    out = es.export_csv_to_filesystem(payload, storage_dir=str(tmp_path))
    assert out["file_id"].startswith("csv_")
    assert os.path.exists(os.path.join(str(tmp_path), out["file_name"]))


@pytest.mark.parametrize("bad", [None, {}, {"document_info": {}}, {"content_data": []}])
def test_validate_errors(bad):
    with pytest.raises(Exception):
        es.validate_output_llm(bad)
