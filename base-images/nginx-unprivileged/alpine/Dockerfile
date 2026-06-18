# Golden hardened base — nginxinc/nginx-unprivileged:alpine with OS packages patched.
# Final-stage base for SPA frontends that serve as non-root (UID 101). nginx
# runs as 101, so we briefly switch to root to run apk, then drop back — the
# published image keeps the unprivileged runtime contract. See
# base-images/node/22-alpine/Dockerfile for the full rationale.
FROM nginxinc/nginx-unprivileged:alpine@sha256:26b5d4920434bc4d8c17a68201488cf4b3d2391f0d25305cdfe66ccdc6d18aa4

USER root
RUN apk upgrade --no-cache
USER 101
