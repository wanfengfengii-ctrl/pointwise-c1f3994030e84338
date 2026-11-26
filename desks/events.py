from dataclasses import dataclass
import json
import sqlite3
from .store import initialize_desk

@dataclass(frozen=True)
class DeskEvent:
    event_id: int
    session_id: int
    edition_id: int
    seat: str
    round_number: int
    request_id: str
    packet: dict
    action: dict | None
    sequence: int

def _event(row) -> DeskEvent:
    return DeskEvent(row['event_id'], row['session_id'], row['edition_id'], row['seat'], row['round_number'], row['request_id'], json.loads(row['packet']), json.loads(row['action']), row['sequence'])

def append_event(conn: sqlite3.Connection, session_id: int, edition_id: int, seat: str, round_number: int, request_id: str, packet: dict, action: dict | None) -> DeskEvent:
    initialize_desk(conn)
    sequence = int(conn.execute('SELECT COALESCE(MAX(sequence), 0) + 1 FROM desk_events WHERE seat = ?', (seat,)).fetchone()[0])
    cursor = conn.execute('INSERT INTO desk_events(session_id, edition_id, seat, round_number, request_id, packet, action, sequence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (session_id, edition_id, seat, round_number, request_id, json.dumps(packet, sort_keys=True), json.dumps(action, sort_keys=True), sequence))
    conn.commit()
    row = conn.execute('SELECT * FROM desk_events WHERE event_id = ?', (cursor.lastrowid,)).fetchone()
    return _event(row)

def find_round_event(conn: sqlite3.Connection, session_id: int, round_number: int) -> DeskEvent | None:
    initialize_desk(conn)
    row = conn.execute('SELECT * FROM desk_events WHERE session_id = ? AND round_number = ?', (session_id, round_number)).fetchone()
    return _event(row) if row else None

def find_request_event(conn: sqlite3.Connection, request_id: str, seat: str) -> DeskEvent | None:
    initialize_desk(conn)
    row = conn.execute('SELECT * FROM desk_events WHERE request_id = ? AND seat = ?', (request_id, seat)).fetchone()
    return _event(row) if row else None

def list_session_events(conn: sqlite3.Connection, session_id: int) -> list[DeskEvent]:
    initialize_desk(conn)
    rows = conn.execute('SELECT * FROM desk_events WHERE session_id = ? ORDER BY round_number', (session_id,)).fetchall()
    return [_event(row) for row in rows]
