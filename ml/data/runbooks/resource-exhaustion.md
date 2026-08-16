# Runbook: CPU / Memory Resource Exhaustion

## Symptoms
CPU or memory utilization climbs steadily (or spikes sharply) toward the instance
limit, often followed by throttling, OOM kills, or cascading latency/error symptoms
in the same service.

## Likely causes
- A memory leak in a recent deploy (unbounded cache, unclosed connections/handles,
  growing in-memory collection).
- A traffic surge pushing genuine load past provisioned capacity.
- A CPU-bound regression (an accidentally quadratic algorithm, a busy-loop, excessive
  logging/serialization on the hot path).
- Missing or misconfigured autoscaling.

## Diagnostic steps
1. Check the trend shape: a slow steady climb suggests a leak; a sudden step suggests
   a traffic surge or a specific deploy.
2. Correlate against the deploy timeline.
3. Check autoscaling policy — did it fail to trigger, or is it maxed out?
4. Profile the process (heap dump / CPU profile) if a leak is suspected.

## Mitigation
- Restart affected instances as an immediate stopgap (clears leaked memory) while the
  root cause is fixed.
- Roll back the suspect deploy if the timeline lines up.
- Raise autoscaling limits or add capacity if it's genuine load growth.
