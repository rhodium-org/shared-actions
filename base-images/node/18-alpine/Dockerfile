# Golden hardened base — node:18-alpine with OS packages patched.
# See base-images/node/22-alpine/Dockerfile for the full rationale: this exists
# so OS-layer CVEs (openssl/libcrypto3 etc.) are patched in ONE place and fan
# out to consumers via a Renovate digest bump, not an apk-upgrade line copied
# into every app Dockerfile. Rebuilt daily; published PUBLIC for anonymous PR pulls.
FROM public.ecr.aws/docker/library/node:18-alpine

RUN apk upgrade --no-cache
