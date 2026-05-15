import unittest

from raasa.core.config import load_config
from raasa.core.app import _apply_mode_override, _wait_for_backend_readiness
from raasa.core.models import PolicyDecision, Tier
from raasa.experiments.run_experiment import build_parser
from raasa.experiments.scenarios import build_scenario


class ScenarioTests(unittest.TestCase):
    def test_small_scenario_has_expected_mix(self) -> None:
        items = build_scenario("small", "demo")
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].name, "raasa-demo-benign_steady-1")
        self.assertEqual(items[-1].workload.expected_tier, "L3")

    def test_large_scenario_count(self) -> None:
        items = build_scenario("large", "demo")
        self.assertEqual(len(items), 20)

    def test_small_tuned_uses_heavier_malicious_workload(self) -> None:
        items = build_scenario("small_tuned", "demo")
        self.assertEqual(len(items), 3)
        self.assertEqual(items[-1].workload.key, "malicious_pattern_heavy")

    def test_benign_only_scenario_has_expected_mix(self) -> None:
        items = build_scenario("benign_only", "demo")
        self.assertEqual(len(items), 3)
        self.assertEqual([item.workload.key for item in items].count("benign_steady"), 2)
        self.assertEqual([item.workload.key for item in items].count("benign_bursty"), 1)

    def test_mixed_adversarial_scenario_has_expected_mix(self) -> None:
        items = build_scenario("mixed_adversarial", "demo")
        self.assertEqual(len(items), 6)
        self.assertEqual([item.workload.key for item in items].count("malicious_network_heavy"), 1)
        self.assertEqual([item.workload.key for item in items].count("malicious_syscall_heavy"), 1)

    def test_agent_misuse_scenario_has_agent_like_exfiltration_probe(self) -> None:
        items = build_scenario("agent_misuse", "demo")
        workload_keys = [item.workload.key for item in items]
        self.assertEqual(len(items), 3)
        self.assertIn("agent_dependency_exfiltration", workload_keys)
        agent_item = next(item for item in items if item.workload.key == "agent_dependency_exfiltration")
        self.assertEqual(agent_item.workload.category, "malicious")
        self.assertEqual(agent_item.workload.expected_tier, "L3")
        self.assertIn("raasa-demo-token-not-a-secret", " ".join(agent_item.workload.command))


class ConfigTests(unittest.TestCase):
    def test_default_config_uses_linear_tuned_story(self) -> None:
        config = load_config("raasa/configs/config.yaml")
        self.assertFalse(config.use_ml_model)
        self.assertEqual(config.controller_variant, "linear_tuned")
        self.assertFalse(config.audit_kms_enabled)
        self.assertEqual(config.audit_kms_mac_algorithm, "HMAC_SHA_256")

    def test_linear_tuned_config_disables_ml_model(self) -> None:
        config = load_config("raasa/configs/config_tuned_small_linear.yaml")
        self.assertFalse(config.use_ml_model)
        self.assertEqual(config.controller_variant, "linear_tuned")

    def test_local_linear_config_uses_docker_scale_syscall_cap(self) -> None:
        config = load_config("raasa/configs/config_tuned_small_linear.yaml")
        self.assertEqual(config.syscall_source, "simulated")
        self.assertEqual(config.syscall_cap, 500.0)

    def test_probe_linear_config_keeps_k8s_scale_syscall_cap(self) -> None:
        config = load_config("raasa/configs/config_tuned_small_linear_probe.yaml")
        self.assertEqual(config.syscall_source, "probe")
        self.assertEqual(config.syscall_cap, 5000.0)

    def test_v2_full_pipeline_config_enables_dna_and_lstm(self) -> None:
        config = load_config("raasa/configs/config_v2_full_pipeline.yaml")
        self.assertEqual(config.syscall_source, "probe")
        self.assertTrue(config.use_behavioral_dna)
        self.assertTrue(config.use_temporal_lstm)
        self.assertEqual(config.controller_variant, "v2_full_pipeline")


class ExperimentCliTests(unittest.TestCase):
    def test_run_experiment_accepts_iteration_count_for_repro_commands(self) -> None:
        args = build_parser().parse_args(
            [
                "--mode",
                "raasa",
                "--scenario",
                "agent_misuse",
                "--iterations",
                "12",
            ]
        )
        self.assertEqual(args.iterations, 12)


class ModeOverrideTests(unittest.TestCase):
    def test_static_override_forces_tier(self) -> None:
        decision = PolicyDecision(
            container_id="c1",
            timestamp=None,
            previous_tier=Tier.L1,
            proposed_tier=Tier.L2,
            applied_tier=Tier.L2,
            reason="adaptive",
            action_required=True,
        )

        updated = _apply_mode_override([decision], "static_L3")[0]
        self.assertEqual(updated.applied_tier, Tier.L3)
        self.assertTrue(updated.action_required)
        self.assertIn("override", updated.reason)
        self.assertEqual(updated.containment_profile, "hard_containment")


class BackendReadinessTests(unittest.TestCase):
    def test_k8s_backend_waits_for_enforcer_readiness(self) -> None:
        class FakeEnforcer:
            def __init__(self) -> None:
                self.calls = []

            def wait_until_ready(self, timeout_seconds: float) -> bool:
                self.calls.append(timeout_seconds)
                return True

        enforcer = FakeEnforcer()
        ready = _wait_for_backend_readiness("k8s", enforcer, timeout_seconds=3.0)
        self.assertTrue(ready)
        self.assertEqual(enforcer.calls, [3.0])

    def test_non_k8s_backend_skips_readiness_wait(self) -> None:
        class FakeEnforcer:
            def wait_until_ready(self, timeout_seconds: float) -> bool:
                raise AssertionError("should not be called")

        self.assertIsNone(_wait_for_backend_readiness("docker", FakeEnforcer(), timeout_seconds=3.0))


if __name__ == "__main__":
    unittest.main()
