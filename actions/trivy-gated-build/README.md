# `trivy-gated-build`

Composite action: build a Docker image, gate on Trivy HIGH/CRITICAL fixable
CVEs, push only on scan-pass. CVE-laden images **never reach the registry**.

Solves the platform-wide bug audited in [rhodium-org/cluster#67]: many repos
had Trivy *observing* after `docker push`, so vulnerable images were already
in GHCR when Trivy fired. This action enforces the canonical scout pattern.

## Pattern A — single image (default)

```yaml
jobs:
  build:
    runs-on: [self-hosted, org, linux, docker]
    permissions:
      contents: read
      packages: write
      id-token: write
    steps:
      - uses: actions/checkout@v5

      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/rhodium-org/myapp
          tags: |
            type=ref,event=branch
            type=raw,value=latest,enable={{is_default_branch}}
            type=raw,value=ts-{{date 'X'}}000,enable={{is_default_branch}}

      - uses: rhodium-org/shared-actions/actions/trivy-gated-build@v1
        with:
          image-name: ghcr.io/rhodium-org/myapp
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          push: ${{ github.event_name != 'pull_request' }}
          registry-password: ${{ secrets.GITHUB_TOKEN }}
```

That replaces ~80 lines of `setup-buildx → build (load:true) → trivy →
login → build (push:true)` boilerplate.

## Pattern B — multiple images in one repo (e.g. shared-iam)

Call the action once per image, each with its own `image-name`, `context`
and `dockerfile`. Each call independently gates its own push.

```yaml
jobs:
  build-backend:
    steps:
      - uses: actions/checkout@v5
      - uses: rhodium-org/shared-actions/actions/trivy-gated-build@v1
        with:
          image-name: ghcr.io/rhodium-org/shared-iam-backend
          context: backend
          dockerfile: backend/Dockerfile
          tags: ${{ steps.meta-backend.outputs.tags }}
          registry-password: ${{ secrets.GITHUB_TOKEN }}

  build-admin-ui:
    steps:
      - uses: actions/checkout@v5
      - uses: rhodium-org/shared-actions/actions/trivy-gated-build@v1
        with:
          image-name: ghcr.io/rhodium-org/shared-iam-admin-ui
          context: admin-ui
          dockerfile: admin-ui/Dockerfile
          tags: ${{ steps.meta-admin.outputs.tags }}
          registry-password: ${{ secrets.GITHUB_TOKEN }}
  # ...mcp-server identical shape
```

## Inputs

| Input               | Default              | Notes |
|---------------------|----------------------|-------|
| `image-name`        | **required**         | `ghcr.io/<org>/<app>`. Also drives the default cache image. |
| `context`           | `.`                  | Docker build context. |
| `dockerfile`        | `Dockerfile`         | Path to Dockerfile (passed to build-push-action `file:`). |
| `platforms`         | `linux/amd64`        | CSV. |
| `severity`          | `CRITICAL,HIGH`      | Trivy gate severities. |
| `trivyignore-path`  | `.trivyignore`       | Silently skipped if the file is absent. |
| `trivy-timeout`     | (empty)              | e.g. `15m0s`. For images bundling large binaries (CUDA, ML weights). Empty = trivy-action 5m default. |
| `target`            | (empty)              | Multi-stage build target. Empty = final stage. For matrix builds emitting several images from one Dockerfile. |
| `predicate-guard`   | (empty)              | Path to a guard script that asserts the invariants behind your suppressions still hold. Runs first; non-zero exit fails the gate. See [Guarding suppressions](#guarding-suppressions). |
| `tags`              | (empty)              | Final tags for the push step. Empty = scan only. Pass `${{ steps.meta.outputs.tags }}`. |
| `labels`            | (empty)              | Final labels. Pass `${{ steps.meta.outputs.labels }}`. |
| `build-args`        | (empty)              | Newline-separated `KEY=value`. |
| `build-secrets`     | (empty)              | Newline-separated `KEY=value` for BuildKit secrets. |
| `push`              | `true`               | Set `${{ github.event_name != 'pull_request' }}` to skip push on PRs. |
| `registry`          | `ghcr.io`            | |
| `registry-username` | `${{ github.actor }}`| |
| `registry-password` | (empty)              | Required when `push=true`. Usually `secrets.GITHUB_TOKEN`. |
| `cache-image`       | `<image-name>:buildcache` | Override only if you want a separate cache namespace. |
| `provenance`        | `true`               | Pass-through. |
| `sbom`              | `true`               | Pass-through. |

## Outputs

- `digest` — pushed image digest (empty when `push=false` or `tags` empty)
- `scan-tag` — local tag used for the Trivy scan

## Guarding suppressions

A `.trivyignore` entry carries a justification — but the justification is a
point-in-time human judgement that nothing enforces as the code evolves.
"Safe because we don't read `request.url.path` for auth" silently rots the
moment someone adds that usage.

`predicate-guard` turns the prose justification into an enforceable
invariant, wired into the **same gate** that honours the suppression so the
two can't drift apart. The script runs first (fail-fast); a non-zero exit
blocks the build.

```yaml
      - uses: rhodium-org/shared-actions/actions/trivy-gated-build@v1
        with:
          image-name: ghcr.io/rhodium-org/myapp
          trivyignore-path: backend/.trivyignore
          predicate-guard: backend/ci-guards/no-request-url.sh
          # ...
```

A guard script is just shell — fail on the condition that would invalidate
a suppression, with a message that names the CVE and the fix:

```bash
#!/usr/bin/env bash
# Predicate for the suppressed PYSEC-2026-161 (starlette Host-header auth
# bypass): no source may read request.url for security decisions.
set -euo pipefail
hits="$(grep -rnE 'request\.url(\.path)?' backend --include='*.py' \
          | grep -vE '/tests?/|# pysec-2026-161-reviewed' || true)"
if [ -n "$hits" ]; then
  echo "::error::PYSEC-2026-161 predicate violated — request.url is read:"
  echo "$hits"
  exit 1
fi
```

Three complementary layers, weakest → strongest:

1. **Expiry date** in the `.trivyignore` comment — bounds staleness, forces
   periodic re-review (see reports-guide's `exp:YYYY-MM-DD` convention).
2. **`predicate-guard`** — catches the specific assumption being violated.
   Grep is fine; semgrep is more precise (ignores comments/strings,
   narrows to auth/middleware paths).
3. **Behavioural regression test** in your normal test suite — asserts the
   security *outcome* (e.g. a malicious `Host` header can't bypass auth),
   so it survives refactors the static guard can't see. This is the only
   layer that holds even if someone legitimately starts using `request.url`.

Reference implementation: `rhodium-org/access-manager`
(`backend/ci-guards/no-request-url.sh` + the PYSEC-2026-161 Host-header
test in `backend/tests/`).

## What the gate catches (and doesn't)

Catches: HIGH/CRITICAL CVEs that have a fix available (`ignore-unfixed: true`).

Doesn't catch: unfixed-upstream CVEs, lower-severity CVEs, license issues,
runtime config drift, supply-chain attacks on the build itself. Use
provenance + SBOM for the supply-chain side; bump base images on a
schedule for unfixed CVEs.

## Self-test

[`.github/workflows/selftest.yml`](../../.github/workflows/selftest.yml)
runs two scenarios on every push:

1. **Clean** image (`python:3.13-alpine`) — gate must PASS, image published.
2. **Sentinel-CVE** image (`python:3.9-slim`, pinned to a known-vulnerable
   release) — gate must FAIL, push must not happen.

Both are asserted in CI. The action ships behind that gate.
