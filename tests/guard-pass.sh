#!/usr/bin/env bash
# Selftest fixture: a predicate guard that holds (exits 0). The gate should
# proceed to build/scan as normal.
set -euo pipefail
echo "guard-pass: predicate holds — nothing to flag."
