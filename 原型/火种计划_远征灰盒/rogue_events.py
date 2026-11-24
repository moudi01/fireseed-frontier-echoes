"""Frozen ordinary-event bargains; outcomes never adapt to the current party.

Only an already sampled material option can host FORTUNE. The original event,
its alternatives, and the shared material budget remain owned by the engine.
"""
from copy import deepcopy
import hashlib
import json

from data import keyed_rng

VERSION = 'ROGUE-EVENTS-0.66'
WHITELIST = frozenset(('EV01', 'EV06', 'EV13', 'EV15', 'EV20', 'EV29',
    'EV32', 'EV35', 'EV38', 'EV41', 'EV44', 'EV47', 'EV50', 'EV60'))
NORMAL_IDS = tuple(f'F{i:02}' for i in range(1, 13))
RARE_IDS = tuple(f'R{i:02}' for i in range(1, 13))
CURSE_IDS = ('C01', 'C02')
PROBABILITIES = (('rare', 50), ('ordinary', 30), ('curse', 20))
COSTS = {'banked_copper': 4}
DEBITS = {'material_units': 2}


def _spec(name, positive, negative):
    return dict(name=name, family='fortune', scope='journey',
                positive=positive, negative=negative)


TEMPLATES = {
    'F01': _spec('锻锋约定', {'physical_damage_increase': .15}, {'magic_damage_penalty': .10}),
    'F02': _spec('引辉约定', {'magic_damage_increase': .15}, {'physical_damage_penalty': .10}),
    'F03': _spec('先声约定', {'early_damage_increase': .18}, {'late_incoming_increase': .12}),
    'F04': _spec('驻足约定', {'stationary_reduction': .10}, {'moved_incoming_increase': .10}),
    'F05': _spec('济护约定', {'active_heal_increase': .15}, {'direct_damage_penalty': .10}),
    'F06': _spec('护旅约定', {'opening_shield_per_cost': 1}, {'direct_damage_penalty': .08}),
    'F07': _spec('追隙约定', {'execute_damage_increase': .20}, {'healthy_damage_penalty': .08}),
    'F08': _spec('远弦约定', {'ranged_damage_increase': .15}, {'near_damage_penalty': .08}),
    'F09': _spec('贯阵约定', {'melee_pierce_radius': 2, 'melee_pierce_targets': 1, 'melee_pierce_coefficient': .6}, {'basic_interval_penalty': 1}),
    'F10': _spec('迸散约定', {'ranged_burst_radius': 1, 'ranged_splash_coefficient': .6}, {'basic_windup_extra': 1}),
    'F11': _spec('长步约定', {'stride_steps': 2}, {'stride_basic_pause': 1}),
    'F12': _spec('接盾约定', {'shield_relay_range': 1}, {'relay_donor_exposure': .10}),
    'C01': _spec('失衡·暴露', {}, {'incoming_increase': .12}),
    'C02': _spec('失衡·钝锋', {}, {'direct_damage_penalty': .10}),
}
for _normal, _rare in zip(NORMAL_IDS[:8], RARE_IDS[:8]):
    _base = TEMPLATES[_normal]
    _positive = {key: (2 if key == 'opening_shield_per_cost' else round(value*1.5, 6))
                 for key, value in _base['positive'].items()}
    TEMPLATES[_rare] = _spec('罕见·'+_base['name'], _positive, deepcopy(_base['negative']))
del _normal, _rare, _base, _positive
TEMPLATES.update({
    'R09': _spec('罕见·贯阵约定', {'melee_pierce_radius': 3, 'melee_pierce_targets': 2, 'melee_pierce_coefficient': .6}, {'basic_interval_penalty': 1}),
    'R10': _spec('罕见·迸散约定', {'ranged_burst_radius': 1, 'ranged_splash_coefficient': .9}, {'basic_windup_extra': 1}),
    'R11': _spec('罕见·长步约定', {'stride_steps': 3}, {'stride_basic_pause': 1}),
    'R12': _spec('罕见·接盾约定', {'shield_relay_range': 2}, {'relay_donor_exposure': .10}),
})


def check(ok, message):
    if not ok:
        raise ValueError(message)


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False,
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def get_spec(template_id):
    check(template_id in TEMPLATES, '未知旅途约定模板。')
    return deepcopy(TEMPLATES[template_id])


def initialize(game):
    game.s.setdefault('rogue_events', dict(version=VERSION, receipts=[]))


def state(game):
    check('rogue_events' in game.s, '本档未初始化旅途约定。')
    return game.s['rogue_events']


def install(cat):
    """No catalog cards, items, or recipes are added by this overlay."""
    return None


def describe_template(template_id):
    spec = get_spec(template_id); p = spec['positive']; n = spec['negative']
    from fortune_mechanics import describe
    mechanic=describe(spec)
    if mechanic:return spec['name']+'：'+mechanic
    percent = lambda value: f'{value*100:g}%'
    effects = []
    if 'physical_damage_increase' in p:
        effects += ['物理直接伤害+'+percent(p['physical_damage_increase']),
                    '魔法直接伤害−'+percent(n['magic_damage_penalty'])]
    if 'magic_damage_increase' in p:
        effects += ['魔法直接伤害+'+percent(p['magic_damage_increase']),
                    '物理直接伤害−'+percent(n['physical_damage_penalty'])]
    if 'early_damage_increase' in p:
        effects += ['每场前6拍直接伤害一般增伤+'+percent(p['early_damage_increase']),
                    '第7拍起承伤+'+percent(n['late_incoming_increase'])]
    if 'stationary_reduction' in p:
        effects += ['静止至少2拍减伤'+percent(p['stationary_reduction']),
                    '真实移动后1拍承伤+'+percent(n['moved_incoming_increase'])+'，初始未动不算']
    if 'active_heal_increase' in p:
        effects += ['原生或书主动治疗量+'+percent(p['active_heal_increase']),
                    '直接伤害−'+percent(n['direct_damage_penalty'])]
    if 'opening_shield_per_cost' in p:
        effects += [f"每场开场私盾{p['opening_shield_per_cost']}×本人Cost",
                    '直接伤害−'+percent(n['direct_damage_penalty'])]
    if 'execute_damage_increase' in p:
        effects += ['对生命比例≤50%的敌人直接伤害+'+percent(p['execute_damage_increase']),
                    '对生命比例>50%的敌人直接伤害−'+percent(n['healthy_damage_penalty'])]
    if 'ranged_damage_increase' in p:
        effects += ['实际攻击距离≥3时直接伤害+'+percent(p['ranged_damage_increase']),
                    '实际攻击距离≤1时直接伤害−'+percent(n['near_damage_penalty'])]
    if not p:
        effects.append('没有正面效果')
        if 'incoming_increase' in n:
            effects.append('承伤+'+percent(n['incoming_increase']))
        if 'direct_damage_penalty' in n:
            effects.append('直接伤害−'+percent(n['direct_damage_penalty']))
    return spec['name']+'：'+'；'.join(effects)


def _eligible(cat, region):
    sites = []
    for site, binding in sorted(region.get('events', {}).items()):
        event_id = binding['event_id']
        event = cat.events.get(event_id)
        if event_id not in WHITELIST or not event or event['type'] == 'humanity':
            continue
        parent = next((o['option_id'] for o in event['options']
                       if o['option_id'] in binding['enabled_options']
                       and o.get('reward_bundle_id') == 'RB-MAT2'), None)
        if parent is not None:
            sites.append((site, event_id, parent))
    return sites


def _region_offer(cat, manifest, region_id):
    """Pure replay from the seed and already sampled event bindings only."""
    seed = manifest['seed']; options = _eligible(cat, manifest['regions'][region_id])
    if not options:
        return None
    site, event_id, parent = keyed_rng(seed, f'{VERSION}:{region_id}:site').choice(options)
    key = f'{VERSION}:{region_id}:{site}:{event_id}'
    safe = keyed_rng(seed, key+':safe').sample(list(NORMAL_IDS), 2)
    risk_base = keyed_rng(seed, key+':risk-base').choice([x for x in NORMAL_IDS if x not in safe])
    curse = keyed_rng(seed, key+':curse').choice(CURSE_IDS)
    templates = dict(rare='R'+risk_base[1:], ordinary=risk_base, curse=curse)
    outcomes = [dict(id=kind, probability=probability, template_id=templates[kind])
                for kind, probability in PROBABILITIES]
    roll = keyed_rng(seed, key+':risk-roll').randrange(sum(x['probability'] for x in outcomes))
    cumulative = 0
    for result in outcomes:
        cumulative += result['probability']
        if roll < cumulative:
            break
    offer = dict(version=VERSION, seed=seed, region=region_id, site=site, event=event_id,
                 parent_option=parent, costs=deepcopy(COSTS), debits=deepcopy(DEBITS),
                 candidates=[dict(id=selection, template_id=template)
                             for selection, template in zip(('A', 'B'), safe)],
                 risk=dict(base_id=risk_base, outcomes=outcomes), secret_roll=roll,
                 secret_result=dict(outcome=result['id'], template_id=result['template_id']))
    offer['digest'] = _digest(offer)
    return offer


def bind(cat, manifest):
    check(type(manifest.get('seed')) is int, '旅途约定需要固定的远征种子。')
    selected = []
    for region_id, region in sorted(manifest['regions'].items()):
        offer = _region_offer(cat, manifest, region_id)
        if offer is None:
            continue
        binding = region['events'][offer['site']]
        binding['rogue_offer'] = offer
        if 'FORTUNE' not in binding['enabled_options']:
            binding['enabled_options'].append('FORTUNE')
        binding.get('disabled_options', {}).pop('FORTUNE', None)
        selected.append({key: deepcopy(offer[key]) for key in
                         ('region', 'site', 'event', 'parent_option', 'digest')})
    manifest['rogue_events'] = dict(version=VERSION, sites=selected)


def _validate_manifest(cat, manifest):
    selected = []
    check(type(manifest.get('seed')) is int, '约定绑定缺少固定种子。')
    for region_id, region in sorted(manifest['regions'].items()):
        expected = _region_offer(cat, manifest, region_id)
        for site, binding in region.get('events', {}).items():
            chosen = expected is not None and site == expected['site']
            if chosen:
                check(binding.get('rogue_offer') == expected and 'FORTUNE' in binding['enabled_options'],
                      '约定候选、概率或隐藏结果与出发冻结不符。')
            else:
                check('rogue_offer' not in binding and 'FORTUNE' not in binding['enabled_options'],
                      '未选中现场出现了额外约定。')
        if expected is not None:
            selected.append({key: deepcopy(expected[key]) for key in
                             ('region', 'site', 'event', 'parent_option', 'digest')})
    check(manifest.get('rogue_events') == dict(version=VERSION, sites=selected),
          '约定出发绑定目录被改写。')


def _at_offer(game, event, binding, require_here=False):
    offer = binding.get('rogue_offer')
    if offer is None:
        return None
    check(offer.get('region') in game.s['manifest']['regions'], '约定地区不属于本趟。')
    expected = _region_offer(game.cat, game.s['manifest'], offer['region'])
    check(offer == expected and offer['event'] == event['event_id'], '本处约定与冻结现场不符。')
    if require_here:
        check(offer['region'] == game.s['region'] and offer['site'] == game.s['site'],
              '须到约定所在现场才能确认。')
    return offer


def card(game, event, binding):
    result = deepcopy(event)
    offer = _at_offer(game, event, binding)
    if offer is None or any(o['option_id'] == 'FORTUNE' for o in result['options']):
        return result
    choices = [dict(id=o['id'], label=describe_template(o['template_id']))
               for o in offer['candidates']]
    risk_text = '；'.join(f"{o['probability']}% {describe_template(o['template_id'])}"
                         for o in offer['risk']['outcomes'])
    choices.append(dict(id='RISK', label='风险试行：'+risk_text))
    parent = next(o for o in result['options'] if o['option_id'] == offer['parent_option'])
    option = deepcopy(parent)
    summary = ('支付已入库铜4，并消耗本趟材料额度2；替代本卡材料机会，不发材料或物品。'
               'A／B为所示普通约定；RISK公开50%罕见版、30%普通版、20%失衡版，'
               '实际结果出发已锁，确认后揭晓，坏结果照常付款并关闭事件。'
               '约定持续本趟，全队生效，与旧旅途约定完整替换且不退款，不叠加；'
               '与锐刃、负重、护片／急磨包独立，可用EV36或边界营地机会整组清理。'
               '不复起、不刷新技能、不造成永久损失。')
    option.update(option_id='FORTUNE', label='接纳一种旅途约定', costs=deepcopy(COSTS),
        effects=[dict(type='rogue_choice')], mechanical_summary=summary,
        result_text='旅途约定已按公开选择结算。', target_choices=choices,
        opportunity_cost='互斥关闭整卡；替代材料机会，新约定完整替换旧约定正负且不退款',
        preview_rule='候选模板、正负效果、费用和三种风险概率公开；隐藏投签只在确认后揭晓',
        rogue_version=VERSION)
    index = next((i for i, o in enumerate(result['options']) if o['option_id'] == 'PASS'),
                 len(result['options']))
    result['options'].insert(index, option)
    return result


def public_binding(binding):
    def clean(value):
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()
                    if not key.startswith('secret_')}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return deepcopy(value)
    return clean(binding)


def _resolved(offer, selection):
    if selection == 'RISK':
        return deepcopy(offer['secret_result'])
    candidate = next(x for x in offer['candidates'] if x['id'] == selection)
    return dict(outcome='ordinary', template_id=candidate['template_id'])


def _source(expedition, offer, selection, result):
    return dict(kind='rogue_event', version=VERSION, template_id=result['template_id'],
        expedition=expedition, region=offer['region'], site=offer['site'], event=offer['event'],
        option='FORTUNE', selection=selection, outcome=result['outcome'],
        frozen_offer_digest=offer['digest'])


def _receipt_id(source):
    return f"RF:{source['expedition']}:{source['region']}:{source['site']}"


def _reveal(receipt):
    selection = receipt['selection']
    result = receipt['outcome']
    label = {'rare': '罕见', 'ordinary': '普通', 'curse': '失衡'}[result]
    return (f"已付4铜并消耗材料额度2；选择{selection}，结果为{label}："
            +describe_template(receipt['template_id'])
            +'。本卡已关闭；新旧旅途约定整组替换，不发材料或物品，不退款。')


def choose(game, target):
    """The engine already paid four copper and commits RESOLVED afterward."""
    check(game.s.get('mission') == 'ORDINARY' and game.s['phase'] == 'EXPLORE',
          '旅途约定仅用于普通远征非战斗现场。')
    selection = target.upper()
    check(selection in ('A', 'B', 'RISK'), '请选择FORTUNE A、B或RISK。')
    event, binding, row = game.event_info()
    offer = _at_offer(game, event, binding, require_here=True)
    check(offer is not None and 'FORTUNE' in binding['enabled_options'], '本处没有冻结约定。')
    check(row['state'] == 'OPEN', '本卡已经开始或提交其他结果。')
    import event_conditions
    check(event_conditions._item_future(game) > 0, '本趟已无后续战斗，不能支付旅途约定。')
    result = _resolved(offer, selection)
    source = _source(game.s['expedition_no'], offer, selection, result)
    rid = _receipt_id(source)
    data = state(game)
    previous = next((r for r in data['receipts'] if r['id'] == rid), None)
    if previous is not None:
        check(previous['selection'] == selection, '本处已经提交另一约定选择。')
        return _reveal(previous)
    game.debit(DEBITS)
    receipt = dict(id=rid, version=VERSION, source=deepcopy(source),
        expedition=source['expedition'], region=source['region'], site=source['site'],
        event=source['event'], option='FORTUNE', selection=selection, outcome=result['outcome'],
        template_id=result['template_id'], frozen_offer_digest=offer['digest'],
        costs=deepcopy(COSTS), debits=deepcopy(DEBITS), condition_id=None)
    if selection == 'RISK':
        receipt['roll'] = offer['secret_roll']
    data['receipts'].append(receipt)
    acquired = event_conditions.acquire_rogue(game, result['template_id'], source)
    receipt['condition_id'] = acquired['id']
    game.log('rogue_event_committed', receipt=deepcopy(receipt))
    return _reveal(receipt)


def _trip(game, expedition):
    if expedition == game.s['expedition_no'] and game.s.get('manifest') is not None:
        return game.s
    return next((h for h in game.s.get('completed_history', [])
                 if h['expedition_no'] == expedition), None)


def _check_receipt(game, receipt):
    source = receipt.get('source', {})
    expedition = source.get('expedition')
    check(type(expedition) is int and 1 <= expedition <= game.s['expedition_no'],
          '约定回执趟次无效。')
    trip = _trip(game, expedition)
    check(trip is not None and trip.get('manifest') is not None, '约定来源远征不存在。')
    manifest = trip['manifest']
    region_id = source.get('region'); site = source.get('site')
    check(region_id in manifest['regions'], '约定来源地区无效。')
    expected = _region_offer(game.cat, manifest, region_id)
    check(expected is not None and expected['site'] == site, '约定来源不是本区冻结现场。')
    binding = manifest['regions'][region_id]['events'][site]
    check(binding.get('rogue_offer') == expected, '约定来源冻结候选被改写。')
    selection = receipt.get('selection')
    check(selection in ('A', 'B', 'RISK'), '约定回执选择无效。')
    result = _resolved(expected, selection)
    expected_source = _source(expedition, expected, selection, result)
    check(source == expected_source and receipt.get('id') == _receipt_id(expected_source)
          and receipt.get('version') == VERSION, '约定回执来源或版本无效。')
    for key in ('expedition', 'region', 'site', 'event', 'option', 'selection',
                'outcome', 'template_id', 'frozen_offer_digest'):
        check(receipt.get(key) == expected_source[key], '约定回执与真实投签结果不符。')
    check(receipt.get('costs') == COSTS and receipt.get('debits') == DEBITS,
          '约定回执费用或材料额度无效。')
    if selection == 'RISK':
        check(receipt.get('roll') == expected['secret_roll'], '风险投签被重抽或改写。')
    else:
        check('roll' not in receipt, '确定候选不应泄漏未选风险投签。')
    location = trip.get('regions', {}).get(region_id, {}).get('events', {}).get(site)
    check(location is not None and location['state'] == 'RESOLVED'
          and (location.get('receipt') or {}).get('option') == 'FORTUNE'
          and (location.get('receipt') or {}).get('target', '').upper() == selection,
          '约定缺少已提交的互斥事件回执。')
    return expected_source


def validate_condition_source(game, row):
    """Called by condition validation; no journal ordering is assumed."""
    source = row.get('source', {})
    receipt = next((r for r in state(game)['receipts']
                    if r.get('id') == _receipt_id(source)), None) if all(
                        k in source for k in ('expedition', 'region', 'site')) else None
    check(receipt is not None, '旅途约定条件缺少取得回执。')
    expected_source = _check_receipt(game, receipt)
    template_id = receipt['template_id']; spec = get_spec(template_id)
    check(row.get('choice') == 'ROGUE' and row.get('template_id') == template_id
          and row.get('source') == expected_source and row.get('id') == receipt['condition_id']
          and all(row.get(key) == spec[key] for key in ('name', 'family', 'positive', 'negative')),
          '旅途约定条件与冻结结算模板不符。')
    return True


def validate(game):
    data = state(game)
    check(data.get('version') == VERSION and isinstance(data.get('receipts'), list),
          '旅途约定版本或回执表无效。')
    trip_states = list(game.s.get('completed_history', []))
    if game.s.get('manifest') is not None:
        trip_states.append(game.s)
    for trip in trip_states:
        manifest = trip.get('manifest')
        if manifest is None:
            continue
        normal = (trip.get('mission') == 'ORDINARY'
                  and manifest.get('version') == 'JOINT-SAMPLE-1.0')
        overlay = any(binding.get('rogue_offer') is not None
                      or 'FORTUNE' in binding.get('enabled_options', [])
                      for region in manifest.get('regions', {}).values()
                      for binding in region.get('events', {}).values())
        if normal or overlay or 'rogue_events' in manifest:
            _validate_manifest(game.cat, manifest)
    receipts = data['receipts']
    check(len({r.get('id') for r in receipts}) == len(receipts), '同一现场重复约定回执。')
    records = [r for r in game.s.get('journey_conditions', {}).get('records', [])
               if r.get('choice') == 'ROGUE']
    for receipt in receipts:
        _check_receipt(game, receipt)
        matching = [r for r in records if r.get('id') == receipt.get('condition_id')]
        check(len(matching) == 1, '约定回执与条件实例不是一一对应。')
        validate_condition_source(game, matching[0])
    check(len(records) == len(receipts), '约定条件存在无回执实例。')


def public(game):
    data = state(game); current = []
    if (game.s.get('mission') == 'ORDINARY' and game.s.get('manifest')
            and game.s.get('region') in game.s['manifest']['regions']):
        region = game.s['manifest']['regions'][game.s['region']]
        seen = set(game.current.get('seen', [])) | {game.s.get('site')}
        for site, binding in region['events'].items():
            if site in seen and binding.get('rogue_offer'):
                current.append(dict(region=game.s['region'], site=site,
                                    offer=public_binding(binding)['rogue_offer']))
    return dict(version=VERSION, receipts=deepcopy(data['receipts']), current=current)


def describe(game):
    view = public(game)
    lines = ['旅途约定：同区至多一处冻结候选；确认前只公开候选与概率，不公开投签结果。']
    for receipt in view['receipts'][-3:]:
        lines.append(_reveal(receipt))
    for row in view['current']:
        offer = row['offer']
        lines.append(row['region']+'/'+row['site']+'：'+
            '；'.join(x['id']+' '+describe_template(x['template_id']) for x in offer['candidates'])+
            '；RISK '+ '／'.join(str(x['probability'])+'% '+describe_template(x['template_id'])
                                 for x in offer['risk']['outcomes']))
    return '\n'.join(lines)
