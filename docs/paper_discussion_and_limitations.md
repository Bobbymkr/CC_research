# RAASA Paper Discussion and Limitations

## 1. Draft Discussion and Limitations Section

The evaluation suggests that RAASA is best understood as a validated research
prototype for adaptive containment rather than as a finished cloud-security
product. This distinction is important. The strongest contribution of the
project is not that it solves runtime security in full, but that it
demonstrates a more balanced model of containment than static sandbox
allocation. Across the bounded evaluation setting, RAASA shows that it is
possible to preserve benign utility while still escalating malicious behavior
into stricter containment tiers. This is the central conceptual result of the
paper.

### 1.1 What the Results Mean

The most important outcome is that adaptive containment appears to occupy a
useful middle ground between permissive and over-restrictive execution models.
The static baselines illustrate the two extremes clearly. A permissive sandbox
maximizes short-term execution freedom, but it provides no credible response to
runaway or malicious behavior. A uniformly strict sandbox improves containment,
but does so by collapsing benign utility and making legitimate workloads pay
the same cost as obviously harmful ones. RAASA's local results suggest that
this trade-off is not inevitable. Under the bounded workload model used here,
the controller can distinguish between behaviors well enough to preserve benign
execution while still escalating the workloads that warrant tighter control.

From a research perspective, this matters because it reframes containment as a
runtime control problem rather than a static policy-selection problem. The
project does not argue that a single sandbox profile can be tuned perfectly in
advance for all workloads. Instead, it argues that containment should adapt as
workload behavior changes, and that such adaptation can be implemented in an
auditable way. This is particularly relevant for modern cloud and agentic
workloads, whose execution profiles are often dynamic, bursty, and difficult to
characterize with a single fixed restriction level.

### 1.2 Why the Architecture Matters

The architectural shape of RAASA is also part of the contribution. The system
is not merely a detector attached to a logger, nor is it simply a privileged
throttling wrapper. Its structure as an Observe-Assess-Decide-Act-Audit loop
allows the project to separate measurement, reasoning, enforcement, and
accountability into explicit layers. This separation has two practical
benefits. First, it makes the research artifact easier to reason about because
each stage can be evaluated and tuned independently. Second, it supports safer
system design, especially in the cloud-native path, where the privileged
enforcement role is decoupled from the unprivileged reasoning path.

This privilege separation is especially important in the context of agentic
runtime security. If a system is meant to respond autonomously to workload
behavior, it becomes risky to let the same reasoning component hold unrestricted
host-level power. RAASA's sidecar-based enforcement path does not eliminate
that risk entirely, but it gives the project a more defensible architecture
than an all-in-one privileged agent design. For the purposes of this paper,
that is a meaningful systems contribution even independent of the raw
performance results.

### 1.3 Why the Cloud Result Is Important

The AWS-hosted Kubernetes path matters because it tests whether the core idea
survives outside a local container harness. The live cloud-native result is not
important because it proves full production readiness; it is important because
it shows that adaptive containment decisions can be translated into pod-specific
live enforcement behavior in a real orchestration environment. This is a higher
bar than demonstrating a local runtime loop alone. Once containment must be
resolved at pod scope under Kubernetes, the system must handle real identity,
resolution, and enforcement-path complexity rather than simply modifying a
single local runtime abstraction.

The cloud result therefore strengthens the paper's claim in a specific way. It
supports the statement that RAASA is not confined to toy local execution. At
the same time, it also exposes the engineering costs of carrying adaptive
containment into a live Kubernetes setting. This dual outcome is useful: the
paper can claim architectural viability in the cloud-native path while still
acknowledging that viability is not the same thing as operational maturity.

### 1.4 Main Limitation: Telemetry and Control-Plane Fragility

The clearest limitation of the current system is the live Kubernetes telemetry
and control-plane path. The strongest evidence in the repo indicates that the
main blocker is not the basic containment idea, but instability around the
telemetry/control-plane interface, especially repeated `metrics.k8s.io`
timeouts under stress. This limitation matters because adaptive containment is
only as strong as the observation path that supports it. If the controller
cannot reliably obtain or recover the telemetry it depends on, then even a
correct policy design becomes operationally fragile.

This limitation should be presented directly rather than softened. In fact, it
improves the paper's credibility to say so plainly. The project does not fail
because adaptive containment is conceptually weak; it remains incomplete
because live cloud-native telemetry is operationally harder to stabilize than
the local path. This distinction is important. It keeps the paper's argument
focused on what has and has not been validated, and it makes future work more
concrete.

### 1.5 Scope Limitations

Several additional limitations should be stated explicitly.

First, the cloud-native validation is currently grounded in a single-node live
testbed rather than a multi-node or multi-tenant deployment. This means the
project cannot yet make broader claims about distributed contention, cluster-
wide scaling behavior, or multi-tenant blast-radius guarantees.

Second, the workload model is intentionally bounded. The paper focuses on a
small number of workload classes chosen to make the adaptive trade-off visible
and measurable. This is appropriate for a research prototype, but it also means
the results should not be interpreted as a universal coverage claim for all
container threats.

Third, the strongest validated controller story is the tuned linear controller,
not the ML path. The Isolation Forest path is implemented and explored, but the
current evidence does not support presenting it as the primary source of the
system's effectiveness. The paper should therefore treat ML as an extension
path rather than the main basis of the evaluation.

Fourth, the LLM advisor is optional and secondary. It may be relevant to
forward-looking discussions about ambiguous runtime decisions or agentic safety,
but it is not the centerpiece of the current empirical story. Over-centering it
would weaken the paper by shifting attention away from the strongest validated
evidence.

### 1.6 Why the Limitations Do Not Undermine the Contribution

These limitations do not invalidate the research contribution. Instead, they
define its proper boundary. The goal of the paper is not to claim that RAASA
has solved cloud-runtime security in the general case. The goal is to show that
a modular, auditable, adaptive containment loop can be built and validated in a
way that is more truthful and more practically useful than static baselines.

Within that boundary, the results remain meaningful. The local experiments
support the adaptive-containment thesis directly. The cloud-native path shows
that the architecture can move beyond local runtime control into live
pod-specific containment behavior. The limitations then explain what still
separates the current system from a stronger v2 candidate. That is a coherent
and credible research story.

### 1.7 Implications for AI-Agent Runtime Security

One of the broader implications of the work is that adaptive containment may be
particularly relevant for AI-agent execution environments. These systems often
need to perform actions that look resource-intensive or operationally unusual
even when they are benign, such as compiling code, installing dependencies, or
running transient automation steps. Static containment policies may therefore
misclassify legitimate activity as hostile or, conversely, may remain too open
until obviously harmful behavior has already progressed.

RAASA does not fully solve this problem today, but it offers a defensible
direction for studying it. By framing the runtime as a control loop with
auditable tier transitions, the project provides a structure that could later
support more realistic agent-specific benchmarks. In that sense, the paper's
value is not only in the immediate local and Kubernetes results, but also in
the clearer research path it creates for future agent-runtime safety work.

### 1.8 Discussion Summary

In summary, the discussion supports four points. First, adaptive containment is
a meaningful alternative to static permissive and static strict sandbox
allocation. Second, RAASA's modular and privilege-separated architecture is
itself part of the paper's contribution. Third, the live AWS-hosted Kubernetes
path materially strengthens the research story by validating pod-specific
containment behavior beyond the local environment. Fourth, the strongest
remaining weakness lies in telemetry and control-plane fragility, not in the
basic adaptive-containment concept. Taken together, these points position RAASA
as a credible research artifact with a clear boundary, a concrete systems
contribution, and a practical path toward a stronger v2.

## 2. Notes for Revision

When this section is integrated into the final paper:

- keep the limitation language explicit
- preserve the tuned-linear-versus-ML distinction
- retain the single-node limitation
- avoid broadening the claim into enterprise readiness
