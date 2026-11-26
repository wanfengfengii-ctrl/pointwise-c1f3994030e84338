import json
import sqlite3
from editions.release import read_edition
from .installations import is_fully_installed
from .opening import read_session
from .round_packets import RoundPacket

def initialize_rounds(conn: sqlite3.Connection) -> None:
    conn.execute('CREATE TABLE IF NOT EXISTS issued_rounds (packet_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, edition_id INTEGER NOT NULL, round_number INTEGER NOT NULL, order_index INTEGER NOT NULL, UNIQUE(session_id, round_number))')
    conn.commit()

def issue_next_round(conn: sqlite3.Connection, session_id: int, round_number: int) -> RoundPacket:
    session = read_session(conn, session_id)
    if session.closed_report_id is not None or not is_fully_installed(conn, session_id):
        raise ValueError('409:session is not ready')
    edition = read_edition(conn, session.edition_id)
    expected = [item.number for item in edition.rounds]
    initialize_rounds(conn)
    existing = [row[0] for row in conn.execute('SELECT round_number FROM issued_rounds WHERE session_id = ? ORDER BY order_index', (session_id,))]
    if len(existing) >= len(expected) or expected[len(existing)] != round_number:
        raise ValueError('409:round is not the next frozen round')
    cursor = conn.execute('INSERT INTO issued_rounds(session_id, edition_id, round_number, order_index) VALUES (?, ?, ?, ?)', (session_id, session.edition_id, round_number, len(existing) + 1))
    conn.commit()
    return RoundPacket(cursor.lastrowid, session_id, session.edition_id, round_number, len(existing) + 1)

def read_issued_rounds(conn: sqlite3.Connection, session_id: int) -> list[RoundPacket]:
    initialize_rounds(conn)
    return [RoundPacket(row[0], row[1], row[2], row[3], row[4]) for row in conn.execute('SELECT packet_id, session_id, edition_id, round_number, order_index FROM issued_rounds WHERE session_id = ? ORDER BY order_index', (session_id,))]
