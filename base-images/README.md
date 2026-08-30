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

Covering every **runtime** (final-stage) base in the fleet — node servers,
nginx-served SPAs, Java JRE runtimes and Python runtimes. (Builder-only stages,
e.g. a node builder feeding an nginx final stage, don't affect the final scan,
so the runtime base is what matters.)

| image | upstream | final stage of |
|-------|----------|----------------|
| `ghcr.io/rhodium-org/base-node:18-alpine` | `node:18-alpine` | node servers / SSR |
| `ghcr.io/rhodium-org/base-node:20-alpine` | `node:20-alpine` | node servers / SSR |
| `ghcr.io/rhodium-org/base-node:22-alpine` | `node:22-alpine` | node servers / MCPs |
| `ghcr.io/rhodium-org/base-nginx:alpine` | `nginx:alpine` | SPA frontends |
| `ghcr.io/rhodium-org/base-nginx-unprivileged:alpine` | `nginxinc/nginx-unprivileged:alpine` | SPA frontends (non-root) |
| `ghcr.io/rhodium-org/base-eclipse-temurin:17-jre-alpine` | `eclipse-temurin:17-jre-alpine` | Java runtimes |
| `ghcr.io/rhodium-org/base-eclipse-temurin:21-jre-alpine` | `eclipse-temurin:21-jre-alpine` | Java runtimes |
| `ghcr.io/rhodium-org/base-eclipse-temurin:21-jre-noble` | `eclipse-temurin:21-jre-noble` | Java runtimes that can't use musl |
| `ghcr.io/rhodium-org/base-python:3.12-slim` | `python:3.12-slim` | Python runtimes |
| `ghcr.io/rhodium-org/base-python:3.13-slim` | `python:3.13-slim` | Python runtimes |
| `ghcr.io/rhodium-org/base-python:3.14-slim` | `python:3.14-slim` | Python runtimes |

### Prefer `21-jre-alpine`; reach for `21-jre-noble` only if you must

The Alpine JRE is the default Java runtime base. Use `21-jre-noble` only when
something in the image needs glibc — a JNI library, a native agent, or a
Playwright/Chromium dependency. It is a bigger image on a slower-moving patch
cadence, but it is a *golden* image, which upstream `eclipse-temurin:21-jre-noble`
is not.

Never use `eclipse-temurin:21-jre` — that tag resolves to **jammy**, which ships
Go binaries with stale Go stdlib HIGH CVEs and will fail your Trivy gate.

### The Python family is Debian, not Alpine

Every Python image in the fleet is `python:*-slim`, and it has to stay that way:
musl has no manylinux wheels, so an Alpine base would make numpy/torch/docling
consumers compile from source. So this family runs `apt-get upgrade` where the
others run `apk upgrade`.

It also does something the Alpine families don't — a `pip install
--force-reinstall` of `pip`, `setuptools` and `wheel`. `python:*-slim` ships
those in `site-packages` with their own CVE history, and Trivy's METADATA scan
finds the `.dist-info` dirs in the *consumer's* runtime stage. A plain
`--upgrade` leaves the stale `.dist-info` sibling behind and Trivy still reports
it. This was previously copy-pasted per app (see `agentic-rag/backend/Dockerfile`).

Caveat that survives the golden base: if a consumer runs further `pip`
operations that pull old transitive versions back in (`opentelemetry-bootstrap`
is the known offender), it must repeat the `--force-reinstall` as the **last**
pip step of its own build.

Built and gated by [`.github/workflows/base-images.yml`](../.github/workflows/base-images.yml).

## One-time bootstrap: make the package PUBLIC

App **PR** builds skip `docker login` by design (`trivy-gated-build` only logs
in when `push=true`). So the `FROM` pull on a Renovate PR build is **anonymous**
— a private base 401s and every PR build fails. The `base-node` package must be
**public**:

> GitHub → Organizations → rhodium-org → Packages → `<package>` →
> Package settings → Danger Zone → **Change visibility → Public**

…for each base package: `base-node`, `base-nginx`, `base-nginx-unprivileged`,
`base-eclipse-temurin`, `base-python`. Packages publish as **internal** by default, and an
anonymous pull of an internal package returns **403** — so a PR build (which
skips `docker login`) can't pull it until it's public. There is no REST endpoint
to flip container-package visibility; it must be done in the UI, once per package.

## Adding a family

Add a `base-images/<family>/<tag>/Dockerfile` (two lines: `FROM upstream` +
`RUN apk upgrade --no-cache`, or the Debian equivalent) and a matrix row in
`base-images.yml`.
