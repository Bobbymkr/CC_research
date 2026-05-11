Phase 1D reconstructed summary

- Source run: `phase1d_resolution_validation_2026_05_09_101914`
- Note: the wrapper command timed out during wrap-up, but the rollout, enforcement, diagnostics, and measurement files were fully written.

Control-path outcome

- All enforcement sends returned `OK`.
- Demo server and demo client were set to `L2` and later restored to `L1`.
- Benchmark client was set to `L1`, then `L3`, then restored to `L1`.
- Enforcer evidence is in `enforcer_logs_final.txt`.

Traffic outcome

- `L1` service DNS resolved successfully.
- Under `L3`, service-name DNS timed out and all benchmark targets dropped to `0` throughput, which is consistent with `netem loss 100%`.

Average measurements

- `L1` service host: `0.040889s`, `599625512 B/s`
- `L3` service host: `4.855469s`, `0 B/s`
- `L1` service IP: `0.004732s`, `945457526 B/s`
- `L3` service IP: `3.108663s`, `0 B/s`
- `L1` pod IP: `0.003150s`, `1453248796 B/s`
- `L3` pod IP: `6.810141s`, `0 B/s`

Ratios

- Service host time ratio `L3/L1`: `118.75x`
- Service IP time ratio `L3/L1`: `656.99x`
- Pod IP time ratio `L3/L1`: `2162.18x`

Interpretation

- The Phase 1D canary succeeded functionally: the enforcement path applied and restored the intended controls, and the benchmark path showed the expected severe degradation under `L3`.
