import json
import sqlite3
from editions.release import read_edition
from reports.archive import find_report_for_session, save_report
from reports.finalize import freeze_report
from reports.reconcile import reconcile_receipts
from .opening import read_session
from .rounds import read_issued_rounds

def close_session(conn: sqlite3.Connection, session_id: int, desk_apps: dict):
    session = read_session(conn, session_id)
    if session.closed_report_id is not None:
        return find_report_for_session(conn, session_id)
    edition = read_edition(conn, session.edition_id)
    issued = read_issued_rounds(conn, session_id)
    receipts = {seat: desk_apps[seat].read_closeout_receipts(session_id) for seat in ('left', 'right')}
    audit = reconcile_receipts(session_id, session.edition_id, [item.number for item in edition.rounds], [item.__dict__ for item in issued], receipts)
    if not audit.complete:
        detail = [{'kind': item.kind, 'seat': item.seat, 'round_number': item.round_number, 'detail': item.detail} for item in audit.issues]
        raise ValueError('409:' + json.dumps({'issues': detail}, sort_keys=True))
    with conn:
        report = save_report(conn, freeze_report(audit))
        conn.execute('UPDATE sessions SET closed_report_id = ? WHERE id = ?', (report.report_id, session_id))
    return report
