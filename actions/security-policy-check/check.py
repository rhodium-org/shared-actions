#!/usr/bin/env python3
"""Security-debt policy meta-guard.

Enforces the invariants that keep a repo's CVE-suppression state from
silently rotting, and emits a machine-readable report for fleet-wide
monitoring. Run in every gate and on a schedule.

WHY THIS EXISTS
---------------
AI-assisted delivery accelerates both commit cadence and CVE cadence past
the point where humans can triage each one. The only sustainable answer is
to make the *safe* state the default and pull a human in by exception. This
script is the enforcement spine: it makes suppressions liabilities with a
mandatory, bounded TTL and a justification — never permanent, never naked —
so security debt converges instead of accumulating.

POLICY (which suppressions are allowed)
---------------------------------------
This guard validates ANY suppression file passed via --policy with the
schema `vulnerabilities: [{id, statement, expired_at}]`. Two files use it:
  * `.trivyignore.yaml`     — image / OS-layer CVEs (Trivy-native).
  * `.pip-audit-ignore.yaml`— UNFIXABLE app-dep CVEs only (no upstream fix).
Each entry MUST:
  * have a non-empty `statement` (why it's safe / what we're waiting on)
  * have an `expired_at` date
  * expire no further out than today + --max-ttl-days (no "forever")
  * not already be expired (the gate stops honouring it; we fail loudly with
    an actionable message rather than letting the CVE silently resurface)

A legacy flat `.trivyignore` with bare CVE lines is a hard failure: bare
lines carry no justification and no expiry, which is the exact rot we are
designing out.

*Fixable* app-dependency CVEs (pip/npm/maven) are still NOT suppressible —
a bump exists, so the policy is bump-or-fail. The ONLY app-dep entries that
belong in `.pip-audit-ignore.yaml` are CVEs with no published fix AND a
recorded functional-exposure check showing the app never reaches the
vulnerable code path. See shared-actions/SECURITY-DEBT.md ("Three lanes").

GUARDS
------
Predicate guards (e.g. ci-guards/no-request-url.sh) are standalone CI
tripwires. The only rule enforced here: no orphans — every guard script
must be wired into a workflow as a `predicate-guard:` input, else it is
dead code pretending to protect something.

OUTPUTS
-------
  * exit non-zero on any hard violation (CI gate)
  * a Markdown table to $GITHUB_STEP_SUMMARY
  * GH error/warning annotations
  * a JSON report (--report PATH) for the fleet aggregator → Prometheus
  * counts to $GITHUB_OUTPUT (total / expired / expiring_soon / violations)
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - the action pip-installs it
    print("::error::PyYAML not available; the action must `pip install pyyaml` first")
    sys.exit(2)


TODAY = dt.date.today()


@dataclass
class Entry:
    id: str
    statement: str
    expired_at: str | None
    days_to_expiry: int | None
    guarded_by: str | None
    status: str  # ok | expiring_soon | expired | naked | over_ttl
    detail: str = ""


@dataclass
class Report:
    repo: str
    generated_at: str
    policy_file: str
    total: int = 0
    expired: int = 0
    expiring_soon: int = 0
    violations: int = 0
    oldest_days_to_expiry: int | None = None
    entries: list[dict] = field(default_factory=list)
    framework_violations: list[str] = field(default_factory=list)


def _gh(line: str) -> None:
    print(line)


def _parse_date(value) -> dt.date | None:
    if value is None:
        return None
    if isinstance(value, dt.date):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def load_policy(path: Path) -> tuple[list[dict], list[str]]:
    """Return (vulnerability entries, framework-level violations)."""
    fviol: list[str] = []

    # Legacy flat .trivyignore (bare CVE lines) is forbidden.
    flat = path.parent / ".trivyignore"
    if flat.exists():
        bare = [
            ln.strip()
            for ln in flat.read_text().splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        if bare:
            fviol.append(
                f"legacy flat `{flat}` contains {len(bare)} bare suppression(s) "
                f"with no statement/expiry — migrate to `{path.name}` "
                f"(vulnerabilities: [{{id, statement, expired_at}}])"
            )

    if not path.exists():
        return [], fviol

    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        fviol.append(f"`{path}` is not valid YAML: {e}")
        return [], fviol

    vulns = data.get("vulnerabilities") or []
    if not isinstance(vulns, list):
        fviol.append(f"`{path}`: `vulnerabilities` must be a list")
        return [], fviol
    return vulns, fviol


def wired_guards(workflows_dir: Path) -> set[str]:
    """Guard script paths referenced as `predicate-guard:` in any workflow."""
    refs: set[str] = set()
    for wf in glob.glob(str(workflows_dir / "*.yml")) + glob.glob(str(workflows_dir / "*.yaml")):
        for m in re.finditer(r"predicate-guard:\s*([^\s#]+)", Path(wf).read_text()):
            refs.add(m.group(1).strip().strip("'\""))
    return refs


def evaluate(
    vulns: list[dict],
    *,
    max_ttl_days: int,
    warn_within_days: int,
) -> list[Entry]:
    out: list[Entry] = []
    for v in vulns:
        cid = str(v.get("id", "")).strip() or "<missing-id>"
        statement = str(v.get("statement", "")).strip()
        raw_exp = v.get("expired_at")
        exp = _parse_date(raw_exp)
        guarded_by = (str(v.get("guarded_by")).strip() if v.get("guarded_by") else None)

        status = "ok"
        detail = ""
        days = None

        if not statement or exp is None:
            status = "naked"
            missing = []
            if not statement:
                missing.append("statement")
            if exp is None:
                missing.append("expired_at")
            detail = f"missing {' + '.join(missing)}"
        else:
            days = (exp - TODAY).days
            if days < 0:
                status = "expired"
                detail = f"expired {-days}d ago ({exp.isoformat()})"
            elif days > max_ttl_days:
                status = "over_ttl"
                detail = f"expires in {days}d — exceeds max TTL of {max_ttl_days}d"
            elif days <= warn_within_days:
                status = "expiring_soon"
                detail = f"expires in {days}d ({exp.isoformat()})"
            else:
                detail = f"ok — expires in {days}d"

        out.append(
            Entry(
                id=cid,
                statement=statement,
                expired_at=exp.isoformat() if exp else (str(raw_exp) if raw_exp else None),
                days_to_expiry=days,
                guarded_by=guarded_by,
                status=status,
                detail=detail,
            )
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--policy", default=".trivyignore.yaml",
                    help="Path to the Trivy YAML suppression file.")
    ap.add_argument("--guards-dir", default="ci-guards",
                    help="Directory of predicate-guard scripts.")
    ap.add_argument("--workflows-dir", default=".github/workflows",
                    help="Where to look for predicate-guard wiring.")
    ap.add_argument("--max-ttl-days", type=int, default=90)
    ap.add_argument("--warn-within-days", type=int, default=14)
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "local"))
    ap.add_argument("--report", default="", help="Write JSON report here.")
    args = ap.parse_args()

    policy_path = Path(args.policy)
    vulns, fviol = load_policy(policy_path)
    entries = evaluate(
        vulns,
        max_ttl_days=args.max_ttl_days,
        warn_within_days=args.warn_within_days,
    )

    # Orphan-guard check.
    guards_dir = Path(args.guards_dir)
    if guards_dir.is_dir():
        scripts = {str(p) for p in guards_dir.glob("*.sh")}
        wired = wired_guards(Path(args.workflows_dir))
        for s in sorted(scripts):
            referenced = any(s == w or s.endswith("/" + w) or w.endswith("/" + Path(s).name) or Path(w).name == Path(s).name for w in wired)
            if not referenced:
                fviol.append(
                    f"orphan guard `{s}` — not wired as `predicate-guard:` in any "
                    f"workflow. Wire it or delete it (dead guards protect nothing)."
                )

    # Build report.
    rep = Report(
        repo=args.repo,
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        policy_file=str(policy_path),
        total=len(entries),
        entries=[asdict(e) for e in entries],
        framework_violations=fviol,
    )
    days_list = [e.days_to_expiry for e in entries if e.days_to_expiry is not None]
    rep.oldest_days_to_expiry = min(days_list) if days_list else None
    rep.expired = sum(1 for e in entries if e.status == "expired")
    rep.expiring_soon = sum(1 for e in entries if e.status == "expiring_soon")
    hard = [e for e in entries if e.status in ("naked", "expired", "over_ttl")]
    rep.violations = len(hard) + len(fviol)

    if args.report:
        Path(args.report).write_text(json.dumps(asdict(rep), indent=2))

    # ---- Reporting: step summary + annotations ----
    summary = []
    summary.append("## Security-debt policy check\n")
    summary.append(f"Repo `{rep.repo}` · {rep.total} suppression(s) · "
                   f"{rep.expired} expired · {rep.expiring_soon} expiring soon · "
                   f"{rep.violations} violation(s)\n")
    if entries:
        summary.append("| CVE | status | detail | statement |")
        summary.append("|-----|--------|--------|-----------|")
        for e in entries:
            badge = {
                "ok": "✅ ok", "expiring_soon": "🟡 soon",
                "expired": "🔴 expired", "naked": "❌ naked",
                "over_ttl": "❌ over-ttl",
            }.get(e.status, e.status)
            stmt = (e.statement[:60] + "…") if len(e.statement) > 60 else (e.statement or "—")
            summary.append(f"| `{e.id}` | {badge} | {e.detail} | {stmt} |")
        summary.append("")
    for fv in fviol:
        summary.append(f"- ❌ framework: {fv}")
    sumtxt = "\n".join(summary) + "\n"
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        with open(gh_summary, "a") as fh:
            fh.write(sumtxt)
    else:
        print(sumtxt)

    for e in entries:
        if e.status in ("naked", "expired", "over_ttl"):
            _gh(f"::error::suppression {e.id}: {e.detail}")
        elif e.status == "expiring_soon":
            _gh(f"::warning::suppression {e.id}: {e.detail} — fix or re-justify soon")
    for fv in fviol:
        _gh(f"::error::{fv}")

    # ---- Outputs for the caller / metrics fan-out ----
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as fh:
            fh.write(f"total={rep.total}\n")
            fh.write(f"expired={rep.expired}\n")
            fh.write(f"expiring_soon={rep.expiring_soon}\n")
            fh.write(f"violations={rep.violations}\n")

    if rep.violations:
        _gh(f"::error::security-debt policy FAILED — {rep.violations} violation(s). "
            f"Fix the dep, set a bounded justified expiry, or remove the entry.")
        return 1

    print(f"OK — security-debt policy holds for {rep.repo} "
          f"({rep.total} suppression(s), {rep.expiring_soon} expiring soon).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
