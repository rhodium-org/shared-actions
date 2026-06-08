# Self-test fixture: deliberately vulnerable image — the Trivy gate
# MUST fail this build. If selftest.yml ever shows this passing,
# the gate is broken.
#
# Sentinel package: pyyaml==5.1
#   - CVE-2020-1747  HIGH  (fix: 5.3.1)
#   - CVE-2020-14343 HIGH  (fix: 5.4)
# Both are HIGH severity and have fixes, so they trip
# `severity: CRITICAL,HIGH` + `ignore-unfixed: true`.
#
# Trivy detects them via the pyyaml-5.1.dist-info/METADATA file
# installed by pip — independent of the OS base.
FROM mirror.gcr.io/library/python:3.13-alpine

RUN pip install --no-cache-dir pyyaml==5.1
