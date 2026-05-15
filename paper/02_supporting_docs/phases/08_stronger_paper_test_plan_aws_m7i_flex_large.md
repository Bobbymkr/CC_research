# Stronger Paper Test Plan For AWS `m7i-flex.large`

## Executive take

If your goal is to make the paper meaningfully stronger, the next testing direction should **not** be "add more random experiments." It should be:

1. prove the **cloud-native telemetry path is actually live**,
2. prove the **closed-loop controller behaves correctly on Kubernetes**,
3. prove enforcement is **targeted to the right workload** and not just the whole node,
4. collect **repeatable baseline vs adaptive evidence** on AWS,
5. measure **overhead and failure behavior** honestly.

That is the shortest path from "interesting prototype" to "credible systems/security paper."

## Why this is the right direction

From the latest v2+ evidence already in this repo:

- the sidecar/enforcer architecture is alive,
- the malicious pod can be held at `L3`,
- but telemetry is incomplete (`metrics_unavailable`, `probe_missing`),
- and the newest K8s validation exposed a correctness gap in the benign stress test,
- and the current `tc` logic strongly suggests a possible **node-wide shaping risk** instead of true per-pod targeting.

As a reviewer, I would care about these questions more than anything else:

1. Is the K8s path using the intended signals, or mostly running degraded?
2. When RAASA says it is isolating a workload, is it isolating **that workload** or the **whole node**?
3. Does adaptive RAASA beat static baselines in the actual cloud-native setting, not just Docker?
4. How much overhead does the controller introduce?
5. How does the system fail when telemetry or enforcement components disappear?

Those are the experiments that will move the paper the most.

---

## Constraints and what they imply

### Your environment

- budget source: `$100` AWS credits
- available instance: `m7i-flex.large`
- practical shape: **single-node K3s on one EC2 instance**

### What this means for the plan

- Do **not** build a multi-node story first.
- Do **not** spend credits on EKS, ALB, NAT Gateway, or managed extras.
- Do **not** rely on internet-heavy traffic generators like repeated external downloads.
- Do **not** make the next phase about ML tuning; the current evidence already says the tuned linear controller is stronger.

### What this instance is good for

`m7i-flex.large` is enough for:

- one-node K3s,
- RAASA DaemonSet,
- test pods,
- Prometheus/Grafana when needed,
- repeated short experiment runs,
- overhead and failure-injection tests.

It is **not** the right machine for a large-scale distributed story. So the paper should aim for:

- **depth of evidence**,
- **correctness of control loop**,
- **clarity of limitations**,

not "huge cluster scale."

---

## The highest-value testing priorities

If you only do three things, do these:

1. **Telemetry integrity test**  
   Show that Metrics API, cAdvisor network, and syscall probe data are actually being consumed in K8s runs.

2. **Enforcement specificity test**  
   Prove whether `L3` containment affects only the target pod or unintentionally shapes the whole node.

3. **Repeatable K8s adaptive-vs-static comparison**  
   Run small repeated K8s experiments with `static_L1`, `static_L3`, and `raasa`, then summarize them the same way you already did for Docker.

If these three land, the paper becomes much harder to dismiss.

---

## Recommended experiment roadmap

## Phase 0 - Clean the K8s evaluation foundation

### Goal

Make sure the AWS/K8s environment is producing trustworthy evidence before running more experiments.

### Why it matters

Right now the latest K8s run shows:

- `network_status = metrics_unavailable`
- `syscall_status = probe_missing`
- some pods missing `workload_class` / `expected_tier`

If those remain unfixed, many later results will be scientifically weaker.

### Tasks

1. Ensure every test pod has:
   - `raasa.class`
   - `raasa.expected_tier`
   - stable, explicit pod names or labels

2. Confirm Metrics Server is working:
   - `kubectl top pods -A`
   - `kubectl top nodes`

3. Confirm cAdvisor network metrics are reachable from the observer path.

4. Confirm syscall probe files are being created under `/var/run/raasa/<pod-id>/syscall_rate`.

5. Capture a short 2-3 minute validation run and check that audit logs contain:
   - nonzero network signal when running internal traffic,
   - non-missing syscall probe status when syscall probe is enabled.

### Acceptance criteria

- `kubectl top` returns valid CPU/memory for test pods
- at least one network-heavy pod shows nonzero `net_rx` / `net_tx`
- at least one probe-enabled pod shows `syscall_status = probe_ok`
- all evaluated pods have correct metadata labels

### Paper value

Very high. This converts vague "K8s support exists" into "the intended telemetry pipeline was actually live."

### Estimated effort

- `0.5-1 day`

---

## Phase 1 - Redesign the test expectations to match the research claim

### Goal

Make sure your tests validate the right scientific behavior, not a misleading expectation.

### Important insight

Your latest test expected a **benign pod under 95% CPU stress** to hit `L3`.

That may not actually be the best research expectation.

A stronger paper story is usually:

- benign steady workload -> stay `L1`
- benign high-compute batch-style workload -> maybe `L2`, but ideally **not** `L3`
- suspicious/process-growth workload -> `L2`
- clearly malicious CPU/process/syscall/network abuse -> `L3`

If a purely benign CPU-heavy task always goes to `L3`, reviewers can argue RAASA is overreacting to legitimate compute.

### Recommendation

Split the current stress test into two different expected behaviors:

1. **Benign compute-heavy**  
   Expected: stay `L1` or escalate to `L2`, but avoid `L3`

2. **Malicious abuse-heavy**  
   Expected: reach `L3`

### Acceptance criteria

- your test suite expectations align with the threat model, not just raw CPU saturation

### Paper value

High. This improves scientific framing and reduces the risk of writing a misleading claim.

### Estimated effort

- `0.25 day`

---

## Phase 2 - Closed-loop correctness on Kubernetes

### Goal

Show that the K8s path behaves correctly on a set of controlled workload classes.

### Workload set to use on `m7i-flex.large`

Keep it small and controlled:

1. `benign_steady`
2. `benign_compute_heavy`
3. `suspicious_process_growth`
4. `malicious_cpu_fanout`
5. `malicious_network_heavy_internal`
6. `malicious_syscall_heavy`

Do **not** run all of these at once initially. Start with 3-4 pods.

### Recommended test matrix

#### Test A - Steady benign

- workload: low CPU, low network
- expected: remain `L1`

#### Test B - Benign compute-heavy

- workload: high CPU but no suspicious network/syscall pattern
- expected: at most `L2`

#### Test C - Suspicious process fan-out

- workload: subprocess growth
- expected: `L2`

#### Test D - Malicious CPU + process abuse

- workload: stress + fan-out
- expected: `L3`

#### Test E - Malicious network-heavy internal exfil simulation

- workload: internal file transfer or `iperf3` flood inside the cluster
- expected: `L3`

#### Test F - Malicious syscall-heavy

- workload: metadata/syscall storm
- expected: `L3`

### Artifact collection for every run

- JSONL audit log
- `kubectl top pods -A` snapshots
- agent log
- enforcer log
- Prometheus scrape snapshot if enabled
- short markdown note with expected vs observed tier transitions

### Acceptance criteria

- expected tier behavior matches the threat model for each case
- malicious classes consistently reach `L3`
- benign classes do not get unjustifiably pushed to `L3`
- tier transitions are visible in the logs

### Paper value

Extremely high. This becomes your **cloud-native correctness section**.

### Estimated effort

- `1-2 days`

---

## Phase 3 - Enforcement specificity / blast-radius test

### Goal

Determine whether K8s enforcement is **per-pod** or accidentally **node-wide**.

### Why this is critical

Your current sidecar logic applies `tc` to `cni0` at the root qdisc level. That creates a real risk that containment is shaping **all** traffic on the node rather than just the target workload.

If true, this is the single most important thing to know before making stronger cloud-native claims.

### Test design

Run three pods:

1. benign client A
2. benign client B
3. malicious target pod

Also run one internal server pod.

Then:

- have A and B both send traffic to the internal server,
- trigger `L3` on the malicious pod,
- measure throughput/latency for A and B during the malicious containment event.

### What to measure

- throughput for target pod before/after containment
- throughput for non-target benign pod before/after containment
- timestamps of RAASA decision and enforcer action

### Strong acceptance criterion

- target pod throughput drops substantially under `L3`
- non-target benign pod throughput changes only minimally

### If the result fails

Then the current implementation is effectively **node-scoped shaping**, not workload-specific shaping.

That is still publishable if reported honestly, but the paper wording must be narrowed to:

- prototype node-local containment
- not yet precise per-pod network shaping

### Paper value

Extremely high. This is the difference between a strong cloud-security paper and a reviewer spotting a core enforcement ambiguity.

### Estimated effort

- `1 day`

---

## Phase 4 - K8s baseline vs adaptive evaluation

### Goal

Bring the same experimental discipline you already used in Docker into the AWS/K8s path.

### Modes to compare

1. `static_L1`
2. `static_L3`
3. `raasa`

### Suggested K8s scenario sizes

Because of the 2 vCPU / 8 GiB limit:

#### K8s-small

- 1 `benign_steady`
- 1 `benign_compute_heavy`
- 1 `malicious_cpu_fanout`
- 1 `malicious_network_heavy_internal`

#### K8s-medium-lite

- 2 `benign_steady`
- 1 `benign_compute_heavy`
- 1 `suspicious_process_growth`
- 1 `malicious_cpu_fanout`
- 1 `malicious_network_heavy_internal`

Keep each run short and repeatable.

### Repeats

- `n = 3` for each mode on K8s-small
- `n = 2` for each mode on K8s-medium-lite

That is enough to support a serious prototype claim without overloading the instance.

### Metrics to compute

- precision
- recall
- false positive rate
- benign restriction rate
- malicious containment rate
- switching rate
- mean time to containment
- explanation coverage

### Acceptance criteria

- `raasa` beats `static_L1` on malicious containment
- `raasa` beats `static_L3` on benign restriction cost
- results are repeatable across runs

### Paper value

Very high. This is what turns the K8s path from "demo" into "evaluated backend."

### Estimated effort

- `1-2 days`

---

## Phase 5 - Telemetry ablation study

### Goal

Show which signals matter in the K8s path.

### Why this helps the paper

Right now you already know telemetry availability is a weak point. An ablation study makes that weakness scientifically useful.

### Suggested ablations

1. CPU/memory/process only
2. + network
3. + syscall
4. full available telemetry

### Best workloads for this phase

- network-heavy malicious
- syscall-heavy malicious
- benign compute-heavy

### What you want to show

- network telemetry materially helps detect network abuse
- syscall telemetry materially helps syscall-heavy abuse
- missing telemetry degrades containment quality

### Paper value

High. This strengthens both the evaluation and the discussion section.

### Estimated effort

- `1 day`

---

## Phase 6 - Overhead characterization on AWS

### Goal

Measure the runtime cost of RAASA in the actual cloud-native environment.

### Minimal overhead study

Measure:

- agent CPU and memory
- enforcer CPU and memory
- syscall probe CPU and memory
- controller loop duration
- pod count vs controller overhead

### Two test conditions

1. idle / benign-only
2. mixed small scenario

### Important note

Do not overcomplicate this. Since you have one node, a clean overhead section is better than a noisy scaling claim.

### Acceptance criteria

- bounded CPU/memory footprint for RAASA components
- stable controller loop timing under small realistic load

### Paper value

Medium to high. Good systems papers nearly always benefit from clean overhead evidence.

### Estimated effort

- `0.5-1 day`

---

## Phase 7 - Failure-injection and safe degradation

### Goal

Prove the system fails safely when dependencies disappear.

### Failure cases to test

1. Metrics Server unavailable
2. syscall probe missing
3. enforcer sidecar restart during a run
4. Prometheus disabled

### What to validate

- controller does not crash
- logs explicitly state degraded telemetry
- decisions remain bounded and auditable
- no uncontrolled escalation occurs

### Paper value

High for credibility. Even a small failure-injection section makes the system look much more serious.

### Estimated effort

- `0.5-1 day`

---

## What I would *not* prioritize next

These are lower value right now:

### 1. More ML experiments

Reason:

- current evidence already says tuned linear > current ML path
- reviewers will care more about telemetry correctness and enforcement specificity first

### 2. Multi-node scaling

Reason:

- your budget and instance size do not support a convincing distributed story
- a weak scale story is worse than a strong single-node story

### 3. Fancy dashboards first

Reason:

- helpful for demos,
- but not the thing that most strengthens the paper.

---

## Credit-aware execution strategy

This plan is intentionally designed to stay well within your AWS credits because it uses:

- a single EC2 instance,
- one-node K3s,
- short repeated runs,
- internal cluster traffic instead of internet-heavy downloads,
- no managed control plane,
- no NAT Gateway,
- no load balancer,
- minimal storage.

## Practical budget discipline

1. Keep root EBS modest, e.g. `20-30 GiB gp3`.
2. Stop Prometheus/Grafana except during overhead and demo capture.
3. Prefer internal traffic generators:
   - `iperf3`
   - internal HTTP file server
   - service-to-service loop
4. Avoid public internet download tests for "network heavy" workloads.
5. Batch experiment runs into dedicated windows; do not leave observability stacks running all day.

## Best use of the credits

Spend credits on:

- repeated K8s runs,
- artifact collection,
- telemetry debugging,
- enforcement specificity testing.

Do not spend them on:

- bigger clusters,
- managed AWS services,
- broad infrastructure complexity.

---

## Suggested 7-day execution plan

## Day 1

- fix labels and telemetry availability
- prove Metrics Server and probe paths work
- collect one clean validation run

## Day 2

- redesign workload expectations
- implement `benign_compute_heavy` and internal malicious network workload
- run correctness tests A-F

## Day 3

- run enforcement specificity / blast-radius test
- decide whether current network shaping is truly per-pod or node-scoped

## Day 4

- run K8s-small `static_L1`, `static_L3`, `raasa` with 3 repeats each

## Day 5

- run K8s-medium-lite with 2 repeats per mode
- generate summaries and plots

## Day 6

- run telemetry ablation tests
- run overhead collection

## Day 7

- run failure-injection tests
- write final markdown result notes
- update the paper draft claims

---

## Artifact checklist

For every major phase, collect:

- audit JSONL
- summary JSON
- agent log
- enforcer log
- exact config used
- workload manifest used
- short markdown interpretation

Use a naming convention like:

```text
aws_k8s_phase2_correctness_r1.jsonl
aws_k8s_phase2_correctness_r1.summary.json
aws_k8s_phase2_correctness_r1.md
```

This will make final writing much easier.

---

## Best possible paper claim after this plan succeeds

If this plan lands well, the paper can make a much stronger and cleaner claim:

> RAASA was evaluated not only as a local Docker prototype but as a cloud-native single-node Kubernetes security agent with a privileged-sidecar enforcement architecture. The study validated telemetry-backed adaptive containment, compared adaptive and static baselines under repeated K8s runs, measured runtime overhead, and explicitly examined enforcement specificity and degraded-telemetry behavior.

That is a serious upgrade.

---

## Final recommendation from me

If I were steering this as your cloud security + sandbox systems team, I would put the next week into **K8s correctness, telemetry integrity, and enforcement specificity**.

That is where the paper has the most to gain.

Not more breadth.

More truth, better measured.

---

## Expert scorecard if this plan is achieved well

These scores assume:

- you complete the plan at a solid prototype level,
- the evidence is repeatable,
- the writeup stays honest about single-node scope and remaining limits.

## Today's relevance

**84/100**

Why this is high:

- cloud-native runtime security is highly relevant,
- eBPF/Kubernetes-aware enforcement is directly aligned with where runtime defense is going,
- adaptive containment is more interesting than static alerting-only stories,
- privileged-sidecar separation is a serious security architecture choice,
- AI agent runtime safety makes the sandbox angle more timely, not less.

Why it is not `90+` yet:

- single-node scope,
- prototype-stage telemetry gaps today,
- likely node-wide vs per-pod enforcement ambiguity unless Phase 3 lands cleanly,
- no strong distributed or production-hardening story yet.

## Tomorrow's relevance

**92/100**

Why this is even higher:

- adaptive sandboxing for AI/agent runtimes will matter more, not less,
- Kubernetes runtime security and kernel-level observability are durable directions,
- workload-specific autonomous containment is a strong future systems problem,
- explainable closed-loop security control is a better long-term story than static rules alone.

Why it is not `95+` automatically:

- the long-term winner will need cleaner per-workload enforcement,
- richer telemetry than CPU/process alone,
- broader validation than a single-node prototype.

## If you nail the two hardest parts

If you **prove telemetry integrity** and **prove enforcement specificity is really per-workload**, I would move the scores to:

- **Today's relevance: 88/100**
- **Tomorrow's relevance: 94/100**

That would put the paper in a genuinely strong position for a serious prototype systems/security submission.
