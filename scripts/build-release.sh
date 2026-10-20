#!/usr/bin/env bash
# Run on the designated Linux release host, never on the Windows editing PC.
set -Eeuo pipefail
cd -- "$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(sed -n 's/^__version__ = "\([0-9.]*\)"/\1/p' moonuestc/__init__.py)"
revision="$(git rev-parse HEAD)"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && "$revision" =~ ^[a-f0-9]{40}$ ]]
[[ -z "$(git status --porcelain)" ]] || { printf 'Release source must be a clean commit.\n' >&2; exit 1; }
image="ghcr.io/horoscope963852/moonuestc:$version"
base="${PYTHON_BASE_IMAGE:-python:3.12-slim-bookworm}"
python3 -B scripts/privacy_scan.py --root . --ref "$revision"

docker build --platform linux/amd64 --build-arg "PYTHON_BASE_IMAGE=$base" --build-arg "VCS_REF=$revision" --tag "$image" .
printf 'Built %s from %s; Dockerfile tests passed.\n' "$image" "$revision"
