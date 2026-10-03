# Task 5 decision sheet

Current status: the approved RF package passed its one authorized final test.
See `task-5-final-test-record.md`. The development decisions below are historical;
no further selection or tuning on the reserved test is permitted.

Status on 2026-10-02: development evidence complete; owner approved the balanced
RF policy, operating choices and final-test criteria for freeze. Package freeze
and clean loading passed; reserved-test authorization remains pending. See
`task-5-freeze-record.md` for the exact package hash and approval evidence. Synthetic Sparkov
results are not real-bank performance evidence.

## Owner requirements

The owner supplied provisional targets in chat: 1 attempt/second normally,
5/second for peak testing, 20 reviews/hour, 160 per assumed eight-hour staffed
day, false blocks at most 0.1% of legitimate transactions, and at least 90%
of labelled fraud routed to Review or Block, preferably 95%. The machine-readable
record is `task-5-operating-requirements.json`. These targets are not approval
of a scorer, threshold pair or final-test run.

Owner subsequently approved a 1000 ms deadline, expiry with no execution,
pre-expiry retries, indefinitely pending human review by an authorized team
reviewer, queued overflow and ten-minute peak testing. Final-test criteria and
policy version are recorded in `task-5-operating-requirements.json`. Reserved-test
authorization remains separate and has not been granted.

## Development exposure

Reused Task 4 run `20261001T141637951841Z`; all 12 model/score artifact hashes
verified before deserialization. Existing fitted preprocessing/models were
not refitted. Development cache, shared feature version and split boundaries
match the Task 4 provenance. Only `fraudTrain.csv` is a development source.

| Use | Time period (UTC simulation clock) | Rows | Fraud |
|---|---|---:|---:|
| Base training | 2019-01-01 through 2019-11-29 19:37:11 | 778005 | 4585 |
| Component calibration | 2019-11-29 19:37:13 through 2019-12-31 | 146845 | 635 |
| Fusion weight fitting | January 2020 | 52202 | 343 |
| Fusion calibration | 2020-02-01 through 2020-03-06 07:15:17 | 60288 | 405 |
| Later comparison/selection | 2020-03-06 07:16:43 through 2020-06-21 12:13:37 | 259335 | 1538 |

Calendar boundaries were checked for class support before fitting. At least
100 of each class per fitting segment is a coverage guard, not an operating
requirement. Equal timestamps stay together. Calibration, weight fitting
and comparison keep natural prevalence. KNN's Task 4 training-only sampling
and the other models' class weights remain recorded in the exposure manifest.

Both sigmoid and isotonic mappings were fitted for all four baselines.
Two component-method variants each have independent fusion weight fitting
and both final fusion mappings: 12 candidates in total. Four-model weights
are nonnegative and sum to one; minimum weight 0.01 retains all components.
The optimizer minimizes natural-prevalence log loss with recorded L2
regularization 0.05 toward equal weights. These are development choices,
not business costs or approved policy defaults.

The score adapter uses installed sklearn 1.9.0's supported
`CalibratedClassifierCV(FrozenEstimator(...), ensemble=False)` with one
explicit all-row prediction split. The frozen adapter cannot fit a base
classifier; only the probability mapping learns from calibration labels.
No default shuffled fitting folds or base preprocessing refit are used.

## Candidate evidence

| Candidate | Average precision | Brier loss | Log loss | Single-row p95 ms |
|---|---:|---:|---:|---:|
| Raw Task 4 Random Forest | 0.950762 | 0.002152 | 0.013328 | See Task 4 report |
| Random Forest / sigmoid | 0.950762 | 0.000919 | 0.004224 | 75.10 |
| Random Forest / isotonic | 0.944334 | 0.000925 | 0.004229 | 37.65 |
| Four-model sigmoid components / sigmoid fusion | 0.921907 | 0.001059 | 0.005673 | 70.95 |
| Four-model sigmoid components / isotonic fusion | 0.910116 | 0.001054 | 0.006149 | 79.27 |

Average precision is sklearn's non-interpolated calculation, not trapezoidal
PR-AUC. All candidates use identical later comparison rows. Reports retain
20 reliability bins with counts and standalone reliability plots. Sigmoid RF
leads ranking and probability loss; it is now approved for package freeze, not
live activation. The owner subsequently requested two independent development
tracks: RF and four-model fusion. Both are retained; the selected balanced
proposal applies only to RF. See `model-tracks.md` for commands and isolation.

Latency measurements are 30 sequential, evenly spaced single-row requests,
one thread, in the existing local Windows/Python environment (four logical
CPUs reported). They include preprocessing, base scoring and calibration,
and complete four-model inference where applicable. They exclude queue,
history, network and database work. Separate candidate timings are noisy;
do not infer a reliable speed ranking or a passing 1/5 TPS workload test.

## Policy choices

Owner requested more headroom after reviewing the highest-capture option.
The owner selected the balanced option below after requesting more headroom.
Selection is recorded at 2026-10-02T06:53:26Z against options run
`20261002T063331225013Z`; this is not approval of outstanding operations or
reserved-test access. At that selection stage no frozen bundle existed; the later
explicit freeze approval/package is recorded in `task-5-freeze-record.md`.
All three use sigmoid-calibrated RF and exact full-precision probabilities.

| Option | Review r | Block b | Fraud routed | Wrong blocks / 10000 legitimate | Estimated normal reviews/h | Estimated peak reviews/h |
|---|---:|---:|---:|---:|---:|---:|
| Highest measured capture | 0.03985572410588941 | 0.16468846603087084 | 94.6034% | 9.9691 | 4.00 | 19.99 |
| Balanced, owner-selected proposal | 0.10 | 0.25 | 92.7828% | 7.7968 | 2.28 | 11.38 |
| More conservative | 0.25 | 0.50 | 90.9623% | 4.6548 | 1.64 | 8.19 |

| Balanced action | Fraud | Legitimate |
|---|---:|---:|
| Pass | 111 | 257460 |
| Review | 28 | 136 |
| Block | 1399 | 201 |

Balanced blocks 90.9623% of fraud and sends 1.8205% to Review; review is not
confirmed detection. Block precision is 87.4375%; review yield is 17.0732%.
Estimated staffed normal review day: 18.21. False-block denominator: 257797
legitimate attempts. Routed-fraud denominator: 1538 labelled fraud attempts.
Wilson 95% intervals: false blocks 6.79 to 8.95 per 10000 legitimate;
fraud routed 91.38% to 93.97%. Serial dependence and simulation limit these
descriptive intervals; they do not establish real-bank error bounds.

The highest-capture option's false-block interval reaches 11.26 per 10000,
above the owner's observed-rate limit. The conservative option's capture
interval extends below 90%. No evaluated candidate/pair reached the preferred
95% while meeting both peak Review and false-block targets. The search uses
score quantiles, explicit boundaries and critical cutoffs derived from the
provisional limits; it does not claim an exhaustive proof for all policies.

Workload estimates scale the development review fraction to specified
traffic. Source replay peak counts are separate columns in the CSV tables.
These estimates do not enforce future queue capacity or promise zero overflow.
Pass is p < r, Review is r <= p < b, Block is p >= b; displayed risk is 100*p.

## Evidence and commands

From `services/ml`:

```powershell
uv run fraud-calibration-develop --baseline-run 20261001T141637951841Z
uv run fraud-policy-options --evidence-run 20261002T061437063185Z --requirements ../../docs/task-5-operating-requirements.json
```

Completed calibration report: `services/ml/reports/sparkov-task5/20261002T061437063185Z/summary.json`.
Its `split-use.json` includes data/cache/code/lock hashes, training exposure,
runtime versions and commands; artifact `inventory.json` hashes every
calibrator, comparison-score array and report. Development artifacts are
NOT a frozen package. The earlier run `20261002T061203737637Z` stopped on an
adapter-interface error; it remains incomplete and is not selection evidence.
That error was fixed and the complete new run passed loaded/cached score
parity at 1e-12 absolute/relative tolerance. The reserved test stayed unscored.

Current assessed policy report: `services/ml/reports/sparkov-policy-options/20261002T063331225013Z/summary.json`.
It retains the owner requirement snapshot and checksum, evidence inventory
checksum, every assessed pair, counts, intervals, estimates and violations.
Earlier quantile-only options are retained separately, not overwritten.

## Approval boundary

Owner approval, operating choices, criteria, freeze and clean-load/reference
proof are now recorded in `task-5-freeze-record.md`. Next: obtain authorization
for its exact checksum, then evaluate the unchanged package once on the reserved test.
Task 6 activation must wait for a passing final-test report and actual-target
database readiness. No drift, feedback learning or retraining is authorized.

Technical method references: [sklearn calibration](https://scikit-learn.org/stable/modules/calibration.html),
[FrozenEstimator](https://scikit-learn.org/stable/modules/generated/sklearn.frozen.FrozenEstimator.html).
