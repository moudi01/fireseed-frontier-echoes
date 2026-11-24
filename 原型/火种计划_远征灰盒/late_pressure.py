"""Public late-contract pressure, frozen at departure; never reads the party."""
from copy import deepcopy

VERSION='LATE-PRESSURE-0.63'
LATE_BOSSES={'MG03','MG04','DEMON','ADMIN'}
# Relative to the 0.62 fixed-story encounter, not to ordinary route growth.
BOSS_HP_PERCENT=120
BOSS_ATTACK_PERCENT=150
BOSS_OVERRIDES={'MG03':{'hp':130,'attack':250}}
BOSS_AREAS={'MG03-A':3,'MG03-C':2,'MG04-A':3,'MG04-C':3,
            'DEMON-A':3,'DEMON-B':3,'ADMIN-A':4,'ADMIN-C':4}
GATE_GUARD_VERSION='L9-CROSSFIRE-0.84'
STAGE_GATE_VERSION='RESEARCH-GATE-0.86'
REAR_LOCK_VERSION='RESEARCH-BACKLINE-0.89'
REAR_LOCK_MOVE='C3-REAR-LOCK'


def route_policy(route,facts):
    """Story permissions select a disclosed advanced-contract threat floor.

    Early contracts remain valid training/supply trips after the finale unlock.
    The same selected contract and story facts give every party the same foes.
    """
    from stage_balance import early_middle_policy
    stage=early_middle_policy(route,facts)
    if stage is not None:return stage
    facts=set(facts or ())
    floor=1;milestone=None;hp=100;attack=100
    if route['chapter']>=3:
        if 'FINALE_READY' in facts:floor=6;milestone='FINALE_READY';hp=115;attack=165
        elif 'CH3_COMPLETE' in facts:floor=5;milestone='CH3_COMPLETE';hp=110;attack=130
    return dict(version=VERSION,route_id=route['route_id'],chapter=route['chapter'],
                stage_floor=floor,milestone=milestone,hp_percent=hp,attack_percent=attack,scale_by_party=False,
                frozen_at='departure')


def apply_rules(rules,route,facts):
    pressure=route_policy(route,facts)
    if route['chapter']==3 and pressure['milestone']=='CH3_COMPLETE':
        pressure['stage_gate_watch']=dict(version=STAGE_GATE_VERSION,minimum_level=5,
            unit_ceiling=6,reinforcement='EN16',extra_reward=False,
            notice='研究后普通门战：兵力允许时增加1名后阵校准体，最远活人原格半径1预警，W3/C8循环；可提前分散、走位、打断或延后。原怪与奖励保留。')
        pressure['stage_backline_lock']=dict(version=REAR_LOCK_VERSION,minimum_level=5,
            enhanced_units=1,extra_reward=False,
            notice='研究后普通门战：原阵最多1名远程敌人追加无弹道后阵追印；起手6格且需视线，W3/C5、单体1.8倍，附着最远可见站立人类本人。标记后换格、离开射程或遮挡仍追踪原人；可在起手前避开射程／视线，或打断、合法延后，护盾与减伤有效。原位置、面板、兵力与奖励保留。')
    # The last public contract tier must still pressure a max-level party.
    # Lower tiers and revisited early routes retain their own fixed contents.
    if route['chapter']>=3 and 'FINALE_READY' in (facts or ()) and rules.get('tier_floor',1)>=4:
        pressure.update(attack_percent=300,stage_name='最高险境委任',difficulty_scope='D2')
        pressure['l9_gate_guard']=dict(version=GATE_GUARD_VERSION,minimum_level=9,
            ranged_floor=2,unit_ceiling=6,reinforcement='EN22',extra_reward=False,
            notice='L9及以上门战补足最多两名远射协防；初始与召唤预留合计最多6人，新增弓手穿阵骨箭W2/C6循环。战前公开阵容，不按我方队伍变化。')
    rules['stage_floor']=pressure['stage_floor']
    rules['progression_pressure']=deepcopy(pressure)
    return pressure


def bind(manifest,route,facts):
    manifest['progression_pressure']=apply_rules(manifest['depth_growth'],route,facts)


def preview(game,rules):
    route=next(r for r in game.cat.config['routes'] if r['route_id']==game.s['route'])
    return apply_rules(rules,route,game.s['unlocked_facts'])


def install(catalog):
    """Broaden disclosed locked zones; retain each move's original lock source."""
    def patch(unit):
        for card in unit.get('moves',[]):
            if card['move_id'] in BOSS_AREAS:
                card.update(pressure_radius=1,max_targets=BOSS_AREAS[card['move_id']])
                if card['move_id']=='ADMIN-C':card['range']=7
                if not card['name'].endswith('·扩域'):
                    card['name']+='·扩域'
    for unit in catalog.enemy_templates.values():patch(unit)
    for encounter in catalog.encounters.values():
        for unit in encounter.get('units',[]):patch(unit)


def fixed_encounter(encounter):
    result=deepcopy(encounter)
    for unit in result.get('units',[]):
        if unit['enemy_id'] not in LATE_BOSSES or unit.get('late_pressure_stats',{}).get('version')==VERSION:
            continue
        source=deepcopy(unit['stats'])
        hp=BOSS_OVERRIDES.get(unit['enemy_id'],{}).get('hp',BOSS_HP_PERCENT)
        attack=BOSS_OVERRIDES.get(unit['enemy_id'],{}).get('attack',BOSS_ATTACK_PERCENT)
        unit['stats']['hp']=(source['hp']*hp+99)//100
        for key in ('physical_attack','magic_attack'):
            unit['stats'][key]=source[key]*attack//100
        unit['late_pressure_stats']=dict(version=VERSION,source_stats=source,
            hp_percent=hp,attack_percent=attack)
    return result


def route_encounter(encounter,rules):
    """A public contract's content coefficient, independent of deployed people."""
    pressure=rules.get('progression_pressure')
    if not pressure or pressure['hp_percent']==pressure['attack_percent']==100:
        return encounter
    # Fixed content encounters retain their separate, authored boss calibration.
    from balance_v062 import FIXED_LEVELS
    if any(u['enemy_id'] in FIXED_LEVELS for u in encounter['units']):return encounter
    result=deepcopy(encounter)
    if result.get('contract_pressure')==pressure:return result
    for group in ('units','spawn_options'):
        for unit in result.get(group,[]):
            if 'stats' not in unit:continue
            source=deepcopy(unit['stats'])
            unit['stats']['hp']=(source['hp']*pressure['hp_percent']+99)//100
            for key in ('physical_attack','magic_attack'):
                unit['stats'][key]=source[key]*pressure['attack_percent']//100
            unit['contract_source_stats']=source
    result['contract_pressure']=deepcopy(pressure)
    return result


def gate_source(catalog,source,board_id,level,rules,slot):
    """Apply the disclosed ordinary gate rule before scaling, without party data.

    The research stage and highest L9 contract are disjoint. Original guards,
    reserved arrivals and rewards remain; their shared capacity is respected.
    """
    pressure=rules.get('progression_pressure') or {}
    if pressure.get('stage_gate_watch'):
        return rear_lock_source(catalog,
            stage_gate_source(catalog,source,board_id,level,rules,slot),level,rules,slot)
    spec=pressure.get('l9_gate_guard')
    if (slot!='G' or not spec or level<spec['minimum_level'] or pressure.get('chapter')!=3
            or pressure.get('milestone')!='FINALE_READY' or pressure.get('difficulty_scope')!='D2'):
        return source
    if source.get('l9_gate_guard',{}).get('version')==GATE_GUARD_VERSION:
        return source
    from balance_v062 import FIXED_LEVELS
    if any(u['enemy_id'] in FIXED_LEVELS for u in source['units']):return source
    units=source['units']+source.get('spawn_options',[])
    def ranged(unit):
        basic=unit.get('basic_attack',{})
        return basic.get('range',0)>=3 or any(m.get('kind')=='damage' and m.get('range',0)>=3 for m in unit.get('moves',[]))
    count=sum(ranged(u) for u in units)
    wanted=min(2,max(0,spec['ranged_floor']-count),max(0,spec['unit_ceiling']-len(units)))
    occupied={tuple(u['position']) for u in units+source.get('mechanisms',[]) if 'position' in u}
    for u in source.get('spawn_options',[]):occupied.update(map(tuple,u.get('position_candidates',[])))
    for link in source.get('reinforcements',{}).get('bindings',{}).values():occupied.update(map(tuple,link['candidates']))
    board=catalog.boards[board_id]
    terrain={(c['q'],c['r']):c['terrain_id'] for c in board['cells']}
    cells=[tuple(p) for p in board['enemy_deploy_cells']
        if tuple(p) not in occupied and catalog.terrain[terrain[tuple(p)]]['walkable']]
    result=deepcopy(source);added=[]
    for index in range(min(wanted,len(cells))):
        # Opposite, forward legal flanks. Selection depends only on the board
        # and frozen enemy occupancy, never the deployed player's positions.
        pos=min(cells,key=lambda p:(p[1],p[0] if index%2==0 else -p[0],p));cells.remove(pos)
        unit=deepcopy(catalog.enemy_templates['EN22'])
        iid=f"L9-{source['encounter_id']}-EN22-{index+1}"
        unit.update(instance_id=iid,hp_owner_id=iid,position=list(pos),facing='D4',
            role='normal',elite_promoted=False,separate_reward=False,name=unit['name']+'·侧翼协防')
        card=next(m for m in unit['moves'] if m['move_id']=='EN22-A');card['cast_limit']=None
        unit['briefing']='最高险境侧翼协防：穿阵骨箭W2/C6循环，最多2目标，锁线不追踪，可走位规避或打断；不额外掉落。'
        result['units'].append(unit);result['threat_budget']+=unit['threat_cost']
        added.append(dict(instance_id=iid,enemy_id='EN22',position=list(pos),threat_cost=unit['threat_cost']))
    if added:
        result['required_briefed_species']=list(dict.fromkeys(result.get('required_briefed_species',[])+['EN22']))
    result['l9_gate_guard']=dict(version=GATE_GUARD_VERSION,ranged_before=count,
        unit_ceiling=spec['unit_ceiling'],original_threat_budget=source['threat_budget'],
        extra_threat_cost=sum(u['threat_cost'] for u in added),added=added,extra_reward=False)
    return result


def rear_lock_source(catalog,source,level,rules,slot):
    """Append one disclosed person lock to a native ranged guard, never a party.

    The existing research-stage ground warning remains on its separate caster.
    The mark attaches at a legal visible start, then follows that same person
    without a projectile. Positions, stats, reservations and rewards stay.
    """
    pressure=rules.get('progression_pressure') or {}
    spec=pressure.get('stage_backline_lock') or {}
    if (slot!='G' or spec.get('version')!=REAR_LOCK_VERSION
            or level<spec.get('minimum_level',5) or pressure.get('chapter')!=3
            or pressure.get('milestone')!='CH3_COMPLETE'):
        return source
    if source.get('stage_backline_lock',{}).get('version')==REAR_LOCK_VERSION:
        return source
    from balance_v062 import FIXED_LEVELS
    if any(u['enemy_id'] in FIXED_LEVELS
           or catalog.enemy_templates[u['enemy_id']].get('stats_are_fixed_for_story_battle')
           for u in source['units']):
        return source
    added={u['instance_id'] for u in source.get('stage_gate_watch',{}).get('added',[])}
    priority={'EN22':0,'EN11':1,'EN16':2,'EN20':3}
    candidates=[]
    for unit in source['units']:
        if unit['instance_id'] in added or unit.get('mechanism') or unit.get('boss_part'):
            continue
        basic=unit.get('basic_attack',{})
        dtype=basic.get('damage_type')
        if (unit['enemy_id'] in priority or basic.get('range',0)>=3) and dtype in ('physical','magic'):
            candidates.append(unit)
    if not candidates:
        return source
    selected=min(candidates,key=lambda u:(priority.get(u['enemy_id'],4),u['instance_id']))
    result=deepcopy(source)
    guard=next(u for u in result['units'] if u['instance_id']==selected['instance_id'])
    dtype=guard['basic_attack']['damage_type']
    summary=('无弹道后阵追印：起手需6格射程与地形视线，锁最远可见站立人类本人，同距按ID；'
             'W3预警、C5循环、单体1.8倍。标记附着后换格、离开射程或产生遮挡仍追踪原人，'
             '释放不重验距离或视线、不改选，目标倒地则落空。'
             '可在起手前避开射程／视线，或打断、合法延后，护盾、减伤与合法护卫代受有效。')
    card=dict(move_id=REAR_LOCK_MOVE,name='后阵追印',kind='damage',damage_type=dtype,
        coefficient=1.8,range=6,windup=3,cooldown=5,cast_limit=None,max_targets=1,
        first_eligible_tick=4,shape='stage_locked_person',locks_cells=False,locks_target=True,
        target_rule='farthest_actionable_human_then_stable_id_lock_person_at_start',
        medium='spell',interruptible=True,delayable_cast=True,
        stage_backline_lock=REAR_LOCK_VERSION,mechanic_summary=summary)
    guard['moves'].insert(0,card)
    guard['briefing']=(guard.get('briefing','')+' '+summary).strip()
    result['stage_backline_lock']=dict(version=REAR_LOCK_VERSION,extra_reward=False,
        enhanced=[dict(instance_id=guard['instance_id'],enemy_id=guard['enemy_id'],move_id=REAR_LOCK_MOVE)])
    return result


def stage_gate_source(catalog,source,board_id,level,rules,slot):
    """One disclosed research-stage gate caster, selected without player data.

    Called by freeze_region only for ordinary missions, before depth scaling.
    Existing sources, rewards, reserves and their own action rules stay intact.
    """
    pressure=rules.get('progression_pressure') or {}
    spec=pressure.get('stage_gate_watch') or {}
    if (slot!='G' or spec.get('version')!=STAGE_GATE_VERSION or level<spec['minimum_level']
            or pressure.get('chapter')!=3 or pressure.get('milestone')!='CH3_COMPLETE'):
        return source
    if source.get('stage_gate_watch',{}).get('version')==STAGE_GATE_VERSION:
        return source
    from balance_v062 import FIXED_LEVELS
    if any(u['enemy_id'] in FIXED_LEVELS or catalog.enemy_templates[u['enemy_id']].get('stats_are_fixed_for_story_battle')
           for u in source['units']):
        return source
    units=source['units']+source.get('spawn_options',[])
    if len(units)>=spec['unit_ceiling']:
        return source
    occupied={tuple(u['position']) for u in units+source.get('mechanisms',[])+source.get('board_parts',[]) if 'position' in u}
    for u in source.get('spawn_options',[]):
        occupied.update(map(tuple,u.get('position_candidates',[])))
    for link in source.get('reinforcements',{}).get('bindings',{}).values():
        occupied.update(map(tuple,link['candidates']))
    board=catalog.boards[board_id]
    terrain={(cell['q'],cell['r']):cell['terrain_id'] for cell in board['cells']}
    cells=[tuple(p) for p in board['enemy_deploy_cells'] if tuple(p) not in occupied
           and catalog.terrain[terrain[tuple(p)]]['walkable']]
    if not cells:
        return source
    center=sum(p[0] for p in board['enemy_deploy_cells'])/len(board['enemy_deploy_cells'])
    position=min(cells,key=lambda p:(p[1],-abs(p[0]-center),p))
    result=deepcopy(source)
    unit=deepcopy(catalog.enemy_templates['EN16'])
    iid='C3-'+source['encounter_id']+'-EN16-1'
    unit.update(instance_id=iid,hp_owner_id=iid,position=list(position),facing='D4',
        role='normal',elite_promoted=False,separate_reward=False,name='后阵校准体')
    card=next(card for card in unit['moves'] if card['move_id']=='EN16-A')
    card.update(name='后阵校准脉冲',shape='stage_locked_circle',stage_gate_watch=STAGE_GATE_VERSION,
        range=6,windup=3,cooldown=8,coefficient=4.0,damage_type='magic',medium='spell',
        max_targets=3,cast_limit=None,pressure_radius=1,threat_evasion_horizon=2,
        first_eligible_tick=3,interruptible=True,delayable_cast=True,
        target_rule='farthest_actionable_human_then_stable_id_lock_at_start',
        mechanic_summary='锁射程与视线内最远站立人类的起手原格半径1；W3预警不追踪，最多3目标。提前分散／避险、集火、打断或延后可应对；施法待命和拥挤可能占用撤离窗口。')
    unit['briefing']=card['mechanic_summary']+' 基础普攻与面板沿原校准体；不额外掉落。'
    result['units'].append(unit)
    result['threat_budget']+=unit['threat_cost']
    result['required_briefed_species']=list(dict.fromkeys(result.get('required_briefed_species',[])+['EN16']))
    result['stage_gate_watch']=dict(version=STAGE_GATE_VERSION,unit_ceiling=spec['unit_ceiling'],
        original_threat_budget=source['threat_budget'],extra_threat_cost=unit['threat_cost'],
        added=[dict(instance_id=iid,enemy_id='EN16',position=list(position),threat_cost=unit['threat_cost'])],
        extra_reward=False)
    return result


def locked_area(actor,card,cells,catalog,board):
    """Expand legal original lock cells once, before windup; never track at impact."""
    import combat
    radius=card.get('pressure_radius',0)
    core=list(dict.fromkeys(tuple(p) for p in cells))
    if not radius:return core
    locked=set(core)
    for q,r in core:
        for dq,dr in combat.DIRS:locked.add((q+dq,r+dr))
    penetration=card.get('low_obstacle_penetration',card.get('low_obstacle_penetration_budget',0))
    legal=lambda p:p in board and combat.distance(actor['pos'],p)<=card['range'] and combat.visible(catalog,board,actor['pos'],p,penetration)
    # Original anchors/history cells retain priority. Remaining cells use a fixed
    # spatial order, never the occupants' current HP or position at release.
    return [p for p in core if legal(p)]+sorted((p for p in locked if p not in core and legal(p)),
        key=lambda p:(min(combat.distance(p,c) for c in core),p))


def early_escape(actor,alive,danger,catalog,board,occupied,edges,tick):
    """First legal step within the disclosed escape horizon of a wide warning.

    One-step due-now evasion remains the ordinary rule. A wide warning can need
    several moves; don't require its first step to leave the whole zone.
    Movement recovery and blocked edges remain real and may prevent escape.
    """
    import heapq
    import combat
    import spatial_moves
    warnings=[a['pending'] for a in alive if a['side']!=actor['side'] and a.get('pending')
              and a['pending'].get('pressure_radius') and a['pending']['kind']=='damage'
              and tuple(actor['pos']) in map(tuple,a['pending']['cells'])
              and tick<a['pending']['due']<=tick+a['pending'].get('threat_evasion_horizon',1)]
    if not warnings:return None
    deadline=min(p['due'] for p in warnings)
    hazards=[a['pending'] for a in alive if a['side']!=actor['side'] and a.get('pending')
             and a['pending']['kind']=='damage' and a['pending']['due']<=deadline]
    start=tuple(actor['pos']);queue=[(tick,start,None)];seen={start:tick}
    while queue:
        move_tick,point,first=heapq.heappop(queue)
        if move_tick>deadline:continue
        for dq,dr in combat.DIRS:
            dest=(point[0]+dq,point[1]+dr)
            if dest not in board or dest in occupied or spatial_moves.crossed(point,dest,edges):continue
            terrain=catalog.terrain[board[dest]]
            if not terrain['walkable']:continue
            if any(p['due']<=move_tick and dest in map(tuple,p['cells']) for p in hazards):continue
            step=dest if first is None else first
            if dest not in danger:return step
            next_tick=move_tick+1+terrain.get('movement_recovery_ticks_on_enter',0)
            if next_tick<=deadline and next_tick<seen.get(dest,deadline+1):
                seen[dest]=next_tick;heapq.heappush(queue,(next_tick,dest,step))
    return None
