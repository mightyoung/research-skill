#!/bin/bash
# Modified 2026-10-01: fixed-version transactional Python fetch; no upstream code execution.
set -euo pipefail
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fetch_paper.py" "$@"
