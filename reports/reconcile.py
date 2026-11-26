from dataclasses import dataclass
from .exceptions import CloseIssue, foreign_receipt, missing_receipt, order_close_issues, unissued_round

@dataclass(frozen=True)
class CloseAudit:
    session_id: int
    edition_id: int
    issued_rounds: tuple[dict, ...]
    receipts: tuple[dict, ...]
    issues: tuple[CloseIssue, ...]

    @property
    def complete(self):
        return not self.issues

def reconcile_receipts(session_id: int, edition_id: int, expected_round_numbers: list[int], issued_rounds: list[dict], receipts_by_seat: dict[str, list[dict]]) -> CloseAudit:
    issues = []
    issued_numbers = {item['round_number'] for item in issued_rounds}
    for number in expected_round_numbers:
        if number not in issued_numbers:
            issues.append(unissued_round(number))
    receipts = []
    for seat in ('left', 'right'):
        for receipt in receipts_by_seat.get(seat, []):
            receipts.append(receipt)
            if receipt.get('session_id') != session_id or receipt.get('edition_id') != edition_id or receipt.get('seat') != seat or receipt.get('round_number') not in issued_numbers:
                issues.append(foreign_receipt(seat, receipt.get('round_number')))
    for number in sorted(issued_numbers):
        for seat in ('left', 'right'):
            matching = [item for item in receipts_by_seat.get(seat, []) if item.get('session_id') == session_id and item.get('edition_id') == edition_id and item.get('round_number') == number and item.get('seat') == seat]
            if not matching:
                issues.append(missing_receipt(seat, number))
    return CloseAudit(session_id, edition_id, tuple(issued_rounds), tuple(receipts), tuple(order_close_issues(issues)))
