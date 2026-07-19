"""
Session-wide test setup.

orchestration/assets/dbt_assets.py needs dbt_project/target/manifest.json to
already exist at IMPORT time -- dagster-dbt's @dbt_assets decorator reads it
eagerly. DbtProject.prepare_if_dev() (see orchestration/project.py) handles
this automatically inside a real `dagster dev` process, but deliberately
does nothing outside of it -- so a fresh clone's first `pytest tests/` would
otherwise fail with a confusing DagsterDbtManifestNotFoundError that gives
no hint that the fix is "run dbt parse first."

This fixture makes the test suite self-sufficient the same way `dagster dev`
already is: generate the manifest once per test session if it doesn't exist.
`dbt parse` is a cheap, no-execution static-analysis step (it doesn't need
the actual DuckDB tables to exist), so this adds negligible overhead.
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt_project"
MANIFEST_PATH = DBT_PROJECT_DIR / "target" / "manifest.json"


def dbt_command() -> list[str]:
    venv_dbt = Path(sys.executable).with_name("dbt")
    if venv_dbt.exists():
        return [str(venv_dbt)]
    return ["dbt"]


@pytest.fixture(scope="session", autouse=True)
def ensure_dbt_manifest_exists():
    if not MANIFEST_PATH.exists():
        profiles_yml = DBT_PROJECT_DIR / "profiles.yml"
        if not profiles_yml.exists():
            # Same file the README asks a human to `cp` manually -- doing it
            # here too just means the test suite doesn't depend on someone
            # having followed that step first. Never overwrites an existing
            # (possibly customized) profiles.yml.
            profiles_yml.write_text((DBT_PROJECT_DIR / "profiles.yml.example").read_text())

        subprocess.run(
            [*dbt_command(), "parse"],
            cwd=DBT_PROJECT_DIR,
            env={**os.environ, "DBT_PROFILES_DIR": str(DBT_PROJECT_DIR)},
            check=True,
        )
    yield
