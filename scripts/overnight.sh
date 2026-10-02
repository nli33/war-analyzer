#!/usr/bin/env bash
# Thin wrapper kept so `./scripts/overnight.sh` still works. All options: python3 scripts/overnight.py --help
exec python3 "$(dirname "${BASH_SOURCE[0]}")/overnight.py" "$@"
