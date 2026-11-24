"""Versioned SB acquisition, frozen random sources and safe-return receipts.

All mutable acquisition state belongs to Game.s and participates in execute's
normal transaction.  The catalogue and combat executor remain independent.
"""
from copy import deepcopy
import hashlib
import json
from data import keyed_rng

VERSION = 'SB-REWARDS-0.72'
STAGE_FACTS = {'B': 'ST-101', 'I': 'ST-104', 'E': 'CH2_COMPLETE'}
PRICES = {'B': 8, 'I': 12, 'E': 16, 'X': 20}
BOSS_BOOKS = dict(zip(('ST-201', 'ST-202', 'ST-301', 'ST-302'),
                      ('SB-X01', 'SB-X02', 'SB-X03', 'SB-X04')))
DELIVERY_FACTS = {'ST-104', 'ST-303'} | set(BOSS_BOOKS)
TASKS = {
    'SB-T01': ['SB-D03', 'SB-D10', 'SB-M03'],
    'SB-T02': ['SB-D06', 'SB-B02', 'SB-M02'],
    'SB-T03': ['SB-H03', 'SB-S03', 'SB-P02'],
}
THEMES = {
    'RG01': 'D01 D02 D03 H01 S01 M01 P01',
    'RG02': 'D02 D04 S02 S04 C01 C04 P04',
    'RG03': 'D09 D10 D11 D12 C02 C03 B04',
    'RG04': 'H02 H03 H04 S03 M04 B03',
    'RG05': 'D04 D07 D12 S04 C04 B02 P04',
    'RG06': 'D01 D05 D06 M01 M02 M03 P02',
    'RG07': 'H01 H02 H03 S02 S03 B01 B03 P03',
    'RG08': 'D02 D05 D07 D08 S01 S04 B02 P01',
}


def check(ok, message):
    if not ok:
        raise ValueError('技能书获取：' + message)


def _books():
    from book_catalog import BOOKS
    return BOOKS


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _state(game):
    return game.s['book_rewards']


def initialize(game):
    game.s['book_rewards'] = dict(version=VERSION, target=None, progress=0,
        deliveries={}, entitlements={}, tasks={}, departures={}, settlements={}, target_events=[])


def _facts(game):
    return set(game.s.get('unlocked_facts', []))


def unlocked(game, book):
    row = _books().get(book)
    if not row:
        return False
    if row.get('hidden'):
        if game.s.get('book_stock', {}).get(book, 0) > 0:
            return True
        people = game.s.get('party', []) + game.s.get('home_roster', [])
        return any(book in m.get('books_learned', []) or book in m.get('books_equipped', [])
                   for m in people)
    stage = row['stage']
    if stage == 'X':
        return any(value == book and key in _state(game)['deliveries']
                   for key, value in BOSS_BOOKS.items())
    return STAGE_FACTS[stage] in _facts(game)


def price(game, book):
    check(book in _books(), '不存在该书。')
    return PRICES[_books()[book]['stage']]


def requirement(game, book):
    row = _books().get(book)
    if not row:
        return '不存在该书'
    if row.get('hidden'):
        return '保全十案后从回信获得'
    return (next(key for key, value in BOSS_BOOKS.items() if value == book) + '真实首次战后报告'
            if row['stage'] == 'X' else STAGE_FACTS[row['stage']])


def _ordinary_ids(facts):
    return sorted(bid for bid, row in _books().items()
                  if row['stage'] != 'X' and STAGE_FACTS[row['stage']] in facts)


def _sample(seed, salt, facts, region):
    rng = keyed_rng(seed, VERSION + ':' + salt)
    available = _ordinary_ids(facts)
    stages = {stage for stage in ('B', 'I', 'E') if any(_books()[bid]['stage'] == stage for bid in available)}
    check(stages, '当前章节没有已开放的普通书。')
    weights = [('B', 10), ('I', 35), ('E', 55)] if 'E' in stages else [('B', 40), ('I', 60)] if 'I' in stages else [('B', 100)]
    roll = rng.randrange(sum(weight for stage, weight in weights if stage in stages))
    stage = None
    for candidate, weight in weights:
        if candidate not in stages:
            continue
        if roll < weight:
            stage = candidate
            break
        roll -= weight
    pool = [bid for bid in available if _books()[bid]['stage'] == stage]
    themed = [bid for bid in pool if bid[3:] in THEMES.get(region, '').split()]
    return rng.choice(themed if themed and rng.randrange(100) < 60 else pool)


def _contract(cat, manifest, seed, facts, target, progress, expedition, game_id):
    facts = sorted(facts)
    profile = manifest['profile']
    cap = {'SHORT': 1, 'MEDIUM': 2, 'LONG': 3}[profile]
    if manifest['tier']['id'] == 'D2':
        cap = max(cap, 2)
    sources = {}
    challenge = manifest.get('challenge') or {}
    for rid, region in sorted(manifest['regions'].items()):
        for slot, probability in (('G', 25), ('L', 50)):
            binding = region['encounters'].get(slot)
            if not binding:
                continue
            if challenge.get('region') == rid and challenge.get('slot') == slot:
                continue
            eid = binding.get('encounter_id', binding.get('default_encounter_id'))
            if not eid or eid.startswith(('BATTLE-MG', 'BATTLE-DEMON', 'BATTLE-ADMIN', 'INTRO-', 'TUT')):
                continue
            key = f'{game_id}:{expedition}:{rid}:{slot}:{slot}'
            sources[key] = dict(key=key, kind=slot, region=rid, site=slot, encounter_id=eid,
                drop=keyed_rng(seed, VERSION + ':drop:' + rid + ':' + slot).randrange(100) < probability,
                normal_id=_sample(seed, rid + ':' + slot, facts, rid), target_id=target)
        eligible = []
        for node, binding in sorted(region['events'].items()):
            event = cat.events[binding['event_id']]
            if event['type'] != 'humanity' and any(
                    option.get('reward_bundle_id') == 'RB-MAT2' and option['option_id'] in binding['enabled_options']
                    for option in event['options']):
                eligible.append(node)
        if eligible:
            node = keyed_rng(seed, VERSION + ':event:' + rid).choice(eligible)
            key = f'{game_id}:{expedition}:{rid}:{node}:BOOK'
            sources[key] = dict(key=key, kind='BOOK', region=rid, site=node, drop=True,
                event_id=region['events'][node]['event_id'],
                normal_id=_sample(seed, rid + ':' + node + ':BOOK', facts, rid), target_id=target)
    return dict(version=VERSION, seed=seed, facts=facts, target=target, progress=progress,
                replacement_enabled=bool(target and progress >= 2), expedition=expedition,
                game_id=game_id, profile=profile, cap=cap, sources=sources)


def _manifest_source(manifest):
    """Keep only the frozen inputs this subsystem actually uses."""
    result = dict(profile=manifest['profile'], tier={'id': manifest['tier']['id']}, regions={})
    if manifest.get('challenge'):
        result['challenge'] = {key: manifest['challenge'][key] for key in ('region', 'slot')}
    for rid, region in manifest['regions'].items():
        result['regions'][rid] = dict(encounters={slot: {
            key: value for key, value in binding.items() if key in ('encounter_id', 'default_encounter_id')}
            for slot, binding in region['encounters'].items() if slot in ('G', 'L')}, events={
                site: {key: deepcopy(binding[key]) for key in ('event_id', 'enabled_options')}
                for site, binding in region['events'].items()})
    return result


def bind_manifest(game, manifest):
    check(game.s.get('mission') == 'ORDINARY', '固定剧情和终战不能冻结普通掉书合同。')
    state = _state(game)
    contract = _contract(game.cat, manifest, game.s['seed'], _facts(game), state['target'],
                         state['progress'], game.s['expedition_no'], game.s['id'])
    check(manifest['caps']['book_claims'] == contract['cap'], '档位与书籍额度不一致。')
    key = str(game.s['expedition_no'])
    check(key not in state['departures'], '本趟已冻结，不能重新抽书。')
    manifest['book_rewards'] = contract
    for region in manifest['regions'].values():
        for binding in region['events'].values():
            binding.pop('book_offer', None)
    for source in contract['sources'].values():
        if source['kind'] == 'BOOK':
            manifest['regions'][source['region']]['events'][source['site']]['book_offer'] = dict(
                source_key=source['key'], book_id=source['normal_id'], target_id=source['target_id'],
                mutually_exclusive_with_original_choices=True)
    state['departures'][key] = dict(contract=deepcopy(contract), manifest_source=_manifest_source(manifest),
                                    claims=[], battle_drops={}, pending_drop=None, settled=None)
    state['target_events'].append(dict(kind='DEPARTURE', expedition=key))
    from joint_sampling_model import digest
    manifest.pop('manifest_sha256', None)
    manifest['manifest_sha256'] = digest(manifest)


def _departure(game):
    return _state(game)['departures'].get(str(game.s['expedition_no']))


def _all_battles(game):
    trips = [game.s] + game.s.get('completed_history', [])
    return {battle['battle_id']: battle for trip in trips for battle in trip.get('battle_reports', [])}


def _metrics(battle):
    actors = {actor['id']: actor for actor in battle['actors']}
    found = {key: [] for key in TASKS}
    for event in battle.get('events', []):
        actor = actors.get(event.get('actor'))
        victim = actors.get(event.get('target'))
        if not actor or actor.get('side') != 'player' or event.get('derived') or event.get('caused_by_consumer'):
            continue
        kind = event['type']
        eid = event.get('event_id') or event.get('action_id') or event.get('origin_action_id')
        if not eid:
            continue
        if kind == 'hit' and victim and victim.get('side') != 'player' and event.get('actual_hp_damage', 0) + event.get('absorbed', 0) > 0:
            medium = event.get('medium', actor.get('basic_medium', actor.get('medium')))
            move = next((row for row in actor.get('moves', []) if row['move_id'] == event.get('action')), {})
            medium = move.get('medium', medium)
            bid = event.get('action', '').removeprefix('SK-')
            if bid in _books():
                requires = _books()[bid]['requires']
                medium = ('near' if any(value in requires for value in ('near', 'physical_near')) else
                          'projectile' if 'physical_projectile' in requires else
                          'spell' if event.get('hit_distance', 0) > 1 else 'tool')
            if medium == 'near':
                found['SB-T01'].append(eid)
            elif medium in ('projectile', 'spell') and event.get('hit_distance', 0) > 1:
                found['SB-T02'].append(eid)
        friendly = victim and victim.get('side') == 'player'
        if kind == 'heal' and friendly and event.get('effective', 0) > 0 and event.get('action_id'):
            found['SB-T03'].append(eid)
        shield_effect = event.get('move', event.get('book', ''))
        active_shield = not shield_effect.endswith('-P') and not any(
            value in shield_effect for value in ('SB-P01', 'SB-P02', 'SB-P03', 'SB-P04'))
        if kind in ('hero_shield', 'book_shield', 'sb_shield') and friendly and active_shield and event.get('added', 0) > 0 and event.get('action_id'):
            found['SB-T03'].append(eid)
        if kind == 'roster_shield_created' and friendly and event.get('added', 0) > 0 and event.get('producer_effect_id') == 'M05-A':
            found['SB-T03'].append(eid)
    return {key: sorted(set(value)) for key, value in found.items()}


def battle_victory(game, battle):
    if battle.get('result') != 'VICTORY' or game.s.get('debug_tainted') or battle.get('debug_tainted'):
        return
    check(any(row == battle for row in game.s['battle_reports']), '胜利必须先归档真实战报。')
    metrics = _metrics(battle)
    for key, task in _state(game)['tasks'].items():
        if metrics[key] and battle['battle_id'] not in task['battles'] and battle['battle_id'] not in task['accepted_battle_ids']:
            task['battles'][battle['battle_id']] = dict(expedition=game.s['expedition_no'],
                battle_digest=_digest(battle), events=metrics[key], status='PENDING')
    departure = _departure(game)
    if not departure or game.s.get('mission') != 'ORDINARY':
        return
    binding = battle.get('world_binding') or {}
    sources = [row for row in departure['contract']['sources'].values()
               if row['kind'] in ('G', 'L') and row['region'] == binding.get('region')
               and row['site'] == binding.get('site') and row['encounter_id'] == battle['encounter_id']]
    if not sources:
        return
    check(len(sources) == 1, '一个遭遇不能对应多份书掉落。')
    source = sources[0]
    key = source['key']
    if key in departure['battle_drops']:
        check(departure['battle_drops'][key]['battle_id'] == battle['battle_id'], '掉落来源冲突。')
        return
    check(game.s['region'] == source['region'] and game.s['site'] == source['site'], '胜利现场不一致。')
    departure['battle_drops'][key] = dict(battle_id=battle['battle_id'],
        status='OFFERED' if source['drop'] else 'NO_DROP')
    if source['drop']:
        check(departure['pending_drop'] is None, '上一处未领取掉落须先放弃。')
        departure['pending_drop'] = key
        game.log('book_drop_offered', source=key, battle_id=battle['battle_id'])


def leave_site(game, region=None, site=None):
    departure = _departure(game)
    if not departure or not departure['pending_drop']:
        return
    key = departure['pending_drop']
    source = departure['contract']['sources'][key]
    region = game.s.get('region') if region is None else region
    site = game.s.get('site') if site is None else site
    if source['region'] == region and source['site'] == site:
        departure['battle_drops'][key]['status'] = 'DECLINED'
        departure['pending_drop'] = None
        game.log('book_drop_declined', source=key)


def _claim(game, key, battle_id=None):
    departure = _departure(game)
    check(departure and not departure['settled'], '没有生效的本趟书籍合同。')
    source = departure['contract']['sources'].get(key)
    check(source and source['drop'], '没有这份实际书籍掉落。')
    old = next((row for row in departure['claims'] if row['source'] == key), None)
    if old:
        return deepcopy(old)
    check(len(departure['claims']) < departure['contract']['cap'], '本趟书籍领取额度用完。')
    use_target = departure['contract']['replacement_enabled'] and not any(row['used_target'] for row in departure['claims'])
    book = source['target_id'] if use_target else source['normal_id']
    game.debit({'book_claims': 1})
    row = dict(source=key, book_id=book, normal_id=source['normal_id'], used_target=use_target,
               claim_index=len(departure['claims']), status='CARRIED', battle_id=battle_id)
    departure['claims'].append(row)
    game.log('book_carried', receipt=deepcopy(row))
    return deepcopy(row)


def claim_event(game):
    game.noncombat()
    event, binding, current = game.event_info()
    offer = binding.get('book_offer')
    check(offer and 'source_key' in offer, '这里没有新版手册报价。')
    if current['state'] == 'RESOLVED' and (current.get('receipt') or {}).get('option') == 'BOOK':
        return '本册已领取。'
    check(current['state'] in ('OPEN', 'UNSEEN'), '已经选择其他结果或开始不可切换操作。')
    row = _claim(game, offer['source_key'])
    current.update(state='RESOLVED', receipt=dict(option='BOOK', book_id=row['book_id'], claim_key=row['source']))
    return '已携带' + row['book_id'] + '；安全归城入库，途中不能学习。'


def _choice(state, key, allowed, source):
    row = dict(id=key, allowed=sorted(allowed), selected=None, source=source)
    if key in state['entitlements']:
        check(state['entitlements'][key]['allowed'] == row['allowed'], '自选权益重复来源冲突。')
    else:
        state['entitlements'][key] = row


def first_delivery(game, fact):
    if fact not in DELIVERY_FACTS:
        return
    state = _state(game)
    check(fact in (game.s.get('campaign') or {}).get('facts', {}), '须真实章节首交，预置试验事实不是奖励。')
    if fact in state['deliveries']:
        return
    state['deliveries'][fact] = dict(fact=fact, evidence=_digest(game.s['campaign']['facts'][fact]))
    if fact in BOSS_BOOKS:
        book = BOSS_BOOKS[fact]
        game.s['book_stock'][book] = game.s['book_stock'].get(book, 0) + 1
    else:
        stage = 'B' if fact == 'ST-104' else 'E'
        _choice(state, fact, [bid for bid, row in _books().items() if row['stage'] == stage], fact)
    game.log('book_first_delivery', fact=fact, book=BOSS_BOOKS.get(fact))


def settle(game, safe, reason=None):
    check(type(safe) is bool, '安全结算标志无效。')
    state = _state(game)
    exp = str(game.s['expedition_no'])
    prior = state['settlements'].get(exp)
    if prior:
        check(prior['safe'] == safe, '同趟不能按另一结果结算。')
        return deepcopy(prior)
    departure = _departure(game)
    claims = departure['claims'] if departure else []
    carried = {}
    for row in claims:
        check(row['status'] == 'CARRIED', '书籍已结算。')
        row['status'] = 'BANKED' if safe else 'LOST'
        carried[row['book_id']] = carried.get(row['book_id'], 0) + 1
    if safe:
        for book, count in carried.items():
            game.s['book_stock'][book] = game.s['book_stock'].get(book, 0) + count
    before = state['progress']
    if safe and departure and departure['contract']['target']:
        target = departure['contract']['target']
        state['progress'] = 0 if target in carried else min(2, before + len(claims))
    task_battles = []
    for key, task in state['tasks'].items():
        for bid, row in task['battles'].items():
            if str(row['expedition']) == exp and row['status'] == 'PENDING':
                row['status'] = 'BANKED' if safe else 'LOST'
                task_battles.append([key, bid])
        if sum(row['status'] == 'BANKED' for row in task['battles'].values()) >= 3:
            _choice(state, key, TASKS[key], key)
    result = dict(expedition=game.s['expedition_no'], safe=safe, reason=reason,
                  books=carried, progress_before=before, progress_after=state['progress'], task_battles=sorted(task_battles))
    state['settlements'][exp] = result
    state['target_events'].append(dict(kind='SETTLEMENT', expedition=exp))
    if departure:
        leave_site(game)
        departure['settled'] = deepcopy(result)
    if game.s.get('summary') is not None:
        game.s['summary']['books_banked' if safe else 'books_lost'] = deepcopy(carried)
        game.s['summary']['book_rewards'] = deepcopy(result)
    game.log('books_settled', receipt=deepcopy(result))
    return deepcopy(result)


def public(game):
    state = _state(game)
    departure = _departure(game)
    return dict(target=state['target'], progress=state['progress'],
        entitlements=deepcopy(state['entitlements']), tasks={key: dict(
            banked=sum(row['status'] == 'BANKED' for row in task['battles'].values())) for key, task in state['tasks'].items()},
        carried=[deepcopy(row) for row in (departure or {}).get('claims', []) if row['status'] == 'CARRIED'],
        pending_drop=deepcopy((departure or {}).get('pending_drop')), pending_offer=offer(game))


def offer(game, source_key=None):
    """Expose only an actual won drop or an event at the current location."""
    departure = _departure(game)
    if not departure or departure['settled'] or game.s.get('phase') != 'EXPLORE':
        return None
    key = source_key or departure['pending_drop']
    source = departure['contract']['sources'].get(key)
    if not source or (source['region'], source['site']) != (game.s.get('region'), game.s.get('site')):
        return None
    if source['kind'] != 'BOOK' and (departure['battle_drops'].get(key) or {}).get('status') != 'OFFERED':
        return None
    if source['kind'] == 'BOOK':
        current = game.s.get('regions', {}).get(source['region'], {}).get('events', {}).get(source['site'], {})
        if current.get('state') not in ('OPEN', 'UNSEEN'):
            return None
    use_target = departure['contract']['replacement_enabled'] and not any(row['used_target'] for row in departure['claims'])
    book = source['target_id'] if use_target else source['normal_id']
    remaining = max(0, departure['contract']['cap'] - len(departure['claims']))
    return dict(source=key, book_id=book, name=_books()[book]['name'], can_claim=remaining > 0, remaining_cap=remaining)


def describe(game):
    row = public(game)
    return ('书籍目标：' + str(row['target']) + '，进度' + str(row['progress']) + '/2；'
            + '携书' + str([value['book_id'] for value in row['carried']])
            + '；待领战利书' + str(row['pending_drop'])
            + '；自选权益' + str({key: value['selected'] for key, value in row['entitlements'].items()})
            + '；研习' + str(row['tasks']))


def handle(game, args):
    state = _state(game)
    if not args or args == ['status']:
        return describe(game)
    action = args[0].lower()
    if action in ('claim', 'drop'):
        check(len(args) == 1 and game.s['phase'] == 'EXPLORE', 'book claim/drop：在战后原现场处理。')
        departure = _departure(game)
        key = departure and departure['pending_drop']
        check(key, '没有待领战利书。')
        source = departure['contract']['sources'][key]
        check((source['region'], source['site']) == (game.s['region'], game.s['site']), '已经离开原现场。')
        if action == 'drop':
            leave_site(game)
            return '已放弃未领取书籍。'
        row = _claim(game, key, departure['battle_drops'][key]['battle_id'])
        departure['battle_drops'][key]['status'] = 'CLAIMED'
        departure['pending_drop'] = None
        return '已携带' + row['book_id'] + '；安全归城才入库。'
    check(game.s['phase'] == 'TOWN', '目标、委托与自选奖励需要城镇。')
    if action == 'target':
        check(len(args) == 2, 'book target SB-ID/clear')
        target = None if args[1].lower() == 'clear' else args[1].upper()
        check(target is None or (target in _books() and _books()[target]['stage'] != 'X' and unlocked(game, target)), '只能指定已公开普通书。')
        if target != state['target']:
            state['target'] = target
            state['progress'] = 0
            state['target_events'].append(dict(kind='TARGET', target=target))
        return describe(game)
    if action == 'task':
        check(len(args) in (2, 3), 'book task accept SB-T01/SB-T02/SB-T03；task status')
        if args[1].lower() == 'status':
            return describe(game)
        check(len(args) == 3 and args[1].lower() == 'accept' and args[2].upper() in TASKS, '请选择研习委托。')
        check('ST-104' in _facts(game), '研习需ST-104首次交档。')
        key = args[2].upper()
        if key not in state['tasks']:
            game.log('book_task_accepted', task=key)
            state['tasks'][key] = dict(accepted_sequence=game.s['sequence'],
                accepted_battle_ids=sorted(_all_battles(game)), battles={})
        return describe(game)
    if action == 'choice':
        check(len(args) == 4 and args[-1].upper() == 'CONFIRM', 'book choice 权益ID SB-ID CONFIRM')
        key, book = args[1].upper(), args[2].upper()
        row = state['entitlements'].get(key)
        check(row and book in row['allowed'], '没有该自选权益或不在合法范围。')
        if row['selected']:
            check(row['selected'] == book, '已兑现权益不能换书。')
            return '该权益已兑现，不重复发书。'
        row['selected'] = book
        game.s['book_stock'][book] = game.s['book_stock'].get(book, 0) + 1
        game.log('book_choice', entitlement=key, book=book)
        return '已领取' + book
    raise ValueError('未知技能书获取命令。')


def validate(game):
    state = _state(game)
    check(state['version'] == VERSION, '获取版本不匹配。')
    check(type(state['progress']) is int and 0 <= state['progress'] <= 2, '定向进度无效。')
    check(state['target'] is None or (state['target'] in _books() and _books()[state['target']]['stage'] != 'X'), '定向目标无效。')
    facts = (game.s.get('campaign') or {}).get('facts', {})
    check(set(state['deliveries']) == DELIVERY_FACTS & set(facts), '首次交付回执与真实任务不同步。')
    for key, row in state['deliveries'].items():
        check(row == dict(fact=key, evidence=_digest(facts[key])), '首交来源被改动。')
    battles = _all_battles(game)
    trips = {str(trip['expedition_no']): trip for trip in game.s.get('completed_history', [])}
    trips[str(game.s['expedition_no'])] = game.s
    for key, task in state['tasks'].items():
        check(key in TASKS and type(task['accepted_sequence']) is int and task['accepted_sequence'] >= 0, '研习委托无效。')
        check(any(row.get('seq') == task['accepted_sequence'] and row.get('type') == 'book_task_accepted'
                  and row.get('task') == key for row in game.s.get('journal', [])), '研习缺少实际接取回执。')
        for bid, row in task['battles'].items():
            battle = battles.get(bid)
            check(bid not in task['accepted_battle_ids'] and battle and battle['result'] == 'VICTORY' and not battle.get('debug_tainted'), '研习缺少接取后的真实胜利。')
            check(row['battle_digest'] == _digest(battle) and row['events'] == _metrics(battle)[key] and row['events'], '研习效果凭据不一致。')
            settlement = state['settlements'].get(str(row['expedition']))
            check(row['status'] == ('BANKED' if settlement['safe'] else 'LOST') if settlement else row['status'] == 'PENDING', '研习带回状态无效。')
    for key, row in state['entitlements'].items():
        allowed = (TASKS[key] if key in TASKS else [bid for bid, book in _books().items()
                   if book['stage'] == ('B' if key == 'ST-104' else 'E')])
        if key in TASKS:
            check(key in state['tasks'] and sum(r['status'] == 'BANKED' for r in state['tasks'][key]['battles'].values()) >= 3, '研习权益缺少三场安全胜利。')
        else:
            check(key in ('ST-104', 'ST-303') and key in state['deliveries'], '自选权益来源不存在。')
        check(row == dict(id=key, allowed=sorted(allowed), selected=row['selected'], source=key)
              and (row['selected'] is None or row['selected'] in allowed), '自选权益内容无效。')
    expected_entitlements = (set(state['deliveries']) & {'ST-104', 'ST-303'}) | {
        key for key, task in state['tasks'].items() if sum(row['status'] == 'BANKED' for row in task['battles'].values()) >= 3}
    check(set(state['entitlements']) == expected_entitlements, '自选权益缺失或多发。')
    for exp, departure in state['departures'].items():
        contract = departure['contract']
        check(str(contract['expedition']) == exp and contract['game_id'] == game.s['id'], '出发来源无效。')
        check(contract['target'] is None or contract['target'] in _ordinary_ids(contract['facts']), '出发目标未公开。')
        trip = trips.get(exp)
        check(trip and trip.get('manifest') and trip['manifest'].get('book_rewards') == contract, '缺少真实当前或历史出发合同。')
        check(trip['manifest']['caps']['book_claims'] == contract['cap'], '当前或历史书额度被改动。')
        check(departure['manifest_source'] == _manifest_source(trip['manifest']), '出发输入与真实冻结地图不一致。')
        expected = _contract(game.cat, departure['manifest_source'], contract['seed'], contract['facts'],
                             contract['target'], contract['progress'], contract['expedition'], game.s['id'])
        check(contract == expected, '冻结掉落或目标合同被改动。')
        claims = departure['claims']
        check(trip.get('debits', {}).get('book_claims', 0) == len(claims), '历史书额度与领取不同步。')
        check(len(claims) <= contract['cap'] and len({row['source'] for row in claims}) == len(claims), '重复领取或超过额度。')
        for index, row in enumerate(claims):
            source = contract['sources'].get(row['source'])
            use_target = bool(contract['replacement_enabled'] and index == 0)
            check(source and source['drop'] and row['claim_index'] == index and row['used_target'] == use_target, '领取来源或一次替换权不一致。')
            check(row['normal_id'] == source['normal_id'] and row['book_id'] == (source['target_id'] if use_target else source['normal_id']), '领取书与冻结报价不一致。')
            check(row['status'] == ('BANKED' if departure['settled']['safe'] else 'LOST') if departure['settled'] else row['status'] == 'CARRIED', '携书结算状态无效。')
            if source['kind'] != 'BOOK':
                check(row['source'] in departure['battle_drops'] and departure['battle_drops'][row['source']]['status'] == 'CLAIMED', '胜利书缺少领取回执。')
                check(row['battle_id'] == departure['battle_drops'][row['source']]['battle_id'], '领取战报ID被替换。')
            else:
                event = trip.get('regions', {}).get(source['region'], {}).get('events', {}).get(source['site'], {})
                check(event.get('state') == 'RESOLVED' and event.get('receipt') == dict(
                    option='BOOK', book_id=row['book_id'], claim_key=row['source']), '事件携书缺少真实互斥选择。')
        for key, row in departure['battle_drops'].items():
            source = contract['sources'].get(key)
            battle = battles.get(row['battle_id'])
            check(source and source['kind'] in ('G', 'L') and battle and battle['result'] == 'VICTORY' and not battle.get('debug_tainted'), '掉落缺少真实胜利来源。')
            binding = battle.get('world_binding') or {}
            check(binding.get('region') == source['region'] and binding.get('site') == source['site'] and battle['encounter_id'] == source['encounter_id'], '掉落战报现场不一致。')
            check(row['status'] in (('OFFERED', 'DECLINED', 'CLAIMED') if source['drop'] else ('NO_DROP',)), '掉落状态不合法。')
            check((row['status'] == 'CLAIMED') == any(claim['source'] == key for claim in claims), '掉落与领取回执不同步。')
        expected_drops = set()
        for source in contract['sources'].values():
            if source['kind'] in ('G', 'L'):
                matches = [battle for battle in trip.get('battle_reports', []) if battle.get('result') == 'VICTORY'
                           and not battle.get('debug_tainted') and battle.get('encounter_id') == source['encounter_id']
                           and (battle.get('world_binding') or {}).get('region') == source['region']
                           and (battle.get('world_binding') or {}).get('site') == source['site']]
                check(len(matches) <= 1, '同一冻结遭遇出现多份胜利。')
                if matches:
                    expected_drops.add(source['key'])
            else:
                receipt = trip.get('regions', {}).get(source['region'], {}).get('events', {}).get(source['site'], {}).get('receipt') or {}
                check((receipt.get('option') == 'BOOK') == any(row['source'] == source['key'] for row in claims), '事件互斥选择与领取不同步。')
        check(set(departure['battle_drops']) == expected_drops, '真实胜利与掉落记录不同步。')
        pending = departure['pending_drop']
        offered = [key for key, row in departure['battle_drops'].items() if row['status'] == 'OFFERED']
        check(offered == ([pending] if pending else []), '待领取书籍与现场不同步。')
        if departure['settled']:
            check(departure['settled'] == state['settlements'].get(exp), '书籍结算回执不一致。')
        elif exp == str(game.s['expedition_no']):
            check(game.s['manifest'] and game.s['manifest'].get('book_rewards') == contract, '实际远征缺少冻结合同。')
            check(game.s['debits'].get('book_claims', 0) == len(claims), '原书额度与真实领取不同步。')
    target = None
    progress = 0
    seen_departures, seen_settlements = set(), set()
    for event in state['target_events']:
        if event['kind'] == 'TARGET':
            check(event['target'] != target and (event['target'] is None or event['target'] in _books()
                  and _books()[event['target']]['stage'] != 'X'), '切换目标凭据无效。')
            target, progress = event['target'], 0
        elif event['kind'] == 'DEPARTURE':
            exp = event['expedition']
            check(exp not in seen_departures and exp in state['departures'], '出发定向记录重复或缺失。')
            contract = state['departures'][exp]['contract']
            check((contract['target'], contract['progress']) == (target, progress), '冻结进度与公开历史不同步。')
            seen_departures.add(exp)
        else:
            check(event['kind'] == 'SETTLEMENT', '定向历史种类无效。')
            exp = event['expedition']
            check(exp not in seen_settlements and exp in state['settlements'], '结算记录重复或缺失。')
            row = state['settlements'][exp]
            departure = state['departures'].get(exp)
            claims = departure['claims'] if departure else []
            counts = {}
            for claim in claims:
                counts[claim['book_id']] = counts.get(claim['book_id'], 0) + 1
            after = (0 if target in counts else min(2, progress + len(claims))) if row['safe'] and departure and target else progress
            check(row['expedition'] == int(exp) and row['progress_before'] == progress
                  and row['progress_after'] == after and row['books'] == counts, '目标优先结算或携书数量被改动。')
            progress = after
            seen_settlements.add(exp)
    check(seen_departures == set(state['departures']) and seen_settlements == set(state['settlements'])
          and (state['target'], state['progress']) == (target, progress), '定向历史／现态不一致。')
