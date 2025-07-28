"""SQLite-based data access layer for the LEGO inventory system.

This module manages a simple SQLite database that stores LEGO parts and
inventory information. It exposes convenience functions for
initialising the database, inserting data and querying it for use in a
web interface. Only Python's standard library is used to ensure that
the application runs in environments without external package
dependencies.

Database schema
---------------

``parts``
    id INTEGER PRIMARY KEY
    part_number TEXT NOT NULL UNIQUE
    name TEXT NOT NULL

``inventory``
    id INTEGER PRIMARY KEY
    part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE
    colour TEXT NOT NULL
    quantity INTEGER NOT NULL
    status TEXT NOT NULL
    container TEXT
    drawer TEXT
    bin TEXT

Locations are represented by the combination of container, drawer and
bin. Any of these fields may be NULL if not applicable.
"""

from __future__ import annotations
from pathlib import Path
import sqlite3
from typing import Dict, List, Tuple, Optional

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "lego_inventory.db"

def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection.

    ``row_factory`` is set to ``sqlite3.Row`` to allow name-based column
    access like a dict. Callers should close the connection when
    finished.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create database tables if they do not already exist."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS parts (
                id INTEGER PRIMARY KEY,
                part_number TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY,
                part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
                colour TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT NOT NULL,
                container TEXT,
                drawer TEXT,
                bin TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def insert_part(part_number: str, name: str) -> int:
    """Insert a part and return its ID.

    If a part with the same part_number already exists, its ID is
    returned without inserting a duplicate.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM parts WHERE part_number = ?", (part_number,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO parts (part_number, name) VALUES (?, ?)", (part_number, name))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def insert_inventory(
    part_id: int,
    colour: str,
    quantity: int,
    status: str,
    container: Optional[str] = None,
    drawer: Optional[str] = None,
    bin_name: Optional[str] = None,
) -> int:
    """Insert an inventory record and return its ID."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO inventory (part_id, colour, quantity, status, container, drawer, bin)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (part_id, colour, quantity, status, container, drawer, bin_name),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_parts_with_totals() -> List[Dict]:
    """Return a list of parts with their total quantity across all inventory records.

    Each list item is a dict with keys ``id``, ``part_number``, ``name`` and
    ``total_quantity``. Parts with no inventory records are included with
    ``total_quantity`` set to 0.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.id, p.part_number, p.name, IFNULL(SUM(i.quantity), 0) AS total_quantity
            FROM parts p
            LEFT JOIN inventory i ON i.part_id = p.id
            GROUP BY p.id
            ORDER BY p.part_number
            """
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_inventory_records_by_part(part_id: int) -> List[Dict]:
    """Return all inventory records for a given part ID.

    Records are returned as dicts with keys ``colour``, ``quantity``, ``status``,
    ``container``, ``drawer`` and ``bin``. Results are ordered by colour,
    status and location.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT colour, quantity, status, container, drawer, bin
            FROM inventory
            WHERE part_id = ?
            ORDER BY colour, status, container, drawer, bin
            """,
            (part_id,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_part(part_id: int) -> Optional[Dict]:
    """Return a single part by ID or ``None`` if not found."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, part_number, name FROM parts WHERE id = ?", (part_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_locations_map() -> Dict[Tuple[Optional[str], Optional[str], Optional[str]], List[Dict]]:
    """Group inventory records by location and return a mapping.

    The keys of the returned dict are (container, drawer, bin) tuples.
    The values are lists of dicts with keys ``part_id``, ``part_number``, ``name``,
    ``colour`` and ``quantity`` for the aggregated quantities at that location.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                i.container,
                i.drawer,
                i.bin,
                p.id AS part_id,
                p.part_number,
                p.name,
                i.colour,
                SUM(i.quantity) AS quantity
            FROM inventory i
            JOIN parts p ON p.id = i.part_id
            GROUP BY i.container, i.drawer, i.bin, p.id, i.colour
            ORDER BY i.container, i.drawer, i.bin, p.part_number, i.colour
            """
        )
        locations: Dict[Tuple[Optional[str], Optional[str], Optional[str]], List[Dict]] = {}
        for row in cur.fetchall():
            key = (row["container"], row["drawer"], row["bin"])
            if key not in locations:
                locations[key] = []
            locations[key].append(
                {
                    "part_id": row["part_id"],
                    "part_number": row["part_number"],
                    "name": row["name"],
                    "colour": row["colour"],
                    "quantity": row["quantity"],
                }
            )
        return locations
    finally:
        conn.close()


def search_parts(query: str) -> List[Dict]:
    """Search parts by part number or name and return parts with totals.

    The search is case-insensitive and matches if the query string
    appears anywhere in the part number or name. Returns a list of
    dicts with the same structure as ``get_parts_with_totals()``.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        pattern = f"%{query}%"
        cur.execute(
            """
            SELECT p.id, p.part_number, p.name, IFNULL(SUM(i.quantity), 0) AS total_quantity
            FROM parts p
            LEFT JOIN inventory i ON i.part_id = p.id
            WHERE p.part_number LIKE ? OR p.name LIKE ?
            GROUP BY p.id
            ORDER BY p.part_number
            """,
            (pattern, pattern),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
