import pytest

from fraud_ml.connected_benchmark import (
    paced_due,
    generated_event,
    guard_application_urls,
    latency_summary,
    main,
)
from fraud_ml.features import FeatureStream


def test_pacing_never_catches_up_after_a_slow_slot():
    assert paced_due(100, 0, 5, None) == 100
    assert paced_due(100, 1, 5, 100) == 100.2
    assert paced_due(100, 2, 5, 101) == 101.2


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
