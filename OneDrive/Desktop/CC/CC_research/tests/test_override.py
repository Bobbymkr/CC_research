import json
from datetime import datetime, timezone
import pytest

from raasa.core.models import Assessment, Tier
from raasa.core.policy import PolicyReasoner
from raasa.core.override import set_override, load_overrides


def test_operator_override(tmp_path):
    # Ensure no old overrides interfere by setting CWD or mocking
    # For now we'll just write one and verify the behavior
    import raasa.core.override as mo
    original_path_func = mo.get_override_path
    
    try:
        # Mock the path to point to tmp_path
        mo.get_override_path = lambda workspace_dir=".": tmp_path / "overrides.json"
        
        # Initially, normal behavior
        reasoner = PolicyReasoner()
        now = datetime.now(timezone.utc)
        assessments = [
            Assessment("c1", now, risk_score=0.1, confidence_score=0.8, reasons=[])
        ]
        decisions = reasoner.decide(assessments)
        assert decisions[0].applied_tier == Tier.L1
        assert "override" not in decisions[0].reason

        # Set an override
        set_override("c1", "L3")
        
        # Verify it
        decisions_ov = reasoner.decide(assessments)
        assert decisions_ov[0].applied_tier == Tier.L3
        assert decisions_ov[0].reason == "operator override"
        
    finally:
        mo.get_override_path = original_path_func
