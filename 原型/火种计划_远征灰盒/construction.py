"""Paid workshop construction on the shared town site, independent of gear jobs."""
from copy import deepcopy


def check(ok,message):
    if not ok:raise ValueError(message)


def initialize(game):
    game.s.update(construction_orders={},active_construction=None,workshop_construction_origin=None)


def active(game):
    return game.s['construction_orders'].get(game.s['active_construction'])


def costs(game,target):
    check(type(target) is int and 1<=target<=3,'工坊建设目标为1、2或3级。')
    spec=game.cat.rules['buildings']['armory'];index=target-1
    return {'copper':spec['copper'][index],'crystal':spec['crystal'][index]},spec['progress'][index]


def conditions(game,target,facts=None):
    facts=set(game.s['unlocked_facts'] if facts is None else facts)
    if target==1:return [('ST-101委任','ST-101' in facts),('ST-104名册交存','ST-104' in facts)]
    if target==2:return [('CH1完成','CH1_COMPLETE' in facts or 'ST-104' in facts)]
    # The authored research line opens upon CH2 completion. Do not grant ST-303 itself.
    research_after=game.cat.rules['narrative']['research_open_after']
    return [('CH2完成','CH2_COMPLETE' in facts),('ST-303研究线开启',research_after in facts or 'ST-303_RESEARCH_OPEN' in facts)]


def refund(order):
    if order['progress']==0:return deepcopy(order['paid'])
    return {'copper':order['paid']['copper']*(order['required']-order['progress'])//order['required'],'crystal':0}


def quote(game,target):
    s=game.s;cost,required=costs(game,target)
    gates='、'.join(name+('：已满足' if ok else '：未满足') for name,ok in conditions(game,target))
    remaining={k:s['bank'][k]-v for k,v in cost.items()}
    return (f"工坊Lv{target-1}→Lv{target}；当前Lv{s['workshop_level']}；{gates}。"
            f"\n需{cost['copper']}铜＋{cost['crystal']}公共结晶（不是晶屑），{required}次后续行动结算；支付后{remaining}。"
            '\n开工不耗日，旧等级持续生效；零进度撤单全退，推进后只按剩余比例退铜、结晶不返。')


def describe(game):
    import facilities
    s=game.s;order=active(game)
    if order:site=f"{order['id']} 工坊Lv{order['target_level']}：{order['progress']}/{order['required']}，{'暂停' if order.get('paused') else '在建'}；现有Lv{s['workshop_level']}仍可用。"
    else:site='工坊没有在建订单。'
    text=f'全城自然施工位{facilities.occupied(game)}/{facilities.workers(game)}，与装备加工位独立；'+site
    for target in range(1,4):text+='\n'+quote(game,target)
    recipes=[r['output_id'] for r in game.cat.recipes.values() if r.get('requires_building')=='armory' and r['requires_building_level']<=s['workshop_level']]
    text+='\n当前可制作：'+('、'.join(recipes) or '无，须先建成一级工坊。')
    text+='\nQ3加工：'+('建筑等级已满足' if s['workshop_level']>=3 else '建筑等级未满足')+'；'+('ST-303实际完成已满足。' if 'ST-303' in s['unlocked_facts'] else 'ST-303实际完成未满足。')
    text+='\n分支与整备请用outfit status；二级竣工后可选A/B。全部工地、暂停与额外施工位用facility status，赶工用service rush。'
    for row in s['construction_orders'].values():
        if row['status']!='ACTIVE':text+=f"\n{row['id']} {row['status']} Lv{row['target_level']}，退款{row.get('refund',{})}。"
    return text


def handle(game,args):
    import workshop
    s=game.s
    if args==['status']:return describe(game)
    check(s['phase']=='TOWN','建设操作需要城镇整备；状态可随时查看。')
    check(args,'construction status / quote 等级 / start 等级 订单ID CONFIRM / cancel 订单ID CONFIRM')
    if args[0]=='quote':
        check(len(args)==2,'construction quote 1/2/3');return quote(game,int(args[1]))
    if args[0]=='cancel':
        check(len(args)==3 and args[-1]=='CONFIRM','construction cancel 订单ID CONFIRM')
        order=s['construction_orders'].get(args[1]);check(order is not None,'建设订单不存在。')
        if order['status']=='CANCELLED':return '原建设订单已撤销，不重复退款。'
        check(order['status']=='ACTIVE' and s['active_construction']==order['id'],'已竣工建设不能撤单。')
        import facilities
        check(not facilities.pending_rush(game,order['id']),'已有已付赶工；结算后再撤单。')
        returned=refund(order)
        for key,amount in returned.items():s['bank'][key]+=amount
        order.update(status='CANCELLED',refund=returned,cancelled_day=s['day']);s['active_construction']=None
        game.log('construction_cancelled',order=order['id'],refund=deepcopy(returned))
        return f'已撤销施工，原工坊等级保留，退还{returned}；装备加工订单不受影响。'
    check(args[0]=='start' and len(args)==4 and args[-1]=='CONFIRM','construction start 1/2/3 订单ID CONFIRM')
    target=int(args[1]);oid=args[2];workshop.order_id(oid);cost,required=costs(game,target)
    request={'building':'armory','target_level':target};old=s['construction_orders'].get(oid)
    if old:
        check(old['request']==request,'同一建设订单ID不能用于不同请求。')
        return '沿用建设订单'+oid+'：'+old['status']+'；不重复扣款或施工。'
    import facilities
    check(oid not in facilities.state(game)['orders'],'该ID已用于其他建筑。')
    check(active(game) is None and facilities.can_start(game),'工坊或自然施工位已被占用。')
    check(s['workshop_level']==target-1,'必须从当前工坊等级逐级建设，不能跳级或重复建设。')
    missing=[name for name,ok in conditions(game,target) if not ok]
    check(not missing,'建设条件未满足：'+'、'.join(missing))
    check(all(s['bank'][k]>=v for k,v in cost.items()),'已入库铜或公共结晶不足；晶屑、携行物资和待入账奖励不能代替。')
    for key,amount in cost.items():s['bank'][key]-=amount
    if s['workshop_construction_origin'] is None:s['workshop_construction_origin']=s['workshop_level']
    s['construction_orders'][oid]={'id':oid,'request':request,'building':'armory','from_level':target-1,'target_level':target,
        'paid':cost,'required':required,'progress':0,'settlements':[],'created_day':s['day'],'status':'ACTIVE',
        'gate_facts':s['unlocked_facts'][:]}
    s['active_construction']=oid;game.log('construction_started',order=oid,target=target,paid=deepcopy(cost))
    return '工坊建设已付款，施工位已占用；下单不耗日，后续实际行动结算推进，竣工前保留旧等级。'


def advance(game):
    s=game.s;order=active(game)
    if not order or order.get('paused') or s['ending'] or s['day']<=order['created_day']:return
    settlement=s['last_settlement_id']
    if settlement in order['settlements']:return
    check(settlement is not None,'施工推进缺少行动结算凭据。')
    import facilities
    credit=min(1+facilities.rush_credit(game,order['id']),order['required']-order['progress'])
    order.setdefault('credits',[]).append(credit)
    order['settlements'].append(settlement);order['progress']+=credit
    game.log('construction_progressed',order=order['id'],progress=order['progress'],settlement=settlement)
    if order['progress']==order['required']:
        check(s['workshop_level']==order['from_level'],'施工期间工坊等级被改变。')
        s['workshop_level']=order['target_level'];s['active_construction']=None
        order.update(status='COMPLETED',completed_day=s['day'],completed_settlement=settlement)
        game.log('construction_completed',order=order['id'],level=s['workshop_level'])


def validate(game):
    s=game.s;orders=s['construction_orders'];active_ids=[];completed={};origin=s['workshop_construction_origin']
    check((not orders and origin is None) or (orders and type(origin) is int and 0<=origin<=2),'建设起始等级记录无效。')
    for oid,row in orders.items():
        target=row['target_level'];cost,required=costs(game,target)
        check(row['id']==oid and row['building']=='armory' and row['from_level']==target-1,'建设订单身份／等级无效。')
        check(row['request']=={'building':'armory','target_level':target} and row['paid']==cost and row['required']==required,'建设费用或目标被改写。')
        check(all(ok for name,ok in conditions(game,target,row['gate_facts'])),'建设受理时缺少剧情门槛。')
        check(type(row['created_day']) is int and 0<=row['created_day']<=s['day'],'建设受理日期无效。')
        progress=row['progress'];settlements=row['settlements']
        check(type(progress) is int and 0<=progress<=required and len(set(settlements))==len(settlements) and sum(row.get('credits',[1]*len(settlements)))==progress and len(row.get('credits',settlements))==len(settlements),'建设进度或结算去重无效。')
        for settlement in settlements:
            prefix=s['id']+':D';check(settlement.startswith(prefix) and row['created_day']<int(settlement[len(prefix):])<=s['day'],'建设结算日期无效。')
        import facilities
        facilities.validate_progress(game,row)
        if row['status']=='ACTIVE':
            active_ids.append(oid);check(progress<required and s['workshop_level']==row['from_level'],'在建等级或进度无效。')
        elif row['status']=='COMPLETED':
            check(progress==required and row['completed_settlement']==settlements[-1] and row['completed_day']==int(settlements[-1].split(':D')[-1]),'建设完工回执无效。')
            check(row['from_level'] not in completed,'同级建设出现重复完工。');completed[row['from_level']]=row
        else:
            check(row['status']=='CANCELLED' and progress<required and row['refund']==refund(row),'建设撤单退款无效。')
            check(row['created_day']<=row['cancelled_day']<=s['day'],'建设撤单日期无效。')
        check(origin<=row['from_level']<=s['workshop_level'],'建设级别与历史链不一致。')
    check(active_ids==([s['active_construction']] if s['active_construction'] else []),'建设订单与唯一施工位不一致。')
    import facilities
    check(facilities.occupied(game)<=facilities.workers(game),'医舍与工坊重复占用默认施工位。')
    if origin is not None:
        level=origin
        while level in completed:level+=1
        check(len(completed)==level-origin and level==s['workshop_level'],'工坊等级缺少连续完工凭据。')
