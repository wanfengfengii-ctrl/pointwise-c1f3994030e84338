from dataclasses import dataclass
import sqlite3
from editions.release import read_edition

@dataclass(frozen=True)
class Session:
    id: int
    edition_id: int
    closed_report_id: int | None

def initialize_sessions(conn: sqlite3.Connection) -> None:
    conn.execute('CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, edition_id INTEGER NOT NULL, closed_report_id INTEGER)')
    conn.commit()

def open_session(conn: sqlite3.Connection, edition_id: int) -> Session:
    read_edition(conn, edition_id)
    initialize_sessions(conn)
    cursor = conn.execute('INSERT INTO sessions(edition_id) VALUES (?)', (edition_id,))
    conn.commit()
    return Session(cursor.lastrowid, edition_id, None)

def read_session(conn: sqlite3.Connection, session_id: int) -> Session:
    row = conn.execute('SELECT id, edition_id, closed_report_id FROM sessions WHERE id = ?', (session_id,)).fetchone()
    if row is None:
        raise KeyError(f'session {session_id}')
    return Session(row[0], row[1], row[2])
