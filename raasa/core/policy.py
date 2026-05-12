from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Iterable, List

from raasa.core.approval import load_approvals
from raasa.core.llm_advisor import LLMPolicyAdvisor
from raasa.core.models import Assessment, PolicyDecision, Tier
from raasa.core.override import load_overrides

TIER_CONTAINMENT_PROFILES = {
    Tier.L1: "observe_only",
    Tier.L2: "degraded_operation",
    Tier.L3: "hard_containment",
}


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
        partial_telemetry_caps_l3: bool = True,
        partial_telemetry_blocks_relaxation: bool = True,
    ) -> None:
        self.l1_max = l1_max
        self.l2_max = l2_max
        self.hysteresis_band = hysteresis_band
        self.cooldown_seconds = cooldown_seconds
        self.l3_min_confidence = l3_min_confidence
        self.low_risk_streak_required = low_risk_streak_required
        self.l3_requires_approval = l3_requires_approval
        self.partial_telemetry_caps_l3 = partial_telemetry_caps_l3
        self.partial_telemetry_blocks_relaxation = partial_telemetry_blocks_relaxation
        self.current_tiers: dict[str, Tier] = defaultdict(lambda: Tier.L1)
        self.cooldown_until: dict[str, datetime] = {}
        self.low_risk_streaks: dict[str, int] = defaultdict(int)
        self.extreme_l3_streaks: dict[str, int] = defaultdict(int)
        self.network_l3_streaks: dict[str, int] = defaultdict(int)
        self.network_l3_misses: dict[str, int] = defaultdict(int)

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
                            containment_profile=self._containment_profile(applied_tier),
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
                self.network_l3_streaks[item.container_id] = 0
                self.network_l3_misses[item.container_id] = 0
                reason = "invalid assessment -> safe hold"
            else:
                self._update_low_risk_streak(item.container_id, item.risk_score)
                network_l3_streak = self._update_network_l3_streak(item.container_id, item)
                if self._should_block_relaxation_due_to_partial_telemetry(previous_tier, proposed_tier, item):
                    self.extreme_l3_streaks[item.container_id] = 0
                    reason = self._partial_telemetry_reason(item, "hold current tier until signals recover")
                elif self._is_sustained_network_l3_candidate(item, network_l3_streak):
                    self.extreme_l3_streaks[item.container_id] = 0
                    applied_tier, reason = self._handle_sustained_network_escalation(
                        previous_tier,
                        network_l3_streak,
                    )
                elif proposed_tier.value > previous_tier.value:
                    applied_tier, reason = self._handle_escalation(previous_tier, proposed_tier, item)
                    applied_tier, reason = self._apply_partial_telemetry_escalation_guard(
                        previous_tier,
                        applied_tier,
                        item,
                        reason,
                    )
                elif proposed_tier.value < previous_tier.value:
                    applied_tier, reason = self._handle_relaxation(
                        previous_tier,
                        proposed_tier,
                        item,
                        cooldown_active,
                    )
                else:
                    if self._is_partial_telemetry(item):
                        reason = self._partial_telemetry_reason(item, "hold current tier")
                    else:
                        reason = "risk within current tier band -> hold"

                if applied_tier.value > previous_tier.value:
                    applied_tier, reason = self._apply_partial_telemetry_escalation_guard(
                        previous_tier,
                        applied_tier,
                        item,
                        reason,
                    )

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
                    containment_profile=self._containment_profile(applied_tier),
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

    def _update_network_l3_streak(self, container_id: str, item: Assessment) -> int:
        features = item.latest_features
        if (
            features is not None
            and features.network_signal >= 0.95
            and item.risk_score >= self.l1_max
        ):
            self.network_l3_streaks[container_id] = min(self.network_l3_streaks[container_id] + 1, 2)
            self.network_l3_misses[container_id] = 0
        else:
            self.network_l3_misses[container_id] += 1
            if self.network_l3_misses[container_id] > 2:
                self.network_l3_streaks[container_id] = 0
                self.network_l3_misses[container_id] = 0
        return self.network_l3_streaks[container_id]

    def _is_sustained_network_l3_candidate(self, item: Assessment, network_l3_streak: int) -> bool:
        features = item.latest_features
        return (
            features is not None
            and features.network_signal >= 0.95
            and item.risk_score >= self.l1_max
            and network_l3_streak > 0
        )

    def _handle_sustained_network_escalation(
        self,
        previous_tier: Tier,
        network_l3_streak: int,
    ) -> tuple[Tier, str]:
        if network_l3_streak < 2:
            if previous_tier is Tier.L1:
                return Tier.L2, "network saturation needs confirmation -> escalate to L2"
            return previous_tier, "network saturation needs confirmation -> hold below L3"
        return Tier.L3, "confirmed sustained network saturation -> escalate to L3 hard containment"

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

        if self.extreme_l3_streaks[item.container_id] == 0 and self._is_bounded_l2_pressure_profile(item):
            self.extreme_l3_streaks[item.container_id] = 0
            if previous_tier is Tier.L1:
                return Tier.L2, "bounded CPU/syscall pressure profile -> cap at L2"
            return previous_tier, "bounded CPU/syscall pressure profile -> hold below L3"

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
                return Tier.L3, reason.replace("escalate to L3", "escalate to L3 hard containment")
            if (
                previous_tier is Tier.L2
                and self.extreme_l3_streaks[item.container_id] > 0
                and item.risk_score >= max(self.l2_max + self.hysteresis_band, 0.85)
                and item.confidence_score >= max(self.l3_min_confidence * 0.5, 0.10)
            ):
                reason = "sustained high risk after extreme anomaly -> escalate to L3 hard containment"
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

        if item.risk_score >= self.l2_max + self.hysteresis_band - trend_accelerator:
            if not self._has_decisive_l3_evidence(item):
                self.extreme_l3_streaks[item.container_id] = 0
                reason = "high risk without decisive L3 evidence -> cap at L2"
                if trend_accelerator > 0:
                    reason += " (accelerated by positive risk trend)"
                if previous_tier is Tier.L1:
                    return Tier.L2, reason
                return previous_tier, reason.replace("cap at L2", "hold below L3")

            self.extreme_l3_streaks[item.container_id] = 0
            reason = "risk and confidence high -> escalate to L3 hard containment"
            if trend_accelerator > 0:
                reason += " (accelerated by positive risk trend)"
            return Tier.L3, reason
        self.extreme_l3_streaks[item.container_id] = 0
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
        if self._is_bounded_l2_pressure_profile(item):
            return False

        cpu_high = features.cpu_signal >= 0.75
        process_high = features.process_signal >= 0.35
        process_extreme = features.process_signal >= 0.60
        process_cpu_support = features.cpu_signal >= 0.50
        syscall_high = features.syscall_signal >= 0.60
        network_high = features.network_signal >= 0.25
        memory_high = features.memory_signal >= 0.50

        return (
            (syscall_high and (cpu_high or process_high))
            or (network_high and (cpu_high or process_high or syscall_high))
            or (process_extreme and process_cpu_support)
            or (memory_high and (cpu_high or process_high))
        )

    def _has_decisive_l3_evidence(self, item: Assessment) -> bool:
        """
        Gate the ordinary L3 path on signal shape, not only aggregate risk.

        A single free-tier sample can combine capped CPU and borderline local
        syscall activity into an L3-sized risk score. Hard containment should
        require evidence that points beyond ordinary CPU pressure: strong
        process fanout, network activity, high syscall pressure with support,
        or memory pressure with support.
        """
        features = item.latest_features
        if features is None:
            return item.confidence_score >= max(self.l3_min_confidence, 0.65)

        cpu_high = features.cpu_signal >= 0.75
        process_high = features.process_signal >= 0.35
        process_extreme = features.process_signal >= 0.60
        process_cpu_support = features.cpu_signal >= 0.50
        syscall_decisive = features.syscall_signal >= 0.60
        network_decisive = features.network_signal >= 0.25
        memory_decisive = features.memory_signal >= 0.50

        return (
            (syscall_decisive and (cpu_high or process_high))
            or network_decisive
            or (process_extreme and process_cpu_support)
            or (memory_decisive and (cpu_high or process_high))
        )

    def _is_bounded_l2_pressure_profile(self, item: Assessment) -> bool:
        """
        Identify bounded CPU-heavy pressure that should degrade before hard containment.

        Free-tier AWS runs showed benign, capped CPU pressure can oscillate between
        idle and saturated samples. With the old two-signal extreme rule, that shape
        escalated to L3 even though the evidence was CPU/local-syscall pressure, not
        strong lateral, memory, or high-rate syscall abuse. Keep this narrow: L3 is
        still available when syscall, network, memory, or process fanout is decisive.
        """
        features = item.latest_features
        if features is None:
            return False
        return (
            features.cpu_signal >= 0.75
            and features.process_signal <= 0.50
            and features.syscall_signal < 0.50
            and features.network_signal < 0.05
            and features.memory_signal < 0.10
        )

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

    def _containment_profile(self, tier: Tier) -> str:
        return TIER_CONTAINMENT_PROFILES.get(tier, "observe_only")

    def _telemetry_metadata(self, item: Assessment) -> dict[str, str]:
        if item.telemetry_metadata:
            return item.telemetry_metadata
        if item.latest_features is not None:
            metadata = getattr(item.latest_features, "telemetry_metadata", {}) or {}
            return dict(metadata)
        return {}

    def _is_partial_telemetry(self, item: Assessment) -> bool:
        telemetry_status = self._telemetry_metadata(item).get("telemetry_status", "")
        return telemetry_status in {"partial", "fallback"}

    def _partial_telemetry_reason(self, item: Assessment, action: str) -> str:
        metadata = self._telemetry_metadata(item)
        degraded = metadata.get("degraded_signals", "")
        suffix = f" ({degraded})" if degraded and degraded != "none" else ""
        return f"partial telemetry{suffix} -> {action}"

    def _should_block_relaxation_due_to_partial_telemetry(
        self,
        previous_tier: Tier,
        proposed_tier: Tier,
        item: Assessment,
    ) -> bool:
        return (
            self.partial_telemetry_blocks_relaxation
            and self._is_partial_telemetry(item)
            and proposed_tier.value < previous_tier.value
        )

    def _apply_partial_telemetry_escalation_guard(
        self,
        previous_tier: Tier,
        candidate_tier: Tier,
        item: Assessment,
        reason: str,
    ) -> tuple[Tier, str]:
        if candidate_tier is not Tier.L3 or not self.partial_telemetry_caps_l3 or not self._is_partial_telemetry(item):
            return candidate_tier, reason
        if not self._partial_telemetry_should_cap_l3(item, reason):
            return candidate_tier, reason
        if previous_tier is Tier.L3:
            return candidate_tier, self._partial_telemetry_reason(item, "maintain L3 hard containment")
        fallback_tier = Tier.L2 if previous_tier is Tier.L1 else previous_tier
        return fallback_tier, self._partial_telemetry_reason(item, "cap escalation at L2 before hard containment")

    def _partial_telemetry_should_cap_l3(self, item: Assessment, reason: str) -> bool:
        metadata = self._telemetry_metadata(item)
        degraded = metadata.get("degraded_signals", "")
        features = item.latest_features

        if "confirmed sustained network saturation" in reason and "network:" not in degraded:
            return False

        if features is None:
            return True

        cpu_degraded = "cpu:" in degraded
        memory_degraded = "memory:" in degraded
        syscall_degraded = "syscall:" in degraded

        cpu_high = features.cpu_signal >= 0.75 and not cpu_degraded
        cpu_support = features.cpu_signal >= 0.50 and not cpu_degraded
        process_high = features.process_signal >= 0.35
        process_extreme = features.process_signal >= 0.60
        syscall_decisive = features.syscall_signal >= 0.60 and not syscall_degraded
        memory_decisive = features.memory_signal >= 0.50 and not memory_degraded

        if process_extreme and cpu_support:
            return False
        if syscall_decisive and (cpu_high or process_high):
            return False
        if memory_decisive and (cpu_high or process_high):
            return False
        return True

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
