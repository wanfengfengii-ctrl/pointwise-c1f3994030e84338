"""按轮求解一套能覆盖整张灯况表的席位指令。

动作以素材号、修订号和起拍为键；``None`` 表示静默。服务端在发行时冻结
所选方案，席位后续只按方案执行，不再重新求解。
"""

SENDER_ORDER = ('left', 'right')
BIT_VALUES = (0, 1)


def action_key(action):
    if action is None:
        return None
    if hasattr(action, 'clip_id'):
        return (action.clip_id, action.revision, action.start)
    return (action['clip_id'], action['revision'], action['start'])


def _order(key):
    return (-1, -1, -1) if key is None else key


def _sorted_actions(actions):
    return sorted(actions, key=_order)


def _cases(light_cases):
    """返回 [(left_light, right_light, [(left_key, right_key), ...]), ...]。"""
    cases = []
    for case in light_cases:
        pairs = [(action_key(pair.left), action_key(pair.right)) for pair in case.allowed]
        cases.append((case.left_light, case.right_light, pairs))
    return cases


def _lights(cases, index):
    seen = []
    for case in cases:
        value = case[index]
        if value not in seen:
            seen.append(value)
    return seen


def _solve_silent(cases):
    left_lights = _lights(cases, 0)
    right_lights = _lights(cases, 1)
    left_domains = {}
    for light in left_lights:
        pairs = [pair for case in cases if case[0] == light for pair in case[2]]
        if not pairs:
            return None
        left_domains[light] = _sorted_actions({pair[0] for pair in pairs})
    # 逐灯枚举左席动作，右席动作在给定左席动作后收紧。
    def walk(index, chosen):
        if index == len(left_lights):
            return _solve_right(cases, right_lights, chosen)
        light = left_lights[index]
        for action in left_domains[light]:
            chosen[light] = action
            result = walk(index + 1, chosen)
            if result is not None:
                return result
        chosen.pop(light, None)
        return None

    return walk(0, {})


def _solve_right(cases, right_lights, left_map):
    right_map = {}
    for light in right_lights:
        candidates = None
        for case in cases:
            if case[1] != light:
                continue
            allowed = {pair[1] for pair in case[2] if pair[0] == left_map[case[0]]}
            if not allowed:
                return None
            candidates = allowed if candidates is None else candidates & allowed
            if not candidates:
                return None
        right_map[light] = _sorted_actions(candidates)[0]
    # 每个灯况的成对动作都必须落在允许集内。
    for case in cases:
        pair = (left_map[case[0]], right_map[case[1]])
        if pair not in case[2]:
            return None
    return {
        'mode': 'silent',
        'sender': None,
        'silent_plan': {
            'left': {str(light): action for light, action in left_map.items()},
            'right': {str(light): action for light, action in right_map.items()},
        },
    }


def _sender_options(cases, sender_index, light):
    pairs = [pair for case in cases if case[0] == light for pair in case[2]]
    sender_actions = _sorted_actions({pair[sender_index] for pair in pairs})
    return [(action, bit) for action in sender_actions for bit in BIT_VALUES]


def _solve_as_sender(cases, sender):
    sender_index = 0 if sender == 'left' else 1
    receiver_index = 1 - sender_index
    sender_lights = _lights(cases, sender_index)
    receiver_lights = _lights(cases, receiver_index)
    domains = {light: _sender_options(cases, sender_index, light) for light in sender_lights}

    def walk(index, chosen):
        if index == len(sender_lights):
            return _solve_as_receiver(cases, sender, receiver_index, chosen)
        light = sender_lights[index]
        for action, bit in domains[light]:
            chosen[light] = (action, bit)
            result = walk(index + 1, chosen)
            if result is not None:
                return result
        chosen.pop(light, None)
        return None

    def _solve_as_receiver(cases, sender, receiver_index, sender_map):
        if len(receiver_lights) > 4:  # pragma: no cover - 结构校验已限制
            return None
        receiver_map = {}
        for case in cases:
            sender_light = case[sender_index]
            sender_action, bit = sender_map[sender_light]
            allowed = {pair[receiver_index] for pair in case[2] if pair[sender_index] == sender_action}
            if not allowed:
                return None
            key = (case[receiver_index], bit)
            current = receiver_map.get(key)
            if current is None:
                receiver_map[key] = set(allowed)
            else:
                receiver_map[key] = current & allowed
            if not receiver_map[key]:
                return None
        resolved = {}
        for (light, bit), actions in receiver_map.items():
            resolved.setdefault(light, {})[str(bit)] = _sorted_actions(actions)[0]
        # 成对动作必须落在允许集内。
        for case in cases:
            sender_action, bit = sender_map[case[sender_index]]
            receiver_action = resolved[case[receiver_index]][str(bit)]
            pair = [None, None]
            pair[sender_index] = sender_action
            pair[receiver_index] = receiver_action
            if tuple(pair) not in case[2]:
                return None
        return {
            'mode': 'signal',
            'sender': sender,
            'sender_plan': {str(light): {'action': action, 'bit': bit}
                            for light, (action, bit) in sender_map.items()},
            'receiver_plan': {str(light): by_bit for light, by_bit in resolved.items()},
        }

    return walk(0, {})


def solve_round(light_cases):
    """返回该轮冻结方案；无解时返回 ``None``。"""
    cases = _cases(light_cases)
    silent = _solve_silent(cases)
    if silent is not None:
        return silent
    for sender in SENDER_ORDER:
        plan = _solve_as_sender(cases, sender)
        if plan is not None:
            return plan
    return None
