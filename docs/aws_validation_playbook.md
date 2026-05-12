# AWS Validation Playbook

This playbook is the paper-first AWS path. It assumes a single-node EC2/K3s
host unless a multi-node cluster is explicitly named in the evidence bundle.

## Key Handling

Keep SSH keys outside the repository.

```powershell
$env:RAASA_AWS_KEY_PATH = "C:\Users\Admin\.ssh\raasa-paper-key.pem"
python -m raasa.scripts.secret_scan --root .
```

All AWS PowerShell scripts accept `-KeyPath`; if it is omitted, they read
`RAASA_AWS_KEY_PATH`. Do not copy PEM files into the project tree.

## Required Paper Evidence

1. Local hygiene and tests:

```powershell
python -m raasa.scripts.secret_scan --root .
python -m pytest tests -q
```

2. Live AWS sanity capture:

```powershell
powershell -ExecutionPolicy Bypass -File raasa/scripts/collect_aws_live_validation.ps1 `
    -TargetHost <AWS_IPV4>
```

3. Closed-loop soak:

```powershell
powershell -ExecutionPolicy Bypass -File raasa/scripts/run_closed_loop_soak_aws.ps1 `
    -TargetHost <AWS_IPV4> `
    -Cycles 10
```

4. Five-run adversarial matrix:

```powershell
powershell -ExecutionPolicy Bypass -File raasa/scripts/run_repeated_adversarial_matrix_aws.ps1 `
    -TargetHost <AWS_IPV4> `
    -DurationSeconds 75 `
    -QuiesceBackgroundWorkloads
```

This matrix includes benign control, syscall storm, process fanout, network
burst, and agent dependency/exfiltration workloads. A passing bundle must retain
all per-run summaries, audit rows, pod snapshots, and capacity snapshots.

5. Failure and stress evidence:

```powershell
powershell -ExecutionPolicy Bypass -File raasa/scripts/run_failure_injection_aws.ps1 `
    -TargetHost <AWS_IPV4>

powershell -ExecutionPolicy Bypass -File raasa/scripts/run_metrics_api_stress_probe.ps1 `
    -TargetHost <AWS_IPV4>
```

6. L3 pod-specific containment:

```powershell
powershell -ExecutionPolicy Bypass -File raasa/scripts/run_phase1d_resolution_validation.ps1 `
    -TargetHost <AWS_IPV4>
```

## Reviewer Acceptance Bar

- Every major claim maps to one row in
  [docs/evidence_index.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/evidence_index.md).
- Failed runs are preserved with diagnosis instead of deleted.
- `L3` is described as hard containment for tested pod/network paths, not a
  general container sandbox.
- The final paper states the current scope: single-node K3s unless new
  multi-node evidence is collected.
