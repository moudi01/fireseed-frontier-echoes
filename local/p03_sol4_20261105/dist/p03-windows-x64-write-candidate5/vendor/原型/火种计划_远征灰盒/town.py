"""Persistent safe-return campaign loop, using authored town costs and time.

No trial fixture is recreated when preparing the next expedition.
"""
from copy import deepcopy
import math
from data import keyed_rng
import rescue
import escort
import refugee
import water
import medicine
import cases
import construction
import outfitting
import facilities

COMMANDS={'town','route','squad','recruit','buy_supply','pack_medical','rest','maintain',
          'care','build_hospital','level_up','stash','take','heal','shelter'}

# Town healing is a paid service, not a free reset. One copper restores up to
# four missing HP before the moral-price multiplier; the multiplier is derived
# from actual case receipts so no extra save key is needed.
HEAL_HP_PER_COPPER=4


def check(condition,message):
    if not condition:raise ValueError(message)


def shelter_status(game):
    s=game.s
    protected=[];exploited=[]
    for eid in game.cat.rules.get('humanity',{}).get('event_ids',[]):
        try:state=cases.get(s,eid)['state']
        except KeyError:continue
        if state=='PROTECTED':protected.append(eid)
        elif state=='EXPLOITED':exploited.append(eid)
    return {'protected':protected,'exploited':exploited}


def shelter_text(game):
    row=shelter_status(game)
    name=lambda eid:game.cat.events[eid]['name'] if eid in game.cat.events else eid
    kept='、'.join(name(eid) for eid in row['protected']) or '无'
    sold='、'.join(name(eid) for eid in row['exploited']) or '无'
    hidden=game.s.get('book_stock',{}).get(cases.HIDDEN_BOOK,0)>0 or any(
        cases.HIDDEN_BOOK in m.get('books_learned',[]) or cases.HIDDEN_BOOK in m.get('books_equipped',[])
        for m in game.s.get('party',[])+game.s.get('home_roster',[]))
    return (f"庇护账：已保全{len(row['protected'])}案（{kept}）；已交割{len(row['exploited'])}案（{sold}）。"
            '道德经济按不对等设计：保全回信给少量随队补给并保留完美结局资格，不给价格折扣；'
            '交割只兑现当次报酬，不追加机械惩罚。完美结局仍须按真实结果满足全部条件。'
            f"回信谢礼：每保全一案+{cases.CASE_LETTER_SUPPLY}随队补给；"
            '十案全部保全后获得隐藏技能书 SB-Z01（终局对策卡：选定高威胁敌人，使其下一次攻击无效）。'
            + ('已取得隐藏技能书 SB-Z01。' if hidden else ''))


def available(game):return game.s['party']+game.s['home_roster']


def roster(game):return available(game)+game.s['captives']+game.s['escorted']


def relief_quote(game):
    """Read-only assistance quote based on capital that can return to cash.

    Keep terminal custody/registries out: a captured or permanently lost item
    cannot finance recovery. Worn, stored and workshop-locked original items
    remain capital because normal removal/cancellation/keep can release them.
    Materials, supplies, consumables, books and people have no copper sale API;
    giving them invented prices would block genuinely insolvent recoveries.
    """
    s=game.s;rule=game.cat.rules['economy']['relief'];equipment=[];seen=set()
    inventories=[(key,s.get(key,[])) for key in ('gear_storage','gear_bag','affix_inventory')]
    inventories += [(key+':'+m['instance_id'],m['gear_instances'])
                    for key in ('party','home_roster') for m in s[key]]
    for location,items in inventories:
        for item in items:
            iid=item['instance_id']
            check(iid not in seen,'救济估值发现装备重复归属：'+iid)
            seen.add(iid)
            equipment.append({'id':iid,'template':item['template_id'],'location':location,
                              'copper':game.cat.gear[item['template_id']]['sell_copper']})
    refundable={'copper':0,'crystal':0};orders=[]
    def add_refund(kind,row,amounts):
        amounts={key:amounts.get(key,0) for key in refundable}
        for key,value in amounts.items():refundable[key]+=value
        orders.append({'kind':kind,'id':row['id'],'progress':row['progress'],
                       'required':row['required'],'refundable':amounts})
    for row in facilities.ongoing(game):
        add_refund('construction',row,construction.refund(row))
    import workshop
    order=workshop.active(game)
    if order and order['kind']=='UPGRADE':
        add_refund('upgrade',order,workshop.cancellation_refund(order))
    cash={key:s['bank'][key] for key in refundable}
    gear_value=sum(row['copper'] for row in equipment)
    capital={'copper':cash['copper']+gear_value+refundable['copper'],
             'crystal':cash['crystal']+refundable['crystal']}
    caps={key:rule[key+'_cap'] for key in refundable}
    steps={key:rule[key+'_step'] for key in refundable}
    gains={key:min(steps[key],max(0,caps[key]-capital[key])) for key in refundable}
    return {'cash':cash,'gear_value':gear_value,'equipment':equipment,'refundable':refundable,
            'orders':orders,'capital':capital,'caps':caps,'steps':steps,'gains':gains,
            'scope':'AVAILABLE_LIQUID_CAPITAL_ONLY_NOT_TOTAL_ASSET_LIMIT'}


def relief_description(game):
    row=relief_quote(game);cash=row['cash'];refund=row['refundable'];gain=row['gains']
    return (f"维护救济预估：铜现金{cash['copper']}＋可卖装备{row['gear_value']}＋可退铜{refund['copper']}"
            f"＝资本{row['capital']['copper']}，本次补{gain['copper']}铜；"
            f"晶现金{cash['crystal']}＋可退晶{refund['crystal']}，本次补{gain['crystal']}晶。"
            '仅按可变现资本补差，售卖收入不设上限。')


def initialize(game,spec):
    s=game.s
    s.update(campaign_seed=s['seed'],expedition_no=1,home_roster=[],recruit_sequence=0,
             unlocked_facts=spec['facts'][:],gear_storage=[],item_storage=[],
             hospital_level=0,hospital_progress=None,care_target=None,downed_this_trip=[])
    for member in s['party']:member.update(level=spec['level'],injury_days=0)
    rescue.initialize(s)
    escort.initialize(s)


def advance_day(game,home,rest=False):
    """Only old wounds progress. Call BEFORE registering this expedition's wounds."""
    s=game.s
    if s['phase']!='TOWN':
        import learning
        learning.settle_departure(game)
    s['day']+=1;healed=[]
    s['last_settlement_id']=f"{s['id']}:D{s['day']}"
    cases.redeem_all(game)
    rescue.expire(game)
    for m in home:
        if m['injury_days']>0:m['injury_days']=max(0,m['injury_days']-1-int(m['instance_id']==s['care_target']))
        if rest:m['erosion']=max(0,m['erosion']-game.cat.rules['mental_erosion']['town_rest_reduction'])
    if s['hospital_progress'] is not None and not facilities.hospital_order(game):
        s['hospital_progress']-=1
        if s['hospital_progress']==0:
            s['hospital_progress']=None;s['hospital_level']=1
            for m in home:m['injury_days']=max(0,m['injury_days']-1)
            game.log('hospital_completed',level=1)
    for m in home:
        if m['injury_days']==0 and m['hp']==0:
            m['hp']=m['stats']['hp'];healed.append(m['instance_id'])
    game.log('town_day',rest=rest,recovered=healed,care_target=s['care_target'])
    s['care_target']=None
    import workshop
    construction.advance(game)
    facilities.advance(game)
    for m in home:
        if m['injury_days']==0 and m['hp']==0:m['hp']=m['stats']['hp']
    workshop.advance(game)
    outfitting.advance(game)


def safe_return_health(game):
    s=game.s
    before=[{'id':m['instance_id'],'hp':m['hp'],'maximum':m['stats']['hp']} for m in s['party']]
    down=(set(s['downed_this_trip']) & {m['instance_id'] for m in s['party']})|{m['instance_id'] for m in s['party'] if m['hp']<=0}
    advance_day(game,s['home_roster'])
    days=facilities.injured_days(game)
    for m in s['party']:
        if m['instance_id'] in down:
            m['injury_days']=facilities.injured_days(game,story=m.get('story_injury',False));m['hp']=0;m['deployed']=False
        else:m['hp']=m['stats']['hp']
    return before,sorted(down)


def handle(game,command,args):
    s=game.s;c=game.cat
    if command=='town':
        check(s['phase'] in ('RETURNED','FAILED'),'需先完成归城结算；终局不可继续。')
        s['completed_history'].append(deepcopy({k:s[k] for k in [
            'expedition_no','route','seed','summary','manifest','request','battle_reports',
            'regions','visited_regions','completed_regions','debits','party','mission','rescue_target','escort_receipts']}))
        s['gear_storage'].extend(s['gear_bag'])
        s['expedition_no']+=1
        s['seed']=keyed_rng(s['campaign_seed'],f"expedition:{s['expedition_no']}").randrange(2**31)
        s.update(phase='TOWN',manifest=None,request=None,region=None,site=None,previous_site=None,
                 visited_regions=[],regions={},pending={'copper':0,'crystal':0},materials={},gear_bag=[],
                 debits={},battle=None,battle_reports=[],completed_regions=[],summary=None,downed_this_trip=[],
                 mission='ORDINARY',rescue_target=None)
        escort.initialize(s)
        if s.get('campaign'):
            s['campaign']['challenge']=None
            if s['route'].startswith('HUNT-'):s['route']='R01'
        game.log('town_preparation',expedition=s['expedition_no'],seed=s['seed'])
        return '已保留现有人员与库存；被俘者留在救援名册。准备下一趟，地图种子按趟次固定。'
    check(s['phase']=='TOWN','该操作需要回城后进入整备。')
    if command=='route':
        check(len(args)==1,'route R01：选择下一趟路线')
        route=next((r for r in c.config['routes'] if r['route_id']==args[0].upper()),None)
        check(route and set(route['facts'])<=set(s['unlocked_facts']),'路线不存在或尚无对应许可。')
        if s.get('campaign'):
            check(not route['route_id'].startswith('HUNT-'),'固定讨伐请使用 challenge MGxx。')
            s['campaign']['challenge']=None
        s['route']=route['route_id'];game.log('route_selected',route=s['route']);return
    if command=='squad':
        check(len(args)==2 and args[1] in ('on','off'),'squad 完整队员ID on/off：随行或留城')
        m=game.member(args[0])
        if args[1]=='off':
            check(m in s['party'],'该人已经留城。')
            s['party'].remove(m);m['deployed']=False;s['home_roster'].append(m)
        else:
            check(m in s['home_roster'],'该人已经随行。')
            check(m['instance_id'] not in facilities.training_ids(game),'该人已报名本次留城补训。')
            check(m['injury_days']==0 and m['hp']>0,'该人仍在恢复。')
            check(sum(x['cost'] for x in s['party'])+m['cost']<=s['budget']['expedition'],'超过出征Cost。')
            occupied={tuple(x['position']) for x in s['party']}
            m['position']=list(next(p for p in c.formation if p not in occupied))
            m['deployed']=False;s['home_roster'].remove(m);s['party'].append(m)
        game.log('squad_changed',member=m['instance_id'],travel=args[1]=='on');return
    if command=='recruit':
        if args in ([],['catalog']):
            from roster_content import PERSONAS
            names={'M01':'护运枪卫','M02':'野战药师','M03':'弩机匠','M04':'雾术师'}
            return '\n'.join(f"{uid} {row.get('name',names.get(uid,uid))}｜Cost2｜{c.rules['economy']['mercenary_recruit_copper']}铜｜"+PERSONAS.get(uid,{}).get('role','既有职业；book show查看固有招式与两书槽') for uid,row in c.rules['mercenaries'].items())
        check(len(args)==1,'recruit S01/S02/S03/M01..M08；recruit catalog查看职业')
        uid=args[0].upper();bases={v['id']:v for v in c.rules['units'].values()};bases.update(c.rules['mercenaries'])
        check(uid in bases,'付费招募支持士兵和佣兵；自然开局英雄使用 summon 请求ID CONFIRM。')
        price=c.rules['economy']['recruit_copper' if uid.startswith('S') else 'mercenary_recruit_copper']
        check(s['bank']['copper']>=price,f'招募需要{price}铜。')
        sequence=s['recruit_sequence']+1;base=bases[uid]
        rng=keyed_rng(s['campaign_seed'],f'recruit:{sequence}')
        stats={k:rng.randint(*bounds) for k,bounds in base['ranges'].items()}
        m={'instance_id':f'N-{sequence:04d}','unit_id':uid,'stats':stats,'birth_stats':deepcopy(stats),
           'recruit_sequence':sequence,'hp':stats['hp'],'erosion':0,'xp':0,'level':1,'injury_days':0,
           'gear':[],'gear_instances':[],'deployed':False,'cost':1 if uid.startswith('S') else 2,
           'range':base['range'],'interval':base['interval'],'attack_type':base['attack_type'],
           **{k:base[k] for k in ('basic_medium','locomotion') if k in base},
           'position':list(c.formation[0]),'stance':'advance','facing':1}
        s['bank']['copper']-=price;s['recruit_sequence']=sequence;s['home_roster'].append(m)
        import save_validation
        save_validation.enroll(game,m,'RECRUIT',sequence)
        game.log('recruited',member=m['instance_id'],unit=uid,price=price,birth=deepcopy(stats))
        return f"已招募{m['instance_id']}，位于留城名册；新人Lv1、无装备。"
    if command in ('buy_supply','pack_medical'):
        check(len(args)==1,'请输入数量。');n=int(args[0])
        if command=='buy_supply':
            check(1<=n<=100,'每次采购1至100份。');price=n*c.rules['economy']['supply_copper']
            check(s['bank']['copper']>=price,'铜不足。');s['bank']['copper']-=price;s['bank']['supply']+=n
        else:
            check(0<=n<=facilities.medical_cap(game),f'额外救护当前上限{facilities.medical_cap(game)}份。')
            difference=n-s['medical'];check(s['bank']['supply']>=difference,'仓库通用补给不足。')
            s['bank']['supply']-=difference;s['medical']=n
        game.log(command,amount=n);return
    if command in ('rest','maintain'):
        rescue.confirm_day(s,args)
        gains={};quote=None
        if command=='maintain':
            quote=relief_quote(game)
            for key in ('copper','crystal'):
                gains[key]=quote['gains'][key];s['bank'][key]+=gains[key]
        advance_day(game,available(game),rest=command=='rest')
        game.log(command,gains=gains,**({'relief_quote':quote} if quote else {}));rescue.check_ending(game)
        return ('已结算1行动日；救援期限、旧伤、建筑施工与装备加工已结算。'
                +(f"维护按可变现资本补差：铜{gains['copper']}、公共结晶{gains['crystal']}；正常售卖不受此上限约束。" if quote else ''))
    if command=='care':
        check(len(args)==1,'care 完整队员ID：花1补给，下一行动额外减1日旧伤')
        m=game.member(args[0]);check(m['injury_days']>0,'该人没有需要伤护的旧伤。')
        check(s['care_target'] is None,'当前已安排一项伤护，需结算行动后再安排。')
        outfitting.pay(game,f"care:{s['day']}",'care',{'supply':1},{'member':m['instance_id']})
        s['care_target']=m['instance_id'];game.log('care_scheduled',member=m['instance_id']);return
    if command=='build_hospital':
        check(not args and s['hospital_level']==0 and s['hospital_progress'] is None,'医舍一级只能建设一次。')
        return facilities.handle(game,['build','hospital','1',f"hospital-{s['day']}-{s['expedition_no']}",'CONFIRM'])
    if command=='level_up':
        check(len(args)==1,'level_up 完整队员ID')
        m=game.member(args[0]);check(m['level']<c.rules['level']['maximum'],'已达等级上限。')
        cost=c.rules['level']['experience_per_step'][m['level']-1];price=c.rules['economy']['level_copper']
        check(m['xp']>=cost and s['bank']['copper']>=price,f'需要{cost}经验、{price}铜。')
        bases={v['id']:v for v in c.rules['units'].values()};bases.update(c.rules['mercenaries']);bases.update(c.rules['hero_templates']);bases['PET-H04']=c.rules['companion_template']
        old_max=m['stats']['hp']
        for k,amount in bases[m['unit_id']]['growth'].items():m['stats'][k]+=amount
        new_max=m['stats']['hp']
        if m['hp']>0:m['hp']=min(new_max,m['hp']+(new_max-old_max))
        m['level']+=1;m['xp']-=cost;s['bank']['copper']-=price
        game.log('level_up',member=m['instance_id'],level=m['level'])
        return f"已升级{m['instance_id']}到Lv{m['level']}；当前HP {m['hp']}/{new_max}（只回填本次新增上限，不恢复旧伤）。"
    if command=='heal':
        check(len(args)==1,'heal 完整队员ID：按缺失生命支付铜，城内即时治疗')
        m=game.member(args[0]);check(m in available(game),'只能治疗随行或留城队员。')
        missing=m['stats']['hp']-m['hp'];check(missing>0,'该人当前没有生命缺口。')
        price=max(1,math.ceil(missing/HEAL_HP_PER_COPPER))
        check(s['bank']['copper']>=price,f'治疗需要{price}铜（缺口{missing}）。')
        s['bank']['copper']-=price;m['hp']=m['stats']['hp']
        game.log('town_heal',member=m['instance_id'],restored=missing,price=price)
        return (f"已治疗{m['instance_id']}，恢复{missing}点生命，支付{price}铜；"
                f"当前{m['hp']}/{m['stats']['hp']}。治疗价格固定，不因保全或交割改变。")
    if command=='shelter':
        check(not args,'shelter：查看已保全/已交割案件')
        return shelter_text(game)
    if command in ('stash','take'):
        check(len(args)==1,'stash/take CO01：在携行袋与城内物品库之间转移')
        item=args[0].upper();source=s['pouch'] if command=='stash' else s['item_storage'];dest=s['item_storage'] if command=='stash' else s['pouch']
        check(item in source,'来源库存没有该物品。')
        if command=='take':check(len(dest)+s['used_prep_slots']<4,'携行袋已满。')
        source.remove(item);dest.append(item);game.log(command,item=item);return
    raise ValueError('未知城镇操作：'+command)
