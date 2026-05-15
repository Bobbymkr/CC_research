"""
RAASA Paper Figure Generator
Uses real experiment summary JSONs to produce all publication figures.
Run from project root: python generate_paper_figures.py
"""
from __future__ import annotations
import json, statistics, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

try:
    import seaborn as sns
    sns.set_theme(style="whitegrid", font="DejaVu Sans", font_scale=1.15)
    HAS_SNS = True
except ImportError:
    HAS_SNS = False
    plt.style.use("seaborn-v0_8-whitegrid")

ROOT = Path(__file__).parent
RESULTS = ROOT / "RM_practical" / "results" / "aws_v2"
OUTDIR  = ROOT / "RM_practical" / "figures"
OUTDIR.mkdir(parents=True, exist_ok=True)

DPI    = 180
COLORS = {
    "RAASA (Adaptive)": "#4C72B0",
    "Static L1":        "#DD8452",
    "Static L3":        "#C44E52",
    "RAASA (ML)":       "#8172B2",
    "RAASA (Large)":    "#55A868",
}

# ── helpers ──────────────────────────────────────────────────────────────────

def load(p: str | Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))

def mean_summaries(*paths) -> dict:
    data = [load(RESULTS / p) for p in paths]
    out: dict = {}
    for k in data[0]:
        vals = [d[k] for d in data if isinstance(d.get(k), (int, float))]
        if vals:
            out[k] = statistics.mean(vals)
        elif k == "tier_occupancy":
            merged: dict[str, list] = {}
            for d in data:
                for t, v in d.get(k, {}).items():
                    merged.setdefault(t, []).append(v)
            raw = {t: statistics.mean(vs) for t, vs in merged.items()}
            total = sum(raw.values()) or 1.0
            out[k] = {t: v / total for t, v in raw.items()}  # normalize to sum=1
        else:
            out[k] = data[0].get(k)
    return out

def annotate_bars(ax, bars, fmt=".2f"):
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.015,
                f"{h:{fmt}}", ha="center", va="bottom",
                fontsize=8.5, color="#333333", fontweight="bold")

def save(fig, name):
    p = OUTDIR / name
    fig.tight_layout()
    fig.savefig(p, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK]  {p.name}")
    return p

# -- assemble mode metrics -----------------------------------------------------

metrics = {
    "Static L1": load("RM_practical/run_L1.summary.json"),
    "Static L3": load("RM_practical/run_L3.summary.json"),
    "RAASA (Adaptive)": mean_summaries(
        "run_small_tuned_raasa_linear_r1.summary.json",
        "run_small_tuned_raasa_linear_r2.summary.json",
        "run_small_tuned_raasa_linear_r3.summary.json",
    ),
    "RAASA (ML)": mean_summaries(
        "run_small_tuned_raasa_ml_r1.summary.json",
        "run_small_tuned_raasa_ml_r2.summary.json",
        "run_small_tuned_raasa_ml_r3.summary.json",
    ),
}

aws_metrics = load("RM_practical/run_aws_k8s_ebpf_r3.summary.json")
large_metrics = load("RM_practical/results/aws_v2/run_large_raasa_linear_r1.summary.json")

# ── Figure 1: Detection (Precision / Recall / FPR) ──────────────────────────

def fig1_detection():
    modes  = ["Static L1", "Static L3", "RAASA (Adaptive)", "RAASA (ML)"]
    labels = ["Static\nL1", "Static\nL3", "RAASA\n(Adaptive)", "RAASA\n(ML)"]
    prec   = [metrics[m].get("precision", 0) for m in modes]
    rec    = [metrics[m].get("recall",    0) for m in modes]
    fpr    = [metrics[m].get("false_positive_rate", 0) for m in modes]

    x = np.arange(len(modes)); w = 0.24
    fig, ax = plt.subplots(figsize=(9, 5.5))
    b1 = ax.bar(x - w, prec, w, label="Precision",          color="#4C72B0", edgecolor="white", linewidth=0.8, alpha=0.92)
    b2 = ax.bar(x,     rec,  w, label="Recall",             color="#55A868", edgecolor="white", linewidth=0.8, alpha=0.92)
    b3 = ax.bar(x + w, fpr,  w, label="False Positive Rate",color="#C44E52", edgecolor="white", linewidth=0.8, alpha=0.92)
    for bars in (b1, b2, b3):
        annotate_bars(ax, bars)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(0, 1.18); ax.set_ylabel("Score [0–1]", fontsize=11)
    ax.set_title("Figure 1 — Security Detection Comparison\n(Precision · Recall · False Positive Rate)",
                 fontsize=12, fontweight="bold", pad=10)
    ax.legend(fontsize=9, framealpha=0.88)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    if HAS_SNS: sns.despine(ax=ax)
    return save(fig, "fig1_detection_comparison.png")


# ── Figure 2: Cost (Containment Pressure + Benign Restriction Rate) ──────────

def fig2_cost():
    modes  = ["Static L1", "Static L3", "RAASA (Adaptive)", "RAASA (ML)"]
    labels = ["Static\nL1", "Static\nL3", "RAASA\n(Adaptive)", "RAASA\n(ML)"]
    cp  = [metrics[m].get("containment_pressure",   0) for m in modes]
    brr = [metrics[m].get("benign_restriction_rate", 0) for m in modes]
    ue  = [metrics[m].get("unnecessary_escalations", 0) / max(metrics[m].get("unnecessary_escalations",1),1)
           for m in modes]

    x = np.arange(len(modes)); w = 0.26
    fig, ax = plt.subplots(figsize=(9, 5.5))
    b1 = ax.bar(x - w, cp,  w, label="Containment Pressure",   color="#DD8452", edgecolor="white", linewidth=0.8, alpha=0.92)
    b2 = ax.bar(x,     brr, w, label="Benign Restriction Rate", color="#C44E52", edgecolor="white", linewidth=0.8, alpha=0.92)
    for bars in (b1, b2):
        annotate_bars(ax, bars)
    # Overlay unnecessary escalations as text
    unesc_raw = [metrics[m].get("unnecessary_escalations", 0) for m in modes]
    for i, v in enumerate(unesc_raw):
        ax.text(x[i] + w, 0.05, f"{int(v)} escalations",
                ha="center", va="bottom", fontsize=8, color="#555555", rotation=90)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(0, 1.18); ax.set_ylabel("Rate [0–1]", fontsize=11)
    ax.set_title("Figure 2 — Isolation Cost Comparison\n(Containment Pressure · Benign Restriction Rate · Unnecessary Escalations)",
                 fontsize=12, fontweight="bold", pad=10)
    ax.legend(fontsize=9, framealpha=0.88)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    if HAS_SNS: sns.despine(ax=ax)
    return save(fig, "fig2_cost_comparison.png")


# ── Figure 3: Tier Occupancy (Stacked) ───────────────────────────────────────

def fig3_tier_occupancy():
    all_modes = {
        "Static L1":        metrics["Static L1"],
        "Static L3":        metrics["Static L3"],
        "RAASA\n(Adaptive)": metrics["RAASA (Adaptive)"],
        "RAASA\n(ML)":       metrics["RAASA (ML)"],
        "RAASA\n(AWS/K8s)":  aws_metrics,
        "RAASA\n(Large-20)": large_metrics,
    }
    labels = list(all_modes.keys())
    l1 = [d.get("tier_occupancy", {}).get("L1", 0.0) for d in all_modes.values()]
    l2 = [d.get("tier_occupancy", {}).get("L2", 0.0) for d in all_modes.values()]
    l3 = [d.get("tier_occupancy", {}).get("L3", 0.0) for d in all_modes.values()]

    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(10, 5.5))
    b1 = ax.bar(x, l1, label="L1 (Minimal)",   color="#55A868", edgecolor="white", linewidth=0.8)
    b2 = ax.bar(x, l2, bottom=l1, label="L2 (Moderate)", color="#DD8452", edgecolor="white", linewidth=0.8)
    b3 = ax.bar(x, l3, bottom=[a+b for a,b in zip(l1,l2)], label="L3 (Strict)", color="#C44E52", edgecolor="white", linewidth=0.8)

    # Annotate totals
    for i in range(len(labels)):
        total = l1[i]+l2[i]+l3[i]
        if total > 0:
            ax.text(x[i], total+0.01, f"{total:.0%}", ha="center", va="bottom", fontsize=8, color="#333")

    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 1.15); ax.set_ylabel("Fraction of ticks in tier", fontsize=11)
    ax.set_title("Figure 3 — Isolation Tier Occupancy (All Scenarios)\n(Local Docker · AWS K8s · 20-Container Scale)",
                 fontsize=12, fontweight="bold", pad=10)
    ax.legend(fontsize=9, framealpha=0.88)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    if HAS_SNS: sns.despine(ax=ax)
    return save(fig, "fig3_tier_occupancy.png")


# ── Figure 4: Scale (Small / Medium / Large RAASA precision & recall) ─────────

def fig4_scale():
    med_r = load("RM_practical/results/aws_v2/run_medium_raasa_linear_r1.summary.json")
    sc_labels = ["Small (3 ctr)", "Medium (10 ctr)", "Large (20 ctr)"]
    raasa_p = [
        metrics["RAASA (Adaptive)"].get("precision", 0),
        med_r.get("precision", 0),
        large_metrics.get("precision", 0),
    ]
    raasa_r = [
        metrics["RAASA (Adaptive)"].get("recall", 0),
        med_r.get("recall", 0),
        large_metrics.get("recall", 0),
    ]
    brr = [
        metrics["RAASA (Adaptive)"].get("benign_restriction_rate", 0),
        med_r.get("benign_restriction_rate", 0),
        large_metrics.get("benign_restriction_rate", 0),
    ]

    x = np.arange(len(sc_labels)); w = 0.25
    fig, ax = plt.subplots(figsize=(9, 5.5))
    b1 = ax.bar(x - w, raasa_p, w, label="Precision",            color="#4C72B0", edgecolor="white", alpha=0.92)
    b2 = ax.bar(x,     raasa_r, w, label="Recall",               color="#55A868", edgecolor="white", alpha=0.92)
    b3 = ax.bar(x + w, brr,     w, label="Benign Restriction Rate", color="#C44E52", edgecolor="white", alpha=0.92)
    for bars in (b1, b2, b3):
        annotate_bars(ax, bars)
    ax.set_xticks(x); ax.set_xticklabels(sc_labels, fontsize=10)
    ax.set_ylim(0, 1.18); ax.set_ylabel("Score [0–1]", fontsize=11)
    ax.set_title("Figure 4 — RAASA Scalability (Linear Controller)\n(Small · Medium · Large Workload Scenarios)",
                 fontsize=12, fontweight="bold", pad=10)
    ax.legend(fontsize=9, framealpha=0.88)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    if HAS_SNS: sns.despine(ax=ax)
    return save(fig, "fig4_scalability.png")


# ── Figure 5: Tier Trajectory from real JSONL ─────────────────────────────────

def fig5_trajectory():
    """Plot live tier transitions from the small_tuned_raasa_r1 run."""
    from datetime import datetime
    from collections import defaultdict

    jsonl_path = RESULTS / "run_small_tuned_raasa_linear_r1.jsonl"
    if not jsonl_path.exists():
        print(f"  [SKIP] {jsonl_path.name} not found, skipping trajectory plot")
        return

    records = [json.loads(l) for l in jsonl_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    TIER_Y = {"L1": 1, "L2": 2, "L3": 3}
    grouped: defaultdict[str, list] = defaultdict(list)
    for row in records:
        grouped[row["container_id"]].append(row)

    t0 = min(datetime.fromisoformat(r["timestamp"]) for r in records)
    fig, ax = plt.subplots(figsize=(10, 5))

    style_map = {"malicious": ("red",   2.5, "--"),
                 "benign":    ("#4C72B0", 1.8, "-"),
                 "suspicious":("#DD8452", 1.8, ":")}

    for cid, rows in sorted(grouped.items()):
        rows = sorted(rows, key=lambda r: r["timestamp"])
        xs = [(datetime.fromisoformat(r["timestamp"]) - t0).total_seconds() for r in rows]
        ys = [TIER_Y.get(str(r.get("new_tier") or "L1"), 1) for r in rows]
        meta = rows[-1].get("metadata", {})
        wclass = str(meta.get("workload_class", "benign")).lower()
        wkey   = meta.get("workload_key", cid[-6:])
        color, lw, ls = style_map.get(wclass, ("#888888", 1.5, "-"))
        ax.step(xs, ys, where="post", color=color, lw=lw, ls=ls,
                label=f"{wkey} ({wclass})", alpha=0.88)

    ax.set_yticks([1, 2, 3]); ax.set_yticklabels(["L1\n(Open)", "L2\n(Moderate)", "L3\n(Strict)"], fontsize=10)
    ax.set_xlabel("Time since experiment start (seconds)", fontsize=11)
    ax.set_ylabel("Isolation Tier", fontsize=11)
    ax.set_title("Figure 5 — Live Tier Trajectory (RAASA Adaptive, small_tuned scenario)\n"
                 "Malicious workloads escalate to L3 · Benign workloads remain at L1",
                 fontsize=12, fontweight="bold", pad=10)
    ax.legend(fontsize=8, framealpha=0.88, loc="upper left", ncol=2)
    ax.grid(axis="both", linestyle="--", alpha=0.4)
    if HAS_SNS: sns.despine(ax=ax)
    return save(fig, "fig5_tier_trajectory.png")


# ── Figure 6: Linear vs ML ablation ──────────────────────────────────────────

def fig6_ablation():
    lin_mean = mean_summaries(
        "run_small_tuned_raasa_linear_r1.summary.json",
        "run_small_tuned_raasa_linear_r2.summary.json",
        "run_small_tuned_raasa_linear_r3.summary.json",
    )
    ml_mean = mean_summaries(
        "run_small_tuned_raasa_ml_r1.summary.json",
        "run_small_tuned_raasa_ml_r2.summary.json",
        "run_small_tuned_raasa_ml_r3.summary.json",
    )

    cats   = ["Precision", "Recall", "FPR", "Benign\nRestriction"]
    lin_v  = [lin_mean.get("precision",0), lin_mean.get("recall",0),
               lin_mean.get("false_positive_rate",0), lin_mean.get("benign_restriction_rate",0)]
    ml_v   = [ml_mean.get("precision",0),  ml_mean.get("recall",0),
               ml_mean.get("false_positive_rate",0),  ml_mean.get("benign_restriction_rate",0)]

    x = np.arange(len(cats)); w = 0.32
    fig, ax = plt.subplots(figsize=(9, 5.5))
    b1 = ax.bar(x - w/2, lin_v, w, label="Linear (Tuned)",     color="#4C72B0", edgecolor="white", alpha=0.92)
    b2 = ax.bar(x + w/2, ml_v,  w, label="ML (Isolation Forest)", color="#8172B2", edgecolor="white", alpha=0.92)
    for bars in (b1, b2):
        annotate_bars(ax, bars)
    ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=10)
    ax.set_ylim(0, 1.18); ax.set_ylabel("Score [0–1]", fontsize=11)
    ax.set_title("Figure 6 — Ablation Study: Linear vs. Isolation Forest Risk Model\n(3-Run Mean · small_tuned scenario)",
                 fontsize=12, fontweight="bold", pad=10)
    ax.legend(fontsize=9, framealpha=0.88)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    if HAS_SNS: sns.despine(ax=ax)
    return save(fig, "fig6_ablation_linear_vs_ml.png")


# ── Run all ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\nGenerating RAASA paper figures -> {OUTDIR}\n")
    generated = []
    for fn in [fig1_detection, fig2_cost, fig3_tier_occupancy, fig4_scale, fig5_trajectory, fig6_ablation]:
        try:
            p = fn()
            if p:
                generated.append(p)
        except Exception as e:
            print(f"  [ERR] {fn.__name__}: {e}")

    print(f"\nDone - {len(generated)} figure(s) written to {str(OUTDIR)}/\n")
