from contextlib import contextmanager
from pathlib import Path
import sqlite3

# 首执表沿用 desk_events 作为唯一事实来源，联动轮额外记录灯号、报码和出票出处。
_EVENT_COLUMNS = {
    'light': 'INTEGER',
    'signal': 'TEXT',
    'origin_request_id': 'TEXT',
    'kind': "TEXT NOT NULL DEFAULT 'fixed'",
}

def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}

def initialize_desk(conn: sqlite3.Connection) -> None:
    conn.execute('CREATE TABLE IF NOT EXISTS installed_programs (session_id INTEGER PRIMARY KEY, edition_id INTEGER NOT NULL, seat TEXT NOT NULL, payload TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS desk_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, edition_id INTEGER NOT NULL, seat TEXT NOT NULL, round_number INTEGER NOT NULL, request_id TEXT NOT NULL, packet TEXT NOT NULL, action TEXT NOT NULL, sequence INTEGER NOT NULL, light INTEGER, signal TEXT, origin_request_id TEXT, kind TEXT NOT NULL DEFAULT \'fixed\', UNIQUE(session_id, round_number), UNIQUE(seat, request_id))')
    existing = _columns(conn, 'desk_events')
    for name, decl in _EVENT_COLUMNS.items():
        if name not in existing:
            conn.execute(f'ALTER TABLE desk_events ADD COLUMN {name} {decl}')
    conn.execute(
        'CREATE TABLE IF NOT EXISTS linked_inputs ('
        'input_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, edition_id INTEGER NOT NULL, '
        'seat TEXT NOT NULL, round_number INTEGER NOT NULL, request_id TEXT NOT NULL, kind TEXT NOT NULL, '
        'packet TEXT NOT NULL, light INTEGER, signal TEXT, UNIQUE(seat, request_id))'
    )
    conn.commit()

def open_desk(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    initialize_desk(conn)
    return conn

@contextmanager
def desk_write_transaction(conn: sqlite3.Connection):
    try:
        conn.execute('BEGIN IMMEDIATE')
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
