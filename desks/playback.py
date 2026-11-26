import sqlite3
from sessions.round_packets import RoundPacket, decode_round_packet
from .events import append_event, find_round_event
from .install import read_installed_program
from .receipts import match_replayed_request
from .store import desk_write_transaction

def validate_round_binding(path_packet_id: int, packet: RoundPacket) -> None:
    if path_packet_id != packet.packet_id:
        raise ValueError('409:route and packet round disagree')

def play_round(conn: sqlite3.Connection, path_packet_id: int, request_id: str, packet: RoundPacket | dict | str):
    packet = decode_round_packet(packet) if not isinstance(packet, RoundPacket) else packet
    validate_round_binding(path_packet_id, packet)
    if not request_id:
        raise ValueError('422:request_id is required')
    installed = read_installed_program(conn, packet.session_id)
    if installed.edition_id != packet.edition_id:
        raise ValueError('409:edition does not match installation')
    existing = match_replayed_request(conn, request_id, installed.seat, packet.__dict__)
    if existing is not None:
        return existing
    prior = find_round_event(conn, packet.session_id, packet.round_number)
    if prior is not None:
        raise ValueError('409:round already has a first receipt')
    frozen = next((item for item in installed.packet.rounds if item.number == packet.round_number), None)
    if frozen is None:
        raise ValueError('409:unknown round for seat packet')
    action = frozen.left if installed.seat == 'left' else frozen.right
    with desk_write_transaction(conn):
        return __import__('desks.receipts', fromlist=['_receipt'])._receipt(append_event(conn, packet.session_id, packet.edition_id, installed.seat, packet.round_number, request_id, packet.__dict__, action))
