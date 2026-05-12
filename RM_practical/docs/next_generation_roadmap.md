# Next-Generation RAASA Roadmap

RAASA v1 is a prototype proving that adaptive containment is feasible. The next phases should extend the same architecture in this order:

1. Add syscall-derived behavioral signals to the `Observer` and `Risk Assessor`.
2. Add network-aware anomaly signals and network-aware containment actions.
3. Introduce richer enforcement backends beyond CPU throttling.
4. Replace the linear risk model with stronger policy reasoning or learned models.
5. Extend the single-host controller into a node agent for Kubernetes environments.
6. Integrate external runtime detection tools as high-confidence evidence sources.
