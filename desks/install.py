from dataclasses import dataclass
import json
import sqlite3
from editions.seat_packets import SeatPacket, decode_seat_packet, encode_seat_packet
from .store import initialize_desk

@dataclass(frozen=True)
class InstalledProgram:
    session_id: int
    edition_id: int
    seat: str
    packet: SeatPacket

@dataclass(frozen=True)
class InstallationReceipt:
    session_id: int
    edition_id: int
    seat: str
    accepted: bool

def install_seat_packet(conn: sqlite3.Connection, session_id: int, packet: SeatPacket | dict | str) -> InstallationReceipt:
    initialize_desk(conn)
    packet = decode_seat_packet(packet) if not isinstance(packet, SeatPacket) else packet
    existing = conn.execute('SELECT edition_id, seat FROM installed_programs WHERE session_id = ?', (session_id,)).fetchone()
    if existing is not None and (existing[0] != packet.edition_id or existing[1] != packet.seat):
        raise ValueError('409:session already has another seat packet')
    payload = json.dumps(encode_seat_packet(packet), sort_keys=True)
    conn.execute('INSERT OR REPLACE INTO installed_programs(session_id, edition_id, seat, payload) VALUES (?, ?, ?, ?)', (session_id, packet.edition_id, packet.seat, payload))
    conn.commit()
    return InstallationReceipt(session_id, packet.edition_id, packet.seat, True)

def read_installed_program(conn: sqlite3.Connection, session_id: int) -> InstalledProgram:
    row = conn.execute('SELECT session_id, edition_id, seat, payload FROM installed_programs WHERE session_id = ?', (session_id,)).fetchone()
    if row is None:
        raise KeyError(f'installation {session_id}')
    return InstalledProgram(row[0], row[1], row[2], decode_seat_packet(row[3]))
