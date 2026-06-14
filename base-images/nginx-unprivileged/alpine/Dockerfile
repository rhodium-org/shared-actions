# Golden hardened base — nginxinc/nginx-unprivileged:alpine with OS packages patched.
# Final-stage base for SPA frontends that serve as non-root (UID 101). nginx
# runs as 101, so we briefly switch to root to run apk, then drop back — the
# published image keeps the unprivileged runtime contract. See
# base-images/node/22-alpine/Dockerfile for the full rationale.
FROM nginxinc/nginx-unprivileged:alpine

USER root
RUN apk upgrade --no-cache
USER 101
