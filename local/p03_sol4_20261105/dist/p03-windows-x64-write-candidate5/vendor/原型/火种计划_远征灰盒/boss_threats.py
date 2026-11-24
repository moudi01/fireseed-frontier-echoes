"""Conditional boss threats, public telegraphs and post-damage execution.

No extra attack is scheduled here. D cards use the ordinary action executor;
only the administrator's announced law is a separate, post-settlement rule.
"""
from copy import deepcopy

VERSION = 'BOSS-THREATS-0.92'
BOSSES = {'DEMON', 'ADMIN'}
MOVES = {'DEMON-D', 'ADMIN-D'}
LAW_FIRST = 6
LAW_INTERVAL = 12
LAW_DELAY = 8
LAW_BREAK_PERCENT = 15
HERO_RELEASES = 4


def _card(kind):
    return dict(move_id=kind+'-D', name=('见证崩流' if kind == 'DEMON' else '法令反噬'),
                kind='damage', damage_type='magic', coefficient=2.0, range=3,
                radius=3, shape='boss_threat_circle', windup=3, cooldown=8,
                cast_limit=None, max_targets=6, first_eligible_tick=1,
                medium='spell', interruptible=True, delayable_cast=True,
                area=True, locks_cells=True, pressure_radius=3, threat_evasion_horizon=2,
                target_rule='locked_boss_origin_then_distance_then_stable_id',
                mechanic_summary=(
                    '实际观察4次英雄原生主动释放（不计普攻、书、伴兽、派生连杀）后就绪；'
                    if kind == 'DEMON' else '本次点名被15%最大HP真实伤害实际破除后就绪；')
                    + 'W3/C8，起手时首领实际位置半径3锁区，最多6人各2.0魔伤；'
                    + '可打断/延后，移出预警可躲避；被打断保留起手后8拍冷却，'
                    + '成功释放后冷却8拍，冷却中最多存1份就绪。',
                condition=('four_witnessed_original_hero_releases' if kind == 'DEMON'
                           else 'one_actually_broken_law'))


def install(cat):
    """Runtime overlay only; ordinary boss rotation sees a conditional D card."""
    def patch(unit, kind):
        if kind not in BOSSES:
            return
        mid = kind+'-D'
        cards = unit.setdefault('moves', [])
        cards[:] = [row for row in cards if row['move_id'] != mid] + [_card(kind)]
        for phase in unit.get('phases', []):
            if mid not in phase['move_ids']:
                phase['move_ids'].append(mid)
        if kind == 'ADMIN':
            note = ('【独立法令·小怪阶段】小怪在场时管理员不点名并获得霸体；清空小怪后才点名。'
                    '点名、破令或被打断后召唤小怪（每次一波；已有一波时不叠加）。'
                    '点名仍按本战累计实际HP伤害最高人类（同伤按ID），原目标8拍后被处决；'
                    '护盾/治疗不抵挡且不轮换目标；点名后对管理员累计造成其最大HP15%的真实HP伤害破令，'
                    '或击倒管理员解除；原目标已倒则取消。')
            if note not in unit.get('briefing', ''):
                unit['briefing'] = (unit.get('briefing', '')+'\n'+note).strip()
    for kind, unit in cat.enemy_templates.items():
        patch(unit, kind)
    for encounter in cat.encounters.values():
        for unit in encounter.get('units', []):
            patch(unit, unit['enemy_id'])
    cat.rules['boss_threats'] = dict(version=VERSION, law_first_tick=LAW_FIRST,
        law_interval=LAW_INTERVAL, law_delay=LAW_DELAY,
        law_break_hp_percent=LAW_BREAK_PERCENT, demon_hero_releases=HERO_RELEASES,
        aoe=dict(windup=3, cooldown=8, radius=3, max_targets=6,
                 magic_coefficient=2.0, conditional=True, tracks=False))
    # The root executor adds the choose/targets branches before legacy bosses.
    import combat
    import bosses
    combat.SUPPORTED_MOVES.update(MOVES)
    bosses.MOVES.update(MOVES)


def _bosses(b):
    return [a for a in b['actors'] if a['side'] == 'enemy'
            and a['kind'] in BOSSES and not a.get('boss_part')]


def _human(a):
    return (a.get('side') == 'player' and not a.get('mechanism')
            and not a.get('boss_part') and a.get('kind') != 'PET-H04')


def _admin(b):
    return next((a for a in _bosses(b) if a['kind'] == 'ADMIN'), None)


def _minion(a):
    return (a.get('side') == 'enemy' and a.get('kind') not in BOSSES
            and not a.get('mechanism') and not a.get('boss_part'))


def _minions(b):
    return [a for a in b['actors'] if _minion(a) and a.get('hp', 0) > 0]


def control_immune(a):
    """The administrator is unstoppable while its minion wave is alive."""
    return a.get('kind') == 'ADMIN' and bool(a.get('super_armor'))


def _set_super_armor(b, tick, log):
    admin = _admin(b)
    if admin is None:
        return
    active = bool(_minions(b))
    if admin.get('super_armor') != active:
        admin['super_armor'] = active
        log('admin_super_armor', actor=admin['id'], active=active,
            minions=len(_minions(b)), tick=tick)


def initialize(b, entry_tick=None, catalog=None):
    """Call at each new battle boundary, including copied ADMIN battle entry."""
    if not _bosses(b):
        b.pop('boss_threats', None)
        return
    old = b.get('boss_threats')
    if old and old.get('battle_id') == b['battle_id']:
        return
    entry_tick = b['tick'] if entry_tick is None else entry_tick
    minion_templates = {}
    for a in b['actors']:
        if not _minion(a):
            continue
        minion_templates.setdefault(a['kind'], dict(
            id=a['id'], kind=a['kind'], name=a.get('name', a['kind']),
            stats=deepcopy(a['stats']), moves=deepcopy(a.get('moves', [])),
            range=a['range'], interval=a['interval'],
            attack_type=a['attack_type'], medium=a.get('medium'), pos=deepcopy(a['pos'])))
    b['boss_threats'] = dict(version=VERSION, battle_id=b['battle_id'],
        entry_tick=entry_tick, damage_totals={}, law_damage={a['id']:{} for a in _bosses(b) if a['kind'] == 'ADMIN'},
        seen_hits=[], seen_releases=[],
        minion_templates=minion_templates, summon_wave=0,
        walkable=[[cell['q'], cell['r']] for cell in b.get('board_cells', [])
                  if catalog is not None and catalog.terrain[cell['terrain_id']]['walkable']],
        states={a['id']: dict(kind=a['kind'], energy=0, ready=False,
            next_law=entry_tick+LAW_FIRST, law_sequence=0, law=None,
            laws=[], broken_laws=0, aoe_releases=0, aoe_action_ids=[])
            for a in _bosses(b)})
    admin = _admin(b)
    if admin is not None:
        admin['super_armor'] = bool(_minions(b))


def _ensure(b, tick=None):
    if not _bosses(b):
        return None
    old = b.get('boss_threats')
    if not old or old.get('battle_id') != b['battle_id']:
        initialize(b, entry_tick=max(0, tick-1) if tick is not None else b['tick'])
    return b['boss_threats']


def _free_position(b, admin, template, occupied):
    import combat as c
    walkable = [tuple(p) for p in ((b.get('boss_threats') or {}).get('walkable') or [])]
    candidates = [tuple(template['pos'])]
    candidates += sorted(walkable, key=lambda p: (c.distance(admin['pos'], p), p))
    for radius in (1, 2):
        for dq, dr in c.DIRS:
            point = (admin['pos'][0] + dq * radius, admin['pos'][1] + dr * radius)
            if point not in candidates:
                candidates.append(point)
    return list(next((p for p in candidates if p not in occupied), None)) if any(
        p not in occupied for p in candidates) else None


def _summon_wave(b, boss, reason, tick, log):
    """Summon one EN16/EN18-style wave; never stack a second living wave."""
    state = _ensure(b, tick)
    if state is None or _minions(b):
        return []
    templates = state.get('minion_templates') or {}
    if not templates:
        log('admin_minions_summon_failed', actor=boss['id'], reason=reason, cause='NO_TEMPLATE')
        return []
    wave = state.get('summon_wave', 0) + 1
    state['summon_wave'] = wave
    occupied = {tuple(a['pos']) for a in b['actors'] if a.get('hp', 0) > 0}
    added = []
    import combat as c
    for kind, template in sorted(templates.items()):
        position = _free_position(b, boss, template, occupied)
        if position is None:
            log('admin_minions_summon_failed', actor=boss['id'], reason=reason,
                minion=kind, cause='NO_FREE_CELL')
            continue
        instance_id = f"ADMIN-SUMMON-{wave}-{kind}"
        unit = {
            'instance_id': instance_id, 'enemy_id': kind,
            'name': template.get('name', kind), 'stats': deepcopy(template['stats']),
            'position': position, 'facing': 'D4', 'moves': deepcopy(template.get('moves', [])),
            'basic_attack': dict(range=template['range'], attack_interval=template['interval'],
                                 damage_type=template['attack_type'], medium=template.get('medium', 'near')),
        }
        try:
            actor = c.enemy_actor(unit)
            c.initialize_actor(actor)
        except Exception as exc:
            log('admin_minions_summon_failed', actor=boss['id'], reason=reason,
                minion=kind, cause=type(exc).__name__, error=str(exc))
            continue
        actor.update(active_from=tick + 1, next_attack=tick + 1, summoned_by=boss['id'])
        b['actors'].append(actor)
        occupied.add(tuple(position))
        added.append(actor)
        log('admin_minion_summoned', actor=boss['id'], reason=reason, minion=actor['id'],
            minion_kind=kind, position=list(position), wave=wave, active_from=tick + 1)
    if added:
        log('admin_minions_summoned', actor=boss['id'], reason=reason, wave=wave,
            minions=[a['id'] for a in added])
    _set_super_armor(b, tick, log)
    return added


def admin_interrupted(b, actor, tick, log):
    """An actual interrupt while exposed calls the next minion wave."""
    if actor.get('kind') != 'ADMIN' or actor.get('hp', 0) <= 0:
        return False
    if _minions(b):
        return False
    return bool(_summon_wave(b, actor, 'ADMIN_INTERRUPTED', tick, log))


def start_tick(b, tick, log):
    """Before intents: name one original human; never replace a live decree."""
    state = _ensure(b, tick)
    if state is None:
        return
    for boss in _bosses(b):
        row = state['states'][boss['id']]
        if boss['kind'] != 'ADMIN' or boss['hp'] <= 0:
            continue
        _set_super_armor(b, tick, log)
        if _minions(b):
            continue
        if row['law'] is not None:
            continue
        if tick < row['next_law']:
            continue
        humans = [a for a in b['actors'] if _human(a) and a['hp'] > 0]
        if not humans:
            continue
        law_totals = state.get('law_damage', {}).get(boss['id'], {})
        target = min(humans, key=lambda a: (-law_totals.get(a['id'], 0), a['id']))
        row['next_law'] = tick + LAW_INTERVAL
        row['law_sequence'] += 1
        law = dict(id=f"{b['battle_id']}:{boss['id']}:LAW-{row['law_sequence']}",
            boss=boss['id'], target=target['id'], started=tick, due=tick+LAW_DELAY,
            threshold=(boss['stats']['hp']*LAW_BREAK_PERCENT+99)//100,
            progress=0, status='ACTIVE', ended_tick=None,
            target_damage_at_naming=law_totals.get(target['id'], 0))
        row['laws'].append(law);row['law'] = law['id']
        log('boss_law_named', actor=boss['id'], target=target['id'],
            law_id=law['id'], due=law['due'], required_hp_damage=law['threshold'],
            progress=0, target_damage=law['target_damage_at_naming'],
            selection='highest_actual_human_hp_damage_this_battle_then_id',
            response='After naming, deal15percent maximum ADMIN HP damage or defeat ADMIN')
        _summon_wave(b, boss, 'LAW_NAMED', tick, log)


def _current(row):
    return next((law for law in row['laws'] if law['id'] == row['law']), None)


def priority_boss(b, actor):
    """An active administrator law makes its owner the player's first target."""
    if actor.get('side') != 'player':return None
    states=(b.get('boss_threats') or {}).get('states') or {}
    for boss in _bosses(b):
        law=_current(states[boss['id']]) if states.get(boss['id']) else None
        if law and law.get('status') == 'ACTIVE':return boss['id']
    return None


def _original_hero(a, action):
    if (a.get('side') != 'player' or a.get('kind') not in {f'H{i:02}' for i in range(1, 13)}
            or action.get('derived') or action.get('extra_chain') or action.get('boss_mimic')):
        return False
    import heroes
    return action.get('move_id') in {card['move_id'] for card in heroes.cards(a['kind'])}


def _released(b, a, action, tick):
    return any(e.get('type') == 'release' and e.get('actor') == a['id']
               and e.get('action_id') == action['id'] and e.get('move') == action['move_id']
               and e.get('tick') == tick for e in reversed(b['events']))


def started(b, a, action, tick, log):
    """After a D action is accepted: reserve cooldown even if later interrupted.

    The ordinary release executor still sets release_tick+C8 on success. Energy
    remains one ready token until that real release; interruption never creates
    an extra token or an immediate same/next-tick retry loop.
    """
    if action.get('move_id') not in MOVES:
        return
    state = _ensure(b, tick)
    if not state or a['id'] not in state['states']:
        return
    mid = action['move_id']
    a.setdefault('move_ready', {})[mid] = max(a.get('move_ready', {}).get(mid, 0), tick+8)
    log('boss_threat_cooldown_reserved', actor=a['id'], action_id=action['id'],
        move=mid, ready_tick=a['move_ready'][mid], energy_reserved=True)


def observe_release(b, a, action, tick, log):
    """After the ordinary release receipt, once per original action ID."""
    state = _ensure(b, tick)
    if state is None or not _released(b, a, action, tick):
        return
    if action['move_id'] in MOVES and a['id'] in state['states']:
        row = state['states'][a['id']]
        if action['id'] in row['aoe_action_ids']:
            return
        row['aoe_action_ids'].append(action['id']);row['aoe_releases'] += 1
        row['energy'] = 0;row['ready'] = False
        log('boss_threat_spent', actor=a['id'], action_id=action['id'],
            move=action['move_id'], energy=0, ready=False)
        return
    if not _original_hero(a, action) or action['id'] in state['seen_releases']:
        return
    state['seen_releases'].append(action['id'])
    for boss in _bosses(b):
        if boss['kind'] != 'DEMON' or boss['hp'] <= 0:
            continue
        row = state['states'][boss['id']]
        if row['ready']:
            continue
        row['energy'] = min(HERO_RELEASES, row['energy']+1)
        row['ready'] = row['energy'] == HERO_RELEASES
        log('boss_threat_charge', actor=boss['id'], source_actor=a['id'],
            source_action_id=action['id'], source_move=action['move_id'],
            energy=row['energy'], required=HERO_RELEASES, ready=row['ready'])


def damage(b, attacker, victim, action, amount, tick, log):
    """Use finite actual_hp_damage after guard/part owner/shields, never raw."""
    state = _ensure(b, tick)
    if state is None or not _human(attacker) or victim.get('side') != 'enemy' or amount <= 0:
        return
    assert type(amount) is int, 'Actual HP damage must be the finite integer ledger value'
    key = (attacker['id'], action['id'], victim['id'])
    if list(key) in state['seen_hits']:
        return
    state['seen_hits'].append(list(key))
    totals = state['damage_totals']
    totals[attacker['id']] = totals.get(attacker['id'], 0)+amount
    law_totals = state.setdefault('law_damage', {})
    boss_row = state['states'].get(victim['id'])
    if boss_row and boss_row['kind'] == 'ADMIN':
        bucket = law_totals.setdefault(victim['id'], {})
        bucket[attacker['id']] = bucket.get(attacker['id'], 0)+amount
    row = boss_row
    law = _current(row) if row else None
    if law is not None and law['status'] == 'ACTIVE' and tick >= law['started']:
        law['progress'] += amount
        log('boss_law_progress', actor=victim['id'], contributor=attacker['id'],
            action_id=action['id'], law_id=law['id'], target=law['target'],
            added=amount, progress=law['progress'], required_hp_damage=law['threshold'])


def prioritize(b, a, cards, tick):
    state = _ensure(b, tick)
    row = state['states'].get(a['id']) if state else None
    if not row or not row['ready'] or tick < a.get('move_ready', {}).get(a['kind']+'-D', 0):
        return cards
    return sorted(cards, key=lambda card: card['move_id'] not in MOVES)


def _cells(cat, board, origin):
    import combat as c
    return sorted(p for p in board if c.distance(origin, p) <= 3
                  and c.visible(cat, board, origin, p))


def choose(b, a, card, foes, cat, board, tick):
    state = _ensure(b, tick)
    row = state['states'].get(a['id']) if state else None
    if (card['move_id'] not in MOVES or not row or not row['ready'] or a['hp'] <= 0
            or tick < a.get('move_ready', {}).get(card['move_id'], 0)):
        return None
    cells = _cells(cat, board, a['pos'])
    victims = [v for v in foes if v['hp'] > 0 and not v.get('mechanism')
               and not v.get('boss_part') and tuple(v['pos']) in cells]
    if not victims:
        return None
    import combat as c
    victim = min(victims, key=lambda v: (c.distance(a['pos'], v['pos']), v['id']))
    return victim, cells, dict(threat_origin=a['pos'][:], threat_started=tick,
        threat_condition=('witnessed_four_hero_releases' if a['kind'] == 'DEMON'
                          else 'law_actually_broken'), threat_energy=row['energy'])


def targets(a, action, alive, cat, board):
    """The original real boss center is locked; each actual hit checks LOS."""
    import combat as c
    origin = action.get('threat_origin', action['origin'])
    locked = {tuple(p) for p in action['cells']}
    victims = [v for v in alive if v['side'] != a['side'] and v['hp'] > 0
               and not v.get('mechanism') and not v.get('boss_part')
               and tuple(v['pos']) in locked and c.distance(origin, v['pos']) <= 3
               and c.visible(cat, board, origin, v['pos'])]
    action['threat_hit_origin'] = list(origin)
    return sorted(victims, key=lambda v: (c.distance(origin, v['pos']), v['id']))[:6]


def end_tick(b, tick, log):
    """After all real HP/healing effects, BEFORE finale/victory settlement."""
    state = _ensure(b, tick)
    if state is None:
        return
    actors = {a['id']: a for a in b['actors']}
    for boss in _bosses(b):
        row = state['states'][boss['id']];law = _current(row)
        if law is None:
            continue
        target = actors[law['target']]
        status = ('BOSS_DOWN' if boss['hp'] <= 0 else
                  'BROKEN' if law['progress'] >= law['threshold'] else
                  'TARGET_DOWN' if target['hp'] <= 0 else
                  'EXECUTED' if tick >= law['due'] else None)
        if status is None:
            continue
        law.update(status=status, ended_tick=tick);row['law'] = None
        if status == 'BROKEN':
            row['broken_laws'] += 1;row['energy'] = 1;row['ready'] = True
            log('boss_law_broken', actor=boss['id'], target=target['id'],
                law_id=law['id'], progress=law['progress'], required_hp_damage=law['threshold'],
                aoe_ready=True)
            if not _minions(b):
                _summon_wave(b, boss, 'LAW_BROKEN', tick, log)
        elif status == 'EXECUTED':
            hp_lost = target['hp'];target['hp'] = 0;target['pending'] = None
            target['hero_chain_due'] = None;target['hero_shadow'] = False;target['downed_tick'] = tick
            log('boss_law_execution', actor=boss['id'], target=target['id'],
                law_id=law['id'], hp_lost=hp_lost, due=law['due'],
                progress=law['progress'], required_hp_damage=law['threshold'],
                ignores_shields=True, grants_kill_rewards=False)
            log('down', actor=target['id'], cause='boss_law_execution', law_id=law['id'])
        else:
            log('boss_law_cancelled', actor=boss['id'], target=target['id'],
                law_id=law['id'], reason=status)
        _set_super_armor(b, tick, log)


def public(b):
    if not b or not b.get('boss_threats'):
        return dict(version=VERSION, bosses=[])
    state = b['boss_threats'];rows = []
    for boss in _bosses(b):
        row = state['states'][boss['id']]
        rows.append(dict(actor=boss['id'], kind=boss['kind'],
            energy=row['energy'], required=HERO_RELEASES if boss['kind'] == 'DEMON' else 1,
            aoe_ready=row['ready'], next_law_tick=row['next_law'] if boss['kind'] == 'ADMIN' else None,
            minions=len(_minions(b)) if boss['kind'] == 'ADMIN' else None,
            super_armor=bool(boss.get('super_armor')) if boss['kind'] == 'ADMIN' else None,
            summon_wave=state.get('summon_wave', 0) if boss['kind'] == 'ADMIN' else None,
            law=deepcopy(_current(row)), broken_laws=row['broken_laws'],
            aoe_releases=row['aoe_releases']))
    return dict(version=VERSION, entry_tick=state['entry_tick'], bosses=rows)


def describe(b):
    out = []
    for row in public(b)['bosses']:
        out.append(f"{row['kind']}条件重击：{row['energy']}/{row['required']}，"
                   + ('已就绪' if row['aoe_ready'] else '未就绪')
                   + '；W3/C8，起手位置半径3锁区、最多6人、2.0魔伤；可移动躲避/延后/打断，打断保留起手C8。')
        law = row['law']
        if row['kind'] == 'ADMIN':
            if row['minions']:
                out.append(f"管理员小怪 {row['minions']}：不点名，霸体；清空后点名。")
            else:
                out.append('管理员无小怪：可点名；点名、破令或被打断会召唤小怪。')
        if law:
            out.append(f"法令点名 {law['target']}：第{law['due']}拍末处决，"
                       f"破令实际HP伤害{law['progress']}/{law['threshold']}；"
                       '护盾和治疗不能抵挡处决；击倒管理员也会解除。')
        elif row['kind'] == 'ADMIN':
            out.append(f"下一次法令第{row['next_law_tick']}拍；点本战实际累计伤害最高人类，同伤按ID。")
    return '\n'.join(out)


def validate(b, cat=None):
    if not b:
        return
    state = b.get('boss_threats')
    if not _bosses(b):
        if state is not None:
            raise ValueError('无对应首领却留有特殊威胁。')
        return
    if not state or state.get('version') != VERSION or state.get('battle_id') != b['battle_id']:
        raise ValueError('首领特殊机制缺少同战快照。')
    def check(ok, text):
        if not ok:
            raise ValueError(text)
    check(type(state['entry_tick']) is int and 0 <= state['entry_tick'] <= b['tick'], '首领入场时钟损坏。')
    check(isinstance(state.get('minion_templates'), dict)
          and type(state.get('summon_wave')) is int and state['summon_wave'] >= 0,
          '管理员小怪模板或召唤波次损坏。')
    admin = _admin(b)
    if admin is not None:
        check(type(admin.get('super_armor')) is bool, '管理员霸体状态损坏。')
    actors = {a['id']: a for a in b['actors']}
    check(set(state['states']) == {a['id'] for a in _bosses(b)}, '首领威胁身份不匹配。')
    check(len(state['seen_releases']) == len(set(state['seen_releases'])), '英雄释放重复计能。')
    hits = [tuple(key) for key in state['seen_hits']]
    check(len(hits) == len(set(hits)), '真实伤害重复计账。')
    check(all(i in actors and _human(actors[i]) and type(n) is int and n >= 0
              for i, n in state['damage_totals'].items()), '点名累计伤害无效。')
    # Reconstruct from finite, owner-resolved hit receipts, never requested raw
    # damage, shield absorption or a different/future battle's history.
    actual_hits = [event for event in b['events'] if event.get('type') == 'hit'
        and event.get('actor') in actors and _human(actors[event['actor']])
        and event.get('target') in actors and actors[event['target']]['side'] == 'enemy'
        and event.get('actual_hp_damage', 0) > 0]
    check(all(type(event['actual_hp_damage']) is int and state['entry_tick'] < event['tick'] <= b['tick']
              for event in actual_hits), '首领伤害账含无效实际HP或跨战时钟。')
    expected_hits = [[event['actor'], event['action_id'], event['target']] for event in actual_hits]
    totals = {}
    for event in actual_hits:
        totals[event['actor']] = totals.get(event['actor'], 0)+event['actual_hp_damage']
    check(state['seen_hits'] == expected_hits and state['damage_totals'] == totals,
          '首领累计伤害或去重账与本战实际HP命中不符。')
    if admin is not None:
        law_expected = {}
        for event in actual_hits:
            if event['target'] == admin['id']:
                law_expected[event['actor']] = law_expected.get(event['actor'], 0)+event['actual_hp_damage']
        check(state.get('law_damage', {}).get(admin['id'], {}) == law_expected,
              '点名目标伤害账含小怪/护卫伤害或与实际本体命中不符。')
    released = [event for event in b['events'] if event.get('type') == 'release'
                and event.get('actor') in actors and _original_hero(actors[event['actor']],
                    dict(move_id=event.get('move'), derived=event.get('derived', False),
                         extra_chain=event.get('extra_chain', False),
                         boss_mimic=event.get('boss_mimic', False)))]
    check(state['seen_releases'] == [event['action_id'] for event in released],
          '英雄充能观察缺少本战原生实际释放回执。')
    for boss in _bosses(b):
        row = state['states'][boss['id']];cap = HERO_RELEASES if boss['kind'] == 'DEMON' else 1
        check(row['kind'] == boss['kind'] and type(row['energy']) is int and 0 <= row['energy'] <= cap
              and type(row['ready']) is bool and row['ready'] == (row['energy'] == cap), '首领能量上限或就绪状态损坏。')
        check(type(row['next_law']) is int and row['next_law'] >= state['entry_tick']+LAW_FIRST, '点名入场偏移损坏。')
        check(len(row['laws']) == row['law_sequence'] and len({x['id'] for x in row['laws']}) == len(row['laws']), '点名实例重复或丢失。')
        active = [law for law in row['laws'] if law['status'] == 'ACTIVE']
        check(len(active) <= 1 and (active[0]['id'] if active else None) == row['law'], '同战存在叠加法令。')
        check(row['broken_laws'] == sum(x['status'] == 'BROKEN' for x in row['laws']), '破令次数缺少真实法令。')
        check(row['aoe_releases'] == len(row['aoe_action_ids']) == len(set(row['aoe_action_ids'])), '条件重击释放重复。')
        for law in row['laws']:
            check(boss['kind'] == 'ADMIN' and law['boss'] == boss['id']
                  and law['target'] in actors and _human(actors[law['target']]), '法令原目标或首领身份无效。')
            check(type(law['started']) is int and state['entry_tick']+LAW_FIRST <= law['started'] <= b['tick']
                  and law['due'] == law['started']+LAW_DELAY
                  and law['threshold'] == (boss['stats']['hp']*LAW_BREAK_PERCENT+99)//100
                  and type(law['progress']) is int and law['progress'] >= 0, '法令期限或破令额度损坏。')
            check(law['status'] in ('ACTIVE', 'BROKEN', 'BOSS_DOWN', 'TARGET_DOWN', 'EXECUTED'), '法令结果未知。')
            named = [event for event in b['events'] if event.get('type') == 'boss_law_named'
                     and event.get('law_id') == law['id']]
            check(len(named) == 1 and named[0].get('actor') == boss['id']
                  and named[0].get('target') == law['target'] and named[0].get('tick') == law['started']
                  and named[0].get('due') == law['due']
                  and named[0].get('required_hp_damage') == law['threshold'],
                  '法令原目标、期限或破令门槛与实际点名回执不符。')
            progress_until = b['tick'] if law['status'] == 'ACTIVE' else law['ended_tick']
            check(type(progress_until) is int, '法令缺少可重建的结束拍。')
            progress = sum(event['actual_hp_damage'] for event in actual_hits
                           if event['target'] == boss['id'] and law['started'] <= event['tick'] <= progress_until)
            check(law['progress'] == progress, '法令破令进度与点名后的本体实际HP损失不符。')
            named_damage = sum(event['actual_hp_damage'] for event in actual_hits
                               if event['actor'] == law['target'] and event['target'] == boss['id'] and event['tick'] < law['started'])
            check(law['target_damage_at_naming'] == named_damage
                  and named[0].get('target_damage') == named_damage,
                  '点名原目标的当时累计伤害不符。')
            if law['status'] == 'ACTIVE':
                check(law['ended_tick'] is None and b['tick'] < law['due'], '过期法令仍在生效。')
            else:
                check(type(law['ended_tick']) is int and law['started'] <= law['ended_tick'] <= b['tick'], '法令结算拍损坏。')
            if law['status'] == 'BROKEN':
                check(law['progress'] >= law['threshold'], '破令没有足额真实伤害。')
            if law['status'] == 'EXECUTED':
                check(law['ended_tick'] >= law['due'] and law['progress'] < law['threshold'], '处决越过破令或期限。')
        pending = boss.get('pending')
        if pending and pending.get('move_id') in MOVES:
            check(pending.get('threat_energy') == cap and pending.get('threat_condition')
                  and pending.get('threat_started', -1) <= b['tick']
                  and pending.get('coefficient') == 2.0 and pending.get('max_targets') == 6
                  and pending.get('range') == 3
                  and boss.get('move_ready', {}).get(pending['move_id'], 0) >= pending.get('threat_started', 0)+8,
                  '条件重击缺少起手充能、冷却预约或规格。')
            if cat is not None:
                import combat as c
                board = c.cells(cat, b)
                check(pending.get('threat_origin') == pending.get('origin')
                      and pending.get('cells') == [list(p) for p in _cells(cat, board, pending['threat_origin'])], '条件重击锁区被改写。')
