# Golden hardened base — nginx:alpine with OS packages patched.
# Final-stage base for the fleet's SPA frontends (node builds the bundle, nginx
# serves it — Trivy scans the nginx final stage, so THIS is where the Alpine
# openssl/libcrypto3 CVE must be fixed). See base-images/node/22-alpine/Dockerfile
# for the full rationale. Rebuilt daily; published PUBLIC for anonymous PR pulls.
FROM public.ecr.aws/docker/library/nginx:alpine@sha256:d565d19ef132a5834f5897f602831ad2e40a36c26c625f2f94f9b3fdf0ed292d

RUN apk upgrade --no-cache
