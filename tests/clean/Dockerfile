# Self-test fixture: clean image — the Trivy gate MUST pass on this.
# Updated 2026-08-15.
FROM mirror.gcr.io/library/python:3.13-alpine

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
