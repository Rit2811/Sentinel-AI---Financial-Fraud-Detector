import json

import pytest

from fraud_ml import application_benchmark as benchmark
from fraud_ml.serving import sha256
from fraud_ml.database import database_target_sha256


def test_external_workload_requires_explicit_candidate_and_target():
    with pytest.raises(SystemExit):
        benchmark.main(
            [
                "--tps",
                "1",
                "--seconds",
                "10",
                "--external-database-target-sha256",
                "a" * 64,
            ]
        )


@pytest.mark.parametrize("wrong", [None, "target", "tls", "certificate", "writable"])
def test_external_database_verification_is_pinned_and_read_only(tmp_path, wrong):
    cert = tmp_path / "root.crt"
    cert.write_text("test-certificate")
    other = tmp_path / "other.crt"
    other.write_text("different-certificate")
    root = "/run/secrets/supabase-root.crt"
    url = (
        "postgresql://postgres.example:placeholder@aws-0-example.pooler.supabase.com:5432/postgres?sslmode=verify-full&sslrootcert="
        + root
    )
    pin = database_target_sha256(url)
    env = {
        "POSTGRES_URL": url,
        "DATABASE_URL": url,
        "PGSSLROOTCERT": root,
        "PGSSLMODE": "verify-full",
    }
    if wrong == "target":
        env["POSTGRES_URL"] = url.replace("postgres.example", "postgres.other")
        env["DATABASE_URL"] = env["POSTGRES_URL"]
    if wrong == "tls":
        env["PGSSLMODE"] = "require"
    detail = {
        "Config": {"Env": [key + "=" + value for key, value in env.items()]},
        "Mounts": [
            {
                "Destination": root,
                "Source": str(other if wrong == "certificate" else cert),
                "RW": wrong == "writable",
            }
        ],
    }
    if wrong:
        with pytest.raises(ValueError):
            benchmark.verify_external_target([detail], pin, cert)
    else:
        benchmark.verify_external_target([detail], pin, cert)


@pytest.mark.parametrize("seconds", ["0", "601"])
def test_application_workload_rejects_unbounded_duration(seconds):
    with pytest.raises(SystemExit):
        benchmark.main(["--tps", "5", "--seconds", seconds])


def test_unqualified_diagnostic_cannot_run_full_gate():
    with pytest.raises(SystemExit):
        benchmark.main(["--tps", "5", "--seconds", "600", "--diagnostic"])


def test_qualification_requires_explicit_one_second_candidate():
    with pytest.raises(SystemExit):
        benchmark.main(["--tps", "5", "--seconds", "600", "--qualification"])


@pytest.mark.parametrize(
    "options",
    [
        ["--diagnostic-deadline-ms", "2000"],
        ["--trial-run-id", "afba0a1e-7d4c-4df0-834f-33ecf9a7c7d3"],
        ["--diagnostic-deadline-ms", "3000"],
    ],
)
def test_deadline_trial_requires_explicit_bounded_configuration(options):
    with pytest.raises(SystemExit):
        benchmark.main(["--tps", "5", "--seconds", "600", *options])


@pytest.mark.parametrize("wrong", ["image", "network", "volume"])
def test_application_client_rejects_wrong_deployment_before_start(
    tmp_path, monkeypatch, wrong
):
    ml = tmp_path / "services/ml"
    (ml / "artifacts/runtime").mkdir(parents=True)
    environment = tmp_path / ".env.application.local"
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


@pytest.mark.parametrize("external", [None, "a" * 64])
def test_local_postgres_is_required_only_for_local_measurement(monkeypatch, external):
    inspected = []

    def inspect(name):
        inspected.append(name)
        if external and name == "sentinel-ai-postgres-1":
            raise AssertionError("Cloud measurement must not inspect local PostgreSQL")
        return {
            "State": {"Running": True},
            "Image": "expected",
            "NetworkSettings": {"Networks": {"sentinel-ai_default": {}}},
            "Mounts": [{"Name": "sentinel-ai-postgres-data"}],
        }

    monkeypatch.setattr(benchmark, "inspect_container", inspect)
    benchmark.verify_application_containers(
        {"worker_image_id": "expected", "backend_image_id": "expected"},
        False,
        external,
    )
    assert ("sentinel-ai-postgres-1" in inspected) is (external is None)


@pytest.mark.parametrize("wrong", ["stopped", "network", "image", "volume"])
def test_local_container_guards_remain_enforced(monkeypatch, wrong):
    def inspect(name):
        return {
            "State": {"Running": wrong != "stopped"},
            "Image": "other" if wrong == "image" else "expected",
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
        benchmark.verify_application_containers(
            {"worker_image_id": "expected", "backend_image_id": "expected"},
            False,
            None,
        )


@pytest.mark.parametrize("wrong", [None, "writable", "volume", "manifest", "missing"])
def test_relocated_bundle_uses_verified_read_only_worker_mount(tmp_path, wrong):
    bundle = tmp_path / "relocated-model"
    bundle.mkdir()
    manifest = bundle / "manifest.json"
    manifest.write_text("frozen-manifest")
    mount = {
        "Destination": "/model",
        "Source": str(bundle),
        "RW": wrong == "writable",
        "Type": "volume" if wrong == "volume" else "bind",
    }
    worker = {"Mounts": [] if wrong == "missing" else [mount]}
    pin = "a" * 64 if wrong == "manifest" else sha256(manifest)
    if wrong:
        with pytest.raises(ValueError):
            benchmark.deployed_bundle_path(worker, pin)
    else:
        assert benchmark.deployed_bundle_path(worker, pin) == bundle
