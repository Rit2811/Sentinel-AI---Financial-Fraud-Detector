# Repository Scripts

- `new-teammate-env.ps1` generates a private independent configuration and refuses
  to overwrite existing credentials.
- `teammate.ps1` builds/starts/checks/stops the dedicated `sentinel-team` Docker
  profile; see [teammate setup](../docs/teammate-setup.md).
- `bootstrap` installs locked host development dependencies.
- `new-local-secret.ps1` generates one local secret for manual use.

The owner's laptop provisioning/activation scripts are bound to that deployment
and are not teammate bootstrap tools. General legacy `verify` scripts manage
their own stacks and migration tests; inspect their targets before use. Use
explicit isolated fixtures for destructive reset/rollback/recovery tests.
Cleanup scripts must never delete retained Docker application volumes.
