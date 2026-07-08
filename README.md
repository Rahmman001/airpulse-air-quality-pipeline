# AirPulse — Global Air Quality Risk Intelligence Platform

**Status: All six phases complete — environment, ingestion, DuckDB storage, dbt models, Dagster
orchestration, Streamlit dashboard, and CI/CD + deployment. Tested end to end, including a real deployment
validation (see Phase 6 below).**

## What's here right now

```
airpulse-air-quality-pipeline/
├── .github/workflows/
│   ├── ci.yml                    # lint + full test suite on every PR/push
│   └── scheduled_refresh.yml    # every 6h: pull data, rebuild, commit refreshed gold snapshot
├── ingestion/
│   ├── openaq_client.py       # paginated, rate-limit-aware, retrying OpenAQ v3 client
│   ├── schemas.py              # pydantic models matching the real OpenAQ v3 response shapes
│   ├── config.py                # target countries, lookback window, paths
│   ├── extract_locations.py    # -> data/bronze/locations/ingest_date=YYYY-MM-DD/
│   └── extract_measurements.py # -> data/bronze/measurements/ingest_date=YYYY-MM-DD/
├── warehouse/
│   ├── db.py                    # DuckDB connection helper (airpulse.duckdb)
│   └── load_raw.py             # bronze Parquet -> raw.locations / raw.measurements
├── dbt_project/
│   ├── models/
│   │   ├── staging/            # clean, rename, flatten nested JSON, dedupe
│   │   ├── intermediate/       # unit normalization + AQI calculation
│   │   └── marts/              # star schema: fact_air_quality_hourly, fact_daily_city_aqi, dims
│   ├── snapshots/
│   │   └── dim_location_snapshot.sql  # SCD Type 2 for location metadata
│   ├── macros/
│   │   ├── convert_units.sql   # ppm/ppb <-> ug/m3, and EPA-AQI-unit normalization
│   │   └── calculate_aqi.sql   # EPA breakpoint piecewise-linear AQI formula
│   └── tests/                  # singular data quality tests
├── orchestration/
│   ├── project.py               # DbtProject + DbtCliResource, self-preparing on a fresh clone
│   ├── definitions.py           # the Definitions object `dagster dev` loads
│   ├── schedules.py             # runs the full pipeline every 6 hours
│   ├── sensors.py               # run-failure alerting
│   ├── asset_checks.py          # operational freshness check (distinct from dbt's correctness tests)
│   └── assets/
│       ├── ingestion_assets.py # raw_locations, raw_measurements, raw_schema_loaded as Dagster assets
│       └── dbt_assets.py       # the entire dbt project as assets, generated from dbt's manifest
├── app/
│   ├── streamlit_app.py         # main dashboard: KPIs + global risk map
│   ├── requirements.txt        # lightweight deps for the DEPLOYED app only (no dbt/Dagster)
│   ├── pages/
│   │   ├── 1_City_Trends.py    # per-location/pollutant AQI history with EPA threshold lines
│   │   └── 2_Alerts.py         # ops watch list, sortable, CSV export
│   └── utils/
│       ├── data.py              # dual-mode data layer: live DuckDB or committed Parquet snapshot
│       └── risk_tiers.py       # shared EPA AQI color scale, used consistently everywhere
├── scripts_dev/
│   └── generate_fake_bronze.py # synthetic bronze fixtures for testing without a live API key
└── tests/
    ├── conftest.py                  # auto-generates the dbt manifest so `pytest` just works on a fresh clone
    ├── test_openaq_client.py       # pagination / throttling / retry logic, fully mocked
    ├── test_schemas.py             # validates our models against real OpenAQ example payloads
    ├── test_extract_integration.py # runs the extract scripts end-to-end against a mocked client
    ├── test_load_raw.py            # bronze -> DuckDB loading, against real (temp) Parquet + DuckDB files
    ├── test_orchestration.py       # materializes the ENTIRE Dagster asset graph end-to-end
    └── test_streamlit_app.py       # headless dashboard tests via Streamlit's AppTest, both data modes
```

33 Python tests (pytest) + 29 dbt tests, all passing, all runnable from a genuinely fresh clone with zero manual setup steps.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and paste in your free key from https://explore.openaq.org/register
```

## Run the tests

```bash
python -m pytest tests/ -v
```

## Run the real pipeline against the live API

```bash
# Pull location + sensor metadata for the configured countries (see ingestion/config.py)
python -m ingestion.extract_locations

# Pull the last 3 days of hourly measurements for every sensor found above
python -m ingestion.extract_measurements

# Quick smoke test against a handful of sensors instead of the full set
python -m ingestion.extract_measurements --limit-sensors 10
```

This will populate `data/bronze/locations/...` and `data/bronze/measurements/...` as
partitioned Parquet (bronze layer is gitignored — it's regenerable from the API).

**Heads up on runtime:** with 8 target countries, `extract_locations` typically returns a few
hundred to low thousands of locations, each with multiple sensors. `extract_measurements` calls
`/v3/sensors/{id}/hours` once per sensor (paginated), and the client self-throttles to stay under
OpenAQ's 60 requests/minute limit — so a full run across every sensor can take a while. Use
`--limit-sensors` while you're iterating, and drop `TARGET_COUNTRY_ISO_CODES` in `ingestion/config.py`
down to 1–2 countries for your first end-to-end run.

## Load bronze into DuckDB (Phase 2)

Once you've run the extract scripts at least once:

```bash
python -m warehouse.load_raw
```

This creates `airpulse.duckdb` in the project root (gitignored — it's fully rebuildable from bronze)
with two tables: `raw.locations` and `raw.measurements`. Every row is tagged with `_source_file` so you
can always trace a row back to the exact ingestion run that produced it.

Two modes are supported:

```bash
python -m warehouse.load_raw                    # full refresh: rebuild raw tables from all of bronze
python -m warehouse.load_raw --mode incremental  # only load ingest_date partitions newer than what's loaded
```

Full refresh is what you'll use day-to-day at this project's data volume — it's simple and always
correct. Incremental append is there mainly as a "how would this scale" answer for interviews once
bronze accumulates enough history that re-reading everything gets slow.

Poke around the result:

```bash
python -c "
from warehouse.db import get_connection
conn = get_connection(read_only=True)
print(conn.execute('SELECT COUNT(*) FROM raw.locations').fetchone())
print(conn.execute('SELECT * FROM raw.measurements LIMIT 5').fetchdf())
conn.close()
"
```

**A design note worth remembering for interviews:** `load_raw.py` deliberately does *not*
deduplicate rows or clean anything — it just gets bronze Parquet into queryable SQL tables. Raw stays
raw. Cleaning, deduping on the real business key (`sensor_id` + timestamp), unit conversion, and AQI
calculation all belong in dbt (Phase 3), so that transformation logic lives in one place, is testable,
and is fully re-runnable without ever re-hitting the API.

## Build the dimensional model (Phase 3)

Install dbt if you haven't already (it's in `requirements.txt`), then:

```bash
cd dbt_project
cp profiles.yml.example profiles.yml
export DBT_PROFILES_DIR=$(pwd)
```

**Run order matters here, and it's a real, well-known dbt gotcha worth knowing:** the SCD2 snapshot
queries `stg_openaq__locations`, which has to already exist as a database object before `dbt snapshot`
can select from it. `dbt run` does **not** run snapshots automatically. So the correct sequence — every
time, not just the first time — is:

```bash
dbt run --select staging intermediate   # build everything upstream of the snapshot
dbt snapshot                             # capture the current state of dim_location_snapshot
dbt run                                  # build the marts, including dim_location, which depends on the snapshot
dbt test                                 # 29 tests: schema tests + singular data quality tests
```

In Phase 4, Dagster will enforce this ordering for you automatically — the manual sequence above is
exactly the kind of thing an orchestrator exists to take off your hands.

Don't have real data yet? Generate realistic synthetic fixtures instead (this is what I used to build
and test the whole dbt project before ever touching a live API key):

```bash
cd ..  # back to the project root
PYTHONPATH=. python scripts_dev/generate_fake_bronze.py
PYTHONPATH=. python -m warehouse.load_raw
```

Explore the result:

```bash
python -c "
from warehouse.db import get_connection
conn = get_connection(read_only=True)
print(conn.execute('SELECT * FROM mart.fact_daily_city_aqi').fetchdf())
conn.close()
"
```

Or generate the docs site (lineage graph + column-level documentation):

```bash
cd dbt_project && export DBT_PROFILES_DIR=$(pwd) && dbt docs generate && dbt docs serve
```

**Two real bugs worth knowing about, both caught while building this (not left in on purpose, and both
now covered by regression tests):**

1. `warehouse/load_raw.py`'s incremental-append mode referenced a column that full-refresh mode never
   actually created — would have thrown "column does not exist" the moment anyone used it against a
   table that already had data. Fixed by using DuckDB's automatic hive-partitioning inference (it
   derives a real, typed `ingest_date` column from the `ingest_date=YYYY-MM-DD` folder names for free).
2. `calculate_aqi()` computed **AQI = 500 ("Hazardous") for a missing/null reading**, instead of a null
   AQI — because `NULL <= 12.0` evaluates to `NULL` in SQL, not `true`, so a null input silently fell
   through every breakpoint bracket to the final `else 500` catch-all. Every automated test still passed
   (500 is technically a valid AQI value, so the 0-500 range check couldn't catch it) — this one only
   surfaced from actually reading the output rows, which is the reason to always eyeball real numbers
   and not just trust green tests.

**Known simplifications, stated on purpose (great interview material, not things to hide):**
- AQI is computed per hourly reading, not over the EPA's official rolling windows (24-hr for PM, 8-hr
  for O3). It's an hourly approximation, documented as such in `calculate_aqi.sql`.
- `fact_air_quality_hourly` joins to the *current* version of `dim_location` rather than the version
  that was valid at the time of the reading — true point-in-time SCD2 joins are more involved, and the
  tradeoff is documented directly in the model's SQL comments.
- Bronze-layer flattening (via pandas `json_normalize`) only produces a `field__subfield` column when at
  least one row in a batch has that nested field populated — a batch where a field is null for every row
  produces a different raw schema than one where it's populated. Worth knowing about even though the
  synthetic fixtures no longer exercise this edge case (see `scripts_dev/generate_fake_bronze.py` for the
  full story). A more production-hardened bronze layer would enforce an explicit schema on write instead
  of relying on pandas' automatic inference.

## Orchestrate everything with Dagster (Phase 4)

```bash
export DAGSTER_HOME=/some/persistent/directory   # create it if it doesn't exist
export PYTHONPATH=.
mkdir -p "$DAGSTER_HOME"
dagster dev -m orchestration.definitions
```

Open the URL it prints (defaults to `http://localhost:3000`). You'll see the full asset graph: the two
ingestion assets, the DuckDB raw-load step, and every single dbt model/snapshot as its own node — all
generated automatically from dbt's own manifest, so Dagster's lineage graph can never drift out of sync
with the actual dbt project.

**The biggest payoff of this phase:** Phase 3's README documented a manual three-step run order
(`dbt run --select staging` → `dbt snapshot` → `dbt run`) because `dbt run` doesn't execute snapshots.
`orchestration/assets/dbt_assets.py` runs `dbt build` instead, which handles models, snapshots, and tests
together in correct dependency order automatically — so that manual sequence is no longer something
anyone needs to remember. That's the concrete difference between "a script" and "an orchestrator."

Click "Materialize all" in the UI to run the whole pipeline against your real OpenAQ key, or use the
schedule (every 6 hours, defined in `orchestration/schedules.py`) to run it automatically.

**Three real things worth knowing about, found while building this phase:**

1. **`from __future__ import annotations` breaks Dagster's decorators.** Every other Python file in this
   project uses that import as a style default, but Dagster's `@asset`/`@dbt_assets` decorators do
   runtime introspection on the `context` parameter's type — which fails when postponed evaluation turns
   the annotation into a string instead of the actual class. Every file under `orchestration/` omits this
   import for exactly that reason.
2. **dbt's `source()` references need asset keys that match exactly.** dagster-dbt automatically expects
   `stg_openaq__locations`'s `{{ source('raw', 'locations') }}` reference to be satisfied by an asset
   keyed `AssetKey(["raw", "locations"])` — not any name you happen to pick. `raw_schema_loaded` is a
   `@multi_asset` (not two separate `@asset`s) specifically so one `load_all()` call can present as the
   two precisely-keyed outputs (`raw/locations`, `raw/measurements`) dbt's lineage expects.
3. **A second real bug in the ingestion schema, caught by Phase 4's own test fixtures**: `Coverage` and
   `Summary` used to be `Optional[...] = None` on `HourlyData`. A test batch where every record legitimately
   lacked coverage data (some OpenAQ providers just don't report it) meant pandas' `json_normalize` never
   split it into `coverage__percentCoverage` etc. — producing a flat `coverage` column instead and breaking
   dbt with a real "column not found" error. Fixed in `ingestion/schemas.py` by giving `summary`/`coverage`
   a `default_factory` so they're always serialized as objects (with null sub-fields when genuinely absent),
   while `period.datetimeFrom` was made a *required* field instead — a reading's timestamp isn't optional
   metadata the way coverage stats are, so a record missing one should fail loudly at validation, not
   silently produce a null downstream.

**Also worth knowing:** both `tests/conftest.py` (for `pytest`) and `orchestration/project.py`'s
`prepare_if_dev()` (for `dagster dev`) auto-generate `dbt_project/profiles.yml` from the `.example`
template and the dbt manifest if either is missing — so a genuinely fresh clone of this repo needs zero
manual dbt setup before either the test suite or `dagster dev` will run. This was tested for real, not
assumed: both were run from a state with `profiles.yml` and `dbt_project/target/` deleted entirely.

**Sensors and asset checks:** `orchestration/sensors.py` has a run-failure sensor (logs loudly; the
production version is a few added lines posting to a Slack webhook, shown commented out).
`orchestration/asset_checks.py` has a freshness check on `raw/measurements` — deliberately *not* a dbt
test, since dbt tests check data correctness while "is the pipeline keeping up operationally" is squarely
an orchestration concern.

## The dashboard (Phase 5)

```bash
export PYTHONPATH=.
streamlit run app/streamlit_app.py
```

Three pages (Streamlit's `pages/` convention puts the extra two in the sidebar automatically):

- **Home** (`app/streamlit_app.py`) — top-line KPIs, a global risk map (pydeck, colored by EPA risk
  tier), and today's worst-affected locations
- **City Trends** (`app/pages/1_City_Trends.py`) — pick any location + pollutant, see the AQI trend
  over time with EPA breakpoint reference lines
- **Alerts** (`app/pages/2_Alerts.py`) — the actual answer to this project's business question: every
  location currently at or above a chosen risk tier, with CSV export

**The dual-mode data layer is the one design decision worth understanding here.** `app/utils/data.py`
checks whether `airpulse.duckdb` exists locally: if so, it queries it live (read-only); if not, it reads
committed Parquet files from `data/gold_snapshot/` instead, using an in-memory DuckDB connection that can
query Parquet directly with the same SQL either way. This is what makes the "hybrid deployment" pattern
from Phase 3's README real rather than aspirational: Streamlit Community Cloud can't run a persistent
Dagster process or see your local `airpulse.duckdb` (it's gitignored), so the deployed app reads whatever
`python -m warehouse.export_gold_snapshot` last committed — refreshed on a schedule by Phase 6's GitHub
Actions job. **This was tested for real**: I deleted the live `.duckdb` file entirely and confirmed the
app produced identical, correct output from the Parquet snapshot alone (see
`tests/test_streamlit_app.py::test_dashboard_works_in_snapshot_mode_with_no_live_duckdb_file`).

Export a snapshot yourself with:

```bash
python -m warehouse.export_gold_snapshot
```

**Two real bugs caught while building this, both via Streamlit's own headless `AppTest` framework** (it
actually runs each page and inspects what renders — not just a syntax check):

1. `pd.cut()` returns a pandas `Categorical` column, and calling `.map()` on it with a dict whose values
   are lists (RGB triples, for the map's marker colors) throws `TypeError: unhashable type: 'list'` —
   categorical `.map()` internally requires hashable mapped values, a restriction plain object-dtype
   columns don't have. Fixed by casting to a plain string with `.astype(str)` right after `pd.cut()`.
2. `use_container_width=True` is deprecated in the installed Streamlit version in favor of
   `width='stretch'` — cheap to fix now, before it's a breaking change later.

**A third bug, caught after initial delivery — this one by an actual person running the app on a fresh
machine, not by a test:** before the pipeline has ever been run, `mart.fact_daily_city_aqi` doesn't exist
at all, and DuckDB raised a raw `CatalogException` that crashed the app with a stack trace instead of the
intended "no data yet" warning. Fixed in `app/utils/data.py::_query` by catching that specific exception
and returning an empty DataFrame — which the page-level `.empty` checks already knew how to handle, they
just never got the chance to run.

**A genuine architectural lesson, found while writing the regression test for the bug above:**
`st.cache_data`'s cache key is based on function identity + arguments — and every loader in
`app/utils/data.py` (`load_latest_city_aqi()`, `load_locations()`, etc.) takes **zero arguments**. Their
actual output depends on hidden external state (whether `airpulse.duckdb` exists, what's in it) that the
cache has no way to see. In the real deployed app this is harmless — `DB_PATH` is fixed for the lifetime
of one running process, it never changes mid-session. But a test that flips `DB_PATH` to prove both LIVE
and SNAPSHOT modes work (exactly what this project's tests do) has to explicitly `st.cache_data.clear()`
both before *and after* mutating that state, or it leaves a stale cached result for whichever test happens
to run next. `tests/test_streamlit_app.py` does this deliberately in both directions now, with the reasoning
documented inline — worth remembering if you ever add a test that changes what data source the app sees.

Every page is covered by a permanent regression test in `tests/test_streamlit_app.py`, including the
exact hand-verified AQI value (127, for the same New Delhi PM2.5 reading from the Phase 3 worked example)
showing up correctly in the City Trends drill-down.

## Setup troubleshooting (real issues hit running this on macOS)

A few environment problems came up getting this running for the first time on a real machine, worth
documenting since they'll likely bite the next person too:

- **Python 3.14 breaks both `streamlit` and `dbt`.** Both depend on packages (`protobuf`'s compiled
  extension for Streamlit; `mashumaro` for dbt) that don't support Python's newest release yet at time of
  writing. Use Python 3.11 or 3.12 for this project's virtual environment — not whatever `python3`
  defaults to on a fresh macOS install.
- **`source .venv/bin/activate` doesn't guarantee commands resolve to the venv.** On macOS/zsh, a command
  found earlier on `$PATH` (e.g. a Framework-installed global `streamlit` or `dbt`) can still win even
  with a venv active. If a traceback's file paths don't say `.venv/`, that's the tell. Force it with
  `python -m streamlit run ...`, or call the venv's binary by its full path directly
  (`.venv/bin/dbt run ...`) — note `dbt` itself has no `__main__.py`, so `python -m dbt` doesn't work the
  way `python -m streamlit` does; the full-path approach is the reliable one for dbt specifically.
- **dbt requires being run from inside `dbt_project/`.** It looks for `dbt_project.yml` in the current
  directory — running any `dbt` command from the repo root fails with "No dbt_project.yml found," which
  looks alarming but just means `cd dbt_project` first.

## CI/CD and deployment (Phase 6)

### Continuous integration

`.github/workflows/ci.yml` runs on every PR and every push to `main`: lint (`ruff`), format check
(`black`), and the full test suite. There's deliberately **no separate "run dbt build" step** — Phase 4
and 5's own integration tests (`test_orchestration.py`, `test_streamlit_app.py`) already run a full
`dbt build` (models, snapshot, and all 29 dbt tests) as part of proving the pipeline works end-to-end, so
`pytest tests/` alone already covers it. That's a direct payoff of investing in thorough tests earlier:
CI doesn't need to duplicate work those tests are already doing.

### Scheduled data refresh

`.github/workflows/scheduled_refresh.yml` is the free-tier substitute for a persistent orchestrator, first
described back in Phase 3's README: every 6 hours (matching `orchestration/schedules.py`), it pulls fresh
data from OpenAQ, rebuilds the pipeline, exports the mart tables to Parquet, and **commits that snapshot
back to the repo**. This is what the deployed dashboard actually reads.

To use it, add one repository secret: go to **Settings → Secrets and variables → Actions → New repository
secret**, name it `OPENAQ_API_KEY`, and paste in your free key.

I validated both workflows by running their exact steps locally (substituting the synthetic fixture
generator for the real API call, since I couldn't reach the live API from the sandbox this was built in) —
`ruff`, `black --check`, the full test suite, and a complete `dbt build` all pass clean, and the gold
snapshot export + git staging steps work exactly as the workflow expects.

### Deploying the dashboard to Streamlit Community Cloud

1. Push this repository to your own GitHub account (public repo — Community Cloud's free tier requires it).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub (free, no card).
3. Click **"New app"**, select your repo and branch, and set **Main file path** to `app/streamlit_app.py`.
4. Under **Advanced settings**, point the requirements file at `app/requirements.txt` — the lightweight
   dependency list (just `streamlit`, `duckdb`, `pandas`, `pydeck`, `altair`) rather than the root
   `requirements.txt`, which also has dbt/Dagster the deployed app never touches. I proved this
   distinction is real, not just tidiness: I installed `app/requirements.txt` into a completely fresh
   virtual environment with nothing else in it, deleted the live `airpulse.duckdb` file to force snapshot
   mode, and confirmed the dashboard still ran correctly using only that minimal environment.
5. Click **Deploy**. The first build takes a few minutes; after that, it reads whatever
   `data/gold_snapshot/` currently contains — which the scheduled workflow above keeps current.

## Design decisions and tradeoffs — the short version

Six phases in, here's the consolidated set of deliberate choices this project makes, and why — the kind
of thing worth having a crisp answer for in an interview:

- **DuckDB over a "real" warehouse.** Free, embedded, no server, genuine SQL engine, first-class dbt
  adapter. Tradeoff: single-writer concurrency, which is exactly why Streamlit never queries the live file
  directly in production — it reads a Parquet snapshot instead.
- **Dagster over Airflow.** Asset-based lineage maps 1:1 onto dbt models via `dagster-dbt`, so the entire
  dbt project became Dagster assets with zero manual bookkeeping. Airflow is an equally valid choice with a
  more task-based mental model — I'd be ready to discuss either.
- **`dbt build`, not `dbt run`.** `dbt run` never executes snapshots, which is why Phase 3 needed a manual
  three-step sequence. Once Dagster (Phase 4) runs `dbt build` instead, that sequencing problem disappears
  entirely — the concrete difference between "a script" and "an orchestrator."
- **Raw stays raw; staging does the cleaning.** `load_raw.py` never deduplicates or cleans anything — all
  of that logic lives in exactly one place (dbt's staging layer), so it's tested once and never duplicated.
- **SCD Type 2 for `dim_location`, not a plain overwrite.** Location metadata changes over time (renames,
  recalibrations); a snapshot keeps that history instead of silently discarding it. I didn't just trust
  this compiles — I simulated two separate pipeline runs and confirmed a renamed location produced a
  correctly closed-out old version and a new current one.
- **Hourly AQI approximation, not the EPA's official rolling windows.** True AQI uses 24-hour averages for
  particulates and 8-hour averages for ozone; this project applies the breakpoint formula per hourly
  reading instead, documented explicitly in `calculate_aqi.sql` as a stated simplification, not a hidden one.
- **The dual-mode dashboard data layer.** One codebase, two data sources depending on whether a live
  DuckDB file exists — proven by literally deleting that file and confirming identical, correct output
  from the Parquet snapshot alone.
- **A lightweight `app/requirements.txt` separate from the root one.** The deployed dashboard doesn't need
  dbt or Dagster; shipping them anyway would only slow down Streamlit Cloud's build for no benefit.

## What's next (beyond these six phases)

- Great Expectations as a second, complementary data-quality layer
- Incremental dbt models once bronze accumulates enough history that a full rebuild gets slow
- A second data source (e.g. NOAA weather) to correlate pollution with weather patterns
- True point-in-time SCD2 joins in `fact_air_quality_hourly` (documented as a known simplification today)
- Slack webhook alerting from `orchestration/sensors.py` (the code is written, commented out, pending a
  real webhook secret)
