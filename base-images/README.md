# Golden hardened base images

Upstream `<family>:<tag>-alpine` + `apk upgrade --no-cache`, rebuilt daily and
published to `ghcr.io/rhodium-org/base-<family>:<tag>`.

## Why

Upstream `*-alpine` tags lag the Alpine security branch. When a fixable
OS-layer CVE drops (e.g. openssl/`libcrypto3` **CVE-2026-45447**, fixed in
`3.5.7-r0`), it sits unpatched in the published tag for days. Our Trivy gate
(`ignore-unfixed: true`) then **correctly blocks** every app whose image
carries that fixable HIGH — and because the whole fleet shares this base, that
is most of the org at once. None of those app PRs can clear it: it's an OS
package, not an npm/pip dependency.

Patching it here fixes it in **one place**. The fix fans out to every consumer
via a single Renovate digest bump — instead of an `apk upgrade` line
copy-pasted into ~50 app Dockerfiles (which is the tech debt we're avoiding).
The eventual `node:22 → 24` move likewise becomes a one-line change here.

## How consumers use it

```dockerfile
# before
FROM public.ecr.aws/docker/library/node:22-alpine
# after
FROM ghcr.io/rhodium-org/base-node:22-alpine
```

Nothing else changes — it's a drop-in (same node binary, WORKDIR, user; only OS
packages are newer). Renovate's `docker:pinDigests` then pins the consumer to a
specific golden-base digest and bumps it as new builds publish.

## Published images

Covering every **runtime** (final-stage) Alpine base in the fleet — node servers,
nginx-served SPAs, and Java JRE runtimes. (Builder-only Alpine stages, e.g. a
node builder feeding an nginx final stage, don't affect the final scan, so the
runtime base is what matters.)

| image | upstream | final stage of |
|-------|----------|----------------|
| `ghcr.io/rhodium-org/base-node:18-alpine` | `node:18-alpine` | node servers / SSR |
| `ghcr.io/rhodium-org/base-node:20-alpine` | `node:20-alpine` | node servers / SSR |
| `ghcr.io/rhodium-org/base-node:22-alpine` | `node:22-alpine` | node servers / MCPs |
| `ghcr.io/rhodium-org/base-nginx:alpine` | `nginx:alpine` | SPA frontends |
| `ghcr.io/rhodium-org/base-nginx-unprivileged:alpine` | `nginxinc/nginx-unprivileged:alpine` | SPA frontends (non-root) |
| `ghcr.io/rhodium-org/base-eclipse-temurin:17-jre-alpine` | `eclipse-temurin:17-jre-alpine` | Java runtimes |
| `ghcr.io/rhodium-org/base-eclipse-temurin:21-jre-alpine` | `eclipse-temurin:21-jre-alpine` | Java runtimes |

Built and gated by [`.github/workflows/base-images.yml`](../.github/workflows/base-images.yml).

## One-time bootstrap: make the package PUBLIC

App **PR** builds skip `docker login` by design (`trivy-gated-build` only logs
in when `push=true`). So the `FROM` pull on a Renovate PR build is **anonymous**
— a private base 401s and every PR build fails. The `base-node` package must be
**public**:

> GitHub → Organizations → rhodium-org → Packages → `<package>` →
> Package settings → Danger Zone → **Change visibility → Public**

…for each base package: `base-node`, `base-nginx`, `base-nginx-unprivileged`,
`base-eclipse-temurin`. Packages publish as **internal** by default, and an
anonymous pull of an internal package returns **403** — so a PR build (which
skips `docker login`) can't pull it until it's public. There is no REST endpoint
to flip container-package visibility; it must be done in the UI, once per package.

## Adding a family

Add a `base-images/<family>/<tag>/Dockerfile` (two lines: `FROM upstream` +
`RUN apk upgrade --no-cache`) and a matrix row in `base-images.yml`. Candidates
already in the fleet: `nginx`/`nginx-unprivileged:*-alpine`,
`eclipse-temurin:{17,21}-jre-alpine`.
