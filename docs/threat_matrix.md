# RAASA v1 Threat-to-Signal-to-Action Matrix

| Workload class | Observable signals | Expected risk pattern | Intended response | Residual limitation in v1 |
| --- | --- | --- | --- | --- |
| `benign_steady` | low CPU, low memory, low process growth | consistently low | remain `L1` | cannot prove deeper syscall safety |
| `benign_bursty` | temporary CPU spikes, limited process growth | transient medium | occasional `L2`, then relax | cannot distinguish every benign burst from early abuse |
| `suspicious` | sustained moderate CPU/process deviation | medium and persistent | move to `L2` | richer network and syscall context still depends on backend signal quality |
| `malicious_pattern` | strong sustained CPU abuse and elevated process behavior | high and persistent | move to `L3` | current `L3` is hard containment, not yet a broader kill or quarantine primitive |
| `agent_dependency_exfiltration` | dependency-index access pattern plus repeated outbound transfer attempts | high when sustained network/process behavior is visible | move to `L3` in agent-misuse benchmark runs | synthetic benchmark; uses fake token material and does not prove general exfiltration prevention |

RAASA v1 is intentionally scoped to the threat classes it can measure honestly.
