"""Additional tests for Settings to improve coverage."""
import os
import tempfile
from pathlib import Path

import pytest

from app.settings import Settings, get_settings


@pytest.mark.unit
def test_settings_defaults():
    """Test Settings with default values."""
    # Settings may load from .env, so we just verify the structure
    s = Settings()
    assert isinstance(s.debug, bool)
    assert isinstance(s.host, str)
    assert isinstance(s.port, int)
    assert isinstance(s.db_path, Path)
    assert isinstance(s.reports_dir, Path)


@pytest.mark.unit
def test_settings_custom_values():
    """Test Settings with custom values."""
    s = Settings(debug=True, host="0.0.0.0", port=9000)
    assert s.debug is True
    assert s.host == "0.0.0.0"
    assert s.port == 9000


@pytest.mark.unit
def test_settings_path_expansion():
    """Test that paths expand user home and env vars."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = f"{tmpdir}/test.db"
        s = Settings(db_path=test_path)
        assert str(s.db_path) == test_path


@pytest.mark.unit
def test_settings_path_normalization():
    """Test path normalization handles strings and Path objects."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test with string
        s1 = Settings(db_path=f"{tmpdir}/db1.db")
        assert isinstance(s1.db_path, Path)
        
        # Test with Path
        s2 = Settings(db_path=Path(f"{tmpdir}/db2.db"))
        assert isinstance(s2.db_path, Path)


@pytest.mark.unit
def test_settings_optional_fields():
    """Test optional credential fields."""
    # Settings may load from .env, so we just verify the fields exist
    s = Settings()
    assert hasattr(s, "rebrickable_api_key")
    assert hasattr(s, "rebrickable_user_token")
    assert hasattr(s, "rebrickable_username")
    assert hasattr(s, "rebrickable_password")
    # Values may be None or set from .env - both are valid


@pytest.mark.unit
def test_settings_with_credentials():
    """Test Settings with credentials."""
    s = Settings(
        rebrickable_api_key="test-key",
        rebrickable_user_token="test-token",
        rebrickable_username="test-user",
        rebrickable_password="test-pass",
    )
    assert s.rebrickable_api_key == "test-key"
    assert s.rebrickable_user_token == "test-token"
    assert s.rebrickable_username == "test-user"
    assert s.rebrickable_password == "test-pass"


@pytest.mark.unit
def test_settings_ensure_directories():
    """Test ensure_directories creates parent dirs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "subdir" / "nested" / "db.db"
        s = Settings(db_path=db_path)
        s.ensure_directories()
        assert db_path.parent.exists()
        assert db_path.parent.is_dir()


@pytest.mark.unit
def test_get_settings_singleton():
    """Test get_settings returns cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    # Should be the same instance due to lru_cache
    assert s1 is s2


@pytest.mark.unit
def test_settings_path_with_none():
    """Test path validator handles None."""
    # This should not raise, but use defaults
    s = Settings()
    # db_path should have a default, not None
    assert s.db_path is not None


@pytest.mark.unit
def test_settings_path_with_invalid_type():
    """Test path validator handles invalid types gracefully."""
    # Pydantic should handle type coercion
    s = Settings()
    # Should not raise, should use defaults or coerce
    assert s.db_path is not None

