#!/bin/bash
# Modified 2026-10-01: dispatch to reviewed non-destructive standard-library implementation.
set -euo pipefail
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/init_project.py" "$@"
