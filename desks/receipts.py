from dataclasses import dataclass
import sqlite3
from .events import DeskEvent, find_request_event, list_session_events

@dataclass(frozen=True)
class PlaybackReceipt:
    request_id: str
    session_id: int
    edition_id: int
    seat: str
    round_number: int
    action: dict | None
    sequence: int

def _receipt(event: DeskEvent) -> PlaybackReceipt:
    return PlaybackReceipt(event.request_id, event.session_id, event.edition_id, event.seat, event.round_number, event.action, event.sequence)

def read_receipt(conn: sqlite3.Connection, request_id: str, seat: str) -> PlaybackReceipt:
    event = find_request_event(conn, request_id, seat)
    if event is None:
        raise KeyError(f'receipt {request_id}')
    return _receipt(event)

def match_replayed_request(conn: sqlite3.Connection, request_id: str, seat: str, packet: dict) -> PlaybackReceipt | None:
    event = find_request_event(conn, request_id, seat)
    if event is None:
        return None
    if event.packet != packet:
        raise ValueError('409:request id parameters differ')
    return _receipt(event)

def read_session_receipts(conn: sqlite3.Connection, session_id: int) -> list[PlaybackReceipt]:
    return [_receipt(event) for event in list_session_events(conn, session_id)]
