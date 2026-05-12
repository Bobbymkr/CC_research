# Manuscript Figure Integration Notes

This file explains how the redesigned figure plan should be referenced inside the manuscript.

## Recommended final figure order

1. Figure 1 - architecture and trust boundary
2. Figure 2 - adaptive vs static baseline comparison
3. Figure 3 - scalability behavior
4. Figure 4 - tier occupancy
5. Figure 5 - tier trajectory
6. Figure 6 - linear vs Isolation Forest ablation

## Section-by-section placement

### Section 5 - Framework / architecture

Use:

- Figure 1

Purpose:

- establish the controller and zero-trust sidecar design before results are discussed

### Section 7 - Results

Use:

- Figure 2 immediately after baseline comparison text
- Figure 3 after the scalability subsection
- Figure 4 when discussing time spent in each tier
- Figure 5 when describing live controller behavior or case-study dynamics

### Section 8 - Ablation

Use:

- Figure 6

Purpose:

- isolate the controller-design-vs-model-choice argument cleanly

## Text alignment rules

- If Figure 2 uses RAASA small-scale mean, the surrounding text must also describe it as repeated-run mean evidence.
- If Figure 3 includes the 20-container point, the text must call it single-run supporting evidence.
- If Figure 6 uses the dumbbell design, the text should emphasize difference direction, not just raw values.

## Phrases to use in the manuscript

For Figure 2:

- "As shown in Figure 2, RAASA improves the security-cost tradeoff rather than merely improving one metric in isolation."

For Figure 3:

- "Figure 3 suggests that the controller's repeated-evidence behavior remains favorable beyond the smallest scenario."

For Figure 4:

- "Figure 4 makes the containment cost distribution explicit by showing how much time the controller spends in each tier."

For Figure 5:

- "Figure 5 illustrates the controller's temporal behavior rather than only its aggregate classification quality."

For Figure 6:

- "Figure 6 shows that, in the present prototype, deterministic alignment with the policy engine is more valuable than model complexity."

## Phrases to avoid

- "Figure 3 proves large-scale generalization" unless you add repeated 20-container runs
- "Figure 6 shows ML is worse in all settings" because the current evidence is scoped
- "Figure 2 demonstrates universal superiority" because the paper-safe framing is evaluated-scenario superiority

## Best final writing sequence

1. finalize Figure 1 wording and caption
2. finalize Figure 2 because it anchors the paper's main claim
3. finalize Figure 6 because it closes the model-choice question
4. integrate Figure 3, 4, and 5 as supporting depth

This ordering keeps the manuscript centered on the strongest, most defensible evidence first.
