# Golden hardened base — python:3.12-slim with the OS layer and the bundled
# Python toolchain patched. See base-images/node/22-alpine/Dockerfile for the
# fleet-wide rationale; the two Python-specific deviations are below.
#
# Debian, not Alpine: every Python image in the fleet is python:*-slim. musl has
# no manylinux wheels, so an Alpine base would make numpy/torch/docling
# consumers compile from source. `apt-get upgrade` is the `apk upgrade` here.
#
# The pip step has no Alpine equivalent. python:*-slim ships pip, setuptools and
# wheel in site-packages with their own CVE history, and Trivy's METADATA scan
# finds those .dist-info dirs in the consumer's runtime stage. Plain --upgrade
# writes new files but leaves the stale .dist-info sibling, which Trivy still
# reports — only --force-reinstall overwrites it. A consumer running further pip
# operations can resurrect old transitive versions, in which case it must repeat
# this as the last pip step of its own build.
FROM public.ecr.aws/docker/library/python:3.12-slim@sha256:dd29372629eeba2dd003fd9e9d35a5b8236c44727875a0364254b5127af88e65

# Cache-buster — without it the patch layer below is restored from the registry
# buildcache and never actually re-runs. See base-images/node/22-alpine.
ARG PATCH_EPOCH
RUN echo "patch epoch ${PATCH_EPOCH}" \
    && apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --force-reinstall --upgrade pip setuptools wheel
