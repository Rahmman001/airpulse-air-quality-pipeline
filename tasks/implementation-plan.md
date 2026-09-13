# Implementation Plan: AirPulse Streamlit to Decoupled Frontend Migration

This plan details the phased migration of the AirPulse user interface from Streamlit to a decoupled architecture consisting of a FastAPI backend and a modern responsive frontend.

---

## User Review Required

> [!IMPORTANT]
> **Zero Disruption to Existing Pipelines:** The migration touches only the presentation and serving layer (`app/`). The data ingestion (`ingestion/`), warehouse transformations (`dbt_project/`), and Dagster orchestration (`orchestration/`) remain completely unchanged and operational.

> [!TIP]
> **Single Container Production Model:** In production, FastAPI directly mounts and serves the pre-compiled frontend static bundle (`frontend/dist/`). There is no need for a separate Nginx or Node.js server in production.

---

## Phased Implementation Roadmap

### Phase 1: High-Performance FastAPI Backend (`app/api/`)
Build the REST API layer that wraps existing DuckDB queries with type-safe Pydantic models and in-memory TTL caching.

- **Tasks:**
  1. Add `fastapi` and `uvicorn` to `requirements.txt`.
  2. Create `app/api/main.py`: FastAPI application setup, CORS middleware, static file mounting.
  3. Create `app/api/routes.py`:
     - `GET /api/v1/health`
     - `GET /api/v1/kpis`
     - `GET /api/v1/locations`
     - `GET /api/v1/pollutants`
     - `GET /api/v1/aqi/latest`
     - `GET /api/v1/aqi/trends`
     - `GET /api/v1/alerts`
  4. Refactor `app/utils/data.py` to decouple from Streamlit caching (`st.cache_data`) into a pure Python in-memory TTL cache (e.g. `functools.lru_cache` or a simple timestamp dict), making it fully independent of Streamlit.
  5. Add `tests/test_api.py` to verify all endpoints return 200 with valid schema on both live DuckDB and Parquet snapshot fallbacks.

### Phase 2: Frontend Architecture & Foundation (`frontend/`)
Scaffold the frontend application with modern build tooling, design tokens, and base components.

- **Tasks:**
  1. Initialize `frontend/` using Vite + React + TypeScript (or lightweight Vanilla JS).
  2. Configure CSS design system matching `docs/design-document.md`:
     - EPA AQI semantic color scale (`#10B981`, `#FBBF24`, `#F97316`, `#EF4444`, `#A855F7`, `#881337`).
     - Dark slate theme layout tokens.
  3. Build persistent Navigation Header with Live Data Source status pill.
  4. Create shared API client module (`frontend/src/api.ts`) for data fetching.

### Phase 3: Overview Dashboard & Interactive Geospatial Map
Implement the primary operational dashboard view.

- **Tasks:**
  1. Implement Top-Line KPI Cards (Locations Monitored, Worst Current Reading, High-Risk Danger Zones, Data Freshness).
  2. Implement Interactive Map using Leaflet:
     - Dark CartoDB base tiles.
     - Custom SVG risk-colored circle markers sized proportionally to AQI.
     - Pulsing CSS animations for Hazardous stations (AQI > 200).
     - Interactive popup card showing location name, country, pollutant, AQI, and risk tier.
  3. Implement "Today's Most Polluted Locations" ranked leaderboard table.
  4. Implement "Unmonitored Locations" fallback table when stations have missing readings.

### Phase 4: City Trends & Operational Alerts Panel
Implement analytical drill-down and field dispatch action tools.

- **Tasks:**
  1. City Trends View:
     - Searchable Location and Pollutant select dropdowns.
     - Time-series line chart with horizontal dashed reference bands for EPA risk breakpoints.
     - Recent readings table with UTC timestamps and unit-normalized concentrations.
  2. Operational Alerts View:
     - Risk tier threshold slider/pills (Good through Hazardous, defaulting to Unhealthy >= 151 AQI).
     - Live count badge of compromised delivery hubs.
     - Alerts data table with flagged reading counts.
     - Browser-native "Download as CSV" export button.

### Phase 5: Verification, Streamlit Archival & Cleanup
Validate behavior, test across browsers, and cleanly archive legacy code.

- **Tasks:**
  1. Run automated test suite: `pytest tests/test_api.py` and `pytest tests/`.
  2. Verify all UI stories in browser.
  3. Move legacy Streamlit files to `app/legacy_streamlit/` or retain side-by-side during user transition.
  4. Update `README.md` and `PROJECT_MANUAL.md` with new run and build instructions (`fastapi dev` / `npm run dev`).

---

## Verification Plan

### Automated Tests
- **API Tests:**
  ```bash
  .venv/bin/pytest tests/test_api.py -v
  ```
  Validates every REST endpoint against live DuckDB and Parquet snapshot fallback modes.
- **Pipeline Integrity:**
  ```bash
  .venv/bin/pytest tests/
  ```
  Ensures zero regression across all 37 existing unit and integration tests.
- **Typecheck & Lint:**
  ```bash
  .venv/bin/ruff check .
  ```

### Manual & Visual Verification
1. Open dashboard in browser:
   - Check all 4 KPI cards populate with real numbers.
   - Interact with Leaflet map: pan, zoom, click stations, verify popup values match EPA tier colors.
2. Navigate to `/trends`:
   - Switch locations and pollutants, verify line chart renders with threshold bands.
3. Navigate to `/alerts`:
   - Drag slider from Moderate to Hazardous; verify row count updates dynamically.
   - Click "Download as CSV" and confirm valid CSV file downloads with correct headers and rows.
