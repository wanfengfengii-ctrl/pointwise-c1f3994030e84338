import unittest
from tests.fixture import make_app, post, get

class TestPublication(unittest.TestCase):
    def test_adjacent_intervals(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        short = post(app, '/clips', {'text': '短句', 'duration': 2})
        long = post(app, '/clips', {'text': '长句', 'duration': 3})
        draft = post(app, '/drafts', {'rounds': [{'number': 1, 'lo': 0, 'hi': 5, 'left': {'clip_id': short['clip_id'], 'revision': 1, 'start': 0}, 'right': {'clip_id': long['clip_id'], 'revision': 1, 'start': 2}}]})
        preview = get(app, f'/drafts/{draft["id"]}/preview')
        self.assertEqual(preview[0]['issues'], [])
        edition = post(app, '/editions', {'draft_id': draft['id']})
        self.assertEqual(edition['rounds'][0]['left']['duration'], 2)

    def test_overlap_rejected(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        short = post(app, '/clips', {'text': '短句', 'duration': 2})
        long = post(app, '/clips', {'text': '长句', 'duration': 3})
        draft = post(app, '/drafts', {'rounds': [{'number': 1, 'lo': 0, 'hi': 5, 'left': {'clip_id': short['clip_id'], 'revision': 1, 'start': 0}, 'right': {'clip_id': long['clip_id'], 'revision': 1, 'start': 1}}]})
        preview = get(app, f'/drafts/{draft["id"]}/preview')
        self.assertEqual(preview[0]['issues'][0]['kind'], 'overlap')
        status, payload = app.handle('POST', '/editions', {'draft_id': draft['id']})
        self.assertEqual(status, 409)
        self.assertIn('publication rejected', payload['error'])

    def test_frozen_clip(self):
        directory, app = make_app()
        self.addCleanup(directory.cleanup)
        clip = post(app, '/clips', {'text': '原句', 'duration': 3})
        draft = post(app, '/drafts', {'rounds': [{'number': 1, 'lo': 0, 'hi': 4, 'left': {'clip_id': clip['clip_id'], 'revision': 1, 'start': 0}, 'right': None}]})
        edition = post(app, '/editions', {'draft_id': draft['id']})
        post(app, '/clips', {'clip_id': clip['clip_id'], 'text': '新版', 'duration': 4})
        frozen = get(app, f'/editions/{edition["id"]}?seat=left')
        self.assertEqual(frozen['rounds'][0]['left']['text'], '原句')
        self.assertEqual(frozen['rounds'][0]['left']['duration'], 3)
