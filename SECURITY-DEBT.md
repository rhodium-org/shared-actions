# Security-debt operating model

A self-managing pipeline for CVE remediation that holds up as AI-assisted
delivery accelerates commit and CVE cadence past human triage capacity.
The principle is a single inversion: **the pipeline does the safe thing by
default; a human is pulled in only by exception.**

This is the operating manual. The mechanisms live in
`actions/trivy-gated-build`, `actions/security-policy-check`, the
`security_repo_*` gauges in `ci-metrics-exporter`, and the Grafana
"Security Debt" dashboard.

## Two regimes

Triage by where a fix can come from, because the economics differ:

| | App deps (pip / npm / maven) | Image / OS layer (Alpine / Debian) |
|---|---|---|
| Fix availability | Almost always a bump exists | Often `fix_deferred` upstream — no fix yet |
| **Default action** | **bump-or-fail — suppressions disallowed** | **time-boxed suppression in `.trivyignore.yaml`** |
| Where suppressions live | nowhere (forbidden) | `.trivyignore.yaml`, Trivy-native |
| Human pulled in when | the bump breaks tests | a suppression nears expiry, still no upstream fix |

Keeping app-dep CVEs out of the suppression store is what keeps the store
small enough to manage. You can always bump a library; you cannot always
bump libxml2.

## The lifecycle of an image-layer suppression

1. Trivy gate fails on a fixable CVE with no available fix (`fix_deferred`).
2. Add an entry to `.trivyignore.yaml`:
   ```yaml
   vulnerabilities:
     - id: CVE-2026-6732
       statement: "libxml2 fix_deferred (Debian); not reachable in a static nginx image"
       expired_at: 2026-09-01   # <= today + 90 days
   ```
3. `security-policy-check` enforces: non-empty `statement`, a bounded
   `expired_at`, no bare lines, no orphan guards. CI fails otherwise.
4. Trivy honours `expired_at` natively — it stops ignoring the CVE on that
   date, the gate re-fails, and the policy check names the lapse. The
   suppression cannot rot silently.
5. The fleet aggregator surfaces it on the dashboard the whole time
   (`min_days_to_expiry`, `expiring_soon`, `expired`).

## What runs where

| Layer | Mechanism | Cadence | Failure mode |
|---|---|---|---|
| **Gate** | `trivy-gated-build` (+ `predicate-guard`) | every build | CVE-laden image never pushed |
| **Policy** | `security-policy-check` | every build | naked / expired / over-TTL / orphan-guard → red |
| **Visibility** | `ci-metrics-exporter` `security_repo_*` → Grafana | every 15 min | dashboard tiles: expired (red), expiring (amber) |
| **Convergence** | auto-bump + dead-suppression sweep (below) | scheduled | PRs, not human triage |

## Convergence loops (no human in the steady state)

### Auto-bump (app-dep regime)

Use Renovate (or Dependabot) so fixable dependency CVEs become PRs, not
suppression decisions. Recommended `renovate.json` posture:

- `"vulnerabilityAlerts": { "enabled": true, "automerge": true }` — a CVE
  fix with green CI merges itself.
- `"rangeStrategy": "bump"`, grouped minor/patch, with the project's pins
  (`fastapi <0.136.3`, etc.) honoured via `packageRules`.
- Humans see only the PRs whose tests go red.

This is what makes "suppressions disallowed for app deps" tenable: the
bump is automated, so refusing to suppress isn't extra work.

### Dead-suppression sweep (image regime)

A scheduled job re-scans each published image **without** its ignorefile,
diffs the still-present CVE set against the policy, and proposes removal of
entries that are no longer flagged (base image rolled, transitive bump
elsewhere). Trivy can scan a remote ref directly, so no rebuild is needed:

```bash
trivy image --severity HIGH,CRITICAL --ignore-unfixed -f json \
  ghcr.io/rhodium-org/<image>:latest > present.json
# any id in .trivyignore.yaml not present in present.json is DEAD → PR its removal
```

This automates the exact rot demonstrated in access-manager this week (a
suppression left pinning a CVE the dep bump had already fixed). Wire it as
a scheduled reusable workflow per repo, or centrally with an image-name map.

## Why every check is necessary (not ceremony)

Each maps to a failure actually hit:

- bare `.trivyignore` lines with stale, wrong comments — access-manager
- a suppression "fixed" on the dep side but left pinning a phantom CVE — access-manager
- a guard script nothing runs — the `predicate-guard` orphan case
- a justified suppression that silently outlived its fix window — the
  whole reason for `expired_at`

Steady-state human cost: zero. Clean repos pass silently. The only outputs
a human reads are a red gate with a one-line fix, or a dashboard tile.

## Rollout

1. `security-policy-check` job in every repo's workflow (cheap, always-on).
2. Migrate existing flat `.trivyignore` → `.trivyignore.yaml` with
   `statement` + bounded `expired_at` (reports-guide is the worked example).
3. Renovate `vulnerabilityAlerts.automerge` on for the app-dep regime.
4. Schedule the dead-suppression sweep.
5. Watch the Grafana "Security Debt" tile; act only on red/amber.
