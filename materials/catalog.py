import sqlite3
from .revisions import ClipRevision, find_revision

def resolve_revision(conn: sqlite3.Connection, reference: dict) -> ClipRevision:
    if not isinstance(reference, dict):
        raise ValueError('422:revision reference must be an object')
    try:
        clip_id = reference['clip_id']
        revision = reference['revision']
    except KeyError as exc:
        raise ValueError('422:revision reference is incomplete') from exc
    if type(clip_id) is not int or type(revision) is not int:
        raise ValueError('422:revision identifiers must be integers')
    try:
        return find_revision(conn, clip_id, revision)
    except KeyError as exc:
        raise ValueError('422:unknown revision') from exc

def resolve_revision_set(conn: sqlite3.Connection, references: list[dict]) -> list[ClipRevision]:
    return [resolve_revision(conn, reference) for reference in references]
