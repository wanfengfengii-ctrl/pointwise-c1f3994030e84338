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

def _normalise(receipt: dict, seat: str) -> dict:
    entry = {
        'request_id': receipt.get('request_id'),
        'session_id': receipt.get('session_id'),
        'edition_id': receipt.get('edition_id'),
        'seat': receipt.get('seat', seat),
        'round_number': receipt.get('round_number'),
        'action': receipt.get('action'),
        'sequence': receipt.get('sequence'),
    }
    # 普通轮保持原响应；联动轮另列灯号、报码及出票出处。
    if receipt.get('kind') == 'linked':
        entry['light'] = receipt.get('light')
        entry['signal'] = receipt.get('signal')
        entry['origin_request_id'] = receipt.get('origin_request_id')
    return entry

def reconcile_receipts(session_id: int, edition_id: int, expected_round_numbers: list[int], issued_rounds: list[dict], receipts_by_seat: dict[str, list[dict]]) -> CloseAudit:
    issues = []
    issued_numbers = {item['round_number'] for item in issued_rounds}
    for number in expected_round_numbers:
        if number not in issued_numbers:
            issues.append(unissued_round(number))
    receipts = []
    accepted: dict[tuple[int, str], dict] = {}
    for seat in ('left', 'right'):
        for receipt in receipts_by_seat.get(seat, []):
            if receipt.get('session_id') == session_id and receipt.get('edition_id') == edition_id and receipt.get('seat') == seat and receipt.get('round_number') in issued_numbers:
                if (receipt['round_number'], seat) not in accepted:
                    accepted[(receipt['round_number'], seat)] = _normalise(receipt, seat)
            else:
                issues.append(foreign_receipt(seat, receipt.get('round_number')))
    for number in sorted(issued_numbers):
        for seat in ('left', 'right'):
            entry = accepted.get((number, seat))
            if entry is None:
                issues.append(missing_receipt(seat, number))
            else:
                receipts.append(entry)
    return CloseAudit(session_id, edition_id, tuple(issued_rounds), tuple(receipts), tuple(order_close_issues(issues)))
