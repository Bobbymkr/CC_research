from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkloadSpec:
    key: str
    category: str
    image: str
    command: list[str]
    description: str
    expected_tier: str


WORKLOAD_CATALOG = {
    "benign_steady": WorkloadSpec(
        key="benign_steady",
        category="benign",
        image="nginx:1.27-alpine",
        command=[],
        description="Steady low-variance web workload",
        expected_tier="L1",
    ),
    "benign_bursty": WorkloadSpec(
        key="benign_bursty",
        category="benign",
        image="python:3.12-alpine",
        command=[
            "sh",
            "-c",
            "while true; do python - <<'PY'\nfor _ in range(1500000):\n    pass\nPY\nsleep 8; done",
        ],
        description="Bursty but non-malicious CPU activity",
        expected_tier="L2",
    ),
    "suspicious": WorkloadSpec(
        key="suspicious",
        category="suspicious",
        image="python:3.12-alpine",
        command=[
            "sh",
            "-c",
            "while true; do python - <<'PY'\nimport subprocess\nfor _ in range(6):\n    subprocess.Popen(['sleep', '15'])\nPY\nsleep 4; done",
        ],
        description="Sustained moderate process growth",
        expected_tier="L2",
    ),
    "malicious_pattern": WorkloadSpec(
        key="malicious_pattern",
        category="malicious",
        image="python:3.12-alpine",
        command=[
            "sh",
            "-c",
            "python - <<'PY'\nwhile True:\n    pass\nPY",
        ],
        description="Strong sustained CPU abuse pattern",
        expected_tier="L3",
    ),
    "malicious_pattern_heavy": WorkloadSpec(
        key="malicious_pattern_heavy",
        category="malicious",
        image="python:3.12-alpine",
        command=[
            "sh",
            "-c",
            (
                "for i in 1 2 3 4 5 6 7 8; do sleep 30 & done; "
                "python - <<'PY'\nwhile True:\n    pass\nPY"
            ),
        ],
        description="CPU abuse plus bounded process fan-out under guardrails",
        expected_tier="L3",
    ),
    "malicious_network_heavy": WorkloadSpec(
        key="malicious_network_heavy",
        category="malicious",
        image="alpine:3",
        command=[
            "sh",
            "-c",
            "while true; do wget -qO /dev/null https://proof.ovh.net/files/10Mb.dat; sleep 0.1; done",
        ],
        description="Network abuse via sustained high-speed downloads",
        expected_tier="L3",
    ),
    "malicious_syscall_heavy": WorkloadSpec(
        key="malicious_syscall_heavy",
        category="malicious",
        image="python:3.12-alpine",
        command=[
            "sh",
            "-c",
            (
                "python - <<'PY'\n"
                "import os, time\n"
                "while True:\n"
                "    for _ in range(200):\n"
                "        os.getpid()\n"
                "        os.listdir('/')\n"
                "        os.stat('/proc/1')\n"
                "    time.sleep(0.01)\n"
                "PY"
            ),
        ],
        description="Syscall storm: high-frequency metadata operations with low CPU footprint",
        expected_tier="L3",
    ),
}
