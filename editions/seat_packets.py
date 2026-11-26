from dataclasses import dataclass
import json
import sqlite3
from .release import Edition, FrozenRound, read_edition

@dataclass(frozen=True)
class SeatPacket:
    edition_id: int
    seat: str
    rounds: tuple[FrozenRound, ...]

def build_seat_packet(edition: Edition, seat: str) -> SeatPacket:
    if seat not in ('left', 'right'):
        raise ValueError('422:unknown seat')
    return SeatPacket(edition.id, seat, edition.rounds)

def encode_seat_packet(packet: SeatPacket) -> dict:
    return {'edition_id': packet.edition_id, 'seat': packet.seat, 'rounds': [item.__dict__ for item in packet.rounds]}

def decode_seat_packet(value: dict | str) -> SeatPacket:
    payload = json.loads(value) if isinstance(value, str) else value
    if not isinstance(payload, dict) or payload.get('seat') not in ('left', 'right'):
        raise ValueError('422:invalid seat packet')
    rounds = tuple(FrozenRound(item['number'], item['lo'], item['hi'], item.get('left'), item.get('right')) for item in payload['rounds'])
    return SeatPacket(int(payload['edition_id']), payload['seat'], rounds)
