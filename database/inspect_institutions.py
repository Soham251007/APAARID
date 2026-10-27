"""Check for mock institutions and expand AICTE Approved Institutions directory."""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "ground_truth.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Check institution names in ground_truth_students
cur.execute("SELECT DISTINCT institution_name FROM ground_truth_students WHERE institution_name IS NOT NULL;")
names = [r[0] for r in cur.fetchall()]
print(f"Total distinct institution names in ground_truth_students: {len(names)}")
for n in names:
    if any(k in n.lower() for k in ["western", "city school", "national college", "demo"]):
        cur.execute("SELECT count(*) FROM ground_truth_students WHERE institution_name = ?", (n,))
        print(f"Demo match: '{n}' has {cur.fetchone()[0]} students")

cur.execute("SELECT count(*) FROM aicte_approved_institutions;")
print(f"Current institutions in aicte_approved_institutions table: {cur.fetchone()[0]}")

conn.close()
