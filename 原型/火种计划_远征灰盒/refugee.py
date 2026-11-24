"""EV03 vertical slice: real handoff, finite supplier credit, persistent person."""
from collections import deque
from copy import deepcopy
import cases
import escort
import event_memory
from joint_sampling_model import digest

TERMINAL = cases.TERMINAL
LAYOUT = {'template_id':'EV03-VISIT', 'name':'避难者续办接洽处',
          'nodes':[{'id':'I','name':'护运站接收口'},{'id':'A','name':'避难者接洽处'}],
          'edges':[['I','A']], 'safe_receiver_site':'I'}


def check(condition, message):
    if not condition: raise ValueError(message)


def initialize(s, enabled):
    s['refugee']={**cases.common(enabled), 'pending':None,
                  'person_id':'EV03-PORTER-01', 'whereabouts':{'location':'原工班附近的隐蔽哨棚','custodian':'原护运接应人','status':'WAITING_CONTACT'}}
    s['private_case_factors']={}
    s['directed_refugee']=False


def profile(eid):
    return cases.CONFIG[eid] if eid!='EV03' else {'receiver':'暮汀接收站','subject':'搬运工','protected':'暮汀接收站已安置搬运工','exploited':'搬运工已被带回私牢','site_name':'原接应处','object_ids':['EV03-PORTER-01']}


def source_options(game, eid='EV03'):
    return {o['option_id']:o for o in game.cat.events[eid]['options']}


def seen(game, eid='EV03'):
    cases.seen(game,eid,receiver='I')


def scene(game, eid='EV03'):
    game.noncombat(); c=cases.get(game.s,eid)
    check(c['enabled'] and game.s['site'] in game.manifest_region['events']
          and game.manifest_region['events'][game.s['site']]['event_id']==eid,'请到避难者所在的事件现场。')
    check(game.current['events'][game.s['site']]['state']!='DECLINED','本趟已明确放弃接手，可归城后定向续办。')
    seen(game,eid)
    return c


def clear_path(game, anchor):
    """An actual existing, cleared route; no crossing an unseen enemy."""
    rid=anchor['region']; start=anchor['site']
    layout=game.cat.layouts[game.s['manifest']['regions'][rid]['template_id']]
    check(layout.get('safe_receiver_site')=='I','此场地缺少真实接收站。')
    queue=deque([(start,[start])]);seen_nodes={start}
    encounters=game.s['manifest']['regions'][rid]['encounters']
    while queue:
        node,path=queue.popleft()
        if node=='I':return path
        if node in encounters and node not in game.s['regions'][rid]['cleared']:continue
        for a,b in layout['edges']:
            nxt=b if a==node else a if b==node else None
            if nxt and nxt not in seen_nodes:seen_nodes.add(nxt);queue.append((nxt,path+[nxt]))
    raise ValueError('返回接收站的道路仍有未清敌阵，不能交付或安全早返。')


def update_scene(game, state, receipt=None, eid='EV03'):
    cases.update_scene(game,eid,state,receipt)


def complete(game, receiver, path, eid='EV03'):
    s=game.s;c=cases.get(s,eid)
    check(c['state']=='PROTECTION_PENDING','没有待交付的避难者。')
    pending=c['pending']
    if pending and pending.get('escort_id'):
        r=next(r for r in s['escort_receipts'] if r['id']==pending['escort_id'])
        check(r['status']=='IN_TRANSIT','护送记录已处理。');r['status']='SAFE_EXIT_LOCKED'
    c['receipt']={'id':eid+'-PROTECTED','receiver':profile(eid)['receiver'],'relay':receiver,'path':path,
                   'person_id':c['person_id'], 'person_ids':profile(eid)['object_ids'], 'whole_group_received':True, 'transfer':['现场','区域入口I','既有护运转送',profile(eid)['receiver']],
                   'destination':profile(eid)['receiver'],
                   'expedition_no':s['expedition_no'],'day':s['day'],'mode':pending['mode'] if pending else 'RETURN'}
    cases.protect(game,eid,c['receipt'],pending=None,whereabouts={'location':profile(eid)['receiver'],'custodian':profile(eid)['receiver'],'status':'ACCEPTED_IN_TOWN'})
    update_scene(game,'RESOLVED',{'option':'PROTECTED','target':profile(eid)['receiver'],'plan':None},eid)
    if eid!='EV03':c['custody']=profile(eid)['protected']
    game.log('refugee_received',receipt=deepcopy(c['receipt']))


def before_settlement(game, success, eid='EV03'):
    s=game.s;c=cases.get(s,eid);p=c['pending']
    if not p:
        if c['encountered'] and c['state'] not in TERMINAL:
            c['whereabouts']={'location':'原区域轮换接应班的临时隐蔽处','custodian':'原案件接应人续接联络','status':'FOLLOWUP_NEEDED'}
        return
    if success:
        complete(game,'暮汀护运站',p['path'],eid)
    else:
        if p.get('escort_id'):
            r=next(r for r in s['escort_receipts'] if r['id']==p['escort_id'])
            r['status']='HANDOFF_FAILED'
            for mid in r['member_ids']:
                m=next(m for m in s['escorted'] if m['instance_id']==mid)
                m.pop('escort_injury',None);s['escorted'].remove(m);s['party'].append(m)
            s['escort_reserved_cost']-=r['reserved_cost']
        c['pending']=None  # Same person remains an unresolved case, no sale or score.
        c['whereabouts']={'location':'途中失散后回到原接应关系的临时掩蔽处','custodian':'原案件接应人','status':'HANDOFF_INTERRUPTED'}
        if eid!='EV03':c['custody']=profile(eid)['subject']+'已由原接应关系重新照应，仍待实际送达'
        game.log('refugee_handoff_interrupted',custody=deepcopy(c['whereabouts']),anchor=deepcopy(c['anchor']))


def redeem(game):
    return cases.redeem(game,'EV03')


def visit(game, eid='EV03'):
    if eid!='EV03':return cases.fixed_visit(game,eid)
    """Dedicated safe follow-up when a random route does not serve the old case.

One action day on return, no invented supply fee, combats, XP or ordinary loot.
"""
    s=game.s;c=cases.get(s,eid);game.validate_deployment()
    rid=c['anchor']['region']
    binding={'event_id':eid,'enabled_options':['HUMANITY','PASS'] if c['state']=='PROTECTION_PENDING' else ['HUMANITY','EXPLOIT','PASS'],
             'disabled_options':{},'reserved_debits':{},
             'site_lighting':deepcopy(game.cat.events[eid]['site_lighting'])}
    manifest={'version':'EV03-VISIT-1.0','profile':'SHORT','start':rid,'target':rid,'paths':[[rid]],
              'regions':{rid:{'template_id':LAYOUT['template_id'],'events':{'A':binding},'encounters':{},'combat_rewards':{}}},
              'caps':{},'departure_supply_cost':0,'choice_policy':{'authoring_gate':'FIXED_CASE_NO_ORDINARY_REWARDS'}}
    manifest['manifest_sha256']=digest(manifest)
    s.update(mission='CASE_VISIT',manifest=manifest,request={'fixed_case':eid},region=rid,site='I',phase='EXPLORE',visited_regions=[rid])
    s['regions']={rid:{'cleared':[],'seen':['I'],'revealed_battles':[],'station_used':False,'camp_used':False,
                       'deployed_here':[],'variant':None,'events':{'A':{'state':'UNSEEN','steps':[],'receipt':None}}}}
    game.log('refugee_fixed_visit',anchor=deepcopy(c['anchor']),action_days=1,supply_cost=0)


def handle(game,args, eid='EV03'):
    if args and args[0].upper() in cases.ALL_IDS:
        target=args[0].upper()
        if target!='EV03':return cases.handle(game,[target]+args[1:])
        args=args[1:]
    if len(args)>=2 and args[0].upper() in ('FOLLOWUP','VISIT') and args[1].upper() in cases.ALL_IDS:
        target=args[1].upper()
        if target!='EV03':return cases.handle(game,[target,args[0].lower()]+args[2:])
        args=[args[0].lower()]+args[2:]
    s=game.s;c=cases.get(s,eid);check(c['enabled'],'case 仅处理 EV03（避难者）；其他案件用 case followup EVxx on/off、case visit EVxx CONFIRM，或 event EVxx ...。')
    check(args,'case escort 07 CONFIRM / receive CONFIRM / return CONFIRM / trade CONFIRM / followup on / visit CONFIRM')
    action=args[0]
    if action in ('followup','visit'):
        check(s['phase']=='TOWN','定向续办需在城镇整备。')
        check(c['encountered'] and c['state'] not in TERMINAL,'仅已遇见但尚未交割的同一案件可续办。')
        if action=='followup':
            check(len(args)==2 and args[1] in ('on','off'),'case followup on/off')
            cases.direct(s,eid,args[1]=='on')
            return '已更新下一趟定向续办；不额外添加事件地点。'
        check(args==['visit','CONFIRM'],'case visit CONFIRM：固定续办，归城计1行动日，无普通战斗和奖励。')
        from rescue import confirm_day
        confirm_day(s,['CONFIRM']);visit(game,eid);return '已到续办接洽处，回城时计1行动日。'
    if action=='receive':
        game.noncombat()
        check(args==['receive','CONFIRM'],'case receive CONFIRM：沿已清道路完成交接。')
        check(c['pending'] and c['pending']['mode']=='ESCORT','没有正在护送的避难者。')
        path=clear_path(game,c['active_scene'])
        complete(game,c['active_scene']['region']+'接收站I',path,eid)
        return (source_options(game,eid)['HUMANITY']['result_text']
                +' '+cases.protect_reward_text(game,eid)
                +' 庇护账已更新：回城输入 shelter 查看已保全/已交割案件。')
    c=scene(game,eid)
    check(c['state'] not in TERMINAL,'此人的去向已经确定，不能重复交付或交易。')
    if action=='trade':
        check(len(args) in (2,3) and args[-1]=='CONFIRM',source_options(game,eid)['EXPLOIT']['confirmation_text']+' 使用 case trade CONFIRM 明确确认。')
        check(c['state']=='OPEN','已开始保全委托，不能再交给管事。')
        check('EXPLOIT' in game.manifest_region['events'][s['site']]['enabled_options'],'本次为待办保全，只能继续交付。')
        spec=game.cat.events[eid]['story_trade']
        c['receipt']={'id':eid+'-EXPLOITED','counterparty':'现场管事','expedition_no':s['expedition_no'],'day':s['day']}
        cases.issue_trade(game,eid,c['receipt'],args[1].split(',') if len(args)==3 else [])
        c['whereabouts']={'location':'私牢' if eid=='EV03' else profile(eid)['exploited'],'custodian':'现场交易方','status':'IRREVERSIBLE_HANDOVER'}
        if eid!='EV03':c['custody']=profile(eid)['exploited']
        update_scene(game,'RESOLVED',{'option':'EXPLOITED','target':'现场交易方','plan':None},eid)
        game.log('refugee_trade_accepted',receipt=deepcopy(c['receipt']),credit=deepcopy(c['trade_credit']))
        return source_options(game,eid)['EXPLOIT']['result_text']
    if action=='escort':
        check(len(args)==3 and args[2]=='CONFIRM','case escort 预备队员ID CONFIRM')
        check(c['pending'] is None,'已派出护送者，请完成交接。')
        leader=game.member(args[1]);check(leader['instance_id'] in escort.preview(game)['leaders'] and not leader['unit_id'].startswith('PET'),'需一名可行动人类预备队员。')
        check(any(m is not leader and m['hp']>0 and m['erosion']<100 and m['injury_days']==0 and not m['unit_id'].startswith('PET') for m in s['party']),'余队至少保留一名可行动人类；可选择全队提前返城。')
        path=clear_path(game,c['active_scene'])
        receipt=escort.send(game,[leader],leader,status='IN_TRANSIT',purpose=eid)
        c.update(state='PROTECTION_PENDING',pending={'mode':'ESCORT','escort_id':receipt['id'],'path':path})
        c['whereabouts']={'location':'经入口I转送'+profile(eid)['receiver']+'途中','custodian':leader['instance_id'],'status':'IN_TRANSIT'}
        if eid!='EV03':c['custody']=profile(eid)['subject']+'由'+leader['instance_id']+'护送途中，尚未接收'
        update_scene(game,'ACTIVE',eid=eid)
        return '护送者已离队，尚未完成交接。使用“完成接收站交接”后才记为获救；本趟Cost不退。'
    if action=='return':
        check(args==['return','CONFIRM'],'case return CONFIRM：全队提前结束本趟，安全归城交付。')
        path=clear_path(game,c['active_scene'])
        if c['pending'] is None:c.update(state='PROTECTION_PENDING',pending={'mode':'RETURN','path':path})
        game.settle_return('REFUGEE_RETURN')
        return ('全队提前归城，'+profile(eid)['receiver']+'已实际接收'+profile(eid)['subject']+'。'
                ' '+cases.protect_reward_text(game,eid)
                +' 庇护账已更新：回城输入 shelter 查看已保全/已交割案件。')
    raise ValueError('未知避难者操作。')


def public(game):
    s=game.s;c=s['refugee']
    if not c['enabled'] or not c['encountered']:return None
    text={'OPEN':'搬运工尚未答应任何一方。',
          'PROTECTION_PENDING':'保全委托尚未完成，不能再交给管事。',
          'PROTECTED':'已由护运班转送暮汀接收站，搬运工已安置。他把石牌留在门外；不会再次成为待救对象。',
          'EXPLOITED':'搬运工已被带回私牢，不能再由本委托赎回。'}[c['state']]
    text+=' 当前去向：'+c['whereabouts']['location']+'；接洽方：'+c['whereabouts']['custodian']+'。'
    if c['pending']:text+=' 护送者正在前往接收站，尚未获安全交接确认。'
    if c['trade_credit']:text+=' 64铜＋4补给'+('已由镇内货仓兑现。' if c['trade_credit']['redeemed'] else '待下次城镇结算兑现；途中不能使用。')
    at_scene=s['phase']=='EXPLORE' and s['site'] in game.manifest_region['events'] and game.manifest_region['events'][s['site']]['event_id']=='EV03'
    closed=at_scene and game.current['events'][s['site']]['state']=='DECLINED'
    return {'text':text,'at_scene':at_scene,'open':at_scene and not closed and c['state'] not in TERMINAL,
            'can_trade':at_scene and not closed and c['state']=='OPEN','in_transit':bool(c['pending']),
            'can_followup':s['phase']=='TOWN' and c['state'] not in TERMINAL,
            'directed':s['directed_refugee'],'leaders':escort.preview(game)['leaders'],
            'scene':scene_text(game),'trade_warning':source_options(game)['EXPLOIT']['confirmation_text']}


def scene_text(game, eid='EV03'):
    if eid!='EV03':return cases.scene_text(game,eid)
    c=cases.get(game.s,eid)
    if c['anchor'] and c['anchor']['expedition_no']!=game.s['expedition_no']:
        return ('原接应人重新联系上同一名搬运工。当前去向：'+c['whereabouts']['location']+
                '。他还没有在暮汀获得安置；本次继续办理实际转送，不重复原先逃出私牢的场景。')
    return game.cat.events[eid]['scene']
