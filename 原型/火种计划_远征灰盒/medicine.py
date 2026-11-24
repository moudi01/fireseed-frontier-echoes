"""EV19: accepting the medical delivery immediately ends the expedition."""
from copy import deepcopy
import cases
import event_memory
from refugee import clear_path
from joint_sampling_model import digest

TERMINAL = cases.TERMINAL
DESTINATION = '暮汀医舍'
LAYOUT = {'template_id':'EV19-VISIT', 'name':'药箱原委托接洽处',
          'nodes':[{'id':'I','name':'返城船接驳口'},{'id':'A','name':'药箱集运棚'}],
          'edges':[['I','A']], 'safe_receiver_site':'I'}


def check(condition, message):
    if not condition: raise ValueError(message)


def initialize(s, enabled):
    s['medicine'] = {**cases.common(enabled), 'box_id':'EV19-MEDICINE-01',
                     'custody':'采药班保管原药箱，暮汀医舍正在照护原定病人'}
    s['directed_medicine'] = False


def seen(game):
    cases.seen(game,'EV19')


def update_scene(game, receipt):
    cases.update_scene(game,'EV19','RESOLVED',receipt)


def scene_text(game):
    c=game.s['medicine']
    if c['anchor'] and c['anchor']['expedition_no']!=game.s['expedition_no']:
        return ('采药班按原委托交出同一只封存药箱，已安排本次返城船。病人仍在暮汀接受基础照护，'
                '等待这批指定治疗用药。若接手送医，全队须直接返城；不是让原先那班船一直停在岸边等候。')
    return game.cat.events['EV19']['scene']


def redeem(game):
    return cases.redeem(game,'EV19')


def visit(game):
    s=game.s; c=s['medicine']; game.validate_deployment(); rid=c['anchor']['region']
    binding={'event_id':'EV19','enabled_options':['HUMANITY','EXPLOIT','PASS'],
             'disabled_options':{},'reserved_debits':{},
             'site_lighting':deepcopy(game.cat.events['EV19']['site_lighting'])}
    manifest={'version':'EV19-VISIT-1.0','profile':'SHORT','start':rid,'target':rid,'paths':[[rid]],
              'regions':{rid:{'template_id':LAYOUT['template_id'],'events':{'A':binding},
                             'encounters':{},'combat_rewards':{}}},
              'caps':{},'departure_supply_cost':0,
              'choice_policy':{'authoring_gate':'FIXED_MEDICINE_NO_ORDINARY_REWARDS'}}
    manifest['manifest_sha256']=digest(manifest)
    s.update(mission='MEDICINE_VISIT',manifest=manifest,request={'fixed_case':'EV19'},
             region=rid,site='I',phase='EXPLORE',visited_regions=[rid])
    s['regions']={rid:{'cleared':[],'seen':['I'],'revealed_battles':[],'station_used':False,
                      'camp_used':False,'deployed_here':[],'variant':None,
                      'events':{'A':{'state':'UNSEEN','steps':[],'receipt':None}}}}
    game.log('medicine_fixed_visit',box_id=c['box_id'],action_days=1)


def handle(game,args,eid='EV19'):
    cfg=cases.CONFIG.get(eid,{'receiver':DESTINATION,'protected':'暮汀医舍已实际接收原药箱，供原定病人治疗','exploited':'原药箱已被转卖，原定病人错过救治机会，本委托不能撤销'})
    s=game.s; c=cases.get(s,eid); check(c['enabled'],'请新建对应事件或全部案件试验档。')
    check(args,'medicine return CONFIRM / trade CONFIRM / followup on/off / visit CONFIRM')
    action=args[0]
    if action in ('followup','visit'):
        check(s['phase']=='TOWN','续办需要在城镇整备。')
        check(c['encountered'] and c['state'] not in TERMINAL,'仅已遇见且未交割的原委托可续办。')
        if action=='followup':
            check(len(args)==2 and args[1] in ('on','off'),'medicine followup on/off')
            cases.direct(s,eid,args[1]=='on')
            return '已更新原案件定向续办，每趟只定向一项，不增加事件地点。'
        check(args==['visit','CONFIRM'],'medicine visit CONFIRM：固定接洽，归城1日，无普通战斗或奖励。')
        from rescue import confirm_day
        confirm_day(s,['CONFIRM'])
        if eid=='EV19':visit(game)
        else:cases.fixed_visit(game,eid)
        return '已到原接洽现场，原委托仍未交割；本次归城计1日。'
    game.noncombat()
    check(s['site'] in game.manifest_region['events'] and game.manifest_region['events'][s['site']]['event_id']==eid,'请到原接洽现场现场。')
    check(game.current['events'][s['site']]['state']!='DECLINED','本趟已放弃接手，可归城后续办。')
    cases.seen(game,eid);check(c['state'] not in TERMINAL,'原案件已交割，不能重复送医或出售。')
    binding=game.manifest_region['events'][s['site']]
    options={o['option_id']:o for o in game.cat.events[eid]['options']}
    if action=='return':
        check(args==['return','CONFIRM'],'确认后全队立即返城送医，放弃剩余遭遇与'+game.cat.events[eid]['story_trade']['reward_text']+'报价；追加CONFIRM。')
        check('HUMANITY' in binding['enabled_options'],'本次地点未提供返城送医服务。')
        path=clear_path(game,c['active_scene'])
        # One atomic command: no persistent promise that allows continued exploration.
        game.settle_return('MEDICINE_RETURN')
        receipt={'id':eid+'-PROTECTED','object_id':c['box_id'],'box_id':c['box_id'],'destination':cfg['receiver'],
                 'path':path,'transfer':[cases.CONFIG[eid]['site_name'] if eid in cases.CONFIG else '集运棚','区域入口I','本次返城护运',cfg['receiver']],
                 'expedition_no':s['expedition_no'],'day':s['day'],'settlement_id':s['last_settlement_id']}
        cases.protect(game,eid,receipt,custody=cfg['protected'])
        cases.update_scene(game,eid,'RESOLVED',{'option':'PROTECTED','target':cfg['receiver'],'plan':None})
        s['summary'].setdefault('case_deliveries',{})[eid]=deepcopy(receipt)
        if eid=='EV19':s['summary']['medicine_delivery']=deepcopy(receipt)
        game.log('medicine_delivered',receipt=deepcopy(receipt))
        return (options['HUMANITY']['result_text']+' 本趟远征已结束。'
                ' '+cases.protect_reward_text(game,eid)
                +' 庇护账已更新：回城输入 shelter 查看已保全/已交割案件。')
    if action=='trade':
        check(args==['trade','CONFIRM'],options['EXPLOIT']['confirmation_text'])
        check('EXPLOIT' in binding['enabled_options'],'本次地点不能交割原委托。')
        spec=game.cat.events[eid]['story_trade']
        cases.issue_trade(game,eid,custody=cfg['exploited'],
                 receipt={'id':eid+'-EXPLOITED','box_id':c['box_id'],'expedition_no':s['expedition_no'],'day':s['day']})
        cases.update_scene(game,eid,'RESOLVED',{'option':'EXPLOITED','target':'现场交易方','plan':None})
        game.log('medicine_trade_accepted',receipt=deepcopy(c['receipt']),credit=deepcopy(c['trade_credit']))
        return options['EXPLOIT']['result_text']
    raise ValueError('未知返城案件操作。送医必须全队立即返城，不能分队护送或装药后继续探索。')


def public(game):
    s=game.s; c=s['medicine']
    if not c['enabled'] or not c['encountered']:return None
    at_scene=s['phase']=='EXPLORE' and s['site'] in game.manifest_region['events'] and game.manifest_region['events'][s['site']]['event_id']=='EV19'
    opened=at_scene and game.current['events'][s['site']]['state']!='DECLINED' and c['state'] not in TERMINAL
    text=c['custody']+'。'; credit=c['trade_credit']
    if credit:text+='80铜＋8结晶'+('已兑现。' if credit['redeemed'] else '待下次城镇结算兑现，途中不可用。')
    return {'text':text,'scene':scene_text(game),'open':opened,
            'can_followup':s['phase']=='TOWN' and c['state'] not in TERMINAL,'directed':s['directed_medicine'],
            'trade_warning':next(o['confirmation_text'] for o in game.cat.events['EV19']['options'] if o['option_id']=='EXPLOIT')}
