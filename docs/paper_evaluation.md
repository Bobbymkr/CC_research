# RAASA Paper Evaluation

## 1. Draft Evaluation Section

This section evaluates whether adaptive containment provides a more balanced
security-utility trade-off than fixed sandbox allocation, and whether the same
architectural approach can carry over from a local container environment into a
live Kubernetes deployment. The evaluation is intentionally bounded. The goal
is not to claim universal cloud-runtime protection, but to test whether RAASA
can (1) outperform static baselines in the local setting, (2) preserve benign
utility while still containing malicious behavior, and (3) demonstrate
pod-specific containment behavior in a live AWS-hosted Kubernetes path.

### 1.1 Evaluation Questions

The evaluation is organized around four questions:

1. Can adaptive containment outperform static baselines in a controlled local
   environment?
2. Can RAASA preserve benign workload utility while still containing malicious
   behavior?
3. Can the architecture carry over from local Docker-based execution into a
   live Kubernetes environment?
4. What currently limits the cloud-native path, even when the core containment
   idea appears to work?

### 1.2 Experimental Framing

The local evaluation compares three control modes over identical workload
profiles:

- `static_L1`, representing a permissive baseline with no meaningful
  containment response
- `static_L3`, representing an over-restrictive baseline that applies strict
  containment unconditionally
- `raasa`, representing the adaptive controller

The key scenario used for the paper is `small_tuned`, which captures the core
adaptive-vs-static trade-off without introducing unnecessary scale complexity
into the main experimental story. This evaluation profile includes both benign
and malicious behaviors so that the controller is forced to make selective
decisions rather than receiving a trivial all-benign or all-malicious input
stream.

The cloud evaluation extends the architecture into an AWS-hosted K3s
environment. In that setting, the local Docker telemetry path is replaced by a
Kubernetes-oriented observer path, and enforcement is routed through a
privilege-separated sidecar responsible for live containment actions. The main
cloud question is therefore not just whether RAASA can assign tiers, but
whether those assignments can be converted into pod-specific live enforcement
behavior without collapsing the architecture into an unsafe monolithic control
model.

### 1.3 Local Baseline: Static L1

The `static_L1` baseline represents under-reaction. In this mode, workloads are
effectively allowed to continue without adaptive containment. As a result, the
controller does not meaningfully stop or constrain malicious behavior. In the
captured evaluation summary, this baseline shows `0.0 / 0.0` precision and
recall with a `0.0%` malicious containment rate. The main implication of this
result is not merely that an open sandbox is permissive, but that it fails to
provide any credible response when workload behavior clearly drifts into abuse.

This baseline is necessary because it establishes the lower bound of the design
space. A permissive sandbox maximizes short-term utility, but it does so by
giving up meaningful runtime containment. For the paper, `static_L1` should be
interpreted as the "do not adapt, do not intervene" extreme.

### 1.4 Local Baseline: Static L3

The `static_L3` baseline represents the opposite failure mode: over-reaction.
Instead of missing malicious behavior, it applies strict containment to
everything from the beginning of execution. In the evaluation summary, this
mode achieves full recall against malicious behavior, but at the cost of
`100%` false positives and `100%` benign restriction. In effect, it secures the
environment by assuming every workload must be treated as hostile.

This result is important because it clarifies that the relevant comparison is
not simply "security" versus "insecurity." A static strict sandbox can indeed
stop abuse, but it does so by collapsing benign utility. From a systems
perspective, this is not a practical success condition for modern container or
agentic runtimes, where legitimate workloads often require bursts of compute,
installation steps, or transient changes in behavior.

### 1.5 Adaptive Controller: RAASA in the Local Path

The adaptive `raasa` mode is the primary local result. In the captured local
evaluation summary, it achieves `1.0 / 1.0` precision and recall, `0.0` false
positive rate, `0.0` benign restriction rate, zero unnecessary escalations, and
full explanation coverage. These results support the central thesis of the
paper: adaptive containment can outperform both static permissiveness and
static strictness by selectively escalating only the workloads whose behavior
justifies tighter control.

The most important point is not the numerical perfection alone, but the shape
of the trade-off. Under the evaluated scenario, RAASA preserves the operational
freedom of benign workloads while still isolating malicious behavior into the
strictest tier. This is precisely the balance that static baselines fail to
achieve. In paper terms, the local evaluation is the clearest evidence that
adaptive containment is worth considering as a distinct security paradigm
rather than as a small variation on conventional static sandboxing.

### 1.6 Why the Local Results Matter

The local results establish the conceptual validity of the architecture. They
show that RAASA is not merely a telemetry collector or a logging system, but an
actual runtime controller capable of making selective containment decisions. In
particular, they support three claims:

1. adaptive control can outperform both static permissive and static strict
   baselines under the bounded workload model
2. the risk-to-tier pipeline is operationally meaningful rather than cosmetic
3. auditable decisions can coexist with effective containment rather than being
   treated as a post hoc reporting feature

These claims are the foundation for extending the architecture into the
cloud-native path.

### 1.7 Cloud-Native Extension: AWS-Hosted K3s

To evaluate whether the architecture remains meaningful outside the local
Docker-based path, RAASA is extended into an AWS-hosted K3s environment. In
this configuration, the controller shifts from the local runtime model toward a
Kubernetes-native execution path in which workload observation and enforcement
must operate under different practical constraints. This matters because many
modern cloud workloads do not run in a simple local container context; they run
under an orchestration layer where pod identity, namespace context, and
pod-specific network behavior must all be resolved correctly for containment to
remain precise.

The strongest paper-safe cloud claim is not that the entire Kubernetes path is
production-ready. Rather, it is that RAASA can perform pod-specific containment
in a live Kubernetes environment while maintaining a privilege-separated
controller/enforcer architecture. This is a narrower claim than broad
cloud-security readiness, but it is also the claim most strongly supported by
the evidence.

### 1.8 Pod-Specific Containment Behavior

The AWS results show that significant effort was required to move from generic
interface-level enforcement toward pod-specific containment resolution. That
work matters because broad network manipulation on a shared host interface is
not the same as precisely containing a targeted workload. The live cloud
artifacts record a progression from early enforcement ambiguity toward
pod-specific host-veth resolution, including corrections to interface mapping
logic and validation of the final resolution path against benchmark workloads.

This progression is important to describe honestly in the paper. It strengthens
the final result rather than weakening it, because it shows that the project
did not hide resolution failures or paper over incorrect enforcement behavior.
Instead, the cloud-native evaluation surfaces the engineering difficulty of
translating adaptive policy decisions into precise live containment on a real
Kubernetes node.

### 1.9 L3 Semantics in the Live Path

One of the most important cloud findings concerns the meaning of `L3` in the
live Kubernetes path. Early descriptions of the cloud-native enforcement path
could be interpreted as simple bandwidth shaping. However, the refined live
validation shows that the effective `L3` behavior is stronger than that. In the
validated live path, `L3` acts as hard containment: service resolution fails,
service and direct pod reachability fail, and network behavior is disrupted in
a way that is more accurately described as containment than as throughput
reduction alone.

This distinction matters for the paper because it changes how reviewers should
interpret the enforcement tier. The correct framing is not "RAASA slows down a
malicious pod," but "RAASA can drive a workload into a live containment state
that disrupts its network reachability in the validated Kubernetes path."

### 1.10 Cloud Stability Evidence

The strongest later-stage stability evidence in the repo is the repeated
closed-loop soak result on the AWS testbed. The current captured summary shows
`10 / 10` passing soak cycles on `2026-05-09`, with per-cycle audit capture.
This does not prove broad production stability, but it does strengthen the case
that the cloud path is more than a single isolated successful run. For the
paper, this soak evidence should be used as support for repeatability on the
single-node live testbed rather than as proof of generalized operational
robustness.

### 1.11 Controller Truthfulness and Calibration

An important part of the evaluation story is that the project ultimately
converged on the tuned linear controller as the truthful primary controller for
the paper. The AWS evidence records that the ML path was explored, deployed,
and then deliberately reframed as secondary once the live evidence showed that
the strongest and most defensible controller story remained the tuned linear
path. This is a strength of the evaluation, because it demonstrates disciplined
experimental correction instead of narrative overfitting.

The calibration work in the live environment also matters. The evidence shows
that the strongest truthful live controller story required specific parameter
tuning, probe-path correction, and a clearer understanding of how benign and
malicious behaviors appeared under the Kubernetes path. As a result, the paper
should not describe the controller as universally self-tuning. It should
describe the tuned linear controller as the most defensible current default,
and the calibration process as part of the real cost of moving adaptive
containment into a cloud-native setting.

### 1.12 Main Limitation Exposed by Evaluation

The most important limitation revealed by the evaluation is not that adaptive
containment fails conceptually. It is that the cloud-native telemetry and
control-plane path remains operationally fragile under stress. In the AWS
artifacts, repeated `metrics.k8s.io` timeout behavior appears as the dominant
technical blocker. This issue matters because even a correct containment policy
loses practical strength if the telemetry path used to support it becomes
unstable in live execution.

For that reason, the correct evaluation conclusion is not that RAASA has
completed the transition from local research prototype to fully hardened
Kubernetes security platform. The correct conclusion is that the project has
validated the architectural viability of adaptive containment across local and
live Kubernetes settings, while also identifying telemetry/control-plane
fragility as the primary barrier to a stronger v2 candidate.

### 1.13 Evaluation Summary

Taken together, the evaluation supports four main conclusions. First, adaptive
containment is superior to both static permissive and static strict baselines
under the bounded workload model used in the paper. Second, RAASA can preserve
benign utility while still containing malicious behavior in the local path.
Third, the architecture can carry over into a live AWS-hosted Kubernetes path
with pod-specific containment behavior and repeatable closed-loop evidence.
Fourth, the strongest remaining limitation lies in the telemetry/control-plane
path rather than in the core adaptive-containment idea itself.

These conclusions give the paper a stable empirical shape: RAASA is best
understood as a validated research prototype that demonstrates the feasibility
of adaptive, auditable, privilege-separated containment for modern container
and agentic workloads.

## 2. Notes for Revision

When this section is integrated into the final paper:

- add inline citations to the exact local summary and AWS evidence bundles
- replace broad phrases like "captured evaluation summary" with concrete table
  or figure references
- keep the cloud limitation paragraph intact
- avoid turning the soak result into a multi-node or production claim
