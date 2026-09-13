# PRD: AirPulse Frontend Migration (Streamlit to Modern Decoupled Web App)

## 1. Introduction / Overview

AirPulse is an enterprise-grade Air Quality Risk Intelligence platform originally built for Meridian Logistics' operations dispatchers. It monitors global ambient air quality (PM2.5, PM10, O3, NO2, CO, SO2) from OpenAQ, standardizes measurements into US EPA Air Quality Index (AQI) values, and surfaces operational risk across supply chain delivery hubs.

The existing user interface is implemented as a monolithic Streamlit application (`app/streamlit_app.py`, `app/pages/1_City_Trends.py`, `app/pages/2_Alerts.py`). While Streamlit provided rapid initial prototyping, it suffers from significant structural limitations:
- **Execution Model:** Streamlit re-executes Python code from top to bottom on every user interaction, causing noticeable latency and UI jitter.
- **Geospatial & Charting Interactivity:** PyDeck and Altair integrations within Streamlit offer rigid styling and cannot support smooth pan/zoom, custom vector pin styling, or dynamic filtering without round-trip re-runs.
- **Deployment & Scaling Bottlenecks:** Tight coupling of UI rendering and Python database queries prevents static asset edge caching, CDN delivery, and independent horizontal scaling.

This project migrates the presentation layer to a modern, decoupled architecture: a high-performance, lightweight backend API (FastAPI) paired with an optimized, responsive frontend (Vite + React / TypeScript).

---

## 2. Goals

- **Performance:** Sub-200ms API response time for all analytical queries; sub-1.0s initial visual dashboard load time.
- **Snappy Interactivity:** Zero full-page reloads on filter changes, metric switches, or location selections.
- **Geospatial Intelligence:** Interactive global map with color-coded risk pins, clustering, and rich tooltip inspectors.
- **Operational Utility:** Dedicated alerts panel with instant risk-tier threshold filtering and one-click CSV export for dispatch teams.
- **Zero Ingestion Disruption:** Seamless reuse of the existing DuckDB mart (`mart.fact_daily_city_aqi`, `mart.fact_air_quality_hourly`, `mart.dim_location`) and fallback to committed Gold Parquet snapshots (`data/gold_snapshot/`).
- **Lean Footprint (Ponytail Principle):** Single-command dev workflow, minimal external dependencies, and single-container deployment (FastAPI serving static SPA assets in production).

---

## 3. User Stories

### US-001: Top-Line Operational KPIs & Freshness Banner
**Description:** As an operations dispatcher, I want to see real-time summary KPIs and pipeline data freshness upon landing so that I can immediately gauge global risk and data reliability.

**Acceptance Criteria:**
- [ ] Displays 4 metric cards: Total Monitored Locations, Worst Current Reading (AQI + location + pollutant), High-Risk Zones Count (>150 AQI), and Pipeline Data Through Date.
- [ ] Shows clear status banner if reading from committed Gold Parquet snapshot instead of live DuckDB.
- [ ] If no recent AQI readings exist, renders a clean fallback table of unmonitored locations.
- [ ] Typecheck/lint passes.
- [ ] Verify in browser using dev-browser skill.

---

### US-002: Interactive Geospatial Risk Map
**Description:** As a logistics planner, I want an interactive global map displaying all active monitoring stations color-coded by EPA risk tier so that I can visually pinpoint hazardous delivery zones.

**Acceptance Criteria:**
- [ ] Map renders all locations with valid latitude/longitude coordinates.
- [ ] Markers colored according to US EPA standards:
  - Good (0–50): `#00E400`
  - Moderate (51–100): `#FFFF00`
  - Unhealthy for Sensitive Groups (101–150): `#FF7E00`
  - Unhealthy (151–200): `#FF0000`
  - Very Unhealthy (201–300): `#8F3F97`
  - Hazardous (301+): `#7E0023`
- [ ] Hovering/clicking a marker displays a tooltip with Location Name, Country, Dominant Pollutant, AQI score, and Risk Tier.
- [ ] Includes interactive legend toggleable across risk tiers.
- [ ] Typecheck/lint passes.
- [ ] Verify in browser using dev-browser skill.

---

### US-003: Today's Most Polluted Leaderboard
**Description:** As an operations manager, I want a ranked table of today's 10 most polluted stations so that I can prioritize immediate schedule adjustments.

**Acceptance Criteria:**
- [ ] Table lists Top 10 locations ranked descending by maximum AQI.
- [ ] Columns: Location, Country, Worst Pollutant, AQI (with colored risk badge), and Risk Tier.
- [ ] Supports instant keyword search and column sorting.
- [ ] Typecheck/lint passes.
- [ ] Verify in browser using dev-browser skill.

---

### US-004: City Historical Trend Drill-Down
**Description:** As an environmental data analyst, I want to select any location and pollutant to inspect hourly AQI trends over time with EPA reference thresholds so that I can detect deteriorating conditions.

**Acceptance Criteria:**
- [ ] Two linked select dropdowns: Location (searchable) and Pollutant (filtered to supported AQI pollutants).
- [ ] Interactive time-series line chart showing hourly AQI progression.
- [ ] Reference dashed threshold lines at 50, 100, 150, 200, and 300 AQI.
- [ ] Detail data table displaying recent readings: Timestamp (UTC), Raw Value, Normalized µg/m³, AQI, and Risk Tier.
- [ ] Graceful empty state when no readings are available for the selected pair.
- [ ] Typecheck/lint passes.
- [ ] Verify in browser using dev-browser skill.

---

### US-005: Operational Watch-List & Alert Filter
**Description:** As a dispatch coordinator, I want to filter delivery zones by minimum risk threshold and download the alert list as CSV so that I can send re-routing instructions to drivers.

**Acceptance Criteria:**
- [ ] Threshold slider / button group: Good, Moderate, USG, Unhealthy (default), Very Unhealthy, Hazardous.
- [ ] Metric badge displaying the count of locations at or above the selected tier.
- [ ] Filtered table showing Location, Country, Pollutant, AQI, Readings Today, and Flagged Readings.
- [ ] One-click "Download as CSV" button generating `airpulse_alerts.csv` directly in the browser.
- [ ] Empty state message with confirmation when 0 locations exceed the threshold.
- [ ] Typecheck/lint passes.
- [ ] Verify in browser using dev-browser skill.

---

### US-006: High-Performance FastAPI Analytical Endpoints
**Description:** As a backend engineer, I need a REST API layer wrapping DuckDB queries with caching so that the frontend can fetch pre-aggregated data quickly without locking the database.

**Acceptance Criteria:**
- [ ] `GET /api/v1/kpis`: Returns top-line summary numbers and freshness date.
- [ ] `GET /api/v1/locations`: Returns monitored locations metadata and current data status.
- [ ] `GET /api/v1/aqi/latest`: Returns latest daily AQI per location & pollutant.
- [ ] `GET /api/v1/aqi/trends?location_key={}&pollutant_key={}`: Returns hourly measurements for charts.
- [ ] `GET /api/v1/alerts?min_tier={}`: Returns filtered operational alerts.
- [ ] Queries reuse existing DuckDB / Parquet fallback logic with read-only connection pooling and 5-minute memory cache.
- [ ] Automatic OpenAPI Swagger docs available at `/docs`.
- [ ] Automated pytest suite validates all endpoints return 200 with valid schema.

---

### US-007: Unified Production Build & Static Asset Serving
**Description:** As a DevOps engineer, I want FastAPI to serve the built frontend assets from `/` in production so that the entire application can run as a single container without needing a separate reverse proxy.

**Acceptance Criteria:**
- [ ] Vite compiles static assets into `frontend/dist/`.
- [ ] FastAPI mounts static files at `/` with SPA HTML5 fallback (`index.html` on unmatched client routes).
- [ ] Single start command (`python -m uvicorn app.api.main:app --port 8000`) serves both API and UI.
- [ ] Deprecated Streamlit app moved to `legacy/streamlit/` or archived cleanly.

---

## 4. Functional Requirements

- **FR-1:** The backend must connect to DuckDB in read-only mode (`duckdb.connect(..., read_only=True)`) if `warehouse/airpulse.duckdb` exists.
- **FR-2:** If the DuckDB file is absent, the backend must dynamically query committed Gold snapshot Parquet files in `data/gold_snapshot/` via DuckDB in-memory views.
- **FR-3:** All analytical API endpoints must implement in-memory caching with a 300-second TTL to avoid redundant analytical scans.
- **FR-4:** The map view must render all locations with valid latitude and longitude, applying coordinate bounding to auto-fit markers.
- **FR-5:** The trend chart must display EPA breakpoint reference lines with appropriate color indicators for risk tiers.
- **FR-6:** The alert panel must dynamically update its item count and table rows when the user adjusts the threshold slider.
- **FR-7:** The CSV export must generate UTF-8 encoded files containing all current alert rows and columns.
- **FR-8:** The frontend must indicate whether data originates from the live DuckDB warehouse or committed static Parquet snapshot.

---

## 5. Non-Goals (Out of Scope)

- **Authentication / Multi-Tenancy:** No user login, OAuth, or RBAC in this migration phase. (Designed for internal VPN or public dashboard access).
- **Write Operations:** The web UI will not write or update sensor data. Ingestion remains owned by Dagster pipelines.
- **Complex Microservices:** No separate Redis or message broker. In-process caching satisfies all performance requirements.
- **Real-time WebSockets:** OpenAQ data refreshes on an hourly/daily batch schedule; WebSocket streaming is speculative and unnecessary.

---

## 6. Design Considerations

- **Theme:** Clean modern dark/light mode with high-contrast data visualization palettes.
- **Standardized Color Scales:** US EPA Air Quality Index colors must be strictly observed.
- **Responsive Layout:** Works smoothly on 1920x1080 ops wallboards, 13-inch laptops, and mobile dispatch tablets.

---

## 7. Technical Considerations & Dependencies

- **Backend:** Python 3.11+, FastAPI, Uvicorn, DuckDB, Pandas, Pydantic v2.
- **Frontend:** Vite, React 18+, TypeScript, TailwindCSS (or Vanilla CSS custom tokens), Leaflet / React-Leaflet for mapping, Chart.js / Recharts for trends.
- **Compatibility:** Fully backwards-compatible with existing Dagster pipeline outputs (`warehouse/export_gold_snapshot.py`).

---

## 8. Success Metrics

- Initial page load time drops from ~3.5s (Streamlit) to <800ms.
- Client memory usage reduced by >60% compared to Streamlit's WebSocket canvas rendering.
- UI interaction latency (dropdowns, sliders) < 50ms.
- 100% test coverage on API endpoints.

---

## 9. Open Questions

1. **Target Frontend Technology:**
   - A. React + Vite + TypeScript (Modern, robust ecosystem, modular components)
   - B. Vanilla HTML5 + CSS + JavaScript (Zero build step, maximum Ponytail simplicity)
   - C. Next.js App Router (Full-stack SSR, higher complexity)

2. **Geospatial Map Library:**
   - A. Leaflet / React-Leaflet (Lightweight, open-source, tile-based, reliable)
   - B. MapLibre GL / Mapbox (Vector tiles, hardware-accelerated, larger bundle)
   - C. Canvas-based SVG / Deck.gl (High-density rendering)

3. **Packaging / Deployment Model:**
   - A. Monolithic FastAPI serving compiled SPA static bundle (Single port, single process)
   - B. Decoupled frontend on Vercel/Cloudflare Pages + FastAPI API on Fly.io/Render
   - C. Docker Compose with Nginx reverse proxy + FastAPI backend + Node frontend
