# Sentinel AI web dashboard

Responsive React/Vite operational dashboard for the Sentinel AI interface. It reads non-sensitive authorization-ingestion and stream-processing aggregates from `GET /api/v1/dashboard`, refreshes automatically, and supports manual refresh and time-range selection. It does not claim fraud results because the offline ML ensemble is not connected to live API scoring.

Reusable UI lives in `src/components/`, visible copy lives in `src/content/`, API access lives in `src/api/`, server-state lifecycle lives in `src/hooks/`, response-to-view mapping lives in `src/adapters/`, chart/runtime settings live in `src/config/`, icons live in `src/icons/`, and all color values and design tokens live in `src/theme.js`.

The Docker image uses Node only as a build stage. A pinned Nginx runtime serves the compiled assets, applies security and cache headers, provides SPA fallback, and proxies `/api/` to the backend over the Compose network.
