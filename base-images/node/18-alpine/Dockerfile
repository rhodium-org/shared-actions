# Golden hardened base — node:18-alpine with OS packages patched.
# See base-images/node/22-alpine/Dockerfile for the full rationale: this exists
# so OS-layer CVEs (openssl/libcrypto3 etc.) are patched in ONE place and fan
# out to consumers via a Renovate digest bump, not an apk-upgrade line copied
# into every app Dockerfile. Rebuilt daily; published PUBLIC for anonymous PR pulls.
FROM public.ecr.aws/docker/library/node:18-alpine@sha256:8d6421d663b4c28fd3ebc498332f249011d118945588d0a35cb9bc4b8ca09d9e

# Cache-buster — without it the patch layer below is restored from the registry
# buildcache and never actually re-runs. See base-images/node/22-alpine.
ARG PATCH_EPOCH
RUN echo "patch epoch ${PATCH_EPOCH}" && apk upgrade --no-cache
