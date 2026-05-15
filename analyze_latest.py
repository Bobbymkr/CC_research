"""Quick diagnostic: trace malicious container risk scores from latest JSONL run."""
import glob
import json

logs = sorted(glob.glob("raasa/logs/run_*.jsonl"))
latest = logs[-1]
print(f"Analyzing: {latest}\n")

rows = [json.loads(line) for line in open(latest, encoding="utf-8") if line.strip()]

print(f"{'Type':<12} {'CPU%':>7} {'f_cpu':>7} {'risk':>7} {'conf':>7} {'prev':>4} {'new':>4}  reason")
print("-" * 110)
for r in rows:
    meta = r.get("metadata", {})
    wc = meta.get("workload_class", "?")
    label = "MALICIOUS" if wc == "malicious" else f"benign"
    print(
        f"{label:<12} {r['cpu']:>7.1f} {r['f_cpu']:>7.3f} {r['risk']:>7.4f} "
        f"{r['confidence']:>7.4f} {r['prev_tier']:>4} {r['new_tier']:>4}  {r['reason']}"
    )
