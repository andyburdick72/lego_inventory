import csv
import io
import urllib.parse

import pytest

pytestmark = pytest.mark.contract


def _read_csv_bytes(content: bytes):
    # Strip UTF-8 BOM if present
    text = content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


@pytest.mark.parametrize(
    "table,columns",
    [
        ("sets", ["id", "set_number", "name", "theme", "year", "num_parts", "status"]),
        ("drawers", ["id", "name", "location", "num_containers"]),
        ("containers", ["id", "name", "drawer_name", "num_parts"]),
    ],
)
def test_export_endpoint_ok(client, table, columns):
    # columns from UI order ->
    cols_str = ",".join(columns)
    url = f"/export?table={table}&columns={urllib.parse.quote(cols_str)}"
    r = client.get(url)
    assert r.status_code == 200
    # content type and attachment header
    assert r.headers.get("Content-Type", "").startswith("text/csv")
    assert "attachment; filename" in r.headers.get("Content-Disposition", "")

    # Validate BOM + CSV header order
    content = r.content
    assert content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    rows = _read_csv_bytes(content)
    assert rows, "CSV should not be empty"
    assert rows[0] == columns  # header equals requested order


def test_export_uses_defaults_when_no_columns(client):
    r = client.get("/export?table=sets")
    assert r.status_code == 200
    rows = _read_csv_bytes(r.content)
    assert rows[0] == ["id", "set_number", "name", "theme", "year", "num_parts", "status"]


def test_export_rejects_invalid_columns(client):
    r = client.get("/export?table=sets&columns=id,badcol,name")
    assert r.status_code == 400


def test_export_csv_quoting_and_utf8(client):
    # We can't guarantee a row with commas/quotes exists in fixtures,
    # but we can at least assert the file is valid CSV and BOM is present.
    r = client.get("/export?table=drawers&columns=id,name,location,num_containers")
    assert r.status_code == 200
    assert r.content.startswith(b"\xef\xbb\xbf")
    # Parse should not throw; rows present
    rows = _read_csv_bytes(r.content)
    assert len(rows) >= 1
