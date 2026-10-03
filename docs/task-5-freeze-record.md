# RF Freeze Record

Recorded 2026-10-02. G2 approved; G3 package and clean-load verification passed.
Subsequently G4 was explicitly authorized and passed once; see
`task-5-final-test-record.md`. No test file was accessed by the freeze itself.
The historical freeze evidence below is preserved. Task 6 remains incomplete.

## Approval

Owner explicitly approved sigmoid RF, Review 0.10 / Block 0.25, for freeze.
The four-model development track is preserved; RF is the approved serving
candidate, not an active deployed scorer. See `task-5-operating-requirements.json`.

Approved evaluation criteria: observed fraud routed to Review/Block >=90%;
legitimate false-block rate <=0.1%; development/test review fraction scaled to
1 and 5 TPS <=20/hour, and to eight normal-traffic hours <=160/day. Report
confidence intervals; 95% routing is aspirational. Review is not confirmed fraud.
Approved operations: 1000 ms server acceptance through durable decision storage;
expired attempts never execute; retries only before expiry; timely Review awaits
an authorized team reviewer without a one-second human deadline; overflow stays
queued. Peak workload is 5 TPS for ten minutes. Live measurements remain missing.

Development evidence: 1427/1538 fraud routed (92.7828%); 201/257797 legitimate
blocked (0.0779683%); Wilson 95% false-block interval approximately
0.0679%-0.0895%. Estimated reviews/hour: 2.28 normal, 11.38 peak. Full evidence
and limitations remain in `task-5-decision-sheet.md`.

## Exact Package

Directory relative to repository:
`services/ml/artifacts/frozen/random-forest/20261002T075558874195Z`

Manifest SHA-256 (package identity):

```text
1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696
```

Hash procedure: SHA-256 of the exact UTF-8 manifest bytes, generated as sorted
JSON keys with compact separators. The manifest lists SHA-256 for each package
file and excludes itself. Keep this independently recorded pin; a checksum file
inside a modified package is not an independent trust root. Load trusted local
joblib files only. No secret HMAC key, source CSV or labels are packaged.

Contains fitted preprocessing/RF pipeline, sigmoid calibrator, approved policy,
feature contract and Python implementation, package source, dependency lock,
development provenance and safe reference cases. Baseline run:
`20261001T141637951841Z`; RF evidence: `20261002T073554111965Z`.

## Verification

Freeze command, from `services/ml`:

```powershell
.venv/Scripts/python.exe -m fraud_ml.freeze --evidence-run 20261002T073554111965Z --approval ../../docs/task-5-operating-requirements.json
```

Created a NEW, non-editable environment using the frozen project's `uv.lock`
with `uv sync --locked --offline --no-editable`; environment lives separately
at `services/ml/artifacts/verification-envs/rf-20261002`.
Installed 29 locked packages. Python 3.12.13, sklearn 1.9.0, numpy 2.5.2,
pandas 2.3.3, scipy 1.18.0, joblib 1.5.3; complete versions are in the manifest.

Verification used that environment's `python -I`, importing installed code from
its `Lib/site-packages`, not the editable repository. `FrozenScorer` verified
the external manifest pin, every listed file, executing inference/feature code
and exact runtime versions before model loading. Reference verification passed:

- Seven history cases: cold start, timestamp ties, one-hour/day boundaries.
- 39 label-free scoring cases, including all three action regions and unseen category.
- Probability comparison at absolute/relative tolerance 1e-12.
- Exact policy-boundary checks: below r -> Pass, r -> Review, b -> Block.

79 ML tests passed. Joblib's existing NumPy deprecation warnings remain.
These checks do not replace the final test, live parity, failure matrix or load test.

## Subsequent Gate

The owner subsequently authorized this exact checksum and its one evaluation
passed. The package is unchanged. See `task-5-final-test-record.md` for counts,
checksums, confidence intervals and limitations. Do not repeat or tune on the test.
