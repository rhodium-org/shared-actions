# Security-debt operating model

A self-managing pipeline for CVE remediation that holds up as AI-assisted
delivery accelerates commit and CVE cadence past human triage capacity.
The principle is a single inversion: **the pipeline does the safe thing by
default; a human is pulled in only by exception.**

This is the operating manual. The mechanisms live in
`actions/trivy-gated-build`, `actions/security-policy-check`, the
`security_repo_*` gauges in `ci-metrics-exporter`, and the Grafana
"Security Debt" dashboard.

## Three lanes

Triage by where a fix can come from, because the economics differ. The
overwhelmingly common app-dep case is "a bump exists" — so the default there
stays bump-or-fail. The two exceptions (an app dep with *no* upstream fix, and
the OS layer) share the same time-boxed-suppression machinery.

| | Fixable app dep (pip / npm / maven) | **Unfixable app dep** (no upstream fix yet) | Image / OS layer (Alpine / Debian) |
|---|---|---|---|
| Fix availability | a bump exists | none published (e.g. torch CVE-2025-3000) | often `fix_deferred` upstream |
| **Default action** | **bump-or-fail — suppressions disallowed** | **time-boxed suppression in `.pip-audit-ignore.yaml`** | **time-boxed suppression in `.trivyignore.yaml`** |
| Where suppressions live | nowhere (forbidden) | `.pip-audit-ignore.yaml` (same schema, policy-checked) | `.trivyignore.yaml`, Trivy-native |
| Extra gate before suppressing | n/a — just bump | **functional-exposure check**: confirm the app never reaches the vulnerable code path (statement records the evidence) | reachability noted in `statement` |
| Human pulled in when | the bump breaks tests | a suppression nears expiry, still no upstream fix | a suppression nears expiry, still no upstream fix |

Keeping *fixable* app-dep CVEs out of the suppression store is what keeps the
store small enough to manage — you can always bump a library, so refusing to
suppress costs nothing. But "you can always bump a library" is not literally
always true: a transitive dep can carry a CVE with **no patched release**
(torch `torch.jit.script` CVE-2025-3000, no fix as of 2026-06). Under
bump-or-fail that PR sits red forever — the exact rot this system exists to
kill. So the unfixable case is admitted to the suppression regime under
*stricter* terms than the OS layer: it additionally requires a recorded
**functional-exposure check** (we only suppress when the app never invokes the
vulnerable API), and it auto-expires like every other suppression so it cannot
become permanent. The moment a fix ships, the dead-suppression sweep (and
Renovate's OSV alerts) surface it for removal → bump.

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

## The lifecycle of an unfixable app-dep suppression

Identical machinery, one extra gate up front. Use ONLY when `pip-audit`
reports a CVE whose **Fix Versions column is empty** (no patched release).

1. `pip-audit` fails on a CVE with no fix version.
2. **Functional-exposure check** (the extra gate): confirm the app never
   reaches the vulnerable code path — e.g. grep for the vulnerable API
   (`torch.jit` for CVE-2025-3000) and confirm it is unused, and that the dep
   is transitive. If the app IS exposed, do NOT suppress — pin down, refactor
   off the path, or hold. Record the evidence in the `statement`.
3. Add an entry to `.pip-audit-ignore.yaml` (same schema as `.trivyignore.yaml`):
   ```yaml
   vulnerabilities:
     - id: CVE-2025-3000
       package: torch                       # informational
       statement: "torch.jit.script memory corruption (CVSS 4.8, local-user). No upstream fix. torch is transitive; app never calls torch.jit — not functionally exposed (verified 2026-06-20)."
       expired_at: 2026-09-18   # <= today + 90 days
   ```
4. The `pip-audit` step feeds `--ignore-vuln <id>` for each **non-expired**
   entry only; on the expiry date the entry stops being passed, the gate
   re-fails, and `security-policy-check --policy .pip-audit-ignore.yaml` names
   the lapse. The suppression cannot rot silently.
5. The dead-suppression sweep (and Renovate OSV alerts) re-check OSV/PyPI for a
   published fix; when one appears it proposes removal → Renovate bumps.

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
