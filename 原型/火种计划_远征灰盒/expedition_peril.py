"""One readable high-contract gate attack, never party-adaptive scaling.

Only chapter3 ordinary D2 gates at public L8+ after FINALE_READY qualify.
It uses an original enemy and the ordinary damage/shield/control executor.
"""
from copy import deepcopy

VERSION = 'EXPEDITION-PERIL-0.68'
MOVE = 'PERIL-RUPTURE'
MOVES = {MOVE}
SELECTION = 'highest_threat_cost_then_instance_id'
WOUND_RULE = 'half_maximum_finite_hp_or_same_action_credited_knockdown_then_reserve_until_return'
RANGE = 10
EVASION_HORIZON = 2
OUTER_RADIUS = 3
MAX_TARGETS = 4
TRIGGER_RULE = 'actionable_human_remains_in_locked_inner_circle_at_release'


def _card(dtype):
    return dict(move_id=MOVE, name='断阵重击', kind='damage', damage_type=dtype,
        coefficient=6.0, range=RANGE, radius=1, windup=3, cooldown=10, cast_limit=1,
        outer_radius=OUTER_RADIUS, max_targets=MAX_TARGETS, first_eligible_tick=1, medium='spell', interruptible=True,
        delayable_cast=True, area=True, shape='peril_conditional_circle', locks_cells=True,
        pressure_radius=1, threat_evasion_horizon=EVASION_HORIZON,
        target_rule='farthest_actionable_human_then_stable_id_lock_at_start',
        mechanic_summary='最高阶段险境G门战：第1拍起，W3/C10，仅接受1次起手（被打断也不重试）。'
            '射程10内锁最远可见人类原格，同距按ID，同时公开内圈半径1和条件外圈至半径3。'
            '释放时内圈无人则整招落空；若仍有站立可行动人类，一人未撤便引爆冻结外圈，'
            '同一次攻击最多4单位各受本敌原普攻伤害类型6.0倍攻击伤害，不产生第二击或连锁。'
            '起手预警不追踪，W3提供最多3个移动窗口；可留出空格用避险姿态撤出、合法延后或打断，仍受占位/墙/浅水/起手待命限制。'
            '护盾、防御和减伤正常有效；单次实际入血达到本人最大HP一半，或本招实际入血并亲自击倒，均为重创；本战仍可治疗/复起，'
            '战后本趟只能预备至归城休整；可提前撤退，此处不是不可撤终战。')


def install(cat):
    import combat
    combat.SUPPORTED_MOVES.update(MOVES)
    cat.rules['expedition_peril'] = dict(version=VERSION, chapter=3, difficulty='D2',
        required_fact='FINALE_READY', minimum_effective_threat=8, slot='G',
        selection=SELECTION, coefficient=6.0, windup=3, cooldown=10,
        range=RANGE, radius=1, outer_radius=OUTER_RADIUS, max_targets=MAX_TARGETS, cast_limit=1, scale_by_party=False,
        first_eligible_tick=1, wound_rule=WOUND_RULE,
        threat_evasion_horizon=EVASION_HORIZON, trigger_rule=TRIGGER_RULE)


def _context(game, growth, rid):
    manifest = game.s.get('manifest') or {}
    tier = manifest.get('tier') or {}
    pressure = manifest.get('progression_pressure') or {}
    route = next((r for r in game.cat.config['routes'] if r['route_id'] == manifest.get('route_id', game.s.get('route'))), {})
    return dict(version=VERSION, mission=game.s.get('mission'),
        chapter=pressure.get('chapter', route.get('chapter', 0)),
        difficulty=tier.get('id'), facts=sorted(tier.get('unlock_facts', [])),
        slot='G', effective_threat=growth.get('effective_threat', 0), region=rid,
        selection=SELECTION)


def _eligible(context):
    return (context['mission'] == 'ORDINARY' and context['chapter'] == 3
            and context['difficulty'] == 'D2' and 'FINALE_READY' in context['facts']
            and context['slot'] == 'G' and context['effective_threat'] >= 8)


def _candidates(encounter):
    import bosses
    # A fixed boss in an ordinary slot still retains its independent0.67 kit.
    if any(u['enemy_id'] in bosses.IDS for u in encounter.get('units', [])):
        return []
    return [u for u in encounter.get('units', []) if not u.get('mechanism')]


def _owner(encounter):
    choices = _candidates(encounter)
    return min(choices, key=lambda u: (-u.get('threat_cost', 0), u['instance_id'])) if choices else None


def freeze(game, growth, rid):
    """Decorate the freshly frozen region BEFORE either intel or combat sees it."""
    context = _context(game, growth, rid)
    if not _eligible(context):
        return growth
    for encounter in growth.get('encounters', {}).get('G', {}).values():
        owner = _owner(encounter)
        if owner is None:
            continue
        dtype = owner['basic_attack']['damage_type']
        meta = dict(**context, owner=owner['instance_id'], enemy_id=owner['enemy_id'],
                    source_stats=deepcopy(owner['stats']),
                    source_threat_cost=owner.get('threat_cost', 0), damage_type=dtype,
                    wound_rule=WOUND_RULE, range=RANGE,
                    threat_evasion_horizon=EVASION_HORIZON, outer_radius=OUTER_RADIUS,
                    max_targets=MAX_TARGETS, trigger_rule=TRIGGER_RULE)
        encounter['expedition_peril'] = meta
        owner['moves'] = [_card(dtype)] + [row for row in owner.get('moves', []) if row['move_id'] != MOVE]
    return growth


def initialize(b, encounter):
    spec = encounter.get('expedition_peril')
    if spec is None:
        b.pop('expedition_peril', None)
        return
    b['expedition_peril'] = dict(spec=deepcopy(spec), actions=[], detonations=[], hits=[], wounds={})


def prioritize(b, a, cards, tick):
    state = b.get('expedition_peril')
    if not state or state['spec']['owner'] != a['id']:
        return cards
    return sorted(cards, key=lambda card: card['move_id'] != MOVE)


def _locked(cat, board, origin, center, radius=1):
    import combat as c
    return sorted(p for p in board if c.distance(center, p) <= radius and c.visible(cat, board, origin, p))


def _outer(cat, board, origin, center):
    import combat as c
    return [p for p in _locked(cat, board, origin, center, OUTER_RADIUS) if c.distance(center, p) > 1]


def choose(b, a, card, foes, cat, board, tick):
    import combat as c
    state = b.get('expedition_peril')
    if (not state or state['spec']['owner'] != a['id'] or card['move_id'] != MOVE
            or tick < 1 or a.get('move_uses', {}).get(MOVE, 0) >= 1):
        return None
    humans = [v for v in foes if v['hp'] > 0 and not v.get('mechanism')
              and not v.get('boss_part') and v['kind'] != 'PET-H04'
              and c.distance(a['pos'], v['pos']) <= RANGE and c.visible(cat, board, a['pos'], v['pos'])]
    if not humans:
        return None
    victim = min(humans, key=lambda v: (-c.distance(a['pos'], v['pos']), v['id']))
    return victim, _locked(cat, board, a['pos'], victim['pos']), dict(
        peril_origin=a['pos'][:], peril_center=victim['pos'][:], peril_started=tick,
        peril_outer_cells=[list(p) for p in _outer(cat, board, a['pos'], victim['pos'])])


def started(b, a, action, tick, log):
    if action.get('move_id') != MOVE:
        return
    state = b['expedition_peril']
    assert state['spec']['owner'] == a['id'] and not state['actions']
    a['move_ready'][MOVE] = max(a['move_ready'].get(MOVE, 0), tick+10)
    row = dict(action_id=action['id'], tick=tick, due=action['due'],
        target=action['target'], center=action['peril_center'][:],
        origin=action['peril_origin'][:], cells=deepcopy(action['cells']),
        outer_cells=deepcopy(action['peril_outer_cells']))
    state['actions'].append(row)
    log('expedition_peril_warning', actor=a['id'], **deepcopy(row),
        region=state['spec']['region'], effective_threat=state['spec']['effective_threat'])


def _is_human(v):
    return (v.get('side') == 'player' and v.get('kind') != 'PET-H04'
            and not v.get('mechanism') and not v.get('boss_part'))


def targets(a, action, alive, cat, board, *, battle=None, tick=None, log=None):
    import combat as c
    origin = action['peril_origin'];center = action['peril_center']
    inner = {tuple(p) for p in action['cells']}
    outer = {tuple(p) for p in action['peril_outer_cells']}
    now = tick if tick is not None else action.get('due', 1)
    eligible = [v for v in alive if v['hp'] > 0 and v['side'] != a['side']
              and not v.get('mechanism') and not v.get('boss_part')
              and now >= v.get('active_from', 1) and tuple(v['pos']) in inner | outer
              and c.visible(cat, board, origin, v['pos'])]
    triggers = sorted(v['id'] for v in eligible if _is_human(v) and tuple(v['pos']) in inner)
    result = sorted(eligible, key=lambda v: (c.distance(center, v['pos']), v['id']))[:MAX_TARGETS] if triggers else []
    action['peril_hit_origin'] = origin[:]
    action['peril_triggered'] = bool(triggers)
    if battle is not None:
        row = dict(action_id=action['id'], tick=now, triggered=bool(triggers), trigger_humans=triggers,
            targets=[v['id'] for v in result], inner_cells=deepcopy(action['cells']),
            outer_cells=deepcopy(action['peril_outer_cells']),
            occupants=[dict(id=v['id'], kind=v['kind'], pos=v['pos'][:], hp=v['hp'],
                            active_from=v.get('active_from', 1), human=_is_human(v))
                       for v in sorted(eligible, key=lambda v: v['id'])])
        state = battle['expedition_peril']
        _check(not any(old['action_id'] == action['id'] for old in state['detonations']), '条件扩散不能同动作重复结算。')
        state['detonations'].append(row)
        if log:
            log('expedition_peril_detonation', actor=a['id'], **deepcopy(row))
    return result


def hit(b, a, v, action, amount, tick, log):
    if action.get('move_id') != MOVE or amount <= 0:
        return
    state = b['expedition_peril']
    row = dict(action_id=action['id'], tick=tick, target=v['id'], actual_hp_damage=amount)
    state['hits'].append(row)
    log('expedition_peril_damage', actor=a['id'], **row)
    if (v['side'] == 'player' and v['kind'] != 'PET-H04'
            and amount*2 >= v['stats']['hp'] and v['id'] not in state['wounds']):
        _mark_wound(b, a, v, action['id'], amount, tick, 'HALF_MAXIMUM_HP', log)


def _wound(b, victim, action_id, amount, tick, reason):
    return dict(version=VERSION, member=victim['id'], action_id=action_id, tick=tick,
        battle_id=b['battle_id'], encounter_id=b['encounter_id'],
        region=b['expedition_peril']['spec']['region'], maximum_hp=victim['stats']['hp'],
        threshold=(victim['stats']['hp']+1)//2, actual_hp_damage=amount, rule=WOUND_RULE, reason=reason)


def _mark_wound(b, owner, victim, action_id, amount, tick, reason, log):
    if victim['id'] in b['expedition_peril']['wounds']:
        return
    wound = _wound(b, victim, action_id, amount, tick, reason)
    b['expedition_peril']['wounds'][victim['id']] = wound
    log('expedition_peril_wound', actor=owner['id'], target=victim['id'], **deepcopy(wound),
        effect='Current battle healing/revival remains legal; reserve only after this battle until return')


def end_tick(b, tick, log):
    """Unique direct-death receipts close the low-starting-HP revival loophole.

    Call after the executor's direct death-credit and any same-tick hero revive.
    Revival does not erase a real credited knockdown that already happened.
    """
    state = b.get('expedition_peril')
    if not state:
        return
    actors = {a['id']: a for a in b['actors']};owner = actors[state['spec']['owner']]
    for receipt in b['events'][:]:
        if (receipt.get('type') != 'death_credit' or receipt.get('tick') != tick
                or receipt.get('actor') != owner['id'] or receipt.get('move') != MOVE):
            continue
        victim = actors.get(receipt.get('target'))
        if not victim or victim['side'] != 'player' or victim['kind'] == 'PET-H04':
            continue
        hit = next((row for row in state['hits'] if row['tick'] == tick
                    and row['action_id'] == receipt['action_id'] and row['target'] == victim['id']), None)
        if hit and hit['actual_hp_damage'] > 0:
            _mark_wound(b, owner, victim, receipt['action_id'], hit['actual_hp_damage'], tick,
                        'CREDITED_KNOCKDOWN', log)


def deployable(member):
    return not member.get('journey_unfit')


def check_deployment(game):
    _check(all(not m.get('deployed') or deployable(m) for m in game.s['party']),
           '断阵重创者本趟只能随队预备，归城休整后才可再次上阵。')


def settle_battle(game, b):
    """After normal HP copying, before the normal after/report snapshots."""
    wounds = (b.get('expedition_peril') or {}).get('wounds', {})
    changed = []
    for iid, wound in wounds.items():
        member = game.member(iid)
        _check(member in game.s['party'], '危险重创不是当前随队原人。')
        old = member.get('journey_unfit')
        _check(not old or old == wound, '重创来源不能静默替换。')
        member['journey_unfit'] = deepcopy(wound);member['deployed'] = False
        changed.append(iid)
    return changed


def clear(game, reason):
    """A real return/defeat settlement ends this trip restriction, not HP loss."""
    import town
    cleared = []
    for member in town.roster(game):
        wound = member.get('journey_unfit')
        if wound:
            cleared.append(dict(member=member['instance_id'], source=deepcopy(wound), reason=reason))
            member.pop('journey_unfit', None)
    if cleared:
        game.log('expedition_peril_return_care', reason=reason, cleared=deepcopy(cleared))
    return cleared


def public_game(game):
    import town
    return [dict(id=m['instance_id'], role=m['unit_id'], cost=m['cost'],
                 source=deepcopy(m['journey_unfit'])) for m in town.roster(game) if m.get('journey_unfit')]


def describe_game(game):
    rows = public_game(game)
    return ('断阵重创（本趟只能预备，归城休整解除）：'+
            '、'.join(f"{row['id']}（Cost{row['cost']}）" for row in rows)) if rows else ''


def public(b):
    return deepcopy(b.get('expedition_peril')) if b else None


def describe(b):
    state = public(b)
    if not state:
        return ''
    return (f"最高阶段G门危险：{state['spec']['owner']}断阵重击，W3/C10、本场1次、r10最远可见原人/同距ID；"
            '起手同时锁内圈r1与条件外圈r3，最多3个移动窗口。内圈人类都撤出则整招落空；一人未撤便引爆冻结外圈，'
            '同一攻击最多4单位、6.0倍伤害，无第二击/连锁。'
            '可避险/延后/打断，现有盾与减伤有效；单次实际入血>=本人最大HP一半，或本招正入血并亲自击倒则重创，'
            '本战可治疗/复起，战后只能预备至归城休整，可撤退终止本趟。')


def _check(ok, message):
    if not ok:
        raise ValueError(message)


def _validate_meta(meta):
    _check(isinstance(meta, dict) and meta.get('version') == VERSION
           and meta.get('selection') == SELECTION, '最高阶段危险规格或选择来源无效。')
    _check(isinstance(meta.get('facts'), list) and meta['facts'] == sorted(set(meta['facts']))
           and _eligible(meta), '最高阶段危险越过公开章节、档位、事实或G门资格。')
    _check(meta.get('damage_type') in ('physical', 'magic') and isinstance(meta.get('source_stats'), dict),
           '最高阶段危险缺少原单位攻击面板。')
    _check(meta.get('wound_rule') == WOUND_RULE, '最高阶段重创规则缺少冻结来源。')
    _check(meta.get('range') == RANGE and meta.get('threat_evasion_horizon') == EVASION_HORIZON,
           '最高阶段后阵射程或公开避险窗口与冻结规格不符。')
    _check(meta.get('outer_radius') == OUTER_RADIUS and meta.get('max_targets') == MAX_TARGETS
           and meta.get('trigger_rule') == TRIGGER_RULE, '最高阶段条件扩散规格与冻结规则不符。')


def validate_encounter(encounter, context=None):
    meta = encounter.get('expedition_peril')
    if meta is None:
        _check(not any(card['move_id'] == MOVE for u in encounter.get('units', []) for card in u.get('moves', [])),
               '危险技能缺少公开来源。')
        if context is not None and _eligible(context):
            _check(_owner(encounter) is None, '合法最高阶段G门丢失冻结危险。')
        return
    _validate_meta(meta)
    if context is not None:
        _check(all(meta.get(key) == value for key, value in context.items()), '危险资格与本区出发冻结规则不符。')
    owner = _owner(encounter)
    _check(owner is not None and owner['instance_id'] == meta['owner']
           and owner['enemy_id'] == meta['enemy_id'] and owner['stats'] == meta['source_stats']
           and owner.get('threat_cost', 0) == meta['source_threat_cost']
           and owner['basic_attack']['damage_type'] == meta['damage_type'], '危险施术者不是按原敌阵预算确定的单位。')
    for unit in encounter['units']:
        cards = [card for card in unit.get('moves', []) if card['move_id'] == MOVE]
        _check(cards == ([_card(meta['damage_type'])] if unit['instance_id'] == meta['owner'] else []),
               '危险技能数值或法定唯一施术者被改变。')


def _validated_due(b, owner, row, actors):
    """Rebuild accepted windup plus actual, source-backed cast extensions.

    plan_cast_window is an auxiliary resource receipt, not another delay.
    EN11 defers acceptance of a start; its wait is already reflected in row.tick
    and therefore never adds another tick to the accepted cast's deadline.
    """
    due = row['due']
    delays = [event for event in b['events']
              if event.get('type') in ('cast_delayed', 'plan_cast_delayed')
              and event.get('target') == owner['id'] and event.get('cast_id') == row['action_id']]
    # All three current producers share the cast.delayed guard. They may not
    # each claim a separate extension on the same cast.
    _check(len(delays) <= 1, '同一危险施法重复延咒，超出当前共享一次规则。')
    for event in delays:
        source = actors.get(event.get('actor'))
        _check(source is not None and source['side'] != owner['side']
               and row['tick'] <= event.get('tick', -1) < due
               and event.get('release_tick') == due+1, '危险延咒的施术者、时序或逐次期限不合法。')
        tick = event['tick']
        positive_hits = [hit for hit in b['events'] if hit.get('type') == 'hit'
                        and hit.get('actor') == source['id'] and hit.get('target') == owner['id']
                        and hit.get('tick') == tick and hit.get('raw', 0) > 0]
        if event['type'] == 'plan_cast_delayed':
            import battle_plans
            _check(battle_plans.has(b, source, 'PL09') and event.get('producer_effect_id') == 'PL09'
                   and any(hit.get('action') == 'BASIC' and hit.get('action_id') == event.get('action_id')
                           for hit in positive_hits), '危险方案延咒缺少PL09与同拍正普攻回执。')
        elif event.get('move') == 'SK-SB-C03':
            aid=event.get('action_id')
            _check('SB-C03' in source.get('books_equipped',[])
                   and any(hit.get('action')=='SK-SB-C03' and hit.get('action_id')==aid for hit in positive_hits)
                   and any(e.get('type')=='release' and e.get('actor')==source['id']
                           and e.get('action_id')==aid and e.get('move')=='SK-SB-C03'
                           and e.get('tick')==tick for e in b['events'])
                   and any(e.get('type')=='windup' and e.get('actor')==source['id']
                           and e.get('action_id')==aid and e.get('move')=='SK-SB-C03'
                           and e.get('target_cast')==row['action_id'] for e in b['events']),
                   '危险延咒缺少SB-C03装备、正命中、释放及原施法预约。')
        elif event.get('move') == 'SK-BK08':
            aid = event.get('action_id')
            _check('BK08' in source.get('books_equipped', [])
                   and any(e.get('type') == 'release' and e.get('actor') == source['id']
                           and e.get('action_id') == aid and e.get('move') == 'SK-BK08'
                           and e.get('tick') == tick for e in b['events'])
                   and any(e.get('type') == 'windup' and e.get('actor') == source['id']
                           and e.get('action_id') == aid and e.get('move') == 'SK-BK08'
                           and e.get('target_cast') == row['action_id'] for e in b['events']),
                   '危险技能书延咒缺少已装备BK08、真实释放与原施法预约。')
        else:
            native_hits = [hit for hit in positive_hits if hit.get('action') in ('M04-A', 'M08-A')]
            _check(any(any(e.get('type') == 'windup' and e.get('actor') == source['id']
                           and e.get('action_id') == hit.get('action_id')
                           and e.get('move') == hit.get('action')
                           and e.get('target_cast') == row['action_id'] for e in b['events'])
                       for hit in native_hits), '危险职业延咒缺少M04/M08正命中与原施法预约。')
        due += 1
    return due


def validate(b, cat=None):
    if not b:
        return
    state = b.get('expedition_peril')
    actors = {a['id']: a for a in b['actors']}
    if not state:
        _check(not any(card.get('move_id') == MOVE for a in actors.values() for card in a.get('moves', [])), '战斗危险技能缺少冻结来源。')
        return
    meta = state['spec'];_validate_meta(meta)
    owner = actors.get(meta['owner'])
    _check(owner is not None and owner['side'] == 'enemy' and owner['kind'] == meta['enemy_id']
           and owner['stats'] == meta['source_stats'], '战斗危险施术者或原面板改变。')
    for actor in actors.values():
        cards = [card for card in actor.get('moves', []) if card['move_id'] == MOVE]
        _check(cards == ([_card(meta['damage_type'])] if actor['id'] == owner['id'] else []), '战斗危险卡片数值或归属无效。')
    actions = state['actions']
    _check(len(actions) <= 1 and owner['move_uses'].get(MOVE, 0) == len(actions), '危险有限一次的起手次数被重置。')
    board = None
    if cat is not None:
        import combat
        board = combat.cells(cat, b)
    for row in actions:
        windups = [e for e in b['events'] if e.get('type') == 'windup'
                   and e.get('actor') == owner['id'] and e.get('action_id') == row['action_id'] and e.get('move') == MOVE]
        _check(len(windups) == 1 and windups[0]['tick'] == row['tick'] >= 1
               and windups[0]['release_tick'] == row['due'] == row['tick']+3
               and windups[0]['cells'] == row['cells'] and windups[0].get('target') == row['target']
               and windups[0].get('peril_outer_cells') == row['outer_cells'], '危险起手、原目标、内外预警或期限缺少真实回执。')
        if board is not None:
            import combat
            _check(combat.distance(row['origin'], row['center']) <= RANGE
                   and combat.visible(cat, board, row['origin'], row['center'])
                   and row['cells'] == [list(p) for p in _locked(cat, board, row['origin'], row['center'])]
                   and row['outer_cells'] == [list(p) for p in _outer(cat, board, row['origin'], row['center'])], '危险内外预警锁区超出真实LOS或被改写。')
        due = _validated_due(b, owner, row, actors)
        releases = [e for e in b['events'] if e.get('type') == 'release'
                    and e.get('actor') == owner['id'] and e.get('action_id') == row['action_id']
                    and e.get('move') == MOVE]
        _check(len(releases) <= 1 and all(e.get('tick') == due for e in releases), '危险实际释放拍与起手及合法延咒账不符。')
        pending = owner.get('pending')
        if pending and pending.get('move_id') == MOVE:
            _check(pending.get('id') == row['action_id'] and pending.get('cells') == row['cells']
                   and pending.get('origin') == pending.get('peril_origin') == row['origin']
                   and pending.get('peril_center') == row['center']
                   and pending.get('peril_outer_cells') == row['outer_cells'], '危险待释放动作脱离原内外预警。')
            for key, value in _card(meta['damage_type']).items():
                _check(pending.get(key) == value, '危险待释放数值被改变：'+key)
            _check(pending['due'] == due, '危险释放期限无合法延后来源。')
        detonations = [d for d in state.get('detonations', []) if d['action_id'] == row['action_id']]
        _check(len(detonations) == len(releases), '条件扩散结算必须与同一次真实释放一一对应。')
        for det in detonations:
            _check(det['tick'] == releases[0]['tick'] and det['inner_cells'] == row['cells']
                   and det['outer_cells'] == row['outer_cells'], '条件扩散脱离原释放拍或冻结警区。')
            occupants = det['occupants'];seen = set();inner = {tuple(p) for p in row['cells']}
            locked = inner | {tuple(p) for p in row['outer_cells']}
            for occupant in occupants:
                v = actors.get(occupant['id'])
                _check(v is not None and v['side'] != owner['side'] and v['kind'] == occupant['kind']
                       and occupant['id'] not in seen and occupant['human'] == _is_human(v)
                       and 0 < occupant['hp'] <= v['stats']['hp'] and occupant['active_from'] <= det['tick']
                       and tuple(occupant['pos']) in locked, '条件扩散占位回执含非活人、重复人或越界单位。')
                if board is not None:
                    import combat
                    _check(combat.visible(cat, board, row['origin'], occupant['pos']), '条件扩散占位不符原点LOS。')
                seen.add(occupant['id'])
            triggers = sorted(v['id'] for v in occupants if v['human'] and tuple(v['pos']) in inner)
            import combat
            targets = [v['id'] for v in sorted(occupants,
                key=lambda v: (combat.distance(row['center'], v['pos']), v['id']))[:MAX_TARGETS]] if triggers else []
            _check(det['triggered'] == bool(triggers) and det['trigger_humans'] == triggers
                   and det['targets'] == targets, '条件扩散未按内圈活人触发或超过同击四目标。')
            events = [event for event in b['events'] if event.get('type') == 'expedition_peril_detonation'
                      and event.get('actor') == owner['id'] and event.get('action_id') == row['action_id']]
            _check(len(events) == 1 and all(events[0].get(key) == value for key, value in det.items()),
                   '条件扩散缺少同拍公开触发回执。')
    actual = [dict(action_id=e['action_id'], tick=e['tick'], target=e['target'], actual_hp_damage=e['actual_hp_damage'])
              for e in b['events'] if e.get('type') == 'hit' and e.get('actor') == owner['id']
              and e.get('action') == MOVE and e.get('actual_hp_damage', 0) > 0]
    _check(state['hits'] == actual, '危险损失与实际HP账不符。')
    expected_wounds = {}
    for receipt in actual:
        victim = actors.get(receipt['target'])
        if (not victim or victim['side'] != 'player' or victim['kind'] == 'PET-H04'
                or receipt['actual_hp_damage']*2 < victim['stats']['hp']):
            continue
        expected_wounds[victim['id']] = _wound(b, victim, receipt['action_id'],
            receipt['actual_hp_damage'], receipt['tick'], 'HALF_MAXIMUM_HP')
    for credit in b['events']:
        if credit.get('type') != 'death_credit' or credit.get('actor') != owner['id'] or credit.get('move') != MOVE:
            continue
        victim = actors.get(credit.get('target'))
        receipt = next((r for r in actual if r['action_id'] == credit.get('action_id')
                        and r['target'] == credit.get('target') and r['tick'] == credit.get('tick')), None)
        if (victim and victim['side'] == 'player' and victim['kind'] != 'PET-H04'
                and receipt and victim['id'] not in expected_wounds):
            expected_wounds[victim['id']] = _wound(b, victim, receipt['action_id'],
                receipt['actual_hp_damage'], receipt['tick'], 'CREDITED_KNOCKDOWN')
    _check(state.get('wounds', {}) == expected_wounds, '重创不对应真实半血单击/本招击倒，或实际重创被删。')


def validate_game(game):
    """Also guard visited frozen regions that have not entered combat yet."""
    for rid, region in game.s.get('regions', {}).items():
        growth = region.get('growth') or {}
        context = _context(game, growth, rid)
        for slot, encounters in growth.get('encounters', {}).items():
            for encounter in encounters.values():
                validate_encounter(encounter, {**context, 'slot': slot})
    battle = game.s.get('battle')
    validate(battle, game.cat)
    if battle and game.s.get('mission') == 'ORDINARY':
        region = game.s.get('regions', {}).get(game.s.get('region'), {})
        options = (region.get('growth') or {}).get('encounters', {}).get(game.s.get('site'), {})
        matches = [enc for enc in options.values() if enc.get('encounter_id') == battle.get('encounter_id')]
        actual = (battle.get('expedition_peril') or {}).get('spec')
        if actual is not None or any(enc.get('expedition_peril') for enc in matches):
            _check(len(matches) == 1, '危险战斗没有唯一的当前冻结敌阵来源。')
            _check(actual == matches[0].get('expedition_peril'), '战斗危险来源与当前区域/战槽的冻结敌阵不符。')
    import town
    reports = game.s.get('battle_reports', []) + ([battle] if battle else [])
    completed_wounds = {}
    for report in game.s.get('battle_reports', []):
        if report.get('expedition_peril'):
            validate(report, game.cat)
        completed_wounds.update((report.get('expedition_peril') or {}).get('wounds', {}))
    for member in town.roster(game):
        wound = member.get('journey_unfit')
        if wound:
            sources = [(report.get('expedition_peril') or {}).get('wounds', {}).get(member['instance_id'])
                       for report in reports if report.get('battle_id') == wound.get('battle_id')]
            _check(len(sources) == 1 and sources[0] == wound, '随队重创缺少原人本趟真实受击来源。')
            _check(not member.get('deployed'), '重创者战后必须作为预备，不能再次部署。')
        if game.s.get('mission') == 'ORDINARY' and game.s.get('phase', 'EXPLORE') in ('EXPLORE', 'BATTLE', 'RECOVERY_STOP'):
            _check(wound == completed_wounds.get(member['instance_id']), '尚未归城的真实重创不能被清除或替换。')
