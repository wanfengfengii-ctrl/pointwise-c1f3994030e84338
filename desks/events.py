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
    light: int | None = None
    signal: dict | None = None
    origin_request_id: str | None = None
    kind: str = 'fixed'

def _load(raw):
    return json.loads(raw) if raw is not None else None

def _event(row) -> DeskEvent:
    keys = row.keys()
    return DeskEvent(
        row['event_id'], row['session_id'], row['edition_id'], row['seat'], row['round_number'],
        row['request_id'], json.loads(row['packet']), json.loads(row['action']), row['sequence'],
        row['light'] if 'light' in keys else None,
        _load(row['signal']) if 'signal' in keys else None,
        row['origin_request_id'] if 'origin_request_id' in keys else None,
        row['kind'] if 'kind' in keys and row['kind'] is not None else 'fixed',
    )

def append_event(conn: sqlite3.Connection, session_id: int, edition_id: int, seat: str, round_number: int, request_id: str, packet: dict, action: dict | None, light: int | None = None, signal: dict | None = None, origin_request_id: str | None = None, kind: str = 'fixed', *, ensure: bool = True, commit: bool = True) -> DeskEvent:
    if ensure:
        initialize_desk(conn)
    sequence = int(conn.execute('SELECT COALESCE(MAX(sequence), 0) + 1 FROM desk_events WHERE seat = ?', (seat,)).fetchone()[0])
    cursor = conn.execute(
        'INSERT INTO desk_events(session_id, edition_id, seat, round_number, request_id, packet, action, sequence, light, signal, origin_request_id, kind) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (session_id, edition_id, seat, round_number, request_id, json.dumps(packet, sort_keys=True),
         json.dumps(action, sort_keys=True), sequence, light,
         json.dumps(signal, sort_keys=True) if signal is not None else None, origin_request_id, kind))
    if commit:
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

def list_session_events(conn: sqlite3.Connection, session_id: int, seat: str | None = None) -> list[DeskEvent]:
    initialize_desk(conn)
    if seat is None:
        rows = conn.execute('SELECT * FROM desk_events WHERE session_id = ? ORDER BY round_number', (session_id,)).fetchall()
    else:
        rows = conn.execute('SELECT * FROM desk_events WHERE session_id = ? AND seat = ? ORDER BY round_number', (session_id, seat)).fetchall()
    return [_event(row) for row in rows]
