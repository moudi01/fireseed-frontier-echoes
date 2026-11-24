"""Six-building logistics overlay; real action settlements own all progress."""
from copy import deepcopy
import construction
import outfitting
import town
import workshop

NAMES={'hospital':'医舍','lamp_store':'遗迹观测站','rescue_post':'搜救所','barracks':'营房','armory':'工坊','council':'镇务厅'}


def check(ok,text):
    if not ok:raise ValueError(text)


def initialize(game):
    game.s['facilities']={'levels':{k:0 for k in NAMES if k not in ('hospital','armory')},
        'branches':{k:None for k in NAMES if k!='armory'},'branch_history':[],
        'orders':{},'origins':{},'refits':{},'services':{},'veterans':[],'nursing':None,'scout':None}


def state(game):return game.s['facilities']
def level(game,key):
    return game.s['workshop_level'] if key=='armory' else game.s['hospital_level'] if key=='hospital' else state(game)['levels'][key]
def branch(game,key):return game.s['workshop_branch'] if key=='armory' else state(game)['branches'][key]
def set_level(game,key,value):
    if key=='hospital':game.s['hospital_level']=value
    else:state(game)['levels'][key]=value
def orders(game):return list(game.s['construction_orders'].values())+list(state(game)['orders'].values())
def ongoing(game):return [r for r in orders(game) if r['status']=='ACTIVE']
def workers(game):return 2 if level(game,'council')>=2 and branch(game,'council')=='A' else 1
def hospital_order(game):return next((r for r in ongoing(game) if r['building']=='hospital'),None)
def occupied(game):
    return len([r for r in ongoing(game) if not r.get('paused')])+int(game.s['hospital_progress'] is not None and not hospital_order(game))
def can_start(game):
    pending=any(r['status']=='READY' and r['building']=='council' and r['branch']=='B' for r in state(game)['refits'].values())
    return occupied(game)<(1 if pending else workers(game))
def training_ids(game):
    return {i for r in state(game)['services'].values() if r['kind']=='training' and r['status']=='READY' for i in r['targets']}
def injured_days(game,story=False,rescued=False):
    if story:return 1 if level(game,'hospital')>=2 and branch(game,'hospital')=='B' else 2 if level(game,'hospital') else 3
    return 1 if level(game,'hospital') or (rescued and level(game,'rescue_post')>=2 and branch(game,'rescue_post')=='A') else 2
def rescue_cost(game):return 0 if level(game,'rescue_post') else 1
def medical_cap(game):return 3 if level(game,'lamp_store') else 2


def gate(game,key,target,facts=None):
    facts=set(game.s['unlocked_facts'] if facts is None else facts)
    if target==1:return 'ST-101' in facts and (key!='armory' or 'ST-104' in facts)
    return ('ST-104' in facts or 'CH1_COMPLETE' in facts) if target==2 else 'CH2_COMPLETE' in facts


def build_cost(game,key,target):
    check(key in NAMES and target in (1,2,3),'建筑键或等级无效。')
    row=game.cat.rules['buildings'][key];i=target-1
    return {'copper':row['copper'][i],'crystal':row['crystal'][i]},row['progress'][i]


def pending_rush(game,oid):
    return any(r['kind']=='rush' and r['status']=='READY' and r['target']==oid for r in state(game)['services'].values())


def rush_credit(game,oid):
    return sum(r['amount'] for r in state(game)['services'].values() if r['kind']=='rush' and r['status']=='READY'
               and r['target']==oid and r['day']<game.s['day'])


def handle(game,args):
    s=game.s;f=state(game)
    if not args or args==['status']:return describe(game)
    check(s['phase']=='TOWN','建设和分支只能在城镇办理。')
    action=args[0]
    if action=='quote':
        check(len(args)==3,'facility quote 建筑键 等级')
        key=args[1];target=int(args[2]);cost,progress=build_cost(game,key,target)
        return f'{NAMES[key]}Lv{target}：{cost}，{progress}进度；前置满足{gate(game,key,target)}，空施工位{max(0,workers(game)-occupied(game))}。'
    if action=='build':
        check(len(args)==5 and args[-1]=='CONFIRM','facility build 建筑键 等级 订单ID CONFIRM')
        key=args[1];target=int(args[2]);oid=args[3];workshop.order_id(oid);cost,required=build_cost(game,key,target)
        request={'building':key,'target_level':target}
        old=next((r for r in orders(game) if r['id']==oid),None)
        if old:
            check(old['request']==request,'建设订单ID已用于不同请求。');return str(old)
        if key=='armory':return construction.handle(game,['start',str(target),oid,'CONFIRM'])
        check(can_start(game),'自然施工位已占用；镇务厅可提供暂停或双工地能力。')
        check(level(game,key)==target-1 and not any(r['building']==key for r in ongoing(game)),'须逐级建设；该楼不能重复开工。')
        check(gate(game,key,target),'章节前置未完成；三级只要求研究线开放，不预发研究交付。')
        check(all(s['bank'][k]>=v for k,v in cost.items()),'已入库铜或公共结晶不足。')
        for k,v in cost.items():s['bank'][k]-=v
        f['origins'].setdefault(key,level(game,key))
        row={'id':oid,'request':request,'building':key,'from_level':target-1,'target_level':target,'paid':cost,
             'required':required,'progress':0,'settlements':[],'credits':[],'created_day':s['day'],'status':'ACTIVE',
             'paused':False,'gate_facts':s['unlocked_facts'][:]}
        f['orders'][oid]=row
        if key=='hospital':s['hospital_progress']=required
        game.log('facility_build_started',order=deepcopy(row));return '施工已付款；后续真实行动结算推进。'
    if action in ('pause','resume','cancel'):
        check(len(args)==3 and args[-1]=='CONFIRM','facility pause/resume/cancel 订单ID CONFIRM')
        row=next((r for r in orders(game) if r['id']==args[1]),None);check(row,'没有该工地。')
        if action=='cancel' and row['status']=='CANCELLED':return '已有撤单回执。'
        check(row['status']=='ACTIVE','仅未完成工地可操作。')
        check(not pending_rush(game,row['id']),'本工地已付赶工，待本次行动结算后再操作。')
        if action=='pause':
            check(level(game,'council')>=1,'暂停需镇务厅一级。')
            if row.get('paused'):return '已经暂停。'
            check(sum(bool(r.get('paused')) for r in ongoing(game))<1,'最多保留一个暂停工地。')
            row['paused']=True
        elif action=='resume':
            if not row.get('paused'):return '已在施工。'
            check(can_start(game),'没有空自然施工位。');row['paused']=False
        elif row['building']=='armory':return construction.handle(game,['cancel',row['id'],'CONFIRM'])
        else:
            returned=construction.refund(row)
            for k,v in returned.items():s['bank'][k]+=v
            row.update(status='CANCELLED',refund=returned,cancelled_day=s['day'])
            if row['building']=='hospital':s['hospital_progress']=None
        game.log('facility_'+action,order=row['id']);return str(row)
    check(action in ('branch','refit'),'facility status / quote / build / pause / resume / cancel / branch / refit')
    check(len(args)==(4 if action=='branch' else 5) and args[-1]=='CONFIRM','facility branch 楼 A/B CONFIRM；facility refit 楼 A/B 订单ID CONFIRM')
    key,value=args[1:3];check(key in NAMES and value in ('A','B'),'未知建筑或分支。')
    if key=='armory':return outfitting.handle(game,[action,value]+args[3:])
    if action=='branch':
        check(level(game,key)>=2,'二级竣工后才可选分支。')
        if branch(game,key)==value:return '分支已选。'
        check(branch(game,key) is None,'已有分支，变更需付费改修。')
        f['branches'][key]=value;f['branch_history'].append({'building':key,'branch':value,'source':'initial','day':s['day']});return
    oid=args[3];workshop.order_id(oid);request={'building':key,'branch':value}
    if oid in s['town_services']:
        check(s['town_services'][oid]['request']==request and s['town_services'][oid]['kind']=='refit','服务订单ID冲突。');return '沿用改修回执。'
    check(level(game,key)>=2 and branch(game,key) and branch(game,key)!=value,'须已有不同分支。')
    check(not any(r['status']=='READY' for r in f['refits'].values()) and not s['active_refit'],'已有待完成改修。')
    if key=='council' and value=='B':check(occupied(game)<=1,'请先暂停或完成第二工地，再改为集中施工。')
    outfitting.pay(game,oid,'refit',{'copper':8,'crystal':2},request)
    f['refits'][oid]={'id':oid,**request,'day':s['day'],'status':'READY'};return '下一行动结算改修；既付服务效果保持。'


def service_base(row):
    if row['kind']=='training':return {'copper':row['unit_price']*sum(row['targets'].values()),'supply':sum(row['targets'].values())}
    return {'scout':{'copper':2},'rush':{'copper':4},'nursing':{'supply':1}}[row['kind']]


def service(game,args):
    s=game.s;f=state(game)
    if not args or args==['status']:return str(f['services'])
    check(s['phase']=='TOWN','服务需要城镇；探路揭示使用 scout。')
    quoting=args[0]=='quote'
    if quoting:
        check(len(args)==3,'service quote nursing/training/rush/scout 对象或-')
        args=[args[1],args[2],'SERVICE-QUOTE','CONFIRM']
    check(len(args)==4 and args[-1]=='CONFIRM','service nursing 队员列表 订单ID CONFIRM；training ID:经验[,ID:经验]；rush 工地ID；scout -')
    kind,selection,oid=args[:3];workshop.order_id(oid)
    check(kind in ('scout','rush','nursing','training'),'未知服务。')
    request={'selection':selection}
    if not quoting and oid in s['town_services']:
        check(s['town_services'][oid]['kind']==kind and s['town_services'][oid]['request']==request,'服务ID对应不同请求。');return '沿用原服务，不重复付款。'
    row={'id':oid,'kind':kind,'day':s['day'],'status':'READY','settlement':None}
    if kind=='scout':
        check(selection=='-' and f['scout'] is None,'已有待用探路，或参数应为-。')
        lv=level(game,'lamp_store');br=branch(game,'lamp_store')
        row.update(level=lv,branch=br,limit=2 if lv>=2 and br=='A' else 1,reveals=[],retargeted=False,expedition=None)
    elif kind=='rush':
        target=next((r for r in ongoing(game) if r['id']==selection),None)
        check(target and not target.get('paused') and target['required']-target['progress']>1,'须有正在施工、自然进度之外仍可加速的工地。')
        row.update(target=selection,level=level(game,'council'),branch=branch(game,'council'),amount=2 if level(game,'council')>=2 and branch(game,'council')=='B' else 1)
    elif kind=='nursing':
        lv=level(game,'hospital');br=branch(game,'hospital');check(lv>=2,'行前护理需医舍二级。')
        check(f['nursing'] is None,'已有待出发护理。')
        ids=outfitting.targets(game,selection,3 if br=='A' else 2)
        row.update(level=lv,branch=br,targets=ids,amount=10 if lv>=3 else 6,expedition=None,battle_id=None)
    else:
        lv=level(game,'barracks');br=branch(game,'barracks');check(lv>=1,'补训需营房一级。')
        selected={}
        for part in selection.split(','):
            key,n=part.rsplit(':',1);m=game.member(key);amount=int(n);iid=m['instance_id']
            check(iid not in selected and m in s['home_roster'] and m['injury_days']==0 and m['hp']>0 and m['erosion']<100,'补训者须为不同、就绪的留城成员。')
            check(iid in f['veterans'],'补训者须有实际出战记录。')
            selected[iid]=amount
        check(1<=len(selected)<=(2 if lv>=2 and br=='A' else 1),'补训人数超过分支能力。')
        check(all(1<=n<=(2 if lv>=2 and br=='B' else 1) for n in selected.values()),'每人经验数量超过分支能力。')
        facts=s['unlocked_facts'];cap=4 if 'CH3_COMPLETE' in facts else 3 if 'CH2_COMPLETE' in facts else 2 if 'ST-104' in facts or 'CH1_COMPLETE' in facts else 1
        seniors=[m for m in town.available(game) if m['instance_id'] in f['veterans']]
        teacher=max(seniors,key=lambda m:(m['level'],m['instance_id']),default=None)
        senior=teacher['level'] if teacher else 1;cap=min(cap,senior)
        for iid,n in selected.items():
            m=game.member(iid);remaining=sum(game.cat.rules['level']['experience_per_step'][m['level']-1:cap-1])-m['xp']
            check(m['level']<cap and n<=remaining,'补训不能超过实际老队员等级或章节上限；满经验者先正常升级。')
        row.update(level=lv,branch=br,targets=selected,cap=cap,unit_price=4 if lv>=3 else 6,
                   teacher=teacher['instance_id'],teacher_level=senior,gate_facts=facts[:])
    if quoting:
        paid,extra=outfitting.price(game,kind,service_base(row))
        return str({'effect':row,'total_cost':paid,'second_service_extra':extra,'next_settlement_day':s['day']+1})
    outfitting.pay(game,oid,kind,service_base(row),request);f['services'][oid]=row
    if kind in ('nursing','scout'):f[kind]=oid
    return '服务已付款并保存；下次实际行动生效，出发前护理和探路保留。'


def advance(game):
    s=game.s;f=state(game);sid=s['last_settlement_id']
    if s['ending']:return
    for row in f['orders'].values():
        if row['status']!='ACTIVE' or row.get('paused') or s['day']<=row['created_day'] or sid in row['settlements']:continue
        credit=min(1+rush_credit(game,row['id']),row['required']-row['progress'])
        row['settlements'].append(sid);row['credits'].append(credit);row['progress']+=credit
        if row['building']=='hospital':s['hospital_progress']=row['required']-row['progress'] or None
        if row['progress']==row['required']:
            set_level(game,row['building'],row['target_level']);row.update(status='COMPLETED',completed_day=s['day'],completed_settlement=sid)
            if row['building']=='hospital' and row['target_level']==1:
                for m in town.available(game):m['injury_days']=max(0,m['injury_days']-1)
            game.log('facility_completed',order=row['id'],building=row['building'],level=row['target_level'])
    for oid,row in f['refits'].items():
        if row['status']=='READY' and row['day']<s['day']:
            f['branches'][row['building']]=row['branch'];row.update(status='COMPLETED',settlement=sid)
            f['branch_history'].append({'building':row['building'],'branch':row['branch'],'source':oid,'day':s['day']})
    for row in f['services'].values():
        if row['day']>=s['day']:continue
        if row['kind']=='training' and row['status']=='READY':
            for iid,n in row['targets'].items():
                m=game.member(iid);check(m in s['home_roster'],'补训者不得随行。');m['xp']+=n
            row.update(status='COMPLETED',settlement=sid);game.log('training_completed',order=row['id'],targets=row['targets'])
        elif row['kind']=='rush' and row['status']=='READY':row.update(status='COMPLETED',settlement=sid)
        elif row['kind'] in ('nursing','scout') and row['status']=='ACTIVE':
            row.update(status='EXPIRED',settlement=sid);f[row['kind']]=None


def depart(game):
    for kind in ('nursing','scout'):
        oid=state(game)[kind]
        if oid:
            row=state(game)['services'][oid];check(row['status']=='READY','服务已绑定另一趟。')
            row.update(status='ACTIVE',expedition=game.s['expedition_no'])


def start_battle(game,battle):
    oid=state(game)['nursing']
    if not oid:return
    row=state(game)['services'][oid]
    if row['status']!='ACTIVE' or row['battle_id']:return
    row['battle_id']=battle['battle_id'];battle['nursing_receipt']={'order':oid,'amount':row['amount'],'targets':row['targets'][:]}
    for a in battle['actors']:
        if a['side']=='player' and a['id'] in row['targets']:a['nursing']={'amount':row['amount'],'used':False}


def record_battle(game,b):
    if not game.s['debug_tainted']:
        f=state(game);f['veterans']=sorted(set(f['veterans'])|{a['id'] for a in b['actors'] if a['side']=='player'})


def scout(game,args):
    s=game.s;f=state(game)
    if args==['history']:
        return str([{'expedition':t['expedition_no'],'visited':t['visited_regions']} for t in s['completed_history']])
    check(s['phase']=='EXPLORE' and s['mission']=='ORDINARY','探路详情绑定普通远征当前锁定地图。')
    row=f['services'].get(f['scout']);check(row and row['status']=='ACTIVE','需先在城内购买探路服务。')
    if not args or args==['status']:return str(row)
    check(len(args)==2 and args[0] in ('reveal','redirect'),'scout reveal/redirect 节点ID')
    action,node=args;nodes={n['id'] for n in game.layout['nodes']};check(node in nodes,'节点不在当前地图。')
    key=[s['region'],node];check(key not in [r['key'] for r in row['reveals']],'同一节点详情已揭示。')
    current=s['site'];check(current not in game.manifest_region['encounters'] or current in game.current['cleared'],'请在安全节点探路，接敌详情已经免费公开。')
    check(node not in game.current['seen'] and node not in game.current['revealed_battles'],'到场已免费公开，不消耗探路名额。')
    if action=='redirect':check(row['level']>=3 and not row['retargeted'] and len(row['reveals'])>=row['limit'],'三级可在用完原名额后重指一次。')
    else:check(len(row['reveals'])<row['limit'],'本趟原探路名额已用完。')
    detail={'node':node}
    if node in game.manifest_region['encounters']:
        import depth_growth
        detail['encounter']=depth_growth.current_encounter(game,node);game.current['revealed_battles'].append(node)
    if node in game.manifest_region['events']:
        binding=game.manifest_region['events'][node];event=game.cat.events[binding['event_id']]
        detail['event']={'id':event['event_id'],'name':event['name'],'options':deepcopy(event['options'])}
    if row['level']>=2 and row['branch']=='B':
        neighbors={b if a==node else a for a,b in game.layout['edges'] if node in (a,b)}
        detail['known_adjacent_costs']={n:[o.get('costs',{}) for o in game.cat.events[game.manifest_region['events'][n]['event_id']]['options']]
            for n in neighbors if n in game.current['seen'] and n in game.manifest_region['events']}
    row['reveals'].append({'key':key,'detail':detail})
    if action=='redirect':row['retargeted']=True
    game.log('paid_scout_reveal',order=row['id'],key=key);return str(detail)


def describe(game):
    return '\n'.join([f"{k} {NAMES[k]} Lv{level(game,k)} 分支{branch(game,k) or '-'}" for k in NAMES]+[
        f'自然施工位{occupied(game)}/{workers(game)}；暂停工地至多1；未用服务额度不积存。',
        '工地：'+str([{k:r.get(k) for k in ('id','building','target_level','progress','required','paused')} for r in ongoing(game)]),
        '待用护理：'+str(state(game)['nursing'])+'；探路：'+str(state(game)['scout']),
        '观测站研究：research status；Lv2解析、Lv3研究交付，A/B均可。线索册：clue status，仅管理任务物、证词和研究记录。人员调查与救援：rescue status；rescue investigate 办理失联调查。搜救所二级B免原物调查点基础补给，三级同区域救人/原物调查可联办1日；recover quote 逐点列费。已收录任务物受保护。'])


def validate(game):
    s=game.s;f=state(game)
    check(all(type(level(game,k)) is int and 0<=level(game,k)<=3 for k in NAMES),'建筑等级无效。')
    check(occupied(game)<=workers(game),'自然施工位超额。')
    check(sum(bool(r.get('paused')) for r in ongoing(game))<=1,'暂停工地超过1。')
    check(not set(f['orders'])&set(s['construction_orders']),'建设订单ID跨建筑重复。')
    for key in f['branches']:
        history=[h for h in f['branch_history'] if h['building']==key]
        check(f['branches'][key]==(history[-1]['branch'] if history else None),'建筑分支缺少历史。')
        check(f['branches'][key] in (None,'A','B'),'分支无效。')
        if history:check(level(game,key)>=2,'一级建筑不能拥有分支。')
        for i,h in enumerate(history):
            if i==0:check(h['source']=='initial','建筑分支初选记录缺失。')
            else:
                r=f['refits'].get(h['source']);check(r and r['building']==key and r['branch']==h['branch'] and r['status']=='COMPLETED' and h['day']==r['day']+1,'建筑改修缺少付费及结算凭据。')
    for oid,r in f['refits'].items():
        paid=s['town_services'].get(oid)
        check(paid and paid['kind']=='refit' and paid['request']=={'building':r['building'],'branch':r['branch']},'建筑改修付款凭据不符。')
        check(r['status'] in ('READY','COMPLETED'),'建筑改修状态无效。')
    completed={}
    for oid,r in f['orders'].items():
        cost,required=build_cost(game,r['building'],r['target_level'])
        check(r['id']==oid and r['paid']==cost and r['required']==required and r['from_level']==r['target_level']-1,'建设费用/等级损坏。')
        check(gate(game,r['building'],r['target_level'],r['gate_facts']),'建设受理前置缺失。')
        check(len(set(r['settlements']))==len(r['settlements'])==len(r['credits']) and sum(r['credits'])==r['progress']<=required,'施工进度重复或不一致。')
        check(all(type(n) is int and 1<=n<=3 for n in r['credits']),'施工单次进度无效。')
        validate_progress(game,r)
        if r['status']=='COMPLETED':
            check(r['progress']==required and r['completed_settlement']==r['settlements'][-1],'竣工凭据无效。')
            completed.setdefault(r['building'],[]).append(r['target_level'])
        elif r['status']=='CANCELLED':check(r['refund']==construction.refund(r) and r['progress']<required,'撤单退款无效。')
        else:check(r['status']=='ACTIVE' and r['progress']<required and level(game,r['building'])==r['from_level'],'在建工地等级不符。')
    for key,origin in f['origins'].items():check(sorted(completed.get(key,[]))==list(range(origin+1,level(game,key)+1)),'建筑升级链缺失。')
    h=hospital_order(game)
    if h:check(s['hospital_progress']==h['required']-h['progress'],'医舍施工显示不同步。')
    for oid,r in f['services'].items():
        paid=s['town_services'].get(oid);check(paid and paid['kind']==r['kind'] and paid['base']==service_base(r),'设施服务缺少付款凭据。')
        check(r['status'] in ('READY','ACTIVE','COMPLETED','EXPIRED'),'服务状态无效。')
        check(r['day']==paid['day'],'服务日期与付款不同步。')
        if r['kind']=='scout':
            check(r['limit']==(2 if r['level']>=2 and r['branch']=='A' else 1) and (not r['retargeted'] or r['level']>=3),'探路效果与付款时建筑不符。')
            check(len(r['reveals'])<=r['limit']+int(r['retargeted']) and len({tuple(x['key']) for x in r['reveals']})==len(r['reveals']),'探路次数重复或超额。')
        if r['kind']=='nursing':
            check(r['level'] in (2,3) and r['amount']==(10 if r['level']==3 else 6),'护理等级或数值无效。')
            check(1<=len(set(r['targets']))==len(r['targets'])<=(3 if r['branch']=='A' else 2),'护理人数无效。')
        if r['kind']=='training':
            check(r['unit_price']==(4 if r['level']==3 else 6) and 1<=r['level']<=3,'补训单价无效。')
            check(1<=len(r['targets'])<=(2 if r['level']>=2 and r['branch']=='A' else 1),'补训人数无效。')
            check(all(type(n) is int and 1<=n<=(2 if r['level']>=2 and r['branch']=='B' else 1) for n in r['targets'].values()),'补训经验无效。')
            facts=r['gate_facts'];cap=4 if 'CH3_COMPLETE' in facts else 3 if 'CH2_COMPLETE' in facts else 2 if 'ST-104' in facts or 'CH1_COMPLETE' in facts else 1
            check(r['cap']==min(cap,r['teacher_level']) and r['teacher'] in f['veterans'] and set(r['targets'])<=set(f['veterans']),'补训章限或实际带教凭据缺失。')
            if r['status']=='READY':check(set(r['targets'])<={m['instance_id'] for m in s['home_roster']},'补训者不能随行。')
        if r['kind']=='rush':
            check(r['amount']==(2 if r['level']>=2 and r['branch']=='B' else 1) and any(o['id']==r['target'] for o in orders(game)),'赶工效果或工地无效。')
    for kind in ('scout','nursing'):
        live=[oid for oid,r in f['services'].items() if r['kind']==kind and r['status'] in ('READY','ACTIVE')]
        check(live==([f[kind]] if f[kind] else []),'下一趟服务唯一占用不一致。')


def validate_progress(game,row):
    credits=row.get('credits',[1]*len(row['settlements']));prior=0;last=row['created_day']
    for sid,credit in zip(row['settlements'],credits):
        prefix=game.s['id']+':D';check(sid.startswith(prefix),'施工结算来源无效。')
        day=int(sid[len(prefix):]);check(last<day<=game.s['day'],'施工日期回退或重复。')
        extra=sum(r['amount'] for r in state(game)['services'].values() if r['kind']=='rush' and r['target']==row['id'] and r['day']==day-1)
        check(credit==min(1+extra,row['required']-prior),'施工进度缺少自然行动或已付赶工来源。')
        prior+=credit;last=day
