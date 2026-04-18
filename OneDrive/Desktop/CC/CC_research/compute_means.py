"""Compute mean metrics across the 3 latest tuned adaptive runs."""
import glob
import json
from pathlib import Path
from raasa.analysis.metrics import load_records, compute_metrics, write_metrics_summary


def mean(values):
    return sum(values) / len(values) if values else 0.0


# Get the 3 most recent JSONL runs
all_logs = sorted(glob.glob("raasa/logs/run_*.jsonl"))
# Skip the failed/diagnosis runs (runs without summaries from earlier sessions)
# just take the last 3 valid ones
valid = [p for p in all_logs if "bootstrap" not in p]
last3 = valid[-3:]
print("Computing mean over:")
for p in last3:
    print(" ", p)

summaries = []
for log_path in last3:
    summary_path = Path(log_path).with_suffix(".summary.json")
    if not summary_path.exists():
        write_metrics_summary(log_path)
    summaries.append(json.loads(summary_path.read_text()))

keys = ["precision", "recall", "false_positive_rate", "unnecessary_escalations",
        "benign_restriction_rate", "malicious_containment_rate",
        "switching_rate", "explanation_coverage"]

print("\n=== PER-RUN RESULTS ===")
for i, s in enumerate(summaries):
    print(f"\nRun {i+1}:")
    for k in keys:
        print(f"  {k}: {s.get(k, 'N/A'):.4f}" if isinstance(s.get(k), float) else f"  {k}: {s.get(k, 'N/A')}")
    print(f"  tier_occupancy: {s.get('tier_occupancy', {})}")
    print(f"  mean_time_to_safe_containment: {s.get('mean_time_to_safe_containment', 0):.2f}s")

print("\n=== MEAN ACROSS 3 RUNS ===")
for k in keys:
    vals = [s.get(k, 0.0) for s in summaries]
    print(f"  mean_{k}: {mean(vals):.4f}")

print("\n=== ACCEPTANCE CRITERIA CHECK ===")
mean_precision = mean([s.get("precision", 0.0) for s in summaries])
mean_recall = mean([s.get("recall", 0.0) for s in summaries])
mean_fpr = mean([s.get("false_positive_rate", 0.0) for s in summaries])

print(f"  Precision == 1.0: {'✅ PASS' if mean_precision == 1.0 else '❌ FAIL'} ({mean_precision:.4f})")
print(f"  Recall >= 0.85:   {'✅ PASS' if mean_recall >= 0.85 else '❌ FAIL'} ({mean_recall:.4f})")
print(f"  FPR == 0.0:       {'✅ PASS' if mean_fpr == 0.0 else '❌ FAIL'} ({mean_fpr:.4f})")
