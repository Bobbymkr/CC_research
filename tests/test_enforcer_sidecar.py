import unittest
from unittest.mock import patch

from raasa.k8s import enforcer_sidecar


class PayloadValidationTests(unittest.TestCase):
    def test_rejects_unknown_tier(self) -> None:
        ok, error = enforcer_sidecar._validate_command_payload(
            {"container_id": "default/raasa-test-benign", "tier": "L4"}
        )
        self.assertFalse(ok)
        self.assertIn("tier", error)

    def test_rejects_unexpected_fields(self) -> None:
        ok, error = enforcer_sidecar._validate_command_payload(
            {"container_id": "default/raasa-test-benign", "tier": "L2", "action": "exec"}
        )
        self.assertFalse(ok)
        self.assertIn("unexpected fields", error)

    def test_rejects_invalid_pod_name(self) -> None:
        ok, error = enforcer_sidecar._validate_command_payload(
            {"container_id": "default/NOT_VALID", "tier": "L2"}
        )
        self.assertFalse(ok)
        self.assertIn("pod name", error)

    def test_accepts_minimal_known_good_payload(self) -> None:
        ok, error = enforcer_sidecar._validate_command_payload(
            {"container_id": "default/raasa-test-benign", "tier": "L3"}
        )
        self.assertTrue(ok)
        self.assertEqual(error, "")


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


class HandleCommandValidationTests(unittest.TestCase):
    def test_handle_command_rejects_invalid_payload_before_enforcement(self) -> None:
        with patch.object(enforcer_sidecar, "_resolve_pod_interface") as resolve_mock, \
             patch.object(enforcer_sidecar, "_apply_network_throttle") as net_mock, \
             patch.object(enforcer_sidecar, "_apply_memory_limit") as mem_mock:
            self.assertFalse(enforcer_sidecar.handle_command({"container_id": "bad name", "tier": "L3"}))
        resolve_mock.assert_not_called()
        net_mock.assert_not_called()
        mem_mock.assert_not_called()

    def test_handle_command_accepts_known_good_payload(self) -> None:
        with patch.object(enforcer_sidecar, "_resolve_pod_interface", return_value="veth0"), \
             patch.object(enforcer_sidecar, "_apply_network_throttle", return_value=True) as net_mock, \
             patch.object(enforcer_sidecar, "_apply_memory_limit", return_value=False) as mem_mock:
            result = enforcer_sidecar.handle_command(
                {"container_id": "default/raasa-test-benign", "tier": "L2"}
            )

        self.assertTrue(result)
        net_mock.assert_called_once_with("raasa-test-benign", "L2", "veth0")
        mem_mock.assert_called_once_with("raasa-test-benign", "L2")

    def test_handle_command_refuses_default_interface_fallback_by_default(self) -> None:
        enforcer_sidecar._LAST_INTERFACE_BY_CONTAINER.clear()
        with patch.object(enforcer_sidecar, "_resolve_pod_interface", return_value=None), \
             patch.object(enforcer_sidecar, "_apply_network_throttle") as net_mock, \
             patch.object(enforcer_sidecar, "_apply_memory_limit") as mem_mock, \
             patch.dict(enforcer_sidecar.os.environ, {}, clear=True):
            result = enforcer_sidecar.handle_command(
                {"container_id": "default/raasa-test-benign", "tier": "L2"}
            )

        self.assertFalse(result)
        net_mock.assert_not_called()
        mem_mock.assert_not_called()

    def test_handle_command_can_use_explicit_default_interface_fallback(self) -> None:
        enforcer_sidecar._LAST_INTERFACE_BY_CONTAINER.clear()
        with patch.object(enforcer_sidecar, "_resolve_pod_interface", return_value=None), \
             patch.object(enforcer_sidecar, "_apply_network_throttle", return_value=True) as net_mock, \
             patch.object(enforcer_sidecar, "_apply_memory_limit", return_value=False), \
             patch.dict(enforcer_sidecar.os.environ, {"RAASA_ALLOW_DEFAULT_INTERFACE_FALLBACK": "true"}, clear=True):
            result = enforcer_sidecar.handle_command(
                {"container_id": "default/raasa-test-benign", "tier": "L2"}
            )

        self.assertTrue(result)
        net_mock.assert_called_once_with("raasa-test-benign", "L2", enforcer_sidecar.DEFAULT_INTERFACE)

    def test_handle_command_uses_cached_interface_when_resolution_temporarily_fails(self) -> None:
        enforcer_sidecar._LAST_INTERFACE_BY_CONTAINER.clear()
        enforcer_sidecar._LAST_INTERFACE_BY_CONTAINER["default/raasa-test-benign"] = "veth-cached"
        try:
            with patch.object(enforcer_sidecar, "_resolve_pod_interface", return_value=None), \
                 patch.object(enforcer_sidecar, "_apply_network_throttle", return_value=True) as net_mock, \
                 patch.object(enforcer_sidecar, "_apply_memory_limit", return_value=False), \
                 patch.dict(enforcer_sidecar.os.environ, {}, clear=True):
                result = enforcer_sidecar.handle_command(
                    {"container_id": "default/raasa-test-benign", "tier": "L2"}
                )
        finally:
            enforcer_sidecar._LAST_INTERFACE_BY_CONTAINER.clear()

        self.assertTrue(result)
        net_mock.assert_called_once_with("raasa-test-benign", "L2", "veth-cached")

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
