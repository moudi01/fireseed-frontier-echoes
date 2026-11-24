"""Unique equipment custody. Receipts and the immutable registry are not inventories."""
from copy import deepcopy
import gear_affixes as affixes

ROSTERS=('party','home_roster','captives','escorted','memorial')


def check(condition,message):
    if not condition:raise ValueError(message)


def panel(catalog,iid,template,source):
    base=catalog.gear[template]
    return {'instance_id':iid,'template_id':template,'panel_version':'TINDER-1.7',
            'slot':'weapon' if base['slot']=='war_gear' else 'armor','effects':[],
            'content_mode':'legacy_panel','source':deepcopy(source)}


def register(game,item):
    affixes.validate(game.cat,item);iid=item['instance_id']
    check(iid not in game.s['gear_register'],'装备实例ID已登记，不能再次生成。')
    item['revision']=0
    game.s['gear_register'][iid]=deepcopy(item)
    game.s['gear_history'][iid]=[{'revision':0,'item':deepcopy(item),'order_id':None,'day':game.s['day']}]
    return item


def issue(game,template,destination,source,effects=None):
    """Mint one item from a locked result; None retains explicit panel fixtures."""
    check(template in game.cat.gear,'未知装备模板。')
    game.s['gear_sequence']+=1
    iid=f"EQ-{game.s['gear_sequence']:06d}"
    item=panel(game.cat,iid,template,source) if effects is None else affixes.make(game.cat,iid,template,effects)
    item['source']=deepcopy(source)
    register(game,item);destination.append(item)
    return item


def initialize(game):
    s=game.s;s.update(gear_sequence=0,gear_register={},gear_history={},gear_lost=[],equipment_drops={})
    for member in s['party']:
        member['gear_instances']=[]
        for template in member['gear']:
            issue(game,template,member['gear_instances'],{'kind':'initial_team_fixture','member':member['instance_id'],'randomized':False})


def locations(game):
    s=game.s
    for key in ('gear_storage','gear_bag','affix_inventory'):
        for item in s.get(key,[]):yield key,item
    for key in ROSTERS:
        for member in s[key]:
            for item in member['gear_instances']:yield key+':'+member['instance_id'],item
    for receipt in s['gear_lost']:yield 'lost:'+receipt['reason'],receipt['item']


def validate(game):
    s=game.s
    check(isinstance(s.get('gear_register'),dict),'缺少装备实例登记；旧档不可混载。')
    check(type(s.get('gear_sequence')) is int and s['gear_sequence']>=0,'装备ID序号无效。')
    people=[m for key in ROSTERS for m in s[key]]
    check(all('gear_instances' in m for m in people),'人员缺少装备实例。')
    check(len({m['instance_id'] for m in people})==len(people),'人员出现重复归属。')
    affixes.validate_party(game.cat,people)
    seen=set()
    for owner,item in locations(game):
        check(isinstance(item,dict),'库存必须记录装备实例，不能使用模板字符串。')
        affixes.validate(game.cat,item);iid=item['instance_id']
        check(iid not in seen,'同一装备实例存在重复归属：'+iid)
        check(s['gear_register'].get(iid)==item,'装备实例未登记或内容已改变：'+iid)
        seen.add(iid)
    check(seen==set(s['gear_register']),'已登记装备缺少归属或遗失记录。')
    check(all(not iid.startswith('EQ-') or int(iid[3:])<=s['gear_sequence'] for iid in seen),'装备ID序号回退。')
    check(set(s['gear_history'])==set(s['gear_register']),'装备版本登记不完整。')
    for iid,history in s['gear_history'].items():
        check(bool(history) and history[-1]['item']==s['gear_register'][iid],'装备当前版本与历史末项不一致。')
        for revision,row in enumerate(history):
            item=row['item'];affixes.validate(game.cat,item)
            check(row['revision']==item.get('revision')==revision and item['instance_id']==iid,'装备版本不连续。')
            check(item['template_id'][:4]==history[0]['item']['template_id'][:4] and item['source']==history[0]['item']['source'],'加工不能改底型或原始来源。')
            if revision:
                order=s['work_orders'].get(row['order_id'],{})
                check(order.get('status')=='COMPLETED' and order.get('item_id')==iid and order.get('result_revision')==revision,'装备修订缺少完工订单。')
            else:check(row['order_id'] is None,'原始版本不能冒充加工修订。')
    from equipment_rolls import validate_state
    validate_state(game)
    import workshop
    workshop.validate(game)


def unlocked(game,item):
    import workshop
    order=workshop.active(game)
    check(not order or order['item_id']!=item['instance_id'],'装备被加工订单锁定；须完工或合法撤单。')


def original(game,iid):
    return game.s['gear_history'][iid][0]['item']


def revise(game,item,replacement,order_id):
    import workshop
    order=workshop.active(game);iid=item['instance_id']
    check(order and order['id']==order_id and order['item_id']==iid and item==order['before'],'修订缺少对应的有效订单或原版本。')
    check(replacement['instance_id']==iid and replacement['template_id'][:4]==item['template_id'][:4],'修订不能换实例或底型。')
    affixes.validate(game.cat,replacement);replacement['revision']=item['revision']+1
    item.clear();item.update(deepcopy(replacement));game.s['gear_register'][iid]=deepcopy(item)
    game.s['gear_history'][iid].append({'revision':item['revision'],'item':deepcopy(item),'order_id':order_id,'day':game.s['day']})


def select(inventory,key):
    item=next((i for i in inventory if i['instance_id']==key),None)
    if item is not None:return item
    check(key.isdecimal() and 0<=int(key)<len(inventory),'来源库存没有该实例；请输入完整实例ID或当前列表序号。')
    return inventory[int(key)]


def swap(game,member,inventory,slot,item=None):
    check(slot in ('weapon','armor'),'只有weapon／armor两个槽。')
    if item is not None:
        unlocked(game,item)
        check(item in inventory,'装备不在可用来源库存中。')
        affixes.validate(game.cat,item)
        kind='H01' if member['unit_id']=='CMD' else member['unit_id']
        check(item['slot']==slot and kind in game.cat.gear[item['template_id']]['allowed_unit_ids'],'装备槽或职业不适配。')
    worn=member['gear_instances'];old=next((i for i in worn if i['slot']==slot),None)
    check(item is not None or old is not None,'该槽已经为空。')
    old_max=member['stats']['hp']
    if old is not None:
        worn.remove(old);inventory.append(old)
        from balance_v062 import gear_modifiers
        for stat,value in gear_modifiers(game.cat,old,member).items():member['stats'][stat]-=value
    if item is not None:
        inventory.remove(item);worn.append(item)
        from balance_v062 import gear_modifiers
        for stat,value in gear_modifiers(game.cat,item,member).items():member['stats'][stat]+=value
    member['gear']=[i['template_id'] for i in worn]  # Validated display/legacy combat mirror only.
    new_max=member['stats']['hp']
    # Wearing a +HP item fills the newly gained maximum, matching level_up.
    # It never heals wounds that existed before the swap.
    if member['hp']>0 and new_max>old_max:member['hp']+=new_max-old_max
    member['hp']=min(member['hp'],new_max)
    return old


def lose_bag(game,reason):
    s=game.s
    for item in s['gear_bag']:
        s['gear_lost'].append({'item':item,'reason':reason,'expedition_no':s['expedition_no'],'day':s['day']})
    s['gear_bag']=[]


def label(item):
    effects='／'.join(e['name'] for e in item['effects']) or '仅面板'
    return f"{item['instance_id']} {item['template_id']} {item['slot']} {effects}"


def describe(game):
    import workshop
    order=workshop.active(game)
    return '\n'.join(owner+' | '+label(item)+f" v{item['revision']}"+(' [加工锁定]' if order and order['item_id']==item['instance_id'] else '') for owner,item in locations(game)) or '没有装备实例。'


def handle(game,command,args):
    s=game.s
    if command=='gear':
        check(bool(args),'gear list / wear 队员 ID / remove 队员 weapon或armor / stash或take ID')
        sub,*args=args
        if sub=='list':
            check(not args,'gear list');return describe(game)
        if sub in ('stash','take'):
            check(s['phase']=='TOWN' and len(args)==1,'仅城内 gear stash/take 实例ID。')
            src,dst=('gear_bag','gear_storage') if sub=='stash' else ('gear_storage','gear_bag')
            item=select(s[src],args[0]);unlocked(game,item);s[src].remove(item);s[dst].append(item)
            game.log('gear_transferred',item=item['instance_id'],source=src,destination=dst);return
        check(sub in ('wear','remove'),'未知装备操作。')
        command='equip' if sub=='wear' else 'unequip'
    check(s['phase'] in ('TOWN','EXPLORE'),'只能在城内或远征非战斗状态穿脱装备。')
    check(len(args)==2,'equip 队员 实例ID或序号 / unequip 队员 weapon或armor')
    member=game.member(args[0])
    if s['phase']=='EXPLORE':check(member in s['party'],'野外只能操作仍在队的人员；倒地者换装不复起。')
    key='gear_storage' if s['phase']=='TOWN' else 'gear_bag';inventory=s[key]
    item=select(inventory,args[1]) if command=='equip' else None
    slot=item['slot'] if item is not None else args[1]
    old=swap(game,member,inventory,slot,item)
    game.log('gear_equipped' if item else 'gear_unequipped',member=member['instance_id'],slot=slot,
             item=item['instance_id'] if item else None,removed=old['instance_id'] if old else None,inventory=key)
