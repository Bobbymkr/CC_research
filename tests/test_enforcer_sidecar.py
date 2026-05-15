import unittest
from pathlib import Path
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


class NetworkPolicyGenerationTests(unittest.TestCase):
    def test_l3_network_policy_denies_ingress_and_egress_for_target_label(self) -> None:
        body = enforcer_sidecar._l3_network_policy_body("default", "raasa-test-benign")
        token = enforcer_sidecar._contained_pod_token("default", "raasa-test-benign")

        self.assertEqual(body["kind"], "NetworkPolicy")
        self.assertEqual(body["metadata"]["namespace"], "default")
        self.assertEqual(
            body["spec"]["podSelector"]["matchLabels"],
            {
                enforcer_sidecar.NETWORK_POLICY_LABEL_KEY: token,
                enforcer_sidecar.NETWORK_POLICY_TIER_LABEL_KEY: "L3",
            },
        )
        self.assertEqual(body["spec"]["policyTypes"], ["Ingress", "Egress"])
        self.assertEqual(body["spec"]["ingress"], [])
        self.assertEqual(body["spec"]["egress"], [])

    def test_l3_network_policy_is_created_after_labeling_pod(self) -> None:
        class MissingPolicy(Exception):
            status = 404

        class FakeCoreApi:
            def __init__(self) -> None:
                self.patches = []

            def patch_namespaced_pod(self, name, namespace, body):
                self.patches.append((name, namespace, body))

        class FakeNetworkingApi:
            def __init__(self) -> None:
                self.created = []

            def patch_namespaced_network_policy(self, name, namespace, body):
                raise MissingPolicy()

            def create_namespaced_network_policy(self, namespace, body):
                self.created.append((namespace, body))

        core_api = FakeCoreApi()
        networking_api = FakeNetworkingApi()

        with patch.object(enforcer_sidecar, "_init_k8s_client", return_value=core_api), \
             patch.object(enforcer_sidecar, "_init_k8s_networking_client", return_value=networking_api):
            self.assertTrue(enforcer_sidecar._apply_network_policy("default/raasa-test-benign", "L3"))

        self.assertEqual(core_api.patches[0][0:2], ("raasa-test-benign", "default"))
        patched_labels = core_api.patches[0][2]["metadata"]["labels"]
        self.assertEqual(patched_labels[enforcer_sidecar.NETWORK_POLICY_TIER_LABEL_KEY], "L3")
        self.assertEqual(len(networking_api.created), 1)
        self.assertEqual(networking_api.created[0][1]["spec"]["egress"], [])

    def test_relaxation_deletes_l3_network_policy_and_clears_labels(self) -> None:
        class FakeCoreApi:
            def __init__(self) -> None:
                self.patches = []

            def patch_namespaced_pod(self, name, namespace, body):
                self.patches.append((name, namespace, body))

        class FakeNetworkingApi:
            def __init__(self) -> None:
                self.deleted = []

            def delete_namespaced_network_policy(self, name, namespace):
                self.deleted.append((name, namespace))

        core_api = FakeCoreApi()
        networking_api = FakeNetworkingApi()

        with patch.object(enforcer_sidecar, "_init_k8s_client", return_value=core_api), \
             patch.object(enforcer_sidecar, "_init_k8s_networking_client", return_value=networking_api):
            self.assertTrue(enforcer_sidecar._apply_network_policy("default/raasa-test-benign", "L2"))

        cleared_labels = core_api.patches[0][2]["metadata"]["labels"]
        self.assertIsNone(cleared_labels[enforcer_sidecar.NETWORK_POLICY_LABEL_KEY])
        self.assertIsNone(cleared_labels[enforcer_sidecar.NETWORK_POLICY_TIER_LABEL_KEY])
        self.assertEqual(networking_api.deleted[0][1], "default")


class LsmExecBlockTests(unittest.TestCase):
    def tearDown(self) -> None:
        enforcer_sidecar._LSM_TRACKED_PIDS_BY_CONTAINER.clear()

    def test_hex_u32_uses_little_endian_bytes(self) -> None:
        self.assertEqual(enforcer_sidecar._hex_u32(0x01020304), ["04", "03", "02", "01"])

    def test_lsm_map_update_uses_bpftool_pinned_map(self) -> None:
        calls: list[list[str]] = []
        map_path = Path("/sys/fs/bpf/raasa/maps/block")

        with patch.object(enforcer_sidecar, "_bpftool_available", return_value=True), \
             patch.object(enforcer_sidecar, "_lsm_block_map_ready", return_value=True), \
             patch.object(enforcer_sidecar, "_run_command", side_effect=lambda command: calls.append(command) or ""):
            result = enforcer_sidecar._update_lsm_block_map(0x01020304, True, map_path)

        self.assertTrue(result)
        self.assertEqual(
            calls[0],
            [
                "bpftool",
                "map",
                "update",
                "pinned",
                str(map_path),
                "key",
                "hex",
                "04",
                "03",
                "02",
                "01",
                "value",
                "hex",
                "01",
                "00",
                "00",
                "00",
            ],
        )

    def test_l3_lsm_exec_block_marks_current_host_pids(self) -> None:
        updates: list[tuple[int, bool]] = []

        with patch.object(enforcer_sidecar, "_bpftool_available", return_value=True), \
             patch.object(enforcer_sidecar, "_lsm_block_map_ready", return_value=True), \
             patch.object(enforcer_sidecar, "_resolve_pod_uid", return_value="pod-uid"), \
             patch.object(enforcer_sidecar, "_find_host_pids_for_pod_uid", return_value=[1002, 1001]), \
             patch.object(
                 enforcer_sidecar,
                 "_update_lsm_block_map",
                 side_effect=lambda pid, blocked, map_path=None: updates.append((pid, blocked)) or True,
             ):
            result = enforcer_sidecar._apply_lsm_exec_block("default/raasa-test-benign", "L3")

        self.assertTrue(result)
        self.assertEqual(updates, [(1001, True), (1002, True)])
        self.assertEqual(
            enforcer_sidecar._LSM_TRACKED_PIDS_BY_CONTAINER["default/raasa-test-benign"],
            {1001, 1002},
        )

    def test_relaxing_lsm_exec_block_clears_current_and_tracked_pids(self) -> None:
        enforcer_sidecar._LSM_TRACKED_PIDS_BY_CONTAINER["default/raasa-test-benign"] = {1001}
        updates: list[tuple[int, bool]] = []

        with patch.object(enforcer_sidecar, "_bpftool_available", return_value=True), \
             patch.object(enforcer_sidecar, "_lsm_block_map_ready", return_value=True), \
             patch.object(enforcer_sidecar, "_resolve_pod_uid", return_value="pod-uid"), \
             patch.object(enforcer_sidecar, "_find_host_pids_for_pod_uid", return_value=[1002]), \
             patch.object(
                 enforcer_sidecar,
                 "_update_lsm_block_map",
                 side_effect=lambda pid, blocked, map_path=None: updates.append((pid, blocked)) or True,
             ):
            result = enforcer_sidecar._apply_lsm_exec_block("default/raasa-test-benign", "L2")

        self.assertTrue(result)
        self.assertEqual(updates, [(1001, False), (1002, False)])
        self.assertNotIn("default/raasa-test-benign", enforcer_sidecar._LSM_TRACKED_PIDS_BY_CONTAINER)


class HandleCommandValidationTests(unittest.TestCase):
    def test_handle_command_rejects_invalid_payload_before_enforcement(self) -> None:
        with patch.object(enforcer_sidecar, "_resolve_pod_interface") as resolve_mock, \
             patch.object(enforcer_sidecar, "_apply_network_throttle") as net_mock, \
             patch.object(enforcer_sidecar, "_apply_memory_limit") as mem_mock, \
             patch.object(enforcer_sidecar, "_apply_lsm_exec_block") as lsm_mock:
            self.assertFalse(enforcer_sidecar.handle_command({"container_id": "bad name", "tier": "L3"}))
        resolve_mock.assert_not_called()
        net_mock.assert_not_called()
        mem_mock.assert_not_called()
        lsm_mock.assert_not_called()

    def test_handle_command_accepts_known_good_payload(self) -> None:
        with patch.object(enforcer_sidecar, "_resolve_pod_interface", return_value="veth0"), \
             patch.object(enforcer_sidecar, "_apply_network_throttle", return_value=True) as net_mock, \
             patch.object(enforcer_sidecar, "_apply_memory_limit", return_value=False) as mem_mock, \
             patch.object(enforcer_sidecar, "_apply_network_policy", return_value=True) as policy_mock, \
             patch.object(enforcer_sidecar, "_apply_lsm_exec_block", return_value=True) as lsm_mock:
            result = enforcer_sidecar.handle_command(
                {"container_id": "default/raasa-test-benign", "tier": "L2"}
            )

        self.assertTrue(result)
        net_mock.assert_called_once_with("raasa-test-benign", "L2", "veth0")
        mem_mock.assert_called_once_with("raasa-test-benign", "L2")
        policy_mock.assert_called_once_with("default/raasa-test-benign", "L2")
        lsm_mock.assert_called_once_with("default/raasa-test-benign", "L2")

    def test_handle_command_refuses_default_interface_fallback_by_default(self) -> None:
        enforcer_sidecar._LAST_INTERFACE_BY_CONTAINER.clear()
        with patch.object(enforcer_sidecar, "_resolve_pod_interface", return_value=None), \
             patch.object(enforcer_sidecar, "_apply_network_throttle") as net_mock, \
             patch.object(enforcer_sidecar, "_apply_memory_limit") as mem_mock, \
             patch.object(enforcer_sidecar, "_apply_network_policy", return_value=False) as policy_mock, \
             patch.object(enforcer_sidecar, "_apply_lsm_exec_block", return_value=False) as lsm_mock, \
             patch.dict(enforcer_sidecar.os.environ, {}, clear=True):
            result = enforcer_sidecar.handle_command(
                {"container_id": "default/raasa-test-benign", "tier": "L2"}
            )

        self.assertFalse(result)
        policy_mock.assert_called_once_with("default/raasa-test-benign", "L2")
        lsm_mock.assert_called_once_with("default/raasa-test-benign", "L2")
        net_mock.assert_not_called()
        mem_mock.assert_not_called()

    def test_handle_command_keeps_network_policy_enforcement_when_interface_resolution_fails(self) -> None:
        enforcer_sidecar._LAST_INTERFACE_BY_CONTAINER.clear()
        with patch.object(enforcer_sidecar, "_resolve_pod_interface", return_value=None), \
             patch.object(enforcer_sidecar, "_apply_network_policy", return_value=True) as policy_mock, \
             patch.object(enforcer_sidecar, "_apply_lsm_exec_block", return_value=True) as lsm_mock, \
             patch.object(enforcer_sidecar, "_apply_network_throttle") as net_mock, \
             patch.object(enforcer_sidecar, "_apply_memory_limit") as mem_mock, \
             patch.dict(enforcer_sidecar.os.environ, {}, clear=True):
            result = enforcer_sidecar.handle_command(
                {"container_id": "default/raasa-test-benign", "tier": "L3"}
            )

        self.assertTrue(result)
        policy_mock.assert_called_once_with("default/raasa-test-benign", "L3")
        lsm_mock.assert_called_once_with("default/raasa-test-benign", "L3")
        net_mock.assert_not_called()
        mem_mock.assert_not_called()

    def test_handle_command_can_use_explicit_default_interface_fallback(self) -> None:
        enforcer_sidecar._LAST_INTERFACE_BY_CONTAINER.clear()
        with patch.object(enforcer_sidecar, "_resolve_pod_interface", return_value=None), \
             patch.object(enforcer_sidecar, "_apply_network_throttle", return_value=True) as net_mock, \
             patch.object(enforcer_sidecar, "_apply_memory_limit", return_value=False), \
             patch.object(enforcer_sidecar, "_apply_lsm_exec_block", return_value=False), \
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
                 patch.object(enforcer_sidecar, "_apply_lsm_exec_block", return_value=False), \
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
