#!/usr/bin/env bash
set -euo pipefail

uv sync --frozen --no-dev --no-install-project

npm --prefix web install
NEXT_PUBLIC_APP_VERSION="$(cat VERSION)" npm --prefix web run build

rm -rf web_dist
cp -R web/out web_dist
