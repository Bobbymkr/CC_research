import subprocess
import unittest

from raasa.core.telemetry import (
    Observer,
    _parse_inspect_output,
    _parse_stats_output,
    _parse_top_output,
)


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        if command[:3] == ["docker", "stats", "--no-stream"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    '{"ID":"c1","CPUPerc":"23.5%","MemPerc":"11.4%"}\n'
                    '{"ID":"c2","CPUPerc":"1.0%","MemPerc":"3.5%"}\n'
                ),
                stderr="",
            )
        if command[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    '[{"Id":"c1","Name":"/web","Config":{"Image":"nginx:latest","Labels":'
                    '{"raasa.class":"benign","raasa.expected_tier":"L1"}},'
                    '"State":{"Status":"running"}},'
                    '{"Id":"c2","Name":"/worker","Config":{"Image":"python:3.12","Labels":'
                    '{"raasa.class":"malicious","raasa.expected_tier":"L3"}},'
                    '"State":{"Status":"running"}}]'
                ),
                stderr="",
            )
        if command[:3] == ["docker", "top", "c1"]:
            return subprocess.CompletedProcess(command, 0, stdout="PID\n12\n44\n", stderr="")
        if command[:3] == ["docker", "top", "c2"]:
            return subprocess.CompletedProcess(command, 0, stdout="PID\n90\n", stderr="")
        raise AssertionError(f"Unexpected command: {command}")


class TelemetryParsingTests(unittest.TestCase):
    def test_parse_stats_output(self) -> None:
        parsed = _parse_stats_output('{"ID":"c1","CPUPerc":"40.0%","MemPerc":"12.2%"}\n')
        self.assertEqual(parsed["c1"]["cpu_percent"], 40.0)
        self.assertEqual(parsed["c1"]["memory_percent"], 12.2)

    def test_parse_inspect_output(self) -> None:
        parsed = _parse_inspect_output(
            '[{"Id":"c1","Name":"/web","Config":{"Image":"nginx","Labels":{"raasa.class":"benign"}},'
            '"State":{"Status":"running"}}]'
        )
        self.assertEqual(parsed["c1"]["name"], "web")
        self.assertEqual(parsed["c1"]["image"], "nginx")
        self.assertEqual(parsed["c1"]["status"], "running")
        self.assertEqual(parsed["c1"]["workload_class"], "benign")

    def test_parse_top_output(self) -> None:
        self.assertEqual(_parse_top_output("PID\n12\n44\n"), 2)
        self.assertEqual(_parse_top_output(""), 0)


class ObserverTests(unittest.TestCase):
    def test_collects_docker_metrics(self) -> None:
        observer = Observer(runner=FakeRunner())
        batch = observer.collect(["c1", "c2"])

        self.assertEqual(len(batch), 2)
        self.assertEqual(batch[0].cpu_percent, 23.5)
        self.assertEqual(batch[0].memory_percent, 11.4)
        self.assertEqual(batch[0].process_count, 2)
        self.assertEqual(batch[0].metadata["name"], "web")
        self.assertEqual(batch[0].metadata["workload_class"], "benign")
        self.assertEqual(batch[1].process_count, 1)

    def test_empty_container_list_returns_empty_batch(self) -> None:
        observer = Observer(runner=FakeRunner())
        self.assertEqual(observer.collect([]), [])


if __name__ == "__main__":
    unittest.main()
