from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class TableSpec:
    name: str
    title: str
    latex_caption: str
    latex_label: str
    columns: list[str]
    rows: list[dict[str, str]]
    notes: list[str]
    latex_environment: str = "table"
    latex_tabular_environment: str = "tabular"
    latex_column_spec: str = ""
    latex_width: str | None = None
    latex_font_size: str = r"\footnotesize"
    latex_tabcolsep_pt: float | None = None
    latex_arraystretch: float | None = 1.08


def _latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    escaped = value
    for source, target in replacements.items():
        escaped = escaped.replace(source, target)
    return escaped


def render_markdown(spec: TableSpec) -> str:
    lines = [f"# {spec.title}", ""]
    header = "| " + " | ".join(spec.columns) + " |"
    separator = "| " + " | ".join("---" for _ in spec.columns) + " |"
    lines.extend([header, separator])
    for row in spec.rows:
        lines.append("| " + " | ".join(row[column] for column in spec.columns) + " |")
    if spec.notes:
        lines.extend(["", "## Notes", ""])
        for note in spec.notes:
            lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def render_csv(spec: TableSpec, output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=spec.columns)
        writer.writeheader()
        writer.writerows(spec.rows)


def _default_column_spec(column_count: int) -> str:
    return " ".join("l" for _ in range(column_count))


def render_latex(spec: TableSpec) -> str:
    column_spec = spec.latex_column_spec or _default_column_spec(len(spec.columns))
    table_env = spec.latex_environment
    tabular_env = spec.latex_tabular_environment
    width = spec.latex_width or (r"\columnwidth" if table_env == "table" else r"\textwidth")

    lines = [
        f"% IEEE include snippet for {spec.title}",
        r"% Requires in preamble: \usepackage{booktabs,tabularx,array}",
        f"\\begin{{{table_env}}}[t]",
        r"\centering",
        spec.latex_font_size,
    ]

    if spec.latex_tabcolsep_pt is not None:
        lines.append(f"\\setlength{{\\tabcolsep}}{{{spec.latex_tabcolsep_pt:.1f}pt}}")
    if spec.latex_arraystretch is not None:
        lines.append(f"\\renewcommand{{\\arraystretch}}{{{spec.latex_arraystretch:.2f}}}")

    lines.extend(
        [
            f"\\caption{{{_latex_escape(spec.latex_caption)}}}",
            f"\\label{{{spec.latex_label}}}",
        ]
    )

    if tabular_env == "tabularx":
        lines.append(f"\\begin{{tabularx}}{{{width}}}{{{column_spec}}}")
    else:
        lines.append(f"\\begin{{tabular}}{{{column_spec}}}")

    lines.append(r"\toprule")
    lines.append(" & ".join(_latex_escape(column) for column in spec.columns) + r" \\")
    lines.append(r"\midrule")

    for row in spec.rows:
        lines.append(
            " & ".join(_latex_escape(row[column]) for column in spec.columns) + r" \\"
        )

    lines.extend(
        [
            r"\bottomrule",
            f"\\end{{{tabular_env}}}",
            f"\\end{{{table_env}}}",
            "",
        ]
    )

    if spec.notes:
        lines.append("% Notes")
        for note in spec.notes:
            lines.append(f"% - {_latex_escape(note)}")
        lines.append("")

    return "\n".join(lines)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_tables() -> Iterable[TableSpec]:
    yield TableSpec(
        name="local_baseline_comparison",
        title="Table A. Local Baseline Comparison",
        latex_caption="Local baseline comparison.",
        latex_label="tab:local-baseline-comparison",
        columns=[
            "Mode",
            "Environment",
            "Scenario",
            "Precision",
            "Recall",
            "FPR",
            "BRR",
            "UE",
        ],
        rows=[
            {
                "Mode": "static_L1",
                "Environment": "Local Docker",
                "Scenario": "small baseline",
                "Precision": "0.00",
                "Recall": "0.00",
                "FPR": "0.00",
                "BRR": "0.00",
                "UE": "0",
            },
            {
                "Mode": "static_L3",
                "Environment": "Local Docker",
                "Scenario": "small baseline",
                "Precision": "0.33",
                "Recall": "1.00",
                "FPR": "1.00",
                "BRR": "1.00",
                "UE": "24",
            },
            {
                "Mode": "raasa linear",
                "Environment": "Local Docker",
                "Scenario": "small_tuned best run",
                "Precision": "1.00",
                "Recall": "1.00",
                "FPR": "0.00",
                "BRR": "0.00",
                "UE": "0",
            },
            {
                "Mode": "raasa linear",
                "Environment": "Local Docker",
                "Scenario": "small_tuned 3-run mean",
                "Precision": "0.87",
                "Recall": "1.00",
                "FPR": "0.11",
                "BRR": "0.11",
                "UE": "1.3",
            },
        ],
        notes=[
            "Values are taken from the current paper draft and local evaluation materials.",
            "FPR = false positive rate, BRR = benign restriction rate, UE = unnecessary escalations.",
        ],
        latex_environment="table",
        latex_tabular_environment="tabular",
        latex_column_spec="l l l c c c c c",
        latex_font_size=r"\footnotesize",
        latex_tabcolsep_pt=4.0,
        latex_arraystretch=1.06,
    )

    yield TableSpec(
        name="cloud_evidence_ladder",
        title="Table B. Cloud Evidence Ladder",
        latex_caption="Cloud evidence ladder from early single-node K3s validation to bounded fresh-account multi-node K3s validation.",
        latex_label="tab:cloud-evidence-ladder",
        columns=[
            "Date",
            "Environment shape",
            "Test / workload",
            "Result",
            "Claim supported",
            "Key limitation",
            "Evidence bundle",
        ],
        rows=[
            {
                "Date": "2026-04-26",
                "Environment shape": "Single-node K3s",
                "Test / workload": "Phase 1D universal resolution validation",
                "Result": "Resolved raasa-net-server, raasa-net-client, and raasa-bench-client to host-veths; benchmark L1 about 0.014 s, L3 about 123.05 s and 0 B/s",
                "Claim supported": "Pod-specific containment works in live K3s rather than only in local Docker",
                "Key limitation": "Single-node only",
                "Evidence bundle": "AWS_Results_26_april/phase1d2_resolution_validation_2026_04_26",
            },
            {
                "Date": "2026-04-26",
                "Environment shape": "Single-node K3s",
                "Test / workload": "Phase 1F refined semantics",
                "Result": "Under L3, DNS lookups, ClusterIP traffic, and direct pod-IP traffic all fail with 0 B/s",
                "Claim supported": "L3 should be described as hard containment, not merely bandwidth shaping",
                "Key limitation": "Single-node only",
                "Evidence bundle": "AWS_Results_26_april/phase1f_resolution_validation_2026_04_26",
            },
            {
                "Date": "2026-05-14",
                "Environment shape": "Fresh-account single-node K3s",
                "Test / workload": "Clean-account replay and bounded soak",
                "Result": "Fresh AWS Free-plan account bootstrapped successfully; stable replay soak passed 2 / 2",
                "Claim supported": "Cloud evidence is reproducible from a clean account state",
                "Key limitation": "Single-node replay only",
                "Evidence bundle": "AWS_Results_26_april/live_instance_validation_2026_05_14_111436 and closed_loop_soak_2026_05_14_112413",
            },
            {
                "Date": "2026-05-14",
                "Environment shape": "Bounded 3-node K3s",
                "Test / workload": "Closed-loop soak plus repeated five-workload adversarial matrix",
                "Result": "Soak passed 3 / 3; repeated matrix passed 2 / 2 runs with benign total L3 count 0",
                "Claim supported": "The cloud path remains coherent beyond single-node replay in a bounded multi-node setting",
                "Key limitation": "Short, bounded run counts",
                "Evidence bundle": "AWS_Results_26_april/closed_loop_soak_2026_05_14_142154 and adversarial_matrix_repeated_2026_05_14_143056",
            },
            {
                "Date": "2026-05-14",
                "Environment shape": "Bounded 3-node K3s",
                "Test / workload": "Failure injection, Metrics API stress, and worker drain/reschedule",
                "Result": "Fake-pod IPC returned ERR; degraded telemetry stayed explicit; 62 complete stress rows with total_failures=0; benign pod rescheduled after drain",
                "Claim supported": "Bounded degraded-mode handling and multi-node continuity are observable and auditable",
                "Key limitation": "Not EKS, not multi-tenant, not HA evidence",
                "Evidence bundle": "AWS_Results_26_april/failure_injection_2026_05_14_145348, metrics_api_stress_probe_2026_05_14_145915, and multinode_reschedule_validation_2026_05_14_151103",
            },
        ],
        notes=[
            "This is the main cloud-evidence ladder for the paper.",
            "It intentionally stops at bounded 3-node K3s and does not imply EKS robustness.",
        ],
        latex_environment="table*",
        latex_tabular_environment="tabularx",
        latex_column_spec=(
            r"p{0.08\textwidth} "
            r"p{0.12\textwidth} "
            r">{\raggedright\arraybackslash}X "
            r">{\raggedright\arraybackslash}X "
            r"p{0.13\textwidth} "
            r"p{0.12\textwidth} "
            r"p{0.16\textwidth}"
        ),
        latex_width=r"\textwidth",
        latex_font_size=r"\scriptsize",
        latex_tabcolsep_pt=3.0,
        latex_arraystretch=1.10,
    )

    yield TableSpec(
        name="failure_degraded_mode_summary",
        title="Table C. Failure and Degraded-Mode Summary",
        latex_caption="Bounded degraded-mode and fail-closed behavior in the fresh-account 3-node K3s campaign.",
        latex_label="tab:failure-degraded-mode-summary",
        columns=[
            "Injected condition",
            "Observed status",
            "Containment outcome",
            "Interpretation",
            "Evidence bundle",
        ],
        rows=[
            {
                "Injected condition": "Metrics API outage",
                "Observed status": "10 audit rows; telemetry complete:1, partial:9; metrics_ok:1, metrics_error:9; memory metrics_ok:1, cadvisor_fallback:9",
                "Containment outcome": "New tiers L3:10",
                "Interpretation": "The controller exposes degraded telemetry instead of silently masking the outage",
                "Evidence bundle": "AWS_Results_26_april/failure_injection_2026_05_14_145348",
            },
            {
                "Injected condition": "Syscall probe pause",
                "Observed status": "11 audit rows; telemetry complete:4, partial:7; probe_ok:4, probe_stale:7",
                "Containment outcome": "New tiers L3:11",
                "Interpretation": "Probe degradation is explicitly surfaced rather than hidden behind a false clean reading",
                "Evidence bundle": "AWS_Results_26_april/failure_injection_2026_05_14_145348",
            },
            {
                "Injected condition": "Fake-pod IPC fail-closed check",
                "Observed status": "IPC response ERR",
                "Containment outcome": "Rejected as expected",
                "Interpretation": "The privileged path fails closed for an invalid target",
                "Evidence bundle": "AWS_Results_26_april/failure_injection_2026_05_14_145348",
            },
            {
                "Injected condition": "Agent restart recovery",
                "Observed status": "Agent changed from raasa-agent-9st2t to raasa-agent-2qgvr",
                "Containment outcome": "Recovery observed after restart",
                "Interpretation": "The bounded experiment shows post-restart continuity, not high-availability",
                "Evidence bundle": "AWS_Results_26_april/failure_injection_2026_05_14_145348",
            },
            {
                "Injected condition": "Metrics API bounded stress",
                "Observed status": "30 s, 6 workers, 62 audit rows, telemetry complete:62, metrics_ok:62, total_failures=0",
                "Containment outcome": "Controller held risk within current tier band for all captured rows",
                "Interpretation": "Bounded stress remained interpretable without forcing a collapse in the cloud path",
                "Evidence bundle": "AWS_Results_26_april/metrics_api_stress_probe_2026_05_14_145915",
            },
        ],
        notes=[
            "This table is especially useful in discussion/limitations or an appendix.",
            "Its purpose is to show that degraded behavior is explicit rather than silently hidden.",
        ],
        latex_environment="table*",
        latex_tabular_environment="tabularx",
        latex_column_spec=(
            r"p{0.16\textwidth} "
            r">{\raggedright\arraybackslash}X "
            r"p{0.12\textwidth} "
            r">{\raggedright\arraybackslash}X "
            r"p{0.18\textwidth}"
        ),
        latex_width=r"\textwidth",
        latex_font_size=r"\scriptsize",
        latex_tabcolsep_pt=3.2,
        latex_arraystretch=1.10,
    )

    yield TableSpec(
        name="scope_nonclaims",
        title="Table D. Scope and Non-Claims",
        latex_caption="Explicit scope boundary for the current RAASA evidence package.",
        latex_label="tab:scope-nonclaims",
        columns=[
            "Claim area",
            "Supported?",
            "Evidence basis",
            "Note",
        ],
        rows=[
            {
                "Claim area": "Adaptive vs static local trade-off",
                "Supported?": "Yes",
                "Evidence basis": "Local Docker baseline comparison",
                "Note": "Core thesis anchor",
            },
            {
                "Claim area": "Fresh-account cloud reproducibility",
                "Supported?": "Yes",
                "Evidence basis": "Single-node replay on a clean AWS Free-plan account",
                "Note": "Bounded replay only",
            },
            {
                "Claim area": "Bounded multi-node K3s continuity",
                "Supported?": "Yes",
                "Evidence basis": "3-node soak, repeated matrix, degraded-mode handling, and drain/reschedule",
                "Note": "K3s only; bounded envelope",
            },
            {
                "Claim area": "Managed Kubernetes / EKS robustness",
                "Supported?": "No",
                "Evidence basis": "No EKS evidence bundle exists",
                "Note": "Must remain a non-claim",
            },
            {
                "Claim area": "Multi-tenant safety",
                "Supported?": "No",
                "Evidence basis": "No multi-tenant evaluation exists",
                "Note": "Must remain a non-claim",
            },
            {
                "Claim area": "Production readiness",
                "Supported?": "No",
                "Evidence basis": "Bounded research-prototype evidence only",
                "Note": "Explicitly avoid this claim",
            },
            {
                "Claim area": "Broad exfiltration-prevention guarantee",
                "Supported?": "No",
                "Evidence basis": "Only bounded adversarial matrix coverage exists",
                "Note": "Specific workloads only",
            },
            {
                "Claim area": "High availability / fault tolerance",
                "Supported?": "No",
                "Evidence basis": "Drain/reschedule continuity exists, but no HA or SLA evidence",
                "Note": "Do not overread the worker-drain result",
            },
        ],
        notes=[
            "This table is helpful in an appendix, rebuttal package, or artifact companion.",
            "It prevents readers from inferring claims larger than the evidence base.",
        ],
        latex_environment="table",
        latex_tabular_environment="tabularx",
        latex_column_spec=(
            r"p{0.22\columnwidth} "
            r"c "
            r">{\raggedright\arraybackslash}X "
            r"p{0.21\columnwidth}"
        ),
        latex_width=r"\columnwidth",
        latex_font_size=r"\footnotesize",
        latex_tabcolsep_pt=3.4,
        latex_arraystretch=1.08,
    )


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    output_dir = base_dir / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    for spec in build_tables():
        write_text(output_dir / f"{spec.name}.md", render_markdown(spec))
        render_csv(spec, output_dir / f"{spec.name}.csv")
        write_text(output_dir / f"{spec.name}.tex", render_latex(spec))

    print(f"Rendered paper tables into: {output_dir}")


if __name__ == "__main__":
    main()
