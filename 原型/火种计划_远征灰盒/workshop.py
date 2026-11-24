"""One paid equipment job, stable upgrade outcomes and transactional revisions."""
from copy import deepcopy
from data import keyed_rng
import equipment
import gear_affixes as affixes
import equipment_rolls as rolls
import reforge


def check(ok,message):
    if not ok:raise ValueError(message)


def initialize(game):
    game.s.update(workshop_level=2,work_orders={},active_work_order=None,upgrade_rolls={},reforge_attempts={})


def active(game):
    return game.s['work_orders'].get(game.s['active_work_order'])


def order_id(oid):
    check(1<=len(oid)<=64 and all(c.isalnum() or c in '-_' for c in oid),'订单ID需为1—64位字母、数字、下划线或短横线。')


def upgrade_key(item,target):
    # A paid adopted reforge is a genuine revision; cancelled/kept orders are not.
    return item['instance_id']+':'+target+':v'+str(item['revision'])


def rule(game,item,target):
    family,quality=item['template_id'].split('-')
    spec=next((r for r in game.cat.loot['gear_operations']['upgrade_steps'] if r['from']==quality and r['to']==target),None)
    check(spec is not None,'只能逐级升阶：Q1→Q2或Q2→Q3。')
    check(quality=='Q1' or item.get('content_mode')!='legacy_panel','仅面板的过渡Q2不能免费补词条；请使用完整词条实例。')
    primary=next(f['primary_material_tag'] for f in game.cat.loot['equipment_families'] if f['family_id']==family)
    cost={'copper':spec['copper']}
    for tag,amount in spec['materials'].items():
        key=primary if tag=='primary' else tag;cost[key]=cost.get(key,0)+amount
    return spec,cost,family+'-'+target


def gate(game,spec):
    required=int(spec['requires_building'][-1]);facts=game.s['unlocked_facts'];story=spec['requires_story']
    check(game.s['workshop_level']>=required,f'需要工坊Lv{required}。')
    completed=story in facts or (story=='CH1_COMPLETE' and 'ST-104' in facts)
    check(completed,'需要实际完成'+story+'；研究线开放不等于完成。')


def stored(game,iid):
    item=next((i for i in game.s['gear_storage'] if i['instance_id']==iid),None)
    check(item is not None,'需要城镇仓库中的已卸装实例；不能远程取人物或携行装备。')
    return item


def candidate(game,item,target_template):
    keep=[e['effect_id'] for e in item['effects']]
    options=[ids for ids in rolls.candidates(target_template,'regular') if set(keep)<=set(ids)]
    check(bool(options),'没有能保留原词条的合法升阶组合。')
    key=upgrade_key(item,target_template)
    cached=game.s['upgrade_rolls'].get(key)
    if cached:
        check(cached['before']==item and cached['effects'] in options,'该装备的已锁升阶记录与当前版本不符。')
        return key,cached
    rng=keyed_rng(game.s['campaign_seed'],rolls.VERSION+':upgrade:'+key)
    return key,{'before':deepcopy(item),'target_template':target_template,'effects':rng.choice(options),'pool_version':rolls.VERSION}


def balances(game,cost):
    return {k:(game.s['bank'] if k=='copper' else game.s['warehouse']).get(k,0) for k in cost}


def apply_cost(game,cost,sign):
    for key,amount in cost.items():
        container=game.s['bank'] if key=='copper' else game.s['warehouse']
        container[key]=container.get(key,0)+sign*amount


def cancellation_refund(order):
    """The same remaining-progress refund used by quotes and real cancellation."""
    check(order['kind']=='UPGRADE' and order['status']=='ACTIVE','只有未完成升阶订单可以撤单退款。')
    return {k:v*(order['required']-order['progress'])//order['required'] for k,v in order['paid'].items()}


def describe(game):
    s=game.s;order=active(game)
    text=f"工坊Lv{s['workshop_level']}；升阶／重铸共用装备加工位1；制药使用剩余库存，不推进加工。"
    if order and order['kind']=='REFORGE':text+='\n'+reforge.describe(game,order)
    elif order:text+=f"\n{order['id']} {order['item_id']} → {order['target_template']}，进度{order['progress']}/{order['required']}；原物留库锁定，完工揭示新词条。"
    else:text+='\n加工位空闲。'
    for order in s['work_orders'].values():
        if order['status']!='ACTIVE':text+=f"\n{order['id']} {order['kind']} {order['status']}，原物{order['item_id']}，选择{order.get('decision','—')}，退款{order.get('refund',{})}"
    return text


def handle(game,args):
    s=game.s;check(args,'workshop status / quote ID Q2 / upgrade ID Q2 订单ID CONFIRM / cancel 订单ID CONFIRM')
    if args==['status']:return describe(game)
    check(s['phase']=='TOWN','加工操作需要城镇整备；状态可随时查看。')
    action=args[0]
    if action in ('reforge_quote','reforge','resolve'):return reforge.handle(game,args)
    if action=='quote':
        check(len(args)==3,'workshop quote 实例ID Q2/Q3')
        item=stored(game,args[1]);spec,cost,target=rule(game,item,args[2])
        # Public costs and gates, never the hidden paid candidate or cached result.
        return f"{item['instance_id']} → {target}；需要{spec['requires_building']}及{spec['requires_story']}；成本{cost}；库存{balances(game,cost)}；{spec['work_progress_required']}次后续真实行动结算。保留原常规词条，完工新增一条；不回血、不自动穿回。"
    if action=='cancel':
        check(len(args)==3 and args[-1]=='CONFIRM','workshop cancel 订单ID CONFIRM')
        order=s['work_orders'].get(args[1]);check(order is not None,'订单不存在。')
        check(order['kind']=='UPGRADE','重铸候选已经付费；请采用新效果或保留旧效果，不支持撤单退款。')
        if order['status']=='CANCELLED':return '该订单已撤销，沿用原退款，不重复返还。'
        check(order['status']=='ACTIVE' and s['active_work_order']==order['id'],'已完工订单不能撤销。')
        refund=cancellation_refund(order)
        apply_cost(game,refund,1);order.update(status='CANCELLED',refund=refund,cancelled_day=s['day'])
        s['active_work_order']=None;game.log('work_cancelled',order=order['id'],refund=deepcopy(refund));return '已返还原品质装备并按进度退款；原升阶抽样记录保留。'
    check(action=='upgrade' and len(args)==5 and args[-1]=='CONFIRM','workshop upgrade 实例ID Q2/Q3 订单ID CONFIRM')
    _,iid,target,oid,_=args
    order_id(oid)
    payload={'kind':'UPGRADE','item_id':iid,'target_quality':target}
    old=s['work_orders'].get(oid)
    if old:
        check(old['request']==payload,'同一订单ID不能用于不同请求。')
        return '沿用原订单'+oid+'：'+old['status']+'；不重复扣款、推进或重新下单。'
    check(active(game) is None,'装备加工位已有订单；仍可制作消耗品。')
    item=stored(game,iid);equipment.unlocked(game,item);spec,cost,target_template=rule(game,item,target);gate(game,spec)
    owned=balances(game,cost);check(all(owned[k]>=v for k,v in cost.items()),'铜或已入库材料不足；不能花待入账收益或携行材料。')
    key,roll=candidate(game,item,target_template)
    apply_cost(game,cost,-1);s['upgrade_rolls'].setdefault(key,deepcopy(roll))
    s['work_orders'][oid]={'id':oid,'request':payload,'kind':'UPGRADE','item_id':iid,'expected_revision':item['revision'],
        'before':deepcopy(item),'target_template':target_template,'candidate_effects':roll['effects'][:],'roll_key':key,
        'paid':cost,'created_day':s['day'],'required':spec['work_progress_required'],'progress':0,'settlements':[], 'status':'ACTIVE'}
    s['active_work_order']=oid;game.log('work_started',order=oid,item=iid,target=target_template,paid=deepcopy(cost))
    return '订单已付费受理，原装备留库锁定；下单不耗日，后续真实行动结算推进。'


def advance(game):
    s=game.s;order=active(game)
    if not order or order['kind']!='UPGRADE' or s['ending'] or s['day']<=order['created_day']:return
    settlement=s['last_settlement_id']
    if settlement in order['settlements']:return
    check(settlement is not None,'加工推进缺少行动结算凭据。')
    order['settlements'].append(settlement);order['progress']+=1
    game.log('work_progressed',order=order['id'],settlement=settlement,progress=order['progress'])
    if order['progress']<order['required']:return
    item=stored(game,order['item_id']);check(item==order['before'],'加工期间原装备版本已变化。')
    replacement=affixes.make(game.cat,item['instance_id'],order['target_template'],order['candidate_effects'])
    replacement['source']=deepcopy(item['source'])
    equipment.revise(game,item,replacement,order['id'])
    order.update(status='COMPLETED',completed_day=s['day'],completed_settlement=settlement,result_revision=item['revision'])
    s['active_work_order']=None;game.log('work_completed',order=order['id'],item=deepcopy(item))


def validate(game):
    s=game.s;check(type(s.get('workshop_level')) is int and 0<=s['workshop_level']<=3,'工坊等级无效。')
    active_ids=[]
    for oid,order in s['work_orders'].items():
        order_id(oid)
        check(order['id']==oid and order['kind'] in ('UPGRADE','REFORGE'),'加工订单身份不一致。')
        check(order['status'] in ('ACTIVE','COMPLETED','CANCELLED'),'加工订单状态无效。')
        before=order['before'];iid=order['item_id']
        check(before['instance_id']==iid and before['revision']==order['expected_revision'],'订单原版本不一致。')
        history=s['gear_history'][iid];check(history[before['revision']]['item']==before,'订单与原装备历史不一致。')
        check(type(order['created_day']) is int and 0<=order['created_day']<=s['day'],'加工受理日期无效。')
        if order['kind']=='REFORGE':
            reforge.validate(game,order)
            if order['status']=='ACTIVE':active_ids.append(oid)
            continue
        spec,cost,target=rule(game,before,order['request']['target_quality'])
        check(order['request']=={'kind':'UPGRADE','item_id':iid,'target_quality':spec['to']} and target==order['target_template']
              and order['paid']==cost and order['required']==spec['work_progress_required'],'订单费用或目标被改写。')
        key=upgrade_key(before,target);cached=s['upgrade_rolls'].get(key)
        check(order['roll_key']==key and cached is not None and cached['before']==before and cached['effects']==order['candidate_effects'],'订单抽样记录不一致。')
        check(len(set(order['settlements']))==len(order['settlements'])==order['progress'] and 0<=order['progress']<=order['required'],'加工进度或结算去重失效。')
        for settlement in order['settlements']:
            prefix=s['id']+':D';check(settlement.startswith(prefix) and order['created_day']<int(settlement[len(prefix):])<=s['day'],'加工结算时间无效。')
        if order['status']=='ACTIVE':
            active_ids.append(oid);check(order['progress']<order['required'] and stored(game,iid)==before,'在制装备归属或版本无效。')
        elif order['status']=='COMPLETED':
            rev=order['result_revision'];check(order['progress']==order['required'] and rev==before['revision']+1,'完工进度／版本无效。')
            check(history[rev]['order_id']==oid and history[rev]['item']['template_id']==target
                  and [e['effect_id'] for e in history[rev]['item']['effects']]==order['candidate_effects'],'完工与修订记录不一致。')
        else:
            expected={k:v*(order['required']-order['progress'])//order['required'] for k,v in cost.items()}
            check(order['progress']<order['required'] and order['refund']==expected,'撤单退款不一致。')
    check(active_ids==([s['active_work_order']] if s['active_work_order'] else []),'唯一加工位与订单不一致。')
    for key,row in s['upgrade_rolls'].items():
        before=row['before'];template=row['target_template'];options=[ids for ids in rolls.candidates(template) if set(e['effect_id'] for e in before['effects'])<=set(ids)]
        check(key==upgrade_key(before,template) and row['pool_version']==rolls.VERSION and bool(options),'升阶保留记录无效。')
        check(s['gear_history'][before['instance_id']][before['revision']]['item']==before,'升阶抽样缺少原版本。')
        expected=keyed_rng(s['campaign_seed'],rolls.VERSION+':upgrade:'+key).choice(options)
        check(row['effects']==expected,'升阶结果与锁定抽样不一致。')
    reforge.validate_attempts(game)
    import construction
    construction.validate(game)
    import outfitting
    outfitting.validate(game)
