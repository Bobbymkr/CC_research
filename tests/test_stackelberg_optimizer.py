from pathlib import Path
import tempfile
import unittest

from raasa.analysis.stackelberg_optimizer import (
    SIGNAL_ORDER,
    default_attack_profiles,
    plot_equilibrium,
    solve_stackelberg_game,
)


class StackelbergOptimizerTests(unittest.TestCase):
    def test_solution_weights_are_valid_simplex(self) -> None:
        solution = solve_stackelberg_game()

        self.assertTrue(solution.success)
        self.assertAlmostEqual(solution.weight_sum, 1.0, places=8)
        self.assertEqual(set(solution.weights), set(SIGNAL_ORDER))
        self.assertTrue(all(0.05 <= value <= 0.55 for value in solution.weights.values()))
        self.assertIn(solution.worst_response, solution.attacker_payoffs)

    def test_solution_reduces_worst_case_payoff(self) -> None:
        solution = solve_stackelberg_game(default_attack_profiles())

        self.assertLessEqual(solution.value, solution.empirical_value + 1e-8)
        self.assertGreaterEqual(solution.payoff_reduction, -1e-8)

    def test_plot_equilibrium_writes_png(self) -> None:
        solution = solve_stackelberg_game()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "fig7_stackelberg_equilibrium.png"
            plot_equilibrium(solution, output)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
