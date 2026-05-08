# RAASA v1 Threat-to-Signal-to-Action Matrix

| Workload class | Observable signals | Expected risk pattern | Intended response | Residual limitation in v1 |
| --- | --- | --- | --- | --- |
| `benign_steady` | low CPU, low memory, low process growth | consistently low | remain `L1` | cannot prove deeper syscall safety |
| `benign_bursty` | temporary CPU spikes, limited process growth | transient medium | occasional `L2`, then relax | cannot distinguish every benign burst from early abuse |
| `suspicious` | sustained moderate CPU/process deviation | medium and persistent | move to `L2` | no network or syscall context yet |
| `malicious_pattern` | strong sustained CPU abuse and elevated process behavior | high and persistent | move to `L3` | containment is CPU-only in v1 |

RAASA v1 is intentionally scoped to the threat classes it can measure honestly.
