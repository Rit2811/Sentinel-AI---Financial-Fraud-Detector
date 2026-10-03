import json

import pytest

from fraud_ml import application_benchmark as benchmark
from fraud_ml.serving import sha256


@pytest.mark.parametrize("seconds", ["0", "601"])
def test_application_workload_rejects_unbounded_duration(seconds):
    with pytest.raises(SystemExit):
        benchmark.main(["--tps", "5", "--seconds", seconds])


@pytest.mark.parametrize("wrong", ["image", "network", "volume"])
def test_application_client_rejects_wrong_deployment_before_start(
    tmp_path, monkeypatch, wrong
):
    ml = tmp_path / "services/ml"
    (ml / "artifacts/runtime").mkdir(parents=True)
    environment = tmp_path / ".env.task6.local"
    environment.write_text("RESULT_API_TOKEN=unit-test-only\n")
    metadata = {
        "environment_sha256": sha256(environment),
        "run_id": "original",
        "worker_image_id": "expected",
        "backend_image_id": "expected",
    }
    (ml / "artifacts/runtime/application.json").write_text(json.dumps(metadata))
    monkeypatch.setattr(
        benchmark, "__file__", str(ml / "src/fraud_ml/application_benchmark.py")
    )

    def inspect(name):
        return {
            "State": {"Running": True},
            "Image": "wrong" if wrong == "image" else "expected",
            "NetworkSettings": {
                "Networks": {
                    "other" if wrong == "network" else "sentinel-ai_default": {}
                }
            },
            "Mounts": [
                {"Name": "other" if wrong == "volume" else "sentinel-ai-postgres-data"}
            ],
        }

    monkeypatch.setattr(benchmark, "inspect_container", inspect)
    with pytest.raises(ValueError):
        benchmark.main(["--tps", "5", "--seconds", "600"])
    assert not (ml / "reports").exists()
