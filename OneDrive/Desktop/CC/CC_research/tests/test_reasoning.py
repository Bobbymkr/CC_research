from datetime import datetime, timedelta, timezone
import unittest

from raasa.core.features import FeatureExtractor
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
