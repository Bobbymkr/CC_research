import unittest

from raasa.core.app import _apply_mode_override
from raasa.core.models import PolicyDecision, Tier
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


if __name__ == "__main__":
    unittest.main()
