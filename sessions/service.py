import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import sqlite3
from materials.intake import register_clip
from editions.program import submit_draft
from editions.preview import preview_draft
from editions.release import issue_edition, read_edition
from editions.seat_packets import build_seat_packet, encode_seat_packet
from sessions.installations import initialize_session_installations, record_installation
from sessions.opening import initialize_sessions, open_session, read_session
from sessions.rounds import initialize_rounds, issue_next_round
from sessions.closing import close_session
from sessions.round_packets import encode_round_packet
from desks.service import build_desk_server
from reports.archive import initialize_report_archive, read_report

class WorkstationApplication:
    def __init__(self, conn: sqlite3.Connection, desks: dict):
        self.conn = conn
        self.desks = desks
        initialize_sessions(conn)
        initialize_session_installations(conn)
        initialize_rounds(conn)
        initialize_report_archive(conn)

    def _edition_payload(self, edition, seat=None):
        if seat:
            return encode_seat_packet(build_seat_packet(edition, seat))
        return {'id': edition.id, 'draft_id': edition.draft_id, 'rounds': [item.__dict__ for item in edition.rounds]}

    def handle(self, method: str, path: str, body: dict | None = None):
        parsed = urlparse(path)
        parts = [part for part in parsed.path.split('/') if part]
        query = parse_qs(parsed.query)
        try:
            if method == 'GET' and parts == ['health']:
                return 200, {'status': 'ok'}
            if method == 'POST' and parts == ['clips']:
                return 200, register_clip(self.conn, body.get('text'), body.get('duration'), body.get('clip_id'))
            if method == 'POST' and parts == ['drafts']:
                draft = submit_draft(self.conn, body)
                return 200, {'id': draft.id}
            if method == 'GET' and len(parts) == 3 and parts[0] == 'drafts' and parts[2] == 'preview':
                previews = preview_draft(self.conn, int(parts[1]))
                return 200, [{'number': item.number, 'left_interval': item.left_interval, 'right_interval': item.right_interval, 'issues': [issue.__dict__ for issue in item.issues]} for item in previews]
            if method == 'POST' and parts == ['editions']:
                edition = issue_edition(self.conn, body['draft_id'])
                return 200, self._edition_payload(edition)
            if method == 'GET' and len(parts) == 2 and parts[0] == 'editions':
                edition = read_edition(self.conn, int(parts[1]))
                seat = query.get('seat', [None])[0]
                return 200, self._edition_payload(edition, seat)
            if method == 'POST' and parts == ['sessions']:
                session = open_session(self.conn, body['edition_id'])
                return 200, session.__dict__ | {'seats': ['left', 'right']}
            if method == 'POST' and parts == ['installations']:
                seat = body['seat']
                if seat not in self.desks:
                    raise ValueError('409:unknown seat')
                receipt = self.desks[seat].handle('POST', '/installations', {'session_id': body['session_id'], 'packet': body['packet']})[1]
                record = record_installation(self.conn, body['session_id'], seat, body['packet']['edition_id'], receipt)
                return 200, record
            if method == 'POST' and len(parts) == 3 and parts[0] == 'sessions' and parts[2] == 'rounds':
                packet = issue_next_round(self.conn, int(parts[1]), body['round_number'])
                return 200, encode_round_packet(packet)
            if method == 'POST' and len(parts) == 3 and parts[0] == 'rounds' and parts[2] == 'play':
                seat = body['seat']
                if seat not in self.desks:
                    raise ValueError('409:unknown seat')
                return self.desks[seat].handle('POST', f'/rounds/{parts[1]}/play', body)
            if method == 'GET' and len(parts) == 2 and parts[0] == 'receipts':
                seat = query.get('seat', [None])[0]
                if seat:
                    return self.desks[seat].handle('GET', f'/receipts/{parts[1]}')
                for candidate in ('left', 'right'):
                    status, result = self.desks[candidate].handle('GET', f'/receipts/{parts[1]}')
                    if status == 200:
                        return status, result
                return 404, {'error': 'receipt not found'}
            if method == 'POST' and len(parts) == 3 and parts[0] == 'sessions' and parts[2] == 'close':
                report = close_session(self.conn, int(parts[1]), self.desks)
                return 200, {'report_id': report.report_id, 'session_id': report.session_id}
            if method == 'GET' and len(parts) == 2 and parts[0] == 'reports':
                report = read_report(self.conn, int(parts[1]))
                return 200, {'report_id': report.report_id, 'session_id': report.session_id, 'edition_id': report.edition_id, 'rounds': [item.__dict__ for item in report.rounds]}
            return 404, {'error': 'not found'}
        except KeyError as exc:
            text = str(exc)
            if text.startswith('report for session'):
                return 404, {'error': text}
            return 404, {'error': text}
        except ValueError as exc:
            text = str(exc)
            code = int(text.split(':', 1)[0]) if len(text) >= 3 and text[:3].isdigit() else 409
            return code, {'error': text.split(':', 1)[-1]}

def initialize_workstation(data_dir: str):
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(Path(data_dir) / 'workstation.db'))
    conn.row_factory = sqlite3.Row
    desks = {'left': build_desk_server(data_dir, 'left'), 'right': build_desk_server(data_dir, 'right')}
    return WorkstationApplication(conn, desks)

def build_workstation(data_dir: str):
    return initialize_workstation(data_dir)

class _Handler(BaseHTTPRequestHandler):
    app = None
    def _serve(self):
        length = int(self.headers.get('Content-Length', '0'))
        body = json.loads(self.rfile.read(length) or b'{}') if length else None
        status, payload = self.app.handle(self.command, self.path, body)
        data = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    do_GET = _serve
    do_POST = _serve
    def log_message(self, *_args):
        return

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--host', choices=('127.0.0.1',), default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)
    _Handler.app = build_workstation(args.data_dir)
    HTTPServer((args.host, args.port), _Handler).serve_forever()

if __name__ == '__main__':
    main()
