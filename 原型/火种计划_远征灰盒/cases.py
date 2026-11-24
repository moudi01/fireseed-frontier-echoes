"""Shared case identity, receipts, typed trade credits and LOCAL actions.

Legacy lifecycle modules keep transport rules; each case has one persisted owner.
All mutations run under Game.execute, including settlement callbacks.
"""
from copy import deepcopy
import equipment_rolls

TERMINAL = ('PROTECTED', 'EXPLOITED')
LEGACY = {'EV03':'refugee', 'EV09':'water', 'EV19':'medicine'}
LOCAL = {'EV25': {'object_id':'EV25-LUGGAGE', 'site_id':'RG05-EXISTING-CLAIM-STATION',
                 'receiver_id':'NPC-RG05-CLAIM-CLERK', 'receiver':'撤离站当班认领员',
                 'site_name':'原行李认领站', 'custody':'原行李由撤离站保管，等候当面核对封存',
                 'protected':'认领员已核对封存原行李，交本站例行护运送往暮汀寄存仓',
                 'exploited':'认领凭据已被收购人销毁，原物主失去追讨凭据，此事不能撤销'}}


# Content metadata only: existing mechanics execute all additional cases.
CONFIG = dict(LOCAL)
CONFIG.update({
 'EV05':dict(mode='RETURN',object_id='EV05-INJURED-WORKER',site_id='EV05-SHELTER',receiver_id='MUTING-HOSPITAL',receiver='暮汀医舍',site_name='伤工临时接应棚',custody='同伴正在接应棚照护原伤工并保管坍塌工单',protected='暮汀医舍已接收原伤工，坍塌工单按本人要求留在床边',exploited='矿主已隔绝伤工并销毁工单，这份证词无法恢复',subject='伤工与工单',action='return',action_label='立即返城送伤工就医'),
 'EV07':dict(mode='ESCORT',object_id='EV07-WORKERS',object_ids=['EV07-WORKER-01','EV07-WORKER-02'],site_id='EV07-HIDDEN-SHELTER',receiver_id='MUTING-OLD-INN',receiver='暮汀旧驿站',site_name='逃工原接应处',custody='原接应人正在隐蔽货棚照应两名逃工',protected='暮汀旧驿站已接收原两名逃工，分别登记铺位',exploited='原两名逃工已被重新锁进窑场，本轮无法追回',subject='两名逃工',action='escort',action_label='派预备队员护送两名逃工'),
 'EV12':dict(mode='LOCAL',object_id='EV12-ADDRESS-PAGE',site_id='EV12-CARAVAN',receiver_id='EV12-BOOK-OWNER',receiver='商队簿主',site_name='商队原登记簿接洽处',custody='簿主仍保管写有暮汀藏身地址的原页',protected='原地址页已在簿主面前烧毁，只留下没有住址的往来账',exploited='原地址页已交给收债人，藏身地址外泄不能收回',subject='地址页',action='destroy',action_label='当着簿主烧掉地址页'),
 'EV16':dict(mode='LOCAL',object_id='EV16-DEED',site_id='EV16-OLD-HOUSE',receiver_id='EV16-HEIR',receiver='原契继承人',site_name='旧林屋遗物接洽处',custody='原契仍在旧林屋，继承人随回收班清点遗物',protected='继承人已核对并收妥原契，放入返城行李',exploited='原契已被买地人销毁，家属失去不可重造的继承凭据',subject='原契',action='receive',action_label='把原契交给继承人'),
 'EV22':dict(mode='LOCAL',object_id='EV22-WORK-TICKETS',site_id='EV22-DUTY-ROOM',receiver_id='EV22-WORKER-DELEGATE',receiver='工人代表',site_name='回收班工票接洽处',custody='完整工票尚未交割，工人代表等待核对',protected='追索联已剪毁，领薪联已交还工人代表',exploited='完整工票已交回监工，追索不能由本委托撤销',subject='工票',action='release',action_label='剪毁追索联并交还领薪联'),
 'EV28':dict(mode='ESCORT',object_id='EV28-FAMILY-GROUP',object_ids=['EV28-FAMILY-GROUP'],site_id='EV28-BOAT-SHELTER',receiver_id='MUTING-PIER',receiver='暮汀码头接应处',site_name='家属原护运接洽处',custody='护运班暂时照应原家属群体，保留本次撤离船班座位',protected='暮汀码头已按原名单接收全部家属',exploited='原家属座位已卖给货主，本次撤离不能重做',subject='原名单上的家属',action='escort',action_label='派预备队员护送家属登船')})
CONFIG['EV25'].update(mode='LOCAL',subject='原行李',action='receive',action_label='当面交付并领取收据')
LOCAL = {eid:cfg for eid,cfg in CONFIG.items() if cfg['mode']=='LOCAL'}
ALL_IDS = tuple(sorted(set(LEGACY)|set(CONFIG)))

# Known-good controlled entry combinations (route, team, seed). These are
# fixtures for reaching the case, not natural-acquisition evidence. The app
# uses them only when the caller did not override route/team/seed.
CASE_DEFAULTS={
 'EV03':('R01','T01',11), 'EV05':('R01','T01',14),
 'EV07':('HUNT-MG01','T06',12), 'EV09':('HUNT-MG01','T02',13),
 'EV12':('R09','T06',13), 'EV16':('R09','T06',13),
 'EV19':('R07','T06',11), 'EV22':('R07','T06',15),
 'EV25':('R07','T06',27), 'EV28':('R07','T06',15),
}


def check(ok, message):
    if not ok: raise ValueError(message)


def common(enabled):
    return dict(enabled=enabled, state='OPEN', encountered=False, anchor=None,
                active_scene=None, receipt=None, trade_credit=None)


def initialize(s, enabled_ids):
    s['cases']={eid:{**common(eid in enabled_ids), 'custody':cfg['custody'],
                     'object_id':cfg['object_id'], 'person_id':cfg['object_id'], 'box_id':cfg['object_id'],
                     'pending':None, 'whereabouts':{'location':cfg['site_name'],'custodian':'原案件接应人','status':'WAITING_CONTACT'}} for eid,cfg in CONFIG.items()}
    s['directed_local']=None


def get(s, eid):
    return s[LEGACY[eid]] if eid in LEGACY else s['cases'][eid]


def entries(s):
    return [(eid,s[key]) for eid,key in LEGACY.items()] + list(s.get('cases',{}).items())


def has_directed_case(s):
    return any(s.get(key) for key in ('directed_refugee','directed_water','directed_medicine','directed_local'))


def guarantee_candidates(game):
    """Return every eligible unseen case when the pity threshold is due.

    The caller tries each candidate against the actual route; the first one the
    route can place wins. The threshold is deterministic: with zero cases met
    the guarantee is due on trip 2, with one on trip 4, and so on. It only
    applies to a natural campaign and never overrides an explicit follow-up.
    """
    s=game.s
    if not s.get('campaign') or s.get('phase')!='TOWN' or has_directed_case(s):return []
    all_rows=[(eid,c) for eid,c in entries(s) if c['enabled']]
    unseen=[eid for eid,c in all_rows if not c['encountered'] and c['state']=='OPEN']
    if not unseen:return []
    facts=set(s.get('unlocked_facts',[]))
    chapter=3 if 'CH2_COMPLETE' in facts else 2 if 'ST-104' in facts else 1
    eligible=sorted(eid for eid in unseen if game.cat.events[eid].get('min_chapter',1)<=chapter)
    if not eligible:return []
    seen=sum(1 for eid,c in all_rows if c['encountered'] or c['state'] in TERMINAL)
    return eligible if s.get('expedition_no',1)>=2*(seen+1) else []


def guarantee_due(game):
    """Display helper: the first candidate for the town status line."""
    rows=guarantee_candidates(game)
    return rows[0] if rows else None


def seen(game,eid,**extra):
    s=game.s;c=get(s,eid)
    if not c['enabled'] or s['site'] not in game.manifest_region['events']:return
    if game.manifest_region['events'][s['site']]['event_id']!=eid:return
    a=dict(expedition_no=s['expedition_no'],region=s['region'],site=s['site'],**extra)
    if c['anchor'] is None:c['anchor']=deepcopy(a)
    c.update(active_scene=a,encountered=True)
    if c['state']=='OPEN':equipment_rolls.ensure_quotes(game,eid)


def update_scene(game,eid,state,receipt=None):
    import event_memory
    a=get(game.s,eid)['active_scene']
    if not a or a['expedition_no']!=game.s['expedition_no']:return
    game.s['regions'][a['region']]['events'][a['site']].update(state=state,receipt=deepcopy(receipt))
    event_memory.record(game,a['region'],a['site'])


CASE_LETTER_SUPPLY=1
HIDDEN_BOOK='SB-Z01'


def protect(game,eid,receipt,**changes):
    s=game.s
    c=get(s,eid);check(c['state'] not in TERMINAL,'原案件已交割。')
    check(receipt['id']==game.cat.events[eid]['protection_receipt_id'],'接收回执与案件不符。')
    c.update(state='PROTECTED',receipt=deepcopy(receipt),**changes)
    s['private_case_factors'][eid]=10
    s['bank']['supply']=s['bank'].get('supply',0)+CASE_LETTER_SUPPLY
    c['reward_text']=f"回信谢礼：+{CASE_LETTER_SUPPLY}随队补给。"
    game.log('case_letter_reward',event=eid,supply=CASE_LETTER_SUPPLY)
    if all(get(s,other)['state']=='PROTECTED' for other in game.cat.rules['humanity']['event_ids']):
        stock=s.setdefault('book_stock',{})
        if stock.get(HIDDEN_BOOK,0)==0:
            stock[HIDDEN_BOOK]=1
            c['reward_text']+=' 十案齐全：获得隐藏技能书 SB-Z01（终局对策卡）。'
            game.log('hidden_book_awarded',book=HIDDEN_BOOK)


def protect_reward_text(game,eid):
    return get(game.s,eid).get('reward_text','')


def direct(s,eid,on):
    if on:
        for key in LEGACY.values():s['directed_'+key]=False
        s['directed_local']=None
    if eid in LEGACY:s['directed_'+LEGACY[eid]]=on
    else:s['directed_local']=eid if on else (None if s.get('directed_local')==eid else s.get('directed_local'))


def applicable_families(game):
    members=game.s['party']+game.s['home_roster']+game.s['captives']+game.s['escorted']
    kinds={m['unit_id'] for m in members}
    return [f['family_id'] for f in game.cat.loot['equipment_families'] if kinds.intersection(f['allowed_unit_ids'])]


def issue_trade(game,eid,receipt,families=(),**changes):
    c=get(game.s,eid);check(c['state']=='OPEN' and not c['trade_credit'],'已接手或交割，不能再次交易。')
    spec=game.cat.events[eid]['story_trade'];reward=deepcopy(spec['reward']);equipment=reward.get('equipment')
    allowed={'copper','crystal','supply','herb','fiber','iron','crystal_shard','equipment'}
    check(set(reward)<=allowed,'交易含尚未支持的资源。')
    for k,v in reward.items():
        if k!='equipment':check(isinstance(v,int) and v>=0,'交易数量无效。')
    gear=[]
    if equipment:
        check(len(families)==equipment['count'],'确认前须按装备件数选择家族。')
        for selection in families:
            family=selection.split(':')[0]
            check(family in applicable_families(game),'装备家族不适用于现有名册。')
            template=family+'-'+equipment['quality'];check(template in game.cat.gear,'装备品质或家族无效。');gear.append(template)
    else:check(not families,'本凭单不含装备，无须选择家族。')
    check(receipt['id']==eid+'-EXPLOITED','交易回执与案件不符。')
    quotes=equipment_rolls.selected_quotes(game,eid,families)
    credit={'equipment_quotes':quotes,'equipment_selections':list(families),'id':spec['trade_id'],'reward':reward,'redeemed':False,
            'equipment_templates':gear,'issued_day':game.s['day']}
    c.update(state='EXPLOITED',receipt=deepcopy(receipt),trade_credit=credit,**changes)


def redeem(game,eid):
    s=game.s;credit=get(s,eid)['trade_credit']
    if not credit or credit['redeemed']:return False
    # Entitlement cannot be claimed in the field or before a town settlement.
    if s['day']<=credit.get('issued_day',-1) or not s.get('last_settlement_id'):return False
    gear=credit.get('equipment_templates',[])
    capacity=s.get('gear_storage_capacity')  # None: existing greybox warehouse has no limit.
    if gear and capacity is not None and len(s['gear_storage'])+len(s['gear_bag'])+len(gear)>capacity:
        credit['waiting_reason']='装备库空位不足，整笔凭单保留，尚未发放任何部分';return False
    for key,value in credit['reward'].items():
        if key=='equipment':continue
        target=s['bank'] if key in ('copper','crystal','supply') else s['warehouse']
        check(key in target,'未知交易资源，拒绝部分兑现。');target[key]+=value
    import equipment
    credit['equipment_instance_ids']=[]
    for row in credit['equipment_quotes']:
        item=equipment.issue(game,row['template_id'],s['gear_storage'],
            {'kind':'story_trade','event':eid,'credit':credit['id'],'randomized':True,
             'quote_id':row['quote_id'],'pool_version':row['pool_version'],'form':row['form']},row['effect_ids'])
        credit['equipment_instance_ids'].append(item['instance_id'])
    credit.pop('waiting_reason',None)
    credit.update(redeemed=True,settlement_id=s['last_settlement_id'],day=s['day'])
    game.log(LEGACY.get(eid,'local')+'_trade_redeemed',event=eid,credit=deepcopy(credit))
    return True


def redeem_all(game):
    for eid,_ in entries(game.s):redeem(game,eid)


def layout(eid):
    return {'template_id':eid+'-VISIT','name':CONFIG[eid]['site_name'],
            'nodes':[{'id':'I','name':'返城接驳口'},{'id':'A','name':CONFIG[eid]['site_name']}],
            'edges':[['I','A']], 'safe_receiver_site':'I'}


def service(eid):
    cfg=CONFIG[eid]
    return {k:cfg[k] for k in ('object_id','site_id','receiver_id')}


def fixed_visit(game,eid):
    from joint_sampling_model import digest
    game.validate_deployment();s=game.s;rid=get(s,eid)['anchor']['region']
    binding={'event_id':eid,'enabled_options':['HUMANITY','PASS'] if get(s,eid)['state']=='PROTECTION_PENDING' else ['HUMANITY','EXPLOIT','PASS'],'disabled_options':{},
             'reserved_debits':{},'case_service':service(eid),
             'site_lighting':deepcopy(game.cat.events[eid]['site_lighting'])}
    manifest={'version':'LOCAL-VISIT-1.0','profile':'SHORT','start':rid,'target':rid,'paths':[[rid]],
              'regions':{rid:{'template_id':layout(eid)['template_id'],'events':{'A':binding},'encounters':{},'combat_rewards':{}}},
              'caps':{},'departure_supply_cost':0,'choice_policy':{'authoring_gate':'FIXED_LOCAL_NO_ORDINARY_REWARDS'}}
    manifest['manifest_sha256']=digest(manifest)
    s.update(mission='LOCAL_VISIT',manifest=manifest,request={'fixed_case':eid},region=rid,site='I',phase='EXPLORE',visited_regions=[rid])
    s['regions']={rid:{'cleared':[],'seen':['I'],'revealed_battles':[],'station_used':False,'camp_used':False,
                      'deployed_here':[],'variant':None,'events':{'A':{'state':'UNSEEN','steps':[],'receipt':None}}}}
    game.log('case_fixed_visit',event=eid,action_days=1)


def handle(game,args):
    check(len(args)>=2,'event EV25 receive/trade/visit CONFIRM；event EV25 followup on/off；event EVxx redeem')
    eid,action=args[:2];s=game.s
    check(eid in dict(entries(s)),'此案件尚未接入。');c=get(s,eid)
    check(c['enabled'],'请先新建对应事件试验档。')
    if action=='quote':
        check(len(args)==2 and s['phase']=='EXPLORE' and game.manifest_region['events'].get(s['site'],{}).get('event_id')==eid,'请到原案件现场查看报价。')
        check(c['state']=='OPEN' and game.current['events'][s['site']]['state']!='DECLINED','此现场已关闭或交割。')
        seen(game,eid);return equipment_rolls.describe(game,eid)
    if action=='redeem':
        check(len(args)==2 and s['phase']=='TOWN','凭单仅可在城镇整备重试兑现。')
        return '凭单已兑现。' if redeem(game,eid) else '尚无可兑现凭单，或库位仍不足；不会重复发放。'
    check(eid in CONFIG,'此案件使用现有护送、运水或药箱入口。')
    if CONFIG[eid]['mode']=='ESCORT':
        import refugee
        return refugee.handle(game,args[1:],eid)
    if CONFIG[eid]['mode']=='RETURN':
        import medicine
        return medicine.handle(game,args[1:],eid)
    cfg=CONFIG[eid]
    if action in ('followup','visit'):
        check(s['phase']=='TOWN' and c['encountered'] and c['state'] not in TERMINAL,'仅城内未交割原案件可续办。')
        if action=='followup':
            check(len(args)==3 and args[2] in ('on','off'),'event '+eid+' followup on/off')
            direct(s,eid,args[2]=='on');return '已更新原案件定向续办，不增加事件地点。'
        check(args==[eid,'visit','CONFIRM'],'固定接洽归城计1日，无普通战斗、奖励和出发费；追加CONFIRM。')
        fixed_visit(game,eid);return '已到原案件接洽处，交付后可返回入口归城。'
    game.noncombat()
    binding=game.manifest_region['events'].get(s['site'],{})
    check(binding.get('event_id')==eid,'请到原案件现场。')
    check(game.current['events'][s['site']]['state']!='DECLINED','本趟已明确放弃，归城后可续办。')
    seen(game,eid)
    options={o['option_id']:o for o in game.cat.events[eid]['options']}
    if action==cfg['action']:
        check(args==[eid,cfg['action'],'CONFIRM'],cfg['action_label']+'会放弃整笔收购报酬；追加CONFIRM。')
        if c['state']=='PROTECTED':return '原案件已完成，沿用原回执，不再交付或计数。'
        check(c['state']=='OPEN','已交割，不能改做另一选择。')
        check('HUMANITY' in binding['enabled_options'],'此现场没有可用的交付服务。')
        check(binding.get('case_service')==service(eid),'原物件或当班接收服务不匹配，不能签发收据。')
        receipt={'id':game.cat.events[eid]['protection_receipt_id'],**service(eid),
                 'action':cfg['action'], 'accepted':action!='destroy', 'witnessed':True, 'action_completed':True,'expedition_no':s['expedition_no'],'day':s['day']}
        receipt['object_state']={'destroy':'DESTROYED','release':'CLAIM_STUB_DESTROYED_PAY_STUB_RETURNED','receive':'ACCEPTED'}[action]
        protect(game,eid,receipt,custody=cfg['protected'])
        update_scene(game,eid,'RESOLVED',{'option':'PROTECTED','target':cfg['receiver'],'plan':None})
        game.log('local_case_received',event=eid,receipt=deepcopy(receipt))
        return (options['HUMANITY']['result_text']+' 队伍可继续本趟远征。'
                ' '+protect_reward_text(game,eid)
                +' 庇护账已更新：回城输入 shelter 查看已保全/已交割案件。')
    if action=='trade':
        check(len(args)>=3 and args[-1]=='CONFIRM',options['EXPLOIT']['confirmation_text'])
        check('EXPLOIT' in binding['enabled_options'],'此现场不能出售。')
        families=args[2].split(',') if len(args)==4 else []
        check(len(args) in (3,4),'event '+eid+' trade [家族列表] CONFIRM')
        issue_trade(game,eid,{'id':eid+'-EXPLOITED','day':s['day'],'object_id':cfg['object_id']},families,custody=cfg['exploited'])
        update_scene(game,eid,'RESOLVED',{'option':'EXPLOITED','target':'现场收购人','plan':None})
        game.log('local_case_trade',event=eid);return options['EXPLOIT']['result_text']
    raise ValueError('未知现场案件操作。')


def public(game):
    rows=[];s=game.s
    for eid,c in s.get('cases',{}).items():
        if not c['enabled'] or not c['encountered']:continue
        at=s['phase']=='EXPLORE' and game.manifest_region['events'].get(s['site'],{}).get('event_id')==eid
        opened=at and game.current['events'][s['site']]['state']!='DECLINED' and c['state'] not in TERMINAL
        cfg=CONFIG[eid];event=game.cat.events[eid];credit=c['trade_credit'];text=(c['whereabouts']['location']+'；'+c['whereabouts']['custodian'] if cfg['mode']=='ESCORT' else c['custody'])+'。'
        if credit:text+=event['story_trade']['reward_text']+('已兑现。' if credit['redeemed'] else '待城镇结算兑现。')
        rows.append({'id':eid,'name':event['name'],'text':text,'scene':scene_text(game,eid),'open':opened,
                     'mode':cfg['mode'],'action':cfg['action'],'action_label':cfg['action_label'],
                     'in_transit':bool(c.get('pending')),'can_trade':opened and c['state']=='OPEN',
                     'reward_text':event['story_trade']['reward_text'],
                     'equipment_count':event['story_trade']['reward'].get('equipment',{}).get('count',0),
                     'equipment_quality':event['story_trade']['reward'].get('equipment',{}).get('quality'),
                     'families':applicable_families(game),'equipment_quotes':equipment_rolls.public_quotes(game,eid),
                     'leaders':__import__('escort').preview(game)['leaders'],
                     'waiting_credit':bool(credit and not credit['redeemed'] and s['phase']=='TOWN'),
                     'can_followup':s['phase']=='TOWN' and c['state'] not in TERMINAL,
                     'directed':s.get('directed_local')==eid,
                     'trade_warning':next(o['confirmation_text'] for o in event['options'] if o['option_id']=='EXPLOIT')})
    return rows


def scene_text(game,eid):
    c=get(game.s,eid)
    if c['anchor'] and c['anchor']['expedition_no']!=game.s['expedition_no']:
        cfg=CONFIG[eid]
        return '原案件继续接洽：'+cfg['subject']+'。'+c['custody']+'。本次沿用原对象与原委托，不重新签发另一份交易。'+('护运班安排本次返城船班，并非原船一直等候。' if eid=='EV28' else '')
    return game.cat.events[eid]['scene']


def before_settlement(game,success):
    import refugee
    for eid,cfg in CONFIG.items():
        if cfg['mode']=='ESCORT':refugee.before_settlement(game,success,eid)
