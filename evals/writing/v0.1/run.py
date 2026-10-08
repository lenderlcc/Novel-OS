"""Offline acceptance runner; existing pytest fixtures own isolated test schemas."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SUITE = Path(__file__).resolve().parent
BACKEND = SUITE.parents[2] / "backend"
sys.path.insert(0, str(BACKEND))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New evidence output directory")
    args = parser.parse_args()
    if Path.cwd() != BACKEND:
        parser.error("Run from backend/ using uv run python ../evals/writing/v0.1/run.py")
    args.output.mkdir(parents=True, exist_ok=False)
    nodes, hashes = [], {}
    for path in sorted((SUITE / "cases").glob("*.json")):
        case = json.loads(path.read_text())
        hashes[case["id"]] = hashlib.sha256(path.read_bytes()).hexdigest()
        for node in case["automated_tests"]:
            assert node.startswith("tests/core/writing/test_") and "test_live" not in node
            if node not in nodes:
                nodes.append(node)
    assert nodes, "No cases selected"
    from lineage_audit import LineageAudit

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    return pytest.main(
        [*nodes, "-q", f"--junitxml={args.output / 'writing-e2e.xml'}"],
        plugins=[LineageAudit(args.output / "lineage.json", commit, hashes)],
    )


if __name__ == "__main__":
    raise SystemExit(main())
