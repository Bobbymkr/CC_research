# RAASA Current Plan: Phase 1D Baseline, Cloud-Native Correctness, and Paper Alignment

## Summary

RAASA is no longer at the early "single-host v1 prototype" planning stage. The repo now contains a stronger evidence base:

- solid local Docker evaluation for the adaptive-vs-static story,
- a tuned linear controller that is stronger than the current ML arm,
- live AWS/K3s evidence through Phase 1D showing pod-specific host-veth containment across the tested demo and benchmark pods,
- and fresh operational evidence that the cloud-native control-plane telemetry path is still fragile under stress.

The plan from this point forward should be evidence-led and paper-safe. The next goal is not to make the ML story bigger. The next goal is to keep the cloud-native path correct, reproducible, and aligned with the claims we can already defend.

## Current project position

### What is strong now

- Adaptive RAASA clearly improves on static `L1` and static `L3` in the curated local evaluation story.
- The tuned linear controller is the primary controller the paper should trust today.
- The AWS/K8s path now has meaningful live evidence, culminating in Phase 1D universal pod resolution with `fallback_lines = []`.
- The AWS/K8s controller path now also has a calibrated live snapshot where benign compute stays in `L1` while malicious CPU reaches `L3`, despite continued Metrics API instability.
- The best current cloud-native claim is pod-specific host-veth containment across the tested pods, not just node-scoped `cni0` shaping.

### What still needs discipline

- The Metrics API path is still operationally unstable under restart and stress.
- The ML path exists, but it is not the strongest controller in the evidence base.
- The draft paper still overstates feature semantics, enforcement maturity, and some cloud-native guarantees.
- The current source must stay synchronized with the curated packet and the live deployment artifacts.
- The live probe config and the live K8s shared-probe directory can drift if config is rolled out from the wrong source file, so live config application now needs an explicit config-only path.

## Active claims

### Safe claims to center

- RAASA is a research prototype for adaptive containment of containerized workloads.
- The strongest overall evidence comes from the local Docker evaluation.
- The strongest current controller is the tuned linear controller.
- The cloud-native path is a meaningful prototype with live pod-specific containment evidence on AWS/K3s.
- The latest live evidence also shows telemetry fragility, so the cloud-native path should be described as promising but still maturing.
- The latest calibrated controller snapshot is `phase1g4b_calibration_snapshot_2026_04_26/`, where `default/raasa-test-benign-compute` stays `L1` and `default/raasa-test-malicious-cpu` escalates to `L3`.

### Claims to avoid unless re-evidenced

- ML superiority over the tuned linear controller.
- Fully mature dynamic seccomp relaxation or CRIU-backed downgrade behavior.
- Full multi-signal telemetry integrity in the K8s path.
- Broad production-grade Kubernetes enforcement claims beyond the tested workloads and artifact bundle.

## Immediate engineering plan

1. Rebuild and deploy a fresh image from the corrected local source, using a new tag after `phase1d`.
2. Include the K8s observer telemetry-hardening patch so CPU stays truthful both when direct probe files exist and when the observer must fall back to Metrics API usage strings.
3. Re-run `raasa/scripts/run_phase1d_resolution_validation.ps1` against the live AWS node and confirm the same clean pod-resolution result still reproduces.
4. Treat that rerun as the first end-to-end regression gate for the current enforcer and observer implementation.
5. Only after that rerun succeeds, decide whether the next live loop should target controller calibration or a fresh ML ablation.

## Current implementation priorities

### Priority 1: Keep the Phase 1D enforcement path correct

- Preserve the pod UID -> host PID -> peer ifindex -> host veth resolution path.
- Keep `L1`, `L2`, and `L3` network behavior tied to explicit tier profiles in the enforcer.
- Continue treating `L3` as hard containment in paper wording unless new evidence proves graceful QoS semantics.
- Current live `phase1e` evidence strengthens that wording: `L3` now produces fast-fail `0 B/s` behavior in about `5 s`, not graceful bandwidth degradation.

### Priority 2: Harden regression coverage around the enforcer

- Keep focused local tests around `_apply_network_throttle()`.
- Expand targeted tests around resolver fallbacks and profile selection before making new K8s enforcement changes.
- Use the live Phase 1D rerun as the next practical validation step.

### Priority 2A: Keep telemetry fallback behavior truthful

- Preserve direct `.cpu_usec` probe reads as the preferred CPU source when available.
- Preserve Metrics API CPU parsing as the fallback source when probe data is absent.
- Keep the K8s observer tests covering both the mocked Metrics API path and the direct probe path.
- Keep the live probe configs aligned with the actual K8s shared volume path (`/var/run/raasa`), not the older local relative path.

### Priority 2B: Separate hard containment from DNS/test-harness effects

- The latest live rerun preserved clean pod resolution but showed `L3` failing fast with `0 B/s` and `curl` name-resolution errors for the benchmark service.
- The next validation refinement should distinguish "payload path blocked" from "service DNS blocked" by adding one direct-IP or non-DNS benchmark path alongside the current service-name path.
- Paper wording should continue to treat the observed result as successful hard containment, not bandwidth QoS.

### Priority 2C: Use the refined Phase 1F interpretation going forward

- The refined live run now shows that `L3` disrupts all three tested benchmark paths: service DNS name, service `ClusterIP`, and direct pod IP.
- That means the current live AWS evidence no longer supports a "maybe only DNS broke" interpretation.
- From this point on, the paper and implementation notes should describe the observed `L3` result as full hard containment in the tested benchmark setup.

### Priority 3: Only revisit ML after correctness is locked down

- If a new ML-vs-linear comparison is run, it must be truthful and isolated.
- The comparison should not be mixed with unresolved enforcement changes or ambiguous telemetry conditions.
- The tuned linear controller remains the default baseline unless ML wins on a clearly stated selection rule.

### Priority 4: Stabilize the K8s control-plane telemetry path

- The current calibrated controller still depends on a degraded telemetry environment where `metrics.k8s.io` calls frequently fail with `subjectaccessreviews` timeouts.
- That instability stretches controller iterations and depresses confidence, which is why the live `L3` confidence floor now has to stay low (`0.05`) to keep malicious CPU escalation truthful.
- The next engineering phase should therefore target Metrics Server / API authorization / timeout stability, not another threshold sweep.

## Paper plan

1. Revise the draft so the feature semantics match the current repo-backed implementation.
2. Keep the adaptive-vs-static trade-off as the center of the quantitative story.
3. Present the K8s/AWS path as a concrete prototype extension with live pod-specific containment evidence.
4. Use the April 26 artifacts to show both progress and honest limitations.
5. Treat richer enforcement semantics and stronger telemetry guarantees as future work unless re-implemented and re-tested.

## Next engineering move

1. Keep the current containment semantics stable rather than changing `L3` behavior immediately.
2. Treat `phase1g4b_calibration_snapshot_2026_04_26/` as the current live controller baseline: `l2_max=0.60`, `l3_min_confidence=0.05`, `syscall_cap=5000.0`, probe path `/var/run/raasa`.
3. Shift the next code-facing effort toward Metrics API and control-plane stabilization, because controller calibration is now in a much better place than telemetry reliability.
4. After that stabilization work, rerun both the calibrated controller snapshot and the refined Phase 1F containment validation.

## Verification plan

- Focused regression guard: `tests/test_enforcer_sidecar.py`
- Live end-to-end guard: rerun the Phase 1D validation script on AWS
- Paper-alignment guard: `RM_practical/06_paper_alignment_and_claim_boundaries.md`

## Environment note

The bundled local runtime is enough to run the focused `unittest` coverage for the enforcer, but not the full broader test suite without additional packages such as `PyYAML`, `joblib`, and `pytest`. Until that environment is filled out, the safest verification sequence is:

1. targeted local unit coverage for the touched enforcement logic,
2. live AWS rerun for the Phase 1D path,
3. paper text updates only after those two stay aligned.
