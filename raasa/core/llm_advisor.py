"""
LLM-Powered Policy Advisor for RAASA.

This module acts as an advanced triage override for ambiguous risk scenarios.
Instead of relying strictly on hysteresis bounds and linear thresholds,
the LLM investigates the 5D feature context and trend to issue a human-like
judgment.

Because LLM API calls have high latency (seconds), this is designed to be:
  1. Fast-failing (strict timeout).
  2. Non-blocking (it handles its own timeout/errors and returns a fallback).
  3. Only invoked for edge cases in the PolicyReasoner.
"""

import json
import logging
import os
from typing import Optional, Tuple

from raasa.core.models import Assessment, Tier

logger = logging.getLogger(__name__)

# Prompt structured to force valid JSON output.
SYSTEM_PROMPT = """You are the AI Policy Advisor for RAASA (Risk-Adaptive Autonomous Security Agent).
Your goal is to assess ambiguous container risk telemetry and recommend an enforcement tier:
- L1 (Unrestricted): Normal behavior or harmless batch jobs.
- L2 (Throttled): Suspicious behavior, needs inspection, limit resources to contain potential damage.
- L3 (Contained): Active threat (e.g. infinite loop, crypto-miner, mass port scan, syscall storm), freeze immediately.

You will receive an Assessment containing:
- risk_score: 0.0 to 1.0
- risk_trend: negative (decreasing) or positive (increasing)
- latest_features: raw telemetry values (CPU, Memory, Process, Network, Syscall)

Rules:
1. If risk_score is high but driven primarily by Memory and CPU without Syscall or Network anomalies, it might just be a heavy data batch process.
2. If Syscall rate or Network I/O is suspiciously high relative to CPU, it's likely malicious.
3. Respond ONLY in valid JSON format.

Output Format:
{
  "recommended_tier": "L1" | "L2" | "L3",
  "reason": "Short explanation of your reasoning based on the 5D features."
}"""

class LLMPolicyAdvisor:
    """Consults an LLM to resolve ambiguous risk policy decisions."""
    
    def __init__(self, timeout_seconds: float = 3.0, mock_latency: float = 0.5) -> None:
        """
        Initialize the advisor.
        
        Parameters
        ----------
        timeout_seconds: Maximum time to wait for the LLM before falling back.
        mock_latency: Simulated latency when operating without an API key.
        """
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.timeout_seconds = timeout_seconds
        self.mock_latency = mock_latency

        self._client = None
        if self.api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("openai package not installed. Falling back to mock LLM.")

    def consult(self, assessment: Assessment, proposed_tier: Tier) -> Tuple[Tier, str]:
        """
        Consult the LLM to confirm or override a proposed tier.
        
        Returns
        -------
        Tuple[Tier, str]: The decided tier and the reasoning string.
        """
        # Formulate contextual prompt
        features = assessment.latest_features
        prompt = f"""
Assessment Context:
Risk Score: {assessment.risk_score:.3f}
Risk Trend: {assessment.risk_trend:.3f}
Confidence: {assessment.confidence_score:.3f}
Proposed Tier by Rules: {proposed_tier.value}

5D Features:
- CPU: {features.cpu_signal:.3f}
- Memory: {features.memory_signal:.3f}
- Process: {features.process_signal:.3f}
- Network: {features.network_signal:.3f}
- Syscall: {features.syscall_signal:.3f}

What is your recommended tier?
"""
        
        if self._client:
            return self._call_real_llm(prompt, proposed_tier)
        else:
            return self._call_mock_llm(assessment, proposed_tier)

    def _call_real_llm(self, prompt: str, fallback_tier: Tier) -> Tuple[Tier, str]:
        import json
        try:
            # Note: We enforce a strict timeout
            response = self._client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                timeout=self.timeout_seconds,
                response_format={ "type": "json_object" }
            )
            content = response.choices[0].message.content
            if content is None:
                return fallback_tier, "LLM returned empty response -> fallback"
            
            data = json.loads(content)
            tier_str = data.get("recommended_tier", fallback_tier.value)
            reason = data.get("reason", "LLM decision")
            
            return Tier(tier_str), f"LLM: {reason}"
            
        except Exception as e:
            logger.error(f"LLM Advisor error: {e}")
            return fallback_tier, f"LLM error/timeout -> fallback ({fallback_tier.value})"

    def _call_mock_llm(self, assessment: Assessment, fallback_tier: Tier) -> Tuple[Tier, str]:
        """
        Simulated LLM reasoning based on deterministic rules so CI/CD tests can pass
        without API keys, but the reasoning process behaves structurally like an LLM.
        """
        import time
        # Simulate network latency
        time.sleep(min(self.mock_latency, self.timeout_seconds - 0.1))
        
        f = assessment.latest_features
        # Simulated LLM logic rules:
        if f.syscall_signal > 0.5 and f.network_signal < 0.1 and f.cpu_signal < 0.3:
            return Tier.L3, "LLM (Mock): High syscall with low CPU indicates stealth anomaly (L3)"
        
        if f.cpu_signal > 0.8 and f.memory_signal > 0.8 and f.syscall_signal < 0.2 and f.network_signal < 0.2:
            return Tier.L1, "LLM (Mock): High CPU/Mem but low Net/Syscall looks like benign batch job (L1)"
            
        if 0.4 < assessment.risk_score < 0.6 and assessment.risk_trend > 0:
            return Tier.L2, "LLM (Mock): Borderline trend increasing, proactive throttle (L2)"
            
        return fallback_tier, f"LLM (Mock): Agreed with rules ({fallback_tier.value})"
