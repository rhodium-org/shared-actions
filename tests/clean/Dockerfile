# Self-test fixture: clean image — the Trivy gate MUST pass on this.
# Updated 2026-08-30.
FROM mirror.gcr.io/library/python:3.13-alpine

# Patch the OS layer, for the same reason every golden base does (see
# base-images/node/22-alpine/Dockerfile). Upstream python:*-alpine lags the
# Alpine security branch, so a fixable OS CVE sits in the published tag for
# days — and this fixture asserts the gate PASSES, so upstream's lag turns the
# selftest red on an image that is doing nothing wrong. That is what happened
# on 2026-08-27: openssl CVE-2026-14456 (libcrypto3/libssl3 3.5.7-r0, fixed in
# 3.5.8-r0) left the selftest failing for four days while the golden bases,
# which do patch, stayed green through this very gate.
#
# PATCH_EPOCH is the cache-buster, passed per-run by selftest.yml. The FROM is
# a moving tag and the RUN string never changes, so without a varying ARG the
# patch layer is restored from buildcache forever and the upgrade silently
# stops happening. The ARG must be *referenced* by the RUN to affect the cache
# key — declaring it is not enough.
ARG PATCH_EPOCH
RUN echo "patch epoch ${PATCH_EPOCH}" && apk upgrade --no-cache

# Strip pip. Trivy's python-pkg scanner reads pip/_vendor/vendor.txt, so any
# image keeping pip inherits a CVE feed for pip's *internal* dependencies —
# packages nothing can import and we cannot upgrade independently. That is what
# turned this fixture red on 2026-08-11 (msgpack 1.1.2, setuptools 70.3.0, both
# listed only in vendor.txt). Removing pip is also correct for real runtime
# images; see DOCKERFILE-STANDARD.md.
RUN rm -rf /usr/local/lib/python3.*/site-packages/pip \
           /usr/local/lib/python3.*/site-packages/pip-*.dist-info \
           /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.*

RUN echo "no vulnerable packages installed"
