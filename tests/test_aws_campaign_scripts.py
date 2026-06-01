from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "raasa" / "scripts"

PHASE_SCRIPTS = [
    "run_phase0_foundation.sh",
    "run_phase1_workload_validation.sh",
    "run_phase2_correctness.sh",
    "run_phase3_blast_radius.sh",
    "run_phase4_baselines.sh",
    "run_phase5_ablation.sh",
    "run_phase6_overhead.sh",
    "run_phase7_failure_injection.sh",
]

TRACKED_LEGACY_SCRIPTS = [
    "aws_k3s_setup.sh",
    "closed_loop_test.sh",
    "create_credit_gated_eks_cluster.sh",
    "create_freetier_raasa_ec2.sh",
    "create_freetier_raasa_k3s_cluster.sh",
    "destroy_credit_gated_eks_cluster.sh",
    "destroy_freetier_raasa_ec2.sh",
    "destroy_freetier_raasa_k3s_cluster.sh",
]


def read_script(name: str) -> str:
    return (SCRIPT_DIR / name).read_text(encoding="utf-8")


def test_orchestrator_self_relocates_to_repository_root() -> None:
    text = read_script("run_all_phases_aws.sh")

    assert 'CC_RESEARCH_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"' in text
    assert 'run_phase "raasa/scripts/run_phase0_foundation.sh"' in text


def test_phase_scripts_are_not_sensitive_to_sudo_home() -> None:
    for script in PHASE_SCRIPTS:
        text = read_script(script)

        assert "$HOME/CC_research" not in text, script
        assert 'export KUBECONFIG="/etc/rancher/k3s/k3s.yaml"' not in text, script
        assert 'export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"' in text, script


def test_phase_scripts_do_not_use_fragile_audit_globs() -> None:
    for script in PHASE_SCRIPTS:
        text = read_script(script)

        assert 'ls -t "$LOG_DIR"/*.jsonl' not in text, script


def test_phase_scripts_do_not_duplicate_grep_count_zeroes() -> None:
    for script in PHASE_SCRIPTS:
        text = read_script(script)

        assert not re.search(r"grep\s+-c[^\n]+?\|\|\s+echo\s+0", text), script


def test_phase_scripts_use_current_raasa_cli_flags() -> None:
    deprecated_flags = ["--duration", "--run-id", "--log-dir"]
    for script in PHASE_SCRIPTS:
        text = read_script(script)

        for flag in deprecated_flags:
            assert flag not in text, script


def test_phase7_uses_safe_failure_injection_primitives() -> None:
    text = read_script("run_phase7_failure_injection.sh")

    assert "xargs rm" not in text
    assert "kill 1" not in text


def test_tracked_legacy_shell_scripts_are_not_empty() -> None:
    for script in TRACKED_LEGACY_SCRIPTS:
        assert (SCRIPT_DIR / script).stat().st_size > 0, script
