from dataclasses import dataclass
import json
import sqlite3
from materials.catalog import resolve_revision
from .program import DraftProgram, FixedAction, read_draft
from .preview import preview_draft

@dataclass(frozen=True)
class FrozenRound:
    number: int
    lo: int
    hi: int
    left: dict | None
    right: dict | None

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

def issue_edition(conn: sqlite3.Connection, draft_id: int) -> Edition:
    draft = read_draft(conn, draft_id)
    previews = preview_draft(conn, draft)
    issues = [issue for item in previews for issue in item.issues]
    if issues:
        raise ValueError('409:publication rejected')
    rounds = tuple(FrozenRound(item.number, item.window.lo, item.window.hi, _freeze_action(conn, item.left), _freeze_action(conn, item.right)) for item in draft.rounds)
    initialize_editions(conn)
    payload = {'draft_id': draft_id, 'rounds': [item.__dict__ for item in rounds]}
    cursor = conn.execute('INSERT INTO editions(draft_id, payload) VALUES (?, ?)', (draft_id, json.dumps(payload, sort_keys=True)))
    conn.commit()
    return Edition(cursor.lastrowid, draft_id, rounds)

def read_edition(conn: sqlite3.Connection, edition_id: int) -> Edition:
    row = conn.execute('SELECT id, draft_id, payload FROM editions WHERE id = ?', (edition_id,)).fetchone()
    if row is None:
        raise KeyError(f'edition {edition_id}')
    payload = json.loads(row[2])
    rounds = tuple(FrozenRound(item['number'], item['lo'], item['hi'], item['left'], item['right']) for item in payload['rounds'])
    return Edition(row[0], row[1], rounds)

def find_frozen_round(conn: sqlite3.Connection, edition_id: int, round_number: int) -> FrozenRound:
    edition = read_edition(conn, edition_id)
    for item in edition.rounds:
        if item.number == round_number:
            return item
    raise KeyError(f'round {round_number}')
