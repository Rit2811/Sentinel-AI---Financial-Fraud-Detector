# Tests

Backend tests live under `backend/tests`, frontend tests under `frontend/src`,
and Python feature/scoring tests under `services/ml/tests`. Database/Redis
integration tests require the explicitly guarded isolated fixture stack.

Never run reset, truncate, rollback or recovery-fixture setup against application
data. Keep test results private; runtime startup instructions are in
[teammate setup](../docs/teammate-setup.md).
