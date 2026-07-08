"""
The dbt project, as Dagster sees it.

`DbtProject.prepare_if_dev()` is what makes this self-healing in local dev:
`@dbt_assets` needs a manifest.json to already exist on disk at the moment
Dagster loads this module -- but a fresh clone of this repo won't have one
yet. `prepare_if_dev()` runs `dbt deps` + regenerates the manifest the first
time `dagster dev` starts (and again on every reload), so there's no manual
"remember to run dbt parse first" step for anyone picking this project up.

It's a no-op outside of `dagster dev` (e.g. in a real deployment you'd bake
an already-prepared manifest into your deployment artifact instead).
"""

import sys
from pathlib import Path

from dagster_dbt import DbtCliResource, DbtProject

from ingestion.config import PROJECT_ROOT

DBT_PROJECT_DIR = PROJECT_ROOT / "dbt_project"

# prepare_if_dev() (below) needs profiles.yml to already exist -- it doesn't
# create one itself, and this dbt project's profile has no real credentials
# (just a DuckDB file path), so there's no reason to make a fresh clone find
# this out via a confusing pydantic ValidationError instead. Same file the
# README asks a human to `cp` manually; never overwrites a customized one.
_profiles_yml = DBT_PROJECT_DIR / "profiles.yml"
if not _profiles_yml.exists():
    _profiles_yml.write_text((DBT_PROJECT_DIR / "profiles.yml.example").read_text())

airpulse_dbt_project = DbtProject(
    project_dir=DBT_PROJECT_DIR,
    profiles_dir=DBT_PROJECT_DIR,
)
airpulse_dbt_project.prepare_if_dev()

_active_python_dbt = Path(sys.executable).with_name("dbt")
_project_venv_dbt = PROJECT_ROOT / ".venv" / "bin" / "dbt"
_dbt_executable = next(
    (str(path) for path in (_active_python_dbt, _project_venv_dbt) if path.exists()),
    "dbt",
)
dbt_resource = DbtCliResource(
    project_dir=airpulse_dbt_project,
    dbt_executable=_dbt_executable,
)
