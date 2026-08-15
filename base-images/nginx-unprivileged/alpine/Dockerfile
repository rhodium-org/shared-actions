# Golden hardened base — nginxinc/nginx-unprivileged:alpine with OS packages patched.
# Final-stage base for SPA frontends that serve as non-root (UID 101). nginx
# runs as 101, so we briefly switch to root to run apk, then drop back — the
# published image keeps the unprivileged runtime contract. See
# base-images/node/22-alpine/Dockerfile for the full rationale.
FROM nginxinc/nginx-unprivileged:alpine@sha256:a718212f9cf21e241f14067333000a3f0930292f5354fe0db269e9a2a2596b9e

USER root
# Cache-buster — without it the patch layer below is restored from the registry
# buildcache and never actually re-runs. See base-images/node/22-alpine.
ARG PATCH_EPOCH
RUN echo "patch epoch ${PATCH_EPOCH}" && apk upgrade --no-cache
USER 101
