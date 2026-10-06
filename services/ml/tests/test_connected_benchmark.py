import pytest

from fraud_ml.connected_benchmark import (
    clocks_consistent,
    paced_due,
    generated_event,
    guard_application_urls,
    latency_summary,
    main,
)
from fraud_ml.features import FeatureStream
from fraud_ml.database import database_target_sha256


def test_pacing_never_catches_up_after_a_slow_slot():
    assert paced_due(100, 0, 5, None) == 100
    assert paced_due(100, 1, 5, 100) == 100.2
    assert paced_due(100, 2, 5, 101) == 101.2


def test_clock_check_accounts_for_network_uncertainty_without_correcting_time():
    assert clocks_consistent([{"midpoint_offset_ms": 30, "uncertainty_ms": 20}])
    for offset in (-460, 460):
        assert not clocks_consistent(
            [{"midpoint_offset_ms": offset, "uncertainty_ms": 20}]
        )
    assert not clocks_consistent([])


def test_docker_workload_uses_only_the_shared_label_free_contract():
    stream = FeatureStream()
    for index in range(50):
        event = generated_event(index)
        features = stream.transform(event)
        assert "is_fraud" not in event and "cc_num" not in event
        assert "channel" not in event and "device_token" not in event
        assert features["prior_count_24h"] == index // 20


def test_controller_refuses_an_application_endpoint():
    with pytest.raises(ValueError, match="isolated API"):
        main(
            [
                "--bundle",
                "unused",
                "--bundle-sha256",
                "f" * 64,
                "--run-id",
                "985d24e4-42be-4e3b-bb9a-ad43664ca053",
                "--base",
                "http://127.0.0.1:18000",
                "--tps",
                "5",
                "--seconds",
                "600",
            ]
        )


def test_latency_statistics_keep_over_deadline_observations_visible():
    assert latency_summary([])["maximum"] is None
    stats = latency_summary([100, 200, 1500])
    assert stats["maximum"] == 1500 and stats["over_1000"] == 1


def test_application_measurement_has_distinct_workload_card_identities():
    a, b = generated_event(0, "one"), generated_event(0, "two")
    assert a["card_token"] != b["card_token"]
    assert a["card_token"] == generated_event(20, "one")["card_token"]
    stream = FeatureStream()
    for index in range(50):
        features = stream.transform(generated_event(index, "one"))
        assert features["prior_count_24h"] == index // 20


@pytest.mark.parametrize(
    "pg,rd",
    [
        (
            "postgresql://127.0.0.1:25432/sentinel_task4_test",
            "redis://127.0.0.1:16379/0",
        ),
        ("postgresql://remote:15432/sentinel", "redis://127.0.0.1:16379/0"),
        ("postgresql://127.0.0.1:15432/other", "redis://127.0.0.1:16379/0"),
        ("postgresql://127.0.0.1:15432/sentinel", "redis://127.0.0.1:16379/1"),
        (
            "postgresql://127.0.0.1:15432/sentinel?options=anything",
            "redis://127.0.0.1:16379/0",
        ),
    ],
)
def test_application_guard_cannot_redirect_to_other_storage(pg, rd):
    with pytest.raises(ValueError, match="confirmed loopback"):
        guard_application_urls(pg, rd)


def test_application_guard_allows_only_confirmed_target():
    guard_application_urls(
        "postgresql://127.0.0.1:15432/sentinel",
        "redis://127.0.0.1:16379/0",
    )


def test_cloud_controller_requires_pin_verified_tls_and_original_redis():
    pg = "postgresql://postgres.example:placeholder@aws-0-example.pooler.supabase.com:5432/postgres?sslmode=verify-full&sslrootcert=/run/secrets/supabase-root.crt"
    rd = "redis://redis:6379/0"
    pin = database_target_sha256(pg)
    guard_application_urls(pg, rd, True, pin)
    for url, redis, docker, target in (
        (pg, rd, True, "f" * 64),
        (pg, rd, False, pin),
        (pg.replace("verify-full", "require"), rd, True, pin),
        (pg, "redis://other:6379/0", True, pin),
        (pg.replace("postgres.example", "postgres.other"), rd, True, pin),
    ):
        with pytest.raises(ValueError):
            guard_application_urls(url, redis, docker, target)


def test_docker_application_target_is_explicit_and_not_an_isolated_alias():
    pg, rd = "postgresql://postgres:5432/sentinel", "redis://redis:6379/0"
    guard_application_urls(pg, rd, docker_client=True)
    with pytest.raises(ValueError):
        guard_application_urls(pg, rd)
    with pytest.raises(ValueError):
        guard_application_urls(
            "postgresql://postgres:5432/sentinel_task4_test", rd, docker_client=True
        )
    with pytest.raises(ValueError):
        guard_application_urls(pg, "redis://127.0.0.1:16379/0", docker_client=True)


def test_docker_client_cannot_bypass_explicit_application_mode():
    with pytest.raises(ValueError, match="explicit application mode"):
        main(
            [
                "--application-docker-client",
                "--bundle",
                "unused",
                "--bundle-sha256",
                "f" * 64,
                "--run-id",
                "985d24e4-42be-4e3b-bb9a-ad43664ca053",
                "--base",
                "http://sentinel-ai-api-1:8000",
                "--tps",
                "5",
                "--seconds",
                "600",
            ]
        )
