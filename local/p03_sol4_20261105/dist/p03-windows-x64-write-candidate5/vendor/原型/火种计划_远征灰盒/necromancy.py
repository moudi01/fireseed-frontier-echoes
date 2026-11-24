"""Bounded enemy bone summons and same-instance undead raising."""
from copy import deepcopy
import combat as c
import reinforcements

RAISEABLE = {'EN21','EN22','EN23'}
MOVES = {'EN24-A','EN24-B'}
RAISE_CARD = dict(move_id='EN24-B',name='亡骸再起',kind='revive',coefficient=0,
    range=3,windup=2,cooldown=8,cast_limit=2,first_eligible_tick=2,
    damage_type='magic',medium='magic',max_targets=1,interruptible=True,
    delayable_cast=True,locks_cells=True,shape='locked_remains',revive_percent=50)


def bone(identity, position):
    return {'enemy_id':'FX02','instance_id':identity,'name':'预备骸骨','position':list(position),
        'facing':'D4','mechanism':True,'threat_cost':0,
        'stats':dict(hp=12,physical_attack=0,magic_attack=0,healing_power=0,physical_defense=0,magic_defense=0),
        'basic_attack':dict(range=0,attack_interval=1,damage_type='physical',medium='near'),
        'moves':[], 'briefing':'可攻击摧毁；12生命，不行动。唤骨起手2拍，骨堆在释放拍被摧毁也会取消生成；不单独掉落。'}


def validate(encounter):
    """All declared spawn options share the same headcount and Cost ceiling."""
    spec=encounter.get('necromancy')
    if not spec:return
    units=encounter['units'];spawns=encounter.get('spawn_options',[]);objects=encounter.get('mechanisms',[])
    reinforcements.validate_reserves(encounter)
    owned_bones=set();owned_spawns=set()
    for owner,link in spec['bindings'].items():
        if not any(u['instance_id']==owner and u['enemy_id']=='EN24' for u in units):raise ValueError('骨堆缺少术士')
        if not any(u['instance_id']==link['bone'] and u['enemy_id']=='FX02' for u in objects):raise ValueError('骨堆绑定无效')
        if not any(u.get('instance_id')==link['spawn'] and u['enemy_id']=='EN21' and u['threat_cost']==1 for u in spawns):raise ValueError('骷髅预留无效')
        if link['bone'] in owned_bones or link['spawn'] in owned_spawns:raise ValueError('术士不能重复绑定预留')
        owned_bones.add(link['bone']);owned_spawns.add(link['spawn'])


def choose(actor,card,battle,catalog,board):
    actors=battle['actors'];mid=card['move_id']
    reserved={a['pending']['target'] for a in actors if a['hp']>0 and a['pending'] and a['pending']['move_id'] in MOVES}
    reserved_cells={tuple(cell) for a in actors if a['hp']>0 and a['pending'] and a['pending']['move_id'] in MOVES|{reinforcements.MOVE} for cell in a['pending']['cells']}
    occupied={tuple(a['pos']) for a in actors if a['hp']>0}
    if mid=='EN24-A':
        link=battle.get('necromancy',{}).get('bindings',{}).get(actor['id'])
        if not link or any(a['id']==link['spawn'] for a in actors):return None
        candidates=[a for a in actors if a['id']==link['bone'] and a['hp']>0]
    else:
        candidates=[a for a in actors if a['side']==actor['side'] and a['kind'] in RAISEABLE
            and a['hp']<=0 and a.get('raise_count',0)==0 and tuple(a['pos']) not in occupied]
    for target in sorted(candidates,key=lambda a:(c.distance(actor['pos'],a['pos']),a['id'])):
        pos=tuple(target['pos'])
        if target['id'] in reserved or pos in reserved_cells or pos not in board or not catalog.terrain[board[pos]]['walkable']:continue
        if c.distance(actor['pos'],pos)<=card['range'] and c.visible(catalog,board,actor['pos'],pos):
            return target,[pos]
    return None


def settle(actions,battle,catalog,board,tick,log):
    """After ordinary damage, before victory; arrivals cannot act in this batch."""
    for caster,action in actions:
        mid=action['move_id']
        if mid not in MOVES:continue
        actors=battle['actors'];target=next((a for a in actors if a['id']==action['target']),None)
        pos=tuple(action['cells'][0])
        reason=None
        if not target or tuple(target['pos'])!=pos:reason='TARGET_MISSING'
        elif pos not in board or not catalog.terrain[board[pos]]['walkable']:reason='TERRAIN_BLOCKED'
        elif c.distance(caster['pos'],pos)>action['range'] or not c.visible(catalog,board,caster['pos'],pos):reason='OUT_OF_RANGE_OR_SIGHT'
        elif any(a['hp']>0 and a is not target and tuple(a['pos'])==pos for a in actors):reason='CELL_OCCUPIED'
        elif mid=='EN24-A' and (target['kind']!='FX02' or target['hp']<=0):reason='BONES_DESTROYED'
        elif mid=='EN24-B' and (target['side']!=caster['side'] or target['kind'] not in RAISEABLE or target['hp']>0 or target.get('raise_count',0)>0):reason='REMAINS_UNAVAILABLE'
        if reason:
            log('necromancy_failed',actor=caster['id'],move=mid,action_id=action['id'],target=action['target'],reason=reason);continue
        if mid=='EN24-A':
            link=battle['necromancy']['bindings'][caster['id']]
            template=next(u for u in battle['spawn_options_snapshot'] if u['instance_id']==link['spawn'])
            if any(a['id']==template['instance_id'] for a in actors):
                log('necromancy_failed',actor=caster['id'],move=mid,action_id=action['id'],target=target['id'],reason='ALREADY_SPAWNED');continue
            arrived=reinforcements.arrive(battle,template,pos,caster['id'],tick)
            target['hp']=0;target['consumed_by']=action['id']
            log('summon',actor=caster['id'],move=mid,action_id=action['id'],target=arrived['id'],bone=target['id'],position=list(pos),hp=arrived['hp'],active_from=tick+1)
        else:
            # Keep identity, frozen stats, spent skills, cooldowns and all counters.
            target.update(hp=max(1,target['stats']['hp']*action['revive_percent']//100),raise_count=1,
                pending=None,shield=0,timed_shields=[],gear_dodge=None,prep=[],
                concealment=None,conceal_view=None,deflection=None,view_tick=0,
                trigger_delay=None,deferred_start=None,petal_exposure=None,
                standard_marks={},plan_crit=None,plan_dodge=None,book_dodge=None,strong_window=None,
                root_until=0,blocked_until=0,move_pause_until=0,weak_from=0,weak_until=0,
                stationary=0,command_token=None,command_attack_bonus=0,command_attack_source=None,
                active_from=tick+1,next_attack=max(target['next_attack'],tick+1))
            for pool in battle['shared_shields']:
                pool['members']=[uid for uid in pool['members'] if uid!=target['id']]
            log('revive',actor=caster['id'],move=mid,action_id=action['id'],target=target['id'],position=list(pos),hp=target['hp'],raise_count=1,active_from=tick+1)


def describe(battle):
    if not any(a['kind']=='EN24' for a in battle['actors']):return ''
    lines=['亡骸再起：每名术士2次，每具骷髅／腐尸最多复起1次、半血；占住遗骸格可阻止，复起不刷新技能。']
    for a in battle['actors']:
        if a['kind']=='EN24':lines.append(f"术士 {a['id']}：唤骨余{max(0,1-a['move_uses'].get('EN24-A',0))}，复起余{max(0,2-a['move_uses'].get('EN24-B',0))}")
        if a['hp']<=0 and a['kind'] in RAISEABLE:
            lines.append(f"遗骸 {a['id']} 格{a['pos']}："+('复起已用尽' if a.get('raise_count') else '可被复起；本格可通行'))
    return '\n'.join(lines)
