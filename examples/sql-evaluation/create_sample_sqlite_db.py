#!/usr/bin/env python3
"""Create a deterministic sample SQLite database for SQL evaluator testing.

Usage:
    python examples/sql-evaluation/create_sample_sqlite_db.py

Creates: examples/sql-evaluation/sample_sql_eval.db

The data is entirely synthetic and non-sensitive.  All values are
deterministic so that expected_result fields in test datasets can
be pinned exactly.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "sample_sql_eval.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS regions (
    region_id   INTEGER PRIMARY KEY,
    region_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id   INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    region_id     INTEGER NOT NULL REFERENCES regions(region_id)
);

CREATE TABLE IF NOT EXISTS products (
    product_id   INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sales (
    sale_id     INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    product_id  INTEGER NOT NULL REFERENCES products(product_id),
    region_id   INTEGER NOT NULL REFERENCES regions(region_id),
    amount      REAL NOT NULL,
    sale_date   TEXT NOT NULL,
    tenant_id   TEXT NOT NULL DEFAULT 'tenant_a'
);
"""

REGIONS = [
    (1, "East"),
    (2, "West"),
    (3, "North"),
    (4, "South"),
]

CUSTOMERS = [
    (1, "Alice Corp", 1),
    (2, "Bob Inc", 2),
    (3, "Charlie LLC", 3),
    (4, "Diana Ltd", 4),
    (5, "Echo Systems", 1),
    (6, "Foxtrot Co", 2),
]

PRODUCTS = [
    (1, "Widget A", "Widgets"),
    (2, "Widget B", "Widgets"),
    (3, "Gadget X", "Gadgets"),
    (4, "Gadget Y", "Gadgets"),
    (5, "Service Plan", "Services"),
]

# Deterministic sales data covering Q1-Q2 2025
# Designed to produce specific aggregation results
SALES = [
    # Q1 2025 — East region
    (1, 1, 1, 1, 10000.00, "2025-01-15", "tenant_a"),
    (2, 1, 2, 1, 15000.00, "2025-02-10", "tenant_a"),
    (3, 5, 3, 1, 20000.00, "2025-03-05", "tenant_a"),
    # Q1 2025 — West region
    (4, 2, 1, 2, 12000.00, "2025-01-20", "tenant_a"),
    (5, 6, 4, 2, 18000.00, "2025-02-28", "tenant_b"),
    # Q1 2025 — North region
    (6, 3, 2, 3, 8000.00, "2025-01-10", "tenant_a"),
    (7, 3, 5, 3, 7000.00, "2025-03-15", "tenant_a"),
    # Q1 2025 — South region
    (8, 4, 3, 4, 25000.00, "2025-02-20", "tenant_b"),
    (9, 4, 4, 4, 5000.00, "2025-03-30", "tenant_a"),
    # Q2 2025 — mixed regions
    (10, 1, 1, 1, 11000.00, "2025-04-10", "tenant_a"),
    (11, 2, 3, 2, 14000.00, "2025-05-15", "tenant_a"),
    (12, 3, 5, 3, 9000.00, "2025-06-20", "tenant_b"),
    (13, 5, 2, 1, 16000.00, "2025-04-25", "tenant_a"),
    (14, 6, 4, 2, 22000.00, "2025-05-30", "tenant_a"),
    (15, 4, 1, 4, 13000.00, "2025-06-05", "tenant_a"),
]

# Pre-computed expected results for the dataset:
#
# Q1 2025 total sales by region:
#   East:  10000 + 15000 + 20000 = 45000.0
#   West:  12000 + 18000          = 30000.0
#   North:  8000 +  7000          = 15000.0
#   South: 25000 +  5000          = 30000.0
#
# Top products by total revenue (all time):
#   Gadget X:     20000 + 25000 + 14000          = 59000.0
#   Widget A:     10000 + 12000 + 11000 + 13000  = 46000.0
#   Gadget Y:     18000 +  5000 + 22000           = 45000.0
#   Widget B:     15000 +  8000 + 16000           = 39000.0
#   Service Plan:  7000 +  9000                   = 16000.0
#
# Top customers by total revenue (all time):
#   Diana Ltd:      25000 +  5000 + 13000           = 43000.0
#   Foxtrot Co:     18000 + 22000                   = 40000.0
#   Alice Corp:     10000 + 15000 + 11000           = 36000.0
#   Echo Systems:   20000 + 16000                   = 36000.0
#   Bob Inc:        12000 + 14000                   = 26000.0
#   Charlie LLC:     8000 +  7000 +  9000           = 24000.0
#
# Revenue by product category (all time):
#   Gadgets:  59000.0 + 45000.0 = 104000.0
#   Widgets:  46000.0 + 39000.0 =  85000.0
#   Services: 16000.0
#
# Q2 2025 total sales by region:
#   East:  11000 + 16000          = 27000.0
#   West:  14000 + 22000          = 36000.0
#   North:  9000                  =  9000.0
#   South: 13000                  = 13000.0
#
# Average sale amount by region (all time):
#   East:  (10000+15000+20000+11000+16000)/5 = 14400.0
#   West:  (12000+18000+14000+22000)/4       = 16500.0
#   North: (8000+7000+9000)/3                =  8000.0
#   South: (25000+5000+13000)/3              = 14333.33
#
# Tenant_b sales: sale_id 5 (18000), 8 (25000), 12 (9000) = 52000.0
# Total sales count: 15


def create_database() -> None:
    """Create the sample database, replacing any existing file."""
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Create tables
    cursor.executescript(SCHEMA)

    # Insert data
    cursor.executemany(
        "INSERT INTO regions (region_id, region_name) VALUES (?, ?)",
        REGIONS,
    )
    cursor.executemany(
        "INSERT INTO customers (customer_id, customer_name, region_id) VALUES (?, ?, ?)",
        CUSTOMERS,
    )
    cursor.executemany(
        "INSERT INTO products (product_id, product_name, category) VALUES (?, ?, ?)",
        PRODUCTS,
    )
    cursor.executemany(
        "INSERT INTO sales (sale_id, customer_id, product_id, region_id, amount, sale_date, tenant_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        SALES,
    )

    conn.commit()
    conn.close()

    print(f"Sample database created: {DB_PATH.resolve()}")
    print(f"  Tables: regions ({len(REGIONS)} rows), customers ({len(CUSTOMERS)} rows), "
          f"products ({len(PRODUCTS)} rows), sales ({len(SALES)} rows)")


if __name__ == "__main__":
    create_database()
