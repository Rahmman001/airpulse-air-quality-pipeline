"""
Unit tests for warehouse.r2_storage.
"""

import duckdb
from warehouse import r2_storage


def test_r2_config_none_by_default(monkeypatch):
    """When R2 env vars are empty, get_r2_config returns None."""
    monkeypatch.delenv("R2_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)
    assert r2_storage.get_r2_config() is None
    assert r2_storage.is_r2_configured() is False


def test_r2_config_ignores_placeholder_values(monkeypatch):
    """Placeholder values like 'your_cloudflare_account_id' should not be treated as configured."""
    monkeypatch.setenv("R2_ACCOUNT_ID", "your_cloudflare_account_id")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "your_r2_access_key_id")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    assert r2_storage.get_r2_config() is None
    assert r2_storage.is_r2_configured() is False


def test_r2_config_parses_valid_credentials(monkeypatch):
    """Valid credentials return a formatted config dict with R2 S3 endpoint."""
    monkeypatch.setenv("R2_ACCOUNT_ID", "acc123456")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key_abc")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "sec_xyz")
    monkeypatch.setenv("R2_BUCKET_NAME", "my-lakehouse")

    cfg = r2_storage.get_r2_config()
    assert cfg is not None
    assert cfg["account_id"] == "acc123456"
    assert cfg["access_key_id"] == "key_abc"
    assert cfg["secret_access_key"] == "sec_xyz"
    assert cfg["bucket_name"] == "my-lakehouse"
    assert cfg["endpoint"] == "acc123456.r2.cloudflarestorage.com"
    assert r2_storage.is_r2_configured() is True


def test_configure_duckdb_r2_executes_successfully():
    """DuckDB correctly executes S3/R2 configuration via httpfs."""
    conn = duckdb.connect(":memory:")
    cfg = {
        "account_id": "test_account",
        "access_key_id": "test_key",
        "secret_access_key": "test_secret",
        "bucket_name": "test-bucket",
        "endpoint": "test_account.r2.cloudflarestorage.com",
    }
    bucket = r2_storage.configure_duckdb_r2(conn, cfg)
    assert bucket == "test-bucket"
    conn.close()


def test_sync_snapshots_fallback_to_local_when_unconfigured(monkeypatch):
    """sync_snapshots safely executes and falls back to local data/gold_snapshot."""
    monkeypatch.delenv("R2_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)

    results = r2_storage.sync_snapshots()
    assert isinstance(results, dict)
    assert "fact_daily_city_aqi" in results
    assert "dim_location" in results
    assert all(count > 0 for count in results.values())
