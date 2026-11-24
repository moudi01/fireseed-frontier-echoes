"""Authored Q1 shop, terminal gear custody and shared-budget field supplies."""
from copy import deepcopy
import equipment
import workshop
from data import keyed_rng
from joint_sampling_model import digest

MATERIAL_BONUS_VERSION='MATERIAL-ELITE-0.88'
MATERIAL_BONUS_RECEIPT='material_commission_bonus'


def check(ok,text):
    if not ok:raise ValueError(text)


def initialize(game):game.s.update(supply_orders={},material_commission=None,carried_books={})


def handle(game,args):
    s=game.s;c=game.cat
    if not args or args==['status']:
        target=(s.get('manifest') or {}).get('material_commission')
        location=f"；本趟目标{target['region']}/{target['site']}，须实际到场领取" if target else ''
        return 'Q1八家族每件8铜；sale/dismantle使用城内未穿戴、未锁定装备。商店制式Q1不能拆材，可按原价售回；投入升至Q2/Q3后恢复正常拆材，掉落和事件Q1不受此限制。\n定向材料：'+str(s['material_commission'])+location+'；途中技能书见 book status。\n'+describe_material_bonus(game)
    if args==['catalog']:
        return '以下固定面板以Cost4为基准；穿戴实际加成＝基准×本人Cost/4（士兵1/4、佣兵1/2、英雄全额），词条另按自身规则。\n'+'\n'.join(f"{gid} {row['name']} 8铜；Cost4基准面板{row['stat_modifiers']}；适配{row['allowed_unit_ids']}" for gid,row in c.gear.items() if gid.endswith('-Q1'))
    if args[0]=='book':return claim_book(game)
    check(s['phase']=='TOWN','采购、拆卖和选择材料委托需在城镇。')
    if args[0]=='quote':
        check(len(args)==3 and args[1] in ('buy','sale','dismantle'),'supply quote buy/sale/dismantle 目标')
        action,target=args[1:]
        if action=='buy':
            check(target in c.gear and target.endswith('-Q1'),'只出售八家族Q1。')
            return str({'price':{'copper':8},'template':c.gear[target],
                        'panel_note':'固定面板是Cost4基准；实际加成＝基准×穿戴者Cost/4，士兵1/4、佣兵1/2、英雄全额；词条另按自身规则。'})
        item=next((i for i in s['gear_storage'] if i['instance_id']==target),None)
        check(item,'请先把实际装备卸入城镇仓库。');equipment.unlocked(game,item)
        template=c.gear[item['template_id']]
        if action=='sale':return str({'consumed_instance':target,'copper':template['sell_copper']})
        return str({'consumed_instance':target,'materials':dismantle_return(game,item)})
    if args[0]=='commission':
        check(len(args)==2,'supply commission MAT-IRON/MAT-SHARD/MAT-FIBER/MAT-HERB/off')
        if args[1]=='off':s['material_commission']=None;return
        spec=next((r for r in c.loot['fixed_material_commissions'] if r['mission_id']==args[1]),None)
        check(spec,'未知材料委托。');gate='ST-104' if spec['unlock']=='CH2_available' else spec['unlock']
        check(gate in s['unlocked_facts'],'尚无该委托许可：'+gate)
        s['material_commission']=spec['mission_id'];return '已登记物资目标：到场选择原材料取得原2单位；若同时战胜目标区原有的可选精英L，再追加同类1单位，本趟最多1次。先领材料或先赢L均可，须携带归城才入库；可放弃精英，原材料不受影响。'
    check(len(args)==4 and args[-1]=='CONFIRM' and args[0] in ('buy','sale','dismantle'),'supply buy EF01-Q1 请求ID CONFIRM；sale/dismantle 装备ID 请求ID CONFIRM')
    action,target,oid=args[:3];workshop.order_id(oid);request={'action':action,'target':target}
    if oid in s['supply_orders']:
        check(s['supply_orders'][oid]['request']==request,'同一请求ID不能用于不同交易。');return str(s['supply_orders'][oid])
    if action=='buy':
        check(target in c.gear and target.endswith('-Q1'),'城镇公开目录只出售八家族Q1。')
        cost=c.loot['gear_operations']['Q1_shop']['copper'];check(s['bank']['copper']>=cost,'铜不足。')
        s['bank']['copper']-=cost
        item=equipment.issue(game,target,s['gear_storage'],{'kind':'town_Q1_shop','request':oid,'randomized':False},[])
        receipt={'paid':{'copper':cost},'item_id':item['instance_id']}
    else:
        item=next((i for i in s['gear_storage'] if i['instance_id']==target),None)
        check(item,'需城镇仓库中已卸下的真实装备；无法处理携行、穿戴、被俘或已消耗装备。')
        equipment.unlocked(game,item)
        template=c.gear[item['template_id']]
        if action=='sale':
            price=template['sell_copper'];s['bank']['copper']+=price;receipt={'received':{'copper':price},'item_id':target}
        else:
            materials=dismantle_return(game,item)
            for k,v in materials.items():s['warehouse'][k]=s['warehouse'].get(k,0)+v
            receipt={'received_materials':materials,'item_id':target}
        s['gear_storage'].remove(item);s['gear_lost'].append({'reason':'town_'+action,'item':deepcopy(item),'request':oid,'day':s['day']})
    row={'id':oid,'request':request,'day':s['day'],**receipt};s['supply_orders'][oid]=row
    game.log('supply_transaction',receipt=row);return str(row)


def disassembly(game,template):
    family=next(r for r in game.cat.loot['equipment_families'] if r['family_id']==template['family_id'])
    materials={}
    for k,v in game.cat.loot['gear_operations']['disassembly']['returns_by_quality'][template['quality_id']].items():
        k=family['primary_material_tag'] if k=='primary' else k;materials[k]=materials.get(k,0)+v
    return materials


def dismantle_return(game,item):
    """One source/current-quality rule for preview, commit and saved receipts.

    Shop Q1 is a purchased standard issue, not a source of newly recovered raw
    materials. A genuine paid upgrade preserves its source but changes current
    quality; those invested Q2/Q3 revisions retain ordinary salvage rules.
    """
    template=game.cat.gear[item['template_id']];source=item.get('source')
    shop=isinstance(source,dict) and source.get('kind')=='town_Q1_shop'
    check(not (shop and template['quality_id']=='Q1'),
          f"商店制式Q1不能拆成材料；可用 supply sale {item['instance_id']} 请求ID CONFIRM 按原售价回收{template['sell_copper']}铜。真实投入升至Q2/Q3后可正常拆材。")
    return disassembly(game,template)


def bind(game,manifest):
    """Add alternatives to existing ordinary sites; never insert a free node."""
    s=game.s;c=game.cat;eligible=[]
    for rid,region in manifest['regions'].items():
        for node,b in region['events'].items():
            event=c.events[b['event_id']]
            if event['type']=='humanity':continue
            opts=[o['option_id'] for o in event['options'] if o.get('reward_bundle_id')=='RB-MAT2' and o['option_id'] in b['enabled_options']]
            if opts:eligible.append((rid,node,b,opts))
    commission=s['material_commission']
    if commission:
        spec=next(r for r in c.loot['fixed_material_commissions'] if r['mission_id']==commission)
        candidates=[r for r in eligible if r[0] in spec['region_ids']]
        check(candidates,'本趟没有可替换的合法材料回收点；请选择覆盖目标地区的路线或取消物资目标，未扣出发费。')
        rid,node,b,opts=keyed_rng(s['seed'],'material-commission:'+commission).choice(candidates)
        b['material_commission']={'id':commission,'materials':deepcopy(spec['reward_materials']),'options':opts}
        manifest['material_commission']={'id':commission,'region':rid,'site':node,'actual_claim_required':True}
        target=manifest['material_commission']
        target['elite_bonus']=material_bonus_contract(c,manifest,target)
    # New SB sources are frozen once by book_rewards.bind_manifest after this
    # material-only binding.  Do not also generate the retired BK offer here.
    from joint_sampling_model import digest
    manifest.pop('manifest_sha256',None);manifest['manifest_sha256']=digest(manifest)


def material_reward(game,bundle,context):
    if bundle!='RB-MAT2' or game.s['mission']!='ORDINARY':return False
    b=game.manifest_region['events'].get(game.s['site'],{});row=b.get('material_commission')
    if not row or context.get('option_id') not in row['options']:return False
    for k,v in row['materials'].items():game.s['materials'][k]=game.s['materials'].get(k,0)+v
    game.log('fixed_material_collected',mission=row['id'],materials=deepcopy(row['materials']));return True


def material_bonus_contract(cat,manifest,target):
    """A public optional target on an existing L, independent of event quota."""
    elite=manifest['regions'][target['region']]['encounters'].get('L')
    if not elite:return None
    spec=next(r for r in cat.loot['fixed_material_commissions'] if r['mission_id']==target['id'])
    check(len(spec['reward_materials'])==1,'追加材料需为单种定向材料。')
    tag=next(iter(spec['reward_materials']))
    return dict(version=MATERIAL_BONUS_VERSION,region=target['region'],site='L',
        encounter_id=elite['encounter_id'],materials={tag:1},unit_cap=1,
        requires_material_pickup=True,carry_then_settle=True)


def _material_bonus_source(trip,target,contract):
    rid=target['region'];region=(trip.get('regions') or {}).get(rid)
    if not region or 'L' not in region['cleared']:return None
    binding=trip['manifest']['regions'][rid]['events'][target['site']]
    material=binding.get('material_commission')
    scene=region['events'][target['site']];chosen=(scene.get('receipt') or {}).get('option')
    if not material or material['id']!=target['id'] or scene['state']!='RESOLVED' or chosen not in material['options']:return None
    matches=[b for b in trip.get('battle_reports',[]) if b['result']=='VICTORY' and not b.get('debug_tainted')
        and b.get('world_binding',{}).get('region')==rid and b.get('world_binding',{}).get('site')=='L'
        and b['encounter_id']==contract['encounter_id']]
    if not matches:return None
    check(len(matches)==1,'追加材料需对应唯一真实精英胜利。')
    return dict(expedition=trip['expedition_no'],region=rid,material_site=target['site'],material_option=chosen,
        elite_site='L',battle_id=matches[0]['battle_id'],encounter_id=contract['encounter_id'],contract_digest=digest(contract))


def award_material_bonus(game):
    s=game.s;target=(s.get('manifest') or {}).get('material_commission')
    if s.get('mission')!='ORDINARY' or not target or not target.get('elite_bonus'):return None
    region=s['regions'].get(target['region']);contract=target['elite_bonus']
    if region and MATERIAL_BONUS_RECEIPT in region:return deepcopy(region[MATERIAL_BONUS_RECEIPT])
    if s.get('debug_tainted'):return None
    proof=_material_bonus_source(s,target,contract)
    if proof is None:return None
    row=dict(version=MATERIAL_BONUS_VERSION,source=proof,materials=deepcopy(contract['materials']),status='PENDING')
    for tag,n in row['materials'].items():s['materials'][tag]=s['materials'].get(tag,0)+n
    region[MATERIAL_BONUS_RECEIPT]=row
    game.log('material_commission_bonus',receipt=deepcopy(row))
    return deepcopy(row)


def settle_material_bonus(game,safe,reason):
    """Only label the earned cargo; normal return/defeat owns its transfer."""
    s=game.s;target=(s.get('manifest') or {}).get('material_commission')
    if s.get('mission')!='ORDINARY' or not target or not target.get('elite_bonus'):return None
    check(type(safe) is bool,'材料追加结算标志无效。')
    row=(s.get('regions',{}).get(target['region']) or {}).get(MATERIAL_BONUS_RECEIPT)
    outcome='BANKED' if safe else 'LOST'
    if row:
        check(row['status'] in ('PENDING',outcome),'追加材料已按另一结果结算。')
        row['status']=outcome
    return dict(version=MATERIAL_BONUS_VERSION,outcome=outcome,reason=reason,
        materials=deepcopy(row['materials']) if row else {},receipt=deepcopy(row))


def describe_material_bonus(game):
    target=(game.s.get('manifest') or {}).get('material_commission')
    if not target:
        return '材料委托可选追索：原材料2单位＋目标区可选精英L胜利，追加同类1单位；不占原事件额度。出发后公开目标区，未选委托不追加。'
    contract=target.get('elite_bonus')
    if not contract:return '本趟材料目标沿原2单位规则，没有精英追加。'
    region=game.s.get('regions',{}).get(target['region'],{})
    if MATERIAL_BONUS_RECEIPT in region:return '本趟追加材料已取得：'+str(contract['materials'])+'，须携带归城入库。'
    return f"可选追索 {target['region']}/L：到{target['site']}选原材料，并战胜此区原有精英，追加{contract['materials']}；整趟限1次，先后顺序不限。可跳过，原2材料保持；到场intel读敌情后再决定。"


def validate_material_bonus(game):
    def trip_check(trip,current=False):
        manifest=trip.get('manifest') or {};target=manifest.get('material_commission')
        regions=trip.get('regions') or {};rows=[(rid,r[MATERIAL_BONUS_RECEIPT]) for rid,r in regions.items() if MATERIAL_BONUS_RECEIPT in r]
        summary=trip.get('summary') or {};settled=summary.get(MATERIAL_BONUS_RECEIPT)
        # Old histories retain their old contracts and never gain retroactive pay.
        if not target or 'elite_bonus' not in target:
            check(not rows and settled is None,'旧合同或无材料委托不能出现追加回执。')
            if current and target:check(False,'本趟材料委托缺少冻结追加合同。')
            return
        contract=target['elite_bonus']
        check(contract==material_bonus_contract(game.cat,manifest,target),'材料追加冻结合同被改动。')
        if contract is None:
            check(not rows and settled is None,'没有原L节点的合同不能发追加材料。');return
        check(trip.get('mission')=='ORDINARY','固定任务不能使用材料追加合同。')
        proof=_material_bonus_source(trip,target,contract)
        check(len(rows)<=1 and all(rid==target['region'] for rid,_ in rows),'超过整趟材料追加上限或目标区错误。')
        row=rows[0][1] if rows else None
        dirty=trip.get('debug_tainted',summary.get('debug_tainted',False))
        if not dirty:check((row is not None)==(proof is not None),'材料追加回执与真实领取／精英胜利不同步。')
        outcome=settled.get('outcome') if isinstance(settled,dict) else 'PENDING'
        check(outcome in ('PENDING','BANKED','LOST'),'材料追加结算状态错误。')
        if row:
            check(proof is not None and row==dict(version=MATERIAL_BONUS_VERSION,source=proof,
                materials=contract['materials'],status=outcome),'材料追加来源、数量或状态被改动。')
        if settled is not None:
            check(outcome==('LOST' if summary.get('result')=='DEFEAT' else 'BANKED'),'材料追加与原结算结果不一致。')
            check(not current or trip.get('phase') not in ('EXPLORE','BATTLE'),'途中不能提前结算追加材料。')
            check(settled==dict(version=MATERIAL_BONUS_VERSION,outcome=outcome,reason=summary.get('result'),
                materials=row['materials'] if row else {},receipt=row),'材料追加结算摘要不同步。')
    try:
        trip_check(game.s,True)
        for trip in game.s.get('completed_history',[]):trip_check(trip)
    except (KeyError,TypeError,IndexError,AttributeError,StopIteration) as exc:
        raise ValueError('材料追加合同或来源回执结构不完整。') from exc


def claim_book(game):
    import book_rewards
    return book_rewards.claim_event(game)


def settle(game,safe):
    import book_rewards
    return book_rewards.settle(game,safe,(game.s.get('summary') or {}).get('result'))


def describe_site(game):
    if game.s['phase']!='EXPLORE' or not game.s['manifest']:return ''
    row=game.manifest_region['events'].get(game.s['site'],{});lines=[]
    if row.get('material_commission'):
        lines.append('物资目标：选择原材料选项时固定取得'+str(row['material_commission']['materials'])+'，占原2材料额度。')
        lines.append(describe_material_bonus(game))
    if row.get('book_offer'):
        import book_rewards
        offer=book_rewards.offer(game,row['book_offer'].get('source_key'))
        if offer:lines.append('同处手册 '+offer['book_id']+' '+offer['name']+'：choose BOOK，替代此处原选项，使用全趟技能书额度；可暂离后回来。')
    return '\n'.join(lines)


def validate(game):
    s=game.s
    check(s['carried_books']=={},'旧携书字段必须留空；新版由来源回执管理。')
    check(s['material_commission'] is None or s['material_commission'] in {r['mission_id'] for r in game.cat.loot['fixed_material_commissions']},'物资目标无效。')
    consumed=set()
    for oid,r in s['supply_orders'].items():
        check(r['id']==oid,'采购事务ID不一致。');req=r['request'];item=s['gear_register'].get(r['item_id']);check(item,'交易装备缺少登记。')
        if req['action']=='buy':
            original=s['gear_history'][r['item_id']][0]['item']
            check(original['template_id']==req['target'] and req['target'].endswith('-Q1') and r['paid']=={'copper':8} and original['source']['request']==oid,'采购内容不一致。')
        else:
            check(req['action'] in ('sale','dismantle') and req['target']==r['item_id'] and r['item_id'] not in consumed,'装备重复消耗。');consumed.add(r['item_id'])
            check(any(x['reason']=='town_'+req['action'] and x.get('request')==oid and x['item']['instance_id']==r['item_id'] for x in s['gear_lost']),'拆卖缺少原件去向。')
            template=game.cat.gear[item['template_id']]
            check(r['received']=={'copper':template['sell_copper']} if req['action']=='sale' else r['received_materials']==dismantle_return(game,item),'拆卖回收量或拆材资格被改变。')
    validate_material_bonus(game)
