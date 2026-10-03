"""Non-destructive application-network load measurement with pinned tool sources."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .serving import sha256
from .worker_benchmark import keep_host_awake, profile_summary


def inspect_container(name):
    return json.loads(subprocess.check_output(["docker", "inspect", name], text=True))[
        0
    ]


@keep_host_awake()
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tps", type=int, choices=(1, 5), required=True)
    parser.add_argument("--seconds", type=int, required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.seconds <= 600:
        parser.error("Workload duration must be 1..600 seconds")
    ml = Path(__file__).resolve().parents[2]
    root = ml.parents[1]
    environment = root / ".env.task6.local"
    metadata_path = ml / "artifacts/runtime/application.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if sha256(environment) != metadata["environment_sha256"]:
        raise ValueError("Private application configuration changed")
    config = dict(
        line.split("=", 1)
        for line in environment.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    for container, key in [
        ("sentinel-ai-scoring-worker-1", "worker_image_id"),
        ("sentinel-ai-api-1", "backend_image_id"),
        ("sentinel-ai-publisher-1", "backend_image_id"),
        ("sentinel-ai-postgres-1", None),
        ("sentinel-ai-redis-1", None),
    ]:
        detail = inspect_container(container)
        if (
            not detail["State"]["Running"]
            or "sentinel-ai_default" not in detail["NetworkSettings"]["Networks"]
        ):
            raise ValueError("Application container/network not ready")
        if key and detail["Image"] != metadata[key]:
            raise ValueError("Application image differs from qualified deployment")
    if not any(
        volume.get("Name") == "sentinel-ai-postgres-data"
        for volume in inspect_container("sentinel-ai-postgres-1")["Mounts"]
    ):
        raise ValueError("Original application PostgreSQL volume required")
    api_config = dict(
        value.split("=", 1)
        for value in inspect_container("sentinel-ai-api-1")["Config"]["Env"]
        if "=" in value
    )
    worker_config = inspect_container("sentinel-ai-scoring-worker-1")["Config"]["Env"]
    profiling = "SCORING_PROFILE=1" in worker_config
    resources = json.loads(
        subprocess.check_output(
            [
                "docker",
                "info",
                "--format",
                '{"cpus":{{.NCPU}},"memory_bytes":{{.MemTotal}}}',
            ],
            text=True,
        )
    )
    if (
        api_config.get("SCORING_RUN_ID") != metadata["run_id"]
        or api_config.get("RESULT_API_TOKEN") != config["RESULT_API_TOKEN"]
    ):
        raise ValueError("Application API identity differs from private configuration")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output = ml / "reports/task6-application-load" / stamp
    output.mkdir(parents=True, exist_ok=False)
    name = "task6-application-controller-" + str(uuid4())
    temporary_env = ml / "artifacts/runtime" / (name + ".env")
    values = {
        "POSTGRES_URL": api_config["POSTGRES_URL"],
        "REDIS_URL": api_config["REDIS_URL"],
        "RESULT_API_TOKEN": config["RESULT_API_TOKEN"],
        "VERIFIED_WORKER_IMAGE_ID": metadata["worker_image_id"],
        "VERIFIED_BACKEND_IMAGE_ID": metadata["backend_image_id"],
    }
    descriptor = os.open(temporary_env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(
            "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
        )
    package = "/app/.venv/lib/python3.12/site-packages/fraud_ml"
    tool_files = [
        ml / "src/fraud_ml" / (module + ".py")
        for module in ("connected_benchmark", "worker_benchmark")
    ]
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "--network",
        "sentinel-ai_default",
        "--label",
        "sentinel.task6.application-controller=true",
        "--entrypoint",
        "/app/.venv/bin/python",
        "--env-file",
        str(temporary_env),
    ]
    for source, target in [
        (Path(config["SCORING_BUNDLE_DIR"]), "/model"),
        (metadata_path, "/application.json"),
        *((source, package + "/" + source.name) for source in tool_files),
    ]:
        command.extend(
            ["--mount", f"type=bind,source={source.resolve()},target={target},readonly"]
        )
    command.extend(
        [
            "--mount",
            f"type=bind,source={output.resolve()},target=/output",
            metadata["worker_image_id"],
            "-m",
            "fraud_ml.connected_benchmark",
            "--application",
            "--application-docker-client",
            "--runtime-metadata",
            "/application.json",
            "--bundle",
            "/model",
            "--bundle-sha256",
            metadata["bundle_sha256"],
            "--run-id",
            metadata["run_id"],
            "--base",
            "http://sentinel-ai-api-1:8000",
            "--tps",
            str(args.tps),
            "--seconds",
            str(args.seconds),
            "--output",
            "/output/report.json",
        ]
    )
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=args.seconds + 180
        )
        (output / "controller.log").write_text(
            result.stdout + result.stderr, encoding="utf-8"
        )
        if result.returncode:
            raise RuntimeError(
                "Application client failed; inspect the private controller log"
            )
        path = output / "report.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report["measurement_tool_sources_sha256"] = {
            source.name: sha256(source)
            for source in [Path(__file__).resolve(), *tool_files]
        }
        report["tool_mount_scope"] = (
            "Controller only; no application worker/model source mounts changed"
        )
        report["docker_resources"] = resources
        report["environment"]["stage_profiling"] = profiling
        if profiling:
            log = output / "worker-profile.log"
            logs = subprocess.run(
                ["docker", "logs", "sentinel-ai-scoring-worker-1"],
                capture_output=True,
                text=True,
                check=True,
            )
            log.write_text(logs.stdout + logs.stderr, encoding="utf-8")
            report["worker_stage_profile"] = profile_summary(log)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "report": str(path),
                    "counts": report["durable_status_counts"],
                    "durable_latency": report["durable_decision_latency_ms"],
                    "timely": report["all_attempts_timely_scored"],
                }
            )
        )
    finally:
        subprocess.run(
            ["docker", "stop", "--time", "1", name], capture_output=True, check=False
        )
        temporary_env.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
