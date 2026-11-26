from dataclasses import dataclass

@dataclass(frozen=True)
class CloseIssue:
    kind: str
    seat: str | None
    round_number: int | None
    detail: str

def unissued_round(round_number: int) -> CloseIssue:
    return CloseIssue('unissued_round', None, round_number, 'round was not issued')

def missing_receipt(seat: str, round_number: int) -> CloseIssue:
    return CloseIssue('missing_receipt', seat, round_number, 'seat has no first receipt')

def foreign_receipt(seat: str, round_number: int) -> CloseIssue:
    return CloseIssue('foreign_receipt', seat, round_number, 'receipt belongs to another session or round')

def order_close_issues(issues: list[CloseIssue]) -> list[CloseIssue]:
    return sorted(issues, key=lambda item: (item.round_number if item.round_number is not None else -1, item.seat or '', item.kind))
