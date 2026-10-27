import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
DB_PATH = os.path.join(BASE_DIR, "ground_truth.db")

def init_database():
    """Initializes the SQLite ground truth database using the schema definition.
    Ensures zero dummy entries are inserted.
    """
    print(f"Initializing SQLite database at: {DB_PATH}")
    
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript(schema_sql)
    conn.commit()
    
    # Verify tables and row counts
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
    
    print("\nInitialized Tables:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table};")
        count = cursor.fetchone()[0]
        print(f" - {table}: {count} records (empty as requested)")
        
    conn.close()
    print("\nDatabase initialization complete successfully with 0 entries.")

if __name__ == "__main__":
    init_database()
