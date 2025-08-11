#!/usr/bin/env python3
"""
Sanity checks for LEGO inventory DB.

Checks:
1) Loose inventory parity:
   inventory(status='loose')  ≟  sum(set_parts) for sets with status='loose'

2) Local vs Rebrickable:
   local = loose inventory + set_parts for non-loose sets (built/wip/in_box/teardown)
   rebrickable = sum(set_parts for all owned sets)

Outputs:
- CSVs in data/reports/ with timestamped filenames
- Console rollups for quick verification

Usage:
  python3 src/inventory_sanity_checks.py
  python3 src/inventory_sanity_checks.py --db ./data/lego_inventory.db --reports-dir ./data/reports \
      --loose-statuses loose,teardown --counted-set-statuses built,wip,in_box
"""

import argparse
import csv
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

# Defaults assume this file lives in <repo>/scripts/sanity_checks.py
DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "lego_inventory.db"
DEFAULT_REPORTS_DIR = Path(__file__).resolve().parents[1] / "data" / "reports"

def _csv_to_list(s: str) -> List[str]:
    return [x.strip() for x in s.split(",") if x.strip()]

def _quote_list(items: List[str]) -> str:
    # naive quoting is fine for our limited status tokens
    return ",".join(f"'{i}'" for i in items)

def build_queries(loose_statuses: List[str], counted_statuses: List[str]) -> Tuple[str, str, str]:
    ls = _quote_list(loose_statuses) or "'loose'"
    cs = _quote_list(counted_statuses) or "'built','wip','in_box'"

    q_loose_parity = f'''
WITH inv AS (
  SELECT design_id, color_id, SUM(quantity) AS qty
  FROM inventory
  WHERE status = 'loose'
  GROUP BY design_id, color_id
),
loose_sets AS (
  SELECT sp.design_id, sp.color_id, SUM(sp.quantity) AS qty
  FROM set_parts sp
  JOIN sets s ON s.set_num = sp.set_num
  WHERE s.status IN ({ls})
  GROUP BY sp.design_id, sp.color_id
)
SELECT i.design_id, i.color_id, i.qty AS inv_qty, COALESCE(ls.qty,0) AS loose_sets_qty,
       i.qty - COALESCE(ls.qty,0) AS delta
FROM inv i
LEFT JOIN loose_sets ls ON ls.design_id = i.design_id AND ls.color_id = i.color_id
WHERE COALESCE(ls.qty,0) != i.qty
UNION ALL
SELECT ls.design_id, ls.color_id, COALESCE(i.qty,0) AS inv_qty, ls.qty AS loose_sets_qty,
       COALESCE(i.qty,0) - ls.qty AS delta
FROM loose_sets ls
LEFT JOIN inv i ON i.design_id = ls.design_id AND i.color_id = ls.color_id
WHERE i.design_id IS NULL
ORDER BY 1, 2;
'''.strip()

    q_local_vs_rb = f'''
WITH local AS (
  SELECT design_id, color_id, SUM(quantity) AS qty
  FROM inventory
  WHERE status = 'loose'
  GROUP BY design_id, color_id

  UNION ALL

  SELECT sp.design_id, sp.color_id, SUM(sp.quantity) AS qty
  FROM set_parts sp
  JOIN sets s ON s.set_num = sp.set_num
  WHERE s.status IN ({cs})
  GROUP BY sp.design_id, sp.color_id
),
local_sum AS (
  SELECT design_id, color_id, SUM(qty) AS qty
  FROM local
  GROUP BY design_id, color_id
),
rb_sum AS (
  SELECT sp.design_id, sp.color_id, SUM(sp.quantity) AS qty
  FROM set_parts sp
  GROUP BY sp.design_id, sp.color_id
)
SELECT l.design_id, l.color_id, l.qty AS local_qty, COALESCE(r.qty,0) AS rb_qty,
       l.qty - COALESCE(r.qty,0) AS delta
FROM local_sum l
LEFT JOIN rb_sum r ON r.design_id = l.design_id AND r.color_id = l.color_id
WHERE COALESCE(r.qty,0) != l.qty
UNION ALL
SELECT r.design_id, r.color_id, COALESCE(l.qty,0) AS local_qty, r.qty AS rb_qty,
       COALESCE(l.qty,0) - r.qty AS delta
FROM rb_sum r
LEFT JOIN local_sum l ON l.design_id = r.design_id AND l.color_id = r.color_id
WHERE l.design_id IS NULL
ORDER BY 1, 2;
'''.strip()

    q_rollups = f'''
SELECT 'loose_inv' AS which, COALESCE(SUM(quantity),0) AS qty
FROM inventory WHERE status='loose'
UNION ALL
SELECT 'sets_loose', COALESCE(SUM(sp.quantity),0)
FROM set_parts sp JOIN sets s ON s.set_num=sp.set_num WHERE s.status IN ({ls})
UNION ALL
SELECT 'sets_non_loose', COALESCE(SUM(sp.quantity),0)
FROM set_parts sp JOIN sets s ON s.set_num=sp.set_num WHERE s.status IN ({cs})
UNION ALL
SELECT 'rebrickable_all_sets', COALESCE(SUM(quantity),0) FROM set_parts;
'''.strip()

    return q_loose_parity, q_local_vs_rb, q_rollups

def run_query(conn: sqlite3.Connection, sql: str):
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql).fetchall()]

def write_csv(rows, path: Path):
    if not rows:
        # Write headers anyway for consistency
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

def fmt(n):
    return f"{n:,}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to sqlite DB (lego_inventory.db)")
    ap.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR, help="Directory to write CSV reports")
    ap.add_argument("--loose-statuses", default="loose,teardown",
                    help="Comma-separated set statuses to treat as 'loose' (default: loose,teardown)")
    ap.add_argument("--counted-set-statuses", default="built,wip,in_box",
                    help="Comma-separated set statuses to count toward in-sets (default: built,wip,in_box)")
    args = ap.parse_args()

    db_path = args.db
    reports_dir = args.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    loose_statuses = _csv_to_list(args.loose_statuses)
    counted_set_statuses = _csv_to_list(args.counted_set_statuses)
    Q_LOOSE_PARITY, Q_LOCAL_VS_RB, Q_ROLLUPS = build_queries(loose_statuses, counted_set_statuses)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_loose = reports_dir / f"sanity_loose_vs_loose_sets_{ts}.csv"
    out_local = reports_dir / f"sanity_local_vs_rebrickable_{ts}.csv"

    print(f"🔗 DB: {db_path}")
    print(f"🗂  Reports → {reports_dir}\n")

    with sqlite3.connect(db_path) as conn:
        # Rollups first for context
        rolls = run_query(conn, Q_ROLLUPS)
        print("=== Rollups ===")
        for r in rolls:
            print(f"{r['which']:>22}: {fmt(r['qty'])}")
        print()
        print(f"Statuses → loose: {loose_statuses} | in-sets: {counted_set_statuses}\n")

        # 1) Loose inventory parity
        loose = run_query(conn, Q_LOOSE_PARITY)
        write_csv(loose, out_loose)
        total_abs_delta_loose = sum(abs(r["delta"]) for r in loose) if loose else 0
        print("=== Check #1: Loose inventory ≟ Loose sets ===")
        print(f"Mismatched rows: {len(loose)}")
        print(f"Total |delta|: {fmt(total_abs_delta_loose)}")
        print(f"CSV: {out_loose}\n")

        # 2) Local vs Rebrickable
        local = run_query(conn, Q_LOCAL_VS_RB)
        write_csv(local, out_local)
        total_abs_delta_local = sum(abs(r["delta"]) for r in local) if local else 0
        print("=== Check #2: Local (loose + non-loose sets) ≟ Rebrickable (all sets) ===")
        print(f"Mismatched rows: {len(local)}")
        print(f"Total |delta|: {fmt(total_abs_delta_local)}")
        print(f"CSV: {out_local}\n")

        if not loose and not local:
            print("✅ All checks passed. No differences found.")
        else:
            print("⚠️  Differences detected. See CSVs for details.")

if __name__ == "__main__":
    main()