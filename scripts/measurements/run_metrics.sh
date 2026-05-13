#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

echo "Installing dev requirements (backend/requirements-dev.txt)"
python3 -m pip install -r "$BACKEND_DIR/requirements-dev.txt"

echo "Running radon cyclomatic complexity on export_service.py"
radon cc "$BACKEND_DIR/file_processing/services/export_service.py" -s

echo "Running pytest for core tests (coverage)"
pytest -q "$BACKEND_DIR/file_processing/tests/test_export_service_core.py" --maxfail=1 --disable-warnings -q --cov=backend/file_processing/services --cov-report=term

echo "Running ISP BEFORE (exhaustive) tests"
pytest -q "$BACKEND_DIR/file_processing/tests/test_export_service_isp_before.py" -q

echo "Running ISP AFTER (partitioned) tests"
pytest -q "$BACKEND_DIR/file_processing/tests/test_export_service_isp_after.py" -q

echo "Running mutation testing with mutmut (may take time)"
pushd "$BACKEND_DIR" >/dev/null
mutmut --paths-to-mutate file_processing/services/export_service.py run
mutmut results
popd >/dev/null

echo "Done"
