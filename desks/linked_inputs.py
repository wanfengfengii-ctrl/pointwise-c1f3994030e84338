from dataclasses import dataclass
import json
import sqlite3
from .store import initialize_desk

@dataclass(frozen=True)
class PendingInput:
    input_id: int
    session_id: int
    edition_id: int
    seat: str
    round_number: int
    request_id: str
    kind: str
    packet: dict
    light: int | None
    signal: dict | None

def _input(row) -> PendingInput:
    return PendingInput(
        row['input_id'], row['session_id'], row['edition_id'], row['seat'], row['round_number'],
        row['request_id'], row['kind'], json.loads(row['packet']), row['light'],
        json.loads(row['signal']) if row['signal'] is not None else None,
    )

def find_input(conn: sqlite3.Connection, request_id: str, seat: str) -> PendingInput | None:
    initialize_desk(conn)
    row = conn.execute('SELECT * FROM linked_inputs WHERE request_id = ? AND seat = ?', (request_id, seat)).fetchone()
    return _input(row) if row else None

def list_round_inputs(conn: sqlite3.Connection, session_id: int, round_number: int, seat: str) -> list[PendingInput]:
    initialize_desk(conn)
    rows = conn.execute('SELECT * FROM linked_inputs WHERE session_id = ? AND round_number = ? AND seat = ? ORDER BY input_id', (session_id, round_number, seat)).fetchall()
    return [_input(row) for row in rows]

def insert_input(conn: sqlite3.Connection, session_id: int, edition_id: int, seat: str, round_number: int, request_id: str, kind: str, packet: dict, light: int | None = None, signal: dict | None = None, *, ensure: bool = True, commit: bool = True) -> PendingInput:
    if ensure:
        initialize_desk(conn)
    cursor = conn.execute(
        'INSERT INTO linked_inputs(session_id, edition_id, seat, round_number, request_id, kind, packet, light, signal) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (session_id, edition_id, seat, round_number, request_id, kind, json.dumps(packet, sort_keys=True), light,
         json.dumps(signal, sort_keys=True) if signal is not None else None))
    if commit:
        conn.commit()
    row = conn.execute('SELECT * FROM linked_inputs WHERE input_id = ?', (cursor.lastrowid,)).fetchone()
    return _input(row)
