import json

from fraud_ml.trial_profile import event_profiles


def test_shared_batch_timings_are_correlated_with_expiry(tmp_path):
    records = [
        {"stage": "inference", "event_ids": ["a", "b"], "elapsed_ms": 50},
        {
            "stage": "assignment_commit_ack",
            "event_id": "b",
            "elapsed_ms": 10,
            "queue_ms": 2100,
        },
    ]
    (tmp_path / "worker-profile.log").write_text(
        json.dumps({"records": records}) + "\n"
    )
    result = event_profiles(
        {
            "event_database_timings": [
                {"event_id": "a", "status": "scored"},
                {"event_id": "b", "status": "expired"},
            ]
        },
        tmp_path,
    )
    assert result["outcomes"]["expired"]["stages"]["inference"]["maximum"] == 50
    assert (
        result["outcomes"]["expired"]["stages"]["accepted_to_assignment_queue"][
            "maximum"
        ]
        == 2100
    )
    assert "publisher_batch_commit_ack" not in result["events"][0]["stages"]
