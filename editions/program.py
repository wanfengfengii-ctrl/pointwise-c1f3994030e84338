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
class DraftRound:
    number: int
    window: BeatWindow
    left: FixedAction | None
    right: FixedAction | None

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

def _round(value: dict) -> DraftRound:
    if not isinstance(value, dict) or type(value.get('number')) is not int or value['number'] <= 0:
        raise ValueError('422:invalid round')
    window = make_window(value.get('lo'), value.get('hi'))
    return DraftRound(value['number'], window, _action(value.get('left')), _action(value.get('right')))

def submit_draft(conn: sqlite3.Connection, payload: dict) -> DraftProgram:
    if not isinstance(payload, dict) or not isinstance(payload.get('rounds'), list) or not payload['rounds']:
        raise ValueError('422:rounds are required')
    rounds = tuple(sorted((_round(item) for item in payload['rounds']), key=lambda item: item.number))
    if len({item.number for item in rounds}) != len(rounds):
        raise ValueError('422:round numbers must be unique')
    for item in rounds:
        for action in (item.left, item.right):
            if action is not None:
                resolve_revision(conn, action.to_dict())
    initialize_drafts(conn)
    encoded = {'rounds': [{'number': item.number, 'lo': item.window.lo, 'hi': item.window.hi, 'left': item.left.to_dict() if item.left else None, 'right': item.right.to_dict() if item.right else None} for item in rounds]}
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
