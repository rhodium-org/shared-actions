# Golden hardened base — python:3.13-slim with the OS layer and the bundled
# Python toolchain patched. See the 3.12-slim sibling for the full rationale.
FROM public.ecr.aws/docker/library/python:3.13-slim@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --force-reinstall --upgrade pip setuptools wheel
