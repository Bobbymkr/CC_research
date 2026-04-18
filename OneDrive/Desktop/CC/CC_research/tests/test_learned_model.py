"""Unit tests for the Isolation Forest ML risk scoring path in RiskAssessor."""
from datetime import datetime, timezone
import os
import tempfile
import unittest

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from raasa.core.models import FeatureVector
from raasa.core.risk_model import RiskAssessor


class IsolationForestRiskTests(unittest.TestCase):
    """Verify that the ML-based risk path produces correct, bounded scores."""

    @classmethod
    def setUpClass(cls) -> None:
        """Train a tiny Isolation Forest on synthetic benign data and save it."""
        rng = np.random.default_rng(42)
        # Simulate benign workloads: low on all 5 axes (cpu, mem, proc, net, syscall)
        benign = rng.uniform(0.0, 0.3, size=(200, 5))
        model = IsolationForest(n_estimators=50, contamination=0.01, random_state=42)
        model.fit(benign)

        cls._tmp_dir = tempfile.mkdtemp()
        cls._model_path = os.path.join(cls._tmp_dir, "test_iforest.pkl")
        joblib.dump(model, cls._model_path)

    # ── ML Model Loading ──────────────────────────────────────────────────

    def test_loads_ml_model_successfully(self) -> None:
        assessor = RiskAssessor(use_ml_model=True, ml_model_path=self._model_path)
        self.assertIsNotNone(assessor.ml_model)

    def test_falls_back_when_model_path_missing(self) -> None:
        assessor = RiskAssessor(use_ml_model=True, ml_model_path="/nonexistent/model.pkl")
        self.assertIsNone(assessor.ml_model)

    def test_falls_back_when_use_ml_model_false(self) -> None:
        assessor = RiskAssessor(use_ml_model=False, ml_model_path=self._model_path)
        self.assertIsNone(assessor.ml_model)

    # ── ML Scoring Correctness ────────────────────────────────────────────

    def test_benign_vector_gets_low_risk(self) -> None:
        """A clearly benign feature vector should produce risk < 0.5."""
        assessor = RiskAssessor(use_ml_model=True, ml_model_path=self._model_path)
        features = [FeatureVector("benign-1", datetime.now(timezone.utc), 0.05, 0.10, 0.02, 0.01, 0.02)]
        result = assessor.assess(features)[0]

        self.assertGreaterEqual(result.risk_score, 0.0)
        self.assertLess(result.risk_score, 0.5)
        self.assertTrue(any("ml_score" in r for r in result.reasons))

    def test_anomalous_vector_gets_high_risk(self) -> None:
        """A clearly anomalous (high on all axes) vector should produce risk > 0.5."""
        assessor = RiskAssessor(use_ml_model=True, ml_model_path=self._model_path)
        features = [FeatureVector("malicious-1", datetime.now(timezone.utc), 1.0, 1.0, 1.0, 1.0, 1.0)]
        result = assessor.assess(features)[0]

        self.assertGreater(result.risk_score, 0.5)
        self.assertLessEqual(result.risk_score, 1.0)

    def test_risk_score_always_bounded_0_1(self) -> None:
        """Regardless of input extremes, risk must be clamped to [0, 1]."""
        assessor = RiskAssessor(use_ml_model=True, ml_model_path=self._model_path)
        edge_cases = [
            FeatureVector("zero", datetime.now(timezone.utc), 0.0, 0.0, 0.0, 0.0, 0.0),
            FeatureVector("max", datetime.now(timezone.utc), 1.0, 1.0, 1.0, 1.0, 1.0),
            FeatureVector("partial", datetime.now(timezone.utc), 0.5, 0.0, 1.0, 0.0, 0.0),
        ]
        for feat in edge_cases:
            result = assessor.assess([feat])[0]
            self.assertGreaterEqual(result.risk_score, 0.0, f"Risk < 0 for {feat.container_id}")
            self.assertLessEqual(result.risk_score, 1.0, f"Risk > 1 for {feat.container_id}")

    # ── Linear Fallback Path ──────────────────────────────────────────────

    def test_linear_fallback_produces_consistent_results(self) -> None:
        """Without ML, the linear weighted sum must still work correctly."""
        assessor = RiskAssessor(use_ml_model=False)
        features = [FeatureVector("c1", datetime.now(timezone.utc), 0.80, 0.50, 0.30, 0.10, 0.0)]
        result = assessor.assess(features)[0]

        # Linear: 0.80*0.40 + 0.50*0.25 + 0.30*0.15 + 0.10*0.10 + 0.0*0.10 = 0.32 + 0.125 + 0.045 + 0.01 + 0.0 = 0.50
        self.assertAlmostEqual(result.risk_score, 0.50, places=2)
        self.assertTrue(any("cpu=" in r for r in result.reasons))

    # ── Confidence & Trend still work under ML ────────────────────────────

    def test_confidence_increases_with_repeated_ml_assessments(self) -> None:
        assessor = RiskAssessor(
            confidence_window=3, use_ml_model=True, ml_model_path=self._model_path
        )
        features = [FeatureVector("c1", datetime.now(timezone.utc), 0.10, 0.10, 0.10, 0.10, 0.10)]

        first = assessor.assess(features)[0]
        assessor.assess(features)
        third = assessor.assess(features)[0]

        self.assertGreater(third.confidence_score, first.confidence_score)

    def test_trend_computed_under_ml_path(self) -> None:
        assessor = RiskAssessor(
            confidence_window=4, use_ml_model=True, ml_model_path=self._model_path
        )
        # Feed low-risk first
        low = [FeatureVector("c1", datetime.now(timezone.utc), 0.05, 0.05, 0.05, 0.05, 0.05)]
        assessor.assess(low)
        assessor.assess(low)

        # Then high-risk
        high = [FeatureVector("c1", datetime.now(timezone.utc), 1.0, 1.0, 1.0, 1.0, 1.0)]
        result = assessor.assess(high)[0]

        self.assertGreater(result.risk_trend, 0.0)


if __name__ == "__main__":
    unittest.main()
