# `security-policy-check`

Meta-guard for CVE-suppression hygiene. The enforcement spine of a
**self-managing** security-debt pipeline: it makes the *safe* state the
default and pulls a human in only by exception, so debt converges instead
of accumulating as commit and CVE cadence accelerate.

## The model: two regimes, one inversion

The default for a CVE finding must be "the pipeline does the safe thing,"
not "a human decides." The two sources have different economics:

| Source | Fix availability | Default | Human pulled in when |
|--------|------------------|---------|----------------------|
| **App deps** (pip/npm/maven) | Almost always a bump exists | **bump-or-fail — suppressions disallowed** | the bump breaks tests |
| **Image / OS layer** (Alpine/Debian) | Often `fix_deferred` upstream | **time-boxed suppression, auto-expiring** | a suppression nears expiry, still no fix |

Keeping app-dep CVEs out of the suppression store is what keeps the store
small enough to manage: you can always bump a library, so you never carry
a library suppression.

## What it enforces (image-layer suppressions in `.trivyignore.yaml`)

Every entry MUST:

- have a non-empty **`statement`** (why it's safe / what we await)
- have an **`expired_at`** date
- expire no further out than today + **`max-ttl-days`** (default 90 — no "forever")
- not already be **expired** (Trivy stops honouring it and the CVE
  resurfaces; this guard fails *loudly* with an actionable message)

Hard-fails on:

- a legacy flat **`.trivyignore`** with bare CVE lines (no justification, no expiry)
- a **naked** entry (missing `statement` or `expired_at`)
- an **expired** or **over-TTL** entry
- an **orphan guard** — a `ci-guards/*.sh` not wired as `predicate-guard:`
  in any workflow (dead code pretending to protect something)

Warns (does not fail) on entries expiring within `warn-within-days`.

## Usage

```yaml
  security-policy:
    runs-on: [self-hosted, org, linux, docker]
    steps:
      - uses: actions/checkout@v5
      - uses: rhodium-org/shared-actions/actions/security-policy-check@v1
        with:
          policy: backend/.trivyignore.yaml   # default .trivyignore.yaml
          guards-dir: backend/ci-guards        # default ci-guards
```

Run it as its own fast job that gates the build, and on a daily
`schedule:` so a suppression expiring *tomorrow* turns the repo red
*today* without anyone touching it.

## The `.trivyignore.yaml` it polices (Trivy-native)

```yaml
vulnerabilities:
  - id: CVE-2026-6732
    statement: "libxml2 pending Alpine 2.13.9-r1; not reachable in a static nginx image"
    expired_at: 2026-09-09
```

Trivy honours `expired_at` natively (it stops ignoring the CVE after that
date), so the scanning side and the policy side agree on one file. No
bespoke parser, no second source of truth.

## Inputs

| Input | Default | Notes |
|-------|---------|-------|
| `policy` | `.trivyignore.yaml` | Trivy YAML suppression file. |
| `guards-dir` | `ci-guards` | Predicate-guard scripts (orphan check). |
| `workflows-dir` | `.github/workflows` | Where `predicate-guard:` wiring is searched. |
| `max-ttl-days` | `90` | Max distance an `expired_at` may be set. |
| `warn-within-days` | `14` | Expiry window that warns rather than fails. |
| `report-path` | `security-debt-report.json` | JSON report for the fleet aggregator. |
| `upload-report` | `true` | Upload the JSON as a build artifact. |

## Outputs

`total`, `expired`, `expiring-soon`, `violations` — fan these into metrics.

## Reporting / fleet monitoring

Each run writes a JSON report (`repo`, counts, per-entry `days_to_expiry`,
`framework_violations`). A scheduled aggregator collects them across repos
and pushes gauges to Prometheus (via `ci-metrics-exporter`) feeding a
Grafana **Security Debt** panel — active suppressions/repo, expiring in
7/30d, already-expired (red), oldest entry. You manage by exception from
the dashboard, not by reading N repos.

## Why this is *necessary* and not ceremony

Every check here maps to a failure we have actually hit:

- bare `.trivyignore` lines with stale/wrong comments (access-manager, this week)
- a suppression "fixed" on the dep side but left pinning a phantom CVE
- a guard script that nothing runs

It adds no steady-state human work: clean repos pass silently; the only
output a human ever reads is a red gate with a one-line fix, or a
dashboard tile.
