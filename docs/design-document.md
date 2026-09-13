# Design Document: AirPulse Web Interface

## 1. Executive Summary & Personas

AirPulse is an operational air quality intelligence system tailored for logistics and supply chain decision-makers. The primary user persona is the **Meridian Logistics Operations Dispatcher**:
- **Goals:** Rapidly identify delivery hubs compromised by toxic air quality (wildfires, industrial smog, temperature inversions), re-route vulnerable freight fleets, and mandate personal protective equipment (N95 handoffs) for field drivers.
- **Key Pain Points with Streamlit:** High interaction latency, full page re-runs on slider changes, rigid map controls, lack of responsive mobile design for field supervisors.

---

## 2. Information Architecture & Navigation

The interface provides three core views easily accessible via a persistent top navigation bar:

```
+-----------------------------------------------------------------------------------+
|  [Logo] AirPulse       [Overview (Map)]    [City Trends]    [Alerts (3)]    [Live] |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ KPI 1: Stations ]   [ KPI 2: Peak AQI ]   [ KPI 3: Danger Zones ]  [ Freshness ]|
|                                                                                   |
|  +--------------------------------------------+  +------------------------------+ |
|  |                                            |  |  Today's Most Polluted       | |
|  |                                            |  |  1. Delhi        342 [Haz]   | |
|  |           Interactive Global Map           |  |  2. Lahore       285 [V.Un]  | |
|  |         (EPA Color-Coded Stations)         |  |  3. Bakersfield  168 [Unh]   | |
|  |                                            |  |  4. Jakarta      155 [Unh]   | |
|  +--------------------------------------------+  +------------------------------+ |
|                                                                                   |
|  Legend: [● Good] [● Moderate] [● USG] [● Unhealthy] [● Very Unhealthy] [● Haz]   |
+-----------------------------------------------------------------------------------+
```

1. **Overview (Default):** High-level operational summary with top-line metric cards, an interactive global station risk map, today's highest-risk leaderboard, and unmonitored location reporting.
2. **City Trends (`/trends`):** Deep analytical exploration allowing users to select a city and pollutant (PM2.5, PM10, NO2, O3, CO, SO2) to examine historical hourly AQI movements against official EPA safety benchmarks.
3. **Operational Alerts (`/alerts`):** Action-oriented triage table filtered by risk tier threshold (defaulting to Unhealthy >= 151 AQI) with instant CSV export for field dispatchers.

---

## 3. Visual Design System & Design Tokens

### 3.1 Color Palette
AirPulse employs an intentional dark-mode industrial theme (`#0F172A` Slate base) that maximizes contrast for map overlays and risk indicators:

- **Background Surfaces:**
  - Base Background: `#0B0F17` (Deep Navy Black)
  - Card / Panel Surface: `#161F30` (Muted Slate)
  - Card Border / Divider: `#23324A` (Subtle Slate Border)
  - Input / Hover Surface: `#1E2B42`
- **Text & Content:**
  - Primary Text: `#F8FAFC` (Slate 50)
  - Secondary Text: `#94A3B8` (Slate 400)
  - Muted / Caption Text: `#64748B` (Slate 500)
- **Official US EPA Air Quality Index (AQI) Semantic Colors:**
  - **Good (0–50):** `#10B981` (Emerald Green) — *Clean air, minimal risk*
  - **Moderate (51–100):** `#FBBF24` (Amber Yellow) — *Acceptable air quality*
  - **Unhealthy for Sensitive Groups (101–150):** `#F97316` (Vibrant Orange) — *General public not likely affected*
  - **Unhealthy (151–200):** `#EF4444` (Crimson Red) — *Everyone begins to experience health effects*
  - **Very Unhealthy (201–300):** `#A855F7` (Deep Purple) — *Health alert; serious health effects*
  - **Hazardous (301+):** `#881337` (Dark Maroon / Rose 900) — *Emergency health warnings*

### 3.2 Typography
- **Font Family:** Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif.
- **Numbers / Metrics:** Tabular numerals (`font-variant-numeric: tabular-nums`) for jitter-free metric updates.
- **Hierarchy:**
  - Page Titles: `text-2xl font-bold tracking-tight` (24px)
  - Section Headings: `text-lg font-semibold` (18px)
  - KPI Stat Figures: `text-3xl font-extrabold tracking-tight` (30px)
  - Table & Body Text: `text-sm font-normal` (14px)
  - Micro-badges & Labels: `text-xs font-semibold uppercase tracking-wider` (11px)

---

## 4. Component Breakdown & Interactions

### 4.1 Header & Status Bar
- Shows project branding `AirPulse` with pulse icon.
- Navigation pill links with active indicator.
- Live data source badge:
  - Green dot: `Live DuckDB Warehouse`
  - Blue dot: `Committed Snapshot (Parquet)`

### 4.2 KPI Metric Cards
Four cards spanning the top of the dashboard:
1. **Monitored Locations:** Total active monitoring sites reporting data.
2. **Worst Current Reading:** Peak AQI with a colored risk chip, location name, and dominant pollutant.
3. **Zones Needing Attention:** Counter of locations with AQI > 150 (Unhealthy+). Pulsing alert dot if count > 0.
4. **Data Freshness:** Timestamp of latest ingested measurement and pipeline sync status.

### 4.3 Interactive Geospatial Risk Map
- Built using **Leaflet** with dark CartoDB tile layer (`https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png`).
- Station markers:
  - Custom SVG circle markers with color matching the station's peak risk tier.
  - Marker radius dynamically scaled: `base_radius (6px) + (aqi / 50)`.
  - Stations with AQI > 200 render with a subtle CSS radar pulse effect.
- Marker Click / Hover Tooltip:
  - Location title, country flag, coordinates.
  - Dominant pollutant and exact AQI score.
  - Quick action link: "Drill into Trends →" which switches to the Trends view with that location pre-selected.

### 4.4 Trend Analytics Line Chart
- Clean, responsive SVG/Canvas line chart (Recharts or Chart.js).
- Visual background bands or horizontal dashed reference lines representing the 5 EPA risk breakpoints:
  - 50 (Good)
  - 100 (Moderate)
  - 150 (USG)
  - 200 (Unhealthy)
  - 300 (Very Unhealthy)
- Interactive crosshair on hover displaying timestamp (UTC), AQI value, raw reading, and unit-normalized concentration (µg/m³).

### 4.5 Operational Alert Hub
- **Risk Threshold Selector:** Interactive horizontal slider or segmented button strip (`[Good] [Moderate] [USG] [Unhealthy (Selected)] [Very Unhealthy] [Hazardous]`).
- **Dynamic Counter:** "Showing X delivery hubs exceeding [Tier]".
- **Alerts Table:**
  - Sortable columns: Location, Country, Worst Pollutant, Peak AQI, Today's Readings, Flagged Readings.
  - Visual status pill on each row.
- **Export Action:** Prominent "Download CSV" button that triggers immediate client-side generation and download of `airpulse_alerts.csv`.

---

## 5. Responsive Behavior & Viewports

- **Desktop (1280px+):** Full multi-column view with side-by-side map and leaderboard; 4-column KPI grid.
- **Tablet (768px–1279px):** 2-column KPI grid; map spans full width with leaderboard stacked below.
- **Mobile (<768px):** Single-column stack. Map height fixed at 360px with touch pinch-to-zoom enabled. Navigation collapses into a compact top drawer or tab bar.

---

## 6. Accessibility & Performance Guardrails

- **Colorblind Safety:** All risk tiers pair color with explicit text labels ("Unhealthy", "Hazardous") and numerical AQI values; color is never the sole information carrier.
- **Keyboard Navigation:** All dropdowns, sliders, and map markers are focusable and navigable via standard keyboard controls (`Tab`, `Arrow keys`, `Enter`).
- **Initial Bundle Target:** Frontend JS bundle < 120KB gzipped (achieved by using lightweight Leaflet and Preact/React with zero heavy UI libraries).
