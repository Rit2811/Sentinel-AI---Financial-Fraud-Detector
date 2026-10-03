# Sparkov Point-in-Time Contract

Contract: `sparkov-pit-v1`. Event schema: `2.0`, origin `sparkov_replay`.
Source: `kartik2112/fraud-detection/versions/1`. This is simulated data.
The source audit and pinned hashes are the prerequisite for using this contract.

Clock audit: the text timestamp equals `unix_time` interpreted as an epoch
timestamp plus seven **calendar years**. The observed offsets are 220924800
and 220838400 seconds because of leap years. Never correct using a constant
seconds offset. Training-file order has one descending pair; sort explicitly.

## Source Mapping

| Source | Event use | Scorer use |
| --- | --- | --- |
| `trans_date_trans_time` | `occurred_at`, source wall clock interpreted as UTC | hour, Monday=0 weekday, history cutoff |
| `amt` | exact decimal cents in `amount_minor` | amount in major units |
| `category` | `merchant_category`, original string | training-fitted one-hot category |
| `merchant` | `merchant_` + SHA-256 of exact UTF-8 string | not a predictor in v1 |
| `cc_num` | `card_` + HMAC-SHA256 using local secret, string input | history join only, never predictor |
| `trans_num` | UUIDv5 URL namespace, prefixes below | identity only, never predictor |
| `unix_time` | source-audit clock comparison only | excluded |
| `is_fraud` | separate offline label lane only | forbidden |
| export index | ignored | excluded |
| names, address, demographics, coordinates | private source only | excluded |

No observed currency or timezone is supplied. The demo assumes USD with 100
minor units and treats the source wall clock as UTC for consistent ordering,
not as a claim about the original location's timezone. Every event carries
`currency_basis=simulation_assumption` and
`time_basis=source_wall_clock_as_utc`. Neither is learned by the model.

There is no observed channel, entry mode, device, terminal, account token,
balance or merchant country. Even categories containing `net` or `pos` do not
authorize populating these fields. Geography is excluded from this first
contract; no distance/location availability claims are made.

UUIDv5 input prefixes are `sentinel:sparkov:v1:event:` and
`sentinel:sparkov:v1:authorization:`, followed by validated lowercase
`trans_num`. The raw transaction identifier never leaves the source adapter.
Keep the HMAC key in ignored `secrets/replay-hmac.key`, at least 32 bytes.
Persist it across replay runs. Never put it in artifacts, logs or Git.

## Ordered Features

| Position | Feature | Type / units | Missing rule |
| --- | --- | --- | --- |
| 1 | `amount` | float64, assumed USD major units | reject missing/nonfinite/negative/subcent |
| 2 | `hour` | integer, 0-23 in the simulation clock | reject invalid time |
| 3 | `day_of_week` | integer, Monday=0 through Sunday=6 | reject invalid time |
| 4 | `prior_count_1h` | integer, prior attempts | zero for empty history |
| 5 | `prior_count_24h` | integer, prior attempts | zero for empty history |
| 6 | `prior_sum_24h` | float64, major units | zero for empty history |
| 7 | `prior_mean_24h` | float64, major units | zero for empty history |
| 8 | `merchant_category` | string, 1-128 characters, no surrounding whitespace | reject empty; unseen encoded all-zero |

The event feature engine emits integer-valued clock/count fields. The cached
numeric training matrix stores all seven numeric columns as float64 without
changing those values; the same preprocessing is applied during scoring.

History windows are `[event_time - window, event_time)`. Compute features
before adding the current attempt. Same-second events do not see each other.
All earlier known unique attempts count, regardless of later demo action or
outcome. Rejected malformed payloads and duplicate retries do not count.
Amounts accumulate as integer cents, then convert to major units once.

Order historical events by canonical text time, then transaction identifier;
do not trust file order. Ties cannot cross development partition boundaries.
Out-of-order live replay requires rebuilding history in event-time order;
do not silently include a future event. Persistent deduplication must precede
history updates. `FeatureStream` also rejects same-time duplicate IDs and
per-card backwards time; it is not a replacement for database idempotency.

`features.py` is the implementation: source adapter -> validated safe event ->
`FeatureStream.transform`. `features_from_prior` independently computes the
same features from stored earlier attempts for parity tests. Labels are read
separately and are never accepted by either feature API.

## Development and Test

After the audit verifies chronology, reserve the entire supplied
`fraudTest.csv` as the new locked test. Source integrity and aggregate label
counts may be audited; no test predictions or selection metrics are permitted
before Task 5 freezes model and policy. No previous model/test is reused.

Sort `fraudTrain.csv`, then allocate 60% fit, 20% future calibration, 20% future
validation, shifting cuts to preserve equal-time groups. Build history across
these boundaries without outcomes. Fit encoders, scalers, class weighting and
any sampling using fit data only. Calibration is a later Task 5 stage.

Task 5 still requires owner-selected Review capacity and legitimate-block
constraints, then frozen versions, checksums and exactly one test evaluation.
Task 6 must use that frozen compatible bundle and persist one action per
authorization. Missing scores are unavailable/pending, never an implicit Pass.
