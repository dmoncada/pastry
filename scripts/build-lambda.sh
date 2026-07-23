#!/usr/bin/env bash

# Package the FastAPI backend into build/lambda.zip for the AWS Lambda (python3.12, x86_64).
# Third-party deps are cross-installed as manylinux wheels; first-party packages are copied.

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build="$root/build"
stage="$build/lambda"

rm -rf "$build"
mkdir -p "$stage"

# External dependencies only (exclude the workspace members — we copy their source below).
uv export --package pastry-api \
  --no-dev \
  --no-hashes \
  --no-emit-workspace \
  -o "$build/requirements.txt"

uv pip install -r "$build/requirements.txt" --target "$stage" \
  --python-platform x86_64-manylinux2014 \
  --python-version 3.12 \
  --only-binary=:all: \
  --no-binary=python-baseconv

cp -r "$root/api/src/pastry_api" "$stage/"
cp -r "$root/shared/src/pastry_shared" "$stage/"

(cd "$stage" && zip -qr "$build/lambda.zip" . -x '*.pyc' '*/__pycache__/*')
echo "built $build/lambda.zip ($(du -h "$build/lambda.zip" | cut -f1))"
