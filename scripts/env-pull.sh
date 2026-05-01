#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_TARGET="${ENV_FILE_PATH:-$ROOT_DIR/.env}"
INFISICAL_ENV="${1:-dev}"

if [[ "$INFISICAL_ENV" != "dev" ]]; then
  echo "Error: this script currently supports only 'dev' environment." >&2
  exit 1
fi

if ! command -v infisical >/dev/null 2>&1 && ! command -v powershell.exe >/dev/null 2>&1; then
  echo "Error: infisical CLI not found. Install it first: https://infisical.com/docs/cli/overview" >&2
  exit 1
fi

can_run_infisical_direct=0
if command -v infisical >/dev/null 2>&1 && infisical --version >/dev/null 2>&1; then
  can_run_infisical_direct=1
fi

run_infisical() {
  if [[ "$can_run_infisical_direct" -eq 1 ]]; then
    infisical "$@"
    return $?
  fi

  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command infisical "$@"
    return $?
  fi

  echo "Error: infisical command cannot be executed in this shell." >&2
  return 1
}

has_service_token=0
if [[ -n "${INFISICAL_TOKEN:-}" ]]; then
  has_service_token=1
fi

echo "Pulling Infisical secrets for env '$INFISICAL_ENV' into $ENV_TARGET"

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

project_id_arg=()
if [[ -n "${INFISICAL_PROJECT_ID:-}" ]]; then
  project_id_arg=(--projectId="$INFISICAL_PROJECT_ID")
fi

if [[ "$has_service_token" -eq 1 ]]; then
  if ! run_infisical export --format=dotenv --env="$INFISICAL_ENV" --token="$INFISICAL_TOKEN" "${project_id_arg[@]}" > "$tmp_file"; then
    echo "Error: failed to export secrets from Infisical using INFISICAL_TOKEN." >&2
    exit 1
  fi
elif ! run_infisical export --format=dotenv --env="$INFISICAL_ENV" "${project_id_arg[@]}" > "$tmp_file"; then
  echo "Error: failed to export secrets from Infisical. Run 'infisical login' and 'infisical init' in repo root, or set INFISICAL_PROJECT_ID." >&2
  exit 1
fi

if [[ ! -s "$tmp_file" ]]; then
  echo "Error: Infisical export returned empty output." >&2
  exit 1
fi

cp "$tmp_file" "$ENV_TARGET"
echo "Success: wrote secrets to $ENV_TARGET"

echo "Running schema validation against .env.example"
ENV_FILE_PATH="$ENV_TARGET" bash "$ROOT_DIR/scripts/env-sync.sh" check
