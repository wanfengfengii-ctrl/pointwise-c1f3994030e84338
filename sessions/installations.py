import sqlite3
from editions.seat_packets import decode_seat_packet
from .opening import read_session

def initialize_session_installations(conn: sqlite3.Connection) -> None:
    conn.execute('CREATE TABLE IF NOT EXISTS installations (session_id INTEGER NOT NULL, seat TEXT NOT NULL, edition_id INTEGER NOT NULL, receipt TEXT NOT NULL, PRIMARY KEY(session_id, seat))')
    conn.commit()

def record_installation(conn: sqlite3.Connection, session_id: int, seat: str, edition_id: int, receipt: dict) -> dict:
    session = read_session(conn, session_id)
    if seat not in ('left', 'right') or edition_id != session.edition_id:
        raise ValueError('409:installation does not match session')
    initialize_session_installations(conn)
    existing = conn.execute('SELECT receipt FROM installations WHERE session_id = ? AND seat = ?', (session_id, seat)).fetchone()
    if existing is None:
        conn.execute('INSERT INTO installations(session_id, seat, edition_id, receipt) VALUES (?, ?, ?, ?)', (session_id, seat, edition_id, str(receipt)))
        conn.commit()
    return {'session_id': session_id, 'seat': seat, 'edition_id': edition_id, 'receipt': receipt}

def installed_seats(conn: sqlite3.Connection, session_id: int) -> set[str]:
    initialize_session_installations(conn)
    return {row[0] for row in conn.execute('SELECT seat FROM installations WHERE session_id = ?', (session_id,))}

def is_fully_installed(conn: sqlite3.Connection, session_id: int) -> bool:
    return installed_seats(conn, session_id) == {'left', 'right'}
