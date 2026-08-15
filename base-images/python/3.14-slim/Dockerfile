# Golden hardened base — python:3.14-slim with the OS layer and the bundled
# Python toolchain patched. See the 3.12-slim sibling for the full rationale.
FROM public.ecr.aws/docker/library/python:3.14-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4

RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --force-reinstall --upgrade pip setuptools wheel
