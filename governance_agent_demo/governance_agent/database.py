import sqlite3
from governance_agent.config import DB_PATH


def get_connection(db_path: str = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def initialize_database(db_path: str = None) -> None:
    """Create all schema tables (idempotent)."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS BUSINESS_TERMS (
            term_id     TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            criticality REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS RULES (
            rule_id          TEXT PRIMARY KEY,
            business_term_id TEXT NOT NULL,
            description      TEXT NOT NULL,
            threshold        REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS TDE (
            tde_id           TEXT PRIMARY KEY,
            name             TEXT NOT NULL,
            business_term_id TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS DQ_SCORES (
            date   TEXT NOT NULL,
            tde_id TEXT NOT NULL,
            score  REAL NOT NULL,
            PRIMARY KEY (date, tde_id)
        );

        CREATE TABLE IF NOT EXISTS DBT_COLUMN_MAPPING (
            model_name  TEXT NOT NULL,
            column_name TEXT NOT NULL,
            tde_id      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS DBT_SQL_MODELS (
            model_name TEXT PRIMARY KEY,
            sql_text   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS EVENT_LOG (
            event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            event_type  TEXT    NOT NULL,
            entity_type TEXT    NOT NULL,
            entity_id   TEXT    NOT NULL,
            entity_name TEXT    NOT NULL,
            context     TEXT    NOT NULL,   -- JSON string
            metrics     TEXT    NOT NULL,   -- JSON string
            explanation TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_event_log_type
            ON EVENT_LOG(event_type);
        CREATE INDEX IF NOT EXISTS idx_event_log_entity
            ON EVENT_LOG(entity_id);
        CREATE INDEX IF NOT EXISTS idx_dq_scores_date
            ON DQ_SCORES(date);
    """)

    conn.commit()
    conn.close()


def clear_event_log(db_path: str = None) -> None:
    """Wipe the event log so simulation can be re-run cleanly."""
    conn = get_connection(db_path)
    conn.execute("DELETE FROM EVENT_LOG")
    conn.execute("DELETE FROM sqlite_sequence WHERE name='EVENT_LOG'")
    conn.commit()
    conn.close()
