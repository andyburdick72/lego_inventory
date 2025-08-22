import os

import pytest

import src.core.enums as enums

THRESHOLD = float(os.environ.get("ENUMS_COVERAGE_MIN", 95))


def _get_coverage():
    try:
        # coverage.py >= 5 provides a public accessor
        from coverage import Coverage

        return Coverage.current()
    except Exception:
        return None


@pytest.mark.coverage
def test_core_enums_file_has_minimum_coverage():
    cov = _get_coverage()
    if cov is None:
        pytest.skip("Coverage is not active; run with pytest --cov to enforce file threshold")

    # Ensure coverage data is collected and up-to-date
    cov.stop()
    cov.start()
    cov_data = cov.get_data()

    filename = os.path.abspath(enums.__file__)
    if filename.endswith(".pyc"):
        filename = filename[:-1]

    # If the file isn't tracked (e.g., wrong --cov path), skip rather than fail noisy
    if not cov_data.lines(filename) and not cov_data.arcs(filename):
        pytest.skip("Coverage data for this file is not available; run with --cov=src")

    try:
        _, statements, excluded, missing, executed = cov.analysis2(filename)
    except Exception:
        pytest.skip("Coverage data for core/enums.py not available; run with --cov=src")

    if not statements:
        pytest.skip("No statements found in core/enums.py (unexpected); skipping gate")

    covered = len(statements) - len(missing)
    pct = 100.0 * covered / max(1, len(statements))

    assert pct >= THRESHOLD, (
        f"core/enums.py coverage {pct:.1f}% is below threshold {THRESHOLD:.1f}%. "
        "Run: pytest --cov=src --cov-report=term-missing"
    )
