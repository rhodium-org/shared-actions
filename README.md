# `rhodium-org/shared-actions`

Shared composite GitHub Actions for rhodium-org repos. Private — intended
for our self-hosted runner pool; some actions reference internal cache
images and `[self-hosted, org, linux, docker]` runners.

## Actions

| Action | Purpose |
|--------|---------|
| [`actions/trivy-gated-build`](actions/trivy-gated-build) | Build a Docker image, gate on Trivy HIGH/CRITICAL fixable CVEs, push only on scan-pass. CVE-laden images never reach the registry. Foundation for [cluster#67] platform-wide remediation. |

## Versioning

- `@v1` — current major. Breaking changes will move to `@v2`.
- `@main` — bleeding edge. Don't pin downstream production workflows to `main`.

The `v1` tag is moved forward by hand after the selftest passes against a
release commit; downstream consumers should always pin to `@v1` (not a
specific SHA) so security fixes propagate.

## Selftest

Every action under `actions/` is exercised by a workflow under
`.github/workflows/selftest*.yml`. CI must be green before tagging.

Today the selftest covers:

- `actions/trivy-gated-build`:
  - clean image (`python:3.13-alpine`) → gate PASSES
  - CVE-laden image (`pyyaml==5.1` — CVE-2020-1747 + CVE-2020-14343, both HIGH/fixable) → gate BLOCKS

## Related

- [rhodium-org/cluster#69] — original spec for `trivy-gated-build`
- [rhodium-org/cluster#67] — platform-wide Trivy gate audit (33 repos to migrate)
- `~/.claude/feedback/feedback_security_scan_must_gate_push.md` — operator memory note that surfaced the bug

[cluster#67]: https://github.com/rhodium-org/cluster/issues/67
[cluster#69]: https://github.com/rhodium-org/cluster/issues/69
[rhodium-org/cluster#69]: https://github.com/rhodium-org/cluster/issues/69
[rhodium-org/cluster#67]: https://github.com/rhodium-org/cluster/issues/67
