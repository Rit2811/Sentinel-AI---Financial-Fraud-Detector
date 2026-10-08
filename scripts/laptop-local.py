"""Private-safe driver for the approved persistent PostgreSQL deployment."""

import json
import re
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from fraud_ml.database import database_target_sha256
from fraud_ml.deployment_binding import environment_digest
from fraud_ml.serving import sha256

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "services/ml/reports/laptop-local"
ART = ROOT / "services/ml/artifacts/laptop-local"
ENV = ROOT / ".env.application-runtime.local"
if not ENV.exists():
    ENV = ROOT / ".env.laptop-local.local"  # Preserved historical configuration.
BASE = [
    "docker",
    "compose",
    "--env-file",
    str(ENV),
    "-f",
    "infrastructure/compose.yaml",
    "-f",
    "infrastructure/compose.postgres-local.yaml",
    "--profile",
    "scoring",
]
BACKUP = ROOT / "services/ml/artifacts/laptop-handoff/rerun-20261008T104708Z"
PRIOR = ROOT / "services/ml/reports/laptop-rerun/20261008T104708Z"


def run(args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "operation-error.log").write_text(result.stderr)
        raise RuntimeError("Operation failed; private error log retained")
    return result.stdout


def config():
    return json.loads(run(BASE + ["config", "--format", "json"]))


def values():
    env = {}
    for line in ENV.read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            env[key] = value.strip('"')
    for _ in range(6):
        env = {
            key: re.sub(r"\$\{([A-Z0-9_]+)\}", lambda match: env[match[1]], value)
            for key, value in env.items()
        }
    return env


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2))


def inspect(name):
    return json.loads(run(["docker", "inspect", name]))[0]


def prepare():
    ART.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if not (ART / "environment-before-binding.env").exists():
        (ART / "environment-before-binding.env").write_bytes(ENV.read_bytes())
    raw = ENV.read_text()
    header = raw.splitlines()[0]
    if (
        not header.startswith("#")
        and "# Local PostgreSQL deployment preparation ONLY" in header
        and "=" not in header
    ):
        raw = header[header.index("#") :] + raw[len(header) :]
        ENV.write_text(raw)
    env = values()
    for key in (
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "RESULT_API_TOKEN",
        "REVIEW_API_TOKEN",
    ):
        assert re.fullmatch("[0-9a-f]{64}", env[key])
    assert (
        sha256(BACKUP / "mumbai-after-laptop-diagnostics.dump")
        == "527f6be441b33e410287497ae36421f277f8361e5e51b879a53dbfb90a31349d"
    )
    assert (
        sha256(BACKUP / "redis-after-rerun.tar")
        == "f5f3e81db04f2ac620268f8e2df73adc714f5dba0920834f51a0b5b120cf9a98"
    )
    # Preserve the generated credential file before adding deployment-only pins.
    if not (ART / "environment-before-binding.env").exists():
        (ART / "environment-before-binding.env").write_bytes(ENV.read_bytes())
    text = ENV.read_text()
    updates = {
        "LOCAL_POSTGRES_IMAGE": "postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24",
        "SCORING_WORKER_IMAGE": "sentinel-ai-scoring-worker:random-forest",
        "APPLICATION_DATABASE_TARGET_SHA256": database_target_sha256(
            env["POSTGRES_URL"]
        ),
    }
    for key, value in updates.items():
        pattern = rf"(?m)^{key}=.*$"
        text = (
            re.sub(pattern, key + "=" + value, text)
            if re.search(pattern, text)
            else text + "\n" + key + "=" + value + "\n"
        )
    ENV.write_text(text)
    (ART / "Dockerfile").write_text(
        "FROM sentinel-ai-scoring-worker:admission-optimized\nCOPY src/fraud_ml/database.py /app/.venv/lib/python3.12/site-packages/fraud_ml/database.py\n"
    )
    save(
        "preparation.json",
        {
            "target_sha256": updates["APPLICATION_DATABASE_TARGET_SHA256"],
            "source_backups_verified": True,
            "local_credentials_preserved": True,
            "activation_held": True,
        },
    )
    print(
        json.dumps(
            {
                "status": "PREPARED",
                "target_sha256": updates["APPLICATION_DATABASE_TARGET_SHA256"],
            }
        )
    )


def provision():
    config()
    env = values()
    existing = set(
        run(["docker", "volume", "ls", "--format", "{{.Name}}"]).splitlines()
    )
    for key in ("LOCAL_POSTGRES_VOLUME", "LOCAL_REDIS_VOLUME"):
        assert env[key] not in existing and env[key] not in (
            "sentinel-ai-postgres-data",
            "sentinel-ai-redis-data",
            "sentinel-ai-redis-laptop-mumbai-20261008",
        )
        run(
            [
                "docker",
                "volume",
                "create",
                "--label",
                "sentinel.purpose=postgres-application",
                env[key],
            ]
        )
    # This helper refuses an already populated target and restores only the stopped archive.
    restore = ART / "restore-redis.sh"
    restore.write_text(
        'set -eu\ntest -z "$(ls -A /data)"\ntar -xf /backup/redis-after-rerun.tar -C /data\nfind /data -type f -exec sha256sum {} \\;\n',
        newline="\n",
    )
    hashes = run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--mount",
            f"type=volume,source={env['LOCAL_REDIS_VOLUME']},target=/data",
            "--mount",
            f"type=bind,source={BACKUP},target=/backup,readonly",
            "--mount",
            f"type=bind,source={restore},target=/restore.sh,readonly",
            "redis:7.2.5-alpine3.20",
            "sh",
            "/restore.sh",
        ]
    )
    save(
        "redis-restored-file-hashes.json",
        {
            "volume": env["LOCAL_REDIS_VOLUME"],
            "hashes": hashes.splitlines(),
            "old_volumes_preserved": True,
        },
    )
    run(BASE + ["up", "-d", "--no-deps", "--no-build", "--wait", "postgres"])
    # Require a newly initialized empty public schema before importing application data.
    empty = run(
        [
            "docker",
            "exec",
            "sentinel-ai-postgres-1",
            "psql",
            "-X",
            "-A",
            "-t",
            "-U",
            env["POSTGRES_USER"],
            "-d",
            env["POSTGRES_DB"],
            "-c",
            "SELECT count(*) FROM pg_tables WHERE schemaname='public'",
        ]
    ).strip()
    assert empty == "0"
    run(
        [
            "docker",
            "cp",
            str(BACKUP / "mumbai-after-laptop-diagnostics.dump"),
            "sentinel-ai-postgres-1:/tmp/application.dump",
        ]
    )
    run(
        [
            "docker",
            "cp",
            str(BACKUP / "laptop-recovery-filtered.toc"),
            "sentinel-ai-postgres-1:/tmp/application.toc",
        ]
    )
    run(
        [
            "docker",
            "exec",
            "sentinel-ai-postgres-1",
            "pg_restore",
            "--dbname",
            env["POSTGRES_DB"],
            "--username",
            env["POSTGRES_USER"],
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--no-acl",
            "--use-list=/tmp/application.toc",
            "/tmp/application.dump",
        ]
    )
    run(
        [
            "docker",
            "cp",
            str(BACKUP / "verify-laptop-restore.sql"),
            "sentinel-ai-postgres-1:/tmp/verify.sql",
        ]
    )
    restored = json.loads(
        run(
            [
                "docker",
                "exec",
                "sentinel-ai-postgres-1",
                "psql",
                "-X",
                "-q",
                "-A",
                "-t",
                "-U",
                env["POSTGRES_USER"],
                "-d",
                env["POSTGRES_DB"],
                "-f",
                "/tmp/verify.sql",
            ]
        )
    )
    source = json.loads((PRIOR / "backup-source-snapshot.json").read_text())
    comparisons = {key: restored[key] == source[key] for key in restored}
    assert all(comparisons.values())
    # Restrict PUBLIC access on the restored local schema, including routines/sequences.
    privilege_sql = "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC; REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC; REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC; REVOKE CREATE ON SCHEMA public FROM PUBLIC;"
    run(
        [
            "docker",
            "exec",
            "sentinel-ai-postgres-1",
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            env["POSTGRES_USER"],
            "-d",
            env["POSTGRES_DB"],
            "-c",
            privilege_sql,
        ]
    )
    save(
        "restore-verification.json",
        {
            "status": "PASS",
            "tables_verified": len(restored["fingerprints"]),
            "comparisons": comparisons,
            "events": restored["fingerprints"]["authorization_events"]["count"],
            "public_privileges_revoked": True,
            "source_preserved": True,
            "postgres_volume": env["LOCAL_POSTGRES_VOLUME"],
            "redis_volume": env["LOCAL_REDIS_VOLUME"],
        },
    )
    run(
        BASE
        + [
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "redis",
            "api",
            "publisher",
            "scoring-worker",
            "dashboard",
        ]
    )
    bind()


def bind():
    env = values()
    images, digests = {}, {}
    for name in ("api", "publisher", "scoring-worker", "postgres", "redis"):
        item = inspect(f"sentinel-ai-{name}-1")
        assert item["State"]["Running"]
        actual = dict(
            value.split("=", 1) for value in item["Config"]["Env"] if "=" in value
        )
        images[name] = item["Image"]
        digests[name] = environment_digest(actual)
    binding = {
        "layout": "laptop-local-pg17",
        "status": "RESTORED_VERIFIED_HELD",
        "run_id": env["SCORING_RUN_ID"],
        "database_target_sha256": env["APPLICATION_DATABASE_TARGET_SHA256"],
        "original_runtime_sha256": sha256(
            ROOT / "services/ml/artifacts/runtime/application.json"
        ),
        "environment_file": str(ENV),
        "environment_sha256": sha256(ENV),
        "restore_verification": str(OUT / "restore-verification.json"),
        "restore_verification_sha256": sha256(OUT / "restore-verification.json"),
        "images": images,
        "environment_digests": digests,
        "volumes": {
            "postgres": env["LOCAL_POSTGRES_VOLUME"],
            "redis": env["LOCAL_REDIS_VOLUME"],
        },
    }
    (ART / "deployment-binding.json").write_text(json.dumps(binding, indent=2))
    print(
        json.dumps(
            {
                "status": binding["status"],
                "target_sha256": binding["database_target_sha256"],
                "images": images,
            }
        )
    )


def probe():
    env = values()
    with psycopg.connect(
        env["HOST_DATABASE_URL"], autocommit=True, row_factory=dict_row
    ) as db:
        db.execute("SET default_transaction_read_only=on")
        from fraud_ml.connected_benchmark import clock_measurements, clocks_consistent

        clocks = clock_measurements(db)
        health = db.execute(
            "SELECT ready,blocked,error_code,extract(epoch FROM clock_timestamp()-heartbeat_at) AS age FROM scoring_worker_health WHERE run_id=%s",
            (env["SCORING_RUN_ID"],),
        ).fetchone()
        health["age"] = float(health["age"])
        settings = db.execute(
            "SELECT current_setting('fsync') AS fsync,current_setting('synchronous_commit') AS synchronous_commit,current_setting('track_io_timing') AS io,current_setting('track_wal_io_timing') AS wal"
        ).fetchone()
        assert settings["fsync"] == settings["synchronous_commit"] == "on"
        counts = db.execute(
            "SELECT count(*) AS events FROM authorization_events"
        ).fetchone()
    report = {
        "clocks_pass": clocks_consistent(clocks),
        "clock_samples": clocks,
        "health": health,
        "settings": settings,
        "counts": counts,
        "activation_held": env["SCORING_ACTIVATION_HOLD"] != "0",
    }
    save("readiness.json", report)
    print(json.dumps(report))
    if (
        not report["clocks_pass"]
        or not health["ready"]
        or health["blocked"]
        or health["age"] > 5
    ):
        sys.exit(2)


if __name__ == "__main__":
    try:
        if sys.argv[1] == "prepare":
            prepare()
        elif sys.argv[1] == "provision":
            provision()
        elif sys.argv[1] == "bind":
            bind()
        elif sys.argv[1] == "probe":
            probe()
        elif sys.argv[1] == "compose":
            run(BASE + sys.argv[2:])
            print(json.dumps({"compose": sys.argv[2:], "status": "PASS"}))
        else:
            raise ValueError("Unknown local operation")
    except Exception as error:
        import traceback

        frames = [
            {
                "file": Path(frame.filename).name,
                "line": frame.lineno,
                "function": frame.name,
            }
            for frame in traceback.extract_tb(error.__traceback__)
        ]
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "exception_type": type(error).__name__,
                    "frames": frames,
                }
            )
        )
        sys.exit(1)
