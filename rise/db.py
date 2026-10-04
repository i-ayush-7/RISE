import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager

# Resolve data/rise.db relative to this file's directory (rise-mcp/rise/..)
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_DB_PATH = Path(os.environ.get("RISE_DB_PATH", PROJECT_ROOT / "data" / "rise.db"))

def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Get a database connection with foreign keys enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def transaction(db_path: Path = DEFAULT_DB_PATH):
    """Context manager for DB transactions."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: Path = DEFAULT_DB_PATH):
    """Initialize the database schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with transaction(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS households (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                household_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                age_group TEXT NOT NULL CHECK(age_group IN ('child', 'adult', 'senior', 'pet')),
                support_level TEXT NOT NULL CHECK(support_level IN ('independent', 'needs_assistance', 'dependent')),
                mobility_needs TEXT,
                medical_needs TEXT,
                notes TEXT,
                is_pet INTEGER NOT NULL DEFAULT 0 CHECK(is_pet IN (0,1)),
                FOREIGN KEY(household_id) REFERENCES households(id) ON DELETE CASCADE,
                CHECK ((age_group = 'pet') = (is_pet = 1))
            )
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_members_household_id ON members(household_id)")
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                household_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                relationship TEXT,
                phone TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 1 CHECK(priority >= 1),
                FOREIGN KEY(household_id) REFERENCES households(id) ON DELETE CASCADE
            )
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_household_id ON contacts(household_id)")
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meeting_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                household_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                description TEXT,
                kind TEXT NOT NULL CHECK(kind IN ('primary', 'backup', 'out_of_area')),
                FOREIGN KEY(household_id) REFERENCES households(id) ON DELETE CASCADE
            )
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meeting_points_household_id ON meeting_points(household_id)")
