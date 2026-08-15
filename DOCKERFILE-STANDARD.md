# Dockerfile standard

The fleet runs ~104 images. In August 2026 eleven of them held 15.6 GB while the
other ninety fitted in under 200 MB each. Every one of the eleven broke a rule
below, and every rule below is already implemented correctly somewhere in the
org — so this document cites in-house reference Dockerfiles rather than
inventing a house style.

## The rules

1. **Multi-stage is mandatory.** Compilers, package managers, `~/.m2`, `node_modules`
   and source trees do not ship. If your final stage contains a thing that only
   built the artefact, it is a bug.
2. **JRE at runtime, never JDK.** Same for `python:*-slim` over `python:*`, and
   `-runtime` over `-devel` for CUDA.
3. **Runtime bases come from `ghcr.io/rhodium-org/base-*`.** See
   [`base-images/README.md`](base-images/README.md). These are rebuilt daily with OS
   patches applied, so a fleet-wide OS CVE is fixed in one place instead of ~50.
   Pinning upstream directly opts you out of that.
4. **Write a `.dockerignore`.** The build context is uploaded to the daemon in
   full. DACAS shipped a 5.5 GB `backend/.venv` on every build until August 2026.
   At minimum: `.git`, `**/.venv`, `**/node_modules`, `**/__pycache__`.
5. **Install dependencies before copying source.** A source-only change should
   not re-resolve the dependency graph.
6. **Never install a GPU build into a CPU pod.** Covered below — it is the single
   most expensive mistake in the estate's history.

## Reference implementations

### Go — [`docs-chat-sidecar/Dockerfile`](https://github.com/rhodium-org/docs-chat-sidecar)

The best Dockerfile in the estate, at **3 MB**. `golang:1.26-alpine` builder
emitting a static stripped binary (`CGO_ENABLED=0`, `-trimpath`,
`-ldflags="-s -w"`), into `gcr.io/distroless/static-debian12:nonroot`. Every
static Go binary should match it.

Distroless has no shell, so `HEALTHCHECK` cannot work — use Kubernetes
liveness/readiness probes instead.

### Python (ML) — [`agentic-rag/backend/Dockerfile`](https://github.com/rhodium-org/agentic-ai-rag-solution)

**2979 MB → 636 MB.** Three stages: Vite frontend builder, Python builder
installing into `--user`, then a runtime that copies `/root/.local` and the SPA
`dist/` and nothing else.

The load-bearing trick is CPU-only torch. `docling` depends on `torch`, and pip
resolves the CUDA build by default — roughly 2 GB of `nvidia/cu*` wheels. Almost
none of our pods request `nvidia.com/gpu` (several *tolerate* the GPU taint so
they can schedule on GPU nodes, which is not the same thing). Pre-install CPU
torch **before** anything resolves the dependency graph, and pip's resolver then
sees torch as satisfied and skips the CUDA variant:

```dockerfile
RUN pip install --user --no-cache-dir torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu
```

Same fix applied to DACAS in August 2026. Before reaching for it, check whether
the app imports torch at all — see whisper-gpu below.

### Quarkus — [`shared-prompt-set/api/Dockerfile`](https://github.com/rhodium-org/shared-prompt-set)

`maven:3.9.9-eclipse-temurin-21` builder → `ghcr.io/rhodium-org/base-eclipse-temurin:21-jre-alpine`,
copying the four fast-jar directories (`lib/`, `*.jar`, `app/`, `quarkus/`)
individually so the rarely-changing `lib/` layer caches independently.

Note `eclipse-temurin:21-jre` resolves to **jammy**, which ships Go binaries with
stale Go stdlib HIGH CVEs. If you cannot use the alpine golden base, use
`21-jre-noble` — scout, truenas-console and http-code-finder all do so
deliberately and document why.

### CUDA — [`whisper-gpu/backend/Dockerfile`](https://github.com/rhodium-org/whisper-gpu)

**6076 MB → ~1300 MB**, by deleting a dependency rather than restructuring.

It inherited `torch` + `torchvision` + `torchaudio` + OpenCV from a shared CUDA
base built for other consumers, while `faster-whisper` runs on CTranslate2 and
the source never imports any of them. Worse, PyPI torch wheels bundle their own
copy of the CUDA libraries already present in the CUDA base image — so the CUDA
payload was in there twice.

Two lessons:

- **Grep before you inherit.** A shared base is only cheap if you use what it
  carries. `grep -rn 'import torch' src/` costs nothing.
- **Do not over-slim a GPU base.** whisper-gpu still needs
  `-cudnn-runtime`, because CTranslate2's CUDA backend links cuBLAS *and* cuDNN.
  The win came from removing torch, not from changing CUDA tier.

Model weights are fetched at runtime into a mounted `MODEL_CACHE_DIR`. Never
bake weights into an image to "make it self-contained".

## When the Trivy gate flags a package you never installed

Package managers vendor their own dependencies, and Trivy scans them. Before
treating a finding as yours, **check the path**:

- `usr/local/lib/python3.*/site-packages/pip/_vendor/…` — pip's vendored tree.
  Trivy reads `pip/_vendor/vendor.txt`, so every image carrying pip inherits a
  CVE feed for packages nothing can import and you cannot upgrade independently.
- `usr/local/lib/node_modules/npm/…` — the bundled npm CLI, not your deps.
  Confirm with `npm ls <pkg>` plus the lockfile; both empty means it isn't yours.

Neither is suppressible in good conscience and neither needs to exist in a
runtime stage — so delete the tool rather than ignoring the CVE:

```dockerfile
RUN rm -rf /usr/local/lib/python3.*/site-packages/pip \
           /usr/local/lib/python3.*/site-packages/pip-*.dist-info \
           /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.*
```

This is the one case where a late `rm` is right despite not shrinking the image:
Trivy scans the flattened filesystem, so a deleted file is not scanned. To
recover the space too, do the removal in the stage you `COPY --from`.

Note the `base-python` images deliberately **keep** pip — they are bases that
downstream builders install with. Strip it in your runtime stage, not upstream.

## What is deliberately exempt

Not every large image is a defect. Two current examples:

- **CI runners** (`github-runner-org-chrome`, 1022 MB) are *supposed* to carry a
  full toolchain. Splitting one breaks jobs.
- **Pinned upstream images** (`hermes-agent`, 2390 MB) are not ours to slim.

If an image is big for a reason, put the reason in a comment at the top of the
Dockerfile. That comment is what stops the next person "fixing" it.

## Measuring

**There are two different numbers and they are not comparable.** Check which one
you are holding before quoting a win:

| Source | Basis | Example (`gpu-node-agent`) |
|---|---|---|
| `docker image inspect --format '{{.Size}}'`, and the CI summary | uncompressed, on-disk | 850 MB |
| kubelet `.status.images[].sizeBytes` | compressed layers + config | 202 MB |

Verified 2026-08-15: the compressed layer sum from the registry manifest was
211,711,129 bytes against the kubelet's 211,729,355 — the 18 KB gap is the config
blob. Compression ratio varies hugely by content (CUDA libraries squeeze ~4x,
an already-compressed JAR barely at all), so you cannot convert between them.

CI reports each built image's size to the workflow summary via
[`actions/trivy-gated-build`](actions/trivy-gated-build). Nothing fails on size —
it is there so growth is visible before it becomes 6 GB.

For what is actually running on the cluster, ask the kubelet:

```sh
kubectl get nodes -o json \
  | jq -r '.items[].status.images[] | (.sizeBytes|tostring) + " " + (.names[]?)' \
  | grep ghcr.io/rhodium-org/ | sort -rn | uniq
```
