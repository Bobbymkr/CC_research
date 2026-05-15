"""Stackelberg weight optimizer for the RAASA linear risk model.

The defender commits to a risk-weight vector over RAASA's current five scalar
signals. A rational attacker observes that vector and chooses the evasion
profile that maximizes residual payoff. The optimizer solves the defender's
minimax problem as a linear program:

    minimize_w max_i reward_i - evasion_cost_i - dot(w, signal_i)

The result is not a replacement for empirical validation. It is a formal,
reproducible policy baseline that makes the current weight choice harder to
game than hand-tuned observation alone.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
from scipy.optimize import linprog


SIGNAL_ORDER = ("cpu", "memory", "process", "network", "syscall")
EMPIRICAL_WEIGHTS = {
    "cpu": 0.40,
    "memory": 0.25,
    "process": 0.15,
    "network": 0.10,
    "syscall": 0.10,
}


@dataclass(frozen=True)
class AttackProfile:
    """Follower strategy used in the Stackelberg game."""

    name: str
    signals: Mapping[str, float]
    reward: float
    evasion_cost: float = 0.0

    def signal_vector(self, signal_order: Sequence[str] = SIGNAL_ORDER) -> np.ndarray:
        values = np.array([float(self.signals.get(name, 0.0)) for name in signal_order], dtype=float)
        if np.any(values < 0.0) or np.any(values > 1.0):
            raise ValueError(f"{self.name} has signals outside [0, 1]: {values!r}")
        return values

    @property
    def net_reward(self) -> float:
        return float(self.reward) - float(self.evasion_cost)


@dataclass(frozen=True)
class StackelbergSolution:
    """Solver output for the defender-leader minimax problem."""

    weights: dict[str, float]
    value: float
    attacker_payoffs: dict[str, float]
    worst_response: str
    empirical_payoffs: dict[str, float]
    empirical_worst_response: str
    success: bool
    message: str

    @property
    def weight_sum(self) -> float:
        return sum(self.weights.values())

    @property
    def empirical_value(self) -> float:
        return max(self.empirical_payoffs.values())

    @property
    def payoff_reduction(self) -> float:
        return self.empirical_value - self.value

    def to_dict(self) -> dict:
        return {
            "weights": self.weights,
            "weight_sum": self.weight_sum,
            "equilibrium_attacker_payoff": self.value,
            "worst_response": self.worst_response,
            "attacker_payoffs": self.attacker_payoffs,
            "empirical_weights": EMPIRICAL_WEIGHTS,
            "empirical_attacker_payoff": self.empirical_value,
            "empirical_worst_response": self.empirical_worst_response,
            "empirical_payoffs": self.empirical_payoffs,
            "payoff_reduction": self.payoff_reduction,
            "success": self.success,
            "message": self.message,
        }


def default_attack_profiles() -> list[AttackProfile]:
    """Return a small adversary library calibrated to current RAASA signals."""

    return [
        AttackProfile(
            name="slow_exfiltration",
            signals={"cpu": 0.12, "memory": 0.10, "process": 0.08, "network": 0.24, "syscall": 0.12},
            reward=0.92,
            evasion_cost=0.06,
        ),
        AttackProfile(
            name="crypto_miner_mimicry",
            signals={"cpu": 0.92, "memory": 0.32, "process": 0.18, "network": 0.03, "syscall": 0.10},
            reward=0.74,
            evasion_cost=0.12,
        ),
        AttackProfile(
            name="syscall_burst_escape",
            signals={"cpu": 0.34, "memory": 0.18, "process": 0.46, "network": 0.08, "syscall": 0.90},
            reward=0.84,
            evasion_cost=0.10,
        ),
        AttackProfile(
            name="side_channel_probe",
            signals={"cpu": 0.58, "memory": 0.09, "process": 0.05, "network": 0.02, "syscall": 0.12},
            reward=0.94,
            evasion_cost=0.03,
        ),
        AttackProfile(
            name="lateral_movement_probe",
            signals={"cpu": 0.28, "memory": 0.12, "process": 0.40, "network": 0.28, "syscall": 0.42},
            reward=0.86,
            evasion_cost=0.11,
        ),
        AttackProfile(
            name="fork_bomb_probe",
            signals={"cpu": 0.66, "memory": 0.44, "process": 0.95, "network": 0.02, "syscall": 0.72},
            reward=0.78,
            evasion_cost=0.16,
        ),
    ]


def normalize_weights(weights: Mapping[str, float], signal_order: Sequence[str] = SIGNAL_ORDER) -> np.ndarray:
    values = np.array([float(weights.get(name, 0.0)) for name in signal_order], dtype=float)
    total = float(values.sum())
    if total <= 0.0:
        raise ValueError("Weight vector must have positive mass.")
    return values / total


def attacker_payoffs(
    weights: Mapping[str, float],
    profiles: Sequence[AttackProfile],
    signal_order: Sequence[str] = SIGNAL_ORDER,
    detection_multiplier: float = 1.0,
) -> dict[str, float]:
    w = normalize_weights(weights, signal_order)
    payoffs: dict[str, float] = {}
    for profile in profiles:
        detection_gain = detection_multiplier * float(np.dot(w, profile.signal_vector(signal_order)))
        payoffs[profile.name] = profile.net_reward - detection_gain
    return payoffs


def solve_stackelberg_game(
    profiles: Sequence[AttackProfile] | None = None,
    signal_order: Sequence[str] = SIGNAL_ORDER,
    min_weight: float = 0.05,
    max_weight: float = 0.55,
    detection_multiplier: float = 1.0,
) -> StackelbergSolution:
    """Solve the defender-leader minimax problem for RAASA risk weights."""

    attack_profiles = list(profiles or default_attack_profiles())
    if not attack_profiles:
        raise ValueError("At least one attack profile is required.")
    if min_weight < 0.0 or max_weight <= 0.0 or min_weight > max_weight:
        raise ValueError("Invalid weight bounds.")

    n = len(signal_order)
    if min_weight * n > 1.0 or max_weight * n < 1.0:
        raise ValueError("Weight bounds make the simplex infeasible.")

    c = np.zeros(n + 1)
    c[-1] = 1.0
    a_ub = []
    b_ub = []
    for profile in attack_profiles:
        row = np.zeros(n + 1)
        row[:n] = -detection_multiplier * profile.signal_vector(signal_order)
        row[-1] = -1.0
        a_ub.append(row)
        b_ub.append(-profile.net_reward)

    a_eq = np.zeros((1, n + 1))
    a_eq[0, :n] = 1.0
    b_eq = np.array([1.0])
    bounds = [(min_weight, max_weight) for _ in range(n)] + [(None, None)]

    result = linprog(
        c,
        A_ub=np.array(a_ub),
        b_ub=np.array(b_ub),
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )
    if not result.success:
        raise RuntimeError(f"Stackelberg optimization failed: {result.message}")

    weights = {name: float(value) for name, value in zip(signal_order, result.x[:n])}
    payoffs = attacker_payoffs(weights, attack_profiles, signal_order, detection_multiplier)
    empirical = attacker_payoffs(EMPIRICAL_WEIGHTS, attack_profiles, signal_order, detection_multiplier)
    worst_response = max(payoffs, key=payoffs.get)
    empirical_worst = max(empirical, key=empirical.get)
    return StackelbergSolution(
        weights=weights,
        value=float(result.x[-1]),
        attacker_payoffs=payoffs,
        worst_response=worst_response,
        empirical_payoffs=empirical,
        empirical_worst_response=empirical_worst,
        success=True,
        message=str(result.message),
    )


def plot_equilibrium(solution: StackelbergSolution, output_path: str | Path) -> Path:
    """Write the Figure 7 equilibrium comparison plot."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    labels = list(SIGNAL_ORDER)
    empirical_values = [EMPIRICAL_WEIGHTS[name] for name in labels]
    optimal_values = [solution.weights[name] for name in labels]
    attack_names = list(solution.attacker_payoffs.keys())
    empirical_payoff_values = [solution.empirical_payoffs[name] for name in attack_names]
    optimal_payoff_values = [solution.attacker_payoffs[name] for name in attack_names]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={"width_ratios": [1.0, 1.35]})
    x = np.arange(len(labels))
    width = 0.36
    axes[0].bar(x - width / 2, empirical_values, width, label="Empirical", color="#4C72B0")
    axes[0].bar(x + width / 2, optimal_values, width, label="Stackelberg", color="#55A868")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=30, ha="right")
    axes[0].set_ylim(0.0, 0.65)
    axes[0].set_ylabel("Weight mass")
    axes[0].set_title("Defender weight vector")
    axes[0].legend(framealpha=0.9)
    axes[0].grid(axis="y", linestyle="--", alpha=0.4)

    y = np.arange(len(attack_names))
    axes[1].barh(y - width / 2, empirical_payoff_values, width, label="Empirical", color="#DD8452")
    axes[1].barh(y + width / 2, optimal_payoff_values, width, label="Stackelberg", color="#8172B2")
    axes[1].set_yticks(y)
    axes[1].set_yticklabels([name.replace("_", "\n") for name in attack_names])
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Attacker residual payoff (lower is better)")
    axes[1].set_title("Follower best-response payoff")
    axes[1].legend(framealpha=0.9)
    axes[1].grid(axis="x", linestyle="--", alpha=0.4)

    fig.suptitle("Figure 7 - Stackelberg equilibrium for RAASA risk weights", fontweight="bold")
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output


def write_solution_json(solution: StackelbergSolution, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(solution.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Solve the RAASA Stackelberg risk-weight game.")
    parser.add_argument(
        "--out",
        default="paper/04_figures/fig7_stackelberg_equilibrium.png",
        help="Output PNG path for the equilibrium figure.",
    )
    parser.add_argument(
        "--json-out",
        default="paper/03_results_data/stackelberg_equilibrium.json",
        help="Output JSON path for the solved equilibrium.",
    )
    parser.add_argument("--min-weight", type=float, default=0.05)
    parser.add_argument("--max-weight", type=float, default=0.55)
    args = parser.parse_args()

    solution = solve_stackelberg_game(min_weight=args.min_weight, max_weight=args.max_weight)
    figure = plot_equilibrium(solution, args.out)
    summary = write_solution_json(solution, args.json_out)
    print(json.dumps(solution.to_dict(), indent=2, sort_keys=True))
    print(f"[RAASA] Wrote figure: {figure}")
    print(f"[RAASA] Wrote summary: {summary}")


if __name__ == "__main__":
    _cli()
