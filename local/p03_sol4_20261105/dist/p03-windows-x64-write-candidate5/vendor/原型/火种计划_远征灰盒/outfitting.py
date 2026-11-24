"""Paid workshop branches and expedition services, with a shared daily budget."""
from copy import deepcopy
import workshop


def check(ok,message):
    if not ok:raise ValueError(message)


def initialize(game):
    game.s.update(workshop_branch=None,branch_history=[],active_refit=None,
                  town_services={},outfit_orders={},active_outfit=None)


def active(game):return game.s['outfit_orders'].get(game.s['active_outfit'])


def today(game):return [r for r in game.s['town_services'].values() if r['day']==game.s['day']]


def price(game,kind,base):
    rows=today(game)
    check(len(rows)<2,'本行动的两项服务已用完；下次实际行动结算后恢复，不靠等待刷新。')
    check(not any(r['kind']==kind for r in rows),'同一行动不能重复购买同类服务；防御和药箱同属工坊整备。')
    extra={}
    if rows:
        rule=game.cat.rules['second_service']
        import facilities
        extra={'copper':rule['council_level_3_extra_copper'] if facilities.level(game,'council')>=3 else rule['extra_copper'],'supply':rule['extra_supply']}
    paid=deepcopy(base)
    for k,v in extra.items():paid[k]=paid.get(k,0)+v
    return paid,extra


def pay(game,oid,kind,base,request):
    s=game.s;check(oid not in s['town_services'],'服务订单ID已被使用。')
    paid,extra=price(game,kind,base)
    check(all(s['bank'][k]>=v for k,v in paid.items()),f'已入库资源不足，合计需要{paid}（含第二服务附加费{extra}）。')
    for k,v in paid.items():s['bank'][k]-=v
    import facilities
    s['town_services'][oid]={'council_level':facilities.level(game,'council'),'id':oid,'kind':kind,'day':s['day'],'slot':len(today(game))+1,
        'request':deepcopy(request),'base':base,'extra':extra,'paid':paid,'settled_by':None}
    game.log('town_service_paid',order=oid,kind_name=kind,paid=paid,preparation_spent=int(bool(extra)))


def specification(level,branch,mode):
    check(level>=1,'需要已竣工的一级工坊。')
    check(mode in ('defense','medicine'),'整备类型为defense（当趟双防）或medicine；旧shield服务已替换。')
    if mode=='defense':
        return {'mode':mode,'amount':10 if level>=2 and branch=='A' else 6,
                'target_cap':3 if level>=3 and branch=='A' else 2,'scope':'expedition_all_battles'}
    check(mode=='medicine' and level>=2 and branch=='B','药箱整备需要工坊二级或三级B支。')
    return {'mode':mode,'fraction':.4,'uses':2 if level>=3 else 1}


def targets(game,keys,cap):
    people=[game.member(k) for k in keys.split(',')]
    ids=[m['instance_id'] for m in people]
    check(1<=len(ids)<=cap and len(set(ids))==len(ids),f'请选择1至{cap}名不同队员。')
    check(all(m in game.s['party'] and m['hp']>0 and m['injury_days']==0 for m in people),'整备对象须为健康的随行队员，可在出发前免费改选。')
    return ids


def describe(game):
    s=game.s;row=active(game)
    text=f"工坊Lv{s['workshop_level']}，分支{s['workshop_branch'] or '未选（二级后可选A/B）'}；本行动服务{len(today(game))}/2。"
    import facilities
    extra_copper=2 if facilities.level(game,'council')>=3 else 4
    text+=f'\n整备4铜＋1公共结晶；第二项不同服务另加{extra_copper}铜＋1补给、消耗1准备额。制药、建筑和装备加工不占服务位。'
    text+='\nA：两人物防和魔防各+10，三级三人；B：首个补给站恢复40%，三级前两个，仍可选基础两人双防各+6。防御整趟每战自动生效，轮换上阵也有效；药箱只在有效补给站治疗时计次。'
    text+='\n先选分支不收费；更换用refit，8铜＋2结晶、下一行动结算完成并占一项服务。已付款整备按购买时等级冻结，不随升级或改修增强。'
    if s['active_refit']:text+='\n改修待完成：'+s['active_refit']
    if row:text+=f"\n整备{row['id']} {row['status']}，效果{row['spec']}，对象{row['targets']}，已用补给站{len(row['stations'])}；已应用{len(row['battles'])}场战斗。"
    else:text+='\n没有待出发或生效中的整备。'
    return text


def handle(game,args):
    s=game.s
    if args==['status']:return describe(game)
    check(s['phase']=='TOWN','整备与分支操作需要城镇，状态可随时查看。')
    check(args,'outfit status / branch A/B CONFIRM / quote defense/medicine / buy 模式 对象或- 订单ID CONFIRM / targets 对象 / refit A/B 订单ID CONFIRM')
    action=args[0]
    if action=='branch':
        check(len(args)==3 and args[1] in ('A','B') and args[2]=='CONFIRM','outfit branch A/B CONFIRM')
        check(s['workshop_level']>=2,'二级工坊竣工后才能选择分支。')
        if s['workshop_branch']==args[1]:return '当前已是该分支，不重复选择。'
        check(s['workshop_branch'] is None,'已有分支；更换需付费改修，不可免费反复切换。')
        s['workshop_branch']=args[1];s['branch_history'].append({'branch':args[1],'day':s['day'],'source':'initial'})
        game.log('workshop_branch_selected',branch=args[1]);return '已选择分支，未自动购买任何远征整备。'
    if action=='quote':
        check(len(args)==2,'outfit quote defense/medicine')
        spec=specification(s['workshop_level'],s['workshop_branch'],args[1]);paid,extra=price(game,'outfit',{'copper':4,'crystal':1})
        return f'本次效果{spec}；总费用{paid}，含附加费{extra}。绑定下一次出发，归城清除；防御可在出发前改选对象，付款后不退款。'
    if action=='targets':
        row=active(game);check(len(args)==2 and row and row['status']=='READY' and row['spec']['mode']=='defense','仅待出发防御整备可改选对象。')
        row['targets']=targets(game,args[1],row['spec']['target_cap']);game.log('outfit_retargeted',order=row['id'],targets=row['targets'][:]);return '已改选，不重扣费、不改变效果。'
    if action=='refit':
        check(len(args)==4 and args[1] in ('A','B') and args[3]=='CONFIRM','outfit refit A/B 订单ID CONFIRM')
        branch,oid=args[1:3];workshop.order_id(oid);request={'branch':branch}
        old=s['town_services'].get(oid)
        if old:
            check(old['kind']=='refit' and old['request']==request,'同一服务订单ID不能用于不同请求。');return '沿用原改修订单，不重复收费或改修。'
        check(s['workshop_level']>=2 and s['workshop_branch'] and s['workshop_branch']!=branch,'需要已有不同的二级以上工坊分支。')
        check(s['active_refit'] is None,'已有待完成的改修。')
        pay(game,oid,'refit',{'copper':8,'crystal':2},request);s['active_refit']=oid
        return '已付费改修；下一行动结算完成，现有分支及已付款整备保持。'
    check(action=='buy' and len(args)==5 and args[-1]=='CONFIRM','outfit buy defense 01,02 订单ID CONFIRM / outfit buy medicine - 订单ID CONFIRM')
    mode,keys,oid=args[1:4];workshop.order_id(oid);request={'mode':mode,'targets_input':keys}
    old=s['town_services'].get(oid)
    if old:
        check(old['kind']=='outfit' and old['request']==request,'同一服务订单ID不能用于不同请求。');return '沿用原整备订单，不重复付款或补充次数。'
    check(active(game) is None,'已有待出发整备；不能再购买另一套叠加。')
    spec=specification(s['workshop_level'],s['workshop_branch'],mode)
    ids=targets(game,keys,spec['target_cap']) if mode=='defense' else []
    check(mode=='defense' or keys=='-','药箱对有效补给站治疗生效，对象填-。')
    pay(game,oid,'outfit',{'copper':4,'crystal':1},request)
    s['outfit_orders'][oid]={'id':oid,'status':'READY','level':s['workshop_level'],'branch':s['workshop_branch'],
        'spec':spec,'targets':ids,'departed_targets':None,'expedition':None,'battles':[],'stations':[],
        'expires_settlement':None}
    s['active_outfit']=oid;return '已购买整备，绑定下一次实际出发（包括救援和固定回访）；未出发的休整不会消耗效果。'


def depart(game):
    row=active(game)
    if not row:return
    check(row['status']=='READY','整备已绑定其他出发。')
    # Moving a target to the home roster is legal; it receives no effect this trip.
    row.update(status='ACTIVE',expedition=game.s['expedition_no'],departed_targets=row['targets'][:])
    game.log('outfit_departed',order=row['id'],expedition=row['expedition'])


def start_battle(game,battle):
    row=active(game)
    if not row or row['status']!='ACTIVE' or row['spec']['mode']!='defense':return
    if battle.get('outfit_receipt'):
        check(battle['outfit_receipt']['order']==row['id'],'战斗已绑定其他整备。')
        return
    granted=[]
    for actor in battle['actors']:
        if actor['side']=='player' and actor['hp']>0 and actor['id'] in row['departed_targets']:
            actor['town_defense_bonus']=row['spec']['amount'];granted.append(actor['id'])
    receipt={'order':row['id'],'application':len(row['battles'])+1,'battle_id':battle['battle_id'],
             'spec':deepcopy(row['spec']),'targets':granted}
    row['battles'].append(deepcopy(receipt));battle['outfit_receipt']=receipt
    battle['events'].append({'type':'workshop_defense','tick':0,**deepcopy(receipt)})
    game.log('outfit_battle_applied',**receipt)


def station_rate(game):
    row=active(game)
    return .4 if row and row['status']=='ACTIVE' and row['spec']['mode']=='medicine' and len(row['stations'])<row['spec']['uses'] else .3


def station_used(game,receipts):
    row=active(game)
    if station_rate(game)==.4:
        row['stations'].append({'region':game.s['region'],'site':game.s['site'],'heal':deepcopy(receipts)})
        game.log('outfit_station_used',order=row['id'],used=len(row['stations']),effective_heal=deepcopy(receipts))


def advance(game):
    s=game.s
    if s['ending']:return
    for row in s['town_services'].values():
        if row['day']<s['day'] and row['settled_by'] is None:row['settled_by']=s['last_settlement_id']
    if s['active_refit']:
        row=s['town_services'][s['active_refit']]
        if row['day']<s['day']:
            s['workshop_branch']=row['request']['branch'];s['branch_history'].append({'branch':s['workshop_branch'],'day':s['day'],'source':row['id']})
            game.log('workshop_refit_completed',order=row['id'],branch=s['workshop_branch']);s['active_refit']=None
    row=active(game)
    if row and row['status']=='ACTIVE':
        row.update(status='EXPIRED',expires_settlement=s['last_settlement_id']);s['active_outfit']=None
        game.log('outfit_expired',order=row['id'],expedition=row['expedition'],settlement=s['last_settlement_id'])


def validate(game):
    s=game.s;history=s['branch_history'];check(s['workshop_branch'] in (None,'A','B'),'工坊分支无效。')
    check(s['workshop_branch']==(history[-1]['branch'] if history else None),'分支缺少选择或改修记录。')
    days={};services=s['town_services']
    base_costs={'care':{'supply':1},'outfit':{'copper':4,'crystal':1},'refit':{'copper':8,'crystal':2}}
    for oid,row in services.items():
        import facilities
        expected_base=base_costs.get(row['kind'])
        if expected_base is None and oid in facilities.state(game)['services']:expected_base=facilities.service_base(facilities.state(game)['services'][oid])
        check(row['id']==oid and expected_base is not None and row['base']==expected_base,'服务身份或基础费用无效。')
        day=row['day'];check(type(day) is int and 0<=day<=s['day'],'服务受理日期无效。');days.setdefault(day,[]).append(row)
        extra={} if row['slot']==1 else {'copper':game.cat.rules['second_service']['council_level_3_extra_copper'] if row.get('council_level',0)>=3 else game.cat.rules['second_service']['extra_copper'],'supply':game.cat.rules['second_service']['extra_supply']}
        paid=deepcopy(row['base'])
        for k,v in extra.items():paid[k]=paid.get(k,0)+v
        check(row['extra']==extra and row['paid']==paid,'服务附加费用无效。')
        check(row['settled_by']==(f"{s['id']}:D{day+1}" if day<s['day'] else None),'服务行动结算回执无效。')
        if row['kind']=='outfit':check(oid in s['outfit_orders'],'付费整备缺少订单。')
        if row['kind']=='refit':
            pending=(oid==s['active_refit']) or facilities.state(game)['refits'].get(oid,{}).get('status')=='READY'
            check(pending==(row['settled_by'] is None),'改修待办与回执不一致。')
    for rows in days.values():
        check(sorted(r['slot'] for r in rows)==list(range(1,len(rows)+1)) and len(rows)<=2 and len({r['kind'] for r in rows})==len(rows),'每日服务位重复或超支。')
    if history:
        check(history[0]['source']=='initial' and s['workshop_level']>=2,'分支初选记录无效。')
        for previous,row in zip(history,history[1:]):
            order=services.get(row['source'])
            check(order and order['kind']=='refit' and order['request']['branch']==row['branch'] and row['branch']!=previous['branch'] and row['day']==order['day']+1,'分支改修记录无效。')
    check(s['active_refit'] is None or s['active_refit'] in services,'改修订单不存在。')
    live=[]
    for oid,row in s['outfit_orders'].items():
        service=services.get(oid)
        check(service and service['kind']=='outfit' and row['id']==oid,'整备缺少付款凭据。')
        check(row['spec']==specification(row['level'],row['branch'],service['request']['mode']),'整备效果与付款等级不一致。')
        check(row['level']<=s['workshop_level'] and row['branch'] in (None,'A','B'),'整备等级或分支无效。')
        spec=row['spec'];ids=row['targets']
        check((spec['mode']=='defense' and 1<=len(ids)<=spec['target_cap'] and len(set(ids))==len(ids)) or (spec['mode']=='medicine' and not ids),'整备目标数量无效。')
        for number,receipt in enumerate(row['battles'],1):
            check(spec['mode']=='defense' and receipt['order']==oid and receipt['application']==number and receipt['spec']==spec,'整备战斗回执无效。')
            check(len(set(receipt['targets']))==len(receipt['targets']) and set(receipt['targets'])<=set(row['departed_targets'] or []),'战斗整备对象与出发绑定不一致。')
        stations=row['stations'];check(len(stations)<=(spec['uses'] if spec['mode']=='medicine' else 0),'药箱补给次数超额。')
        check(len({(r['region'],r['site']) for r in stations})==len(stations) and all(r['site']=='S' and r['heal'] for r in stations),'药箱消费回执无效。')
        if row['status'] in ('READY','ACTIVE'):live.append(oid)
        check(row['status'] in ('READY','ACTIVE','EXPIRED'),'整备状态无效。')
        if row['status']=='READY':check(row['expedition'] is None and row['departed_targets'] is None and not row['battles'] and not stations and row['expires_settlement'] is None,'未出发整备被提前消耗。')
        else:
            check(type(row['expedition']) is int and 1<=row['expedition']<=s['expedition_no'] and row['departed_targets']==ids,'整备出发绑定无效。')
            if row['status']=='ACTIVE':check(row['expedition']==s['expedition_no'] and row['expires_settlement'] is None,'生效整备跨趟或已过期。')
            else:
                receipt=row['expires_settlement'];prefix=s['id']+':D'
                check(isinstance(receipt,str) and receipt.startswith(prefix) and service['day']<int(receipt[len(prefix):])<=s['day'],'过期整备缺少合法结算凭据。')
    check(live==([s['active_outfit']] if s['active_outfit'] else []),'整备唯一占用不一致。')

    battle=s.get('battle')
    if battle:
        receipt=battle.get('outfit_receipt')
        if receipt:
            row=s['outfit_orders'].get(receipt['order'])
            check(row and row['status']=='ACTIVE' and row['spec']['mode']=='defense' and row['battles'][-1]==receipt,'当前战斗缺少有效整备回执。')
        for actor in battle['actors']:
            expected=receipt['spec']['amount'] if receipt and actor['side']=='player' and actor['id'] in receipt['targets'] else 0
            check(actor.get('town_defense_bonus',0)==expected,'当前战斗防御整备加成与付费回执不一致。')
