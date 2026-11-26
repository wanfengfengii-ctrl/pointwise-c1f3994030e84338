from dataclasses import dataclass
import sqlite3

@dataclass(frozen=True)
class Clip:
    id: int
    label: str

def initialize_clips(conn: sqlite3.Connection) -> None:
    conn.execute('CREATE TABLE IF NOT EXISTS clips (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL)')
    conn.commit()

def create_clip(conn: sqlite3.Connection, label: str) -> Clip:
    initialize_clips(conn)
    cursor = conn.execute('INSERT INTO clips(label) VALUES (?)', (label,))
    conn.commit()
    return Clip(cursor.lastrowid, label)

def find_clip(conn: sqlite3.Connection, clip_id: int) -> Clip:
    row = conn.execute('SELECT id, label FROM clips WHERE id = ?', (clip_id,)).fetchone()
    if row is None:
        raise KeyError(f'clip {clip_id}')
    return Clip(row[0], row[1])
