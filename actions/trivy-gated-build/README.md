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
