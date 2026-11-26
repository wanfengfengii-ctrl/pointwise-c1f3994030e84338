import unittest
from tests.fixture import make_app, post, get

SHORT = {'text': '请留步', 'duration': 2}
LONG = {'text': '前方进入安静场景', 'duration': 3}


def seed_clips(app):
    short = post(app, '/clips', SHORT)
    long = post(app, '/clips', LONG)
    return {'clip_id': short['clip_id'], 'revision': 1, 'start': 0}, {'clip_id': long['clip_id'], 'revision': 1, 'start': 0}


def right_only_rows(S, L):
    """只允许右席发声的四行表：00→S, 01→L, 10→L, 11→S。"""
    return [
        {'left_light': 0, 'right_light': 0, 'allowed': [{'left': None, 'right': S}]},
        {'left_light': 0, 'right_light': 1, 'allowed': [{'left': None, 'right': L}]},
        {'left_light': 1, 'right_light': 0, 'allowed': [{'left': None, 'right': L}]},
        {'left_light': 1, 'right_light': 1, 'allowed': [{'left': None, 'right': S}]},
    ]


def publish(app, rows):
    draft = post(app, '/drafts', {'rounds': [{'number': 1, 'lo': 0, 'hi': 3, 'light_cases': rows}]})
    return post(app, '/editions', {'draft_id': draft['id']})


def open_and_install(app, edition):
    session = post(app, '/sessions', {'edition_id': edition['id']})
    packets = {}
    for seat in ('left', 'right'):
        packets[seat] = get(app, f'/editions/{edition["id"]}?seat={seat}')
        post(app, '/installations', {'session_id': session['id'], 'seat': seat, 'packet': packets[seat]})
    return session, packets


class TestLinkagePublication(unittest.TestCase):
    def test_sample_edition_sender_is_left_with_null_actions(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        S, L = seed_clips(app)
        edition = publish(app, right_only_rows(S, L))
        self.assertEqual(edition['rounds'][0]['sender'], 'left')
        self.assertIsNone(edition['rounds'][0]['left'])
        self.assertIsNone(edition['rounds'][0]['right'])
        plan = edition['rounds'][0]['light_plan']
        self.assertEqual(plan['mode'], 'signal')
        self.assertEqual(plan['sender_plan']['0']['action'], None)
        self.assertEqual(plan['sender_plan']['0']['bit'], 0)
        self.assertEqual(plan['sender_plan']['1']['bit'], 1)

    def test_left_only_speaks_flips_sender(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        S, L = seed_clips(app)
        rows = [
            {'left_light': 0, 'right_light': 0, 'allowed': [{'left': S, 'right': None}]},
            {'left_light': 0, 'right_light': 1, 'allowed': [{'left': L, 'right': None}]},
            {'left_light': 1, 'right_light': 0, 'allowed': [{'left': L, 'right': None}]},
            {'left_light': 1, 'right_light': 1, 'allowed': [{'left': S, 'right': None}]},
        ]
        edition = publish(app, rows)
        self.assertEqual(edition['rounds'][0]['sender'], 'right')

    def test_silent_solution_uses_no_signal(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        S, L = seed_clips(app)
        rows = [
            {'left_light': 0, 'right_light': 0, 'allowed': [{'left': None, 'right': None}]},
            {'left_light': 0, 'right_light': 1, 'allowed': [{'left': None, 'right': S}]},
        ]
        edition = publish(app, rows)
        plan = edition['rounds'][0]['light_plan']
        self.assertEqual(plan['mode'], 'silent')
        self.assertIsNone(edition['rounds'][0]['sender'])

    def test_unsolvable_table_is_rejected(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        S, L = seed_clips(app)
        rows = [
            {'left_light': 0, 'right_light': 0, 'allowed': [{'left': None, 'right': None}]},
            {'left_light': 0, 'right_light': 1, 'allowed': [{'left': S, 'right': None}]},
            {'left_light': 1, 'right_light': 0, 'allowed': [{'left': None, 'right': S}]},
        ]
        draft = post(app, '/drafts', {'rounds': [{'number': 1, 'lo': 0, 'hi': 3, 'light_cases': rows}]})
        preview = get(app, f'/drafts/{draft["id"]}/preview')
        self.assertIn('unsolvable', [issue['kind'] for issue in preview[0]['issues']])
        status, payload = app.handle('POST', '/editions', {'draft_id': draft['id']})
        self.assertEqual(status, 409)

    def test_three_right_actions_is_rejected(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        S, L = seed_clips(app)
        rows = [
            {'left_light': 0, 'right_light': 0, 'allowed': [{'left': None, 'right': S}]},
            {'left_light': 1, 'right_light': 0, 'allowed': [{'left': None, 'right': L}]},
            {'left_light': 2, 'right_light': 0, 'allowed': [{'left': None, 'right': None}]},
        ]
        draft = post(app, '/drafts', {'rounds': [{'number': 1, 'lo': 0, 'hi': 3, 'light_cases': rows}]})
        preview = get(app, f'/drafts/{draft["id"]}/preview')
        self.assertIn('unsolvable', [issue['kind'] for issue in preview[0]['issues']])
        status, _ = app.handle('POST', '/editions', {'draft_id': draft['id']})
        self.assertEqual(status, 409)

    def test_structural_validation(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        S, _ = seed_clips(app)
        cases = [
            [{'left_light': 0, 'right_light': 0, 'allowed': [{'left': None, 'right': S}]},
             {'left_light': 0, 'right_light': 0, 'allowed': [{'left': None, 'right': S}]}],
            [{'left_light': True, 'right_light': 0, 'allowed': [{'left': None, 'right': S}]}],
            [{'left_light': 0, 'right_light': 0, 'allowed': []}],
            [{'left_light': number, 'right_light': 0, 'allowed': [{'left': None, 'right': S}]} for number in range(5)],
        ]
        for rows in cases:
            status, _ = app.handle('POST', '/drafts', {'rounds': [{'number': 1, 'lo': 0, 'hi': 3, 'light_cases': rows}]})
            self.assertEqual(status, 422, rows)


class TestLinkedFieldFlow(unittest.TestCase):
    def _setup(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        S, L = seed_clips(app)
        edition = publish(app, right_only_rows(S, L))
        session, packets = open_and_install(app, edition)
        return app, session, packets, S, L

    def _round(self, app, session):
        return post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 1})

    def test_receiver_first_stays_pending_then_resolves(self):
        app, session, packets, S, L = self._setup()
        packet = self._round(app, session)
        status, _ = app.handle('POST', f'/rounds/{packet["packet_id"]}/observe',
                               {'seat': 'right', 'request_id': 'r-obs', 'packet': packet, 'light': 0})
        self.assertEqual(status, 202)
        self.assertEqual(get(app, '/receipts/r-obs')['receipt']['pending'], True)
        self.assertIsNone(get(app, '/receipts/r-obs')['receipt']['action'])

        left = post(app, f'/rounds/{packet["packet_id"]}/observe',
                    {'seat': 'left', 'request_id': 'l-obs', 'packet': packet, 'light': 0})
        ticket = left['receipt']['signal']
        self.assertEqual(ticket['bit'], 0)

        right = post(app, f'/rounds/{packet["packet_id"]}/signal',
                     {'seat': 'right', 'request_id': 'r-sig', 'packet': packet, 'signal': ticket})
        self.assertEqual(right['receipt']['action']['clip_id'], S['clip_id'])
        self.assertEqual(right['receipt']['origin_request_id'], 'l-obs')

    def test_signal_before_light(self):
        app, session, packets, S, L = self._setup()
        packet = self._round(app, session)
        left = post(app, f'/rounds/{packet["packet_id"]}/observe',
                    {'seat': 'left', 'request_id': 'l-obs', 'packet': packet, 'light': 1})
        ticket = left['receipt']['signal']
        self.assertEqual(ticket['bit'], 1)
        status, _ = app.handle('POST', f'/rounds/{packet["packet_id"]}/signal',
                               {'seat': 'right', 'request_id': 'r-sig', 'packet': packet, 'signal': ticket})
        self.assertEqual(get(app, '/receipts/r-sig')['receipt']['pending'], True)
        right = post(app, f'/rounds/{packet["packet_id"]}/observe',
                     {'seat': 'right', 'request_id': 'r-obs', 'packet': packet, 'light': 0})
        self.assertEqual(right['receipt']['action']['clip_id'], L['clip_id'])

    def test_misfiled_ticket_from_other_session_is_rejected(self):
        app, session, packets, S, L = self._setup()
        first = self._round(app, session)
        left = post(app, f'/rounds/{first["packet_id"]}/observe',
                    {'seat': 'left', 'request_id': 'l-obs', 'packet': first, 'light': 0})
        ticket = left['receipt']['signal']

        second_session = post(app, '/sessions', {'edition_id': packets['left']['edition_id']})
        for seat in ('left', 'right'):
            post(app, '/installations', {'session_id': second_session['id'], 'seat': seat, 'packet': packets[seat]})
        second = post(app, f'/sessions/{second_session["id"]}/rounds', {'round_number': 1})
        status, _ = app.handle('POST', f'/rounds/{second["packet_id"]}/signal',
                               {'seat': 'right', 'request_id': 'r-sig', 'packet': second, 'signal': ticket})
        self.assertEqual(status, 409)

    def test_wrong_sender_seat_is_rejected(self):
        app, session, packets, S, L = self._setup()
        packet = self._round(app, session)
        post(app, f'/rounds/{packet["packet_id"]}/observe',
             {'seat': 'right', 'request_id': 'r-obs', 'packet': packet, 'light': 0})
        bogus = {'packet': packet, 'from_seat': 'right', 'from_request_id': 'r-obs', 'bit': 0}
        status, _ = app.handle('POST', f'/rounds/{packet["packet_id"]}/signal',
                               {'seat': 'right', 'request_id': 'r-sig', 'packet': packet, 'signal': bogus})
        self.assertEqual(status, 409)

    def test_undefined_light_is_rejected(self):
        app, session, packets, S, L = self._setup()
        packet = self._round(app, session)
        status, _ = app.handle('POST', f'/rounds/{packet["packet_id"]}/observe',
                               {'seat': 'left', 'request_id': 'l-obs', 'packet': packet, 'light': 9})
        self.assertEqual(status, 409)

    def test_direct_play_on_linked_round_is_rejected(self):
        app, session, packets, S, L = self._setup()
        packet = self._round(app, session)
        status, _ = app.handle('POST', f'/rounds/{packet["packet_id"]}/play',
                               {'seat': 'left', 'request_id': 'l-play', 'packet': packet})
        self.assertEqual(status, 409)

    def test_replay_same_id_returns_fixed_receipt(self):
        app, session, packets, S, L = self._setup()
        packet = self._round(app, session)
        first = post(app, f'/rounds/{packet["packet_id"]}/observe',
                     {'seat': 'left', 'request_id': 'l-obs', 'packet': packet, 'light': 0})
        again = post(app, f'/rounds/{packet["packet_id"]}/observe',
                     {'seat': 'left', 'request_id': 'l-obs', 'packet': packet, 'light': 0})
        self.assertEqual(first, again)

    def test_changed_parameters_and_new_id_are_rejected(self):
        app, session, packets, S, L = self._setup()
        packet = self._round(app, session)
        post(app, f'/rounds/{packet["packet_id"]}/observe',
             {'seat': 'left', 'request_id': 'l-obs', 'packet': packet, 'light': 0})
        status, _ = app.handle('POST', f'/rounds/{packet["packet_id"]}/observe',
                               {'seat': 'left', 'request_id': 'l-obs', 'packet': packet, 'light': 1})
        self.assertEqual(status, 409)
        status, _ = app.handle('POST', f'/rounds/{packet["packet_id"]}/observe',
                               {'seat': 'left', 'request_id': 'l-obs-2', 'packet': packet, 'light': 0})
        self.assertEqual(status, 409)
        # 同一号改投另一操作也算改参。
        status, _ = app.handle('POST', f'/rounds/{packet["packet_id"]}/signal',
                               {'seat': 'left', 'request_id': 'l-obs', 'packet': packet, 'signal': {'packet': packet, 'from_seat': 'right', 'from_request_id': 'x', 'bit': 0}})
        self.assertEqual(status, 409)

    def test_recovered_pending_input_after_lost_response(self):
        app, session, packets, S, L = self._setup()
        packet = self._round(app, session)
        post(app, f'/rounds/{packet["packet_id"]}/observe',
             {'seat': 'right', 'request_id': 'r-obs', 'packet': packet, 'light': 0})
        # 视作失答，再用原号查回。
        pending = get(app, '/receipts/r-obs?seat=right')
        self.assertTrue(pending['receipt']['pending'])
        left = post(app, f'/rounds/{packet["packet_id"]}/observe',
                    {'seat': 'left', 'request_id': 'l-obs', 'packet': packet, 'light': 0})
        post(app, f'/rounds/{packet["packet_id"]}/signal',
             {'seat': 'right', 'request_id': 'r-sig', 'packet': packet, 'signal': left['receipt']['signal']})
        recovered = get(app, '/receipts/r-obs')
        self.assertEqual(recovered['receipt']['action']['clip_id'], S['clip_id'])
        self.assertEqual(recovered['receipt']['sequence'], 1)

    def test_reopen_seat_keeps_single_receipt(self):
        app, session, packets, S, L = self._setup()
        packet = self._round(app, session)
        post(app, f'/rounds/{packet["packet_id"]}/observe',
             {'seat': 'right', 'request_id': 'r-obs', 'packet': packet, 'light': 0})
        left = post(app, f'/rounds/{packet["packet_id"]}/observe',
                    {'seat': 'left', 'request_id': 'l-obs', 'packet': packet, 'light': 0})
        # 收码后、记灯前重开右席：丢弃最终响应，用原号查回。
        post(app, f'/rounds/{packet["packet_id"]}/signal',
             {'seat': 'right', 'request_id': 'r-sig', 'packet': packet, 'signal': left['receipt']['signal']})
        for request_id in ('r-obs', 'r-sig'):
            self.assertEqual(get(app, f'/receipts/{request_id}?seat=right')['receipt']['action']['clip_id'], S['clip_id'])
        closed = post(app, f'/sessions/{session["id"]}/close', {})
        report = get(app, f'/reports/{closed["report_id"]}')
        self.assertEqual(report['rounds'][0]['right']['sequence'], 1)

    def test_close_blocked_until_both_seats_done(self):
        app, session, packets, S, L = self._setup()
        packet = self._round(app, session)
        post(app, f'/rounds/{packet["packet_id"]}/observe',
             {'seat': 'right', 'request_id': 'r-obs', 'packet': packet, 'light': 0})
        status, payload = app.handle('POST', f'/sessions/{session["id"]}/close', {})
        self.assertEqual(status, 409)
        self.assertIn('missing_receipt', payload['error'])
        post(app, f'/rounds/{packet["packet_id"]}/observe',
             {'seat': 'left', 'request_id': 'l-obs', 'packet': packet, 'light': 0})
        status, _ = app.handle('POST', f'/sessions/{session["id"]}/close', {})
        self.assertEqual(status, 409)
        left = get(app, '/receipts/l-obs')['receipt']
        post(app, f'/rounds/{packet["packet_id"]}/signal',
             {'seat': 'right', 'request_id': 'r-sig', 'packet': packet, 'signal': left['signal']})
        closed = post(app, f'/sessions/{session["id"]}/close', {})
        report = get(app, f'/reports/{closed["report_id"]}')
        self.assertEqual(report['rounds'][0]['left']['light'], 0)
        self.assertEqual(report['rounds'][0]['right']['light'], 0)
        self.assertEqual(report['rounds'][0]['right']['signal']['from_request_id'], 'l-obs')
        self.assertEqual(report['rounds'][0]['right']['action']['clip_id'], S['clip_id'])

    def test_query_does_not_create_receipt(self):
        app, session, packets, S, L = self._setup()
        packet = self._round(app, session)
        status, _ = app.handle('GET', '/receipts/never-sent?seat=right')
        self.assertEqual(status, 404)
        post(app, f'/rounds/{packet["packet_id"]}/observe',
             {'seat': 'right', 'request_id': 'r-obs', 'packet': packet, 'light': 0})
        status, payload = app.handle('GET', '/receipts/r-obs')
        self.assertEqual(status, 200)
        self.assertTrue(payload['receipt']['pending'])


class TestLinkedWorkdayDemo(unittest.TestCase):
    def test_same_right_light_two_sentences_and_report(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        S, L = seed_clips(app)
        edition = publish(app, right_only_rows(S, L))
        sessions = []
        for left_light, expected in ((0, S), (1, L)):
            session, packets = open_and_install(app, edition)
            packet = post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 1})
            right = post(app, f'/rounds/{packet["packet_id"]}/observe',
                         {'seat': 'right', 'request_id': f'r-{left_light}', 'packet': packet, 'light': 0})
            self.assertEqual(right, {'status': 'pending'})
            # 左席先记灯再出票
            left = post(app, f'/rounds/{packet["packet_id"]}/observe',
                        {'seat': 'left', 'request_id': f'l-{left_light}', 'packet': packet, 'light': left_light})
            right = post(app, f'/rounds/{packet["packet_id"]}/signal',
                         {'seat': 'right', 'request_id': f'rs-{left_light}', 'packet': packet, 'signal': left['receipt']['signal']})
            self.assertEqual(right['receipt']['action']['clip_id'], expected['clip_id'])
            sessions.append((session, packet, right['receipt']['action']))
        first, second = sessions[0][2], sessions[1][2]
        self.assertEqual(first['clip_id'], S['clip_id'])
        self.assertEqual(second['clip_id'], L['clip_id'])
        self.assertNotEqual(first['clip_id'], second['clip_id'])
        for session, packet, action in sessions:
            closed = post(app, f'/sessions/{session["id"]}/close', {})
            report = get(app, f'/reports/{closed["report_id"]}')
            self.assertEqual(report['rounds'][0]['right']['action']['clip_id'], action['clip_id'])

    def test_fixed_round_keeps_original_play(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        S, L = seed_clips(app)
        draft = post(app, '/drafts', {'rounds': [{'number': 1, 'lo': 0, 'hi': 3, 'left': S, 'right': None}]})
        edition = post(app, '/editions', {'draft_id': draft['id']})
        session, packets = open_and_install(app, edition)
        packet = post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 1})
        for seat in ('left', 'right'):
            receipt = post(app, f'/rounds/{packet["packet_id"]}/play',
                           {'seat': seat, 'request_id': f'{seat}-fixed', 'packet': packet})
            self.assertIsNone(receipt.get('light', None))
        closed = post(app, f'/sessions/{session["id"]}/close', {})
        report = get(app, f'/reports/{closed["report_id"]}')
        self.assertEqual(report['rounds'][0]['left']['action']['clip_id'], S['clip_id'])
        self.assertIsNone(report['rounds'][0]['right']['action'])

    def test_mixed_fixed_and_linked_rounds(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        S, L = seed_clips(app)
        draft = post(app, '/drafts', {'rounds': [
            {'number': 1, 'lo': 0, 'hi': 3, 'left': S, 'right': None},
            {'number': 2, 'lo': 0, 'hi': 3, 'light_cases': right_only_rows(S, L)},
        ]})
        edition = post(app, '/editions', {'draft_id': draft['id']})
        session, packets = open_and_install(app, edition)
        first = post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 1})
        second = post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 2})
        for seat in ('left', 'right'):
            post(app, f'/rounds/{first["packet_id"]}/play', {'seat': seat, 'request_id': f'{seat}-1', 'packet': first})
        post(app, f'/rounds/{second["packet_id"]}/observe',
             {'seat': 'right', 'request_id': 'r-2', 'packet': second, 'light': 1})
        left = post(app, f'/rounds/{second["packet_id"]}/observe',
                    {'seat': 'left', 'request_id': 'l-2', 'packet': second, 'light': 0})
        post(app, f'/rounds/{second["packet_id"]}/signal',
             {'seat': 'right', 'request_id': 'rs-2', 'packet': second, 'signal': left['receipt']['signal']})
        closed = post(app, f'/sessions/{session["id"]}/close', {})
        report = get(app, f'/reports/{closed["report_id"]}')
        self.assertEqual(len(report['rounds']), 2)
        self.assertEqual(report['rounds'][1]['right']['action']['clip_id'], L['clip_id'])


if __name__ == '__main__':
    unittest.main()


class TestSilentLinkage(unittest.TestCase):
    def test_silent_plan_resolves_without_signal(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        S, L = seed_clips(app)
        rows = [
            {'left_light': 0, 'right_light': 0, 'allowed': [{'left': None, 'right': None}]},
            {'left_light': 0, 'right_light': 1, 'allowed': [{'left': None, 'right': S}]},
        ]
        edition = publish(app, rows)
        session, packets = open_and_install(app, edition)
        packet = post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 1})
        left = post(app, f'/rounds/{packet["packet_id"]}/observe',
                    {'seat': 'left', 'request_id': 'l-0', 'packet': packet, 'light': 0})
        self.assertEqual(left['receipt']['action'], None)
        self.assertIsNone(left['receipt']['signal'])
        right = post(app, f'/rounds/{packet["packet_id"]}/observe',
                     {'seat': 'right', 'request_id': 'r-1', 'packet': packet, 'light': 1})
        self.assertEqual(right['receipt']['action']['clip_id'], S['clip_id'])
        self.assertIsNone(right['receipt']['signal'])
        closed = post(app, f'/sessions/{session["id"]}/close', {})
        report = get(app, f'/reports/{closed["report_id"]}')
        self.assertIsNone(report['rounds'][0]['left']['action'])
        self.assertEqual(report['rounds'][0]['right']['action']['clip_id'], S['clip_id'])


class TestDeskStandalone(unittest.TestCase):
    def test_desk_service_runs_issued_round_offline(self):
        import tempfile
        from desks.service import build_desk_server
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        S, L = seed_clips(app)
        edition = publish(app, right_only_rows(S, L))
        session, packets = open_and_install(app, edition)
        packet = post(app, f'/sessions/{session["id"]}/rounds', {'round_number': 1})

        left_desk = build_desk_server(directory.name, 'left')
        right_desk = build_desk_server(directory.name, 'right')
        status, left = left_desk.handle('POST', f'/rounds/{packet["packet_id"]}/observe',
                                        {'request_id': 'l-0', 'packet': packet, 'light': 0})
        self.assertEqual(status, 200)
        status, pending = right_desk.handle('POST', f'/rounds/{packet["packet_id"]}/observe',
                                            {'request_id': 'r-0', 'packet': packet, 'light': 0})
        self.assertEqual(status, 202)
        self.assertEqual(pending, {'status': 'pending'})
        status, right = right_desk.handle('POST', f'/rounds/{packet["packet_id"]}/signal',
                                          {'request_id': 'r-sig', 'packet': packet, 'signal': left['receipt']['signal']})
        self.assertEqual(status, 200)
        self.assertEqual(right['receipt']['action']['clip_id'], S['clip_id'])
        status, queried = right_desk.handle('GET', '/receipts/r-0', None)
        self.assertEqual(queried['receipt']['action']['clip_id'], S['clip_id'])
        closed = post(app, f'/sessions/{session["id"]}/close', {})
        report = get(app, f'/reports/{closed["report_id"]}')
        self.assertEqual(report['rounds'][0]['right']['origin_request_id'], 'l-0')
