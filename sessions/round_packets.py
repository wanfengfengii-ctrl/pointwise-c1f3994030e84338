from dataclasses import dataclass
import json

@dataclass(frozen=True)
class RoundPacket:
    packet_id: int
    session_id: int
    edition_id: int
    round_number: int
    order_index: int

def encode_round_packet(packet: RoundPacket) -> dict:
    return packet.__dict__.copy()

def decode_round_packet(value: dict | str) -> RoundPacket:
    payload = json.loads(value) if isinstance(value, str) else value
    return RoundPacket(int(payload['packet_id']), int(payload['session_id']), int(payload['edition_id']), int(payload['round_number']), int(payload['order_index']))
