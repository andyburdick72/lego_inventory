import os
import sys

import pytest

# Ensure repo root and 'src/' are on sys.path for imports like 'from src.core import enums'
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_SRC_PATH = os.path.join(_REPO_ROOT, "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)


API_ENV_VAR = "API_BASE_URL"


def pytest_addoption(parser):
    parser.addoption(
        "--api-base-url",
        action="store",
        default=None,
        help="Override base URL for contract tests (e.g. http://localhost:8000/api)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "contract: mark a test as a contract test")


@pytest.fixture(scope="session")
def api_base_url(pytestconfig):
    # Priority: CLI flag > env var > None (contract tests will skip)
    cli = pytestconfig.getoption("--api-base-url")
    if cli:
        return cli
    return os.environ.get(API_ENV_VAR)


@pytest.fixture
def skip_if_no_api(api_base_url):
    if not api_base_url:
        pytest.skip(
            f"Skipping contract tests: {API_ENV_VAR} is unset and --api-base-url not provided"
        )
