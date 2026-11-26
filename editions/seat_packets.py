from dataclasses import dataclass
import json
from .release import Edition, FrozenRound

@dataclass(frozen=True)
class SeatPacket:
    edition_id: int
    seat: str
    rounds: tuple[dict, ...]

def _instruction(item: FrozenRound, seat: str) -> dict:
    """把冻结轮改写成该席可独立执行的指令，同时保留整轮原始字段。"""
    base = {'number': item.number, 'lo': item.lo, 'hi': item.hi,
            'left': item.left, 'right': item.right,
            'action': item.left if seat == 'left' else item.right,
            'linked': item.light_plan is not None, 'sender': item.sender,
            'role': None, 'plan': None}
    plan = item.light_plan
    if plan is None:
        return base
    base['action'] = None
    if plan['mode'] == 'silent':
        base['role'] = 'silent'
        base['plan'] = plan[seat]
        return base
    if plan['sender'] == seat:
        base['role'] = 'sender'
        base['plan'] = plan['sender_plan']
        return base
    base['role'] = 'receiver'
    base['plan'] = plan['receiver_plan']
    return base

def build_seat_packet(edition: Edition, seat: str) -> SeatPacket:
    if seat not in ('left', 'right'):
        raise ValueError('422:unknown seat')
    return SeatPacket(edition.id, seat, tuple(_instruction(item, seat) for item in edition.rounds))

def encode_seat_packet(packet: SeatPacket) -> dict:
    return {'edition_id': packet.edition_id, 'seat': packet.seat, 'rounds': [dict(item) for item in packet.rounds]}

def decode_seat_packet(value: dict | str) -> SeatPacket:
    payload = json.loads(value) if isinstance(value, str) else value
    if not isinstance(payload, dict) or payload.get('seat') not in ('left', 'right'):
        raise ValueError('422:invalid seat packet')
    rounds = tuple(dict(item) for item in payload['rounds'])
    return SeatPacket(int(payload['edition_id']), payload['seat'], rounds)
