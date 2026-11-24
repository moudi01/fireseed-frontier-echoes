"""Locked cell attacks and one shared, topology-preserving temporary edge."""
from collections import deque
from copy import deepcopy
import combat as c

PERSON_LOCK='C3-REAR-LOCK'
AREAS={'EN05-A','EN16-A','EN10-A',PERSON_LOCK}
EDGE='EN18-A'
BRIEFINGS={
    'EN05':'盐弧：2拍起手，锁定射程3内两相邻格，最多命中2人，C5、2次；不追踪移出的目标、不改水域、不留持续伤害。释放后下一拍侧后魔防−6。可延后标记不代表当前雾绊能及时反应。',
    'EN16':'划界脉冲：2拍起手，公开射程3内三格直线，最多命中2人，C6、2次；仅释放拍伤害，不追踪、不留地面伤害，不能被雾绊延后。',
    'EN18':'闭合：1拍起手，预约正面2格内一条通行边，释放拍封闭1拍，C6、2次。全场只可预约或封闭一条；起手和释放都保留原有通路，无合法边则不耗次数。封边不挡攻击、不阻止撤退。',
}


def install(cat):
    for uid,text in BRIEFINGS.items():
        cat.enemy_templates[uid]['briefing']=text
        cat.enemy_templates[uid]['calibration_unsupported_mechanics']=[x for x in cat.enemy_templates[uid].get('calibration_unsupported_mechanics',[]) if x!='edge_block']
    for e in cat.encounters.values():
        for u in e['units']:
            if u['enemy_id'] in BRIEFINGS:
                u['briefing']=BRIEFINGS[u['enemy_id']]
                u['calibration_unsupported_mechanics']=[x for x in u.get('calibration_unsupported_mechanics',[]) if x!='edge_block']
        e['calibration_unsupported_mechanics']=[x for x in e.get('calibration_unsupported_mechanics',[]) if x!='edge_block']


def neighbors(pos):return [(pos[0]+dq,pos[1]+dr) for dq,dr in c.DIRS]
def edge_key(a,b):return tuple(sorted((tuple(a),tuple(b))))
def crossed(a,b,blocked):return edge_key(a,b) in blocked


def active_edges(battle,tick):
    row=battle.get('closed_edge')
    return {edge_key(*row['edge'])} if row and row['starts']<=tick<=row['expires'] else set()


def area_choice(actor,card,foes,catalog,board):
    walk={p for p,t in board.items() if catalog.terrain[t]['walkable']}
    legal=lambda p:p in walk and c.distance(actor['pos'],p)<=card['range'] and c.visible(catalog,board,actor['pos'],p)
    if card['move_id']==PERSON_LOCK and card.get('shape')=='stage_locked_person' and card.get('locks_target'):
        humans=[a for a in foes if a['hp']>0 and not a.get('mechanism') and not a.get('boss_part')
                and a['kind']!='PET-H04' and legal(tuple(a['pos']))]
        if not humans:return None
        victim=min(humans,key=lambda a:(-c.distance(actor['pos'],a['pos']),a['id']))
        # This is an identity warning, not dangerous ground. Empty cells keep
        # ordinary evade from spending actions on an ineffective sidestep.
        return victim,[]
    if (card['move_id']=='EN16-A' and card.get('stage_gate_watch')=='RESEARCH-GATE-0.86'
            and card.get('shape')=='stage_locked_circle'):
        humans=[a for a in foes if a['hp']>0 and not a.get('mechanism') and not a.get('boss_part')
                and a['kind']!='PET-H04' and legal(tuple(a['pos']))]
        if not humans:return None
        victim=min(humans,key=lambda a:(-c.distance(actor['pos'],a['pos']),a['id']))
        center=tuple(victim['pos'])
        locked=[center]+sorted(p for p in walk if p!=center and c.distance(center,p)<=1 and legal(p))
        return victim,locked
    for victim in sorted(foes,key=lambda a:(c.distance(actor['pos'],a['pos']),a['id'])):
        first=tuple(victim['pos'])
        if not legal(first):continue
        if card['move_id'] in ('EN05-A','EN10-A'):
            occupied={tuple(a['pos']) for a in foes}
            seconds=[p for p in neighbors(first) if p!=tuple(actor['pos']) and legal(p)]
            if seconds:return victim,[first,min(seconds,key=lambda p:(p not in occupied,p))]
        else:
            for dq,dr in c.DIRS:
                cells=[(actor['pos'][0]+dq*i,actor['pos'][1]+dr*i) for i in (1,2,3)]
                if first in cells and all(legal(p) for p in cells):return victim,cells
    return None


def targets(actor,action,alive,catalog,board):
    if action['move_id']==PERSON_LOCK and action.get('shape')=='stage_locked_person' and action.get('locks_target'):
        victim=next((a for a in alive if a['id']==action['target'] and a['hp']>0
            and a['side']!=actor['side'] and not a.get('mechanism') and not a.get('boss_part')
            and a['kind']!='PET-H04'),None)
        # The legal start attached a mark to this identity. Subsequent movement,
        # range and cover cannot detach it; a fallen target is never replaced.
        return [victim] if victim else []
    locked=list(map(tuple,action['cells']))
    return sorted([a for a in alive if a['side']!=actor['side'] and tuple(a['pos']) in locked
        and tuple(a['pos']) in board and catalog.terrain[board[tuple(a['pos'])]]['walkable']
        and c.distance(actor['pos'],a['pos'])<=action['range'] and c.visible(catalog,board,actor['pos'],a['pos'])],
        key=lambda a:(locked.index(tuple(a['pos'])),a['id']))[:action['max_targets']]


def path(walk,start,target,blocked=()):
    start,target=tuple(start),tuple(target)
    if start not in walk or target not in walk:return None
    todo=deque([start]);parents={start:None}
    while todo:
        here=todo.popleft()
        if here==target:
            result=[]
            while here is not None:result.append(here);here=parents[here]
            return result[::-1]
        for nxt in sorted(neighbors(here)):
            if nxt in walk and nxt not in parents and not crossed(here,nxt,blocked):parents[nxt]=here;todo.append(nxt)
    return None


def preserves_routes(catalog,board,edge,actors):
    """A non-bridge preserves every previously connected pair, including retreat.

    Check static topology and each unit's currently free-space graph. Bodies
    remain ordinary temporary occupiers; the edge cannot sever a path that exists.
    """
    a,b=map(tuple,edge);walk={p for p,t in board.items() if catalog.terrain[t]['walkable']}
    if a not in walk or b not in walk or c.distance(a,b)!=1:return False
    blocked={edge_key(a,b)}
    if path(walk,a,b,blocked) is None:return False
    occupied={tuple(u['pos']) for u in actors if u['hp']>0}
    for u in actors:
        if u['hp']<=0 or u.get('mechanism'):continue
        available=walk-occupied|{tuple(u['pos'])}
        if a in available and b in available and path(available,a,b,blocked) is None:return False
    return True


def legal_edge(actor,card,edge,catalog,board,actors):
    from mechanics import front
    return all(c.distance(actor['pos'],p)<=card['range'] and (list(p)==actor['pos'] or front(actor,p))
               and c.visible(catalog,board,actor['pos'],p) for p in edge) and preserves_routes(catalog,board,edge,actors)


def edge_choice(actor,card,foes,battle,catalog,board):
    if battle.get('edge_reservation') or active_edges(battle,battle['tick']):return None
    walk={p for p,t in board.items() if catalog.terrain[t]['walkable']}
    for victim in sorted(foes,key=lambda a:(c.distance(actor['pos'],a['pos']),a['id'])):
        if not c.visible(catalog,board,actor['pos'],victim['pos']):continue
        route=path(walk,victim['pos'],actor['pos'])
        if not route:continue
        candidates=[edge_key(a,b) for a,b in zip(route,route[1:])]
        for edge in sorted(candidates,key=lambda edge:(min(c.distance(victim['pos'],p) for p in edge),edge)):
            if legal_edge(actor,card,edge,catalog,board,battle['actors']):return victim,edge
    return None


def reserve(battle,actor):
    action=actor['pending']
    if battle.get('edge_reservation'):raise ValueError('场景封边名额已预约')
    battle['edge_reservation']={'owner':actor['id'],'action_id':action['id'],'edge':deepcopy(action['edge']),'due':action['due']}


def cancel_invalid(battle,log):
    row=battle.get('edge_reservation')
    if not row:return
    owner=next((a for a in battle['actors'] if a['id']==row['owner']),None)
    if not owner or owner['hp']<=0 or not owner['pending'] or owner['pending']['id']!=row['action_id']:
        battle['edge_reservation']=None
        log('edge_reservation_cancelled',actor=row['owner'],action_id=row['action_id'])


def start_tick(battle,catalog,board,tick,log):
    old=battle.get('closed_edge')
    if old and old['expires']<tick:
        log('edge_opened',actor=old['owner'],edge=old['edge'],action_id=old['action_id']);battle['closed_edge']=None
    cancel_invalid(battle,log)
    row=battle.get('edge_reservation')
    if not row:return
    owner=next(a for a in battle['actors'] if a['id']==row['owner']);action=owner['pending']
    if action['due']>tick:return
    battle['edge_reservation']=None
    if active_edges(battle,tick) or not legal_edge(owner,action,row['edge'],catalog,board,battle['actors']):
        log('edge_failed',actor=owner['id'],action_id=action['id'],edge=row['edge'],reason='REVALIDATION_FAILED');return
    battle['closed_edge']={'owner':owner['id'],'action_id':action['id'],'edge':row['edge'],
                           'starts':tick,'expires':tick+action['duration_ticks']-1}
    log('edge_closed',actor=owner['id'],action_id=action['id'],edge=row['edge'],expires=battle['closed_edge']['expires'])


def describe(battle):
    lines=[]
    if battle.get('edge_reservation'):lines.append('封边预约：'+str(battle['edge_reservation']))
    if active_edges(battle,battle['tick']):lines.append('本拍封边（仅挡移动、不挡攻击／撤退）：'+str(battle['closed_edge']))
    return '\n'.join(lines)
