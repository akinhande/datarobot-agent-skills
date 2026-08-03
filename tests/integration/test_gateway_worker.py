# Copyright (c) 2026 DataRobot, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT_DIR = (
    REPO_ROOT
    / "skills"
    / "datarobot-agent-assist"
    / "agent-assist-simulate"
    / "scripts"
)
SCRIPT_PATH = SCRIPT_DIR / "gateway_worker.py"
sys.path.insert(0, str(SCRIPT_DIR))
artifacts = importlib.import_module("artifacts")
SPEC = importlib.util.spec_from_file_location("gateway_worker", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
gateway_worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway_worker)


def test_scenario_id_from_runner_input(tmp_path: Path) -> None:
    input_path = tmp_path / "runner-input.json"
    input_path.write_text(
        json.dumps({"scenario_id": "scn_040a81e85e34"}),
        encoding="utf-8",
    )

    assert gateway_worker._scenario_id_from_input(input_path) == "scn_040a81e85e34"


def test_scenario_id_from_nested_scenario_input(tmp_path: Path) -> None:
    input_path = tmp_path / "nested-scenario-input.json"
    input_path.write_text(
        json.dumps({"scenario": {"scenario_id": "scn_abc123456789"}}),
        encoding="utf-8",
    )

    assert gateway_worker._scenario_id_from_input(input_path) == "scn_abc123456789"


def test_write_metrics_writes_shard_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metrics_path = tmp_path / ".datarobot/swarm/metrics.jsonl"
    monkeypatch.setattr(gateway_worker, "METRICS_PATH", metrics_path)

    gateway_worker._write_metrics({"role": "runner", "success": True})

    shards = list(metrics_path.parent.glob("metrics-*.jsonl"))
    assert len(shards) == 1
    record = json.loads(shards[0].read_text(encoding="utf-8").strip())
    assert record["role"] == "runner"
    assert record["success"] is True


def test_merge_metrics_combines_shards_and_removes_them(tmp_path: Path) -> None:
    metrics_dir = tmp_path / "swarm"
    metrics_dir.mkdir()
    (metrics_dir / "metrics-aaa.jsonl").write_text(
        json.dumps({"role": "runner", "success": True}) + "\n", encoding="utf-8"
    )
    (metrics_dir / "metrics-bbb.jsonl").write_text(
        json.dumps({"role": "evaluator", "success": False}) + "\n", encoding="utf-8"
    )

    artifacts.merge_metrics(metrics_dir)

    merged = metrics_dir / "metrics.jsonl"
    assert merged.is_file()
    lines = [ln for ln in merged.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2
    records = [json.loads(ln) for ln in lines]
    roles = {r["role"] for r in records}
    assert roles == {"runner", "evaluator"}
    assert not list(metrics_dir.glob("metrics-*.jsonl")), "shards should be removed"


def test_merge_metrics_is_idempotent_when_no_shards(tmp_path: Path) -> None:
    metrics_dir = tmp_path / "swarm"
    metrics_dir.mkdir()

    artifacts.merge_metrics(metrics_dir)

    assert not (metrics_dir / "metrics.jsonl").exists()
