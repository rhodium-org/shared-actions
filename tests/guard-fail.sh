#!/usr/bin/env bash
# Selftest fixture: a predicate guard that is VIOLATED (exits non-zero). The
# gate must abort before building, proving a suppression can't outlive its
# justification.
set -euo pipefail
echo "::error::guard-fail: predicate violated (selftest fixture)."
exit 1
