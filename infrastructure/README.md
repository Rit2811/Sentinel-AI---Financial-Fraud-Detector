# Local infrastructure

`compose.yaml` defines the isolated `sentinel-ai` development stack: API, web, PostgreSQL, and Redis. All published ports bind only to `127.0.0.1`; project-specific volumes and the default project network remain separate from UniHub.

This is local infrastructure proof only, not production orchestration.
