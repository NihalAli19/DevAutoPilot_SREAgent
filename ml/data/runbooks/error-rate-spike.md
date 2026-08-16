# Runbook: Elevated Error Rate

## Symptoms
5xx (or application-level failure) rate rises above baseline for a service. May be
sudden (a bad deploy) or gradual (a dependency degrading, a resource leak).

## Likely causes
- A recent deploy shipped a regression (unhandled exception, bad config, broken
  feature flag).
- A downstream dependency is returning errors or timing out.
- A resource leak (connections, file handles, memory) eventually causes failures
  under load.
- A schema/contract mismatch after a partial rollout (old and new versions disagree).

## Diagnostic steps
1. Check the deploy timeline against the error-rate inflection point.
2. Group errors by type/stack trace — one dominant error class points at a single
   root cause; many different errors points at resource exhaustion or infra issues.
3. Check downstream dependency health dashboards for correlated errors.
4. Check recent config/feature-flag changes.

## Mitigation
- Roll back the most recent deploy if timing lines up.
- Disable the implicated feature flag.
- Add/verify retries with backoff for transient downstream errors; escalate to the
  owning team if the dependency itself is down.
