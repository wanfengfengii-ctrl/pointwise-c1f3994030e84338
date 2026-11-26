"""演示报码联动：右席灯号相同，因左席报码不同而兑现不同句子，并回读收场复盘。"""
import json
import unittest
from tests.fixture import make_app, post, get


def _seed(app):
    short = post(app, '/clips', {'text': '请留步', 'duration': 2})
    long = post(app, '/clips', {'text': '前方进入安静场景', 'duration': 3})
    S = {'clip_id': short['clip_id'], 'revision': 1, 'start': 0}
    L = {'clip_id': long['clip_id'], 'revision': 1, 'start': 0}
    return S, L


def _publish(app, S, L):
    rows = [
        {'left_light': 0, 'right_light': 0, 'allowed': [{'left': None, 'right': S}]},
        {'left_light': 0, 'right_light': 1, 'allowed': [{'left': None, 'right': L}]},
        {'left_light': 1, 'right_light': 0, 'allowed': [{'left': None, 'right': L}]},
        {'left_light': 1, 'right_light': 1, 'allowed': [{'left': None, 'right': S}]},
    ]
    draft = post(app, '/drafts', {'rounds': [{'number': 1, 'lo': 0, 'hi': 3, 'light_cases': rows}]})
    return post(app, '/editions', {'draft_id': draft['id']})


class TestLinkageDemo(unittest.TestCase):
    def test_right_light_same_two_sentences_and_closeout(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        S, L = _seed(app)
        edition = _publish(app, S, L)
        assert edition['rounds'][0]['sender'] == 'left'

        scenes = []
        for left_light in (0, 1):
            session = post(app, '/sessions', {'edition_id': edition['id']})
            packets = {}
            for seat in ('left', 'right'):
                packets[seat] = get(app, f'/editions/{edition["id"]}?seat={seat}')
                post(app, '/installations', {'session_id': session['id'], 'seat': seat, 'packet': packets[seat]})
            packet = post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 1})
            # 右席先记灯，仍在等左席报码。
            waiting = post(app, f'/rounds/{packet["packet_id"]}/observe',
                           {'seat': 'right', 'request_id': f'r-{left_light}', 'packet': packet, 'light': 0})
            assert waiting == {'status': 'pending'}
            left = post(app, f'/rounds/{packet["packet_id"]}/observe',
                        {'seat': 'left', 'request_id': f'l-{left_light}', 'packet': packet, 'light': left_light})
            ticket = left['receipt']['signal']
            right = post(app, f'/rounds/{packet["packet_id"]}/signal',
                         {'seat': 'right', 'request_id': f'rs-{left_light}', 'packet': packet, 'signal': ticket})
            recovered = get(app, f'/receipts/r-{left_light}?seat=right')['receipt']
            assert recovered == right['receipt']
            closed = post(app, f'/sessions/{session["id"]}/close', {})
            report = get(app, f'/reports/{closed["report_id"]}')
            scenes.append({
                'left_light': left_light,
                'right_light': 0,
                'bit': ticket['bit'],
                'right_action': report['rounds'][0]['right']['action'],
                'left_receipt_light': report['rounds'][0]['left']['light'],
                'right_origin_request_id': report['rounds'][0]['right']['origin_request_id'],
            })

        assert scenes[0]['right_action']['clip_id'] == S['clip_id']
        assert scenes[1]['right_action']['clip_id'] == L['clip_id']
        assert scenes[0]['bit'] == 0 and scenes[1]['bit'] == 1
        expected = {
            'same_right_light': scenes[0]['right_light'] == scenes[1]['right_light'],
            'bits': [scenes[0]['bit'], scenes[1]['bit']],
            'sentences': [scenes[0]['right_action']['text'], scenes[1]['right_action']['text']],
            'distinct_sentences': scenes[0]['right_action']['clip_id'] != scenes[1]['right_action']['clip_id'],
            'origins': [scenes[0]['right_origin_request_id'], scenes[1]['right_origin_request_id']],
        }
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 'v8.linkage',
            'input': {'edition_id': edition['id'], 'sender': edition['rounds'][0]['sender']},
            'expected': {'same_right_light': True, 'bits': [0, 1], 'distinct_sentences': True},
            'actual': expected,
            'downstream_expected': 'two scenes share right light 0 but play 请留步 and 前方进入安静场景',
            'downstream_actual': {'scenes': scenes},
            'code_paths': ['editions/linkage.py', 'editions/release.py', 'editions/seat_packets.py',
                           'desks/linked.py', 'reports/reconcile.py'],
            'oracle': 'independent assertions on sender bit, frozen actions and closeout readback',
        }, ensure_ascii=False, sort_keys=True))
        self.assertEqual(expected['bits'], [0, 1])
        self.assertTrue(expected['distinct_sentences'])
        self.assertEqual(expected['origins'], ['l-0', 'l-1'])


if __name__ == '__main__':
    unittest.main()
