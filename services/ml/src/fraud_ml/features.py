"""Sparkov v1 feature contract shared by chronological training and replay."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

FEATURE_VERSION = "sparkov-pit-v1"
NUMERIC_FEATURES = (
    "amount",
    "hour",
    "day_of_week",
    "prior_count_1h",
    "prior_count_24h",
    "prior_sum_24h",
    "prior_mean_24h",
)
FEATURE_ORDER = (*NUMERIC_FEATURES, "merchant_category")
EVENT_FIELDS = frozenset(
    {
        "schema_version",
        "data_origin",
        "event_id",
        "authorization_id",
        "occurred_at",
        "amount_minor",
        "currency",
        "card_token",
        "merchant_id",
        "merchant_category",
        "time_basis",
        "currency_basis",
    }
)
SOURCE_INPUT_COLUMNS = (
    "trans_date_trans_time",
    "cc_num",
    "merchant",
    "category",
    "amt",
    "trans_num",
)


def source_to_event(row: dict, key: bytes) -> dict:
    """Private source boundary: explicitly select fields; discard all labels/PII."""
    if len(key) < 32:
        raise ValueError("Pseudonymization requires at least 32 secret bytes")
    card = str(row["cc_num"])
    transaction = str(row["trans_num"])
    if not re.fullmatch(r"[0-9]+", card) or not re.fullmatch(
        r"[a-f0-9]{32}", transaction
    ):
        raise ValueError("Invalid source identity")
    amount = Decimal(str(row["amt"])) * 100
    if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
        raise ValueError("Invalid source amount")
    time = datetime.strptime(str(row["trans_date_trans_time"]), "%Y-%m-%d %H:%M:%S")
    event = {
        "schema_version": "2.0",
        "data_origin": "sparkov_replay",
        "event_id": str(
            uuid5(NAMESPACE_URL, "sentinel:sparkov:v1:event:" + transaction)
        ),
        "authorization_id": str(
            uuid5(NAMESPACE_URL, "sentinel:sparkov:v1:authorization:" + transaction)
        ),
        "occurred_at": time.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z"),
        "amount_minor": int(amount),
        "currency": "USD",
        "card_token": "card_"
        + hmac.new(key, card.encode("ascii"), hashlib.sha256).hexdigest(),
        "merchant_id": "merchant_"
        + hashlib.sha256(str(row["merchant"]).encode("utf-8")).hexdigest(),
        "merchant_category": str(row["category"]),
        "time_basis": "source_wall_clock_as_utc",
        "currency_basis": "simulation_assumption",
    }
    validate_event(event)
    return event


def validate_event(event: dict) -> datetime:
    if set(event) != EVENT_FIELDS:
        raise ValueError(
            "Unexpected or missing event fields; scoring never accepts a label"
        )
    for name, value in {
        "schema_version": "2.0",
        "data_origin": "sparkov_replay",
        "currency": "USD",
        "time_basis": "source_wall_clock_as_utc",
        "currency_basis": "simulation_assumption",
    }.items():
        if event[name] != value:
            raise ValueError("Incompatible replay contract")
    for name in ("event_id", "authorization_id"):
        UUID(event[name])
    if not re.fullmatch(r"card_[0-9a-f]{64}", event["card_token"]):
        raise ValueError("Invalid card token")
    if not re.fullmatch(r"merchant_[0-9a-f]{64}", event["merchant_id"]):
        raise ValueError("Invalid merchant identifier")
    category = event["merchant_category"]
    if (
        not isinstance(category, str)
        or not 1 <= len(category) <= 128
        or category != category.strip()
    ):
        raise ValueError("Invalid category")
    amount = event["amount_minor"]
    if type(amount) is not int or not 0 <= amount <= 9_007_199_254_740_991:
        raise ValueError("Invalid minor-unit amount")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", event["occurred_at"]):
        raise ValueError("Replay requires whole-second UTC simulation timestamps")
    return datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00"))


def features_from_prior(event: dict, prior: list[tuple[int, int]]) -> dict:
    """Pure reference implementation for stored history and parity checks."""
    moment = validate_event(event)
    second = int(moment.timestamp())
    history = [
        (time, amount) for time, amount in prior if second - 86400 <= time < second
    ]
    total = sum(amount for _, amount in history)
    return _features(
        event,
        moment,
        sum(time >= second - 3600 for time, _ in history),
        len(history),
        total,
    )


def _features(event, moment, count_hour, count_day, sum_day):
    return {
        "amount": event["amount_minor"] / 100.0,
        "hour": moment.hour,
        "day_of_week": moment.weekday(),
        "prior_count_1h": count_hour,
        "prior_count_24h": count_day,
        "prior_sum_24h": sum_day / 100.0,
        "prior_mean_24h": sum_day / (100.0 * count_day) if count_day else 0.0,
        "merchant_category": event["merchant_category"],
    }


@dataclass
class CardHistory:
    day: deque = field(default_factory=deque)
    hour: deque = field(default_factory=deque)
    pending: list = field(default_factory=list)
    current_second: int | None = None
    day_sum: int = 0
    current_ids: set = field(default_factory=set)


class FeatureStream:
    """Ordered attempt history. Call only after durable identity deduplication.

    Events sharing a timestamp stay pending until a later timestamp, so peers
    never influence each other. An out-of-order attempt requires replay/reset.
    """

    def __init__(self):
        self.cards: dict[str, CardHistory] = {}

    def transform(self, event: dict) -> dict:
        moment = validate_event(event)
        second = int(moment.timestamp())
        state = self.cards.setdefault(event["card_token"], CardHistory())
        if state.current_second is not None and second < state.current_second:
            raise ValueError("Out-of-order attempt")
        if second == state.current_second and event["event_id"] in state.current_ids:
            raise ValueError(
                "Duplicate attempt must be deduplicated before feature history"
            )
        if state.current_second != second:
            for amount in state.pending:
                state.day.append((state.current_second, amount))
                state.hour.append(state.current_second)
                state.day_sum += amount
            state.pending.clear()
            state.current_ids.clear()
            state.current_second = second
        while state.day and state.day[0][0] < second - 86400:
            state.day_sum -= state.day.popleft()[1]
        while state.hour and state.hour[0] < second - 3600:
            state.hour.popleft()
        result = _features(
            event, moment, len(state.hour), len(state.day), state.day_sum
        )
        state.pending.append(event["amount_minor"])
        state.current_ids.add(event["event_id"])
        return result
