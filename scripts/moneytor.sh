#!/usr/bin/env bash
# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

# Launch the MoneyTor GUI from a desktop icon / app-grid entry.
#
# A double-clicked .desktop launcher inherits none of your shell environment,
# so this wrapper does two things the .desktop file cannot:
#   1. cd into the project root, so .env and .cache/tokens.json resolve.
#   2. use the venv's interpreter by absolute path, so nothing depends on PATH.
set -euo pipefail

# Resolve the repo root from this script's own location (survives moves/symlinks).
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

PY="$PROJECT_ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
    # Fall back to uv if the venv is missing (e.g. fresh checkout).
    exec uv run python src/main.py "$@"
fi

exec "$PY" src/main.py "$@"
