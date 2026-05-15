# RAASA Paper Evidence Package

## 1. Purpose

This document defines the evidence package needed to turn RAASA into a
credible paper submission. It is intentionally reviewer-oriented: each evidence
type is mapped to the claim it supports, why that evidence matters, what form
it should take in the paper, and whether the current repository already has the
needed material.

Use this file together with:

- [docs/paper_positioning.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/paper_positioning.md)
- [docs/evidence_index.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/evidence_index.md)
- [docs/testing_environment_inventory.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/testing_environment_inventory.md)
- [docs/paper_full_draft.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/paper_full_draft.md)
- [docs/figures/README.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/README.md)
- [docs/tables/README.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/tables/README.md)

## 2. What a Paper Needs

A strong systems/security paper does not rely on one kind of evidence. It
needs a layered package:

1. **tabular evidence** for compact comparison and claim accounting
2. **graphical evidence** for intuition, trends, and architecture clarity
3. **artifact evidence** for reproducibility and auditability
4. **negative evidence** for honesty about failure modes and boundaries
5. **methodology evidence** for experimental trustworthiness
6. **scope evidence** for what is and is not being claimed

The key idea is that each type answers a different reviewer question:

- tables answer: "what exactly happened?"
- figures answer: "what pattern should I see?"
- artifacts answer: "can I trust this was actually run?"
- failure evidence answers: "what breaks and how honestly is it reported?"
- methods answer: "was this evaluated cleanly?"
- scope evidence answers: "are the claims larger than the data?"

## 3. Core Evidence Matrix

| Evidence class | What it proves | Why reviewers care | Required paper form | Current status |
| --- | --- | --- | --- | --- |
| Local baseline comparison | Adaptive control is better than static L1/L3 under bounded workloads | Establishes the thesis before cloud complexity is introduced | Main table in evaluation | Available |
| Single-node fresh-account replay | Cloud evidence is reproducible from a clean AWS account, not only a long-lived host | Reduces suspicion that the result depends on one special machine | Short table row plus one paragraph | Available |
| Bounded 3-node K3s evidence | The architecture survives beyond single-node replay | Supports the paper's strongest distributed claim | Main cloud-evidence table plus summary paragraph | Available |
| Failure/degraded-mode evidence | The system fails in interpretable ways rather than silently lying | Important for credibility in security and systems work | Table or compact bullet summary | Available |
| Reschedule continuity evidence | Worker drain does not immediately collapse the bounded 3-node story | Distinguishes a cloud exercise from a mere static deployment demo | Table row plus appendix artifact references | Available |
| Threat-model scope evidence | Claims are bounded to tested workload families | Prevents overclaiming | Threat-model subsection | Available, but should be made explicit in final draft |
| Reproducibility inventory | The environment and constraints are documented | Makes the artifact believable and reusable | Appendix or artifact section | Available |
| Managed-cluster evidence | Whether claims extend to EKS | Critical if the paper mentions managed Kubernetes | Separate section only if run | Not available, should remain a non-claim |

## 4. Tabular Evidence Needed

Tabular evidence is the backbone of the paper. If a claim cannot be tied to a
table, reviewers often perceive it as weaker.

### 4.1 Required tables

#### Table A. Local baseline comparison

This is the anchor table for the main thesis.

Minimum columns:

- mode
- environment
- scenario
- precision
- recall
- false positive rate
- benign restriction rate
- unnecessary escalations

Why it matters:

- this is the cleanest proof that adaptive containment is worth discussing at
  all
- it gives reviewers a fast baseline-relative picture before the cloud story
  begins

Current status:

- already reflected in the paper draft

#### Table B. Cloud evidence ladder

This should be the main cloud table.

Minimum rows:

- pod-specific containment resolution
- refined L3 semantics
- fresh-account single-node replay
- bounded 3-node soak + repeated matrix
- failure injection + Metrics API stress
- worker drain/reschedule continuity

Minimum columns:

- date
- environment shape
- workload / test
- result
- claim supported
- key limitation

Why it matters:

- it turns many AWS artifacts into one reviewer-readable evidence ladder
- it makes the progression from single-node to bounded multi-node explicit

Current status:

- rendered in [docs/tables/generated/cloud_evidence_ladder.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/tables/generated/cloud_evidence_ladder.md)
- ready to cite directly in the next paper-draft tightening pass

#### Table C. Failure and degraded-mode summary

This table should separate "works when healthy" from "behaves honestly when not
healthy."

Minimum rows:

- Metrics API outage
- syscall probe pause
- fake-pod IPC fail-closed
- agent restart recovery
- Metrics API bounded stress

Minimum columns:

- injected condition
- expected behavior
- observed behavior
- telemetry status
- interpretation

Why it matters:

- strong systems/security papers usually win trust by documenting degraded
  behavior explicitly
- this is one of RAASA's most credible differentiators

Current status:

- rendered in [docs/tables/generated/failure_degraded_mode_summary.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/tables/generated/failure_degraded_mode_summary.md)
- ready for direct inclusion in the evaluation or appendix

#### Table D. Scope and non-claims table

This should be short but explicit.

Minimum rows:

- single-node replay
- bounded 3-node K3s
- multi-tenant Kubernetes
- EKS / managed control plane
- production readiness

Minimum columns:

- claim area
- supported?
- evidence basis
- note

Why it matters:

- this is not always required, but for RAASA it is unusually valuable
- it prevents reviewers from inferring claims that the paper does not intend to
  make

Current status:

- rendered in [docs/tables/generated/scope_nonclaims.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/tables/generated/scope_nonclaims.md)
- especially useful for appendix, rebuttal, or camera-ready scope control

## 5. Graphical Evidence Needed

Figures should not merely decorate the paper. Each figure should answer one
clear question.

### 5.1 Required figures

#### Figure 1. High-level architecture

Show:

- Observe-Assess-Decide-Act-Audit flow
- unprivileged controller
- privileged enforcer sidecar
- IPC boundary
- telemetry inputs
- audit outputs

Why it matters:

- explains the core systems idea quickly
- makes the privilege-separation contribution legible

Current status:

- DOT source is available in [docs/figures/raasa_control_loop.dot](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/raasa_control_loop.dot)
- render with Graphviz on a machine that has `dot` installed

#### Figure 2. Cloud deployment / node-local enforcement path

Show:

- control-plane node
- worker nodes
- RAASA DaemonSet placement
- malicious pod
- benign pod
- node-local agent selection
- host-veth or pod-specific enforcement path

Why it matters:

- this is the key "why multi-node was nontrivial" figure
- it explains the value of node-local resolution fixes better than prose alone

Current status:

- DOT source is available in [docs/figures/raasa_multinode_k3s.dot](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/raasa_multinode_k3s.dot)
- render with Graphviz on a machine that has `dot` installed

#### Figure 3. Local baseline trade-off figure

A bar chart or grouped bar chart comparing:

- static L1
- static L3
- adaptive RAASA

Recommended metrics:

- precision
- recall
- false positive rate
- benign restriction rate

Why it matters:

- gives a visual form to the paper's central thesis
- makes the "middle path" argument much more memorable

Current status:

- rendered in [docs/figures/generated/local_baseline_tradeoff.svg](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/generated/local_baseline_tradeoff.svg)
- Python source remains the canonical editable form in [docs/figures/plot_local_baseline_tradeoff.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/plot_local_baseline_tradeoff.py)

#### Figure 4. Cloud evidence timeline or progression figure

Show a chronological progression:

- resolution correctness
- L3 semantics clarification
- single-node repeatability
- fresh-account replay
- bounded 3-node validation

Why it matters:

- this paper's cloud story is as much about disciplined progression as it is
  about one final number
- a timeline helps reviewers see that the work matured through correction

Current status:

- DOT source is available in [docs/figures/raasa_validation_progression.dot](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/raasa_validation_progression.dot)
- recommended in the main paper if the venue allows one extra figure

#### Figure 5. Degraded-mode behavior figure

Possible forms:

- stacked bars for telemetry status (`complete`, `partial`)
- line or grouped bars for `metrics_ok` vs `metrics_error`, `probe_ok` vs
  `probe_stale`

Why it matters:

- communicates that the system does not merely "pass" or "fail"
- shows observability honesty under stress

Current status:

- rendered in [docs/figures/generated/cloud_degraded_mode_summary.svg](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/generated/cloud_degraded_mode_summary.svg)
- Python source remains the canonical editable form in [docs/figures/plot_degraded_mode_summary.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/plot_degraded_mode_summary.py)

### 5.2 Nice-to-have figures

- one screenshot or appendix figure of raw audit-row structure
- one appendix figure showing pod placement before and after worker drain
- one appendix figure showing the fresh-account replay as a compact evidence
  flow

## 6. Artifact Evidence Needed

These are not necessarily main-paper figures or tables, but they are part of a
credible submission package.

### 6.1 Required artifact classes

#### A. Evidence index

Purpose:

- every major claim should map to a concrete artifact bundle

Current status:

- available in [docs/evidence_index.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/evidence_index.md)

#### B. Testing environment inventory

Purpose:

- makes the evaluation environment explicit
- prevents "what exactly was this run on?" reviewer friction

Current status:

- available in [docs/testing_environment_inventory.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/testing_environment_inventory.md)

#### C. Reproducibility guide

Purpose:

- shows how the artifact can be rerun

Current status:

- available in [REPRODUCIBILITY.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/REPRODUCIBILITY.md)

#### D. Cloud validation playbook

Purpose:

- shows the AWS/K3s methodology was operationally disciplined

Current status:

- available in [docs/aws_validation_playbook.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/aws_validation_playbook.md)

#### E. Raw result bundles

Purpose:

- lets a reviewer or artifact evaluator inspect the non-summarized evidence

Current status:

- available under [AWS_Results_26_april](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april)

## 7. Negative Evidence Needed

Negative evidence is often the difference between a pitch and a paper.

RAASA should preserve:

- failed soak attempts that were superseded
- SSH / CloudShell / control-plane friction where relevant to methodology
- control-plane telemetry fragility
- the fact that EKS evidence does not exist yet
- the fact that the bounded multi-node campaign required node-local agent
  resolution fixes

Why it matters:

- it demonstrates epistemic discipline
- it lets reviewers trust the positive evidence more

Current status:

- mostly available in artifacts and discussion text
- should be summarized explicitly in discussion/limitations, not buried

## 8. Methodology Evidence Needed

Even strong results can be discounted if the paper does not show how the
evaluation was controlled.

### 8.1 Minimum methodology evidence

- exact environment shape
- exact workload classes
- exact run counts
- duration of runs
- what was quiesced between runs
- what counted as pass/fail
- how fake-pod IPC, stress, and drain scenarios were triggered
- how cleanup and teardown were verified

Current status:

- present across the playbook, evidence index, and AWS bundles
- should be consolidated into a compact methods paragraph/table in the paper

## 9. What Is Already Strong Enough

The current submission package is already strong on:

1. **bounded claim discipline**
2. **local baseline comparison**
3. **fresh-account cloud reproducibility**
4. **bounded 3-node K3s continuity**
5. **failure/degraded-mode honesty**
6. **privilege-separation architecture**

These are the assets to lean on.

## 10. What Still Needs Synthesis

The main gap is no longer missing experiments. It is **paper synthesis**.

Still needed before a polished submission:

1. render the architecture figures
2. render the local baseline comparison figure
3. synthesize the failure/degraded-mode table
4. synthesize a compact evaluation-envelope table
5. attach explicit artifact references to the cloud results in the main draft
6. optionally include an appendix evidence map for artifact review

## 11. Recommended Final Paper Package

If space is tight, the strongest package is:

### Main paper

- Table A: local baseline comparison
- Table B: cloud evidence ladder
- Figure 1: control-loop architecture
- Figure 2: cloud / node-local enforcement architecture
- Figure 3: local baseline trade-off figure
- explicit limitations paragraph

### Appendix or artifact package

- Table C: failure and degraded-mode summary
- Table D: scope and non-claims table
- raw artifact references
- environment inventory
- reschedule before/after snapshots

This gives the paper both readability and depth.

## 12. Final Recommendation

The most reasoned way to present RAASA is:

- **main claim**: adaptive, auditable, privilege-separated containment is
  feasible and reproducible in bounded local and AWS/K3s settings
- **strongest cloud claim**: fresh-account replay plus bounded 3-node K3s
  continuity
- **strongest trust signal**: explicit degraded-mode and non-claim evidence
- **do not force**: EKS, production readiness, or broad multi-tenant claims

That combination gives the paper the best chance of being read as serious,
disciplined systems/security work rather than as an overextended prototype
story.
