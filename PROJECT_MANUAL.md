# AirPulse — Complete Project Documentation

### A beginner's guide to everything built, what it does, and why

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [The Real-World Problem It Solves](#2-the-real-world-problem-it-solves)
3. [Tech Stack — What and Why](#3-tech-stack--what-and-why)
4. [Architecture — The Big Picture](#4-architecture--the-big-picture)
5. [Folder Structure — Everything at a Glance](#5-folder-structure--everything-at-a-glance)
6. [Deep Dive: Phase by Phase](#6-deep-dive-phase-by-phase)
   - [Phase 1: Ingestion](#phase-1-ingestion--ingestion)
   - [Phase 2: Storage](#phase-2-storage--warehouse)
   - [Phase 3: Transformation](#phase-3-transformation--dbt_project)
   - [Phase 4: Orchestration](#phase-4-orchestration--orchestration)
   - [Phase 5: Dashboard](#phase-5-dashboard--app)
7. [One Reading's Complete Journey — A Worked Example](#7-one-readings-complete-journey--a-worked-example)
8. [Testing Philosophy](#8-testing-philosophy)
9. [Real Bugs Found and Fixed](#9-real-bugs-found-and-fixed)
10. [How to Run Everything](#10-how-to-run-everything)
11. [Glossary](#11-glossary)

---

## 1. What This Project Is

**AirPulse** is an end-to-end data engineering pipeline that turns messy, real-time global air quality
sensor data into a trustworthy, queryable dataset and an interactive dashboard. It pulls data from
**OpenAQ** (a real, free, public API aggregating readings from tens of thousands of air quality monitors
worldwide), cleans and models it properly, computes the official **EPA Air Quality Index (AQI)** for every
reading, and serves the result through a **Streamlit** dashboard anyone can open in a browser.

It is built entirely from **free, open-source tools** — no cloud provider, no credit card, nothing that
costs money to run on your own laptop.

The project is deliberately built the way a real company's data platform would be built: not one big
script, but a series of distinct, single-purpose layers, each one tested independently, each one
replaceable without breaking the others.

---

## 2. The Real-World Problem It Solves

**The narrative:** Imagine a company called **Meridian Logistics** — a last-mile delivery and field-services
business operating in 30+ countries. Their operations team has three real, unanswered questions every day:

1. **Which delivery zones currently have hazardous air quality** that puts outdoor couriers at risk?
2. **Which regions are trending worse over time**, so the company can proactively change delivery windows
   or require indoor handoffs before it becomes a safety issue?
3. **What is "the" air quality number for a city right now?** Raw sensor data arrives from thousands of
   independent monitoring stations, in inconsistent units, with missing readings and occasional garbage
   values — there's no single trustworthy number today.

This isn't a hypothetical. Companies like IQAir, BreezoMeter, and various insurance/ESG platforms sell
exactly this kind of processed air-quality intelligence commercially. AirPulse builds the same kind of
system from scratch, using only free tools, as a demonstration of real data engineering skill.

**Why this is a genuinely hard data problem** (not just "call an API and show a chart"):

- **Pagination**: OpenAQ's API returns results a page at a time; you have to loop through pages correctly.
- **Nested JSON**: Each location has an array of sensors nested inside it — turning that into flat,
  queryable rows is a real transformation challenge.
- **Multi-provider unit inconsistency**: Different sensors report the same pollutant in different units
  (µg/m³, ppm, ppb) depending on who owns the equipment. You cannot compare "45" from one sensor to "45"
  from another without knowing the units and converting correctly.
- **Missing and duplicate data**: Sensors go offline. The same hour's reading can get pulled twice by an
  overlapping ingestion window. Both cases have to be handled deliberately, not ignored.
- **A real, non-trivial calculation**: The EPA's AQI formula is a piecewise mathematical function with
  different breakpoint tables per pollutant — this is genuine business logic, not a lookup table.

---

## 3. Tech Stack — What and Why

| Layer | Tool | Why this one |
|---|---|---|
| **Data source** | [OpenAQ v3 API](https://docs.openaq.org) | Free (registration only, no credit card), globally recognized, genuinely messy real-world data |
| **Ingestion language** | Python (`requests`, `tenacity`, `pydantic`) | Industry standard; `tenacity` handles retries, `pydantic` validates data shape |
| **Bronze storage** | Local Parquet files | Columnar, immutable, the same pattern as an S3/cloud data lake — just on a laptop |
| **Data warehouse** | [DuckDB](https://duckdb.org) | Free, embedded (no server to run), reads Parquet natively, has a real SQL engine underneath |
| **Transformation** | [dbt-core](https://www.getdbt.com) | The industry-standard tool for testable, documented SQL transformations |
| **Orchestration** | [Dagster](https://dagster.io) | Schedules and monitors the pipeline; understands data lineage natively |
| **Dashboard** | [Streamlit](https://streamlit.io) | Turns a Python script into a web app with almost no frontend code |
| **Testing** | `pytest` + dbt's built-in test framework + Streamlit's `AppTest` | Every layer has its own appropriate testing tool |

**The unifying idea:** every one of these tools is free and runs entirely on your own machine. Nothing
here requires a cloud account, a credit card, or ongoing cost — a deliberate constraint that also happens
to mirror how a lot of real companies actually run analytics workloads at small-to-medium scale today.

---

## 4. Architecture — The Big Picture

Data moves through five distinct layers. Each layer has exactly one job, which is the single most
important design principle in this whole project:

```
┌─────────────────┐
│   OpenAQ API     │  external source — thousands of real air quality sensors worldwide
└────────┬─────────┘
         │  Python: paginated, retried, validated
         ▼
┌─────────────────┐
│  Bronze layer    │  raw Parquet files — an exact, unmodified copy of what the API said
└────────┬─────────┘
         │  loaded as-is, still uncleaned
         ▼
┌─────────────────┐
│  raw schema      │  the same bronze data, now inside DuckDB and queryable with SQL
│  (DuckDB)        │
└────────┬─────────┘
         │  dbt: clean, deduplicate, flatten nested JSON
         ▼
┌─────────────────┐
│ staging +        │  one clean row per sensor-reading; units normalized; AQI computed
│ intermediate     │
└────────┬─────────┘
         │  dbt: join into a proper dimensional model
         ▼
┌─────────────────┐
│  marts           │  the final, tested "star schema" — fact + dimension tables
│  (star schema)   │
└────────┬─────────┘
         │  Streamlit reads this directly
         ▼
┌─────────────────┐
│  Dashboard       │  map, trends, and an operational alert list a human can act on
└─────────────────┘
```

**Why this many layers, instead of one script that does everything?**

Because each layer can be **tested, fixed, and re-run independently**. If a transformation bug is found in
how AQI gets calculated, you fix the transformation layer and re-run *only* that layer — the raw data
sitting in bronze is untouched and doesn't need to be re-downloaded from the API. This is exactly what
happened multiple times while building this project (see [Section 9](#9-real-bugs-found-and-fixed)).

**Dagster sits above all of this**, coordinating when each layer runs and in what order, and **Streamlit
sits at the very end**, only ever reading the final, tested marts — it never touches raw or messy data
directly.

---

## 5. Folder Structure — Everything at a Glance

```
airpulse-air-quality-pipeline/
│
├── ingestion/              # PHASE 1 — pulls data from the OpenAQ API
│   ├── openaq_client.py    #   the API client: pagination, rate-limiting, retries
│   ├── schemas.py          #   defines exactly what a valid API response looks like
│   ├── config.py           #   which countries to pull, how far back to look
│   ├── extract_locations.py    # script: pulls sensor/location metadata
│   └── extract_measurements.py # script: pulls hourly pollution readings
│
├── warehouse/              # PHASE 2 — loads bronze data into a queryable database
│   ├── db.py               #   how to connect to the DuckDB database file
│   ├── load_raw.py         #   copies bronze Parquet into DuckDB tables
│   └── export_gold_snapshot.py # exports final tables to Parquet for deployment
│
├── dbt_project/            # PHASE 3 — cleans, models, and tests the data
│   ├── models/
│   │   ├── staging/        #   clean + flatten + deduplicate (1 job per model)
│   │   ├── intermediate/   #   unit conversion + AQI calculation
│   │   └── marts/          #   the final star schema: facts + dimensions
│   ├── snapshots/          #   tracks location history over time (SCD Type 2)
│   ├── macros/              #   reusable SQL logic (AQI formula, unit conversion)
│   └── tests/               #   custom data-quality checks
│
├── orchestration/          # PHASE 4 — schedules and monitors the whole pipeline
│   ├── assets/              #   every step of the pipeline, as a Dagster "asset"
│   ├── schedules.py         #   runs the pipeline automatically every 6 hours
│   ├── sensors.py           #   alerts if a pipeline run fails
│   └── asset_checks.py      #   checks the data is actually fresh, not just present
│
├── app/                    # PHASE 5 — the dashboard a human actually looks at
│   ├── streamlit_app.py     #   home page: map + key numbers
│   ├── pages/                #   two more pages: trends and alerts
│   └── utils/                #   shared code: data access, color scheme
│
├── scripts_dev/            # fake test data, so you can try everything without a real API key
│
├── tests/                  # automated tests for everything above
│
├── data/                   # where bronze files and snapshot exports actually land (not committed)
│
├── requirements.txt        # every Python package this project needs
└── README.md               # setup instructions and phase-by-phase build notes
```

---

## 6. Deep Dive: Phase by Phase

### Phase 1: Ingestion — `ingestion/`

**What it does:** talks to the real OpenAQ API and saves the results to disk, untouched.

**Why it's its own layer:** talking to an external API is unreliable — it can be slow, rate-limited, or
temporarily down. This layer's whole job is to handle that unreliability once, carefully, so nothing
downstream ever has to think about it again.

#### `ingestion/openaq_client.py` — the API client

This is the most technically interesting file in this phase. It solves three real problems:

1. **Pagination.** OpenAQ returns results a page at a time. You ask for page 1, get 100 results, ask for
   page 2, and so on. The tricky part: OpenAQ's own documentation says the field that tells you "how many
   results exist in total" can be a number, the *string* `">100"`, or nothing at all. So this client never
   trusts that field — instead, it keeps asking for more pages until a page comes back with *fewer*
   results than requested, which is the only signal that's always reliable.

   ```python
   def _paginate(self, path, params, limit=100):
       page = 1
       while True:
           payload = self._get(path, params={**params, "page": page, "limit": limit})
           results = payload.get("results", [])
           for record in results:
               yield record
           if len(results) < limit:
               return   # a short page means we've reached the end
           page += 1
   ```

2. **Rate limiting.** OpenAQ allows 60 requests per minute. Rather than firing requests as fast as
   possible and getting blocked, the client checks how many requests it has "left" (from a header the API
   sends back) and slows itself down *before* it ever gets blocked.

3. **Retrying failures correctly.** If the API returns a temporary error (like "too many requests" or "server
   error"), the client waits a bit and tries again automatically, using a library called `tenacity`. But if
   the API returns a *permanent* error (like "that address doesn't exist"), it does **not** waste time
   retrying — it fails immediately, because retrying a mistake five times just wastes five times as long
   finding out what you already knew.

#### `ingestion/schemas.py` — what a valid API response looks like

This file uses a library called **pydantic** to describe, in code, exactly what shape a response from
OpenAQ should have — which fields exist, what type each one is, and which fields are allowed to be
missing.

**Why this matters:** without this file, if OpenAQ ever changed their API (added a field, removed one,
changed a type), the ingestion code might silently accept broken data and pass it downstream, where it
would cause a confusing error three steps later. With this file in place, a broken response fails
**immediately and loudly**, at the exact point where it entered the system — which is the cheapest,
easiest place to debug a problem.

**Example — a real design decision made in this file:** a sensor reading's `value` (the actual pollution
number) is allowed to be missing (`None`) — a sensor can have an outage and simply not report anything for
an hour. But a reading's `period` (which hour is being reported) is **required** — a reading with no
timestamp at all is meaningless and should be rejected outright, not silently accepted with a blank
timestamp.

```python
class HourlyData(BaseModel):
    value: Optional[float] = None     # allowed to be missing — a real sensor gap
    period: Period                     # NOT allowed to be missing — required
```

#### `ingestion/extract_locations.py` and `extract_measurements.py`

These are the actual scripts you run. Each one:
1. Calls the client to fetch data
2. Validates every record against the schemas above
3. Writes the result to two places: a raw `.json` file (an audit trail — "exactly what the API said") and
   a `.parquet` file (the same data, but flattened into a table)

They save data into folders named by date, like `data/bronze/locations/ingest_date=2026-06-29/`. This is
called **partitioning**, and it means every day's pull is kept separately, forever, so you can always look
back at exactly what the API returned on any given day.

---

### Phase 2: Storage — `warehouse/`

**What it does:** takes the Parquet files from Phase 1 and loads them into an actual SQL database
(DuckDB), so they can be queried with SQL instead of manipulated as files.

**Why DuckDB specifically:** DuckDB is a real, proper SQL database engine — but unlike Postgres or
Snowflake, it doesn't need a server running somewhere. It's just a single file on disk (like a
`.duckdb` file), and any Python program (or dbt, or Streamlit) can open and query it directly. This makes
it perfect for a project that needs to run entirely on one laptop with no ongoing infrastructure.

#### `warehouse/db.py`

A tiny file with one real job: know where the database file lives, and hand back a connection to it. It's
deliberately this simple — every other file in the project imports from here rather than hardcoding a
path, so there's exactly one place that knows "where is the actual database."

#### `warehouse/load_raw.py`

This is the file that actually copies Parquet data into DuckDB tables. It supports two modes:

- **Full refresh** — rebuild the tables from scratch, reading every single bronze file that's ever been
  written. Simple, always correct, and what you'd use for a project at this scale.
- **Incremental append** — only load files that are newer than what's already loaded. Faster at a much
  bigger scale, and included here mainly as a good answer to "how would this scale up" in an interview.

**An important design decision in this file:** it does **not** remove duplicate rows. If the same hour's
reading gets pulled twice (which genuinely happens — see Phase 3 below), both copies land in this raw
table. That's deliberate: **raw data should always stay exactly as raw as what came from the source.**
Cleaning it up is a job for the *next* layer, not this one.

#### `warehouse/export_gold_snapshot.py`

Exports the final, cleaned tables (built in Phase 3) into Parquet files that get committed to the project.
This is what makes it possible to deploy the dashboard to a free hosting service that can't run a live
database — more on this in the Phase 5 section.

---

### Phase 3: Transformation — `dbt_project/`

**What it does:** this is where the real "data engineering" happens — cleaning messy data, calculating the
Air Quality Index, and organizing everything into a proper, well-tested database design called a **star
schema**.

**Why dbt specifically:** dbt lets you write transformations as plain SQL files, but adds three
enormously valuable things on top: automatic **dependency tracking** (dbt figures out which models depend
on which, and runs them in the right order), built-in **testing** (you can assert things like "this column
should never be empty" and dbt checks it every time), and automatic **documentation**.

The dbt project is organized into three layers, matching the same "one job per layer" philosophy as the
rest of the project:

#### Staging models (`models/staging/`) — clean, but don't calculate anything yet

- **`stg_openaq__locations.sql`** — takes the raw location data and keeps only the most recently-pulled
  version of each location (a location can be pulled fresh every single day; this model narrows it down
  to "the latest known state of this location").
- **`stg_openaq__sensors.sql`** — this is where the **nested JSON problem gets solved**. Each location's
  raw data contains a *list* of sensors buried inside it (one location might have 4 sensors: one for
  PM2.5, one for PM10, one for ozone, one for NO2). This model uses a SQL command called `UNNEST` to turn
  that single nested list into separate, flat rows — one row per sensor.
- **`stg_openaq__measurements.sql`** — cleans up the actual pollution readings, and **removes duplicate
  readings**. Here's a concrete example of why duplicates happen: the ingestion script pulls "the last 3
  days" of readings every time it runs. If it runs once on Monday and again on Tuesday, both runs include
  Monday's readings — so Monday's data legitimately appears twice in the raw layer. This model picks the
  most recently-pulled copy of each (sensor, hour) combination and discards the rest.

#### Macros (`macros/`) — reusable calculation logic

- **`convert_units.sql`** — different sensors report gas pollutants (ozone, NO2, etc.) in different
  units — some in µg/m³, some in ppm, some in ppb — depending on who owns the equipment. This macro
  converts everything to one consistent unit, using the real chemistry formula
  (`µg/m³ = ppm × molecular_weight ÷ 24.45 × 1000`) for each specific gas.
- **`calculate_aqi.sql`** — the actual EPA Air Quality Index formula. This is a genuine piece of business
  logic, not a lookup table: AQI is calculated with a formula that interpolates between published
  "breakpoints" specific to each pollutant. For example, PM2.5 has different math than ozone. A worked
  example of this exact calculation is in [Section 7](#7-one-readings-complete-journey--a-worked-example).

#### Intermediate models (`models/intermediate/`) — apply the macros

- **`int_measurements_unit_normalized.sql`** — applies the unit-conversion macro to every reading.
- **`int_measurements_aqi.sql`** — applies the AQI-calculation macro to every reading.

#### Snapshots (`snapshots/dim_location_snapshot.sql`) — tracking history over time

This is one of the more advanced concepts in the project, called **SCD Type 2** (Slowly Changing
Dimension, Type 2). Here's the plain-English version:

A location's details can change over time — a sensor gets recalibrated, a station gets renamed, and so
on. A normal database table would just *overwrite* the old name with the new one, losing history forever.
A **snapshot** instead keeps *both* versions: the old name, with a note saying "this was true from date X
to date Y," and the new name, with a note saying "this has been true since date Y." This means you can
always answer questions like "what did we think this location was called back in March?"

#### Marts (`models/marts/`) — the final, polished star schema

This is the "gold" layer everything else builds toward — the tables that are actually queried by the
dashboard. It follows a standard, well-known data warehouse design called a **star schema**:

- **Dimension tables** (`dim_location`, `dim_pollutant`, `dim_date`) — descriptive information: *what*
  a location is, *what* a pollutant is called, calendar information.
- **Fact tables** (`fact_air_quality_hourly`, `fact_daily_city_aqi`) — the actual measurements: *numbers*
  that happened at a specific time, linked back to the dimension tables.

Two fact tables exist on purpose: `fact_air_quality_hourly` has one row per sensor per hour (very
detailed, useful for drilling into specific history), while `fact_daily_city_aqi` is a pre-summarized
"one row per city per day" table, built specifically so the dashboard's main page can load instantly
without having to re-calculate an average across thousands of hourly rows every single time someone opens
it.

#### Tests (`tests/`) — dbt's built-in data quality checks

Every model in this project has tests attached — things like "this column should never be blank" or
"this value should never be negative." A few of the tests were written specifically *because* they caught
a real bug during development:

- **`assert_no_negative_concentrations.sql`** — a pollution reading below zero is physically impossible; if
  one ever shows up, something upstream is broken.
- **`assert_null_value_yields_null_aqi.sql`** — encodes a bug that was actually found and fixed (see
  [Section 9](#9-real-bugs-found-and-fixed)): a missing reading was accidentally being calculated as the
  *worst possible* AQI score instead of "no score at all."

---

### Phase 4: Orchestration — `orchestration/`

**What it does:** automatically runs every phase above, in the correct order, on a schedule, and tells you
if something breaks.

**Why this is needed at all:** Phases 1-3 are a series of manual commands you'd otherwise have to
remember to run in the right order, every single day, forever. Dagster turns that into something that
just happens automatically.

**The single most important concept in this phase:** Dagster treats every step of the pipeline as an
**asset** — a named "thing that gets produced," like "the raw locations table" or "the `dim_location`
dimension." Dagster automatically figures out which assets depend on which other assets, and draws that
as a picture (a **lineage graph**) you can look at in a web browser.

#### `orchestration/assets/ingestion_assets.py`

Wraps the Phase 1 and Phase 2 Python scripts as Dagster assets — "pull locations from the API," "pull
measurements from the API," "load everything into the raw database."

#### `orchestration/assets/dbt_assets.py`

This is a genuinely clever piece of the project: rather than manually listing every single dbt model as
its own separate Dagster asset (which would mean maintaining two separate lists that could drift out of
sync), this file reads dbt's own internal "manifest" file and **automatically generates one Dagster asset
per dbt model** — so Dagster's picture of the pipeline is always guaranteed to match the real dbt project,
with zero manual bookkeeping.

**A real "aha" moment from building this:** Phase 3's instructions originally said you had to run three
separate commands in a specific order (`dbt run`, then `dbt snapshot`, then `dbt run` again) because
normal dbt commands don't include snapshots automatically. This file instead runs a single command called
`dbt build`, which *does* include snapshots in the correct order automatically — so once Dagster is
running things, that whole manual three-step dance disappears completely.

#### `orchestration/schedules.py`

A simple rule: "run the whole pipeline every 6 hours." Easy to change to any schedule you want.

#### `orchestration/sensors.py`

Watches for failed pipeline runs and logs a loud error message (in a real company, this would send a
Slack notification instead — the code for that is written but commented out, since it needs a real Slack
account to actually send anything).

#### `orchestration/asset_checks.py`

A check that's different from dbt's tests on purpose: dbt tests check whether the *data* is correct
(no duplicates, no negative numbers). This check instead asks an *operational* question: "is the pipeline
actually keeping up?" — specifically, is the newest reading in the database less than 48 hours old? If the
pipeline silently stopped running, this is what would catch it.

---

### Phase 5: Dashboard — `app/`

**What it does:** the part a human being actually looks at — a website showing the current air quality
risk around the world, with enough detail to act on.

#### `app/streamlit_app.py` — the home page

Shows four key numbers at the top (how many locations are being monitored, the single worst reading right
now, how many locations need attention, how current the data is), a world map with color-coded markers,
and a "worst cities today" leaderboard.

#### `app/pages/1_City_Trends.py`

Lets you pick any location and any pollutant, and see how its Air Quality Index has changed over time,
with reference lines showing exactly where the EPA's official risk categories begin and end.

#### `app/pages/2_Alerts.py`

The page that most directly answers Meridian Logistics' original question: a sortable list of every
location currently at or above a chosen risk level, with a button to download the list as a spreadsheet
(CSV) file — the actual "who do I need to worry about today" action list.

#### `app/utils/data.py` — the most architecturally important file in this phase

This file decides **where the dashboard's data actually comes from**, and it does something clever: it
checks whether a live database file exists on the computer running it.

- If yes (you're running this on your own laptop, right after the pipeline has run) — it queries that
  live database directly.
- If no (the dashboard has been deployed somewhere else, like a free hosting website, which has no access
  to your laptop's files) — it instead reads a set of Parquet files that were exported and saved into the
  project itself.

**Why this matters:** the free dashboard-hosting service this project is designed to deploy to
(Streamlit Community Cloud) cannot run a live, constantly-updating database. So instead, a scheduled job
refreshes those exported Parquet files periodically, and the deployed dashboard just reads whatever the
most recent export says — the same way a newspaper's website shows "as of this morning's print run"
information rather than updating every millisecond.

#### `app/utils/risk_tiers.py`

A small shared file listing the six official EPA risk categories (`Good`, `Moderate`, `Unhealthy for
Sensitive Groups`, `Unhealthy`, `Very Unhealthy`, `Hazardous`) and their official colors, so the map, the
trend charts, and the alert list all use exactly the same color for exactly the same meaning everywhere in
the app.

---

## 7. One Reading's Complete Journey — A Worked Example

The clearest way to understand this whole project is to follow one single, real measurement all the way
through every layer, watching exactly what changes and why.

**The starting fact:** a real PM2.5 sensor in New Delhi (OpenAQ sensor ID `811801`) measures **46.0 µg/m³**
at midnight UTC on June 29th.

| Step | What happens | The value at this point |
|---|---|---|
| 1. API response | OpenAQ's API returns this reading as one JSON object | `{"value": 46.0, "units": "µg/m³", ...}` |
| 2. Bronze | `extract_measurements.py` validates it and writes it, untouched, to a dated Parquet file | `46.0 µg/m³`, unchanged |
| 3. Raw (DuckDB) | `load_raw.py` copies it into a SQL table — **twice**, because an overlapping ingestion window re-pulled the same hour on a later day | Two rows, both `46.0` (or possibly a corrected value) |
| 4. Staging | `stg_openaq__measurements.sql` keeps only the most recently-pulled copy | One row: `46.0 µg/m³` |
| 5. AQI calculation | `calculate_aqi()` runs the real EPA formula for PM2.5 | `AQI = (46.0 − 35.5) × (150 − 101) ÷ (55.4 − 35.5) + 101 = 126.85 → rounds to 127` |
| 6. Mart | `fact_air_quality_hourly` buckets AQI 127 into a named risk category | `risk_tier = "Unhealthy for Sensitive Groups"` |
| 7. Dashboard | The City Trends page shows this exact point on a chart | An orange dot on the New Delhi PM2.5 trend line, tooltip reading "AQI 127" |

**Why this example is worth remembering:** every single number above was independently, mathematically
verified by hand during development — the same `46.0 → 127 → "Unhealthy for Sensitive Groups"` result shows
up correctly in the dbt models, in the Dagster-orchestrated pipeline test, and in the Streamlit dashboard's
own automated tests. All three layers agree with each other, which is exactly the kind of consistency a
well-built pipeline should have.

---

## 8. Testing Philosophy

Every layer of this project has its own kind of test, matched to what that layer actually needs to prove:

| Layer | Testing tool | What it proves |
|---|---|---|
| Ingestion (Phase 1) | `pytest`, with fake/mocked API responses | The pagination, retry, and validation logic works correctly, without needing a real internet connection |
| Storage (Phase 2) | `pytest`, against a real (temporary) DuckDB file | Loading logic behaves correctly against the real database engine, not just a simulated one |
| Transformation (Phase 3) | dbt's built-in test framework | The actual data meets real quality rules — no duplicates, no impossible values, correct relationships between tables |
| Orchestration (Phase 4) | `pytest`, materializing the entire Dagster pipeline | The whole pipeline — ingestion through dbt — actually runs correctly together, not just each piece in isolation |
| Dashboard (Phase 5) | Streamlit's own `AppTest` tool | Each page of the actual website runs without crashing and shows the correct numbers |

**As of the most recent build: 33 automated Python tests and 29 dbt tests, all passing**, runnable from a
completely fresh copy of the project with no manual setup steps required beyond installing dependencies.

---

## 9. Real Bugs Found and Fixed

Every one of these was a genuine mistake caught during development — not a hypothetical "here's what could
go wrong" — and each one is a good, honest example to bring up in an interview.

1. **A missing reading was silently scored as the worst possible air quality.** In SQL, comparing a blank
   value to a number (`NULL <= 12.0`) doesn't come back "true" or "false" — it comes back "unknown," which
   caused a completely blank sensor reading to fall through every real check in the AQI formula and land on
   the default "worst case" value of 500 ("Hazardous"). It should have shown as "no data available." This
   passed every existing automated test, because 500 is a technically *valid* AQI number — it just wasn't
   the *correct* one for this situation. It was only caught by manually reading through the actual output
   numbers rather than just checking that tests were green.

2. **A pipeline setting quietly relied on a value that was never actually being saved.** A "load only new
   data" feature checked a column that a "load everything from scratch" feature never actually created,
   which meant the "load only new data" mode would have failed with a confusing error the very first time
   someone used it for real.

3. **The database crashed with an ugly technical error instead of a friendly message.** Before the
   pipeline has ever been run on a brand-new computer, the final "clean" tables don't exist yet. The
   dashboard's original code didn't specifically expect that situation, so instead of showing "no data yet
   — here's how to fix that," it showed a raw, intimidating error message. This was found by an actual
   person running the project for the first time, not by an automated test — a good reminder that real
   users find real problems tests can miss.

4. **Some sensor data didn't get flattened the way it should have.** A common Python tool for converting
   nested data into a flat table only actually flattens a field if *at least one* row in a batch has real
   data in it. A batch where every single reading happened to be missing one particular optional field
   caused that field to be structured completely differently than expected, breaking a later step that
   assumed a consistent structure. Fixed by guaranteeing that field is *always* present in a consistent
   shape, even when it's empty.

---

## 10. How to Run Everything

**One-time setup:**
```bash
python3.12 -m venv .venv          # this project needs Python 3.11 or 3.12, not the newest release
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # then edit .env and add your free OpenAQ API key
```

**Run the pipeline once, manually, to see real output:**
```bash
python -m ingestion.extract_locations
python -m ingestion.extract_measurements
python -m warehouse.load_raw

cd dbt_project
cp profiles.yml.example profiles.yml
export DBT_PROFILES_DIR=$(pwd)
dbt run --select staging intermediate
dbt snapshot
dbt run
cd ..
```

**Or run everything automatically, on a schedule, through Dagster:**
```bash
export DAGSTER_HOME=/some/folder/you/create
export PYTHONPATH=.
dagster dev -m orchestration.definitions
```

**See the dashboard:**
```bash
export PYTHONPATH=.
streamlit run app/streamlit_app.py
```

**Run every automated test:**
```bash
pytest tests/ -v
```

*(Full troubleshooting notes for common setup problems — Python version conflicts, path issues, and
similar — are in the project's `README.md`.)*

---

## 11. Glossary

**Term** | **Plain-English meaning**
---|---
**API** | A way for one computer program to ask another program (usually over the internet) for data
**Pagination** | Getting a large set of results back a "page" at a time instead of all at once
**Bronze / Raw / Staging / Marts** | Names for the increasingly clean stages data passes through, from "exactly as received" to "polished and ready to use"
**Pydantic** | A Python tool for describing exactly what shape a piece of data should have, and rejecting it loudly if it doesn't match
**DuckDB** | A real SQL database that lives in a single file on your computer, with no server needed
**dbt** | A tool for writing data transformations as SQL, with automatic testing and dependency tracking built in
**SQL** | The standard language used to ask questions of a database ("show me every row where...")
**Star schema** | A standard way of organizing a database into "fact" tables (numbers/events) and "dimension" tables (descriptions), designed to be fast and easy to query
**SCD Type 2** | A way of keeping the *history* of changes to something, instead of just overwriting old information
**Dagster** | A tool that runs a data pipeline's steps in the correct order, on a schedule, and tells you if something fails
**Asset (in Dagster)** | A named "thing that gets produced" by a pipeline step, like a specific database table
**Lineage** | A picture showing which steps in a pipeline depend on which other steps
**Streamlit** | A tool that turns a Python script into an interactive website with very little extra code
**AQI (Air Quality Index)** | A standardized 0-500 score, published by the US EPA, that converts raw pollution measurements into one easy-to-understand number and risk category
**µg/m³, ppm, ppb** | Different ways of measuring how much of a substance is present in the air — this project has to convert between them correctly
**Pytest** | The standard tool for writing and running automated tests in Python
**Regression test** | A test written specifically because something was once broken, to make sure it never quietly breaks the same way again
