"""Cooldown-only standing heals, heat shields and visible elite exposure."""
from copy import deepcopy
import combat as c

HEAL='EN15-A'
HEAT={'EN14-A','EL06-A'}
BRIEFINGS={
    'EN15':'同调：1拍起手，2格内按生命比例锁定最多2名站立缺血友军（可含自己），每人8＋治疗强度，C5循环、不限次数。释放时重验，不换人、不复起、不治疗机制对象；没有药师首次加成。一拍起手短于当前雾绊的观察＋施放窗口。',
    'EN14':'吞热：1拍起手，获得12点私人盾3拍；3拍内下一次普攻仅在目标位于自身正面时增伤25%，背侧出手或落空也耗用。C6循环、不限次数；灯不加盾。释放后保留原普攻时钟，最早下一拍出手。',
    'EL06':'精英吞热：沿用12点私人盾，下一次正面普攻增伤40%；起手拍起连续3拍，侧后受到物理攻击时物防−8，魔防不变。盾与增伤释放后生效，C6循环、不限次数；无灯光加盾。',
}


def install(cat):
    tags={'EN14':{'conditional_basic_buff'},'EN15':{'formula_heal','ally_targeted_heal'},'EL06':{'elite_behavior'}}
    for uid,briefing in BRIEFINGS.items():
        cat.enemy_templates[uid]['briefing']=briefing
        cat.enemy_templates[uid]['calibration_unsupported_mechanics']=[x for x in cat.enemy_templates[uid].get('calibration_unsupported_mechanics',[]) if x not in tags[uid]]
    for e in cat.encounters.values():
        completed=set()
        for u in e['units']:
            if u['enemy_id'] not in BRIEFINGS:continue
            uid=u['enemy_id'];u['briefing']=BRIEFINGS[uid]
            u['calibration_unsupported_mechanics']=[x for x in u.get('calibration_unsupported_mechanics',[]) if x not in tags[uid]]
            completed.update(tags[uid])
        if any(u['enemy_id'] in cat.elite_ids and u['enemy_id']!='EL06' for u in e['units']):completed.discard('elite_behavior')
        e['calibration_unsupported_mechanics']=[x for x in e.get('calibration_unsupported_mechanics',[]) if x not in completed]


def heal_targets(actor,card,alive,catalog,board,tick):
    candidates=[a for a in alive if a['side']==actor['side'] and not a.get('mechanism') and not a.get('boss_part')
        and 0<a['hp']<a['stats']['hp'] and tick>=a.get('active_from',1)
        and c.distance(actor['pos'],a['pos'])<=card['range'] and c.visible(catalog,board,actor['pos'],a['pos'])]
    return sorted(candidates,key=lambda a:(a['hp']/a['stats']['hp'],a['id']))[:card['max_targets']]


def start(actor,card,tick,log):
    exposure=card.get('side_rear_exposure')
    if exposure:
        actor['heat_exposure']={'starts':tick,'expires':tick+exposure['duration_ticks']-1,'modifier':exposure['physical_defense_modifier']}
        log('heat_exposure',actor=actor['id'],move=card['move_id'],**actor['heat_exposure'])


def release(actor,action,tick,log):
    mid=action['move_id'];expiry=tick+action['duration_ticks']-1
    actor['timed_shields'][:]=[p for p in actor['timed_shields'] if p['effect'] not in HEAT]
    actor['timed_shields'].append({'effect':mid,'source':actor['id'],'amount':action['shield'],'expires':expiry,'created':tick})
    bonus=action['bonus_next_basic']
    actor['heat_charge']={'bonus':bonus['damage_bonus'],'remaining':bonus['uses'],'expires':tick+bonus['duration_ticks']-1,
                          'front_only':bonus['front_only'],'move':mid}
    log('private_shield',actor=actor['id'],target=actor['id'],move=mid,amount=action['shield'],expires=expiry)
    log('heat_ready',actor=actor['id'],**deepcopy(actor['heat_charge']))


def consume(actor,action,target,tick,is_front,log):
    charge=actor.get('heat_charge')
    if action['move_id']!='BASIC' or not charge or not charge['remaining'] or tick>charge['expires']:return 0
    charge['remaining']-=1
    eligible=bool(target and (not charge['front_only'] or is_front(actor,target['pos'])))
    bonus=charge['bonus'] if eligible else 0
    log('heat_consumed',actor=actor['id'],action_id=action['id'],target=action['target'],bonus=bonus,front=eligible,expires=charge['expires'])
    return bonus


def defense_modifier(actor,origin,dtype,tick,is_front):
    window=actor.get('heat_exposure')
    if dtype=='physical' and window and window['starts']<=tick<=window['expires'] and not is_front(actor,origin):return window['modifier']
    return 0


def describe(battle):
    lines=[]
    for a in battle['actors']:
        if a['kind'] not in BRIEFINGS:continue
        mid=HEAL if a['kind']=='EN15' else 'EL06-A' if a['kind']=='EL06' else 'EN14-A'
        card=next((move for move in a.get('moves',[]) if move['move_id']==mid),None)
        if card is None:
            timing='未装载该技能'
        else:
            limit=card.get('cast_limit');used=a.get('move_uses',{}).get(mid,0)
            budget='不限次数' if limit is None else f'余{max(0,limit-used)}次'
            timing=f"W{card['windup']}/C{card['cooldown']}，{budget}（本战已起手{used}次）"
        lines.append(f"{a['name']} {a['id']}：{timing}，强化{a.get('heat_charge')}，侧后窗口{a.get('heat_exposure')}")
    return '\n'.join(lines)
