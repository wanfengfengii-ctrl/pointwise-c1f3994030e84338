import sqlite3
from .clips import create_clip, initialize_clips
from .revisions import append_revision, initialize_revisions

def validate_clip_input(text: str, duration: int) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ValueError('422:clip text must be non-empty')
    if type(duration) is not int or duration <= 0:
        raise ValueError('422:duration must be a positive integer')

def register_clip(conn: sqlite3.Connection, text: str, duration: int, clip_id: int | None = None) -> dict:
    validate_clip_input(text, duration)
    initialize_clips(conn)
    initialize_revisions(conn)
    with conn:
        if clip_id is None:
            clip = create_clip(conn, text.strip())
            clip_id = clip.id
        else:
            from .clips import find_clip
            find_clip(conn, clip_id)
        revision = append_revision(conn, clip_id, text.strip(), duration)
    return {'clip_id': revision.clip_id, 'revision': revision.revision, 'text': revision.text, 'duration': revision.duration}
