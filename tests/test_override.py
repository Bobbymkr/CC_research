import json
from datetime import datetime, timezone
from pathlib import Path
import shutil

from raasa.core.models import Assessment, Tier
from raasa.core.approval import get_approval_path, load_approvals, set_approval
from raasa.core.policy import PolicyReasoner
from raasa.core.override import get_override_path, load_overrides, set_override


def test_operator_override():
    # Ensure no old overrides interfere by setting CWD or mocking
    # For now we'll just write one and verify the behavior
    import raasa.core.override as mo
    original_path_func = mo.get_override_path
    temp_dir = Path("tests/.tmp_override")
    override_path = temp_dir / "overrides.json"
    
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        # Mock the path to point to tmp_path
        mo.get_override_path = lambda workspace_dir=".": override_path
        
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
        set_override("c1", "L3", path=override_path)
        
        # Verify it
        decisions_ov = reasoner.decide(assessments)
        assert decisions_ov[0].applied_tier == Tier.L3
        assert decisions_ov[0].reason == "operator override"
        
    finally:
        mo.get_override_path = original_path_func
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_override_path_can_be_redirected_with_env(monkeypatch, tmp_path):
    override_path = tmp_path / "runtime" / "overrides.json"
    monkeypatch.setenv("RAASA_OVERRIDE_PATH", str(override_path))

    assert get_override_path() == override_path

    set_override("c2", "L2")

    assert override_path.exists()
    assert load_overrides() == {"c2": "L2"}


def test_approval_path_can_be_redirected_with_env(monkeypatch, tmp_path):
    approval_path = tmp_path / "runtime" / "approvals.json"
    monkeypatch.setenv("RAASA_APPROVAL_PATH", str(approval_path))

    assert get_approval_path() == approval_path

    set_approval("c3", "approve")

    assert approval_path.exists()
    approvals = load_approvals()
    assert approvals["c3"]["decision"] == "approve"
    assert approvals["c3"]["target_tier"] == "L3"
    assert approvals["c3"]["updated_at"]
