# Table 1 Draft - Capability Gap Matrix

Use this as the structured replacement for the missing "Table 1" referenced in the draft.
This table is aligned to the current RAASA paper position and should be pasted into the manuscript as a formatted table.

## Table 1. Capability comparison of representative container security approaches versus RAASA

Legend:

- `Yes` = clearly supported by the cited tool description in the current paper materials
- `No` = clearly not the tool's main capability
- `Partial` = present in limited or non-central form
- `Prototype` = implemented in RAASA as a research prototype path, not yet broad production proof

| Capability | Falco / Sysdig-style runtime detection | Kata / gVisor / Firecracker | Tetragon | eBPF-PATROL | RAASA |
|---|---|---|---|---|---|
| Continuous quantitative risk score from multiple signals | No | No | No | Partial | Yes |
| Graduated isolation tiers instead of binary allow / block or fixed isolation | No | No | No | No | Yes |
| Runtime adaptation based on observed behavior | Partial | No | Partial | Partial | Yes |
| Explicit closed-loop controller (observe -> assess -> decide -> act -> audit) | No | No | No | Partial | Yes |
| Real-time enforcement without killing the workload by default | Partial | No | Partial | Partial | Yes |
| Dynamic resource containment (CPU / memory shaping) | No | No | Partial | No | Yes |
| Dynamic network containment | No | No | Partial | Partial | Yes |
| Full audit trail with reasoned policy output | Partial | No | Partial | Partial | Yes |
| Zero-trust separation between reasoning and privileged enforcement | No | No | No | No | Prototype |

## Suggested paper reading text

Table 1 situates RAASA against representative detection-only tools, fixed strong-isolation runtimes, production eBPF enforcement systems, and the closest recent adaptive eBPF research. Existing tools cover important parts of the problem, but none combine multi-signal quantitative risk scoring, graduated tiered containment, explicit closed-loop policy reasoning, and dynamically applied resource and network controls in a single adaptive framework. RAASA is designed to occupy that gap, with the additional architectural contribution of a zero-trust sidecar path that decouples unprivileged reasoning from privileged enforcement.

## Notes for careful use

- Keep Kata / gVisor / Firecracker grouped if space is tight; the point is "fixed strong isolation," not fine-grained differentiation between those runtimes.
- Do not overclaim that every RAASA cell is production-grade. In particular, the final row should be discussed as a prototype architectural contribution.
- If reviewers push on eBPF-PATROL, the safest distinguishing line is:
  RAASA's core novelty is not "uses eBPF," but "maps telemetry to graduated adaptive containment through an explicit policy loop."

## Short caption

Table 1. Capability comparison of representative container security approaches and RAASA. RAASA's distinguishing contribution is the combination of multi-signal quantitative risk scoring, graduated adaptive containment, explicit policy safety rules, and a prototype zero-trust enforcement path.
