import json
from types import SimpleNamespace

import pytest

from fraud_ml.worker import ScoringWorker
from fraud_ml.worker_benchmark import profile_summary


def test_profiling_off_is_silent(monkeypatch, capsys):
    monkeypatch.delenv("SCORING_PROFILE", raising=False)
    worker = object.__new__(ScoringWorker)
    with worker.profile_stage("feature_calculation"):
        pass
    assert capsys.readouterr().out == ""


def test_profile_retains_failed_stage_without_payload(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("SCORING_PROFILE", "1")
    worker = object.__new__(ScoringWorker)
    worker.run_id = "safe-run"
    worker._profile_records = []
    with pytest.raises(ValueError):
        with worker.profile_stage("result_commit_ack", "safe-event", queue_ms=200):
            raise ValueError("secret-payload-not-logged")
    assert capsys.readouterr().out == ""
    worker.flush_profile()
    output = capsys.readouterr().out
    row = json.loads(output)["records"][0]
    assert row["elapsed_ms"] >= 0
    assert row["process_cpu_ms"] >= 0
    assert "secret-payload" not in output
    path = tmp_path / "worker.log"
    path.write_text("not json\n" + output)
    report = profile_summary(path)
    assert report["records"] == 1
    assert report["stages"]["accepted_to_assignment_queue"]["maximum"] == 200
    assert report["stages"]["result_commit_ack"]["count"] == 1


def test_heartbeat_debounces_only_ready_updates(monkeypatch):
    worker = object.__new__(ScoringWorker)
    worker.run_id = "safe-run"
    worker._ready_heartbeat_at = 100
    calls = []
    worker.db = SimpleNamespace(
        execute=lambda *args: SimpleNamespace(fetchone=lambda: {"blocked": False})
    )
    worker.health = lambda ready: calls.append(ready)
    monkeypatch.setattr("fraud_ml.worker.time.monotonic", lambda: 100.5)
    worker.ready_heartbeat()
    assert calls == []
    monkeypatch.setattr("fraud_ml.worker.time.monotonic", lambda: 101)
    worker.ready_heartbeat()
    assert calls == [True]
    worker.db = SimpleNamespace(
        execute=lambda *args: SimpleNamespace(fetchone=lambda: {"blocked": True})
    )
    worker.ready_heartbeat()
    assert calls == [True]
