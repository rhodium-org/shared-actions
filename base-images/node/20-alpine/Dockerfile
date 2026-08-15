# Golden hardened base — node:20-alpine with OS packages patched.
# See base-images/node/22-alpine/Dockerfile for the full rationale: this exists
# so OS-layer CVEs (openssl/libcrypto3 etc.) are patched in ONE place and fan
# out to consumers via a Renovate digest bump, not an apk-upgrade line copied
# into every app Dockerfile. Rebuilt daily; published PUBLIC for anonymous PR pulls.
FROM public.ecr.aws/docker/library/node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293

# Cache-buster — without it the patch layer below is restored from the registry
# buildcache and never actually re-runs. See base-images/node/22-alpine.
ARG PATCH_EPOCH
RUN echo "patch epoch ${PATCH_EPOCH}" && apk upgrade --no-cache
