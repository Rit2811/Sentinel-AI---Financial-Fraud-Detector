# Operational Dashboard

React/Vite dashboard for non-sensitive authorization-ingestion and stream activity.
It refreshes aggregates from `GET /api/v1/dashboard` and supports range selection.
Scoring/review routes are provided by the backend, but the dashboard is not a
complete analyst case-management interface.

Use [teammate setup](../docs/teammate-setup.md) for Docker operation. API proxy
settings are server-side; PostgreSQL/Redis passwords and result/review tokens must
never be embedded in React builds. The teammate profile targets `http://api:8000`
on its private Compose network.
