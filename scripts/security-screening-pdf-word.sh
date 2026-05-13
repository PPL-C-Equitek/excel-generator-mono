#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
UPLOAD_URL="${BASE_URL%/}/upload/"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

print_line() {
  printf '%s\n' "$1"
}

json_value() {
  local json_file="$1"
  local key="$2"
  python3 - "$json_file" "$key" <<'PY'
import json
import sys

path = sys.argv[1]
key = sys.argv[2]

try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    print("")
    raise SystemExit(0)

value = data.get(key, "")
print(value if isinstance(value, str) else str(value))
PY
}

run_case() {
  local case_name="$1"
  local file_path="$2"
  local expected_status="$3"
  local expected_substring="$4"

  local response_file
  response_file="${TMP_DIR}/response.json"

  local http_code
  if ! http_code="$(curl -sS -o "$response_file" -w "%{http_code}" -F "file=@${file_path}" "$UPLOAD_URL")"; then
    print_line "[FAIL] ${case_name}: gagal terhubung ke ${UPLOAD_URL}"
    return 1
  fi

  local status message
  status="$(json_value "$response_file" "status")"
  message="$(json_value "$response_file" "message")"

  local ok=0
  if [[ "$status" == "$expected_status" ]] && [[ "$message" == *"$expected_substring"* ]]; then
    ok=1
  fi

  if [[ "$ok" -eq 1 ]]; then
    print_line "[PASS] ${case_name} | HTTP ${http_code} | status=${status} | message=${message}"
    return 0
  fi

  print_line "[FAIL] ${case_name} | HTTP ${http_code} | status=${status} | message=${message}"
  print_line "       expected status=${expected_status}, message contains='${expected_substring}'"
  return 1
}

print_line "== Security Screening PDF/Word =="
print_line "Target endpoint: ${UPLOAD_URL}"

python3 - "$TMP_DIR" <<'PY'
import io
import os
import zipfile

tmp = os.sys.argv[1]
ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# 1) DOCX mime spoof (plaintext with .docx extension)
with open(os.path.join(tmp, "spoofed.docx"), "wb") as f:
    f.write(b"not a zip payload")

# 2) Encrypted-like OOXML in OLE container
with open(os.path.join(tmp, "encrypted.docx"), "wb") as f:
    f.write(ole + b"EncryptedPackage" + b"padding")

# 3) Corrupt PDF
with open(os.path.join(tmp, "broken.pdf"), "wb") as f:
    f.write(b"%PDF-1.4\nthis is not a valid pdf")

# 4) Legacy DOC with page-break markers > max page limit
with open(os.path.join(tmp, "too-many-pages.doc"), "wb") as f:
    f.write(ole + b"WordDocument" + (b"\x0c" * 101))

# 5) Minimal valid DOCX baseline
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as zf:
    zf.writestr(
        "[Content_Types].xml",
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
    )
    zf.writestr(
        "word/document.xml",
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>hello</w:t></w:r></w:p></w:body></w:document>',
    )
    zf.writestr(
        "docProps/app.xml",
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Pages>2</Pages></Properties>',
    )

with open(os.path.join(tmp, "valid.docx"), "wb") as f:
    f.write(buf.getvalue())
PY

failures=0

run_case "DOCX mime spoof" "${TMP_DIR}/spoofed.docx" "error" "does not match" || failures=$((failures + 1))
run_case "Encrypted OOXML wrapper" "${TMP_DIR}/encrypted.docx" "error" "password-protected" || failures=$((failures + 1))
run_case "Corrupt PDF" "${TMP_DIR}/broken.pdf" "error" "corrupt" || failures=$((failures + 1))
run_case "Legacy DOC page-limit bypass" "${TMP_DIR}/too-many-pages.doc" "error" "maximum allowed page count" || failures=$((failures + 1))
run_case "Valid DOCX baseline" "${TMP_DIR}/valid.docx" "success" "uploaded" || failures=$((failures + 1))

print_line ""
if [[ "$failures" -gt 0 ]]; then
  print_line "Screening selesai dengan ${failures} kegagalan."
  exit 1
fi

print_line "Screening selesai: semua skenario lolos sesuai ekspektasi keamanan."