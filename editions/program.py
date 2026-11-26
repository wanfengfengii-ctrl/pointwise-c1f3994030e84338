from dataclasses import dataclass
import json
import sqlite3
from materials.catalog import resolve_revision
from .windows import BeatWindow, make_window

@dataclass(frozen=True)
class FixedAction:
    clip_id: int
    revision: int
    start: int

    def to_dict(self) -> dict:
        return {'clip_id': self.clip_id, 'revision': self.revision, 'start': self.start}

@dataclass(frozen=True)
class AllowedPair:
    left: FixedAction | None
    right: FixedAction | None

@dataclass(frozen=True)
class LightCase:
    left_light: int
    right_light: int
    allowed: tuple[AllowedPair, ...]

@dataclass(frozen=True)
class DraftRound:
    number: int
    window: BeatWindow
    left: FixedAction | None
    right: FixedAction | None
    light_cases: tuple[LightCase, ...] | None = None

    @property
    def linked(self) -> bool:
        return self.light_cases is not None

@dataclass(frozen=True)
class DraftProgram:
    id: int
    rounds: tuple[DraftRound, ...]

def initialize_drafts(conn: sqlite3.Connection) -> None:
    conn.execute('CREATE TABLE IF NOT EXISTS drafts (id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL)')
    conn.commit()

def _action(value: dict | None) -> FixedAction | None:
    if value is None:
        return None
    if not isinstance(value, dict) or type(value.get('clip_id')) is not int or type(value.get('revision')) is not int or type(value.get('start')) is not int or value['start'] < 0:
        raise ValueError('422:invalid fixed action')
    return FixedAction(value['clip_id'], value['revision'], value['start'])

def _action_key(action: FixedAction | None) -> tuple | None:
    if action is None:
        return None
    return (action.clip_id, action.revision, action.start)

def _allowed_pair(value: dict) -> AllowedPair:
    if not isinstance(value, dict) or 'left' not in value or 'right' not in value:
        raise ValueError('422:allowed entry must contain left and right')
    return AllowedPair(_action(value['left']), _action(value['right']))

def _light_cases(value) -> tuple[LightCase, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError('422:light_cases must be a non-empty list')
    cases = []
    seen_combinations = set()
    left_lights = set()
    right_lights = set()
    seat_actions = {'left': set(), 'right': set()}
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError('422:invalid light case')
        left_light = raw.get('left_light')
        right_light = raw.get('right_light')
        if type(left_light) is not int or type(right_light) is not int:
            raise ValueError('422:light numbers must be integers')
        combination = (left_light, right_light)
        if combination in seen_combinations:
            raise ValueError('422:duplicate light combination')
        allowed = raw.get('allowed')
        if not isinstance(allowed, list) or not allowed:
            raise ValueError('422:allowed plays are required')
        pairs = []
        for entry in allowed:
            pair = _allowed_pair(entry)
            pairs.append(pair)
            for seat, action in (('left', pair.left), ('right', pair.right)):
                if action is not None:
                    seat_actions[seat].add(_action_key(action))
        seen_combinations.add(combination)
        left_lights.add(left_light)
        right_lights.add(right_light)
        cases.append(LightCase(left_light, right_light, tuple(pairs)))
    if len(left_lights) > 4 or len(right_lights) > 4:
        raise ValueError('422:a seat may use at most four light numbers in a round')
    if len(seat_actions['left']) > 2 or len(seat_actions['right']) > 2:
        raise ValueError('422:a seat may use at most two non-silent actions in a round')
    return tuple(cases)

def _round(value: dict) -> DraftRound:
    if not isinstance(value, dict) or type(value.get('number')) is not int or value['number'] <= 0:
        raise ValueError('422:invalid round')
    window = make_window(value.get('lo'), value.get('hi'))
    if value.get('light_cases') is not None:
        if value.get('left') is not None or value.get('right') is not None:
            raise ValueError('422:linked round replaces fixed left and right')
        return DraftRound(value['number'], window, None, None, _light_cases(value['light_cases']))
    return DraftRound(value['number'], window, _action(value.get('left')), _action(value.get('right')))

def _encode_round(item: DraftRound) -> dict:
    encoded = {'number': item.number, 'lo': item.window.lo, 'hi': item.window.hi}
    if item.linked:
        encoded['light_cases'] = [
            {
                'left_light': case.left_light,
                'right_light': case.right_light,
                'allowed': [
                    {'left': pair.left.to_dict() if pair.left else None,
                     'right': pair.right.to_dict() if pair.right else None}
                    for pair in case.allowed
                ],
            }
            for case in item.light_cases
        ]
    else:
        encoded['left'] = item.left.to_dict() if item.left else None
        encoded['right'] = item.right.to_dict() if item.right else None
    return encoded

def _iter_actions(item: DraftRound):
    if item.linked:
        for case in item.light_cases:
            for pair in case.allowed:
                yield pair.left
                yield pair.right
    else:
        yield item.left
        yield item.right

def submit_draft(conn: sqlite3.Connection, payload: dict) -> DraftProgram:
    if not isinstance(payload, dict) or not isinstance(payload.get('rounds'), list) or not payload['rounds']:
        raise ValueError('422:rounds are required')
    rounds = tuple(sorted((_round(item) for item in payload['rounds']), key=lambda item: item.number))
    if len({item.number for item in rounds}) != len(rounds):
        raise ValueError('422:round numbers must be unique')
    for item in rounds:
        for action in _iter_actions(item):
            if action is not None:
                resolve_revision(conn, action.to_dict())
    initialize_drafts(conn)
    encoded = {'rounds': [_encode_round(item) for item in rounds]}
    cursor = conn.execute('INSERT INTO drafts(payload) VALUES (?)', (json.dumps(encoded, sort_keys=True),))
    conn.commit()
    return DraftProgram(cursor.lastrowid, rounds)

def read_draft(conn: sqlite3.Connection, draft_id: int) -> DraftProgram:
    row = conn.execute('SELECT id, payload FROM drafts WHERE id = ?', (draft_id,)).fetchone()
    if row is None:
        raise KeyError(f'draft {draft_id}')
    payload = json.loads(row[1])
    rounds = tuple(_round(item) for item in payload['rounds'])
    return DraftProgram(row[0], rounds)
