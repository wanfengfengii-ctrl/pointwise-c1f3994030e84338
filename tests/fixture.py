import tempfile
from pathlib import Path
from sessions.service import build_workstation

def make_app():
    directory = tempfile.TemporaryDirectory()
    return directory, build_workstation(directory.name)

def post(app, path, body):
    status, payload = app.handle('POST', path, body)
    if status >= 400:
        raise AssertionError((status, payload))
    return payload

def get(app, path):
    status, payload = app.handle('GET', path)
    if status >= 400:
        raise AssertionError((status, payload))
    return payload

def seed_program(app, include_silence=False):
    short = post(app, '/clips', {'text': '请留步', 'duration': 2})
    long = post(app, '/clips', {'text': '下一段为安静场景', 'duration': 3})
    rounds = [{'number': 1, 'lo': 0, 'hi': 5, 'left': {'clip_id': short['clip_id'], 'revision': short['revision'], 'start': 0}, 'right': {'clip_id': long['clip_id'], 'revision': long['revision'], 'start': 2}}]
    if include_silence:
        rounds.append({'number': 2, 'lo': 0, 'hi': 4, 'left': {'clip_id': long['clip_id'], 'revision': long['revision'], 'start': 0}, 'right': None})
    draft = post(app, '/drafts', {'rounds': rounds})
    return post(app, '/editions', {'draft_id': draft['id']})

def install_both(app, edition):
    session = post(app, '/sessions', {'edition_id': edition['id']})
    for seat in ('left', 'right'):
        packet = get(app, f'/editions/{edition["id"]}?seat={seat}')
        post(app, '/installations', {'session_id': session['id'], 'seat': seat, 'packet': packet})
    return session
