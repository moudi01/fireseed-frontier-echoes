"""Paid affix candidates, optional material locks and one persistent choice."""
from copy import deepcopy
from data import keyed_rng
import equipment
import equipment_rolls as rolls
import gear_affixes as affixes

VERSION='GEAR-REFORGE-1.0'


def check(ok,message):
    if not ok:raise ValueError(message)


def locks(text):
    ids=[] if text.lower()=='none' else text.split(',')
    check(len(ids)==len(set(ids)) and all(ids),'锁定项重复或为空；不锁请填none。')
    return sorted(ids)


def spec(game,item,locked):
    family,quality=item['template_id'].split('-');ids=[e['effect_id'] for e in item['effects']]
    check(quality in ('Q2','Q3') and item.get('content_mode')!='legacy_panel','需要Q2／Q3完整词条装备；Q1先升阶，过渡面板装备不能免费补词条。')
    form='strong' if any(e.get('negative') for e in item['effects']) else 'regular'
    pool=rolls.candidates(item['template_id'],form)
    check(any(set(row)==set(ids) for row in pool),'当前效果不在该底型的已登记重铸池。')
    check(len(locked)==len(set(locked)) and set(locked)<=set(ids),'只能锁定原装备实际具有的词条，且不能重复。')
    if form=='strong':check(not locked or set(locked)==set(ids),'强效与负面必须整组处理，不能只锁正面或单洗负面。')
    options=[row for row in pool if set(locked)<=set(row) and set(row)!=set(ids)]
    primary=next(f['primary_material_tag'] for f in game.cat.loot['equipment_families'] if f['family_id']==family)
    cost={'copper':6 if quality=='Q2' else 12}
    for tag,amount in [(primary,2 if quality=='Q2' else 4),('crystal_shard',1 if quality=='Q2' else 2+2*len(locked))]:
        cost[tag]=cost.get(tag,0)+amount
    gate={'requires_building':'WORKSHOP-Lv2' if quality=='Q2' else 'WORKSHOP-Lv3',
          'requires_story':'CH1_COMPLETE' if quality=='Q2' else 'ST-303'}
    return form,options,cost,gate


def draw(game,iid,attempt,options):
    return keyed_rng(game.s['campaign_seed'],VERSION+':'+rolls.VERSION+':reforge:'+iid+':'+str(attempt)).choice(options)


def details(game,item,ids=None):
    return rolls.details(game,{'template_id':item['template_id'],'effect_ids':ids if ids is not None else [e['effect_id'] for e in item['effects']]})


def describe(game,order):
    return (f"{order['id']} {order['item_id']} 重铸待选择；已付{order['paid']}；锁定{order['request']['locked_effects'] or '无'}。"
            f"\n原效果：{details(game,order['before'])}\n新候选：{details(game,order['before'],order['candidate_effects'])}"
            f"\nworkshop resolve {order['id']} adopt/keep CONFIRM；采用新效果或保留原效果均不退款，选择后释放加工位。")


def handle(game,args):
    import workshop
    s=game.s;action=args[0]
    if action=='resolve':
        check(len(args)==4 and args[-1]=='CONFIRM' and args[2] in ('adopt','keep'),'workshop resolve 订单ID adopt/keep CONFIRM')
        _,oid,decision,_=args;order=s['work_orders'].get(oid)
        check(order is not None and order['kind']=='REFORGE','需要重铸订单。')
        if order['status']=='COMPLETED':
            check(order['decision']==decision,'订单已经结清，不能反向选择；可另付费重铸。')
            return '沿用已保存选择；不重复修订或扣款。'
        check(order['status']=='ACTIVE' and s['active_work_order']==oid,'重铸订单不是当前待选择项。')
        item=workshop.stored(game,order['item_id']);check(item==order['before'],'重铸原版本已变化。')
        if decision=='adopt':
            replacement=affixes.make(game.cat,item['instance_id'],item['template_id'],order['candidate_effects'])
            # Lock the entire effect payload, not only its identity.
            by_id={e['effect_id']:e for e in order['locked_effects']}
            replacement['effects']=[deepcopy(by_id.get(e['effect_id'],e)) for e in replacement['effects']]
            replacement['source']=deepcopy(item['source'])
            equipment.revise(game,item,replacement,oid)
        order.update(status='COMPLETED',decision=decision,result_revision=item['revision'],completed_day=s['day'])
        s['active_work_order']=None
        game.log('reforge_resolved',order=oid,decision=decision,result_revision=item['revision'])
        return ('已采用新词条，原实例版本加一。' if decision=='adopt' else '已保留原词条和版本。')+'本次费用已消耗，加工位已释放；不自动穿回或治疗。'
    check(action in ('reforge_quote','reforge'),'未知重铸操作。')
    check(len(args)==(3 if action=='reforge_quote' else 5) and (action=='reforge_quote' or args[-1]=='CONFIRM'),
          'workshop reforge_quote 实例ID none/词条ID；workshop reforge 实例ID none/词条ID 订单ID CONFIRM')
    iid=args[1];locked=locks(args[2]);payload={'kind':'REFORGE','item_id':iid,'locked_effects':locked}
    if action=='reforge':
        oid=args[3];workshop.order_id(oid);old=s['work_orders'].get(oid)
        if old:
            check(old['request']==payload,'同一订单ID不能用于不同请求。')
            return describe(game,old) if old['status']=='ACTIVE' else '沿用原重铸订单'+oid+'：'+old['decision']+'；不再次收费或抽样。'
    item=workshop.stored(game,iid);form,options,cost,required=spec(game,item,locked)
    if action=='reforge_quote':
        if not options:return '没有其他合法候选（全锁、正负整组或适配池不足）；不收费、不占加工位。'
        owned=workshop.balances(game,cost);remaining={k:owned[k]-v for k,v in cost.items()}
        return (f"原效果：{details(game,item)}\n锁定{locked or '无'}；需要{required['requires_building']}及{required['requires_story']}；"
                f"成本{cost}；库存{owned}；支付后{remaining}。\n合法组合{len(options)}个，各等概率1/{len(options)}：\n"
                +'\n'.join(details(game,item,row) for row in options)+'\n付款后只生成一份候选，采用或留旧均消耗费用；确认前可退出。')
    check(workshop.active(game) is None,'装备加工位已有订单；仍可制作消耗品。')
    equipment.unlocked(game,item);workshop.gate(game,required)
    check(bool(options),'没有其他合法候选（全锁、正负整组或适配池不足）；不收费、不占加工位。')
    owned=workshop.balances(game,cost);check(all(owned[k]>=v for k,v in cost.items()),'铜或已入库材料不足；不能花待入账收益或携行材料。')
    attempt=s['reforge_attempts'].get(iid,0)+1;candidate=draw(game,iid,attempt,options)
    workshop.apply_cost(game,cost,-1);s['reforge_attempts'][iid]=attempt
    order={'id':oid,'kind':'REFORGE','request':payload,'item_id':iid,'expected_revision':item['revision'],
           'before':deepcopy(item),'locked_effects':[deepcopy(e) for e in item['effects'] if e['effect_id'] in locked],
           'target_template':item['template_id'],'form':form,'pool_version':rolls.VERSION,'reforge_version':VERSION,
           'attempt_index':attempt,'candidate_effects':candidate[:],'paid':cost,'created_day':s['day'],'status':'ACTIVE'}
    s['work_orders'][oid]=order;s['active_work_order']=oid
    game.log('reforge_paid',order=oid,item=iid,attempt=attempt,paid=deepcopy(cost))
    return describe(game,order)


def validate(game,order):
    import workshop
    s=game.s;before=order['before'];iid=order['item_id'];locked=order['request']['locked_effects']
    check(order['request']=={'kind':'REFORGE','item_id':iid,'locked_effects':sorted(set(locked))},'重铸请求不一致。')
    form,options,cost,_=spec(game,before,locked)
    check(order['status'] in ('ACTIVE','COMPLETED') and bool(options),'重铸状态或合法候选无效。')
    attempt=order['attempt_index'];check(type(attempt) is int and attempt>0,'重铸付费序号无效。')
    check(order['target_template']==before['template_id'] and order['form']==form and order['paid']==cost,'重铸底型、形态或费用不一致。')
    check(order['pool_version']==rolls.VERSION and order['reforge_version']==VERSION,'重铸候选池版本不一致。')
    check(order['candidate_effects']==draw(game,iid,attempt,options),'重铸候选与已付费抽样不一致。')
    check(order['locked_effects']==[e for e in before['effects'] if e['effect_id'] in locked],'锁定词条参数被改变。')
    check('refund' not in order,'付费重铸不能退款。')
    if order['status']=='ACTIVE':
        check(workshop.stored(game,iid)==before and 'decision' not in order,'待选择装备版本或状态无效。')
    else:
        decision=order['decision'];check(decision in ('adopt','keep'),'重铸选择无效。')
        check(order['created_day']<=order['completed_day']<=s['day'],'重铸结清日期无效。')
        revision=before['revision']+(decision=='adopt');check(order['result_revision']==revision,'重铸修订版本错误。')
        if decision=='adopt':
            row=s['gear_history'][iid][revision];item=row['item']
            expected=affixes.make(game.cat,iid,before['template_id'],order['candidate_effects'])
            expected.update(source=deepcopy(before['source']),revision=revision)
            check(row['order_id']==order['id'] and item==expected,'重铸成品与候选／修订记录不一致。')
            check(all(e in item['effects'] for e in order['locked_effects']),'已锁词条未完整保留。')


def validate_attempts(game):
    attempts={}
    for order in game.s['work_orders'].values():
        if order['kind']=='REFORGE':attempts.setdefault(order['item_id'],[]).append(order['attempt_index'])
    check(set(attempts)==set(game.s['reforge_attempts']),'重铸付费序号登记不完整。')
    for iid,indices in attempts.items():
        count=game.s['reforge_attempts'][iid]
        check(type(count) is int and sorted(indices)==list(range(1,count+1)),'重铸付费序号重复或回退。')
