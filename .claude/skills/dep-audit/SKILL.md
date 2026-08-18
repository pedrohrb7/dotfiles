---
name: dep-audit
description: Audit project dependencies for outdated, unmaintained, or vulnerable packages before shipping. Use when user says "audit deps", "check dependencies", or "security audit".
disable-model-invocation: true
---

# Dep Audit

1. Run the project's native audit tool (npm/pnpm audit, pip-audit, cargo audit, govulncheck, etc.), detected from its lockfile/manifest.
2. Cross-check flagged packages: is the vulnerable code path actually reachable, or is it a transitive dep behind an unused feature?
3. For outdated-but-not-vulnerable packages, note how far behind they are and whether upgrading is a breaking major bump.
4. Report findings ranked by real risk, not raw count. Recommend concrete upgrade or replacement actions.

Never run a command that auto-upgrades packages without first listing what it will change.
