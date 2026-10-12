#!/usr/bin/env bash
set -euo pipefail
exec python3 -u "$(dirname "$0")/run_bench.py"
