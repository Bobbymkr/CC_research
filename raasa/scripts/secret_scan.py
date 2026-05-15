from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws_secret_access_key_assignment", re.compile(r"(?i)\baws_secret_access_key\b\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{20,}")),
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
)

SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "AWS_Results",
    "AWS_Results_26_april",
    "AWS_Results_Data",
    "AWS_v2_Results",
    "__pycache__",
    "graphify-out",
}

BINARY_SUFFIXES = {
    ".docx",
    ".gz",
    ".ico",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".pkl",
    ".png",
    ".tar",
    ".zip",
}


def iter_candidate_files(root: Path) -> list[Path]:
    tracked = _git_tracked_files(root)
    if tracked:
        return [path for path in tracked if _should_scan(path)]
    return [path for path in root.rglob("*") if path.is_file() and _should_scan(path)]


def scan_file(path: Path) -> list[tuple[str, int]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    findings: list[tuple[str, int]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append((name, line_number))
    return findings


def scan_tree(root: Path) -> list[str]:
    failures: list[str] = []
    for path in iter_candidate_files(root):
        for finding, line_number in scan_file(path):
            failures.append(f"{path.relative_to(root)}:{line_number}: {finding}")
    return failures


def _git_tracked_files(root: Path) -> list[Path]:
    try:
        repo_root_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(repo_root_result.stdout.strip()).resolve()
        try:
            root_arg = str(root.relative_to(repo_root))
        except ValueError:
            root_arg = str(root)
        result = subprocess.run(
            ["git", "ls-files", "--", root_arg],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    tracked_paths: list[Path] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = (repo_root / line.strip()).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        tracked_paths.append(path)
    return tracked_paths


def _should_scan(path: Path) -> bool:
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    lower_parts = {part.lower() for part in path.parts}
    if "rm_practical" in lower_parts and "results" in lower_parts:
        return False
    if path.suffix.lower() in BINARY_SUFFIXES:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan tracked RAASA files for obvious committed secrets.")
    parser.add_argument("--root", default=".", help="Repository root to scan")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    failures = scan_tree(root)
    if failures:
        print("Secret scan failed. Remove or rotate these credentials before publishing:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print("Secret scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
