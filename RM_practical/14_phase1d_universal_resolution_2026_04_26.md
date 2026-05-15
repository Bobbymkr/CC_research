## Phase 1D Summary

Phase 1D closes the remaining interface-resolution gap from Phase 1C.

The final live AWS result is not just "the benchmark still works." It shows that the previously stubborn demo server pod now resolves cleanly to a real host-side veth, alongside the demo client and benchmark client, with no fallback lines in the canonical summary.

Canonical artifacts:

- `results/aws_v2_2026_04_26/phase1d2_deploy_2026_04_26/`
- `results/aws_v2_2026_04_26/phase1d2_resolution_validation_2026_04_26/`

What changed technically:

- the old resolver depended on `nsenter -n -m sh -lc ...`, which breaks on images that do not contain `sh`,
- the final resolver reads `ip -o link show` inside the target network namespace and parses peer indices from entries like `eth0@if6`,
- those peer indices are then mapped back to host veth names through host `ifindex` values.

That made the live AWS result much cleaner:

- `raasa-net-server -> veth3018bd1d`
- `raasa-net-client -> vethb9f7d033`
- `raasa-bench-client -> veth04a1b488`
- `fallback_lines = []`

The benchmark path also held up after the fix:

- `L1` average transfer time: `0.014134 s`
- `L3` average transfer time: `123.051984 s`
- `L3` average throughput: `0 B/s`

So the paper claim can now move from:

- benchmark-specific pod containment

to:

- pod-specific host-veth enforcement across the tested live AWS demo and benchmark workloads

One honest nuance still matters:

`L3` still behaves like hard containment with connection resets, not graceful `1mbit` shaping. That is still a strong security result, but it should be described that way in the paper.
