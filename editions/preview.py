from dataclasses import dataclass
import sqlite3
from materials.catalog import resolve_revision
from .linkage import solve_round
from .program import DraftProgram, DraftRound, FixedAction, read_draft
from .windows import first_overlap_beat, is_covered, spoken_interval

@dataclass(frozen=True)
class PublicationIssue:
    round_number: int
    seat: str | None
    kind: str
    beat: int | None

@dataclass(frozen=True)
class RoundPreview:
    number: int
    left_interval: tuple[int, int] | None
    right_interval: tuple[int, int] | None
    issues: tuple[PublicationIssue, ...]

def _duration(conn: sqlite3.Connection, action: FixedAction | None, cache: dict) -> int | None:
    if action is None:
        return None
    key = (action.clip_id, action.revision)
    if key not in cache:
        cache[key] = resolve_revision(conn, action.to_dict()).duration
    return cache[key]

def _pair_issues(conn: sqlite3.Connection, item: DraftRound, left: FixedAction | None, right: FixedAction | None, cache: dict) -> list[PublicationIssue]:
    left_interval = spoken_interval(left.start if left else None, _duration(conn, left, cache))
    right_interval = spoken_interval(right.start if right else None, _duration(conn, right, cache))
    issues = []
    if not is_covered(item.window, left_interval):
        issues.append(PublicationIssue(item.number, 'left', 'overrun', left_interval[1] if left_interval else None))
    if not is_covered(item.window, right_interval):
        issues.append(PublicationIssue(item.number, 'right', 'overrun', right_interval[1] if right_interval else None))
    overlap = first_overlap_beat(left_interval, right_interval)
    if overlap is not None:
        issues.append(PublicationIssue(item.number, 'both', 'overlap', overlap))
    return issues

def _round_bounds(conn: sqlite3.Connection, item: DraftRound) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
    cache: dict = {}
    if not item.linked:
        return (spoken_interval(item.left.start if item.left else None, _duration(conn, item.left, cache)),
                spoken_interval(item.right.start if item.right else None, _duration(conn, item.right, cache)))
    lefts = {pair.left for case in item.light_cases for pair in case.allowed}
    rights = {pair.right for case in item.light_cases for pair in case.allowed}
    def span(actions):
        intervals = [spoken_interval(action.start, _duration(conn, action, cache)) for action in actions if action is not None]
        intervals = [value for value in intervals if value is not None]
        if not intervals:
            return None
        return (min(value[0] for value in intervals), max(value[1] for value in intervals))
    return span(lefts), span(rights)

def evaluate_round(conn: sqlite3.Connection, item: DraftRound) -> RoundPreview:
    left_interval, right_interval = _round_bounds(conn, item)
    issues: list[PublicationIssue] = []
    cache: dict = {}
    if item.linked:
        seen = set()
        for case in item.light_cases:
            for pair in case.allowed:
                for issue in _pair_issues(conn, item, pair.left, pair.right, cache):
                    if issue not in seen:
                        seen.add(issue)
                        issues.append(issue)
        if solve_round(item.light_cases) is None:
            issues.append(PublicationIssue(item.number, None, 'unsolvable', None))
    else:
        issues.extend(_pair_issues(conn, item, item.left, item.right, cache))
    return RoundPreview(item.number, left_interval, right_interval, tuple(issues))

def preview_draft(conn: sqlite3.Connection, draft: DraftProgram | int) -> list[RoundPreview]:
    program = read_draft(conn, draft) if isinstance(draft, int) else draft
    return [evaluate_round(conn, item) for item in program.rounds]
