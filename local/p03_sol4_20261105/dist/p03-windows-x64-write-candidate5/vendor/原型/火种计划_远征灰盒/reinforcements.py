"""Shared reserved arrivals and EN13's destructible, one-tick army cocoon."""
from copy import deepcopy
import combat as c

VERSION='COCOON-0.1'
MOVE='EN13-A'
BRIEFING='缝军起手2拍，在公开候选空格造12生命行军茧，1拍后孵化1名锁矛行军者。每战1次；提前击倒军匠、占住锁定格或打破茧可阻止。造茧后军匠死亡不取消孵化；子体下一拍行动，无额外奖励。'


def validate_reserves(encounter):
    units=encounter['units'];spawns=encounter.get('spawn_options',[])
    objects=encounter.get('mechanisms',[])
    ids=[u['instance_id'] for u in units+spawns+objects if 'instance_id' in u]
    if len(ids)!=len(set(ids)):raise ValueError('召唤实例ID重复')
    if len(units)+len(spawns)>6:raise ValueError('初始与召唤预留合计超出6人')
    if sum(u['threat_cost'] for u in units+spawns)>encounter['threat_budget']:raise ValueError('新旧召唤必须共用威胁预算')
    if encounter.get('spawn_reserve_cost')!=sum(u['threat_cost'] for u in spawns):raise ValueError('召唤预留成本与载荷不符')


def arrive(battle,template,position,owner,tick):
    """Both bone summons and hatched soldiers use the frozen payload exactly once."""
    if any(a['id']==template['instance_id'] for a in battle['actors']):raise ValueError('召唤预留已经使用')
    unit=deepcopy(template);unit['position']=list(position)
    actor=c.enemy_actor(unit);c.initialize_actor(actor)
    actor.update(active_from=tick+1,next_attack=tick+1,summoned_by=owner)
    battle['actors'].append(actor)
    return actor


def install(cat,fixtures):
    fixture=next(f for f in fixtures if f['fixture_id']=='FX01')
    cat.enemy_templates['EN13']['briefing']=BRIEFING
    cat.enemy_templates['EN13']['calibration_unsupported_mechanics']=[]
    for encounter in cat.encounters.values():
        owners=[u for u in encounter['units'] if u['enemy_id']=='EN13']
        if not owners:continue
        reserves=[u for u in encounter.get('spawn_options',[]) if u.get('fixture_id')=='FX01']
        if len(reserves)!=len(owners):raise ValueError('缝军必须逐名登记独立预留')
        links={}
        for i,(owner,spawn) in enumerate(zip(owners,reserves),1):
            owner['briefing']=BRIEFING
            owner['calibration_unsupported_mechanics']=[x for x in owner.get('calibration_unsupported_mechanics',[]) if x!='spawn']
            spawn.update(instance_id=encounter['encounter_id']+':EN17:reserve'+str(i),name=cat.enemy_templates['EN17']['name'],facing='D4')
            links[owner['instance_id']]={'spawn':spawn['instance_id'],'cocoon':encounter['encounter_id']+':FX01:'+str(i),
                                        'candidates':deepcopy(spawn['position_candidates'])}
        encounter['reinforcements']={'version':VERSION,'bindings':links,'fixture':deepcopy(fixture)}
        encounter['calibration_unsupported_mechanics']=[x for x in encounter.get('calibration_unsupported_mechanics',[]) if x!='spawn']
        validate(encounter)


def validate(encounter):
    spec=encounter.get('reinforcements')
    if not spec:return
    validate_reserves(encounter)
    used=set();ids={u['instance_id'] for u in encounter['units']+encounter.get('mechanisms',[])+encounter.get('spawn_options',[])}
    for owner,link in spec['bindings'].items():
        if not any(u['instance_id']==owner and u['enemy_id']=='EN13' for u in encounter['units']):raise ValueError('行军茧缺少军匠')
        spawn=next((u for u in encounter['spawn_options'] if u['instance_id']==link['spawn']),None)
        if not spawn or spawn['enemy_id']!='EN17' or spawn['threat_cost']!=2 or spawn.get('separate_reward') is not False:raise ValueError('行军子体预留无效')
        if any(m['kind'] in ('spawn','summon','revive') for m in spawn['moves']):raise ValueError('行军子体不可再生产')
        if link['spawn'] in used or link['cocoon'] in ids:raise ValueError('行军茧不能重复绑定预留')
        if not link['candidates']:raise ValueError('行军茧缺少候选位置')
        used.add(link['spawn']);ids.add(link['cocoon'])


def choose(actor,card,battle,catalog,board):
    link=battle.get('reinforcements',{}).get('bindings',{}).get(actor['id'])
    if not link or any(a['id'] in (link['cocoon'],link['spawn']) for a in battle['actors']):return None
    occupied={tuple(a['pos']) for a in battle['actors'] if a['hp']>0}
    reserved={tuple(p) for a in battle['actors'] if a['hp']>0 and a['pending']
              and a['pending']['move_id'] in (MOVE,'EN24-A','EN24-B') for p in a['pending']['cells']}
    for pos in sorted(map(tuple,link['candidates']),key=lambda p:(c.distance(actor['pos'],p),p)):
        if pos in board and catalog.terrain[board[pos]]['walkable'] and pos not in occupied|reserved:
            if c.distance(actor['pos'],pos)<=card['range'] and c.visible(catalog,board,actor['pos'],pos):return pos
    return None


def settle(actions,battle,catalog,board,tick,log):
    """Make new cocoons after damage; hatch prior cocoons after their vulnerable tick."""
    spec=battle.get('reinforcements',{})
    for owner,action in actions:
        if action['move_id']!=MOVE:continue
        link=spec['bindings'][owner['id']];pos=tuple(action['cells'][0]);reason=None
        if any(a['id'] in (link['cocoon'],link['spawn']) for a in battle['actors']):reason='RESERVE_USED'
        elif pos not in board or not catalog.terrain[board[pos]]['walkable']:reason='TERRAIN_BLOCKED'
        elif any(a['hp']>0 and tuple(a['pos'])==pos for a in battle['actors']):reason='CELL_OCCUPIED'
        elif c.distance(owner['pos'],pos)>action['range'] or not c.visible(catalog,board,owner['pos'],pos):reason='OUT_OF_RANGE_OR_SIGHT'
        if reason:
            log('cocoon_failed',actor=owner['id'],move=MOVE,action_id=action['id'],reason=reason);continue
        fixture=spec['fixture']
        unit={'instance_id':link['cocoon'],'enemy_id':'FX01','name':fixture['name'],'stats':deepcopy(fixture['stats']),
              'position':list(pos),'mechanism':True,'threat_cost':0,'moves':[],
              'basic_attack':{'range':0,'attack_interval':1,'damage_type':'physical','medium':'near'}}
        cocoon=c.enemy_actor(unit);c.initialize_actor(cocoon)
        cocoon.update(hatch_tick=tick+action['fixture_hatch_delay'],hatch_state='WAITING',spawn_id=link['spawn'],summoned_by=owner['id'])
        battle['actors'].append(cocoon)
        log('cocoon_created',actor=owner['id'],move=MOVE,action_id=action['id'],target=cocoon['id'],position=list(pos),hp=cocoon['hp'],hatch_tick=cocoon['hatch_tick'])
    for cocoon in list(battle['actors']):
        if cocoon.get('hatch_state')!='WAITING':continue
        reason=None;pos=tuple(cocoon['pos'])
        if cocoon['hp']<=0:reason='COCOON_DESTROYED'
        elif tick<cocoon['hatch_tick']:continue
        elif pos not in board or not catalog.terrain[board[pos]]['walkable']:reason='TERRAIN_BLOCKED'
        elif any(a is not cocoon and a['hp']>0 and tuple(a['pos'])==pos for a in battle['actors']):reason='CELL_OCCUPIED'
        elif any(a['id']==cocoon['spawn_id'] for a in battle['actors']):reason='RESERVE_USED'
        if reason:
            cocoon.update(hp=0,hatch_state='CANCELLED')
            log('hatch_failed',actor=cocoon['summoned_by'],target=cocoon['id'],reason=reason);continue
        template=next(u for u in battle['spawn_options_snapshot'] if u['instance_id']==cocoon['spawn_id'])
        child=arrive(battle,template,pos,cocoon['summoned_by'],tick)
        cocoon.update(hp=0,hatch_state='HATCHED')
        log('summon',actor=cocoon['summoned_by'],move=MOVE,target=child['id'],cocoon=cocoon['id'],position=list(pos),hp=child['hp'],active_from=tick+1)


def pending(battle):
    return any(a['hp']>0 and a.get('hatch_state')=='WAITING' for a in battle['actors'])


def describe(battle):
    if not battle.get('reinforcements'):return ''
    lines=['缝军：2拍造12生命行军茧，1拍后孵化EN17；破茧可阻止，造茧后击倒军匠不取消。子体下一拍行动，无额外奖励。']
    for a in battle['actors']:
        if a['kind']=='EN13':lines.append(f"军匠 {a['id']}：缝军余{max(0,1-a['move_uses'].get(MOVE,0))}")
        if a['kind']=='FX01':lines.append(f"行军茧 {a['id']} 格{a['pos']} HP{a['hp']}，{a['hatch_state']}，孵化拍{a['hatch_tick']}")
    return '\n'.join(lines)
