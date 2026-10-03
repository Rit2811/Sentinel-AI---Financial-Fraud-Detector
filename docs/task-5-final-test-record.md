# Authorized Final Test

## Status

Task 5 gates passed for sigmoid-calibrated Random Forest only. The owner
authorized one evaluation of the exact frozen package in
`task-5-reserved-test-authorization.json`. Evaluation completed once at
2026-10-02T12:33:51Z. No fitting, calibration changes or threshold tuning occurred.
The independent four-model development track remains unchanged and is not approved
for serving. A model-quality pass does not complete Task 6 or activate a worker.

## Exact Evidence

Frozen manifest SHA-256:
`1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696`

Report: `services/ml/reports/final-test/1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696/report.json`

Report SHA-256:
`abdffc8e3e90bfe040c72577de795e48a7d514e6de470adcf7dfb9732a2e18c2`

The frozen manifest remains unchanged. Worker activation-report verification
independently recomputed the approved checks and returned PASS. Seven history
references, 39 scoring references and exact policy boundaries passed again.
The package retains its historical freeze-time status; the separate immutable
report is the subsequent gate evidence, not a rewritten model package.

## Results

All 555,719 reserved transactions were evaluated: 2,145 fraud and 553,574 legitimate.
Review threshold 0.10; Block threshold 0.25.

| Actual label | Pass | Review | Block |
| --- | ---: | ---: | ---: |
| Fraud | 184 | 55 | 1,906 |
| Legitimate | 552,921 | 243 | 410 |

| Approved check | Measured | Limit | Result |
| --- | ---: | ---: | --- |
| Fraud routed to Review/Block | 91.4219% | >=90% | PASS |
| Legitimate falsely blocked | 0.074064% | <=0.1% | PASS |
| Estimated reviews/hour at 1 TPS | 1.9305 | <=20 | PASS |
| Estimated reviews/hour at 5 TPS | 9.6524 | <=20 | PASS |
| Estimated reviews/8-hour normal day | 15.4438 | <=160 | PASS |

False-block Wilson 95% interval: 0.067236%-0.081585%.
Fraud-routing Wilson 95% interval: 90.1615%-92.5342%.
Average precision 0.928120; ROC AUC 0.996450; Brier score 0.000788808.
The aspirational 95% routing target was not met; it was not an acceptance gate.

## Method and Limits

Both CSV hashes were verified against the original source audit. The shared
frozen feature implementation processed chronological events, warming history
with 2,773 earlier training attempts in the initial 24-hour lookback. Labels were
removed before feature generation and passed only to offline metrics. Card
numbers were used only inside the private source-to-HMAC boundary; neither raw
identifiers nor transaction-level labels/predictions were written to application
storage or logs. Only aggregate results and a prediction checksum were persisted.

The evaluator creates an exclusive package-specific evidence directory before
test access and refuses another invocation. Do not delete it to rerun or tune.
Generated evidence remains Git-ignored. This record contains no private data.

This is synthetic-data evidence. Review means routed for investigation, not
confirmed detection. Review workload is an expected rate scaled from this sample,
not an actual hourly arrival guarantee. Binomial intervals are descriptive and
may understate uncertainty for correlated transactions. Real-world performance,
connected throughput and deadline compliance remain Task 6 concerns.
