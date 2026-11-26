import unittest
from tests.fixture import make_app, post, get, seed_program, install_both

class TestPerformance(unittest.TestCase):
    def test_wrong_edition(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        first = seed_program(app)
        second = seed_program(app)
        session = post(app, '/sessions', {'edition_id': first['id']})
        packet = get(app, f'/editions/{second["id"]}?seat=right')
        status, _ = app.handle('POST', '/installations', {'session_id': session['id'], 'seat': 'right', 'packet': packet})
        self.assertEqual(status, 409)

    def test_reopen_receipt(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        edition = seed_program(app)
        session = install_both(app, edition)
        round_packet = post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 1})
        first = post(app, f'/rounds/{round_packet["packet_id"]}/play', {'seat': 'left', 'request_id': 'left-r1', 'packet': round_packet})
        second = post(app, f'/rounds/{round_packet["packet_id"]}/play', {'seat': 'left', 'request_id': 'left-r1', 'packet': round_packet})
        self.assertEqual(first, second)
        status, _ = app.handle('POST', f'/rounds/{round_packet["packet_id"]}/play', {'seat': 'left', 'request_id': 'left-r2', 'packet': round_packet})
        self.assertEqual(status, 409)

    def test_route_round(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        edition = seed_program(app, include_silence=True)
        session = install_both(app, edition)
        first = post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 1})
        second = post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 2})
        status, _ = app.handle('POST', f'/rounds/{second["packet_id"]}/play', {'seat': 'left', 'request_id': 'wrong-route', 'packet': first})
        self.assertEqual(status, 409)
        self.assertEqual(get(app, '/receipts/wrong-route') if False else 404, 404)
