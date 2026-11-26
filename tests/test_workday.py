import json
import unittest
from tests.fixture import make_app, post, get, seed_program, install_both

class TestWorkday(unittest.TestCase):
    def test_complete_workday_and_print_scenario(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        edition = seed_program(app, include_silence=True)
        session = install_both(app, edition)
        packets = [post(app, f'/sessions/{session["id"]}/rounds', {'round_number': number}) for number in (1, 2)]
        for packet in packets:
            for seat in ('left', 'right'):
                post(app, f'/rounds/{packet["packet_id"]}/play', {'seat': seat, 'request_id': f'{seat}-{packet["round_number"]}', 'packet': packet})
        closed = post(app, f'/sessions/{session["id"]}/close', {})
        report = get(app, f'/reports/{closed["report_id"]}')
        expected = {'rounds': 2, 'silent_round': 2}
        actual = {'rounds': len(report['rounds']), 'silent_round': next(item['round_number'] for item in report['rounds'] if item['right']['action'] is None)}
        self.assertEqual(actual, expected)
        print('POINTWISE_SCENARIO ' + json.dumps({'case_id': 'v8.workday', 'input': {'edition_id': edition['id'], 'session_id': session['id']}, 'expected': expected, 'actual': actual, 'downstream_expected': 'frozen report has two rounds and a right-seat silence receipt', 'downstream_actual': {'report_id': report['report_id'], 'rounds': report['rounds']}, 'code_paths': ['editions/windows.py', 'editions/preview.py', 'sessions/rounds.py', 'desks/playback.py', 'reports/reconcile.py', 'reports/archive.py'], 'oracle': 'independent assertions on half-open intervals, receipt count, and report snapshot'}, ensure_ascii=False, sort_keys=True))

if __name__ == '__main__':
    unittest.main()
