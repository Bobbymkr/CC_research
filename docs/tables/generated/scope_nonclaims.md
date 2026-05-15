# Table D. Scope and Non-Claims

| Claim area | Supported? | Evidence basis | Note |
| --- | --- | --- | --- |
| Adaptive vs static local trade-off | Yes | Local Docker baseline comparison | Core thesis anchor |
| Fresh-account cloud reproducibility | Yes | Single-node replay on a clean AWS Free-plan account | Bounded replay only |
| Bounded multi-node K3s continuity | Yes | 3-node soak, repeated matrix, degraded-mode handling, and drain/reschedule | K3s only; bounded envelope |
| Managed Kubernetes / EKS robustness | No | No EKS evidence bundle exists | Must remain a non-claim |
| Multi-tenant safety | No | No multi-tenant evaluation exists | Must remain a non-claim |
| Production readiness | No | Bounded research-prototype evidence only | Explicitly avoid this claim |
| Broad exfiltration-prevention guarantee | No | Only bounded adversarial matrix coverage exists | Specific workloads only |
| High availability / fault tolerance | No | Drain/reschedule continuity exists, but no HA or SLA evidence | Do not overread the worker-drain result |

## Notes

- This table is helpful in an appendix, rebuttal package, or artifact companion.
- It prevents readers from inferring claims larger than the evidence base.
