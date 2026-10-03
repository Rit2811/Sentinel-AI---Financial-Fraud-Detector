from itertools import count
import json

from fraud_ml import connected_benchmark as benchmark


def test_manifest_checked_before_traffic_but_reference_model_loaded_after_terminal_observation(
    monkeypatch,
):
    phases = []

    def write_report(_, value, **_kwargs):
        assert json.loads(value)["offline_reference_model_loaded_after_traffic"] is True
        return len(value)

    monkeypatch.setattr(benchmark.Path, "write_text", write_report)
    run_id = "985d24e4-42be-4e3b-bb9a-ad43664ca053"
    pin = "f" * 64
    monkeypatch.setenv(
        "TEST_DATABASE_URL", "postgresql://127.0.0.1:25432/sentinel_task4_test"
    )
    monkeypatch.setenv("TEST_REDIS_URL", "redis://127.0.0.1:26379/0")
    monkeypatch.setenv("RESULT_API_TOKEN", "unit-test-only")
    ticks = count()
    monkeypatch.setattr(benchmark.time, "perf_counter", lambda: next(ticks) / 100)
    monkeypatch.setattr(benchmark.time, "sleep", lambda _: None)

    def manifest(*_):
        phases.append("manifest")

    class Scorer:
        def __init__(self, *_):
            assert "terminal_observed" in phases
            phases.append("reference_loaded")

        def verify_references(self):
            phases.append("references_verified")

    class Rows:
        def __init__(self, one=None, many=None):
            self.one, self.many = one, many or []

        def fetchone(self):
            return self.one

        def fetchall(self):
            return self.many

    class Database:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, sql, _=None):
            if "SELECT s.*" in sql:
                return Rows(
                    {
                        "mode": "fixture",
                        "bundle_sha256": pin,
                        "ready": True,
                        "blocked": False,
                        "durability_contract": "postcommit-v1",
                    }
                )
            if "AS pending" in sql:
                return Rows({"pending": 0, "oldest": 0})
            if "AS total" in sql:
                return Rows({"total": 0, "invalid_or_late": 0})
            if "count(*) AS n" in sql and "authorization_event_outbox" in sql:
                return Rows({"n": 1})
            if "GROUP BY status" in sql:
                return Rows(many=[{"status": "expired", "n": 1}])
            return Rows()

    def call(url, method="GET", *_args, **_kwargs):
        if method == "POST":
            assert phases == ["manifest"]
            phases.append("traffic")
            return 202, {"outcome": "accepted"}
        phases.append("terminal_observed")
        return 200, {"status": "expired"}

    monkeypatch.setattr(benchmark, "verify_manifest", manifest)
    monkeypatch.setattr(benchmark, "FrozenScorer", Scorer)
    monkeypatch.setattr(benchmark, "call", call)
    monkeypatch.setattr(
        benchmark.psycopg, "connect", lambda *_args, **_kwargs: Database()
    )
    monkeypatch.setattr(benchmark, "durable_latency_report", lambda *_: {"count": 0})
    benchmark.main(
        [
            "--bundle",
            "unused",
            "--bundle-sha256",
            pin,
            "--run-id",
            run_id,
            "--base",
            f"http://task6-fixture-api-{run_id}:8000",
            "--tps",
            "1",
            "--seconds",
            "1",
        ]
    )
    assert phases == [
        "manifest",
        "traffic",
        "terminal_observed",
        "reference_loaded",
        "references_verified",
    ]
