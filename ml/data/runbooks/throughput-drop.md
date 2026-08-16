# Runbook: Throughput Drop

## Symptoms
Request/transaction volume for a service drops well below its expected baseline for
the time of day, without a corresponding drop in upstream traffic.

## Likely causes
- An upstream service or load balancer is failing to route traffic (misconfigured
  routing rule, unhealthy targets removed from rotation).
- The service itself is unhealthy and failing readiness checks, so it's pulled from
  the pool.
- A queue/consumer is stalled (e.g. a worker deadlocked or crashed without restart).
- An upstream client-side change reduced call volume (e.g. a caching layer added
  upstream, or a batch job stopped running).

## Diagnostic steps
1. Check instance/pod health and readiness-probe status — are healthy instances being
   pulled from the load balancer?
2. Check upstream traffic volume — is less traffic arriving at all, or is it arriving
   but not reaching this service?
3. Check queue depth and consumer lag if the service is queue-driven.
4. Check for recent infra changes (routing rules, DNS, service mesh config).

## Mitigation
- Restore healthy instances to the pool; fix the readiness check if it's a false
  negative.
- Restart stalled consumers/workers.
- Revert recent routing/infra config changes.
