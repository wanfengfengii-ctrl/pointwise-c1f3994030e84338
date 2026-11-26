from dataclasses import asdict
import json
import sqlite3
from .finalize import Closeout, ReportRound

def initialize_report_archive(conn: sqlite3.Connection) -> None:
    conn.execute('CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER UNIQUE NOT NULL, payload TEXT NOT NULL)')
    conn.commit()

def save_report(conn: sqlite3.Connection, report: Closeout) -> Closeout:
    initialize_report_archive(conn)
    existing = conn.execute('SELECT id, payload FROM reports WHERE session_id = ?', (report.session_id,)).fetchone()
    if existing is not None:
        return read_report(conn, existing[0])
    payload = {'session_id': report.session_id, 'edition_id': report.edition_id, 'rounds': [asdict(item) for item in report.rounds]}
    cursor = conn.execute('INSERT INTO reports(session_id, payload) VALUES (?, ?)', (report.session_id, json.dumps(payload, sort_keys=True)))
    conn.commit()
    return Closeout(cursor.lastrowid, report.session_id, report.edition_id, report.rounds)

def read_report(conn: sqlite3.Connection, report_id: int) -> Closeout:
    row = conn.execute('SELECT id, payload FROM reports WHERE id = ?', (report_id,)).fetchone()
    if row is None:
        raise KeyError(f'report {report_id}')
    payload = json.loads(row[1])
    rounds = tuple(ReportRound(item['round_number'], item['left'], item['right']) for item in payload['rounds'])
    return Closeout(row[0], payload['session_id'], payload['edition_id'], rounds)

def find_report_for_session(conn: sqlite3.Connection, session_id: int) -> Closeout:
    row = conn.execute('SELECT id FROM reports WHERE session_id = ?', (session_id,)).fetchone()
    if row is None:
        raise KeyError(f'report for session {session_id}')
    return read_report(conn, row[0])
