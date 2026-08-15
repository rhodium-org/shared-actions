# Golden hardened base — node:22-alpine with OS packages patched.
#
# WHY THIS EXISTS
#   Upstream node:*-alpine images lag the Alpine security branch: a freshly
#   disclosed OS-layer CVE (e.g. openssl/libcrypto3 CVE-2026-45447, fixed in
#   3.5.7-r0) sits unpatched in the published tag for days. Our Trivy gate
#   (ignore-unfixed:true) then correctly BLOCKS every app whose image carries
#   the fixable HIGH — which, because the whole fleet shares this base, is most
#   of the org at once. None of those app PRs can clear it: it's an OS package,
#   not an npm/pip dep.
#
#   This image patches it in ONE place. `apk upgrade` pulls the latest Alpine
#   point-release of every OS package, so the fix lands here and fans out to
#   every consumer via a single Renovate digest bump — instead of an
#   `apk upgrade` line copy-pasted into ~50 app Dockerfiles (which IS the tech
#   debt we're avoiding).
#
#   Rebuilt daily by .github/workflows/base-images.yml and published PUBLIC so
#   PR builds (which skip docker-login) can pull it anonymously.
FROM public.ecr.aws/docker/library/node:22-alpine@sha256:ab07539e0988b63558ff621f5fbe1077054c39d9809112974fb79993949d41cd

# Cache-buster, passed as a per-run value by .github/workflows/base-images.yml.
# Without it BuildKit restores the patch layer below from the registry
# buildcache — the FROM digest is pinned and the RUN string never changes, so
# the cache key is stable forever and the "rebuilt daily with OS patches" that
# every consumer relies on silently stops happening. Verified 2026-08-15: the
# eclipse-temurin legs had been serving a June package set for weeks, logging
# `RUN apk upgrade --no-cache` / `CACHED` on every scheduled run. The ARG must
# be *referenced* by the RUN; merely declaring it does not affect the cache key.
ARG PATCH_EPOCH
RUN echo "patch epoch ${PATCH_EPOCH}" && apk upgrade --no-cache
