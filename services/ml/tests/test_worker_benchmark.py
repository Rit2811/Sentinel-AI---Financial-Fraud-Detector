from types import SimpleNamespace

import pytest

from fraud_ml import worker_benchmark as benchmark


def test_awake_request_is_restored_on_failure(monkeypatch):
    calls = []

    def set_state(flags):
        calls.append(flags)
        return 0x80000000

    monkeypatch.setattr(benchmark.sys, "platform", "win32")
    monkeypatch.setattr(
        benchmark.ctypes,
        "WinDLL",
        lambda *args, **kwargs: SimpleNamespace(SetThreadExecutionState=set_state),
        raising=False,
    )
    with pytest.raises(ValueError, match="fixture"):
        with benchmark.keep_host_awake():
            raise ValueError("fixture")
    assert calls == [0x80000001, 0x80000000]


def test_producer_does_not_catch_up_after_suspend(monkeypatch):
    monkeypatch.setattr(benchmark.time, "perf_counter", lambda: 50000)
    with pytest.raises(RuntimeError, match="paused"):
        benchmark.producer_lag_seconds(100, 30, 5)


def test_small_scheduling_lag_is_measured(monkeypatch):
    monkeypatch.setattr(benchmark.time, "perf_counter", lambda: 106.1)
    assert benchmark.producer_lag_seconds(100, 30, 5) == pytest.approx(0.1)


def test_durable_latency_scopes_application_attempts_without_resetting_history():
    calls = []
    db = SimpleNamespace(
        execute=lambda query, params: (
            calls.append((query, params))
            or SimpleNamespace(fetchall=lambda: [{"milliseconds": 123}])
        )
    )
    assert benchmark.durable_latency_report(db, "same-run", ["new-event"])["count"] == 1
    assert calls[0][1] == ("same-run", ["new-event"], ["new-event"])
    assert "ANY(%s::uuid[])" in calls[0][0]
    benchmark.durable_latency_report(db, "same-run")
    assert calls[1][1] == ("same-run", None, None)
