from pathlib import Path

from src.app.settings import Settings


def test_settings_expand_user_and_env_with_str(tmp_path):
    # Use a path string to exercise the validator's str/Path branch
    db = str(tmp_path / "db.sqlite")
    reports = str(tmp_path / "reports")
    s = Settings(db_path=db, reports_dir=reports)  # type: ignore[arg-type]
    assert isinstance(s.db_path, Path)
    assert isinstance(s.reports_dir, Path)
    assert s.db_path == Path(db)
    assert s.reports_dir == Path(reports)


def test_settings_expand_user_and_env_else_branch():
    # Call the validator directly with a non-str/non-Path to exercise the "else: return v" path
    val = Settings._expand_user_and_env(None)  # type: ignore[attr-defined]
    assert val is None


def test_ensure_directories_creates_parent_dirs(tmp_path):
    # Point to nested, non-existent directories and ensure they're created
    db_path = tmp_path / "nested" / "more" / "db.sqlite"
    reports_dir = tmp_path / "out" / "reports"
    s = Settings(db_path=db_path, reports_dir=reports_dir)
    # Should create parent directories idempotently
    s.ensure_directories()
    assert db_path.parent.exists() and db_path.parent.is_dir()
    assert reports_dir.exists() and reports_dir.is_dir()


def test_env_prefix_loading_overrides(monkeypatch, tmp_path):
    # Ensure env vars with APP_ prefix are honored
    env_db = tmp_path / "env_db.sqlite"
    env_reports = tmp_path / "env_reports"
    monkeypatch.setenv("APP_DB_PATH", str(env_db))
    monkeypatch.setenv("APP_REPORTS_DIR", str(env_reports))

    s = Settings()
    assert s.db_path == env_db
    assert s.reports_dir == env_reports
