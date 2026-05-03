#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_TARGET="${ENV_FILE_PATH:-$ROOT_DIR/.env}"

ENV_FILE_PATH="$ENV_TARGET" bash "$ROOT_DIR/scripts/env-pull.sh" dev
