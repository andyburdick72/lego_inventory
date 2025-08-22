import importlib
import inspect

import src.core.utils.common_functions as cf
from src.app.settings import get_settings as app_get_settings


def test_common_functions_exports_get_settings():
    # Module should expose get_settings and re-export it from app.settings
    assert hasattr(cf, "get_settings"), "common_functions should export get_settings"
    assert callable(cf.get_settings)

    # Compare the underlying function targets (handle decorators and dual import paths)
    base_cf = inspect.unwrap(cf.get_settings)
    base_app = inspect.unwrap(app_get_settings)

    allowed_modules = {"app.settings", "src.app.settings"}
    assert base_cf.__name__ == base_app.__name__ == "get_settings"
    assert base_cf.__module__ in allowed_modules
    assert base_app.__module__ in allowed_modules

    # Sanity check that both callables return the same Settings *shape*
    val1 = cf.get_settings()
    val2 = app_get_settings()
    cls1 = type(val1)
    cls2 = type(val2)
    assert cls1.__name__ == cls2.__name__ == "Settings"
    assert cls1.__module__ in allowed_modules
    assert cls2.__module__ in allowed_modules


def test_common_functions___all__contains_get_settings():
    all_attr = getattr(cf, "__all__", None)
    if all_attr is not None:
        assert "get_settings" in all_attr


def test_common_functions_import_fresh_module():
    # Ensure import path is correct and module reload works without side effects
    m = importlib.reload(cf)
    assert inspect.ismodule(m)
    assert hasattr(m, "get_settings") and callable(m.get_settings)
