from dataclasses import dataclass
import json
import sqlite3
from materials.catalog import resolve_revision
from .linkage import solve_round
from .program import DraftProgram, FixedAction, read_draft
from .preview import preview_draft

@dataclass(frozen=True)
class FrozenRound:
    number: int
    lo: int
    hi: int
    left: dict | None
    right: dict | None
    sender: str | None = None
    light_plan: dict | None = None

@dataclass(frozen=True)
class Edition:
    id: int
    draft_id: int
    rounds: tuple[FrozenRound, ...]

def initialize_editions(conn: sqlite3.Connection) -> None:
    conn.execute('CREATE TABLE IF NOT EXISTS editions (id INTEGER PRIMARY KEY AUTOINCREMENT, draft_id INTEGER NOT NULL, payload TEXT NOT NULL)')
    conn.commit()

def _freeze_action(conn: sqlite3.Connection, action: FixedAction | None) -> dict | None:
    if action is None:
        return None
    revision = resolve_revision(conn, action.to_dict())
    return {'clip_id': action.clip_id, 'revision': action.revision, 'start': action.start, 'text': revision.text, 'duration': revision.duration}

def _freeze_action_value(conn: sqlite3.Connection, value) -> dict | None:
    if value is None:
        return None
    return _freeze_action(conn, FixedAction(value[0], value[1], value[2]))

def _freeze_plan(conn: sqlite3.Connection, plan: dict) -> dict:
    frozen = {'mode': plan['mode'], 'sender': plan['sender']}
    if plan['mode'] == 'silent':
        frozen['left'] = {str(light): _freeze_action_value(conn, action) for light, action in plan['silent_plan']['left'].items()}
        frozen['right'] = {str(light): _freeze_action_value(conn, action) for light, action in plan['silent_plan']['right'].items()}
    else:
        frozen['sender_plan'] = {str(light): {'action': _freeze_action_value(conn, value['action']), 'bit': value['bit']} for light, value in plan['sender_plan'].items()}
        frozen['receiver_plan'] = {str(light): {str(bit): _freeze_action_value(conn, action) for bit, action in by_bit.items()} for light, by_bit in plan['receiver_plan'].items()}
    return frozen

def _freeze_round(conn: sqlite3.Connection, item) -> FrozenRound:
    if not item.linked:
        return FrozenRound(item.number, item.window.lo, item.window.hi, _freeze_action(conn, item.left), _freeze_action(conn, item.right))
    plan = solve_round(item.light_cases)
    if plan is None:
        raise ValueError('409:publication rejected')
    if plan['mode'] == 'silent':
        silent = (plan['silent_plan']['left'].get('0'), plan['silent_plan']['right'].get('0'))
        left = _freeze_action_value(conn, silent[0])
        right = _freeze_action_value(conn, silent[1])
    else:
        left = right = None
    return FrozenRound(item.number, item.window.lo, item.window.hi, left, right, plan['sender'], _freeze_plan(conn, plan))

def _round_payload(item: FrozenRound) -> dict:
    if item.light_plan is None:
        return {'number': item.number, 'lo': item.lo, 'hi': item.hi, 'left': item.left, 'right': item.right}
    return {'number': item.number, 'lo': item.lo, 'hi': item.hi, 'left': item.left, 'right': item.right,
            'sender': item.sender, 'light_plan': item.light_plan}

def issue_edition(conn: sqlite3.Connection, draft_id: int) -> Edition:
    draft = read_draft(conn, draft_id)
    previews = preview_draft(conn, draft)
    issues = [issue for item in previews for issue in item.issues]
    if issues:
        raise ValueError('409:publication rejected')
    rounds = tuple(_freeze_round(conn, item) for item in draft.rounds)
    initialize_editions(conn)
    payload = {'draft_id': draft_id, 'rounds': [_round_payload(item) for item in rounds]}
    cursor = conn.execute('INSERT INTO editions(draft_id, payload) VALUES (?, ?)', (draft_id, json.dumps(payload, sort_keys=True)))
    conn.commit()
    return Edition(cursor.lastrowid, draft_id, rounds)

def read_edition(conn: sqlite3.Connection, edition_id: int) -> Edition:
    row = conn.execute('SELECT id, draft_id, payload FROM editions WHERE id = ?', (edition_id,)).fetchone()
    if row is None:
        raise KeyError(f'edition {edition_id}')
    payload = json.loads(row[2])
    rounds = tuple(FrozenRound(item['number'], item['lo'], item['hi'], item['left'], item['right'], item.get('sender'), item.get('light_plan')) for item in payload['rounds'])
    return Edition(row[0], row[1], rounds)

def find_frozen_round(conn: sqlite3.Connection, edition_id: int, round_number: int) -> FrozenRound:
    edition = read_edition(conn, edition_id)
    for item in edition.rounds:
        if item.number == round_number:
            return item
    raise KeyError(f'round {round_number}')
