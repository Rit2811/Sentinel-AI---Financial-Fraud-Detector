# Remaining Project Work

## Completed Boundaries

Task 4: pinned Sparkov data, audit, safe point-in-time feature contract, shared
offline/replay implementation, chronological baselines and schema-v2 ingestion.
Task 5: selected sigmoid RF, approved Review 0.10/Block 0.25 policy, frozen
package/reference checks and one authorized passing reserved-test evaluation.
Actual sentinel: migrations 0001-0009 and verified populated backup restoration.
Prepared Task 6: durable history/snapshots, frozen worker, immutable decisions,
separate once-only simulated actions, authorized result/review APIs and failure
recovery tests. Actual-application Pass/Review/Block, review authorization,
duplicate delivery and same-run restart were also verified. Private credentials
and a stable application run identity exist. General activation is held because
actual persistent-database peak acceptance failed.

## Required to Finish Task 6

1. Pass the one-second durable-decision deadline with ZERO expiries at normal
   load and for all ten minutes of 5 TPS; preserve parity and no late executions.
2. Preserve the qualified ingestion image/evidence pins and existing run identity
   through further worker performance fixes. Its isolated normal/peak gates
   passed and runtime metadata was refreshed without changing credentials.
   Actual persistent-database peak qualification still failed. Never repeat
   the reserved model evaluation.
3. Activate only after actual-application normal and full peak gates pass;
   recheck readiness, original actions/review and same-run history preservation
   on the final qualified images. Earlier passing isolated tmpfs peak evidence
   does not establish application disk performance.

Current evidence and performance limitations are in [the verification record](task-6-verification-record.md).
Existing owner approvals are sufficient; these are engineering/evidence gaps.

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
