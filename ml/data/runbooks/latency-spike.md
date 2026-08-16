# Runbook: Service Latency Spike (p95/p99)

## Symptoms
p95 or p99 latency rises well above baseline for a service (e.g. checkout, payments)
while error rate stays flat. Often correlates with a deploy, a traffic surge, or a
downstream dependency slowing down.

## Likely causes
- A recent deploy introduced a slow code path (missing index, N+1 query, synchronous
  call that used to be async).
- A downstream dependency (database, cache, third-party API) is degraded.
- Connection pool exhaustion under increased load, causing queueing.
- GC pauses or CPU throttling on the host/container.

## Diagnostic steps
1. Check the deploy timeline — did latency start rising right after a release?
2. Compare p95 latency against the same service's downstream dependencies; isolate
   which hop in the call chain is slow.
3. Check database slow-query logs and connection pool saturation.
4. Check CPU/memory utilization and GC metrics on the affected instances.

## Mitigation
- If tied to a deploy: roll back the deploy first, then investigate offline.
- If a downstream dependency is slow: fail over, add a circuit breaker, or degrade
  gracefully (serve cached/stale data) until the dependency recovers.
- If pool exhaustion: scale out replicas or raise pool limits as a stopgap, then fix
  the root query/call pattern.
