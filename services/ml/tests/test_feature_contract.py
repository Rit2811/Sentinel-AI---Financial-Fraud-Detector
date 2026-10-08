"""Verify the existing frozen contract on generated fixtures, without fitting."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import numpy as np
import pandas as pd
import pytest

from fraud_ml.features import (
    EVENT_FIELDS,
    FEATURE_ORDER,
    NUMERIC_FEATURES,
    FeatureStream,
    features_from_prior,
    source_to_event,
    validate_event,
)
from fraud_ml.models import validate_features
from fraud_ml.serving import FrozenScorer

PIN = "1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696"
BUNDLE = (
    Path(__file__).resolve().parents[1]
    / "artifacts/frozen/random-forest/20261002T075558874195Z"
)


@pytest.fixture(scope="module")
def frozen_scorer():
    scorer = FrozenScorer(BUNDLE, PIN)
    scorer.verify_references()
    return scorer


def contract_events(namespace="unit"):
    # Hand-auditable lower-inclusive / upper-exclusive window boundaries.
    specifications = [
        (0, "a", 101),
        (0, "a", 199),
        (1, "c", 777),
        (1, "a", 0),
        (3599, "a", 300),
        (3600, "a", 100),
        (3601, "a", 201),
        (86399, "a", 199),
        (86400, "a", 999),
        (86401, "a", 777),
        (90000, "a", 222),
    ]
    return [
        {
            "schema_version": "2.0",
            "data_origin": "sparkov_replay",
            "event_id": str(
                uuid5(NAMESPACE_URL, f"contract-fixture:{namespace}:event:{index}")
            ),
            "authorization_id": str(
                uuid5(
                    NAMESPACE_URL, f"contract-fixture:{namespace}:authorization:{index}"
                )
            ),
            "occurred_at": (
                datetime(2020, 1, 6, tzinfo=UTC) + timedelta(seconds=offset)
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "amount_minor": amount,
            "currency": "USD",
            "card_token": "card_" + card * 64,
            "merchant_id": "merchant_" + "b" * 64,
            "merchant_category": "contract_fixture_unseen"
            if index % 2
            else "grocery_pos",
            "time_basis": "source_wall_clock_as_utc",
            "currency_basis": "simulation_assumption",
        }
        for index, (offset, card, amount) in enumerate(specifications)
    ]


def expected_features(events):
    # Independent contract oracle: inspect only earlier available event records.
    output = []
    for index, event in enumerate(events):
        moment = datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00"))
        day = [
            previous
            for previous in events[:index]
            if previous["card_token"] == event["card_token"]
            and timedelta(0)
            < moment
            - datetime.fromisoformat(previous["occurred_at"].replace("Z", "+00:00"))
            <= timedelta(days=1)
        ]
        hour = [
            previous
            for previous in day
            if moment
            - datetime.fromisoformat(previous["occurred_at"].replace("Z", "+00:00"))
            <= timedelta(hours=1)
        ]
        minor_sum = sum(previous["amount_minor"] for previous in day)
        output.append(
            {
                "amount": event["amount_minor"] / 100,
                "hour": moment.hour,
                "day_of_week": moment.weekday(),
                "prior_count_1h": len(hour),
                "prior_count_24h": len(day),
                "prior_sum_24h": minor_sum / 100,
                "prior_mean_24h": minor_sum / (100 * len(day)) if day else 0.0,
                "merchant_category": event["merchant_category"],
            }
        )
    return output


def test_shared_engines_match_independent_boundary_oracle():
    events = contract_events()
    expected = expected_features(events)
    stream, prior = FeatureStream(), {}
    for event, vector in zip(events, expected, strict=True):
        known = prior.setdefault(event["card_token"], [])
        assert stream.transform(event) == features_from_prior(event, known) == vector
        known.append((int(validate_event(event).timestamp()), event["amount_minor"]))
    assert [vector["prior_count_1h"] for vector in expected] == [
        0,
        0,
        0,
        2,
        3,
        4,
        3,
        0,
        1,
        2,
        2,
    ]
    assert [vector["prior_count_24h"] for vector in expected] == [
        0,
        0,
        0,
        2,
        3,
        4,
        5,
        6,
        7,
        6,
        5,
    ]
    assert [vector["prior_sum_24h"] for vector in expected] == [
        0,
        0,
        0,
        3,
        3,
        6,
        7,
        9.01,
        11,
        17.99,
        22.76,
    ]


def test_stored_reference_excludes_tied_future_and_stale_history():
    event = contract_events()[0]
    second = int(validate_event(event).timestamp())
    prior = [
        (second - 86401, 999999),
        (second - 86400, 123),
        (second - 3601, 201),
        (second - 3600, 177),
        (second, 888888),
        (second + 1, 999999),
    ]
    vector = features_from_prior(event, prior)
    assert vector["prior_count_1h"] == 1 and vector["prior_count_24h"] == 3
    assert vector["prior_sum_24h"] == 5.01 and vector["prior_mean_24h"] == 1.67


def test_frozen_preprocessing_matches_saved_transforms_without_refit(frozen_scorer):
    vectors = expected_features(contract_events())
    frame = pd.DataFrame(vectors, columns=FEATURE_ORDER)
    preprocessor = frozen_scorer.model.named_steps["preprocessor"]
    scaler = preprocessor.named_transformers_["numeric"]
    encoder = preprocessor.named_transformers_["category"]
    center, scale, categories = (
        scaler.center_.copy(),
        scaler.scale_.copy(),
        encoder.categories_[0].copy(),
    )
    transformed = preprocessor.transform(frame)
    assert transformed.shape == (11, 21)
    np.testing.assert_array_equal(
        transformed[:, :7], (frame[list(NUMERIC_FEATURES)].to_numpy() - center) / scale
    )
    known = list(categories).index("grocery_pos")
    for index, vector in enumerate(vectors):
        expected = np.zeros(14)
        if vector["merchant_category"] == "grocery_pos":
            expected[known] = 1
        np.testing.assert_array_equal(transformed[index, 7:], expected)
    float_frame = frame.copy()
    float_frame[list(NUMERIC_FEATURES)] = float_frame[list(NUMERIC_FEATURES)].astype(
        "float64"
    )
    np.testing.assert_array_equal(preprocessor.transform(float_frame), transformed)
    probability, actions = frozen_scorer.score(vectors)
    float_probability, float_actions = frozen_scorer.score(
        float_frame.to_dict("records")
    )
    np.testing.assert_allclose(probability, float_probability, rtol=1e-12, atol=1e-12)
    np.testing.assert_array_equal(actions, float_actions)
    np.testing.assert_array_equal(scaler.center_, center)
    np.testing.assert_array_equal(scaler.scale_, scale)
    np.testing.assert_array_equal(encoder.categories_[0], categories)


def test_frozen_score_matches_sequential_replay_and_cold_reconstruction(frozen_scorer):
    events = contract_events()
    vectors = expected_features(events)
    batch_probability, batch_actions = frozen_scorer.score(vectors)
    stream = FeatureStream()
    for index, event in enumerate(events):
        if index == 7:
            # Reconstruct from prior immutable attempts; process no event twice.
            stream = FeatureStream()
            for previous in events[:index]:
                stream.transform(previous)
        vector = stream.transform(event)
        assert vector == vectors[index]
        probability, actions = frozen_scorer.score([vector])
        assert probability[0] == pytest.approx(
            batch_probability[index], abs=1e-12, rel=1e-12
        )
        assert actions[0] == batch_actions[index]


@pytest.mark.parametrize(
    "timestamp",
    [
        "2020-01-06T00:00:00.001Z",
        "2020-01-06T00:00:00+00:00",
        "2020-02-30T00:00:00Z",
        "2020-01-06T24:00:00Z",
    ],
)
def test_event_time_rejects_milliseconds_offsets_and_invalid_calendar(timestamp):
    with pytest.raises(ValueError):
        validate_event(dict(contract_events()[0], occurred_at=timestamp))


def test_calendar_clock_units_and_feature_order(frozen_scorer):
    event = dict(contract_events()[0], occurred_at="2020-02-29T23:59:59Z")
    vector = features_from_prior(event, [])
    assert (vector["hour"], vector["day_of_week"]) == (23, 5)
    assert (
        tuple(vector) == tuple(frozen_scorer.manifest["feature_order"]) == FEATURE_ORDER
    )
    frame = pd.DataFrame([vector], columns=FEATURE_ORDER)
    validate_features(frame)
    with pytest.raises(ValueError):
        validate_features(frame[list(reversed(FEATURE_ORDER))])
    with pytest.raises(ValueError, match="label-free"):
        frozen_scorer.score([{**vector, "is_fraud": 1}])


def test_source_mapping_preserves_canonical_identity_and_decimal_cents():
    # Generated source fixture, not a row read from any dataset.
    row = {
        "trans_date_trans_time": "2020-02-29 23:59:59",
        "cc_num": "0001234567890123",
        "trans_num": "f" * 32,
        "merchant": "generated_contract_merchant",
        "category": "grocery_pos",
        "amt": "0.03",
        "unix_time": 0,
        "is_fraud": 1,
        "device": "unobserved",
    }
    event = source_to_event(row, b"generated-test-key-only" * 2)
    assert set(event) == EVENT_FIELDS
    assert event["amount_minor"] == 3
    assert event["occurred_at"] == "2020-02-29T23:59:59Z"
    assert event["event_id"] == str(
        uuid5(NAMESPACE_URL, "sentinel:sparkov:v1:event:" + row["trans_num"])
    )
    assert event["authorization_id"] == str(
        uuid5(NAMESPACE_URL, "sentinel:sparkov:v1:authorization:" + row["trans_num"])
    )
    assert row["cc_num"] not in str(event) and row["trans_num"] not in str(event)
    assert (
        source_to_event(
            dict(row, is_fraud=0, unix_time=999999), b"generated-test-key-only" * 2
        )
        == event
    )
