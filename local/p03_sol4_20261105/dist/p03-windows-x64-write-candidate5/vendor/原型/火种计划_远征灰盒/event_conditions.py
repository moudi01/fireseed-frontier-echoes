"""Six ordinary-event alternatives and their source-bound journey conditions.

Event selection/payment/RESOLVED receipts remain owned by engine.Game.execute.
This module changes neither the sampled event pool nor the three plan slots.
"""
from copy import deepcopy
import hashlib
import json

VERSION = 'JOURNEY-CONDITIONS-0.66'

SPECS = {
    'FIT': dict(event='EV30', name='束带整备', family='ward', scope='battles',
                positive={'opening_shield_per_cost': 2}, negative={}, battles=2),
    'TREAT': dict(event='EV54', name='全队简易敷治'),
    'SHARP': dict(event='EV39', name='锐刃承压', family='edge', scope='journey',
                  positive={'direct_damage_increase': .08},
                  negative={'incoming_increase': .08}),
    'CLEANSE': dict(event='EV36', name='解除一组负担'),
    'HAUL': dict(event='EV55', name='整捆负重', family='burden', scope='region',
                 positive={}, negative={'incoming_increase': .10}),
    'RUSH': dict(event='EV59', name='双封急磨', family='edge', scope='battles',
                 positive={'direct_damage_increase': .20},
                 negative={'incoming_increase': .20}, battles=2),
}
EVENT_CHOICES = {spec['event']: choice for choice, spec in SPECS.items()}
CONDITIONS = {key for key, spec in SPECS.items() if 'family' in spec} | {'ROGUE'}
ITEM_CHOICES = {'CO11': 'FIT', 'CO12': 'RUSH'}

SUMMARIES = {
    'FIT': ('支付随身铁2、纤维1与已入库铜3（原PRIMARY制作费用），制作CO11两战护片包，'
            '须有空携行格；不附送原护片，不增加拾获成品额度。不会立即生效，'
            '战外use CO11后从下一场完整战斗起，最多2场每名实际上阵者开场获得'
            '2×本人Cost私盾（士兵2／佣兵4／英雄8／伴兽2）。使用后占格至本趟结算；'
            '未用成品可正常入库留待下趟，已用剩余战数不跨返城。不回血、不复起；'
            '纯正面不能CLEANSE，同护持系有效时不能重复使用。'),
    'TREAT': ('支付随身草药1，扣本趟休整额度1；全队站立随行者'
              '各恢复3×本人Cost生命（士兵3／佣兵6／英雄12／伴兽3），按现有恢复削减计算，'
              '不超上限、不复起、不解除伤势或侵蚀，不触发英雄主动治疗被动。'
              '全队无正数恢复不支付、不扣额度；不领取材料或成品、不占携行格，'
              '关闭本卡单人20%恢复与侵蚀减5等其他结果。'),
    'SHARP': ('支付随身铁1、草药1、纤维1与已入库铜3（原PRIMARY制作费用）；'
              '不制作或领取锐刃油、不占携行格。本趟全体实际上阵队员直接伤害一般增伤+8%，'
              '同时承伤×1.08；正负绑定一整组，刃系不可叠加或刷新，'
              '仅EV36或边界营地可按对应机会整组解除，返城或败战到期。不复起、不刷新技能。'),
    'CLEANSE': ('不收铜或材料；支付本趟休整额度1，指定一个'
                '当前仍有效且带负面的条件实例ID，整组移除其正面和负面。'
                '无可清理负面拒绝；不回收已兑现的材料、不返还急磨占用的携行格、'
                '不补技能次数、不复起、不解除伤势或侵蚀。关闭本卡原制作或材料结果。'),
    'HAUL': ('无即时铜、材料或生命支付；按原PRIMARY真实领取4单位本区材料，'
             '扣材料额度4，替代原指定一人损失10%生命。'
             '代价是本区全队承伤×1.10；G已清不能领取。跨区自动到期，或经EV36'
             '消耗休整额度、边界营地消耗营地机会整组解除，已领材料不回滚。'
             '不占携行格、不复起。'),
    'RUSH': ('无即时铜或材料支付；扣本趟材料额度2及'
             '拾获成品额度1，领取CO12两战急磨包，须有空携行格，'
             '不附送原油或粉，不会立即生效。战外use CO12后，从下一场完整战斗起最多2场，'
             '全体实际上阵队员直接伤害一般增伤+20%，同时承伤×1.20。'
             '刃系不可叠加或刷新，正负只能经EV36或边界营地整组解除。'
             '使用后占格至本趟结算，到期或清理也不退格；未用成品可正常入库留待下趟。'
             '不复起、不刷新技能；战内不可用，野外已无后续战斗不能使用。'),
}
ITEM_SUMMARIES = {
    'CO11': ('战外use CO11消耗携行的一份护片包，不再支付材料或铜；使用后占1格至本趟结算。'
             '城内先预备，下一场真实战斗才生效；未来最多2场，每位实际出战者开场获得'
             '2×本人Cost私盾（士兵2／佣兵4／英雄8／伴兽2）。同护持系不能叠加或刷新，'
             '纯正面不可清理；不回血、不复起、不刷新技能。未用包可入库跨趟，'
             '已用效果在返城、败战或终局结束时到期。'),
    'CO12': ('战外use CO12消耗携行的一份急磨包，不再支付材料或铜；使用后占1格至本趟结算，'
             '到期或清理也不提前退格。城内先预备，下一场真实战斗才生效；未来最多2场，'
             '全体实际上阵者直接伤害一般增伤+20%，同时承伤×1.20。与锐刃承压同属刃系，'
             '不可叠加、覆盖或刷新；只能按EV36或边界营地机会整组解除。'
             '不复起、不刷新技能。未用包可入库跨趟，已用效果不跨本趟结算。'),
}


def check(ok, message):
    if not ok:
        raise ValueError(message)


def initialize(game):
    game.s.setdefault('journey_conditions', dict(version=VERSION, next_id=1,
        records=[], settled_battles=[]))


def state(game):
    check('journey_conditions' in game.s, '本档未初始化单趟条件。')
    return game.s['journey_conditions']


def install(cat):
    """Append one deep-copied PRIMARY alternative; originals stay untouched."""
    for item, choice in ITEM_CHOICES.items():
        cat.items[item] = dict(consumable_id=item,
            name='两战护片包' if choice == 'FIT' else '两战急磨包',
            effect=dict(type='journey_condition_consumable', choice=choice),
            sell_copper=0, use_count_per_item=1, can_use_in_town=True,
            can_use_any_noncombat_route_state=True, can_use_in_battle_or_paused_battle=False,
            action_days=0, mechanical_summary=ITEM_SUMMARIES[item])
    for event_id, choice in EVENT_CHOICES.items():
        original = cat.events[event_id]
        check(original['type'] != 'humanity', '条件选项不能覆盖人性事件。')
        if any(o['option_id'] == choice for o in original['options']):
            continue
        event = deepcopy(original)
        parent = next(o for o in event['options'] if o['option_id'] == 'PRIMARY')
        option = deepcopy(parent)
        option.update(option_id=choice, label=SPECS[choice]['name'],
            effects=[dict(type='journey_choice', choice=choice)],
            mechanical_summary=SUMMARIES[choice], result_text=SUMMARIES[choice],
            journey_choice=choice, journey_parent_option='PRIMARY',
            journey_version=VERSION,
            requires='ordinary_noncombat; real_cost_target_budget_and_bound_condition_rules',
            opportunity_cost='互斥关闭整张事件；不附送原制作物或其他选项奖励')
        # The inherited bundle reference remains a sampling/preview reference.
        # Only journey_choice executes; it never also grants the original item.
        if choice == 'TREAT':
            option['costs'] = {'carried_materials': {'herb': 1}}
        elif choice == 'CLEANSE':
            option['costs'] = {}
        index = next((i for i, o in enumerate(event['options'])
                      if o['option_id'] == 'PASS'), len(event['options']))
        event['options'].insert(index, option)
        cat.events[event_id] = event


def bind(cat, manifest):
    """Expose only alternatives whose original PRIMARY was already enabled."""
    enabled = []
    for region_id, region in manifest.get('regions', {}).items():
        for site, binding in region.get('events', {}).items():
            choice = EVENT_CHOICES.get(binding['event_id'])
            if not choice:
                continue
            parent_enabled = 'PRIMARY' in binding['enabled_options']
            metadata = dict(version=VERSION, choice=choice, parent='PRIMARY',
                            parent_enabled=parent_enabled)
            binding['journey_choice'] = metadata
            if parent_enabled:
                if choice not in binding['enabled_options']:
                    binding['enabled_options'].append(choice)
                binding.get('disabled_options', {}).pop(choice, None)
                enabled.append(dict(region=region_id, site=site,
                                    event=binding['event_id'], choice=choice))
            else:
                binding.setdefault('disabled_options', {})[choice] = \
                    '原PRIMARY未启用，新增替代选项同步禁用。'
    manifest['journey_conditions'] = dict(version=VERSION, enabled=enabled)


def _active(game):
    expedition = game.s['expedition_no']
    return [r for r in state(game)['records'] if r['status'] in ('ACTIVE', 'READY')
            and r['source']['expedition'] == expedition
            and (r['duration']['kind'] != 'region'
                 or r['source']['region'] == game.s.get('region'))]


def remaining_mandatory_battles(game):
    if game.s.get('mission') != 'ORDINARY' or not game.s.get('manifest'):
        return 0
    manifest = game.s['manifest']
    current = sum(slot in game.manifest_region['encounters']
                  and slot not in game.current['cleared']
                  for slot in ('B1', 'B2', 'G'))
    total = game.cat.multi['profiles'][manifest['profile']]['region_count']
    future_regions = max(0, total-len(game.s['visited_regions']))
    return current + 3*future_regions


def _budget_ready(game, debits):
    names = {'material_units': '材料额度', 'event_recovery_claims': '休整额度',
             'event_found_consumable_claims': '拾获成品额度'}
    for key, amount in debits.items():
        check(game.s['debits'].get(key, 0)+amount
              <= game.s['manifest']['caps'].get(key, 0), '本趟'+names.get(key, key)+'不足。')


def _source(game, choice):
    check(game.s.get('mission') == 'ORDINARY' and game.s['phase'] == 'EXPLORE',
          '单趟条件只用于普通远征的非战斗事件。')
    event, binding, row = game.event_info()
    check(event['event_id'] == SPECS[choice]['event'], '本事件没有这个条件选项。')
    check(row['state'] not in ('RESOLVED', 'DECLINED'), '事件已关闭。')
    check(choice in binding['enabled_options'], '本趟没有启用该替代选项。')
    return dict(kind='event', expedition=game.s['expedition_no'], region=game.s['region'],
                site=game.s['site'], event=event['event_id'], option=choice)


def _new(game, choice, source, ready=False):
    data = state(game); spec = SPECS[choice]
    number = data['next_id']; data['next_id'] += 1
    row = dict(id=f'JC-{number:06d}', choice=choice, name=spec['name'],
        family=spec['family'], status='READY' if ready else 'ACTIVE', source=deepcopy(source),
        duration=dict(kind=spec['scope'], initial=spec.get('battles'),
                      remaining=spec.get('battles')),
        positive=deepcopy(spec['positive']), negative=deepcopy(spec['negative']),
        battles=[], ended_reason=None,
        prep_slot_reserved=source.get('kind') == 'consumable',
        prep_slot_held=source.get('kind') == 'consumable')
    data['records'].append(row)
    game.log('journey_condition_acquired', condition=deepcopy(row))
    return row


def _end(game, row, reason, status='EXPIRED'):
    row.update(status=status, ended_reason=reason,
               ended_expedition=game.s['expedition_no'], ended_region=game.s.get('region'))
    game.log('journey_condition_ended', condition_id=row['id'], choice=row['choice'],
             status=status, reason=reason)


def acquire_rogue(game, template_id, source):
    """Apply one catalogued journey pact; replacements remove the whole old pact."""
    import rogue_events
    check(game.s.get('mission') == 'ORDINARY' and game.s['phase'] == 'EXPLORE',
          '行军约定只在普通远征事件中取得。')
    spec = rogue_events.get_spec(template_id)
    check(source.get('kind') == 'rogue_event' and source.get('template_id') == template_id,
          '行军约定缺少冻结来源。')
    for previous in _active(game):
        if previous['family'] == 'fortune':
            _end(game, previous, 'REPLACED_BY_FORTUNE')
    data = state(game); number = data['next_id']; data['next_id'] += 1
    row = dict(id=f'JC-{number:06d}', choice='ROGUE', template_id=template_id,
        name=spec['name'], family='fortune', status='ACTIVE', source=deepcopy(source),
        duration=dict(kind='journey', initial=None, remaining=None),
        positive=deepcopy(spec['positive']), negative=deepcopy(spec['negative']),
        battles=[], ended_reason=None, prep_slot_reserved=False, prep_slot_held=False)
    data['records'].append(row)
    game.log('journey_condition_acquired', condition=deepcopy(row))
    return deepcopy(row)


def has_negative(row):
    return any(value > 0 for value in row.get('negative', {}).values())


def choose(game, choice, target='01'):
    """Called inside Game.execute after the option's ordinary costs were paid."""
    choice = choice.upper()
    check(choice in SPECS, '未知单趟条件选项。')
    source = _source(game, choice)
    if choice == 'SHARP':
        check(remaining_mandatory_battles(game) > 0, '本趟已无后续必经战，不能领取强化。')
    if choice in ('SHARP', 'HAUL'):
        spec = SPECS[choice]
        check(not any(r['family'] == spec['family'] for r in _active(game)),
              '同族条件仍有效，不能叠加、覆盖或刷新；需先整组解除或正常到期。')
        check(not any(r['source'] == source for r in state(game)['records']),
              '该事件的条件已经取得，不能重复领取。')
    if choice == 'TREAT':
        _budget_ready(game, {'event_recovery_claims': 1})
        receipts = []
        for member in game.s['party']:
            if member['hp'] > 0:
                receipts.extend(game.heal([member], amount=3*member['cost']))
        check(receipts, '全队没有实际正数恢复，不消耗本次休整。')
        game.debit({'event_recovery_claims': 1})
        game.log('journey_event_treatment', source=source, effective_heal=receipts)
        return receipts
    if choice == 'CLEANSE':
        return cleanse(game, target, 'EVENT')
    if choice == 'HAUL':
        check('G' not in game.current['cleared'], '本区G已清，不能在出口白领负重材料。')
        parent = next(o for o in game.cat.events['EV55']['options']
                      if o['option_id'] == 'PRIMARY')
        claim = next(e for e in parent['effects'] if e['type'] == 'claim_reward')
        _budget_ready(game, game.cat.bundles[claim['bundle_id']]['budget_debits'])
        # Use the real existing regional material reward and budget debit.
        context = deepcopy(parent); context['option_id'] = choice
        game.grant(claim['bundle_id'], context)
    elif choice in ('FIT', 'RUSH'):
        check(len(game.s['pouch'])+game.s['used_prep_slots'] < 4,
              '携行格已满，成品需要一个空位。')
        if choice == 'RUSH':
            debit = {'material_units': 2, 'event_found_consumable_claims': 1}
            _budget_ready(game, debit); game.debit(debit)
        item = next(item for item, effect in ITEM_CHOICES.items() if effect == choice)
        game.s['pouch'].append(item)
        game.log('journey_condition_item_received', source=source, item=item)
        return {'item': item, 'choice': choice, 'activated': False}
    return deepcopy(_new(game, choice, source))


def _eligible(game):
    return [r for r in _active(game) if game.s.get('mission') == 'ORDINARY'
            or r['source'].get('kind') == 'consumable']


def _item_future(game):
    if game.s.get('mission') == 'ORDINARY':
        if not game.s.get('manifest'):
            return 0
        current = sum(slot not in game.current['cleared']
                      for slot in game.manifest_region['encounters'])
        total = game.cat.multi['profiles'][game.s['manifest']['profile']]['region_count']
        return current+3*max(0, total-len(game.s['visited_regions']))
    # Existing fixed exploration missions expose their own remaining encounters.
    # Finale preparation/intermission uses its existing commands, not battle use.
    if game.s.get('manifest') and game.s.get('region'):
        return sum(slot not in game.current['cleared']
                   for slot in game.manifest_region.get('encounters', {}))
    return 0


def use_item(game, item):
    """Use a real carried package; only the next full battle activates READY."""
    item = item.upper()
    check(item in ITEM_CHOICES, '不是单趟条件消耗品。')
    check(game.s['phase'] in ('TOWN', 'EXPLORE'), '只能在城内或远征战外使用，战斗或暂停中不可用。')
    check(item in game.s['pouch'], '没有实际携带这份成品。')
    choice = ITEM_CHOICES[item]; spec = SPECS[choice]
    check(not any(r['family'] == spec['family'] for r in _active(game)),
          '同族条件已预备或仍有效，不能叠加、刷新或覆盖；未消耗成品。')
    if game.s['phase'] == 'EXPLORE':
        check(_item_future(game) > 0, '本趟已无后续战斗，不能使用强化成品。')
    town = game.s['phase'] == 'TOWN'
    source = dict(kind='consumable', item=item, expedition=game.s['expedition_no'],
                  region='TOWN' if town else game.s.get('region'),
                  site='TOWN' if town else game.s.get('site'), event=None, option='USE')
    game.s['pouch'].remove(item)
    game.s['used_prep_slots'] += 1
    row = _new(game, choice, source, ready=town)
    game.log('journey_condition_item_used', item=item, condition_id=row['id'],
             reserved_slot=True, first_battle_pending=town)
    return deepcopy(row)


def cleanse(game, target, source='EVENT'):
    """Only the existing event alternative or an unused boundary camp calls this."""
    check(source in ('EVENT', 'CAMP'), '清理须来自事件或边界营地。')
    check(game.s.get('mission') == 'ORDINARY' and game.s['phase'] == 'EXPLORE',
          '仅普通远征非战斗状态可处理条件。')
    if source == 'EVENT':
        origin = _source(game, 'CLEANSE')
        _budget_ready(game, {'event_recovery_claims': 1})
    else:
        check(game.s['site'] == 'X' and 'G' in game.current['cleared']
              and not game.current['camp_used']
              and len(game.s['visited_regions']) < game.cat.multi['profiles'][
                  game.s['manifest']['profile']]['region_count'],
              '需在非末区已完成目标的出口，使用未用营地机会。')
        origin = dict(expedition=game.s['expedition_no'], region=game.s['region'],
                      site=game.s['site'], event=None, option='CAMP_CLEANSE')
    row = next((r for r in _active(game) if r['id'] == target and has_negative(r)), None)
    check(row is not None, '须指定当前有效且带负面的条件实例ID；没有可清理负面。')
    if source == 'EVENT':
        game.debit({'event_recovery_claims': 1})
    else:
        game.current['camp_used'] = True
    _end(game, row, source+'_CLEANSE', 'CLEANSED')
    row['cleansed_source'] = origin
    return deepcopy(row)


def _totals(records):
    values = dict(direct_damage_increase=0, incoming_increase=0, opening_shield_per_cost=0)
    for row in records:
        for effects in (row['positive'], row['negative']):
            for key, value in effects.items():
                values[key] = round(values.get(key, 0)+value, 10)
    return values


def _battle_id(base, context, records):
    if not records:
        return base
    payload = [VERSION, base, context, records]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False,
                                    sort_keys=True).encode()).hexdigest()[:24]


def start_battle(game, battle):
    previous = battle.get('journey_conditions')
    if previous is not None and previous.get('battle_id') == battle['battle_id']:
        return
    # The administrator stage copies the previous real actors and their clocks.
    # Only metadata is replaced; existing HP/shields/uses stay intact.
    battle.pop('journey_conditions', None)
    for actor in battle['actors']:
        actor.pop('journey_conditions', None)
    eligible = _eligible(game)
    for row in eligible:
        if row['status'] == 'READY':
            row['status'] = 'ACTIVE'
            game.log('journey_condition_activated', condition_id=row['id'])
    records = deepcopy(eligible)
    context = dict(expedition=game.s['expedition_no'],
                   region=game.s.get('region'), site=game.s.get('site'), started_tick=battle['tick'])
    base = battle['battle_id']; battle['battle_id'] = _battle_id(base, context, records)
    key = ':'.join(str(context[k]) for k in ('expedition', 'region', 'site'))+':'+battle['battle_id']
    frozen = dict(version=VERSION, base_battle_id=base, battle_id=battle['battle_id'],
                  context=context, started_tick=battle['tick'], records=records, condition_ids=[r['id'] for r in records],
                  settlement_key=key)
    battle['journey_conditions'] = frozen
    if not records:
        return
    total = _totals(records)
    for actor in battle['actors']:
        if actor['side'] != 'player':
            continue
        amount = total['opening_shield_per_cost']*actor['cost']
        actor['journey_conditions'] = dict(version=VERSION, battle_id=battle['battle_id'],
            records=deepcopy(records), condition_ids=frozen['condition_ids'][:], started_tick=frozen['started_tick'],
            opening_shield=amount, **total)
        if amount:
            actor['shield'] += amount
            battle['events'].append(dict(tick=battle['tick'], type='journey_condition_shield',
                event_id=battle['battle_id']+':journey-shield:'+actor['id'],
                actor=actor['id'], amount=amount, cost=actor['cost'],
                condition_ids=frozen['condition_ids'][:]))
    battle['events'].append(dict(tick=battle['tick'], type='journey_conditions_frozen',
        event_id=battle['battle_id']+':journey-freeze',
        condition_ids=frozen['condition_ids'][:], **total))


def finish_battle(game, battle):
    if not battle.get('result'):
        return
    frozen = battle.get('journey_conditions')
    if not frozen:
        return
    data = state(game); key = frozen['settlement_key']
    if key in data['settled_battles']:
        return
    rows = {r['id']: r for r in data['records']}
    for snap in frozen['records']:
        row = rows.get(snap['id'])
        check(row is not None, '战斗冻结的条件来源已丢失。')
        if row['duration']['kind'] == 'battles':
            check(row['status'] == 'ACTIVE' and row['duration']['remaining'] > 0,
                  '条件次数与战斗冻结状态不符。')
            row['duration']['remaining'] -= 1
            row['battles'].append(key)
            if row['duration']['remaining'] == 0:
                _end(game, row, 'BATTLES_SPENT')
    data['settled_battles'].append(key)
    game.log('journey_conditions_battle_settled', battle_id=battle['battle_id'],
             settlement_key=key, condition_ids=frozen['condition_ids'][:])


def enter_region(game, region_id):
    for row in state(game)['records']:
        if (row['status'] == 'ACTIVE' and row['duration']['kind'] == 'region'
                and row['source']['region'] != region_id):
            _end(game, row, 'REGION_LEFT')


def settle(game, reason):
    data = state(game)
    for row in data['records']:
        if row['status'] in ('ACTIVE', 'READY'):
            _end(game, row, 'SETTLEMENT:'+str(reason))
        row['prep_slot_held'] = False
    return deepcopy([r for r in data['records']
                     if r['source']['expedition'] == game.s['expedition_no']])


def _values(actor):
    return actor.get('journey_conditions', {}) if actor.get('side') == 'player' else {}


def _hit_distance(actor, origin, hit_cell, victim):
    if origin is None:origin = actor.get('pos')
    if hit_cell is None and victim is not None:hit_cell = victim.get('pos')
    if origin is None or hit_cell is None:return None
    q, r = origin[0]-hit_cell[0], origin[1]-hit_cell[1]
    return max(abs(q), abs(r), abs(q+r))


def increase(actor, action=None, victim=None, tick=0, origin=None, hit_cell=None):
    if actor.get('side') != 'player':
        return 0
    values = _values(actor); total = values.get('direct_damage_increase', 0)
    dtype = (action or {}).get('damage_type')
    if dtype:total += values.get(dtype+'_damage_increase', 0)
    if 1 <= tick-values.get('started_tick', 0) <= 6:total += values.get('early_damage_increase', 0)
    if victim and victim.get('stats', {}).get('hp', 0) > 0 and victim['hp']*2 <= victim['stats']['hp']:
        total += values.get('execute_damage_increase', 0)
    distance = _hit_distance(actor, origin, hit_cell, victim)
    if distance is not None and distance >= 3:total += values.get('ranged_damage_increase', 0)
    return min(1., max(0., total))


def outgoing_factor(actor, action, victim, tick, origin=None, hit_cell=None):
    values = _values(actor); penalty = values.get('direct_damage_penalty', 0)
    dtype = action.get('damage_type')
    if dtype:penalty += values.get(dtype+'_damage_penalty', 0)
    if victim.get('stats', {}).get('hp', 0) > 0 and victim['hp']*2 > victim['stats']['hp']:
        penalty += values.get('healthy_damage_penalty', 0)
    distance = _hit_distance(actor, origin, hit_cell, victim)
    if distance is not None and distance <= 1:penalty += values.get('near_damage_penalty', 0)
    return round(1-min(.75, max(0., penalty)), 10)


def incoming_factor(actor, tick=0):
    if actor.get('side') != 'player':
        return 1
    values = _values(actor); increase = values.get('incoming_increase', 0)
    if tick-values.get('started_tick', 0) > 6:increase += values.get('late_incoming_increase', 0)
    moved = actor.get('last_moved_tick', 0)
    if moved > 0 and tick == moved+1:increase += values.get('moved_incoming_increase', 0)
    from fortune_mechanics import incoming_extra
    increase+=incoming_extra(actor,tick)
    return round(1+max(0., increase), 10)


def damage_reduction(actor, tick=0):
    """F04/R04 use actual unmoved time, independently of action preparation.

    The old ``stationary`` counter is intentionally reset by starting a skill.
    Movement timestamps cover walking, flashes and forced displacement; a new
    battle's frozen clock and a revival's active_from start a fresh two-tick
    wait even when the actor keeps its previous movement timestamp.
    """
    values = _values(actor)
    active_from = actor.get('active_from', 1)
    if actor.get('hp', 1) <= 0 or tick < active_from:
        return 0
    since = max(values.get('started_tick', 0), actor.get('last_moved_tick', 0),
                active_from-1)
    return values.get('stationary_reduction', 0) if tick-since >= 2 else 0


def active_heal(actor, amount):
    basis = round(_values(actor).get('active_heal_increase', 0)*10000)
    return amount*(10000+basis)//10000


def public(game):
    data = state(game); active = deepcopy(_active(game))
    return dict(version=VERSION, records=deepcopy(data['records']), active=active,
        cleansable=[r for r in active if has_negative(r)],
        remaining_mandatory_battles=remaining_mandatory_battles(game))


def describe(game):
    active = _active(game)
    if not active:
        return ('当前没有有效单趟条件；与三方案槽独立，plan clear/undo不清条件。'
                '边界可用camp CLEANSE 条件ID，替代同一次营地恢复。')
    lines = ['单趟条件（与方案槽独立，正负绑定；EV36或camp CLEANSE 条件ID整组清理；'
             '营地清理替代30%生命恢复和侵蚀−15）：']
    for row in active:
        duration = row['duration']
        end = (f"{'已预备，首场起算；' if row['status'] == 'READY' else ''}余{duration['remaining']}场" if duration['kind'] == 'battles'
               else '离开本区到期' if duration['kind'] == 'region' else '本趟结算到期')
        effects = []
        if row['choice'] == 'ROGUE':
            import rogue_events
            effects.append(rogue_events.describe_template(row['template_id']))
        if row['positive'].get('opening_shield_per_cost'):
            effects.append(f"每场开场私盾{row['positive']['opening_shield_per_cost']:g}×本人Cost")
        if row['positive'].get('direct_damage_increase'):
            effects.append(f"直接伤害+{row['positive']['direct_damage_increase']*100:g}%")
        if row['negative'].get('incoming_increase'):
            effects.append(f"承伤+{row['negative']['incoming_increase']*100:g}%")
        if row['prep_slot_held']:
            effects.append('已用携行格1，结算才释放')
        lines.append(row['id']+' '+row['name']+' '+end+'；'+'／'.join(effects))
    return '\n'.join(lines)


def validate(game):
    data = state(game)
    check(data.get('version') == VERSION and type(data.get('next_id')) is int
          and data['next_id'] >= 1, '单趟条件版本或序号无效。')
    records = data.get('records'); settled = data.get('settled_battles')
    check(isinstance(records, list) and isinstance(settled, list)
          and all(isinstance(x, str) and x for x in settled)
          and len(settled) == len(set(settled)), '条件历史或战斗结算去重无效。')
    ids = set(); numbers = []; families = set(); held = 0
    for row in records:
        choice = row.get('choice'); check(choice in CONDITIONS, '条件类型无效。')
        if choice == 'ROGUE':
            import rogue_events
            spec = rogue_events.get_spec(row.get('template_id'))
            rogue_events.validate_condition_source(game,row)
        else:spec = SPECS[choice]
        rid = row.get('id', '')
        check(isinstance(rid, str) and rid.startswith('JC-') and rid[3:].isdigit()
              and rid not in ids, '条件实例ID重复或无效。')
        ids.add(rid); numbers.append(int(rid[3:]))
        check(row.get('family') == spec['family'] and row.get('name') == spec['name']
              and row.get('positive') == spec['positive'] and row.get('negative') == spec['negative'],
              '条件效果或同族来源被改写。')
        source = row.get('source', {})
        check(type(source.get('expedition')) is int and 1 <= source['expedition'] <= game.s['expedition_no'],
              '条件趟次来源无效。')
        item_source = source.get('kind') == 'consumable'
        if item_source:
            check(ITEM_CHOICES.get(source.get('item')) == choice and source.get('event') is None
                  and source.get('option') == 'USE'
                  and all(source.get(k) is None or isinstance(source.get(k), str)
                          for k in ('region', 'site')), '条件消耗品来源无效。')
        elif choice == 'ROGUE':
            check(source.get('kind') == 'rogue_event' and source.get('template_id') == row.get('template_id')
                  and source.get('option') == 'FORTUNE'
                  and all(isinstance(source.get(k),str) and source[k] for k in ('region','site','event')),
                  '行军约定来源无效。')
        else:
            check(source.get('kind') == 'event' and choice in ('SHARP', 'HAUL')
                  and source.get('event') == spec['event'] and source.get('option') == choice
                  and all(isinstance(source.get(k), str) and source[k] for k in ('region', 'site')),
                  '条件事件来源无效。')
        duration = row.get('duration', {})
        check(duration.get('kind') == spec['scope'] and duration.get('initial') == spec.get('battles'),
              '条件持续范围无效。')
        battles = row.get('battles')
        check(isinstance(battles, list) and len(battles) == len(set(battles))
              and set(battles) <= set(settled), '条件战斗扣次缺少结算回执。')
        if spec['scope'] == 'battles':
            left = duration.get('remaining')
            check(type(left) is int and 0 <= left <= spec['battles']
                  and left+len(battles) == spec['battles'], '条件剩余战数无效。')
        else:
            check(duration.get('remaining') is None and not battles, '条件范围被篡改为有限战数。')
        check(row.get('status') in ('READY', 'ACTIVE', 'EXPIRED', 'CLEANSED'), '条件状态无效。')
        check(row.get('prep_slot_reserved') == item_source
              and type(row.get('prep_slot_held')) is bool, '条件携行占位无效。')
        if row['prep_slot_held']:
            check(item_source and source['expedition'] == game.s['expedition_no'], '占位不能跨趟。')
            held += 1
        if row['status'] in ('READY', 'ACTIVE'):
            check(source['expedition'] == game.s['expedition_no'] and row.get('ended_reason') is None,
                  '有效条件跨趟残留。')
            if item_source:
                phases = ('TOWN', 'EXPLORE', 'FINAL_CHOICE', 'FINAL_REGROUP', 'MISSING_SEARCH', 'ABORTED') \
                    if row['status'] == 'READY' else ('EXPLORE', 'BATTLE', 'FINAL_CHOICE', 'FINAL_REGROUP', 'MISSING_SEARCH', 'ABORTED')
                check(game.s['phase'] in phases, '消耗品条件处于不合法阶段。')
            else:
                check(row['status'] == 'ACTIVE' and game.s.get('mission') == 'ORDINARY'
                      and game.s['phase'] in ('EXPLORE', 'BATTLE', 'ABORTED'),
                      '事件条件不能跨固定任务生效。')
            check(spec['scope'] != 'region' or source['region'] == game.s['region'], '本区条件跨区残留。')
            check(spec['scope'] != 'battles' or duration['remaining'] > 0, '零次条件仍有效。')
            check(row['family'] not in families, '同族条件叠加或刷新。')
            families.add(row['family'])
        else:
            check(bool(row.get('ended_reason')), '条件到期或清除缺少原因。')
    check(not numbers or data['next_id'] > max(numbers), '条件实例序号倒退。')
    check(held <= game.s.get('used_prep_slots', 0), '急磨占用的携行格被提前返还。')
    battle = game.s.get('battle')
    if battle:
        from fortune_mechanics import validate_actor
        import combat
        board=combat.cells(game.cat,battle)
        for actor in battle['actors']:validate_actor(actor,battle['tick'],board)
    if not battle or not battle.get('journey_conditions'):
        return
    frozen = battle['journey_conditions']; snaps = frozen.get('records', [])
    check(frozen.get('version') == VERSION and frozen.get('battle_id') == battle['battle_id']
          and frozen.get('condition_ids') == [r['id'] for r in snaps]
          and type(frozen.get('started_tick')) is int and 0 <= frozen['started_tick'] <= battle['tick'], '战斗条件冻结无效。')
    check(_battle_id(frozen['base_battle_id'], frozen['context'], snaps) == battle['battle_id'],
          '战斗ID与冻结条件不符。')
    context = frozen['context']
    check(context.get('started_tick') == frozen['started_tick'], '战斗起始拍来源不符。')
    key = ':'.join(str(context[k]) for k in ('expedition', 'region', 'site'))+':'+battle['battle_id']
    check(key == frozen['settlement_key'], '战斗条件结算身份无效。')
    by_id = {r['id']: r for r in records}
    for snap in snaps:
        current = by_id.get(snap['id'])
        check(current is not None and all(snap[k] == current[k] for k in
            ('choice', 'family', 'name', 'source', 'positive', 'negative')), '冻结条件被替换或丢失。')
    if not battle.get('result'):
        check(snaps == _eligible(game), '进行中的战斗与当前条件不符。')
    total = _totals(snaps)
    for actor in battle['actors']:
        snap = actor.get('journey_conditions')
        if actor['side'] != 'player' or not snaps:
            check(not snap, '没有来源的战斗条件。')
            continue
        expected = dict(version=VERSION, battle_id=battle['battle_id'], records=deepcopy(snaps),
            condition_ids=frozen['condition_ids'][:], started_tick=frozen['started_tick'],
            opening_shield=total['opening_shield_per_cost']*actor['cost'], **total)
        check(snap == expected, '出战者条件快照与冻结来源不符。')
