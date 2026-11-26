from dataclasses import dataclass
import sqlite3
from materials.catalog import resolve_revision
from .program import DraftProgram, DraftRound, FixedAction, read_draft
from .windows import first_overlap_beat, is_covered, spoken_interval

@dataclass(frozen=True)
class PublicationIssue:
    round_number: int
    seat: str
    kind: str
    beat: int | None

@dataclass(frozen=True)
class RoundPreview:
    number: int
    left_interval: tuple[int, int] | None
    right_interval: tuple[int, int] | None
    issues: tuple[PublicationIssue, ...]

def evaluate_round(conn: sqlite3.Connection, item: DraftRound) -> RoundPreview:
    durations = {}
    for action in (item.left, item.right):
        if action is not None:
            revision = resolve_revision(conn, action.to_dict())
            durations[(action.clip_id, action.revision)] = revision.duration
    left_duration = durations.get((item.left.clip_id, item.left.revision)) if item.left else None
    right_duration = durations.get((item.right.clip_id, item.right.revision)) if item.right else None
    left_interval = spoken_interval(item.left.start if item.left else None, left_duration)
    right_interval = spoken_interval(item.right.start if item.right else None, right_duration)
    issues = []
    if not is_covered(item.window, left_interval):
        issues.append(PublicationIssue(item.number, 'left', 'overrun', left_interval[1] if left_interval else None))
    if not is_covered(item.window, right_interval):
        issues.append(PublicationIssue(item.number, 'right', 'overrun', right_interval[1] if right_interval else None))
    overlap = first_overlap_beat(left_interval, right_interval)
    if overlap is not None:
        issues.append(PublicationIssue(item.number, 'both', 'overlap', overlap))
    return RoundPreview(item.number, left_interval, right_interval, tuple(issues))

def preview_draft(conn: sqlite3.Connection, draft: DraftProgram | int) -> list[RoundPreview]:
    program = read_draft(conn, draft) if isinstance(draft, int) else draft
    return [evaluate_round(conn, item) for item in program.rounds]
