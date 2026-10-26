#!/usr/bin/env bash
# Offline CI entry point. Python maps all nonzero assessment outcomes to root exit 1.
set -eu
action_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${action_root}/mcp_zap_gate.py" assessment-regression "$@"
