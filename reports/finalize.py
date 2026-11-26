from dataclasses import dataclass
from .reconcile import CloseAudit

@dataclass(frozen=True)
class ReportRound:
    round_number: int
    left: dict
    right: dict

@dataclass(frozen=True)
class Closeout:
    report_id: int | None
    session_id: int
    edition_id: int
    rounds: tuple[ReportRound, ...]

def freeze_report(audit: CloseAudit, report_id: int | None = None) -> Closeout:
    by_key = {(item['round_number'], item['seat']): item for item in audit.receipts}
    rounds = tuple(ReportRound(number, by_key[(number, 'left')], by_key[(number, 'right')]) for number in sorted({item['round_number'] for item in audit.issued_rounds}))
    return Closeout(report_id, audit.session_id, audit.edition_id, rounds)
