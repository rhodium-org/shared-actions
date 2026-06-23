# Golden hardened base — nginxinc/nginx-unprivileged:alpine with OS packages patched.
# Final-stage base for SPA frontends that serve as non-root (UID 101). nginx
# runs as 101, so we briefly switch to root to run apk, then drop back — the
# published image keeps the unprivileged runtime contract. See
# base-images/node/22-alpine/Dockerfile for the full rationale.
FROM nginxinc/nginx-unprivileged:alpine@sha256:054e14f543eb688809d59ec2ad1644d1a61678e247c87a318ad605977eb37eaf

USER root
RUN apk upgrade --no-cache
USER 101
