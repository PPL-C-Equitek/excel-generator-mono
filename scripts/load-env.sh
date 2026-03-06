#!/bin/bash

load_env_file() {
  local env_file="${1:-$HOME/apps/.env}"

  if [ ! -f "$env_file" ]; then
    echo "Environment file not found: $env_file" >&2
    return 1
  fi

  while IFS= read -r raw_line || [ -n "$raw_line" ]; do
    line="${raw_line%$'\r'}"

    case "$line" in
      ''|\#*) continue ;;
    esac

    if [[ "$line" != *=* ]]; then
      echo "Skipping malformed .env line: $line" >&2
      continue
    fi

    key="${line%%=*}"
    value="${line#*=}"

    if [[ "$key" =~ [[:space:]] ]]; then
      echo "Skipping .env key with whitespace: $key" >&2
      continue
    fi

    if [ "${#value}" -ge 2 ]; then
      first_char="${value:0:1}"
      last_char="${value: -1}"
      if [[ ("$first_char" == "\"" && "$last_char" == "\"") || ("$first_char" == "'" && "$last_char" == "'") ]]; then
        value="${value:1:${#value}-2}"
      fi
    fi

    export "$key=$value"
  done < "$env_file"
}
