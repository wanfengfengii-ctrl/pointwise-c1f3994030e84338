import unittest
from tests.fixture import make_app, post, get, seed_program, install_both

class TestCloseout(unittest.TestCase):
    def test_missing_silence(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        edition = seed_program(app, include_silence=True)
        session = install_both(app, edition)
        first = post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 1})
        second = post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 2})
        for seat in ('left', 'right'):
            post(app, f'/rounds/{first["packet_id"]}/play', {'seat': seat, 'request_id': f'{seat}-one', 'packet': first})
        post(app, f'/rounds/{second["packet_id"]}/play', {'seat': 'left', 'request_id': 'left-two', 'packet': second})
        status, payload = app.handle('POST', f'/sessions/{session["id"]}/close', {})
        self.assertEqual(status, 409)
        self.assertIn('missing_receipt', payload['error'])
        post(app, f'/rounds/{second["packet_id"]}/play', {'seat': 'right', 'request_id': 'right-two', 'packet': second})
        closed = post(app, f'/sessions/{session["id"]}/close', {})
        report_a = get(app, f'/reports/{session["id"]}')
        report_b = get(app, f'/reports/{closed["report_id"]}')
        self.assertEqual(report_a, report_b)
        self.assertEqual(report_a['rounds'][1]['right']['action'], None)

    def test_reopen_report(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        edition = seed_program(app)
        session = install_both(app, edition)
        packet = post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 1})
        for seat in ('left', 'right'):
            post(app, f'/rounds/{packet["packet_id"]}/play', {'seat': seat, 'request_id': f'{seat}-only', 'packet': packet})
        closed = post(app, f'/sessions/{session["id"]}/close', {})
        again = post(app, f'/sessions/{session["id"]}/close', {})
        self.assertEqual(closed, again)
