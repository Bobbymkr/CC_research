# Future Work And Further Testing

## Future work already suggested by the repo itself

The project materials point to a clear next roadmap:

1. strengthen syscall-grounded signals with richer real probe data,
2. improve network-aware detection and containment,
3. extend containment beyond CPU throttling in the local path,
4. mature the Kubernetes backend and sidecar enforcement model,
5. improve operator review and approval workflows,
6. continue larger-scale and more adversarial testing.

Supporting source files:

- `docs/next_generation_roadmap.md`
- `docs/future_implementation.md`
- `docs/live_experiment_notes.md`

## Areas that need more testing before stronger claims

### 1. Cross-environment reproducibility

The strongest evidence currently comes from curated local Docker experiments plus selected cloud-native artifacts. The next paper-ready step is broader rerun coverage:

- repeated K8s runs with complete summaries,
- same scenario across different Linux hosts,
- confirmation that metrics are stable across runtime environments.

### 2. Adversarial workload diversity

Current scenarios are useful, but a stronger paper would test more:

- stealthy low-and-slow attacks,
- mixed CPU and network abuse,
- staged privilege-escalation simulations,
- workloads that deliberately mimic benign burst patterns.

### 3. False-positive characterization

The medium and large scenarios show small but nonzero benign restriction cost. A stronger follow-up should ask:

- which benign classes trigger most false positives,
- whether `benign_bursty` dominates the residual cost,
- whether new features or threshold tuning can reduce that cost without harming recall.

### 4. Cloud-native enforcement realism

The K8s path should be stressed with:

- repeated DaemonSet deployments,
- more pod classes and namespaces,
- better pod-to-interface resolution,
- clearer proof of per-pod rather than node-wide network shaping where possible.

### 5. End-to-end operational overhead

The packet includes monitor-overhead evidence, but a stronger systems paper would add:

- per-iteration latency distributions across scales,
- enforcement latency by tier transition,
- overhead under sustained K8s load,
- resource overhead of the privileged sidecar architecture.

### 6. Approval and human-in-the-loop safety

The policy layer already has approval-related logic in the repo. Follow-up work should test:

- operator approval delays,
- rejected escalations,
- how approval gating changes containment speed and safety.

## Research directions that could make this project genuinely stronger

### Better telemetry semantics

- richer syscall semantics,
- file-system behavior that is actually implemented and measured,
- cgroup and network patterns tied more directly to abuse classes,
- integration with tools like Tetragon as high-confidence evidence sources.

### Better risk modeling

- keep the tuned linear controller as the baseline,
- only replace it when a new model clearly beats it on recall, false-positive cost, and stability,
- test hybrid designs where learned models assist but do not dominate the safety-critical path.

### Better containment semantics

- finer per-tier controls,
- more explicit network isolation policies,
- stronger mapping between policy tier and real cloud enforcement actions.

## What this project could help achieve in the future

If matured, RAASA-like systems could help achieve:

- adaptive containment for AI agent runtime platforms,
- safer code-execution sandboxes that preserve utility when benign and tighten rapidly when behavior drifts,
- cloud node agents that act as bounded autonomous intrusion-prevention layers,
- auditable human-reviewable security automation rather than opaque autonomous blocking.

## Best future-work paragraph for the paper

RAASA should be presented as a strong prototype and research direction rather than a finished platform. The next phase is to deepen telemetry fidelity, harden the cloud-native enforcement path, broaden adversarial testing, and prove that adaptive containment remains stable and low-cost across repeated multi-node experiments. The most important scientific lesson so far is that a disciplined, auditable, closed-loop controller can outperform static containment, but the strongest controller in the current evidence base is still the tuned linear path, not the more ambitious learned alternative.
