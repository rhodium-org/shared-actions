# Golden hardened base — nginx:alpine with OS packages patched.
# Final-stage base for the fleet's SPA frontends (node builds the bundle, nginx
# serves it — Trivy scans the nginx final stage, so THIS is where the Alpine
# openssl/libcrypto3 CVE must be fixed). See base-images/node/22-alpine/Dockerfile
# for the full rationale. Rebuilt daily; published PUBLIC for anonymous PR pulls.
FROM public.ecr.aws/docker/library/nginx:alpine@sha256:1a8724a52d432501548a8d8681bb1554c2d09778f8b9ed0882fc3442549980b7

RUN apk upgrade --no-cache
