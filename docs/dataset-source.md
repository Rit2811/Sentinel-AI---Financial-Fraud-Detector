# Active Dataset Record

Source: https://www.kaggle.com/datasets/kartik2112/fraud-detection

Exact handle: `kartik2112/fraud-detection/versions/1`.
On 2026-10-01 the Kaggle public metadata API returned version 1, dataset ID
817870, last update `2020-08-05T15:20:55.217Z`, license `CC0: Public Domain`.
Files were downloaded using `kagglehub.dataset_download` with the versioned
handle, into ignored `services/ml/data/kagglehub/`. No login was needed.
This is simulated Sparkov data, not issuer transactions or bank feedback.

| File | Bytes | Rows | Fraud | Cards |
| --- | ---: | ---: | ---: | ---: |
| `fraudTrain.csv` | 351238196 | 1296675 | 7506 | 983 |
| `fraudTest.csv` | 150354339 | 555719 | 2145 | 924 |

SHA-256:

```text
fraudTrain.csv fd7139200dbfcbed0b6742bbe05a4f1abce532c4fef20918228a651647a3e75d
fraudTest.csv  12d553ab19440c752d2531ee1af44bb64f12cc3d3839f1649f19e81c230545f0
```

Audit results: 23 source columns; no missing/nonfinite values, invalid binary
labels, negative/subcent amounts, duplicate transaction IDs or duplicate row
fingerprints. No cross-file transaction-ID overlap. There are 908 shared card
identities: expected for a later-time, known-card simulation, not an unseen-card
generalization experiment. Both files contain 693 merchants and 14 categories.
Fraud prevalence is 0.578865% in train and 0.385986% in test.

Source schema:

```text
Unnamed: 0, trans_date_trans_time, cc_num, merchant, category, amt,
first, last, gender, street, city, state, zip, lat, long, city_pop,
job, dob, trans_num, unix_time, merch_lat, merch_long, is_fraud
```

Train period: `2019-01-01 00:00:18` to `2020-06-21 12:13:37`.
Test period: `2020-06-21 12:14:25` to `2020-12-31 23:59:34`.
The supplied test is strictly later. Its aggregate labels were inspected only
for the source audit; no test predictions or selection metrics were computed.

The text clock equals the Unix clock plus seven calendar years in **every row**.
Observed text-minus-Unix offsets are 220924800 and 220838400 seconds; leap
years explain the variation. A calendar shift can collapse leap-day times onto
the same wall-clock date. The source train order contains one descending pair.
The chosen contract uses the text clock with an explicit UTC simulation
assumption and sorts it before history; Unix time is never a second predictor.
Same-time attempts cannot observe one another.

Repeatable audit: `python -m fraud_ml.sparkov_audit --data-dir <version-1-directory>`
from `services/ml`. It streams chunks, checks IDs exactly and uses row
fingerprints to rule out full duplicates. Any fingerprint candidate fails the
gate pending exact comparison. The full ignored aggregate report includes code
commit/hash, observed dtypes and checks in `artifacts/sparkov-v1/source-audit.json`.

Source fields excluded from inference and absent transaction attributes are
specified in the single source of truth, `feature-contract.md`.
