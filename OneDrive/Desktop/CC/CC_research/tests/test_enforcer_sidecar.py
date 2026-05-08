import unittest
from unittest.mock import patch

from raasa.k8s import enforcer_sidecar


class NetworkThrottleProfileTests(unittest.TestCase):
    def test_l1_clears_existing_qdisc_only(self) -> None:
        calls: list[list[str]] = []

        with patch.object(enforcer_sidecar, "_run_tc", side_effect=lambda args: calls.append(args) or True):
            self.assertTrue(enforcer_sidecar._apply_network_throttle("pod-a", "L1", "veth0"))

        self.assertEqual(calls, [["qdisc", "del", "dev", "veth0", "root"]])

    def test_l2_uses_degraded_tbf_profile(self) -> None:
        calls: list[list[str]] = []

        with patch.object(enforcer_sidecar, "_run_tc", side_effect=lambda args: calls.append(args) or True):
            self.assertTrue(enforcer_sidecar._apply_network_throttle("pod-a", "L2", "veth0"))

        self.assertEqual(calls[0], ["qdisc", "del", "dev", "veth0", "root"])
        self.assertEqual(
            calls[1],
            [
                "qdisc",
                "add",
                "dev",
                "veth0",
                "root",
                "tbf",
                "rate",
                "20mbit",
                "burst",
                "1mbit",
                "latency",
                "250ms",
            ],
        )

    def test_l3_uses_hard_containment_netem_loss_profile(self) -> None:
        calls: list[list[str]] = []

        with patch.object(enforcer_sidecar, "_run_tc", side_effect=lambda args: calls.append(args) or True):
            self.assertTrue(enforcer_sidecar._apply_network_throttle("pod-a", "L3", "veth0"))

        self.assertEqual(calls[0], ["qdisc", "del", "dev", "veth0", "root"])
        self.assertEqual(
            calls[1],
            [
                "qdisc",
                "add",
                "dev",
                "veth0",
                "root",
                "netem",
                "loss",
                "100%",
            ],
        )


if __name__ == "__main__":
    unittest.main()
