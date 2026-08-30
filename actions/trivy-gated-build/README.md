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

> **Tag width — read before writing the Flux ImagePolicy.**
> `ts-{{date 'X'}}000` is unix **seconds with three literal zeros appended**, so the
> tag is **13 digits**, not 10. The matching policy in the cluster repo must therefore be:
>
> ```yaml
> filterTags:
>   pattern: '^ts-(?P<ts>[0-9]{13})$'   # pinned AND anchored
>   extract: '$ts'
> policy:
>   numerical:
>     order: asc
> ```
>
> Pin `{10}` against this tag line and Flux matches nothing, so the app never deploys.
> Leave the pattern unpinned (`[0-9]+`) or unanchored (`[0-9]{13}` with no `$`) and a
> single malformed over-long tag outranks every real build for ever — silently, with no
> error anywhere. If you would rather emit 10-digit seconds, use plain
> `ts-{{date 'X'}}` (no `000`) and pin `{10}$`. Either is fine; they must agree.

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
| `gha-cache`         | `true`               | Set `'false'` for images over ~10 GB. See [Cache sizing](#cache-sizing). |
| `pull`              | `true`               | Re-resolve every `FROM` against the registry each build. Keep `true` for the moving golden bases. See [Moving base tags](#moving-base-tags). |
| `provenance`        | `true`               | Pass-through. |
| `sbom`              | `true`               | Pass-through. |

## Outputs

- `digest` — pushed image digest (empty when `push=false` or `tags` empty)
- `scan-tag` — local tag used for the Trivy scan

## Cache sizing

Two caches are written by default: a registry cache (`<image>:buildcache` on
GHCR) and the GitHub Actions cache (`type=gha`).

**The GHA cache is capped at 10 GB per repository.** A `mode=max` export of an
image larger than that cannot fit, so the export runs to completion, the entry
is evicted, and the next run gets no hit and pays the full export again. It is
pure cost with no upside, and it is invisible: the step succeeds.

Measured on `skyreels-v3-backend` (~18 GB of CUDA and torch) — a 71-minute job,
broken down:

| Phase | Time |
|---|---|
| Actual `docker build` | 5m30s |
| Export layers to OCI | 3m24s |
| Load tarball into the local daemon (`load: true`, needed for the scan) | 2m54s |
| **Export to GitHub Actions Cache** | **59m** |

Setting `gha-cache: 'false'` drops `type=gha` from both `cache-from` and
`cache-to` on both builds. The registry cache has no size cap and actually
persists, so nothing is lost.

Rule of thumb: if the image is over ~8 GB, or the job log shows
`exporting to GitHub Actions Cache` taking minutes, turn it off.

## Moving base tags

Do not pin the golden bases by digest in your Dockerfile:

```dockerfile
# Wrong — a time bomb.
FROM ghcr.io/rhodium-org/base-eclipse-temurin:21-jre-alpine@sha256:89dfb70d...

# Right.
FROM ghcr.io/rhodium-org/base-eclipse-temurin:21-jre-alpine
```

`base-eclipse-temurin`, `base-node`, `base-nginx` and friends are **moving
tags**. They are rebuilt for CVE patches and GHCR garbage-collects the
manifest they superseded. A digest pinned in a Dockerfile therefore builds
fine right up until the base is next rebuilt, and then every build fails with
`failed to resolve source metadata ... not found` — at a date nobody chose.
That took finance-scenario-simulator's backend offline for two commits in
August 2026; because its paths filter meant only the frontend job ran, the
workflow stayed green and a committed API change never reached production.

Renovate will not re-pin them: the org config sets `pinDigests: false` for the
`dockerfile` manager precisely because a daily-rebuilt base makes a pin stale
within a day.

`pull: true` (the default) is the other half. It passes `--pull` to both the
scan build and the push build so buildx re-resolves `FROM` against the
registry instead of reusing a digest an earlier run left in the layer cache —
which matters especially on the self-hosted runners, where that state persists
between jobs. Both builds pull, so the image that gets pushed is resolved as
freshly as the one that got scanned.

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
