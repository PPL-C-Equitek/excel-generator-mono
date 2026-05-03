#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_TEMPLATE="${ENV_TEMPLATE_PATH:-$ROOT_DIR/.env.example}"
ENV_FILE="${ENV_FILE_PATH:-$ROOT_DIR/.env}"

if [[ ! -f "$ENV_TEMPLATE" ]]; then
  echo "Error: template file not found: $ENV_TEMPLATE" >&2
  exit 1
fi

declare -a template_keys=()
declare -a template_malformed=()
declare -a env_keys=()
declare -a env_malformed=()
declare -A template_seen=()
declare -A env_seen=()
declare -A template_values=()

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

parse_env_file() {
  local file="$1"
  local kind="$2"
  local line_no=0

  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    line_no=$((line_no + 1))
    local line="${raw_line%$'\r'}"

    if [[ "$line" =~ ^[[:space:]]*$ ]] || [[ "$line" =~ ^[[:space:]]*# ]]; then
      continue
    fi

    if [[ "$line" != *=* ]]; then
      if [[ "$kind" == "template" ]]; then
        template_malformed+=("line $line_no: $line")
      else
        env_malformed+=("line $line_no: $line")
      fi
      continue
    fi

    local key_part="${line%%=*}"
    local value_part="${line#*=}"
    local key
    key="$(trim "$key_part")"

    if [[ -z "$key" ]] || [[ "$key" =~ [[:space:]] ]] || [[ ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      if [[ "$kind" == "template" ]]; then
        template_malformed+=("line $line_no: $line")
      else
        env_malformed+=("line $line_no: $line")
      fi
      continue
    fi

    if [[ "$kind" == "template" ]]; then
      if [[ -z "${template_seen[$key]+x}" ]]; then
        template_keys+=("$key")
      fi
      template_seen["$key"]=1
      template_values["$key"]="$value_part"
    else
      if [[ -z "${env_seen[$key]+x}" ]]; then
        env_keys+=("$key")
      fi
      env_seen["$key"]=1
    fi
  done < "$file"
}

run_sync() {
  parse_env_file "$ENV_TEMPLATE" template

  if [[ -f "$ENV_FILE" ]]; then
    parse_env_file "$ENV_FILE" env
  fi

  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$ENV_TEMPLATE" "$ENV_FILE"
    echo "Created .env from .env.example"
    return 0
  fi

  local added=0
  for key in "${template_keys[@]}"; do
    if [[ -z "${env_seen[$key]+x}" ]]; then
      printf '\n%s=%s\n' "$key" "${template_values[$key]}" >> "$ENV_FILE"
      added=$((added + 1))
    fi
  done

  if [[ $added -eq 0 ]]; then
    echo "Sync complete: no missing keys added."
  else
    echo "Sync complete: added $added missing key(s)."
  fi
}

run_check() {
  parse_env_file "$ENV_TEMPLATE" template

  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Check failed: .env not found. Run 'make env-sync' first." >&2
    exit 1
  fi

  parse_env_file "$ENV_FILE" env

  if [[ ${#template_malformed[@]} -gt 0 ]]; then
    echo "Check failed: malformed lines in .env.example" >&2
    for item in "${template_malformed[@]}"; do
      echo "  - $item" >&2
    done
    exit 1
  fi

  if [[ ${#env_malformed[@]} -gt 0 ]]; then
    echo "Check failed: malformed lines in .env" >&2
    for item in "${env_malformed[@]}"; do
      echo "  - $item" >&2
    done
    exit 1
  fi

  local -a missing=()
  for key in "${template_keys[@]}"; do
    if [[ -z "${env_seen[$key]+x}" ]]; then
      missing+=("$key")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Check failed: missing required key(s) in .env:" >&2
    for key in "${missing[@]}"; do
      echo "  - $key" >&2
    done
    exit 1
  fi

  echo "Check passed: .env includes all keys from .env.example"
}

run_doctor() {
  parse_env_file "$ENV_TEMPLATE" template

  if [[ -f "$ENV_FILE" ]]; then
    parse_env_file "$ENV_FILE" env
  fi

  local -a missing=()
  local -a extra=()

  for key in "${template_keys[@]}"; do
    if [[ -z "${env_seen[$key]+x}" ]]; then
      missing+=("$key")
    fi
  done

  for key in "${env_keys[@]}"; do
    if [[ -z "${template_seen[$key]+x}" ]]; then
      extra+=("$key")
    fi
  done

  echo "Env Doctor Report"
  echo "-----------------"
  echo "Template keys: ${#template_keys[@]}"
  echo "Env keys: ${#env_keys[@]}"

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Missing keys (${#missing[@]}):"
    for key in "${missing[@]}"; do
      echo "  - $key"
    done
  else
    echo "Missing keys: none"
  fi

  if [[ ${#extra[@]} -gt 0 ]]; then
    echo "Extra keys (${#extra[@]}):"
    for key in "${extra[@]}"; do
      echo "  - $key"
    done
  else
    echo "Extra keys: none"
  fi

  if [[ ${#template_malformed[@]} -gt 0 ]]; then
    echo "Malformed lines in .env.example:"
    for item in "${template_malformed[@]}"; do
      echo "  - $item"
    done
  else
    echo "Malformed lines in .env.example: none"
  fi

  if [[ ${#env_malformed[@]} -gt 0 ]]; then
    echo "Malformed lines in .env:"
    for item in "${env_malformed[@]}"; do
      echo "  - $item"
    done
  else
    echo "Malformed lines in .env: none"
  fi
}

mode="${1:-}"
case "$mode" in
  sync) run_sync ;;
  check) run_check ;;
  doctor) run_doctor ;;
  *)
    echo "Usage: bash scripts/env-sync.sh sync|check|doctor" >&2
    exit 1
    ;;
esac
