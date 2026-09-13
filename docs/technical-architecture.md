# Technical Architecture Document: AirPulse Decoupled Platform

## 1. Architectural Overview

AirPulse migrates from a coupled Streamlit monolith to a decoupled client-server architecture. In accordance with the **Ponytail Principle (Ladder Rung 1–5: minimal complexity, native features, zero unneeded abstractions)**, the stack avoids complex multi-container or microservice architectures. 

The entire system is powered by:
1. **Analytical Engine:** DuckDB querying local analytical tables (`warehouse/airpulse.duckdb`) with zero-downtime fallback to committed Gold snapshot Parquet files (`data/gold_snapshot/*.parquet`).
2. **Backend Serving Layer:** A lean **FastAPI** application in Python 3.11+ providing high-throughput, low-latency REST endpoints with automatic OpenAPI documentation.
3. **Frontend Presentation Layer:** A lightweight Single-Page Application (SPA) built with **Vite + React + TypeScript** (or Vanilla JS), utilizing **Leaflet** for geospatial rendering and **Chart.js** for time-series visualization.
4. **Single-Process Production Packaging:** FastAPI serves the compiled SPA static assets directly from `/` via `fastapi.staticfiles.StaticFiles`, eliminating the need for a separate Nginx or Node.js container in production.

---

## 2. High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph DataPipeline ["Data Engineering Pipeline"]
        OpenAQ["OpenAQ REST API"] --> Ingestion["ingestion/*.py"]
        Ingestion --> RawData["data/raw/*.parquet"]
        RawData --> DBT["dbt build (mart)"]
        DBT --> DuckDBFile[("warehouse/airpulse.duckdb")]
        DBT --> SnapshotJob["export_gold_snapshot.py"]
        SnapshotJob --> ParquetFiles[("data/gold_snapshot/*.parquet")]
    end

    subgraph BackendAPI ["FastAPI Serving Layer (app/api/)"]
        Router["FastAPI App & Routers (/api/v1)"]
        QueryEngine["Data Access Layer (app.utils.data)"]
        Cache["In-Memory Cache (TTL: 300s)"]
        
        Router --> Cache
        Cache --> QueryEngine
        QueryEngine -.->|Primary (Read-Only)| DuckDBFile
        QueryEngine -.->|Fallback if DB absent| ParquetFiles
    end

    subgraph FrontendSPA ["Frontend Presentation Layer (frontend/)"]
        ClientApp["Single Page Application (React / TS)"]
        MapEngine["Leaflet Map Component"]
        ChartEngine["Trends Chart Component"]
        AlertsView["Operational Alerts & CSV Exporter"]
        
        ClientApp --> MapEngine
        ClientApp --> ChartEngine
        ClientApp --> AlertsView
    end

    ClientApp -->|HTTP Fetch /api/v1/*| Router
    Router -->|Serves frontend/dist/* at /| ClientApp
```

---

## 3. API Contract & Endpoint Specifications

All API endpoints reside under `/api/v1` and return JSON responses.

### 3.1 `GET /api/v1/health`
Checks backend and database availability.
```json
{
  "status": "healthy",
  "storage_backend": "live_duckdb",
  "database_path": "warehouse/airpulse.duckdb",
  "timestamp": "2026-09-13T12:00:00Z"
}
```

### 3.2 `GET /api/v1/kpis`
Returns aggregated operational metrics for the top-line dashboard banner.
- **Cache TTL:** 300 seconds
- **Response Schema:**
```json
{
  "locations_monitored": 24,
  "worst_current_reading": {
    "location_name": "Anand Vihar, Delhi",
    "country_name": "India",
    "parameter_name": "pm25",
    "avg_aqi": 342.5,
    "risk_tier": "Hazardous"
  },
  "hazardous_zones_count": 4,
  "latest_data_date": "2026-09-12",
  "data_source_label": "live DuckDB warehouse"
}
```

### 3.3 `GET /api/v1/locations`
Returns all active monitoring stations with geographic coordinates and current status.
- **Response Schema:**
```json
[
  {
    "location_key": "loc_delhi_anand_vihar",
    "location_name": "Anand Vihar",
    "country_code": "IN",
    "country_name": "India",
    "latitude": 28.6469,
    "longitude": 77.3160,
    "has_recent_data": true
  }
]
```

### 3.4 `GET /api/v1/aqi/latest`
Returns the latest daily average AQI for every monitored location and pollutant pair.
- **Query Parameters:** `min_aqi` (optional, float)
- **Response Schema:**
```json
[
  {
    "location_key": "loc_delhi_anand_vihar",
    "location_name": "Anand Vihar",
    "country_name": "India",
    "latitude": 28.6469,
    "longitude": 77.3160,
    "parameter_name": "pm25",
    "measured_date": "2026-09-12",
    "avg_aqi": 342.5,
    "risk_tier": "Hazardous",
    "reading_count": 24,
    "flagged_reading_count": 1
  }
]
```

### 3.5 `GET /api/v1/aqi/trends`
Retrieves chronological hourly measurements for a specific location and pollutant.
- **Query Parameters:** 
  - `location_key` (required, string)
  - `pollutant_key` (required, string)
- **Response Schema:**
```json
[
  {
    "measured_at_utc": "2026-09-12T00:00:00Z",
    "aqi": 310,
    "raw_value": 260.4,
    "value_ugm3": 260.4,
    "risk_tier": "Hazardous"
  },
  {
    "measured_at_utc": "2026-09-12T01:00:00Z",
    "aqi": 325,
    "raw_value": 275.1,
    "value_ugm3": 275.1,
    "risk_tier": "Hazardous"
  }
]
```

### 3.6 `GET /api/v1/alerts`
Returns list of stations currently violating the specified operational risk tier.
- **Query Parameters:** 
  - `min_tier` (optional, default: `"Unhealthy"`, options: `Good`, `Moderate`, `Unhealthy for Sensitive Groups`, `Unhealthy`, `Very Unhealthy`, `Hazardous`)
- **Response Schema:**
```json
{
  "min_tier": "Unhealthy",
  "threshold_aqi": 151,
  "alert_count": 4,
  "alerts": [
    {
      "location_name": "Anand Vihar",
      "country_name": "India",
      "parameter_name": "pm25",
      "avg_aqi": 342.5,
      "risk_tier": "Hazardous",
      "reading_count": 24,
      "flagged_reading_count": 1
    }
  ]
}
```

---

## 4. Data Access, Concurrency & Caching

### 4.1 Safe Read-Only DuckDB Concurrency
DuckDB supports multiple concurrent readers if each connection is established in read-only mode:
```python
conn = duckdb.connect(str(DB_PATH), read_only=True)
```
To avoid file-lock contention and connection leaks:
- A context manager opens and closes read-only DuckDB connections per query batch.
- If `DB_PATH` is absent (such as in lightweight test runners or demo deployments), the context manager initializes an in-memory database and attaches the committed Parquet snapshots:
```python
conn = duckdb.connect(":memory:")
conn.execute("CREATE SCHEMA IF NOT EXISTS mart")
for f in GOLD_SNAPSHOT_DIR.glob("*.parquet"):
    conn.execute(f"CREATE VIEW mart.{f.stem} AS SELECT * FROM read_parquet('{f}')")
```

### 4.2 In-Memory Query Caching
Analytical scans do not need to hit disk on every user request. A thread-safe, 300-second TTL cache in Python intercepts requests for `latest_aqi`, `kpis`, and `locations`. This guarantees sub-5ms response times on repeated reads.

---

## 5. Build, Bundling & Single-Process Deployment

### 5.1 Development Workflow
- **Backend:** `uvicorn app.api.main:app --reload --port 8000`
- **Frontend:** `npm run dev --prefix frontend` (Vite dev server running on port 5173 with proxy configuration forwarding `/api` to `http://localhost:8000`).

### 5.2 Production Packaging (Single Process)
1. **Frontend Build:** `npm run build --prefix frontend` outputs static HTML, CSS, and JS into `frontend/dist/`.
2. **FastAPI Static Mount:**
```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Route all non-API paths to index.html for client-side routing
    return FileResponse("frontend/dist/index.html")
```
3. **Execution Command:**
```bash
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```
This guarantees zero operational debt: no Nginx configuration, no Node runtime required in production, and zero cost overhead.
