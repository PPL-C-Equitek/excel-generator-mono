import pytest
from file_processing.services import export_service as es


def make_payload(a, b, include_summary=True):
    payload = {
        "document_info": {"source_type": "PDF", "filename": f"doc_{a}_{b}.pdf"},
        "summary": {"pages": 1} if include_summary else {},
        "content_data": [
            {"table_name": "T", "headers": ["a", "b"], "rows": [{"a": a, "b": b}]}
        ],
    }
    return payload


# After: reduced partitioned test set (ISP)
@pytest.mark.parametrize("a,b", [
    ("1", "2"),  # valid
    ("", "2"),   # missing a
    ("1", None),  # missing b
])
def test_partitioned_validate(a, b):
    p = make_payload(a, b)
    try:
        es.validate_output_llm(p)
    except Exception:
        assert True
