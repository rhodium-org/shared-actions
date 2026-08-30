# Golden hardened base — eclipse-temurin:21-jre-noble with OS packages patched.
#
# Ubuntu, not Alpine: this is the sibling of 21-jre-alpine for the Java runtimes
# that cannot use musl. DOCKERFILE-STANDARD.md already directs those apps at
# `21-jre-noble` (rather than the default `21-jre`, which resolves to jammy and
# ships Go binaries with stale Go stdlib HIGH CVEs) — but until this image
# existed there was no *golden* noble to point them at, so all eleven of them
# pinned upstream directly and opted out of the daily patch fanout. Five were
# sitting red on Ubuntu 24.04 OS findings when this was added (2026-08-30).
#
# `apt-get upgrade` is the `apk upgrade` here, exactly as in the python family.
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jre-noble@sha256:96975602e131485862eb8cd32927face8a06d7591a5e865944b634a701d9df72

# Cache-buster — without it the patch layer below is restored from the registry
# buildcache and never actually re-runs. See base-images/node/22-alpine.
ARG PATCH_EPOCH
RUN echo "patch epoch ${PATCH_EPOCH}" \
    && apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*
