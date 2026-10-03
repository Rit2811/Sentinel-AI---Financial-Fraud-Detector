import json
from datetime import datetime

import pytest
import pandas as pd

from fraud_ml.data import SOURCE_HASHES, load_key, verify_audit, verify_source
from fraud_ml.features import (
    EVENT_FIELDS,
    FEATURE_ORDER,
    FeatureStream,
    features_from_prior,
    source_to_event,
    validate_event,
)
from fraud_ml.sparkov_audit import SOURCE_COLUMNS, audit_file


def source(index=1, time="2019-01-01 00:00:00", amount="10.00"):
    return {
        "trans_date_trans_time": time,
        "cc_num": "0001234567890123",
        "merchant": "synthetic_merchant",
        "category": "shopping_net",
        "amt": amount,
        "trans_num": f"{index:032x}",
        "is_fraud": 1,
        "first": "Private",
        "street": "Private address",
    }


def event(index=1, time="2019-01-01 00:00:00", amount="10.00"):
    return source_to_event(source(index, time, amount), b"x" * 32)


def test_source_adapter_excludes_labels_and_private_fields():
    row = source()
    first = source_to_event(row, b"x" * 32)
    row.update(is_fraud=0, first="Changed", street="Changed")
    assert source_to_event(row, b"x" * 32) == first
    assert set(first) == EVENT_FIELDS
    assert row["cc_num"] not in json.dumps(first)
    assert first["amount_minor"] == 1000
    assert "channel" not in first
    assert source_to_event(row, b"y" * 32)["card_token"] != first["card_token"]
    assert source_to_event(row, b"y" * 32)["event_id"] == first["event_id"]


@pytest.mark.parametrize(
    "field", ["is_fraud", "cc_num", "channel", "balance", "device_token"]
)
def test_inference_event_rejects_extra_fields(field):
    with pytest.raises(ValueError):
        validate_event({**event(), field: 0})


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1", "0.001"])
def test_invalid_source_amount_is_rejected(amount):
    with pytest.raises(ValueError):
        event(amount=amount)


def test_strict_prior_windows_ties_and_replay_parity():
    stream = FeatureStream()
    history = []
    events = [
        event(1),
        event(2, amount="20"),
        event(3, "2019-01-01 01:00:00", "30"),
        event(4, "2019-01-02 00:00:00", "40"),
        event(5, "2019-01-02 00:00:01", "50"),
    ]
    results = []
    for attempt in events:
        result = stream.transform(attempt)
        assert result == features_from_prior(attempt, history)
        assert tuple(result) == FEATURE_ORDER
        history.append(
            (
                int(datetime.fromisoformat(attempt["occurred_at"]).timestamp()),
                attempt["amount_minor"],
            )
        )
        results.append(result)
    assert results[0]["prior_count_24h"] == results[1]["prior_count_24h"] == 0
    assert results[2]["prior_count_1h"] == 2
    assert results[2]["prior_sum_24h"] == 30
    assert results[3]["prior_count_24h"] == 3
    assert results[4]["prior_count_24h"] == 2


def test_reference_history_excludes_future_and_current():
    attempt = event()
    second = int(datetime.fromisoformat(attempt["occurred_at"]).timestamp())
    assert features_from_prior(
        attempt, [(second, 900), (second + 1, 900)]
    ) == features_from_prior(attempt, [])


def test_stream_rejects_duplicates_and_backwards_time():
    stream = FeatureStream()
    stream.transform(event(2, "2019-01-01 01:00:00"))
    with pytest.raises(ValueError, match="Duplicate"):
        stream.transform(event(2, "2019-01-01 01:00:00"))
    with pytest.raises(ValueError, match="Out-of-order"):
        stream.transform(event(1))


def test_card_histories_are_separate():
    stream = FeatureStream()
    stream.transform(event())
    another = source(2, "2019-01-01 00:00:01")
    another["cc_num"] = "1111222233334444"
    assert stream.transform(source_to_event(another, b"x" * 32))["prior_count_24h"] == 0


def test_secret_creation_is_stable_and_not_replaced(tmp_path):
    path = tmp_path / "key"
    key = load_key(path, create=True)
    assert len(key) == 32
    assert key == load_key(path, create=True)


def test_mutated_source_fails_before_features(tmp_path):
    path = tmp_path / "fraudTrain.csv"
    path.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="pinned"):
        verify_source(path)


def test_failed_audit_prevents_training(tmp_path):
    path = tmp_path / "audit.json"
    path.write_text(json.dumps({"status": "FAIL"}), encoding="utf-8")
    with pytest.raises(ValueError, match="passing"):
        verify_audit(path)
    assert set(SOURCE_HASHES) == {"fraudTrain.csv", "fraudTest.csv"}


def test_source_audit_resolves_calendar_shift_and_fails_bad_labels(tmp_path):
    row = {name: "private_placeholder" for name in SOURCE_COLUMNS}
    row.update(source())
    row.update({"Unnamed: 0": 0, "unix_time": 1325376000, "amt": 10, "is_fraud": 0})
    path = tmp_path / "sample.csv"
    pd.DataFrame([row], columns=SOURCE_COLUMNS).to_csv(path, index=False)
    report, _, _, _, failures = audit_file(path)
    assert failures == []
    assert report["checks"]["calendar_shift_mismatches"] == 0
    assert "private_placeholder" not in json.dumps(report)
    row["is_fraud"] = 2
    row["unix_time"] += 1
    pd.DataFrame([row, row], columns=SOURCE_COLUMNS).to_csv(path, index=False)
    report, _, _, _, failures = audit_file(path)
    assert report["checks"]["invalid_labels"] == 2
    assert report["checks"]["calendar_shift_mismatches"] == 2
    assert report["checks"]["duplicate_transaction_ids"] == 1
    assert failures
