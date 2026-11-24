"""Actual event receipts and frozen, optional campaign follow-ups.

Ordinary history never changes base-card eligibility or weights. Source choices
are world actions, not proof that carried loot was safely delivered to town.
"""
from copy import deepcopy
from data import keyed_rng
from joint_sampling_model import digest


def recent(game):
    history = [h['expedition_no'] for h in game.s['completed_history']
               if h['mission'] == 'ORDINARY']
    allowed = set(history[-game.cat.event_links['source_window_ordinary_expeditions']:])
    return [r for r in game.s['event_memory'].values() if r['expedition_no'] in allowed]


def presented_history(game):
    groups = {}
    for record in recent(game):
        groups.setdefault(record['expedition_no'], set()).add(record['event_id'])
    return [sorted(ids) for _, ids in sorted(groups.items())]


def record(game, region=None, site=None):
    s = game.s
    region=region or s['region']; site=site or s['site']
    binding = s['manifest']['regions'][region]['events'][site]
    state = s['regions'][region]['events'][site]
    key = f"{s['expedition_no']}:{region}:{site}"
    previous = s['event_memory'].get(key)
    row = {'id': key, 'expedition_no': s['expedition_no'], 'region': region,
           'site': site, 'event_id': binding['event_id'], 'state': state['state'],
           'steps': state['steps'][:], 'receipt': deepcopy(state['receipt']),
           'followup': binding.get('followup', {}).get('rule_id')}
    # One record per scene. A revisit or repeated submission cannot create history.
    if previous is None or any(previous.get(k) != v for k, v in row.items()):
        row['updated_seq'] = s['sequence']
        s['event_memory'][key] = row


def freeze(game, manifest):
    """Run once at departure; subsequent visits/loads cannot reroll a follow-up."""
    history = recent(game)
    rules = game.cat.event_links
    for rid, region in manifest['regions'].items():
        for slot, binding in region['events'].items():
            for rule in rules['rules']:
                if binding['event_id'] != rule['target_event']:
                    continue
                candidates = [r for r in history if r['event_id'] == rule['source_event']
                              and r['region'] == rid and r['state'] == 'RESOLVED'
                              and r['receipt']['option'] in rule['source_options']]
                if not candidates or rule['budget_parent_option'] not in binding['enabled_options']:
                    continue
                source = max(candidates, key=lambda r: (r['expedition_no'], r['updated_seq'], r['id']))
                roll = keyed_rng(game.s['seed'], f"followup:{rid}:{slot}:{rule['id']}:{source['id']}").random()
                if roll >= rules['followup_chance']:
                    continue
                parent = next(o for o in game.cat.events[binding['event_id']]['options']
                              if o['option_id'] == rule['budget_parent_option'])
                option = deepcopy(parent)
                option.update(option_id='LINK', label=rule['label'], result_text=rule['result_text'])
                if rule['mode'] == 'consume_brace_heal':
                    item = rule['source_options'][source['receipt']['option']]
                    option['costs'] = {'carried_consumables': {item: 1}}
                    option['effects'][0]['numerator'] = 2
                    option['mechanical_summary'] = f'消耗包内1份未使用的{item}，治疗一名站立队员最大生命的40%（不超过缺血）；占1次恢复额度，与原选项互斥。'
                elif rule['mode'] == 'fiber_instead_of_exertion':
                    option['costs'] = {'carried_materials': {'fiber': 1}}
                    option['effects'] = [e for e in option['effects'] if e['type'] != 'event_hp_exertion']
                    option['mechanical_summary'] = '消耗途中包内1木纤，不消耗生命，取得4单位本区材料；仍扣4材料领取额度，不退已消耗材料的额度，与原选项互斥。'
                else:
                    raise ValueError('Unknown follow-up mode: ' + rule['mode'])
                binding['followup'] = {'rule_id': rule['id'], 'source_id': source['id'],
                                       'source_event': source['event_id'], 'source_option': source['receipt']['option'],
                                       'source_expedition': source['expedition_no'],
                                       'scene': rule['scene'], 'option': option}
                binding['enabled_options'].append('LINK')
                break
    manifest['event_history_policy'] = {'version': rules['version'], 'ordinary_cooldown': 0,
                                        'ordinary_recent_weight_multiplier': 1,
                                        'followups_locked_at_departure': True}
    manifest.pop('manifest_sha256', None)
    manifest['manifest_sha256'] = digest(manifest)


def card(base, binding):
    followup = binding.get('followup')
    if not followup:
        return base
    result = deepcopy(base)
    result['scene'] += '\n' + followup['scene']
    result['options'].insert(-1, deepcopy(followup['option']))
    return result


def describe(game):
    lines = []
    for row in sorted(game.s['event_memory'].values(), key=lambda r: (r['expedition_no'], r['updated_seq']))[-12:]:
        event = game.cat.events[row['event_id']]
        if row['state'] == 'RESOLVED':
            choice = next((o['label'] for o in event['options'] if o['option_id'] == row['receipt']['option']), '完成联动选择')
            if row['receipt']['option'] == 'FORTUNE':
                import rogue_events
                receipt = next((r for r in game.s['rogue_events']['receipts']
                    if r.get('expedition') == row['expedition_no']
                    and r.get('region') == row['region'] and r.get('site') == row['site']), None)
                choice = '已采用行军约定'
                if receipt and receipt.get('template_id'):
                    choice += '：'+rogue_events.get_spec(receipt['template_id'])['name']
            if row['event_id']=='EV03': choice={'PROTECTED':'已转送暮汀并接收搬运工','EXPLOITED':'已交给管事，不能再由本委托赎回'}[row['receipt']['option']]
            if row['event_id']=='EV09': choice={'PROTECTED':'原两桶水已送达暮汀安置街','EXPLOITED':'水已交给铸造收购方，原定住户无法收到'}[row['receipt']['option']]
            if row['event_id'] in ('EV05','EV07','EV12','EV16','EV22','EV28'):
                import cases
                choice=cases.CONFIG[row['event_id']]['protected' if row['receipt']['option']=='PROTECTED' else 'exploited']
            if row['event_id']=='EV25': choice={'PROTECTED':'认领员已收妥原行李，凭据随例行护运转送暮汀','EXPLOITED':'认领凭据已销毁，原物主失去追讨凭据'}[row['receipt']['option']]
            if row['event_id']=='EV19': choice={'PROTECTED':'原药箱已由暮汀医舍接收','EXPLOITED':'原药箱已转卖，原定病人错过救治机会'}[row['receipt']['option']]
        else:
            choice = {'OPEN': '已见，尚未完成', 'ACTIVE': '已开始，尚未完成', 'DECLINED': '明确放弃本趟现场'}[row['state']]
        lines.append(f"第{row['expedition_no']}趟 · {event['name']}：{choice}")
    return '\n'.join(lines) or '尚未遇到事件。普通事件可以在后续远征再次出现。'
