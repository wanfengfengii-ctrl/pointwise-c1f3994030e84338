"""席端办理联动轮：记灯与收码。

首执与触发它的本席输入在同一事务内落库；条件未齐只留待办，条件齐备后
重投任一原请求号都返回同一固定首执。查询路径只读，不产生首执。
"""
import json
import sqlite3
from sessions.round_packets import decode_round_packet
from .events import append_event, find_request_event
from .install import read_installed_program
from .linked_inputs import PendingInput, find_input, insert_input

LINKED_KIND = 'linked'

def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True)

def _receipt_dict(event) -> dict:
    return {
        'request_id': event.request_id,
        'session_id': event.session_id,
        'edition_id': event.edition_id,
        'seat': event.seat,
        'round_number': event.round_number,
        'action': event.action,
        'sequence': event.sequence,
        'light': event.light,
        'signal': event.signal,
        'origin_request_id': event.origin_request_id,
        'kind': event.kind,
    }

def _pending_dict(item: PendingInput) -> dict:
    return {
        'request_id': item.request_id,
        'session_id': item.session_id,
        'edition_id': item.edition_id,
        'seat': item.seat,
        'round_number': item.round_number,
        'action': None,
        'sequence': None,
        'light': item.light,
        'signal': item.signal,
        'origin_request_id': None,
        'kind': item.kind,
        'pending': True,
    }

def _binding(conn: sqlite3.Connection, path_packet_id: int, packet: dict, seat: str):
    decoded = decode_round_packet(packet)
    if decoded.packet_id != path_packet_id:
        raise ValueError('409:route and packet round disagree')
    try:
        installed = read_installed_program(conn, decoded.session_id)
    except KeyError as exc:
        raise ValueError('409:session is not installed on this seat') from exc
    if installed.edition_id != decoded.edition_id or installed.seat != seat:
        raise ValueError('409:edition does not match installation')
    frozen = next((item for item in installed.packet.rounds if item['number'] == decoded.round_number), None)
    if frozen is None:
        raise ValueError('409:unknown round for seat packet')
    if not frozen.get('linked'):
        raise ValueError('409:fixed round uses play')
    return decoded, frozen

def _round_inputs(conn: sqlite3.Connection, session_id: int, round_number: int, seat: str) -> list[PendingInput]:
    from .linked_inputs import _input
    rows = conn.execute('SELECT * FROM linked_inputs WHERE session_id = ? AND round_number = ? AND seat = ? ORDER BY input_id', (session_id, round_number, seat)).fetchall()
    return [_input(row) for row in rows]

def _round_receipt(conn: sqlite3.Connection, session_id: int, round_number: int, seat: str):
    from .events import _event
    row = conn.execute('SELECT * FROM desk_events WHERE session_id = ? AND round_number = ? AND seat = ?', (session_id, round_number, seat)).fetchone()
    return _event(row) if row else None

def _validate_observe(frozen: dict, light) -> None:
    if type(light) is not int:
        raise ValueError('422:light must be an integer')
    plan = frozen.get('plan') or {}
    if str(light) not in plan:
        raise ValueError('409:light is not defined for this seat in this round')

def _validate_signal(frozen: dict, seat: str, packet: dict, signal) -> None:
    if frozen.get('role') != 'receiver':
        raise ValueError('409:signal is only accepted by the receiving seat')
    if not isinstance(signal, dict):
        raise ValueError('422:signal must be an object')
    for key in ('packet', 'from_seat', 'from_request_id', 'bit'):
        if key not in signal:
            raise ValueError('422:signal is incomplete')
    from_seat = signal['from_seat']
    if from_seat not in ('left', 'right') or from_seat == seat:
        raise ValueError('409:signal comes from the wrong seat')
    if frozen.get('sender') != from_seat:
        raise ValueError('409:signal comes from the wrong sender')
    if type(signal['bit']) is not int or signal['bit'] not in (0, 1):
        raise ValueError('422:signal bit must be 0 or 1')
    if not isinstance(signal['from_request_id'], str) or not signal['from_request_id']:
        raise ValueError('422:signal ticket is incomplete')
    try:
        origin = decode_round_packet(signal['packet'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('409:signal packet does not belong to this round') from exc
    if (origin.session_id, origin.edition_id, origin.round_number, origin.packet_id) != (packet['session_id'], packet['edition_id'], packet['round_number'], packet['packet_id']):
        raise ValueError('409:signal packet does not belong to this round')

def _action_for(frozen: dict, light: int, bit: int | None):
    plan = frozen.get('plan') or {}
    role = frozen.get('role')
    key = str(light)
    if role in ('silent', 'sender'):
        if key not in plan:
            raise ValueError('409:light is not defined for this seat in this round')
        return plan[key] if role == 'silent' else plan[key]['action']
    by_bit = plan.get(key)
    if not isinstance(by_bit, dict) or str(bit) not in by_bit:
        raise ValueError('409:signal bit is not defined for this seat light')
    return by_bit[str(bit)]

def _outbound_ticket(frozen: dict, seat: str, request_id: str, light: int, packet: dict):
    if frozen.get('role') != 'sender':
        return None
    return {'packet': packet, 'from_seat': seat, 'from_request_id': request_id, 'bit': frozen['plan'][str(light)]['bit']}

def lookup(conn: sqlite3.Connection, request_id: str, seat: str):
    """返回 ('accepted'|'pending', payload) 或 (None, None)。只读。

    普通轮不走这里，由原查单路径平铺返回，保持原响应。
    """
    event = find_request_event(conn, request_id, seat)
    if event is not None:
        if getattr(event, 'kind', 'fixed') != LINKED_KIND:
            return None, None
        return 'accepted', _receipt_dict(event)
    item = find_input(conn, request_id, seat)
    if item is None:
        return None, None
    receipt = _round_receipt(conn, item.session_id, item.round_number, seat)
    if receipt is not None:
        return 'accepted', _receipt_dict(receipt)
    return 'pending', _pending_dict(item)

def submit_linked(conn: sqlite3.Connection, path_packet_id: int, body: dict, seat: str, kind: str):
    """返回 (状态, 载荷)，状态为 200 或 202。"""
    from .store import initialize_desk
    initialize_desk(conn)
    if not isinstance(body, dict):
        raise ValueError('422:body must be an object')
    request_id = body.get('request_id')
    if not isinstance(request_id, str) or not request_id:
        raise ValueError('422:request_id is required')
    if body.get('seat') is not None and body['seat'] != seat:
        raise ValueError('409:input does not belong to this seat')
    packet = body.get('packet')
    if not isinstance(packet, dict):
        raise ValueError('422:packet is required')
    _, frozen = _binding(conn, path_packet_id, packet, seat)
    light = body.get('light')
    signal = body.get('signal')
    if kind == 'observe':
        _validate_observe(frozen, light)
    else:
        _validate_signal(frozen, seat, packet, signal)

    event = find_request_event(conn, request_id, seat)
    if event is not None:
        if kind == 'observe' and event.request_id == request_id and event.light == light:
            return 200, {'receipt': _receipt_dict(event)}
        raise ValueError('409:request id parameters differ')
    item = find_input(conn, request_id, seat)
    if item is not None:
        if item.kind != kind or (kind == 'observe' and item.light != light) or (kind == 'signal' and _canonical(item.signal) != _canonical(signal)):
            raise ValueError('409:request id parameters differ')
        receipt = _round_receipt(conn, item.session_id, item.round_number, seat)
        if receipt is not None:
            return 200, {'receipt': _receipt_dict(receipt)}
        return 202, {'status': 'pending'}

    if _round_receipt(conn, packet['session_id'], packet['round_number'], seat) is not None:
        raise ValueError('409:round already has a first receipt')
    if any(existing.kind == kind for existing in _round_inputs(conn, packet['session_id'], packet['round_number'], seat)):
        raise ValueError('409:input already accepted for this operation')

    with conn:
        insert_input(conn, packet['session_id'], packet['edition_id'], seat, packet['round_number'], request_id, kind, packet, light, signal, ensure=False, commit=False)
        inputs = _round_inputs(conn, packet['session_id'], packet['round_number'], seat)
        observes = [existing for existing in inputs if existing.kind == 'observe']
        signals = [existing for existing in inputs if existing.kind == 'signal']
        role = frozen.get('role')
        complete = bool(observes) if role in ('sender', 'silent') else (bool(observes) and bool(signals))
        if not complete:
            return 202, {'status': 'pending'}
        observe = observes[0]
        used_signal = signals[0].signal if signals else None
        bit = used_signal['bit'] if used_signal is not None else None
        action = _action_for(frozen, observe.light, bit)
        if role == 'receiver':
            outbound = used_signal
            origin = used_signal['from_request_id']
        else:
            outbound = _outbound_ticket(frozen, seat, observe.request_id, observe.light, packet)
            origin = observe.request_id
        event = append_event(
            conn, packet['session_id'], packet['edition_id'], seat, packet['round_number'],
            observe.request_id, packet, action,
            light=observe.light, signal=outbound, origin_request_id=origin, kind=LINKED_KIND,
            ensure=False, commit=False,
        )
        return 200, {'receipt': _receipt_dict(event)}
