from dataclasses import dataclass
import sqlite3
from .clips import find_clip

@dataclass(frozen=True)
class ClipRevision:
    clip_id: int
    revision: int
    text: str
    duration: int

def initialize_revisions(conn: sqlite3.Connection) -> None:
    conn.execute('CREATE TABLE IF NOT EXISTS clip_revisions (clip_id INTEGER NOT NULL, revision INTEGER NOT NULL, text TEXT NOT NULL, duration INTEGER NOT NULL, PRIMARY KEY(clip_id, revision))')
    conn.commit()

def append_revision(conn: sqlite3.Connection, clip_id: int, text: str, duration: int) -> ClipRevision:
    find_clip(conn, clip_id)
    initialize_revisions(conn)
    row = conn.execute('SELECT COALESCE(MAX(revision), 0) + 1 FROM clip_revisions WHERE clip_id = ?', (clip_id,)).fetchone()
    revision = int(row[0])
    conn.execute('INSERT INTO clip_revisions(clip_id, revision, text, duration) VALUES (?, ?, ?, ?)', (clip_id, revision, text, duration))
    conn.commit()
    return ClipRevision(clip_id, revision, text, duration)

def find_revision(conn: sqlite3.Connection, clip_id: int, revision: int) -> ClipRevision:
    row = conn.execute('SELECT clip_id, revision, text, duration FROM clip_revisions WHERE clip_id = ? AND revision = ?', (clip_id, revision)).fetchone()
    if row is None:
        raise KeyError(f'revision {clip_id}:{revision}')
    return ClipRevision(row[0], row[1], row[2], row[3])
