"""EV09: finite cargo capacity, real town delivery, persistent consignment."""
from copy import deepcopy
import cases
import event_memory
from joint_sampling_model import digest

TERMINAL = cases.TERMINAL
LAYOUT = {'template_id': 'EV09-VISIT', 'name': '采水队货物续运处',
          'nodes': [{'id': 'I', 'name': '返镇接驳口'}, {'id': 'A', 'name': '原货物接洽处'}],
          'edges': [['I', 'A']], 'safe_receiver_site': 'I'}
DESTINATION = '暮汀安置街指定住户接收处'


def check(condition, message):
    if not condition: raise ValueError(message)


def initialize(s, enabled):
    s['water'] = {**cases.common(enabled), 'cargo_id': 'EV09-WATER-01', 'loaded_trip': None,
                  'custody': '采水队保管两桶封水，等待交运',
                  'transport_history': []}
    s['directed_water'] = False


def seen(game):
    cases.seen(game,'EV09')


def update_scene(game, state, receipt=None):
    cases.update_scene(game,'EV09',state,receipt)


def reserved(game):
    """Directed trips keep two *unspent* units until loading or this trip ends."""
    s = game.s; c = s['water']; manifest = s.get('manifest')
    if not manifest or not manifest.get('water_capacity_reserved'): return 0
    if c['loaded_trip'] == s['expedition_no'] or c['state'] in TERMINAL: return 0
    return 2


def scene_text(game):
    c = game.s['water']
    if c['anchor'] and c['anchor']['expedition_no'] != game.s['expedition_no']:
        return ('采水队按原运单交接同一批封水，桶上的暮汀门牌仍在。' + c['custody'] +
                ' 两桶仍需占本趟2份材料回收额度，实际送到暮汀才算交货。')
    return game.cat.events['EV09']['scene']


def before_settlement(game, success):
    s = game.s; c = s['water']
    if c['loaded_trip'] != s['expedition_no']: return
    transport = {'cargo_id': c['cargo_id'], 'expedition_no': s['expedition_no'],
                 'visited_regions': s['visited_regions'][:], 'success': success}
    c['transport_history'].append(transport)
    c['loaded_trip'] = None
    if success:
        receipt = {'id': 'EV09-PROTECTED', 'cargo_id': c['cargo_id'], 'destination': DESTINATION,
                   'expedition_no': s['expedition_no'], 'day': s['day'] + 1,
                   'visited_regions': s['visited_regions'][:]}
        cases.protect(game,'EV09',receipt,custody='两桶水已由原定住户实际接收')
        if s.get('summary') is None:s['summary']={}
        s['summary'].setdefault('case_rewards',{})['EV09']=cases.protect_reward_text(game,'EV09')
        update_scene(game, 'RESOLVED', {'option': 'PROTECTED', 'target': DESTINATION, 'plan': None})
        game.log('water_delivered', receipt=deepcopy(receipt))
    else:
        # Explicit authored custody contract, not recovered ordinary loot or a
        # successful delivery. The same intact sealed cargo returns to its carrier.
        c['custody'] = '护运货车中止转送，采水队接回原两桶封水；仍需重新装载运往暮汀'
        game.log('water_transport_interrupted', cargo_id=c['cargo_id'], custody=c['custody'])


def redeem(game):
    return cases.redeem(game,'EV09')


def visit(game):
    s = game.s; c = s['water']; game.validate_deployment()
    rid = c['anchor']['region']
    binding = {'event_id': 'EV09', 'enabled_options': ['HUMANITY', 'PASS'] if c['state']=='PROTECTION_PENDING' else ['HUMANITY', 'EXPLOIT', 'PASS'],
               'disabled_options': {}, 'reserved_debits': {'material_units': 2},
               'site_lighting': deepcopy(game.cat.events['EV09']['site_lighting'])}
    manifest = {'version': 'EV09-VISIT-1.0', 'profile': 'SHORT', 'start': rid, 'target': rid,
                'paths': [[rid]], 'regions': {rid: {'template_id': LAYOUT['template_id'],
                'events': {'A': binding}, 'encounters': {}, 'combat_rewards': {}}},
                'caps': {'material_units': 2}, 'water_capacity_reserved': True,
                'departure_supply_cost': 0, 'choice_policy': {'authoring_gate': 'FIXED_CARGO_NO_ORDINARY_REWARDS'}}
    manifest['manifest_sha256'] = digest(manifest)
    s.update(mission='WATER_VISIT', manifest=manifest, request={'fixed_case': 'EV09'},
             region=rid, site='I', phase='EXPLORE', visited_regions=[rid])
    s['regions'] = {rid: {'cleared': [], 'seen': ['I'], 'revealed_battles': [], 'station_used': False,
                        'camp_used': False, 'deployed_here': [], 'variant': None,
                        'events': {'A': {'state': 'UNSEEN', 'steps': [], 'receipt': None}}}}
    game.log('water_fixed_visit', cargo_id=c['cargo_id'], action_days=1)


def handle(game, args):
    s = game.s; c = s['water']; check(c['enabled'], '请新建“运水事件”或“两项事件”试验档。')
    check(args, 'water load CONFIRM / trade CONFIRM / followup on/off / visit CONFIRM')
    action = args[0]
    if action in ('followup', 'visit'):
        check(s['phase']=='TOWN', '续办需要在城镇整备。')
        check(c['encountered'] and c['state'] not in TERMINAL, '仅已遇见、未交割的原运单可以续办。')
        if action=='followup':
            check(len(args)==2 and args[1] in ('on','off'), 'water followup on/off')
            cases.direct(s,'EV09',args[1]=='on')
            return '已更新运水定向续办；每趟只定向一项，出发先预留2份材料额度。'
        check(args==['visit','CONFIRM'], 'water visit CONFIRM：固定续运，归城1日，无普通战斗或奖励。')
        from rescue import confirm_day
        confirm_day(s, ['CONFIRM']); visit(game)
        return '已到原货物接洽处，预留2份材料额度；归城结算1日。'
    game.noncombat()
    check(s['site'] in game.manifest_region['events'] and game.manifest_region['events'][s['site']]['event_id']=='EV09', '请到运水事件现场。')
    check(game.current['events'][s['site']]['state']!='DECLINED', '本趟已放弃接手，可归城后续办。')
    seen(game)
    check(c['state'] not in TERMINAL, '原运单已交割，不能再次装载或出售。')
    options = {o['option_id']: o for o in game.cat.events['EV09']['options']}
    if action=='load':
        check(args==['load','CONFIRM'], 'water load CONFIRM：占2份未使用材料额度；放弃40铜＋8结晶报价。')
        check(c['loaded_trip'] is None, '同一批水已装载，不重复占位。')
        check('HUMANITY' in game.manifest_region['events'][s['site']]['enabled_options'], '本次地点未提供运水服务。')
        # Occupancy consumes the same budget as ordinary material claims, never
        # actual warehouse materials or the four consumable inventory slots.
        game.debit({'material_units': 2}, cargo=True)
        c.update(state='PROTECTION_PENDING', loaded_trip=s['expedition_no'],
                 custody='原两桶封水随本队货车运输，尚未抵达暮汀')
        update_scene(game, 'ACTIVE')
        game.log('water_loaded', cargo_id=c['cargo_id'], occupied_material_units=2)
        return '已装载两桶水，占用本趟2份材料回收额度；可以继续探索，归城实际交货后完成。'
    if action=='trade':
        check(args==['trade','CONFIRM'], options['EXPLOIT']['confirmation_text'])
        check(c['state']=='OPEN', '已经接手运水，不能改卖或卸货腾出奖励额度。')
        check('EXPLOIT' in game.manifest_region['events'][s['site']]['enabled_options'], '本次仅可继续交货。')
        spec = game.cat.events['EV09']['story_trade']
        cases.issue_trade(game,'EV09', custody='原两桶水已交给铸造收购方，不可重新交给住户',
                 receipt={'id':'EV09-EXPLOITED','cargo_id':c['cargo_id'],'day':s['day'],'expedition_no':s['expedition_no']})
        update_scene(game, 'RESOLVED', {'option':'EXPLOITED','target':'现场军需商','plan':None})
        game.log('water_trade_accepted', receipt=deepcopy(c['receipt']), credit=deepcopy(c['trade_credit']))
        return options['EXPLOIT']['result_text']
    raise ValueError('未知运水操作。')


def public(game):
    s = game.s; c = s['water']
    if not c['enabled'] or not c['encountered']: return None
    at_scene = (s['phase']=='EXPLORE' and s['site'] in game.manifest_region['events'] and
                game.manifest_region['events'][s['site']]['event_id']=='EV09')
    opened = at_scene and game.current['events'][s['site']]['state']!='DECLINED' and c['state'] not in TERMINAL
    cap = (s.get('manifest') or {}).get('caps', {}).get('material_units', 0)
    used = s['debits'].get('material_units', 0)
    text = c['custody'] + '。'
    credit = c['trade_credit']
    if credit: text += '40铜＋8结晶' + ('已兑现。' if credit['redeemed'] else '待下次城镇结算兑现，途中不可用。')
    return {'text':text, 'scene':scene_text(game), 'open':opened,
            'can_load':opened and c['loaded_trip'] is None, 'can_trade':opened and c['state']=='OPEN',
            'loaded':c['loaded_trip']==s['expedition_no'], 'capacity':cap, 'used':used,
            'free':max(0,cap-used), 'reserved':reserved(game),
            'can_followup':s['phase']=='TOWN' and c['state'] not in TERMINAL,
            'directed':s['directed_water'],
            'trade_warning':next(o['confirmation_text'] for o in game.cat.events['EV09']['options'] if o['option_id']=='EXPLOIT')}
