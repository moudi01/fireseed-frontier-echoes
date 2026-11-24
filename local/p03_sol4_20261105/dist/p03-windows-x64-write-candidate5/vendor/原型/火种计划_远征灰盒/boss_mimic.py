"""Demon's receipt-backed native-active copies, scheduled by normal actions.

No player passive, book, ordinary attack or recursive sample is copied. Geometry
and non-numeric active semantics use the current hero implementation. Native W0
becomes W1 for readable warnings; integer control durations stay native. Damage,
healing, shield and command/debuff magnitudes use 135%. Source panel is frozen at
the real release; boss/source attack and healing panels take the larger value.
Percentage shields on the boss use source hero HP, avoiding body-size scaling.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math

import combat as c
import hero_power_v062 as power
import commander

VERSION = 'DEMON-NATIVE-MIMIC-0.67'
GATE = 'DEMON-MIMIC'
PREFIX = 'MIMIC-'
FACTOR = 1.35
STATS = ('hp', 'physical_attack', 'magic_attack', 'healing_power',
         'physical_defense', 'magic_defense')
NATIVE = {uid: tuple(row['move_id'] for row in power.cards(uid))
          for uid in sorted(power.IDS)}
MAPPING = {mid: {'hero': uid, 'name': row['name'],
                'identity': power.DESCRIPTIONS[mid]}
           for uid in sorted(power.IDS) for row in power.cards(uid)
           for mid in [row['move_id']]}
SUMMARY = ('复制本场我方英雄真正释放的原生主动，最近2种按公开次序选择当前合法的一种；'
           '冻结源面板与魔王对应攻击/治疗面板取高，正效135%；'
           '给魔王本人的百分比盾以源英雄最大生命为基准，护卫以自身最大生命为基准。'
           '不复制普攻、被动、技能书或复制动作。'
           '至少1拍预警、占正常行动、共享C4。遁影亲手击杀可次拍续链，不再次采样。')
ENTRY = dict(move_id=GATE, name='映技', kind='boss_mimic', windup=1,
             cooldown=4, cast_limit=None, first_eligible_tick=2, range=99,
             max_targets=1, medium='tool', damage_type='physical',
             coefficient=0, interruptible=True, mechanic_summary=SUMMARY)


def _check(ok, text):
    if not ok:
        raise ValueError(text)


def _digest(row):
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def install(cat):
    """Append one gateway to all demon phases; retain native A/B/C unchanged."""
    def patch(unit):
        if not any(row['move_id'] == GATE for row in unit.setdefault('moves', [])):
            unit['moves'].append(deepcopy(ENTRY))
        for phase in unit.get('phases', []):
            if GATE not in phase['move_ids']:
                phase['move_ids'].append(GATE)
    patch(cat.enemy_templates['DEMON'])
    for encounter in cat.encounters.values():
        for unit in encounter['units']:
            if unit['enemy_id'] == 'DEMON':
                patch(unit)


def initialize(actor):
    if actor.get('kind') == 'DEMON' and not actor.get('boss_part'):
        actor['boss_mimic'] = dict(version=VERSION, samples=[], history=[], cursor=0)
        actor['mimic_chain'] = None
        actor['mimic_setup'] = False


def is_copy(action):
    return bool(isinstance(action, dict) and action.get('boss_mimic')
                and action.get('move_id', '').startswith(PREFIX))


def prioritize(b, a, cards, tick):
    """Caller places any conditional boss attack ahead of this resulting list."""
    state = a.get('boss_mimic')
    ready = state and state['samples'] and tick >= a.get('move_ready', {}).get(GATE, 0)
    return sorted(cards, key=lambda row: 0 if ready and row['move_id'] == GATE else 1)


def _bosses(b):
    return [a for a in b['actors'] if a.get('kind') == 'DEMON' and not a.get('boss_part')]


def _release_proven(b, sample):
    return any(e.get('type') == 'release' and e.get('actor') == sample['actor']
               and e.get('move') == sample['move_id']
               and e.get('action_id') == sample['action_id']
               and e.get('tick') == sample['tick'] for e in b['events'])


def observe(b, actor, action, tick, log):
    """Call immediately AFTER the executor's genuine native release log."""
    uid = actor.get('kind'); mid = action.get('move_id')
    if (actor.get('side') != 'player' or uid not in NATIVE or mid not in NATIVE[uid]
            or action.get('derived') or action.get('extra_chain') or is_copy(action)):
        return False
    sample = dict(actor=actor['id'], hero=uid, move_id=mid,
                  action_id=action['id'], tick=tick,
                  source_stats={k: actor['stats'][k] for k in STATS})
    _check(_release_proven(b, sample), '复制样本缺少真实原生主动释放记录。')
    sample['sha256'] = _digest(sample)
    for boss in _bosses(b):
        if 'boss_mimic' not in boss:
            initialize(boss)
        state = boss['boss_mimic']
        if any(row['action_id'] == sample['action_id'] for row in state['history']):
            continue
        previous_next = (state['samples'][state['cursor']]['move_id']
                         if state['samples'] else None)
        state['history'].append(deepcopy(sample))
        state['samples'] = [row for row in state['samples'] if row['move_id'] != mid]
        state['samples'].append(deepcopy(sample))
        state['samples'] = state['samples'][-2:]
        state['cursor'] = next((i for i,row in enumerate(state['samples'])
                                if row['move_id'] == previous_next), 0)
        log('mimic_observed', actor=boss['id'], source_actor=actor['id'],
            source_hero=uid, source_move=mid, source_action_id=action['id'],
            source_stats=sample['source_stats'], order=[r['move_id'] for r in state['samples']])
    return bool(_bosses(b))


def _native_card(sample):
    return next(row for row in power.cards(sample['hero']) if row['move_id'] == sample['move_id'])


def _card(sample):
    row = _native_card(sample)
    row.update(move_id=PREFIX+sample['move_id'], boss_mimic=True,
               mimic_original=sample['move_id'], mimic_source=deepcopy(sample),
               name='映·'+row['name'], windup=max(1, row['windup']), cooldown=4,
               cast_limit=None, first_eligible_tick=2, mechanic_summary=SUMMARY,
               medium=row.get('medium', 'tool'),
               damage_type=row.get('damage_type', 'physical'),
               coefficient=row.get('coefficient', 0))
    return row


@contextmanager
def _native(action):
    mid = action['move_id']
    action['move_id'] = action['mimic_original']
    try:
        yield action
    finally:
        action['move_id'] = mid


def _friends(a, alive, rng, cat, board):
    return [v for v in alive if power.living(v) and v['side'] == a['side']
            and c.distance(a['pos'], v['pos']) <= rng
            and c.visible(cat, board, a['pos'], v['pos'])]


def choose(b, a, foes, alive, prior, cat, board, occupied, blocked, tick):
    """Return (dynamic_card, target, locked_cells, extra), or None.

    Check at most two samples in public order. An unavailable support action is
    never cast or consumed; a currently legal second sample may be selected.
    """
    if a.get('kind') != 'DEMON' or a.get('boss_part') or a.get('hp', 0) <= 0:
        return None
    if 'boss_mimic' not in a:
        initialize(a)
    state = a['boss_mimic']
    if not state['samples'] or tick < a.get('move_ready', {}).get(GATE, 0):
        return None
    for offset in range(len(state['samples'])):
        sample = state['samples'][(state['cursor']+offset) % len(state['samples'])]
        chosen = _choose_sample(b,a,sample,foes,alive,prior,cat,board,occupied,blocked,tick)
        if chosen:
            return chosen
    return None


def _choose_sample(b,a,sample,foes,alive,prior,cat,board,occupied,blocked,tick):
    card = _card(sample); native = _native_card(sample); mid = sample['move_id']
    if mid in ('CMD-A', 'CMD-B'):
        guards = [v for v in _friends(a, alive, 3, cat, board) if v is not a]
        legal = [v for v in foes if power._legal(a, v, cat, board, tick, 4)]
        if not guards or (mid == 'CMD-A' and not legal):
            return None
        chosen = ((min(legal, key=lambda v: (c.distance(a['pos'], v['pos']), v['id'])), [], {})
                  if mid == 'CMD-A' else (a, [], {}))
    else:
        # Only active H12 setup affects its future copied cannon; no passive x1.5.
        old = a.get('hero_setup', False)
        a['hero_setup'] = a.get('mimic_setup', False)
        try:
            chosen = power.choose(b, a, native, foes, alive, prior, cat, board, occupied, blocked, tick)
        finally:
            a['hero_setup'] = old
        if not chosen:
            return None
    target, cells, extra = chosen
    card.update(deepcopy(extra))
    card['windup'] = max(1, card.pop('hero_windup', card['windup']))
    if card.get('kind') == 'damage':
        card['coefficient'] *= FACTOR
    # Dynamic fields already belong to card. Passing the native extra again to
    # begin(**extra) would overwrite the scaled cannon coefficient.
    return card, target, cells, {}


def started(b, a, action, tick, log):
    if not is_copy(action):
        return
    _check(action['mimic_source'] in a['boss_mimic']['history'], '复制起手缺少本场真实样本。')
    a['move_ready'][GATE] = tick+4
    state = a['boss_mimic']
    if state['samples']:
        selected = next((i for i,row in enumerate(state['samples'])
                         if row == action['mimic_source']), state['cursor'])
        state['cursor'] = (selected+1) % len(state['samples'])
    if action['mimic_original'] == 'H11-A':
        a['mimic_shadow'] = True
    if action['mimic_original'] in ('H12-A', 'H12-B'):
        action['hero_anchor'] = a['pos'][:]
    log('mimic_start', actor=a['id'], action_id=action['id'],
        source_hero=action['mimic_source']['hero'], source_move=action['mimic_original'],
        source_action_id=action['mimic_source']['action_id'],
        release_tick=action['due'], factor=FACTOR, cells=deepcopy(action['cells']))


def attack(a, action, default):
    if not is_copy(action) or action.get('mimic_response'):
        return default
    return max(default, action['mimic_source']['source_stats'][action['damage_type']+'_attack'])


def _heal_power(a, action, tick):
    return max(c.stat(a, 'healing_power', tick), action['mimic_source']['source_stats']['healing_power'])


def _cost(v):
    return v.get('cost', 4 if v.get('kind') == 'DEMON' else 1)


def _shield(b, a, v, amount, action, tick, log):
    return power.add_shield(b, a, v, math.floor(amount*FACTOR), action['move_id'],
                            action, tick, log, active=False, duration=3)


def _shield_hp(a, v, action):
    return (action['mimic_source']['source_stats']['hp'] if v is a
            else v['stats']['hp'])


def movement(actions, b, alive, cat, board, tick, log):
    result = []
    for a, action in actions:
        if not is_copy(action) or action.get('mimic_response'):
            continue
        with _native(action):
            result.extend(power.movement([(a, action)], b, alive, cat, board, tick, log))
    return result


def release(b, a, action, alive, cat, board, tick, log):
    if not is_copy(action) or action.get('mimic_response'):
        return
    mid = action['mimic_original']
    if mid in ('H01-A', 'H08-B'):
        for v in _friends(a, alive, action['range'], cat, board):
            _shield(b, a, v, 7*_cost(v) if mid == 'H01-A' else _shield_hp(a,v,action)*.4, action, tick, log)
    elif mid == 'H05-B':
        panel = action['mimic_source']['source_stats']['hp']
        _shield(b, a, a, panel*.5, action, tick, log)
        a['hero_stance'] = dict(starts=tick, expires=tick+2, source=a['id'], amount=.3*FACTOR)
    elif mid == 'H08-A':
        v = next((v for v in _friends(a, alive, 4, cat, board) if v['id'] == action['target']), None)
        if v:
            _shield(b, a, v, _shield_hp(a,v,action)*.5, action, tick, log)
    elif mid in ('CMD-A', 'CMD-B'):
        members = [v for v in _friends(a, alive, 3, cat, board) if v is not a]
        if mid == 'CMD-A':
            v = next((v for v in alive if v['id'] == action['target'] and v['side'] != a['side']), None)
            if v and power._legal(a, v, cat, board, tick, 4):
                a['mimic_command'] = dict(target=v['id'], members=[v['id'] for v in members],
                    starts=tick, expires=tick+3, cast_id=action['id'])
                log('mimic_command_mark', actor=a['id'], **a['mimic_command'])
        else:
            for v in members:
                v['mimic_token'] = dict(owner=a['id'], source=deepcopy(action['mimic_source']),
                    cast_id=action['id'], valid_from=tick+1, expires=tick+2)
            log('mimic_command_grant', actor=a['id'], members=[v['id'] for v in members], action_id=action['id'])
    else:
        oldpos = a['pos'][:]
        with _native(action):
            power.release(b, a, action, alive, cat, board, tick, log)
        if mid == 'H09-B':
            action['coefficient'] *= FACTOR
        if mid == 'H11-A':
            a['mimic_shadow'] = False
        if mid == 'H12-A' and not action.get('hero_target_failed'):
            a['mimic_setup'] = True
            a['hero_setup'] = False
        if oldpos != a['pos']:
            import bosses
            bosses.moved(b, a)
            moved(a, 'mimic_flash', tick)


def targets(a, action, alive, cat, board, tick):
    if not is_copy(action):
        return []
    if action.get('mimic_response'):
        return [v for v in alive if v['id'] == action['target']
                and power._legal(a, v, cat, board, tick, a['range'])][:1]
    with _native(action):
        return power.targets(a, action, alive, cat, board, tick)


def heals(b, a, action, alive, cat, board, tick):
    if not is_copy(action):
        return []
    h = _heal_power(a, action, tick); mid = action['mimic_original']
    if mid == 'H03-A':
        return [(v, math.floor((16+1.8*h)*FACTOR))
                for v in _friends(a, alive, 3, cat, board) if v['id'] == action['target']]
    if mid == 'H03-B':
        center = action.get('hero_center')
        if center is None or c.distance(a['pos'], center) > 3 or not c.visible(cat, board, a['pos'], center):
            return []
        return [(v, math.floor((10+h)*_cost(v)/4*FACTOR)) for v in _friends(a, alive, 4, cat, board)
                if c.distance(center, v['pos']) <= 1 and v['id'] != action.get('hero_revive_target')]
    return []


def hit(b, a, v, action, amount, tick, log, spend_shields=None):
    if not is_copy(action) or action.get('mimic_response') or amount <= 0:
        return
    mid = action['mimic_original']
    # This function's native clauses include A's control/reveal, but kind DEMON
    # never grants H06/H09 ordinary-hit passives or H11 backstab.
    with _native(action):
        power.hit(b, a, v, action, amount, tick, log, spend_shields)
    if mid == 'H09-A':
        row = power._debuff(v, 'hero_contract', .4*FACTOR, 3, a, action, tick)
        log('mimic_contract', actor=a['id'], target=v['id'], **row)


def defense(a, v, action, tick, log):
    if is_copy(action) and action['mimic_original'] == 'H05-A':
        return max(0, c.stat(v, 'physical_defense', tick)+v.get('boss_rule', {}).get('physical_defense_offset', 0))*.5
    return 0


def projectile_deflected(b, a, v, action, tick, log):
    if is_copy(action):
        with _native(action):
            power.projectile_deflected(b, a, v, action, tick, log)


def on_kill(b, a, v, action, tick, log):
    if (is_copy(action) and not action.get('mimic_response')
            and action['mimic_original'] == 'H11-A' and a['hp'] > 0
            and not action.get('mimic_kill_awarded')):
        action['mimic_kill_awarded'] = True
        a['mimic_chain'] = dict(due=tick+1, source=deepcopy(action['mimic_source']))
        a['mimic_shadow'] = True
        log('mimic_chain_queued', actor=a['id'], target=v['id'], action_id=action['id'], due=tick+1)


def chain_action(b, a, alive, cat, board, tick, log):
    row = a.get('mimic_chain')
    if not row or row['due'] > tick:
        return None
    a['mimic_chain'] = None
    if (row['due'] != tick or a['hp'] <= 0 or power._movement_disabled(a, tick)
            or a.get('skill_mode') == 'off'):
        a['mimic_shadow'] = False
        return None
    action = _card(row['source'])
    action.update(extra_chain=True, mimic_chain=True, windup=0, due=tick,
                  target=a['id'], cells=[], origin=a['pos'][:], facing=a['facing'])
    action['coefficient'] *= FACTOR
    return action


def targetable(observer, target, tick):
    return observer['side'] == target['side'] or not target.get('mimic_shadow', False)


def moved(a, reason=None, tick=None):
    if not a.get('mimic_setup'):
        return
    a['mimic_setup'] = False
    pending = a.get('pending')
    if pending and is_copy(pending) and pending['mimic_original'] in ('H12-A', 'H12-B') and (tick is None or pending['due'] > tick):
        a['pending'] = None


def damage_bonus(b, a, v, action, tick):
    if action.get('derived'):
        return 0
    for owner in _bosses(b):
        row = owner.get('mimic_command')
        if (owner['hp'] > 0 and row and row['starts'] <= tick <= row['expires']
                and a['id'] in row['members'] and v['id'] == row['target']):
            return .5*FACTOR
    return 0


def extra_actions(b, alive, actions, moves, tick, cat, board, action_id, log):
    busy = {a['id'] for a, _, _ in moves}|{a['id'] for a, act in actions if act['move_id'] != 'BASIC'}
    for a in alive:
        row = a.get('mimic_token')
        if not row:
            continue
        owner = next((v for v in alive if v['id'] == row['owner']), None)
        if not owner or row['expires'] < tick:
            a['mimic_token'] = None
            continue
        if tick < row['valid_from'] or a['id'] in busy or a.get('pending') or power.active(a.get('hero_stun'), tick):
            continue
        foes = [v for v in alive if commander.attackable(a, v, cat, board, tick)]
        if not foes:
            continue
        v = min(foes, key=lambda v: (c.distance(a['pos'], v['pos']), v['id']))
        a['mimic_token'] = None
        action = dict(id=action_id(a), move_id=PREFIX+'CMD-EXTRA', kind='damage',
            boss_mimic=True, mimic_response=True, mimic_original='CMD-B',
            mimic_source=deepcopy(row['source']), mimic_cast_id=row['cast_id'], derived=True,
            target=v['id'], cells=[], coefficient=1.5*FACTOR, damage_type=a['attack_type'],
            range=a['range'], medium=a['medium'], max_targets=1, origin=a['pos'][:])
        actions.append((a, action))
        log('mimic_command_response', actor=a['id'], target=v['id'], action_id=action['id'], cast_id=row['cast_id'])


def end_tick(actions, b, cat, board, tick, log):
    for a, action in actions:
        if not is_copy(action) or action.get('mimic_response'):
            continue
        mid = action['mimic_original']
        if mid not in ('H03-B', 'H11-B'):
            continue
        oldpos = a['pos'][:]
        def active_log(kind, **details):
            if (kind == 'hero_shield' and details.get('move') == 'H03-P') or kind == 'hero_revive':
                return
            log(kind, **details)
        with _native(action):
            power.end_tick([(a, action)], b, cat, board, tick, active_log)
        if mid == 'H03-B' and action.get('hero_revive_target'):
            v = next((v for v in b['actors'] if v['id'] == action['hero_revive_target']), None)
            if v and v.get('active_from') == tick+1 and v['hp'] > 0:
                v['hp'] = max(1, min(v['stats']['hp'], math.floor(v['stats']['hp']*.35*FACTOR)))
                v['timed_shields'][:] = [p for p in v['timed_shields'] if p.get('effect') != 'H03-P']
                log('hero_revive', actor=a['id'], target=v['id'], action_id=action['id'],
                    hp=v['hp'], position=v['pos'][:], active_from=tick+1, boss_mimic=True)
        if oldpos != a['pos']:
            import bosses
            bosses.moved(b, a)
            moved(a, 'mimic_flash', tick)
    for a in _bosses(b):
        if a['hp'] <= 0:
            a['mimic_chain'] = None
            a['mimic_shadow'] = False
            a['mimic_setup'] = False
        row = a.get('mimic_chain')
        pending = a.get('pending')
        if not row and not (pending and is_copy(pending) and pending['mimic_original'] == 'H11-A'):
            a['mimic_shadow'] = False


def _validate_pending(b, a, action, history):
    _check(is_copy(action) and not action.get('mimic_response')
           and not action.get('extra_chain'), '待释放复制动作标记或动作类别无效。')
    sample = action.get('mimic_source')
    _check(sample in history, '复制动作脱离真实释放来源。')
    expected = _card(sample)
    if sample['move_id'] == 'H12-B':
        setup = action.get('hero_entrenched')
        _check(type(setup) is bool, '复制重炮缺少真实架阵快照。')
        expected.update(range=5 if setup else 4, radius=2 if setup else 1,
                        windup=2 if setup else 1, coefficient=2.5 if setup else 1.6)
    if expected['kind'] == 'damage':
        expected['coefficient'] *= FACTOR
    fields = ('move_id','mimic_original','kind','windup','cooldown','cast_limit',
              'range','medium','damage_type','coefficient','max_targets','area',
              'radius','shape','penetration','interruptible','delayable_cast',
              'global_target','duration_ticks','heal_base','healing_power_coefficient')
    _check(all(action.get(key) == expected.get(key) for key in fields),
           '复制待释放动作与源原生技能或135%动态规格不符。')
    start = next((e for e in b['events'] if e.get('type') == 'mimic_start'
                  and e.get('actor') == a['id'] and e.get('action_id') == action['id']), None)
    _check(start and start.get('source_hero') == sample['hero']
           and start.get('source_move') == sample['move_id']
           and start.get('source_action_id') == sample['action_id']
           and start.get('cells') == action.get('cells'),
           '复制待释放动作脱离本次已公开的来源或锁区。')
    # A true counter/delay may extend due after the public start. Do not mistake
    # that supported interaction for a changed native windup/specification.
    _check(type(action.get('due')) is int and action['due'] >= start['release_tick'],
           '复制释放时刻早于已公开的预警。')


def validate(b):
    if not b:
        return
    actors = {a['id']: a for a in b['actors']}
    for a in _bosses(b):
        state = a.get('boss_mimic')
        _check(isinstance(state,dict) and {'version','samples','history','cursor'} <= set(state),
               '魔王缺少本版复制状态。')
        _check(state.get('version') == VERSION and len(state['samples']) <= 2,
               '魔王复制状态版本或样本上限损坏。')
        _check(len({r['move_id'] for r in state['samples']}) == len(state['samples']), '魔王复制样本重复。')
        _check(type(state['cursor']) is int and 0 <= state['cursor'] < max(1, len(state['samples'])), '魔王复制顺序损坏。')
        _check(len({r['action_id'] for r in state['history']}) == len(state['history']), '魔王重复采样同一释放。')
        for row in state['history']:
            source = actors.get(row['actor'])
            _check(source and source['side'] == 'player' and source['kind'] == row['hero']
                   and row['hero'] in NATIVE and row['move_id'] in NATIVE[row['hero']]
                   and 0 <= row['tick'] <= b['tick'] and _release_proven(b, row), '魔王复制来源不是本场真实英雄原生主动。')
            _check(row['source_stats'] == {k: source['stats'][k] for k in STATS}
                   and row['sha256'] == _digest({k: v for k, v in row.items() if k != 'sha256'}), '魔王复制源面板或来源证明被改写。')
        _check(all(row in state['history'] for row in state['samples']), '魔王当前样本缺少来源历史。')
        expected = []
        for row in state['history']:
            expected = [old for old in expected if old['move_id'] != row['move_id']]
            expected = (expected+[row])[-2:]
        _check(state['samples'] == expected, '魔王当前样本不是最近两种真实主动。')
        pending = a.get('pending')
        if pending and (pending.get('boss_mimic') or pending.get('move_id','').startswith(PREFIX)):
            _validate_pending(b,a,pending,state['history'])
        chain = a.get('mimic_chain')
        if chain:
            _check(chain.get('source') in state['history']
                   and chain['source']['move_id'] == 'H11-A'
                   and type(chain.get('due')) is int and chain['due'] == b['tick']+1,
                   '复制续链脱离真实遁影来源或次拍时刻。')


def describe(b):
    lines = []
    for a in _bosses(b):
        state = a.get('boss_mimic')
        if not state:
            continue
        order = state['samples'][state['cursor']:] + state['samples'][:state['cursor']]
        lines.append('映技顺序（取当前合法者）：'+(' → '.join(r['hero']+'/'+MAPPING[r['move_id']]['name']+'（源动作'+r['action_id']+'）' for r in order) or '尚未观察到真实原生主动'))
        if a.get('pending') and is_copy(a['pending']):
            act = a['pending']
            lines.append(f"复制预警 {act['name']}：第{act['due']}拍，锁格{act['cells']}，源{act['mimic_source']['action_id']}；面板取高/正效135%。")
        if a.get('mimic_chain'):
            lines.append('映·遁影：亲手击杀续链，第'+str(a['mimic_chain']['due'])+'拍再发动；不重新采样。')
    return '\n'.join(lines)

