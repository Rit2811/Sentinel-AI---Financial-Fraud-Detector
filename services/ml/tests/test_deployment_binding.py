import json

import pytest

from fraud_ml.database import database_target_sha256
from fraud_ml.deployment_binding import environment_digest, verify_local_binding
from fraud_ml.serving import sha256


@pytest.mark.parametrize(
    "wrong",
    [None, "environment", "image", "original", "restore", "volume", "hold", "network"],
)
def test_local_binding_preserves_restore_identity_and_effective_configuration(
    tmp_path, wrong
):
    original = tmp_path / "original.json"
    original.write_text("original-approval")
    environment = tmp_path / "local.env"
    environment.write_text("local-configuration")
    restore = tmp_path / "restore.json"
    restore.write_text(json.dumps({"status": "PASS", "tables_verified": 18}))
    url = "postgresql://sentinel:placeholder@postgres:5432/sentinel"
    details = {}
    images, digests = {}, {}
    volumes = {
        "postgres": "sentinel-ai-postgres-laptop-local-pg17-data",
        "redis": "sentinel-ai-redis-laptop-local-data",
    }
    for name in ("api", "publisher", "scoring-worker", "postgres", "redis"):
        env = {
            "POSTGRES_URL": url,
            "SCORING_ACTIVATION_HOLD": "1",
            "SCORING_RUN_ID": "run",
        }
        images[name] = "image-" + name
        digests[name] = environment_digest(env)
        details["sentinel-ai-" + name + "-1"] = {
            "State": {"Running": True},
            "Image": images[name],
            "Config": {"Env": [key + "=" + value for key, value in env.items()]},
            "NetworkSettings": {"Networks": {"sentinel-ai_default": {}}},
            "Mounts": [
                {
                    "Type": "volume",
                    "Name": volumes.get(name),
                    "Destination": "/var/lib/postgresql/data"
                    if name == "postgres"
                    else "/data",
                }
            ],
        }
    binding = {
        "layout": "laptop-local-pg17",
        "status": "RESTORED_VERIFIED_HELD",
        "original_runtime_sha256": sha256(original),
        "environment_file": str(environment),
        "environment_sha256": sha256(environment),
        "restore_verification": str(restore),
        "restore_verification_sha256": sha256(restore),
        "database_target_sha256": database_target_sha256(url),
        "run_id": "run",
        "images": images,
        "environment_digests": digests,
        "volumes": volumes,
    }
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(binding))
    if wrong == "environment":
        environment.write_text("changed")
    if wrong == "original":
        original.write_text("changed")
    if wrong == "restore":
        restore.write_text("changed")
    if wrong == "image":
        details["sentinel-ai-api-1"]["Image"] = "wrong"
    if wrong == "volume":
        details["sentinel-ai-postgres-1"]["Mounts"][0]["Name"] = (
            "sentinel-ai-postgres-data"
        )
    if wrong == "hold":
        details["sentinel-ai-api-1"]["Config"]["Env"][1] = "SCORING_ACTIVATION_HOLD=0"
    if wrong == "network":
        details["sentinel-ai-api-1"]["NetworkSettings"]["Networks"] = {}
    if wrong:
        with pytest.raises(ValueError):
            verify_local_binding(path, details.__getitem__, original)
    else:
        actual, env = verify_local_binding(path, details.__getitem__, original)
        assert actual == binding and env["SCORING_ACTIVATION_HOLD"] == "1"


@pytest.mark.parametrize(
    "wrong",
    [
        None,
        "no_opt_in",
        "approval",
        "qualified",
        "held_binding",
        "technical",
        "actions",
        "restart",
        "workload",
        "credentials",
        "other_api_setting",
        "publisher_setting",
        "run",
        "image",
        "held_environment",
    ],
)
def test_active_binding_requires_approved_unchanged_qualification(tmp_path, wrong):
    original = tmp_path / "original.json"
    original.write_text("original")
    environment = tmp_path / "local.env"
    environment.write_text("SCORING_ACTIVATION_HOLD=1\nSECRET=preserved\n")
    saved_environment = tmp_path / "held.env"
    saved_environment.write_bytes(environment.read_bytes())
    restore = tmp_path / "restore.json"
    restore.write_text(json.dumps({"status": "PASS", "tables_verified": 18}))
    url = "postgresql://sentinel:placeholder@postgres:5432/sentinel"
    env = {"POSTGRES_URL": url, "SCORING_ACTIVATION_HOLD": "1", "SCORING_RUN_ID": "run"}
    volumes = {"postgres": "new-pg-data", "redis": "new-redis-data"}
    names = ("api", "publisher", "scoring-worker", "postgres", "redis")
    images = {name: "image-" + name for name in names}
    details = {
        "sentinel-ai-" + name + "-1": {
            "State": {"Running": True},
            "Image": images[name],
            "Config": {"Env": [key + "=" + value for key, value in env.items()]},
            "NetworkSettings": {"Networks": {"sentinel-ai_default": {}}},
            "Mounts": [
                {
                    "Type": "volume",
                    "Name": volumes.get(name),
                    "Destination": "/var/lib/postgresql/data"
                    if name == "postgres"
                    else "/data",
                }
            ],
        }
        for name in names
    }
    held = {
        "layout": "laptop-local-pg17",
        "status": "RESTORED_VERIFIED_HELD",
        "original_runtime_sha256": sha256(original),
        "environment_file": str(environment),
        "environment_sha256": sha256(environment),
        "restore_verification": str(restore),
        "restore_verification_sha256": sha256(restore),
        "database_target_sha256": database_target_sha256(url),
        "run_id": "run",
        "images": images,
        "environment_digests": {name: environment_digest(env) for name in names},
        "volumes": volumes,
    }
    held_path = tmp_path / "held.json"
    held_path.write_text(json.dumps(held))
    workload = tmp_path / "workload.json"
    workload.write_text("qualification-results")
    qualified = {
        "status": "LOAD_QUALIFIED",
        "activation_authorized": False,
        "deployment_binding_sha256": sha256(held_path),
        "original_runtime_sha256": sha256(original),
        "backend_image_id": images["api"],
        "worker_image_id": images["scoring-worker"],
        "run_id": "run",
        "database_target_sha256": held["database_target_sha256"],
        "normal_report": str(workload),
        "normal_report_sha256": sha256(workload),
        "peak_report": str(workload),
        "peak_report_sha256": sha256(workload),
    }
    qualified_path = tmp_path / "qualified.json"
    qualified_path.write_text(json.dumps(qualified))
    paths = {
        name: tmp_path / (name + ".json")
        for name in (
            "technical_gates",
            "actions",
            "restart",
            "backup_restore",
            "readiness",
        )
    }
    for name in ("actions", "restart", "backup_restore"):
        paths[name].write_text(json.dumps({"status": "PASS"}), encoding="utf-8-sig")
    paths["readiness"].write_text(json.dumps({"qualifiedWorkerEligible": True}))
    paths["technical_gates"].write_text(
        json.dumps(
            {
                "status": "TASK6_TECHNICAL_GATES_PASSED_ACTIVATION_HELD",
                "qualified_metadata_sha256": sha256(qualified_path),
                "actions_report": str(paths["actions"]),
                "actions_report_sha256": sha256(paths["actions"]),
                "restart_verification": str(paths["restart"]),
                "backup_restore_verification": str(paths["backup_restore"]),
                "readiness_verification": str(paths["readiness"]),
            }
        )
    )
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(
        json.dumps(
            {
                "decision": "AUTHORIZE_LOCAL_ACTIVATION",
                "run_id": "run",
                "database_target_sha256": held["database_target_sha256"],
                "qualified_metadata_sha256": sha256(qualified_path),
                "held_binding_sha256": sha256(held_path),
                "evidence": {
                    name: {"path": str(path), "sha256": sha256(path)}
                    for name, path in paths.items()
                },
            }
        )
    )
    environment.write_bytes(
        saved_environment.read_bytes().replace(b"HOLD=1", b"HOLD=0")
    )
    active_env = dict(env, SCORING_ACTIVATION_HOLD="0")
    details["sentinel-ai-api-1"]["Config"]["Env"] = [
        key + "=" + value for key, value in active_env.items()
    ]
    active = dict(
        held,
        status="QUALIFIED_ACTIVE",
        environment_sha256=sha256(environment),
        held_environment_file=str(saved_environment),
        environment_digests=dict(
            held["environment_digests"], api=environment_digest(active_env)
        ),
        activation_approval=str(approval_path),
        activation_approval_sha256=sha256(approval_path),
        held_binding=str(held_path),
        held_binding_sha256=sha256(held_path),
        qualified_metadata=str(qualified_path),
        qualified_metadata_sha256=sha256(qualified_path),
    )
    if wrong in (
        "approval",
        "qualified",
        "held_binding",
        "technical",
        "actions",
        "restart",
        "workload",
        "held_environment",
    ):
        target = {
            "approval": approval_path,
            "qualified": qualified_path,
            "held_binding": held_path,
            "technical": paths["technical_gates"],
            "actions": paths["actions"],
            "restart": paths["restart"],
            "workload": workload,
            "held_environment": saved_environment,
        }[wrong]
        target.write_text("tampered")
    if wrong == "credentials":
        environment.write_text(environment.read_text().replace("preserved", "changed"))
        active["environment_sha256"] = sha256(environment)
    if wrong in ("other_api_setting", "publisher_setting"):
        name = "api" if wrong == "other_api_setting" else "publisher"
        changed = dict(active_env if name == "api" else env, POSTGRES_POOL_MAX="100")
        details["sentinel-ai-" + name + "-1"]["Config"]["Env"] = [
            key + "=" + value for key, value in changed.items()
        ]
        active["environment_digests"][name] = environment_digest(changed)
    if wrong == "run":
        active["run_id"] = "other-run"
    if wrong == "image":
        active["images"] = dict(images, api="changed-image")
        details["sentinel-ai-api-1"]["Image"] = "changed-image"
    path = tmp_path / "active.json"
    path.write_text(json.dumps(active))
    if wrong:
        with pytest.raises(ValueError):
            verify_local_binding(
                path, details.__getitem__, original, allow_active=wrong != "no_opt_in"
            )
    else:
        actual, api = verify_local_binding(
            path, details.__getitem__, original, allow_active=True
        )
        assert actual == active and api["SCORING_ACTIVATION_HOLD"] == "0"
