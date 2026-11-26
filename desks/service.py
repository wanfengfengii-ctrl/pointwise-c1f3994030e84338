import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from .events import list_session_events
from .install import install_seat_packet
from .linked import lookup, submit_linked
from .playback import play_round
from .receipts import read_receipt
from .store import open_desk

class DeskApplication:
    def __init__(self, conn, seat: str):
        self.conn = conn
        self.seat = seat

    def read_closeout_receipts(self, session_id: int):
        receipts = []
        for event in list_session_events(self.conn, session_id, self.seat):
            entry = {
                'request_id': event.request_id,
                'session_id': event.session_id,
                'edition_id': event.edition_id,
                'seat': event.seat,
                'round_number': event.round_number,
                'action': event.action,
                'sequence': event.sequence,
                'light': event.light,
                'signal': event.signal,
                'origin_request_id': event.origin_request_id,
                'kind': event.kind,
            }
            receipts.append(entry)
        return receipts

    def handle(self, method: str, path: str, body: dict | None = None):
        parsed = urlparse(path)
        parts = [part for part in parsed.path.split('/') if part]
        try:
            if method == 'POST' and parts == ['installations']:
                receipt = install_seat_packet(self.conn, int(body['session_id']), body['packet'])
                return 200, receipt.__dict__
            if method == 'POST' and len(parts) == 3 and parts[0] == 'rounds' and parts[2] in ('observe', 'signal'):
                status, payload = submit_linked(self.conn, int(parts[1]), body, self.seat, parts[2])
                if status == 202:
                    return 202, {'status': 'pending'}
                return 200, {'receipt': payload['receipt']}
            if method == 'POST' and len(parts) == 3 and parts[0] == 'rounds' and parts[2] == 'play':
                result = play_round(self.conn, int(parts[1]), body['request_id'], body['packet'])
                return 200, result.__dict__
            if method == 'GET' and len(parts) == 2 and parts[0] == 'receipts':
                state, payload = lookup(self.conn, parts[1], self.seat)
                if state is not None:
                    return 200, {'receipt': payload}
                return 200, read_receipt(self.conn, parts[1], self.seat).__dict__
            return 404, {'error': 'not found'}
        except KeyError as exc:
            return 404, {'error': str(exc)}
        except ValueError as exc:
            text = str(exc)
            code = int(text.split(':', 1)[0]) if text[:3].isdigit() else 409
            return code, {'error': text.split(':', 1)[-1]}

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

def build_desk_server(data_dir: str, seat: str) -> DeskApplication:
    return DeskApplication(open_desk(f'{data_dir}/{seat}.db'), seat)

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--seat', choices=('left', 'right'), required=True)
    parser.add_argument('--host', choices=('127.0.0.1',), default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args(argv)
    app = build_desk_server(args.data_dir, args.seat)
    _Handler.app = app
    HTTPServer((args.host, args.port), _Handler).serve_forever()

if __name__ == '__main__':
    main()
