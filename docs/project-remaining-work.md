# Remaining Project Work

LATEST: [Mumbai deployment](mumbai-deployment.md) supersedes the deployment notes
below. Migration and full backup restoration passed; one-second peak acceptance
has NOT passed. Writers are stopped after renewed measured clock drift. Restore
stable clock sync, verify short checks, then BOTH ten-minute actual 1/5 TPS tests
and final qualified-deployment actions/review/readiness/recovery. Activation held.
The following local-storage checkpoint and older metrics are HISTORICAL.

Latest evidence: [storage and pipeline correction](storage-and-pipeline-correction.md).
The final candidate passed actual one-second 1 TPS/600s with 600/600 scored.
Paced 5 TPS/60s still failed with six expiries out of 300; full peak remains
unqualified. The machine has only one HDD and no available SSD target.
Existing owner model/policy/test approvals are sufficient; performance and
final deployment evidence remain the blockers. Candidate scoring is stopped.

## Completed Boundaries

Task 4: pinned Sparkov data, audit, safe point-in-time feature contract, shared
offline/replay implementation, chronological baselines and schema-v2 ingestion.
Task 5: selected sigmoid RF, approved Review 0.10/Block 0.25 policy, frozen
package/reference checks and one authorized passing reserved-test evaluation.
Actual sentinel: migrations 0001-0011 and verified populated backup restoration.
Prepared Task 6: durable history/snapshots, frozen worker, immutable decisions,
separate once-only simulated actions, authorized result/review APIs and failure
recovery tests. Actual-application Pass/Review/Block, review authorization,
duplicate delivery and same-run restart were also verified. Private credentials
and a stable application run identity exist. General activation is held because
actual persistent-database peak acceptance failed.

## Required to Finish Task 6

1. Pass the current one-second durable-decision deadline with ZERO expiries at
   normal load and for all ten minutes of 5 TPS; preserve parity and no late
   executions. The owner allowed a separate two-second diagnostic, but has not
   adopted a revised requirement. Its full 5 TPS test also failed.
2. Preserve qualified pins and existing run identity through further performance
   work. The owner-authorized single-commit publisher is implemented and recovery
   tested, but NOT qualified/promoted. It reduced nonempty publisher commits by
   48.8%; actual 5 TPS/30s improved 112 Scored/38 Expired to 147/3. Candidate
   isolated normal passed 60/60, isolated full peak FAILED 2940/60, and actual
   normal diagnostic FAILED 58/2. No reliable zero-expiry actual-storage rate
   is established for this candidate. Previous qualified deployment is restored,
   scoring stopped. Candidate full actual peak was not bypassed after failure.
   These older publisher candidate measurements are historical. The newer
   correction measured startup stream-audit commits, premature publication
   timeout/retry waiting and redundant preparation commits, and fixed those
   paths. Persistent-HDD durable-write/queue tails still caused the final peak
   failure; pool exhaustion and feature arithmetic are not dominant. Further
   progress needs a material storage/workload option and qualification, not
   another minor optimization loop. Actual normal capacity is now observed at
   1 TPS for ten minutes on the final candidate; its maximum rate is unknown.
   Never repeat the reserved test, relax durability or change limits silently.
   Earlier zero-expiry 2 TPS/60s evidence is a previous-build short diagnostic,
   not a proven maximum or revised requirement. Existing publisher approval is
   recorded and must not be requested again.
3. Activate only after actual-application normal and full peak gates pass;
   recheck readiness, original actions/review and same-run history preservation
   on the final qualified images. Actions/review and same-run restart passed
   again on 2026-10-04, but general activation is still blocked and scoring is
   stopped. Earlier passing isolated tmpfs peak evidence
   does not establish application disk performance.

Current evidence and performance limitations are in [the verification record](scoring-verification.md).
Existing owner approvals are sufficient; these are engineering/evidence gaps.

The separately authorized two-second diagnostic trial is recorded in
[its report](two-second-diagnostic-trial.md). A combined-commit worker passed
85 focused ML/recovery checks. On the actual application database, full
1 TPS/600s passed 600/600 with zero expiry, but full 5 TPS/600s failed:
2927 Scored, 73 Expired, exact scored parity and no late execution. Queue wait
and persistent-HDD WAL sync/write tails remain the measured bottleneck;
feature arithmetic is not dominant. Neither the current one-second nor the
diagnostic two-second peak gate is satisfied. No revised deadline or activation
is approved. The diagnostic worker is stopped, the previous qualified
API/publisher are restored, and public scoring readiness is HTTP 503. Further
work needs a material throughput/storage strategy with evidence, not another
minor optimization or an unapproved deadline increase.

## Task 7 Boundary

The supplied dataset-switch and Task 5/6 guides do not define a precise Task 7
acceptance plan. They explicitly defer feedback learning, drift monitoring and
adaptation. Do not treat a suggested next phase as an approved implementation.
The guide's G7 recovery/handoff gate belongs to Task 6; it is not Task 7.

A possible next phase is a separately specified confirmed-outcome feedback
contract, drift/performance monitoring and controlled model updates. Human
allow/reject decisions are NOT confirmed fraud labels. New models would need
independent evaluation, approval, versioning and rollback; automatic learning
from Pass/Review/Block is not acceptable. None of this is started in Task 6.

## Broader Roadmap Gaps

- A full transaction-score/review dashboard and optional live visual updates;
  the existing dashboard focuses on ingestion/stream activity.
- Full user authentication and role-based access; current result/review bearer
  tokens are only a localhost prototype authorization boundary.
- The separate four-model ensemble is development-only, not an approved
  deployed scorer. Its own policy/evaluation gates must remain independent.
- Adaptive imbalance handling and incremental updates need their own confirmed
  feedback, evaluation and controlled rollout contracts; current fitting and
  calibration do not constitute an adaptive live-learning system.
- Production deployment, operational security, real-bank validation and banking
  authorization integration are outside this synthetic local prototype.

These future items do not prevent finishing the approved Task 6 prototype and
must not be silently added to its completion criteria.
