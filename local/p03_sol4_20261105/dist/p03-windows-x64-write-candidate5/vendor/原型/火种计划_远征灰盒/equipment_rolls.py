"""Versioned first-pass affix pools and persistent story quotes, not tuned balance."""
from copy import deepcopy
from itertools import combinations
import hashlib
import json
from data import keyed_rng
import gear_affixes as affixes

VERSION='GEAR-POOL-0.2'
POOLS={
    'EF01':(['SEEK','LEECH','BREAK'],[['FURY','FRAGILE'],['TECHNIQUE','BLUNT']]),
    'EF02':(['SEEK','LEECH','BREAK'],[['FURY','FRAGILE'],['TECHNIQUE','BLUNT']]),
    'EF03':(['SEEK','LEECH','BREAK'],[['FURY','FRAGILE'],['TECHNIQUE','BLUNT']]),
    'EF04':(['SEEK','LEECH','CHANNEL'],[]),
    'EF05':(['SEEK','LEECH','BANDAGE'],[['OVERDRAW','HARDHEAL'],['TRIAGE','FATIGUE']]),
    'EF06':(['SEEK','LEECH','BREAK'],[['FURY','FRAGILE'],['TECHNIQUE','BLUNT']]),
    'EF07':(['LINING','LIGHT','BASTION'],[['HEAVY','SLOW'],['RECUP','EXPOSED']]),
    'EF08':(['LINING','LIGHT','BASTION'],[['HEAVY','SLOW'],['RECUP','EXPOSED']]),
}


def check(ok,message):
    if not ok:raise ValueError(message)


def candidates(template,form='regular'):
    family,quality=template.split('-');normal,strong=POOLS[family]
    check(form in ('regular','strong'),'未知词条形态。')
    if quality=='Q1':return [[]] if form=='regular' else []
    if form=='strong':return deepcopy(strong) if quality=='Q3' else []
    return [[eid] for eid in normal] if quality=='Q2' else [list(pair) for pair in combinations(normal,2)]


def roll(catalog,template,seed,key,form=None):
    rng=keyed_rng(seed,VERSION+':'+key)
    # Keep family/quality draws independent; only Q3 with a registered pair uses 80:20.
    if form is None:
        form='strong' if template.endswith('-Q3') and POOLS[template[:4]][1] and rng.randrange(100)<20 else 'regular'
    pool=candidates(template,form);check(pool,'该底型没有此形态的合法候选。')
    ids=rng.choice(pool);affixes.make(catalog,'candidate',template,ids)
    return {'template_id':template,'effect_ids':ids,'form':form,'pool_version':VERSION}


def build_quotes(game,eid):
    spec=game.cat.events[eid]['story_trade']['reward'].get('equipment')
    if not spec:return None
    slots=[]
    for index in range(spec['count']):
        offers={}
        for family in POOLS:
            template=family+'-'+spec['quality']
            for form in ('regular','strong'):
                if not candidates(template,form):continue
                selection=family+(':strong' if form=='strong' else '')
                row=roll(game.cat,template,game.s['campaign_seed'],f'trade:{eid}:{index}:{selection}',form)
                digest=hashlib.sha256(json.dumps([eid,index,selection,row],sort_keys=True).encode()).hexdigest()[:16]
                offers[selection]={**row,'quote_id':'QUOTE-'+digest}
        slots.append(offers)
    return {'pool_version':VERSION,'slots':slots}


def ensure_quotes(game,eid):
    import cases
    case=cases.get(game.s,eid)
    if 'equipment_quotes' not in case:
        quotes=build_quotes(game,eid)
        if quotes is not None:case['equipment_quotes']=quotes
    return case.get('equipment_quotes')


def selected_quotes(game,eid,selections):
    import cases
    spec=game.cat.events[eid]['story_trade']['reward'].get('equipment')
    if not spec:
        check(not selections,'本凭单不含装备。');return []
    check(len(selections)==spec['count'],'请按件数选择装备报价。')
    allowed=cases.applicable_families(game)
    # Validate every selection before creating a cache, so invalid calls never partially mutate.
    quotes=cases.get(game.s,eid).get('equipment_quotes') or build_quotes(game,eid)
    for index,selection in enumerate(selections):
        check(selection.split(':')[0] in allowed and selection in quotes['slots'][index],'装备报价不存在、形态无候选或家族不适用于名册。')
    ensure_quotes(game,eid)
    return [deepcopy(quotes['slots'][i][selection]) for i,selection in enumerate(selections)]


def details(game,row):
    template=row['template_id'];base=game.cat.gear[template];rules=affixes.EFFECTS
    text={
        'SEEK':f"直接攻击暴击率+{rules['SEEK']['critical_chance']*100:g}个百分点、额外暴伤+{rules['SEEK']['extra_critical_damage']*100:g}%",
        'LEECH':f"本人普攻／主动伤害按实际生命伤害{rules['LEECH']['life_steal_percent']}%吸取；不计盾、过量及派生响应，不复起",
        'BREAK':f"普攻命中已起手未释放目标，本击增伤{rules['BREAK']['increase']*100:g}%；每场{rules['BREAK']['limit']}次",
        'BANDAGE':f"有效主动治疗后给原目标{rules['BANDAGE']['shield']}私盾，随后{rules['BANDAGE']['duration']}拍有效；每场{rules['BANDAGE']['limit']}次、每拍1次，同名不叠不续时",
        'LINING':f"首次正直接承伤减伤{rules['LINING']['reduction']*100:g}%；每场1次",
        'LIGHT':f"首次真实自主移动后，随后{rules['LIGHT']['duration']}拍闪避{rules['LIGHT']['dodge']*100:g}%；每场1次",
        'FURY':f"直接物理伤害+{rules['FURY']['increase']*100:g}%",
        'FRAGILE':f"本人有效物防／魔防各-{rules['FRAGILE']['defense_penalty']}，最低0",
        'HEAVY':f"直接承伤减伤{rules['HEAVY']['reduction']*100:g}%（仍受总减伤上限）",
        'SLOW':f"每次真实自主移动后，下一拍禁止自主移动，攻击／技能照常",
        'OVERDRAW':f"本人主动治疗公式+{rules['OVERDRAW']['outgoing_heal_percent']}%",
        'HARDHEAL':f"本人接受恢复-{rules['HARDHEAL']['received_recovery_penalty_percent']}%；含治疗／药品／汲生，城镇明确置满豁免",
        'BASTION':f"拍初生命不高于{rules['BASTION']['hp_threshold_percent']}%时承伤减伤{rules['BASTION']['reduction']*100:g}%，同拍不因治疗／受击切换；总减伤上限75%",
        'RECUP':f"本人接受恢复+{rules['RECUP']['received_recovery_percent']}%，含治疗／药品／汲生；与难愈百分比相加，城镇明确置满豁免",
        'EXPOSED':f"本人承受攻击伤害另乘{1+rules['EXPOSED']['incoming_damage_percent']/100:g}，含普攻／技能／号令响应，先算再扣盾；事件扣血不变",
        'TECHNIQUE':f"本人非派生主动物理伤害+{rules['TECHNIQUE']['increase']*100:g}%；不含普攻和号令响应，不增加次数",
        'BLUNT':f"本人普通物理攻击伤害另乘{1-rules['BLUNT']['basic_damage_penalty_percent']/100:g}；不影响技能／号令响应",
        'TRIAGE':f"本场首次有效主动治疗公式+{rules['TRIAGE']['outgoing_heal_percent']}%；首次有效恢复才消耗，派生恢复不触发",
        'FATIGUE':f"急救消耗后，本场后续主动治疗公式-{rules['FATIGUE']['outgoing_heal_penalty_percent']}%；不削减用药／汲生",
        'CHANNEL':f"本人非派生主动魔法伤害+{rules['CHANNEL']['increase']*100:g}%；不含普攻／治疗／号令响应，不增加次数",
    }
    names={'hp':'生命上限','physical_attack':'物攻','magic_attack':'魔攻','healing_power':'治疗强度','physical_defense':'物防','magic_defense':'魔防'}
    panel='、'.join(names[k]+f'{v:+g}' for k,v in base['stat_modifiers'].items() if v)
    effects=[('负面·' if rules[eid].get('negative') else '')+rules[eid]['name']+'：'+text[eid] for eid in row['effect_ids']]
    return template+' Cost4基准面板：'+panel+'；穿戴固定加成＝基准×本人Cost/4（士兵1/4、佣兵1/2、英雄全额）；'+('；'.join(effects) or '仅面板')


def public_quotes(game,eid):
    import cases
    quotes=cases.get(game.s,eid).get('equipment_quotes')
    if not quotes:return []
    allowed=cases.applicable_families(game)
    return [[{'selection':key,'quote_id':row['quote_id'],'description':details(game,row)}
             for key,row in slot.items() if key.split(':')[0] in allowed] for slot in quotes['slots']]


def describe(game,eid):
    slots=public_quotes(game,eid)
    return '\n'.join(f'第{i+1}件 {row["selection"]}：{row["description"]}' for i,slot in enumerate(slots) for row in slot) or '此交易没有装备报价。'


def drop(game,template,source,key):
    import equipment
    check(key not in game.s['equipment_drops'],'该装备奖励槽已领取，不能再次生成。')
    row=roll(game.cat,template,game.s['seed'],'drop:'+key)
    source={**source,'pool_version':VERSION,'reward_key':key,'form':row['form']}
    item=equipment.issue(game,template,game.s['gear_bag'],source,row['effect_ids'])
    game.s['equipment_drops'][key]={**row,'instance_id':item['instance_id']}
    return item


def validate_state(game):
    import cases
    import equipment
    for eid,case in cases.entries(game.s):
        quotes=case.get('equipment_quotes');credit=case.get('trade_credit')
        if quotes is not None:check(quotes==build_quotes(game,eid),'装备报价与原案件固定候选不一致。')
        if credit and credit.get('equipment_templates'):
            check(quotes is not None,'装备凭单缺少原报价。')
            selections=credit.get('equipment_selections',[])
            check(len(selections)==len(quotes['slots']),'装备凭单选择数量错误。')
            expected=[quotes['slots'][i].get(key) for i,key in enumerate(selections)]
            check(all(expected) and credit.get('equipment_quotes')==expected,'装备凭单内容与原报价不符。')
            check(credit['equipment_templates']==[r['template_id'] for r in expected],'凭单模板与报价不符。')
            if credit['redeemed']:
                ids=credit.get('equipment_instance_ids',[]);check(len(ids)==len(expected),'兑现实例数量错误。')
                for iid,row in zip(ids,expected):
                    item=equipment.original(game,iid)
                    check(item.get('template_id')==row['template_id'] and [e['effect_id'] for e in item.get('effects',[])]==row['effect_ids']
                          and item.get('source',{}).get('quote_id')==row['quote_id'],'兑现装备与已确认报价不符。')
    for key,row in game.s['equipment_drops'].items():
        item=equipment.original(game,row['instance_id'])
        check(row['pool_version']==VERSION and item.get('template_id')==row['template_id']
              and [e['effect_id'] for e in item.get('effects',[])]==row['effect_ids']
              and item.get('source',{}).get('reward_key')==key,'装备掉落与领取记录不符。')
