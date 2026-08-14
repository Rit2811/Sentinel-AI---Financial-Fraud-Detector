# Repository scripts

`verify.ps1` (Windows) and `verify.sh` (Bash environments) implement `make verify`. They run backend and frontend static checks and tests, validate and start the four-service stack, cycle Task 3 migrations down/up, run real-PostgreSQL concurrency and rollback tests, perform endpoint smoke and truthful-readiness failure checks, restart the stack, inspect bounded logs, and shut it down without deleting volumes.

The matching `bootstrap` scripts install locked dependencies. The `clean` scripts remove only explicitly listed generated dependency/cache/build directories beneath the repository and never touch Docker volumes.
