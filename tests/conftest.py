import os
import sys

# Ensure 'src/' is in sys.path for imports like 'from core import enums'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "contract: mark a test as a contract test")


@pytest.fixture
def api_base_url():
    return "http://localhost:8000/api"
