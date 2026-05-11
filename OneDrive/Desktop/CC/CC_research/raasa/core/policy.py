from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Iterable, List

from raasa.core.approval import load_approvals
from raasa.core.llm_advisor import LLMPolicyAdvisor
from raasa.core.models import Assessment, PolicyDecision, Tier
from raasa.core.override import load_overrides


class PolicyReasoner:
    """Chooses tiers and applies safe autonomy rules."""

    def __init__(
        self,
        l1_max: float = 0.40,
        l2_max: float = 0.70,
        hysteresis_band: float = 0.05,
        cooldown_seconds: int = 15,
        l3_min_confidence: float = 0.65,
        low_risk_streak_required: int = 2,
        l3_requires_approval: bool = False,
        use_llm_advisor: bool = False,
    ) -> None:
        self.l1_max = l1_max
        self.l2_max = l2_max
        self.hysteresis_band = hysteresis_band
        self.cooldown_seconds = cooldown_seconds
        self.l3_min_confidence = l3_min_confidence
        self.low_risk_streak_required = low_risk_streak_required
        self.l3_requires_approval = l3_requires_approval
        self.current_tiers: dict[str, Tier] = defaultdict(lambda: Tier.L1)
        self.cooldown_until: dict[str, datetime] = {}
        self.low_risk_streaks: dict[str, int] = defaultdict(int)
        self.extreme_l3_streaks: dict[str, int] = defaultdict(int)

        self.use_llm_advisor = use_llm_advisor
        self.llm_advisor = LLMPolicyAdvisor() if use_llm_advisor else None

    def decide(self, assessments: Iterable[Assessment]) -> List[PolicyDecision]:
        decisions: List[PolicyDecision] = []
        overrides = load_overrides()
        approvals = load_approvals()

        for item in assessments:
            previous_tier = self.current_tiers[item.container_id]
            proposed_tier = self._tier_from_risk(item.risk_score)
            cooldown_active = self._is_cooldown_active(item.container_id, item.timestamp)

            forced_tier_str = overrides.get(item.container_id)
            if forced_tier_str:
                try:
                    applied_tier = Tier(forced_tier_str)
                except ValueError:
                    applied_tier = previous_tier
                else:
                    action_required = applied_tier != previous_tier
                    if action_required:
                        self.current_tiers[item.container_id] = applied_tier
                        self.cooldown_until[item.container_id] = item.timestamp + timedelta(
                            seconds=self.cooldown_seconds
                        )
                    decisions.append(
                        PolicyDecision(
                            container_id=item.container_id,
                            timestamp=item.timestamp,
                            previous_tier=previous_tier,
                            proposed_tier=proposed_tier,
                            applied_tier=applied_tier,
                            reason="operator override",
                            action_required=action_required,
                            cooldown_active=cooldown_active,
                            approval_required=False,
                            approval_state="forced",
                        )
                    )
                    continue

            applied_tier = previous_tier
            reason = "hold current tier"

            if not self._valid_assessment(item):
                self.extreme_l3_streaks[item.container_id] = 0
                reason = "invalid assessment -> safe hold"
            else:
                self._update_low_risk_streak(item.container_id, item.risk_score)
                if proposed_tier.value > previous_tier.value:
                    applied_tier, reason = self._handle_escalation(previous_tier, proposed_tier, item)
                elif proposed_tier.value < previous_tier.value:
                    applied_tier, reason = self._handle_relaxation(
                        previous_tier,
                        proposed_tier,
                        item,
                        cooldown_active,
                    )
                else:
                    reason = "risk within current tier band -> hold"

            applied_tier, reason, approval_required, approval_state = self._apply_l3_approval_gate(
                container_id=item.container_id,
                previous_tier=previous_tier,
                candidate_tier=applied_tier,
                reason=reason,
                approvals=approvals,
            )

            action_required = applied_tier != previous_tier
            if action_required:
                self.current_tiers[item.container_id] = applied_tier
                self.cooldown_until[item.container_id] = item.timestamp + timedelta(
                    seconds=self.cooldown_seconds
                )

            decisions.append(
                PolicyDecision(
                    container_id=item.container_id,
                    timestamp=item.timestamp,
                    previous_tier=previous_tier,
                    proposed_tier=proposed_tier,
                    applied_tier=applied_tier,
                    reason=reason,
                    action_required=action_required,
                    cooldown_active=cooldown_active,
                    approval_required=approval_required,
                    approval_state=approval_state,
                )
            )
        return decisions

    def _tier_from_risk(self, risk: float) -> Tier:
        if risk < self.l1_max:
            return Tier.L1
        if risk < self.l2_max:
            return Tier.L2
        return Tier.L3

    def _valid_assessment(self, item: Assessment) -> bool:
        return 0.0 <= item.risk_score <= 1.0 and 0.0 <= item.confidence_score <= 1.0

    def _is_cooldown_active(self, container_id: str, timestamp: datetime) -> bool:
        target = self.cooldown_until.get(container_id)
        if target is None:
            return False
        return timestamp < target

    def _update_low_risk_streak(self, container_id: str, risk: float) -> None:
        if risk <= max(self.l1_max - self.hysteresis_band, 0.0):
            self.low_risk_streaks[container_id] += 1
        else:
            self.low_risk_streaks[container_id] = 0

    def _handle_escalation(
        self,
        previous_tier: Tier,
        proposed_tier: Tier,
        item: Assessment,
    ) -> tuple[Tier, str]:
        trend_accelerator = self.hysteresis_band if getattr(item, "risk_trend", 0.0) > 0.05 else 0.0

        if proposed_tier is Tier.L2:
            self.extreme_l3_streaks[item.container_id] = 0
            ambiguous_l1_l2 = abs(item.risk_score - self.l1_max) <= self.hysteresis_band + trend_accelerator
            if ambiguous_l1_l2 and self.use_llm_advisor and self.llm_advisor:
                return self.llm_advisor.consult(item, proposed_tier)

            if item.risk_score >= self.l1_max + self.hysteresis_band - trend_accelerator:
                reason = "risk above L2 hysteresis threshold -> escalate"
                if trend_accelerator > 0:
                    reason += " (accelerated by positive risk trend)"
                return Tier.L2, reason
            return previous_tier, "risk near L1/L2 boundary -> hold"

        ambiguous_l2_l3 = (
            abs(item.risk_score - self.l2_max) <= self.hysteresis_band + trend_accelerator
            or item.confidence_score < self.l3_min_confidence
        )
        if ambiguous_l2_l3 and self.use_llm_advisor and self.llm_advisor:
            self.extreme_l3_streaks[item.container_id] = 0
            return self.llm_advisor.consult(item, proposed_tier)

        if item.confidence_score < self.l3_min_confidence:
            if self._is_extreme_l3_candidate(item):
                streak = self.extreme_l3_streaks[item.container_id] + 1
                self.extreme_l3_streaks[item.container_id] = streak
                if previous_tier is Tier.L1 and streak < 2:
                    reason = "extreme anomaly needs confirmation -> escalate to L2"
                    if trend_accelerator > 0:
                        reason += " (accelerated by positive risk trend)"
                    return Tier.L2, reason
                reason = "confirmed extreme multi-signal anomaly -> escalate to L3 despite low confidence"
                if trend_accelerator > 0:
                    reason += " (accelerated by positive risk trend)"
                return Tier.L3, reason
            if (
                previous_tier is Tier.L2
                and self.extreme_l3_streaks[item.container_id] > 0
                and item.risk_score >= max(self.l2_max + self.hysteresis_band, 0.85)
                and item.confidence_score >= max(self.l3_min_confidence * 0.5, 0.10)
            ):
                reason = "sustained high risk after extreme anomaly -> escalate to L3"
                if trend_accelerator > 0:
                    reason += " (accelerated by positive risk trend)"
                return Tier.L3, reason
            self.extreme_l3_streaks[item.container_id] = 0
            return previous_tier, "risk high but confidence below L3 threshold -> hold"

        normal_l3_confidence = self._normal_l3_confidence_threshold(item)
        if item.confidence_score < normal_l3_confidence:
            self.extreme_l3_streaks[item.container_id] = 0
            if previous_tier is Tier.L1:
                reason = "high risk but confidence below normal L3 threshold -> cap at L2"
                if trend_accelerator > 0:
                    reason += " (accelerated by positive risk trend)"
                return Tier.L2, reason
            return previous_tier, "risk high but confidence below normal L3 threshold -> hold"

        self.extreme_l3_streaks[item.container_id] = 0
        if item.risk_score >= self.l2_max + self.hysteresis_band - trend_accelerator:
            reason = "risk and confidence high -> escalate to L3"
            if trend_accelerator > 0:
                reason += " (accelerated by positive risk trend)"
            return Tier.L3, reason
        return previous_tier, "risk near L2/L3 boundary -> hold"

    def _normal_l3_confidence_threshold(self, item: Assessment) -> float:
        """
        Require extra confidence for near-boundary L3 jumps.

        Live soak evidence showed moderate-load cycles occasionally reaching a
        low-but-nonzero confidence that was enough for the ordinary L3 path,
        even though the signal shape looked more like an L2 event. We keep the
        extreme low-confidence escape hatch for obvious spikes, but for the
        normal path we ask for stronger confidence until risk is well above the
        L2/L3 boundary.
        """
        elevated_threshold = max(self.l3_min_confidence, 0.35)
        if item.risk_score < max(self.l2_max + self.hysteresis_band + 0.10, 0.75):
            return elevated_threshold
        return self.l3_min_confidence

    def _is_extreme_l3_candidate(self, item: Assessment) -> bool:
        """
        Escalate obvious high-severity spikes even when short-window confidence is low.

        In the K8s backend, stressy workloads can alternate between near-idle and
        saturated samples across a few 5s ticks, which drives the stability-based
        confidence score to zero. For clear multi-signal anomalies we still want
        to contain quickly instead of waiting for a smoother history window.
        """
        features = item.latest_features
        if features is None:
            return False
        if item.risk_score < max(self.l2_max + self.hysteresis_band, 0.80):
            return False

        strong_signals = 0
        if features.cpu_signal >= 0.75:
            strong_signals += 1
        if features.process_signal >= 0.35:
            strong_signals += 1
        if features.syscall_signal >= 0.25:
            strong_signals += 1
        if features.network_signal >= 0.25:
            strong_signals += 1
        return strong_signals >= 2

    def _handle_relaxation(
        self,
        previous_tier: Tier,
        proposed_tier: Tier,
        item: Assessment,
        cooldown_active: bool,
    ) -> tuple[Tier, str]:
        self.extreme_l3_streaks[item.container_id] = 0
        if cooldown_active:
            return previous_tier, "cooldown active -> hold"
        if self.low_risk_streaks[item.container_id] < self.low_risk_streak_required:
            return previous_tier, "low-risk streak not long enough -> hold"
        if previous_tier is Tier.L3 and item.risk_score < self.l2_max - self.hysteresis_band:
            return Tier.L2, "sustained lower risk -> relax to L2"
        if previous_tier is Tier.L2 and item.risk_score < self.l1_max - self.hysteresis_band:
            return Tier.L1, "sustained low risk -> relax to L1"
        return previous_tier, "risk still inside hysteresis band -> hold"

    def _apply_l3_approval_gate(
        self,
        container_id: str,
        previous_tier: Tier,
        candidate_tier: Tier,
        reason: str,
        approvals: dict[str, dict[str, str]],
    ) -> tuple[Tier, str, bool, str]:
        if candidate_tier is not Tier.L3 or not self.l3_requires_approval:
            return candidate_tier, reason, False, "not_needed"

        approval = approvals.get(container_id, {})
        target_tier = approval.get("target_tier", "").upper()
        decision = approval.get("decision", "").lower()

        if target_tier != "L3" or not decision:
            return previous_tier, "L3 approval required -> hold pending approval", True, "pending"
        if decision == "approve":
            return candidate_tier, f"{reason} (operator approved L3)", False, "approved"
        if decision == "reject":
            return previous_tier, "L3 approval rejected -> hold", False, "rejected"
        return previous_tier, "L3 approval required -> hold pending approval", True, "pending"
