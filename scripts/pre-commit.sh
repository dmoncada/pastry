#!/usr/bin/env bash

# Install with: $ ln -s ../../scripts/pre-commit.sh .git/hooks/pre-commit

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
make check
