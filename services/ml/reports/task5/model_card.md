# Task 5 model card

Status: Validation-only development; locked test not opened.

## Purpose

Offline research demonstration of calibrated fraud probabilities and
Allow/Review/Block policy analysis on the historical anonymized ULB benchmark.
It is not approved for live payments, customer decisions or issuer loss claims.

## Data and leakage controls

- Dataset SHA-256: 76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89
- Training and validation only were used in this development report.
- The locked test contains 56962 rows and remains unopened.

## Models and fusion

All four Task 4 models are calibrated from training-only out-of-fold scores.
The validation-selected fusion candidate is weighted_soft_vote. SVM margins are
never used directly as probabilities.

## Decision policy

Three measured profiles are available. The current recommendation is
Balanced Demo, but no policy is frozen until owner approval M4.

## Limitations

The ULB dataset is historical, anonymized and highly imbalanced. It does not
represent current issuer populations, card-present/card-not-present behavior,
review capacity, customer friction, confirmed loss, fairness groups or live
latency. Amount evidence is a benchmark scenario only.

## Final test

Not run. This section must only be completed after freeze approval M5 and
separate one-time test authorization M6. No post-test tuning is permitted.
