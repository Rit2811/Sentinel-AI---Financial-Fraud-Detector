# Repository scripts

`verify.ps1` (Windows) and `verify.sh` (Bash environments) implement `make verify`. They run static checks and tests, validate and start the four-service stack, perform smoke and truthful-readiness failure checks, restart it, inspect bounded logs, and shut it down without deleting volumes.

The matching `bootstrap` scripts install locked dependencies. The `clean` scripts remove only explicitly listed generated dependency/cache/build directories beneath the repository and never touch Docker volumes.
