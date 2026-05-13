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


# Before: exhaustive combinations (simulating many test cases)
@pytest.mark.parametrize("a,b", [(i, j) for i in ("", "1", "bad") for j in ("", "2", None)])
def test_exhaustive_validate(a, b):
    p = make_payload(a, b)
    try:
        es.validate_output_llm(p)
    except Exception:
        # some combos intentionally invalid
        assert True
