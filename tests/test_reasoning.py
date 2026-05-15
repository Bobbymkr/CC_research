from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import unittest

from raasa.core.approval import set_approval
from raasa.core.features import FeatureExtractor, jensen_shannon_divergence, shannon_entropy_signal
from raasa.core.models import Assessment, ContainerTelemetry, FeatureVector, Tier
from raasa.core.policy import PolicyReasoner
from raasa.core.risk_model import RiskAssessor


class FeatureExtractorTests(unittest.TestCase):
    def test_extracts_bounded_signals(self) -> None:
        telemetry = [
            ContainerTelemetry(
                container_id="c1",
                timestamp=datetime.now(timezone.utc),
                cpu_percent=125.0,
                memory_percent=20.0,
                process_count=25,
            )
        ]
        features = FeatureExtractor(process_cap=20).extract(telemetry)
        self.assertEqual(features[0].cpu_signal, 1.0)
        self.assertEqual(features[0].memory_signal, 0.2)
        self.assertEqual(features[0].process_signal, 1.0)

    def test_carries_telemetry_metadata_into_feature_vector(self) -> None:
        telemetry = [
            ContainerTelemetry(
                container_id="c1",
                timestamp=datetime.now(timezone.utc),
                cpu_percent=50.0,
                memory_percent=20.0,
                process_count=3,
                metadata={"telemetry_status": "partial", "degraded_signals": "memory:cadvisor_fallback"},
            )
        ]
        features = FeatureExtractor(process_cap=20).extract(telemetry)
        self.assertEqual(features[0].telemetry_metadata["telemetry_status"], "partial")
        self.assertIn("memory:cadvisor_fallback", features[0].telemetry_metadata["degraded_signals"])

    def test_respects_custom_syscall_cap_without_forcing_saturation(self) -> None:
        telemetry = [
            ContainerTelemetry(
                container_id="c1",
                timestamp=datetime.now(timezone.utc),
                cpu_percent=0.0,
                memory_percent=1.0,
                process_count=1,
                syscall_rate=3720.6,
            )
        ]
        features = FeatureExtractor(process_cap=20, syscall_cap=5000.0).extract(telemetry)
        self.assertAlmostEqual(features[0].syscall_signal, 3720.6 / 5000.0, places=6)
        self.assertLess(features[0].syscall_signal, 1.0)

    def test_carries_lateral_movement_signal(self) -> None:
        telemetry = [
            ContainerTelemetry(
                container_id="c1",
                timestamp=datetime.now(timezone.utc),
                cpu_percent=0.0,
                memory_percent=0.0,
                process_count=1,
                lateral_movement_signal=1.0,
            )
        ]
        features = FeatureExtractor(process_cap=20).extract(telemetry)
        self.assertEqual(features[0].lateral_movement_signal, 1.0)

    def test_jensen_shannon_divergence_is_zero_for_matching_distributions(self) -> None:
        self.assertEqual(jensen_shannon_divergence({"0": 10, "1": 5}, {"0": 20, "1": 10}), 0.0)

    def test_jensen_shannon_divergence_is_one_for_disjoint_distributions(self) -> None:
        self.assertAlmostEqual(jensen_shannon_divergence({"0": 10}, {"1": 10}), 1.0, places=6)

    def test_shannon_entropy_signal_separates_repeated_and_diverse_samples(self) -> None:
        self.assertEqual(shannon_entropy_signal(["/etc/passwd"] * 8), 0.0)
        self.assertAlmostEqual(
            shannon_entropy_signal(["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4"]),
            1.0,
            places=6,
        )

    def test_syscall_distribution_shift_becomes_feature_signal(self) -> None:
        extractor = FeatureExtractor(syscall_baseline_alpha=0.0)
        baseline = [
            ContainerTelemetry(
                container_id="c1",
                timestamp=datetime.now(timezone.utc),
                cpu_percent=0.0,
                memory_percent=0.0,
                process_count=1,
                syscall_counts={"0": 10},
            )
        ]
        shifted = [
            ContainerTelemetry(
                container_id="c1",
                timestamp=datetime.now(timezone.utc),
                cpu_percent=0.0,
                memory_percent=0.0,
                process_count=1,
                syscall_counts={"1": 10},
            )
        ]

        first = extractor.extract(baseline)[0]
        second = extractor.extract(shifted)[0]

        self.assertEqual(first.syscall_jsd_signal, 0.0)
        self.assertGreater(second.syscall_jsd_signal, 0.9)

    def test_entropy_samples_become_feature_signals(self) -> None:
        telemetry = [
            ContainerTelemetry(
                container_id="c1",
                timestamp=datetime.now(timezone.utc),
                cpu_percent=0.0,
                memory_percent=0.0,
                process_count=1,
                file_accesses=["/var/log/app.log"] * 4,
                network_destinations=["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4"],
                dns_queries=["a.example.test", "b.example.test", "c.example.test", "d.example.test"],
            )
        ]

        feature = FeatureExtractor(process_cap=20).extract(telemetry)[0]

        self.assertEqual(feature.file_entropy_signal, 0.0)
        self.assertGreater(feature.network_entropy_signal, 0.9)
        self.assertGreater(feature.dns_entropy_signal, 0.9)


class RiskAssessorTests(unittest.TestCase):
    def test_computes_bounded_risk_and_confidence(self) -> None:
        extractor = FeatureExtractor(process_cap=10)
        telemetry = [
            ContainerTelemetry(
                container_id="c1",
                timestamp=datetime.now(timezone.utc),
                cpu_percent=80.0,
                memory_percent=50.0,
                process_count=5,
            )
        ]
        features = extractor.extract(telemetry)
        assessor = RiskAssessor(confidence_window=3)
        first = assessor.assess(features)[0]
        second = assessor.assess(features)[0]
        third = assessor.assess(features)[0]

        self.assertGreater(first.risk_score, 0.0)
        self.assertLessEqual(third.risk_score, 1.0)
        self.assertGreater(third.confidence_score, first.confidence_score)
        self.assertLessEqual(third.confidence_score, 1.0)

    def test_computes_positive_trend(self) -> None:
        assessor = RiskAssessor(confidence_window=4)
        extractor = FeatureExtractor()
        
        # Low risk
        f1 = [FeatureVector("c1", datetime.now(timezone.utc), 0.25, 0.0, 0.0, 0.0)] # risk ~0.10
        assessor.assess(f1)
        assessor.assess(f1)
        
        # Suddenly high risk
        f2 = [FeatureVector("c1", datetime.now(timezone.utc), 1.0, 1.0, 0.0, 0.0)] # risk ~0.65
        a3 = assessor.assess(f2)[0]
        
        self.assertGreater(a3.risk_trend, 0.0)

    def test_preserves_partial_telemetry_metadata_in_assessment(self) -> None:
        assessor = RiskAssessor(confidence_window=3)
        features = [
            FeatureVector(
                "c1",
                datetime.now(timezone.utc),
                0.5,
                0.2,
                0.1,
                telemetry_metadata={"telemetry_status": "partial", "degraded_signals": "cpu:metrics_cache_fallback"},
            )
        ]
        result = assessor.assess(features)[0]

        self.assertEqual(result.telemetry_metadata["telemetry_status"], "partial")
        self.assertTrue(any(reason == "telemetry=partial" for reason in result.reasons))
        self.assertTrue(any("cpu:metrics_cache_fallback" in reason for reason in result.reasons))

    def test_syscall_jsd_weight_contributes_to_linear_risk(self) -> None:
        assessor = RiskAssessor(weights={"syscall_jsd": 0.50}, confidence_window=3)
        features = [
            FeatureVector(
                container_id="c1",
                timestamp=datetime.now(timezone.utc),
                cpu_signal=0.0,
                memory_signal=0.0,
                process_signal=0.0,
                syscall_jsd_signal=0.80,
            )
        ]

        result = assessor.assess(features)[0]

        self.assertAlmostEqual(result.risk_score, 0.40, places=6)
        self.assertIn("sys_jsd=0.80*0.50", result.reasons)

    def test_entropy_weights_contribute_to_linear_risk(self) -> None:
        assessor = RiskAssessor(
            weights={"file_entropy": 0.10, "network_entropy": 0.20, "dns_entropy": 0.30},
            confidence_window=3,
        )
        features = [
            FeatureVector(
                container_id="c1",
                timestamp=datetime.now(timezone.utc),
                cpu_signal=0.0,
                memory_signal=0.0,
                process_signal=0.0,
                file_entropy_signal=0.50,
                network_entropy_signal=0.50,
                dns_entropy_signal=0.50,
            )
        ]

        result = assessor.assess(features)[0]

        self.assertAlmostEqual(result.risk_score, 0.30, places=6)
        self.assertIn("file_ent=0.50*0.10", result.reasons)
        self.assertIn("net_ent=0.50*0.20", result.reasons)
        self.assertIn("dns_ent=0.50*0.30", result.reasons)

    def test_linear_risk_includes_shap_attribution_rows(self) -> None:
        assessor = RiskAssessor(weights={"cpu": 0.25, "network_entropy": 0.50}, confidence_window=3)
        features = [
            FeatureVector(
                container_id="c1",
                timestamp=datetime.now(timezone.utc),
                cpu_signal=0.40,
                memory_signal=0.0,
                process_signal=0.0,
                network_entropy_signal=0.80,
            )
        ]

        result = assessor.assess(features)[0]
        shap_total = sum(float(row["shap_value"]) for row in result.attributions)

        self.assertAlmostEqual(result.risk_score, 0.50, places=6)
        self.assertAlmostEqual(shap_total, result.risk_score, places=6)
        self.assertEqual(result.attributions[0]["feature"], "network_entropy")
        self.assertEqual(result.attributions[0]["shap_value"], 0.4)


class PolicyReasonerTests(unittest.TestCase):
    def test_trend_acceleration_bypasses_hysteresis_band(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.40, hysteresis_band=0.05)
        
        # Without trend, 0.42 is held (needs > 0.45)
        decision_hold = reasoner.decide(
            [Assessment("c1", datetime.now(timezone.utc), 0.42, 0.8, risk_trend=0.0, reasons=[])]
        )[0]
        self.assertEqual(decision_hold.applied_tier, Tier.L1)
        
        # With high trend, it accelerates and escalates
        decision_escalate = reasoner.decide(
            [Assessment("c2", datetime.now(timezone.utc), 0.42, 0.8, risk_trend=0.10, reasons=[])]
        )[0]
        self.assertEqual(decision_escalate.applied_tier, Tier.L2)

    def test_hysteresis_blocks_immediate_l2_escalation_near_boundary(self) -> None:
        reasoner = PolicyReasoner()
        timestamp = datetime.now(timezone.utc)
        decision = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp,
                    risk_score=0.42,
                    confidence_score=0.9,
                    reasons=[],
                )
            ]
        )[0]
        self.assertEqual(decision.applied_tier, Tier.L1)
        self.assertIn("boundary", decision.reason)

    def test_l3_requires_confidence(self) -> None:
        reasoner = PolicyReasoner()
        timestamp = datetime.now(timezone.utc)
        decision = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp,
                    risk_score=0.92,
                    confidence_score=0.20,
                    reasons=[],
                )
            ]
        )[0]
        self.assertEqual(decision.applied_tier, Tier.L1)
        self.assertIn("confidence", decision.reason)

    def test_partial_telemetry_still_allows_l2_escalation(self) -> None:
        reasoner = PolicyReasoner()
        timestamp = datetime.now(timezone.utc)
        decision = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp,
                    risk_score=0.50,
                    confidence_score=0.9,
                    reasons=[],
                    latest_features=FeatureVector(
                        "c1",
                        timestamp,
                        cpu_signal=0.50,
                        memory_signal=0.20,
                        process_signal=0.10,
                        telemetry_metadata={
                            "telemetry_status": "partial",
                            "degraded_signals": "memory:cadvisor_fallback",
                        },
                    ),
                    telemetry_metadata={
                        "telemetry_status": "partial",
                        "degraded_signals": "memory:cadvisor_fallback",
                    },
                )
            ]
        )[0]
        self.assertEqual(decision.applied_tier, Tier.L2)
        self.assertEqual(decision.containment_profile, "degraded_operation")

    def test_partial_telemetry_caps_new_l3_escalation_at_l2(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        decision = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp,
                    risk_score=0.85,
                    confidence_score=0.45,
                    risk_trend=0.15,
                    reasons=[],
                    latest_features=FeatureVector(
                        "c1",
                        timestamp,
                        cpu_signal=0.85,
                        memory_signal=0.20,
                        process_signal=0.35,
                        network_signal=0.30,
                        syscall_signal=0.30,
                        telemetry_metadata={
                            "telemetry_status": "partial",
                            "degraded_signals": "cpu:metrics_cache_fallback",
                        },
                    ),
                    telemetry_metadata={
                        "telemetry_status": "partial",
                        "degraded_signals": "cpu:metrics_cache_fallback",
                    },
                )
            ]
        )[0]
        self.assertEqual(decision.applied_tier, Tier.L2)
        self.assertIn("cap escalation at L2 before hard containment", decision.reason)
        self.assertEqual(decision.containment_profile, "degraded_operation")

    def test_partial_telemetry_allows_decisive_process_l3_when_degraded_signal_is_unrelated(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        decision = reasoner.decide(
            [
                Assessment(
                    container_id="process-fanout",
                    timestamp=timestamp,
                    risk_score=1.0,
                    confidence_score=0.45,
                    risk_trend=0.10,
                    reasons=[],
                    latest_features=FeatureVector(
                        "process-fanout",
                        timestamp,
                        cpu_signal=1.0,
                        memory_signal=0.05,
                        process_signal=1.0,
                        network_signal=0.0,
                        syscall_signal=0.0,
                        telemetry_metadata={
                            "telemetry_status": "partial",
                            "degraded_signals": "syscall:probe_stale",
                        },
                    ),
                    telemetry_metadata={
                        "telemetry_status": "partial",
                        "degraded_signals": "syscall:probe_stale",
                    },
                )
            ]
        )[0]

        self.assertEqual(decision.applied_tier, Tier.L3)
        self.assertIn("risk and confidence high", decision.reason)

    def test_partial_telemetry_blocks_relaxation_from_l3(self) -> None:
        reasoner = PolicyReasoner(cooldown_seconds=0, low_risk_streak_required=1)
        now = datetime.now(timezone.utc)

        first = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=now,
                    risk_score=0.90,
                    confidence_score=0.95,
                    reasons=[],
                )
            ]
        )[0]
        self.assertEqual(first.applied_tier, Tier.L3)
        self.assertEqual(first.containment_profile, "hard_containment")

        blocked = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=now + timedelta(seconds=20),
                    risk_score=0.10,
                    confidence_score=0.90,
                    reasons=[],
                    latest_features=FeatureVector(
                        "c1",
                        now + timedelta(seconds=20),
                        cpu_signal=0.10,
                        memory_signal=0.10,
                        process_signal=0.05,
                        telemetry_metadata={
                            "telemetry_status": "partial",
                            "degraded_signals": "network:cadvisor_unavailable",
                        },
                    ),
                    telemetry_metadata={
                        "telemetry_status": "partial",
                        "degraded_signals": "network:cadvisor_unavailable",
                    },
                )
            ]
        )[0]
        self.assertEqual(blocked.applied_tier, Tier.L3)
        self.assertIn("hold current tier until signals recover", blocked.reason)
        self.assertEqual(blocked.containment_profile, "hard_containment")

    def test_extreme_multi_signal_anomaly_requires_confirmation_from_l1(self) -> None:
        reasoner = PolicyReasoner()
        timestamp = datetime.now(timezone.utc)
        first = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp,
                    risk_score=0.95,
                    confidence_score=0.0,
                    risk_trend=0.10,
                    reasons=[],
                    latest_features=FeatureVector(
                        "c1",
                        timestamp,
                        cpu_signal=1.0,
                        memory_signal=0.05,
                        process_signal=0.50,
                        network_signal=0.0,
                        syscall_signal=0.60,
                    ),
                )
            ]
        )[0]
        self.assertEqual(first.applied_tier, Tier.L2)
        self.assertIn("needs confirmation", first.reason)

        second = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp + timedelta(seconds=5),
                    risk_score=0.95,
                    confidence_score=0.0,
                    risk_trend=0.10,
                    reasons=[],
                    latest_features=FeatureVector(
                        "c1",
                        timestamp + timedelta(seconds=5),
                        cpu_signal=1.0,
                        memory_signal=0.05,
                        process_signal=0.50,
                        network_signal=0.0,
                        syscall_signal=0.60,
                    ),
                )
            ]
        )[0]
        self.assertEqual(second.applied_tier, Tier.L3)
        self.assertIn("confirmed extreme multi-signal anomaly", second.reason)

    def test_bounded_cpu_syscall_pressure_caps_at_l2(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        first = reasoner.decide(
            [
                Assessment(
                    container_id="benign-pressure",
                    timestamp=timestamp,
                    risk_score=0.86,
                    confidence_score=0.0,
                    risk_trend=0.25,
                    reasons=[],
                    latest_features=FeatureVector(
                        "benign-pressure",
                        timestamp,
                        cpu_signal=0.80,
                        memory_signal=0.01,
                        process_signal=0.40,
                        network_signal=0.0,
                        syscall_signal=0.42,
                    ),
                )
            ]
        )[0]
        self.assertEqual(first.applied_tier, Tier.L2)
        self.assertIn("bounded CPU/syscall pressure profile", first.reason)

        second = reasoner.decide(
            [
                Assessment(
                    container_id="benign-pressure",
                    timestamp=timestamp + timedelta(seconds=5),
                    risk_score=1.0,
                    confidence_score=0.0,
                    risk_trend=0.30,
                    reasons=[],
                    latest_features=FeatureVector(
                        "benign-pressure",
                        timestamp + timedelta(seconds=5),
                        cpu_signal=0.96,
                        memory_signal=0.01,
                        process_signal=0.40,
                        network_signal=0.0,
                        syscall_signal=0.43,
                    ),
                )
            ]
        )[0]
        self.assertEqual(second.applied_tier, Tier.L2)
        self.assertIn("hold below L3", second.reason)

    def test_live_bounded_cpu_pressure_reaches_l2_with_low_confidence(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        decision = reasoner.decide(
            [
                Assessment(
                    container_id="benign-pressure",
                    timestamp=timestamp,
                    risk_score=0.8733,
                    confidence_score=0.0,
                    risk_trend=0.30,
                    reasons=[],
                    latest_features=FeatureVector(
                        "benign-pressure",
                        timestamp,
                        cpu_signal=1.0,
                        memory_signal=0.0157,
                        process_signal=0.50,
                        network_signal=0.0,
                        syscall_signal=0.3976,
                    ),
                )
            ]
        )[0]

        self.assertEqual(decision.applied_tier, Tier.L2)
        self.assertIn("bounded CPU/syscall pressure profile", decision.reason)

    def test_cpu_pressure_syscall_spike_without_attack_context_stays_l2(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        first = reasoner.decide(
            [
                Assessment(
                    container_id="benign-pressure",
                    timestamp=timestamp,
                    risk_score=0.9971,
                    confidence_score=0.0,
                    risk_trend=0.59,
                    reasons=[],
                    latest_features=FeatureVector(
                        "benign-pressure",
                        timestamp,
                        cpu_signal=1.0,
                        memory_signal=0.0157,
                        process_signal=0.50,
                        network_signal=0.0,
                        syscall_signal=0.2973,
                    ),
                )
            ]
        )[0]
        self.assertEqual(first.applied_tier, Tier.L2)

        second = reasoner.decide(
            [
                Assessment(
                    container_id="benign-pressure",
                    timestamp=timestamp + timedelta(seconds=10),
                    risk_score=1.0,
                    confidence_score=0.0,
                    risk_trend=-0.10,
                    reasons=[],
                    latest_features=FeatureVector(
                        "benign-pressure",
                        timestamp + timedelta(seconds=10),
                        cpu_signal=1.0,
                        memory_signal=0.0157,
                        process_signal=0.50,
                        network_signal=0.0,
                        syscall_signal=0.5088,
                    ),
                )
            ]
        )[0]

        self.assertEqual(second.applied_tier, Tier.L2)
        self.assertIn("confidence below L3 threshold", second.reason)

    def test_stronger_syscall_pressure_still_reaches_l3_after_confirmation(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        first = reasoner.decide(
            [
                Assessment(
                    container_id="syscall-attack",
                    timestamp=timestamp,
                    risk_score=0.95,
                    confidence_score=0.0,
                    risk_trend=0.20,
                    reasons=[],
                    latest_features=FeatureVector(
                        "syscall-attack",
                        timestamp,
                        cpu_signal=0.85,
                        memory_signal=0.01,
                        process_signal=0.40,
                        network_signal=0.0,
                        syscall_signal=0.65,
                    ),
                )
            ]
        )[0]
        self.assertEqual(first.applied_tier, Tier.L2)

        second = reasoner.decide(
            [
                Assessment(
                    container_id="syscall-attack",
                    timestamp=timestamp + timedelta(seconds=5),
                    risk_score=0.95,
                    confidence_score=0.0,
                    risk_trend=0.20,
                    reasons=[],
                    latest_features=FeatureVector(
                        "syscall-attack",
                        timestamp + timedelta(seconds=5),
                        cpu_signal=0.85,
                        memory_signal=0.01,
                        process_signal=0.40,
                        network_signal=0.0,
                        syscall_signal=0.65,
                    ),
                )
            ]
        )[0]
        self.assertEqual(second.applied_tier, Tier.L3)
        self.assertIn("confirmed extreme multi-signal anomaly", second.reason)

    def test_sustained_network_saturation_reaches_l3_after_confirmation(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        first = reasoner.decide(
            [
                Assessment(
                    container_id="network-exfil",
                    timestamp=timestamp,
                    risk_score=0.82,
                    confidence_score=0.0,
                    risk_trend=0.35,
                    reasons=[],
                    latest_features=FeatureVector(
                        "network-exfil",
                        timestamp,
                        cpu_signal=0.34,
                        memory_signal=0.02,
                        process_signal=0.15,
                        network_signal=1.0,
                        syscall_signal=0.0,
                    ),
                )
            ]
        )[0]
        self.assertEqual(first.applied_tier, Tier.L2)
        self.assertIn("network saturation needs confirmation", first.reason)

        second = reasoner.decide(
            [
                Assessment(
                    container_id="network-exfil",
                    timestamp=timestamp + timedelta(seconds=5),
                    risk_score=0.58,
                    confidence_score=0.0,
                    risk_trend=0.10,
                    reasons=[],
                    latest_features=FeatureVector(
                        "network-exfil",
                        timestamp + timedelta(seconds=5),
                        cpu_signal=0.0,
                        memory_signal=0.02,
                        process_signal=0.05,
                        network_signal=1.0,
                        syscall_signal=0.0,
                    ),
                )
            ]
        )[0]

        self.assertEqual(second.applied_tier, Tier.L3)
        self.assertIn("confirmed sustained network saturation", second.reason)

    def test_confirmed_network_saturation_ignores_unrelated_syscall_partial_telemetry(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        reasoner.decide(
            [
                Assessment(
                    container_id="network-burst",
                    timestamp=timestamp,
                    risk_score=0.63,
                    confidence_score=0.02,
                    risk_trend=0.28,
                    reasons=[],
                    latest_features=FeatureVector(
                        "network-burst",
                        timestamp,
                        cpu_signal=0.0,
                        memory_signal=0.02,
                        process_signal=0.15,
                        network_signal=1.0,
                        syscall_signal=0.0,
                    ),
                )
            ]
        )

        second = reasoner.decide(
            [
                Assessment(
                    container_id="network-burst",
                    timestamp=timestamp + timedelta(seconds=5),
                    risk_score=0.66,
                    confidence_score=0.0,
                    risk_trend=-0.05,
                    reasons=[],
                    latest_features=FeatureVector(
                        "network-burst",
                        timestamp + timedelta(seconds=5),
                        cpu_signal=0.06,
                        memory_signal=0.02,
                        process_signal=0.15,
                        network_signal=1.0,
                        syscall_signal=0.0,
                        telemetry_metadata={
                            "telemetry_status": "partial",
                            "degraded_signals": "syscall:probe_stale",
                        },
                    ),
                    telemetry_metadata={
                        "telemetry_status": "partial",
                        "degraded_signals": "syscall:probe_stale",
                    },
                )
            ]
        )[0]

        self.assertEqual(second.applied_tier, Tier.L3)
        self.assertIn("confirmed sustained network saturation", second.reason)

    def test_single_network_saturation_sample_stays_below_l3(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        decision = reasoner.decide(
            [
                Assessment(
                    container_id="network-burst",
                    timestamp=timestamp,
                    risk_score=0.82,
                    confidence_score=0.0,
                    risk_trend=0.35,
                    reasons=[],
                    latest_features=FeatureVector(
                        "network-burst",
                        timestamp,
                        cpu_signal=0.34,
                        memory_signal=0.02,
                        process_signal=0.15,
                        network_signal=1.0,
                        syscall_signal=0.0,
                    ),
                )
            ]
        )[0]

        self.assertEqual(decision.applied_tier, Tier.L2)
        self.assertIn("network saturation needs confirmation", decision.reason)

    def test_intermittent_network_saturation_reaches_l3_after_short_gap(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        first = reasoner.decide(
            [
                Assessment(
                    container_id="network-burst",
                    timestamp=timestamp,
                    risk_score=0.63,
                    confidence_score=0.02,
                    risk_trend=0.28,
                    reasons=[],
                    latest_features=FeatureVector(
                        "network-burst",
                        timestamp,
                        cpu_signal=0.0,
                        memory_signal=0.02,
                        process_signal=0.15,
                        network_signal=1.0,
                        syscall_signal=0.0,
                    ),
                )
            ]
        )[0]
        self.assertEqual(first.applied_tier, Tier.L2)

        for offset in (5, 10):
            reasoner.decide(
                [
                    Assessment(
                        container_id="network-burst",
                        timestamp=timestamp + timedelta(seconds=offset),
                        risk_score=0.10,
                        confidence_score=0.20,
                        risk_trend=-0.05,
                        reasons=[],
                        latest_features=FeatureVector(
                            "network-burst",
                            timestamp + timedelta(seconds=offset),
                            cpu_signal=0.0,
                            memory_signal=0.02,
                            process_signal=0.15,
                            network_signal=0.0,
                            syscall_signal=0.0,
                        ),
                    )
                ]
            )

        second = reasoner.decide(
            [
                Assessment(
                    container_id="network-burst",
                    timestamp=timestamp + timedelta(seconds=15),
                    risk_score=0.64,
                    confidence_score=0.04,
                    risk_trend=-0.05,
                    reasons=[],
                    latest_features=FeatureVector(
                        "network-burst",
                        timestamp + timedelta(seconds=15),
                        cpu_signal=0.0,
                        memory_signal=0.02,
                        process_signal=0.15,
                        network_signal=1.0,
                        syscall_signal=0.0,
                    ),
                )
            ]
        )[0]

        self.assertEqual(second.applied_tier, Tier.L3)
        self.assertIn("confirmed sustained network saturation", second.reason)

    def test_low_confidence_high_risk_without_multi_signal_support_still_holds(self) -> None:
        reasoner = PolicyReasoner()
        timestamp = datetime.now(timezone.utc)
        decision = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp,
                    risk_score=0.90,
                    confidence_score=0.0,
                    risk_trend=0.0,
                    reasons=[],
                    latest_features=FeatureVector(
                        "c1",
                        timestamp,
                        cpu_signal=0.20,
                        memory_signal=0.90,
                        process_signal=0.05,
                        network_signal=0.0,
                        syscall_signal=0.0,
                    ),
                )
            ]
        )[0]
        self.assertEqual(decision.applied_tier, Tier.L1)
        self.assertIn("confidence", decision.reason)

    def test_extreme_confirmation_resets_after_non_extreme_sample(self) -> None:
        reasoner = PolicyReasoner(cooldown_seconds=0, low_risk_streak_required=1)
        timestamp = datetime.now(timezone.utc)

        first = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp,
                    risk_score=0.95,
                    confidence_score=0.0,
                    risk_trend=0.10,
                    reasons=[],
                    latest_features=FeatureVector(
                        "c1",
                        timestamp,
                        cpu_signal=1.0,
                        memory_signal=0.05,
                        process_signal=0.50,
                        network_signal=0.0,
                        syscall_signal=0.60,
                    ),
                )
            ]
        )[0]
        self.assertEqual(first.applied_tier, Tier.L2)

        reset = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp + timedelta(seconds=5),
                    risk_score=0.10,
                    confidence_score=0.9,
                    risk_trend=-0.20,
                    reasons=[],
                    latest_features=FeatureVector(
                        "c1",
                        timestamp + timedelta(seconds=5),
                        cpu_signal=0.10,
                        memory_signal=0.05,
                        process_signal=0.05,
                        network_signal=0.0,
                        syscall_signal=0.0,
                    ),
                )
            ]
        )[0]
        self.assertEqual(reset.applied_tier, Tier.L1)

        third = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp + timedelta(seconds=10),
                    risk_score=0.95,
                    confidence_score=0.0,
                    risk_trend=0.10,
                    reasons=[],
                    latest_features=FeatureVector(
                        "c1",
                        timestamp + timedelta(seconds=10),
                        cpu_signal=1.0,
                        memory_signal=0.05,
                        process_signal=0.50,
                        network_signal=0.0,
                        syscall_signal=0.60,
                    ),
                )
            ]
        )[0]
        self.assertEqual(third.applied_tier, Tier.L2)
        self.assertIn("needs confirmation", third.reason)

    def test_sustained_high_risk_after_extreme_l2_can_finish_l3_escalation(self) -> None:
        reasoner = PolicyReasoner(l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        first = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp,
                    risk_score=0.95,
                    confidence_score=0.0,
                    risk_trend=0.10,
                    reasons=[],
                    latest_features=FeatureVector(
                        "c1",
                        timestamp,
                        cpu_signal=1.0,
                        memory_signal=0.05,
                        process_signal=0.50,
                        network_signal=0.0,
                        syscall_signal=0.60,
                    ),
                )
            ]
        )[0]
        self.assertEqual(first.applied_tier, Tier.L2)

        second = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp + timedelta(seconds=5),
                    risk_score=0.90,
                    confidence_score=0.12,
                    risk_trend=0.08,
                    reasons=[],
                    latest_features=FeatureVector(
                        "c1",
                        timestamp + timedelta(seconds=5),
                        cpu_signal=0.80,
                        memory_signal=0.05,
                        process_signal=0.20,
                        network_signal=0.0,
                        syscall_signal=0.10,
                    ),
                )
            ]
        )[0]
        self.assertEqual(second.applied_tier, Tier.L3)
        self.assertIn("sustained high risk after extreme anomaly", second.reason)

    def test_near_boundary_normal_l3_escalation_caps_at_l2_when_confidence_is_only_moderate(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        decision = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp,
                    risk_score=0.6536,
                    confidence_score=0.2590,
                    risk_trend=0.3278,
                    reasons=[],
                    latest_features=FeatureVector(
                        "c1",
                        timestamp,
                        cpu_signal=0.6429,
                        memory_signal=0.0147,
                        process_signal=0.30,
                        network_signal=0.0,
                        syscall_signal=0.2308,
                    ),
                )
            ]
        )[0]
        self.assertEqual(decision.applied_tier, Tier.L2)
        self.assertIn("cap at L2", decision.reason)

    def test_borderline_syscall_cpu_sample_caps_at_l2_without_decisive_l3_evidence(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        decision = reasoner.decide(
            [
                Assessment(
                    container_id="benign-moderate",
                    timestamp=timestamp,
                    risk_score=0.7716,
                    confidence_score=0.2093,
                    risk_trend=0.2467,
                    reasons=[],
                    latest_features=FeatureVector(
                        "benign-moderate",
                        timestamp,
                        cpu_signal=0.7502,
                        memory_signal=0.0,
                        process_signal=0.15,
                        network_signal=0.0,
                        syscall_signal=0.5014,
                    ),
                )
            ]
        )[0]

        self.assertEqual(decision.applied_tier, Tier.L2)
        self.assertIn("without decisive L3 evidence", decision.reason)

    def test_process_fanout_with_moderate_cpu_support_reaches_l3(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        decision = reasoner.decide(
            [
                Assessment(
                    container_id="process-fanout",
                    timestamp=timestamp,
                    risk_score=0.8765,
                    confidence_score=0.4895,
                    risk_trend=0.2548,
                    reasons=[],
                    latest_features=FeatureVector(
                        "process-fanout",
                        timestamp,
                        cpu_signal=0.5920,
                        memory_signal=0.0,
                        process_signal=1.0,
                        network_signal=0.0,
                        syscall_signal=0.0,
                    ),
                )
            ]
        )[0]

        self.assertEqual(decision.applied_tier, Tier.L3)
        self.assertIn("risk and confidence high", decision.reason)

    def test_near_boundary_normal_l3_escalation_still_triggers_with_strong_confidence(self) -> None:
        reasoner = PolicyReasoner(l1_max=0.35, l2_max=0.60, hysteresis_band=0.04, l3_min_confidence=0.20)
        timestamp = datetime.now(timezone.utc)

        decision = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=timestamp,
                    risk_score=0.70,
                    confidence_score=0.45,
                    risk_trend=0.15,
                    reasons=[],
                    latest_features=FeatureVector(
                        "c1",
                        timestamp,
                        cpu_signal=0.70,
                        memory_signal=0.02,
                        process_signal=0.30,
                        network_signal=0.30,
                        syscall_signal=0.24,
                    ),
                )
            ]
        )[0]
        self.assertEqual(decision.applied_tier, Tier.L3)
        self.assertIn("risk and confidence high", decision.reason)

    def test_relaxation_requires_cooldown_and_sustained_low_risk(self) -> None:
        reasoner = PolicyReasoner(cooldown_seconds=10, low_risk_streak_required=2)
        now = datetime.now(timezone.utc)

        first = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=now,
                    risk_score=0.80,
                    confidence_score=0.90,
                    reasons=[],
                )
            ]
        )[0]
        self.assertEqual(first.applied_tier, Tier.L3)

        during_cooldown = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=now + timedelta(seconds=1),
                    risk_score=0.10,
                    confidence_score=0.90,
                    reasons=[],
                )
            ]
        )[0]
        self.assertEqual(during_cooldown.applied_tier, Tier.L3)
        self.assertIn("cooldown", during_cooldown.reason)

        after_cooldown = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=now + timedelta(seconds=11),
                    risk_score=0.10,
                    confidence_score=0.90,
                    reasons=[],
                )
            ]
        )[0]
        self.assertEqual(after_cooldown.applied_tier, Tier.L2)

        final_relax = reasoner.decide(
            [
                Assessment(
                    container_id="c1",
                    timestamp=now + timedelta(seconds=22),
                    risk_score=0.10,
                    confidence_score=0.90,
                    reasons=[],
                )
            ]
        )[0]
        self.assertEqual(final_relax.applied_tier, Tier.L1)

    def test_l3_requires_explicit_approval(self) -> None:
        import raasa.core.approval as approval_module

        temp_dir = Path("tests/.tmp_approval")
        approval_path = temp_dir / "approvals.json"
        original_path_func = approval_module.get_approval_path
        shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        approval_module.get_approval_path = lambda workspace_dir=".": approval_path
        try:
            reasoner = PolicyReasoner(l3_requires_approval=True)
            now = datetime.now(timezone.utc)
            assessment = Assessment(
                container_id="c1",
                timestamp=now,
                risk_score=0.95,
                confidence_score=0.90,
                reasons=[],
            )

            pending = reasoner.decide([assessment])[0]
            self.assertEqual(pending.applied_tier, Tier.L1)
            self.assertTrue(pending.approval_required)
            self.assertEqual(pending.approval_state, "pending")

            set_approval("c1", "approve", path=approval_path)
            approved = reasoner.decide([assessment])[0]
            self.assertEqual(approved.applied_tier, Tier.L3)
            self.assertEqual(approved.approval_state, "approved")
        finally:
            approval_module.get_approval_path = original_path_func
            shutil.rmtree(temp_dir, ignore_errors=True)

class LLMPolicyAdvisorTests(unittest.TestCase):
    def test_llm_called_on_l1_l2_ambiguity(self) -> None:
        from unittest.mock import MagicMock
        from raasa.core.models import FeatureVector
        reasoner = PolicyReasoner(use_llm_advisor=True)
        # Mock the advisor to always return L3
        reasoner.llm_advisor.consult = MagicMock(return_value=(Tier.L3, "LLM: test override to L3"))
        
        now = datetime.now(timezone.utc)
        # Ambiguous risk score exactly at L1_max (0.40) + margin => proposed L2, but ambiguous
        a = Assessment(
            container_id="c1",
            timestamp=now,
            risk_score=0.42,
            confidence_score=0.9,
            reasons=[],
            latest_features=FeatureVector("c1", now, 0.1, 0.1, 0.1, 0.1, 0.1)
        )
        
        result = reasoner.decide([a])[0]
        # Should be L3 because the mock LLM overrode it!
        self.assertEqual(result.applied_tier, Tier.L3)
        self.assertIn("LLM: test override", result.reason)
        reasoner.llm_advisor.consult.assert_called_once()

    def test_mock_llm_logic_returns_l3_for_syscall_storm(self) -> None:
        from raasa.core.llm_advisor import LLMPolicyAdvisor
        from raasa.core.models import FeatureVector
        
        mock_adv = LLMPolicyAdvisor(timeout_seconds=0.5, mock_latency=0.0)
        now = datetime.now(timezone.utc)
        a = Assessment(
            container_id="c1",
            timestamp=now,
            risk_score=0.48,
            confidence_score=0.6,
            reasons=[],
            latest_features=FeatureVector("c1", now, 0.1, 0.1, 0.1, 0.05, 0.9) # High syscall, strictly low net
        )
        
        tier, reason = mock_adv.consult(a, Tier.L2)
        self.assertEqual(tier, Tier.L3)
        self.assertIn("High syscall", reason)

if __name__ == "__main__":
    unittest.main()
