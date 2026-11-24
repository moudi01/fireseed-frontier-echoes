"""Finite M05-M08 abilities; hero kits execute only in hero_power_v062.

Support creates actual private shields; marks and passive shields commit at tick
end and become usable on the following tick. No ability adds a free attack,
refreshes another ability's charges, or grants soldier command authority.
"""
from copy import deepcopy
import combat as c
from balance_v062 import passive_value


def _card(mid,**fields):
    row=dict(move_id=mid,name=mid,kind='damage',windup=1,cooldown=4,cast_limit=2,
             first_eligible_tick=1,max_targets=1,range=1,medium='near',
             damage_type='physical',coefficient=1,shape='locked_target',interruptible=True)
    row.update(fields);row['delayable_cast']=row['medium']=='spell'
    return row


MERC_CARDS={
    'M05':_card('M05-A',name='隔位护持',kind='private_shield',range=2,medium='tool',shield=24),
    'M06':_card('M06-A',name='绕步',kind='roster_move',cooldown=3,medium='tool'),
    'M07':_card('M07-A',name='留痕札',range=3,cooldown=3,medium='spell',damage_type='magic',coefficient=1),
    'M08':_card('M08-A',name='贴掌截咒',damage_type='magic',coefficient=1.6),
}
HERO_CARDS={}
MOVES={card['move_id'] for card in MERC_CARDS.values()}|set(HERO_CARDS)
MARK_MOVES={'M07-A'}
MOVE_MOVES={'M06-A'}
M05_HP_THRESHOLD=.75
M05_MAX_USES=6
SELF_MOVES={'move','evade','short_dash','book_dash','side_step','charge_move','plan_move','interface_move'}


def initialize(a):
    a['roster_state']={'M05-P':0,'M06-P':0,'M06-ready':False,'M07-P':0,'M08-P':0,
                       }
    a['roster_self_move_action']=None
    a['roster_block_due']=0


def state(a):
    if 'roster_state' not in a:
        initialize(a)
    return a['roster_state']


def enabled(a,kind):return a.get('kind')==kind and a.get('hero_enabled',True)
def _living(v):return v['hp']>0 and not v.get('mechanism') and not v.get('boss_part')
def _queue(b,row):b.setdefault('roster_queue',[]).append(row)


def _shield_later(b,a,v,amount,effect,action_id,tick,consumer=False,parent=None):
    _queue(b,{'kind':'shield','source':a['id'],'target':v['id'],'amount':amount,'effect':effect,
              'action_id':action_id,'created':tick,'starts':tick+1,'expires':tick+2,
              'caused_by_consumer':consumer,'parent_resource':parent})


def _owner(b,v):
    from bosses import owner_of
    return owner_of(b,v)


def _unsafe(prior,alive,side,tick,next_only=False):
    return {tuple(pos) for other in alive if other['side']!=side
            for pending in [prior.get(other['id'])] if pending and pending.get('kind')=='damage'
            and (pending['due']==tick+1 if next_only else tick<=pending['due']<=tick+1)
            for pos in pending.get('cells',[])}


def _walkable(cat,board,pos):return pos in board and cat.terrain[board[pos]]['walkable']


def _neighbors(pos):return [(pos[0]+dq,pos[1]+dr) for dq,dr in c.DIRS]


def _safe_neighbors(v,cat,board,occupied,blocked,unsafe):
    from spatial_moves import crossed
    return sorted(pos for pos in _neighbors(v['pos']) if _walkable(cat,board,pos)
                  and pos not in occupied and pos not in unsafe and not crossed(v['pos'],pos,blocked))


def _claimed_marks(b,side):
    result=set(b.get('mark_reserved',[]))
    for actor in b['actors']:
        pending=actor.get('pending')
        if actor['hp']<=0 or actor['side']!=side or not pending:continue
        ids=pending.get('roster_mark_targets',[])
        if pending.get('move_id') in ('SK-BK04','SK-BK09'):ids=[pending.get('mark_owner',pending['target'])]
        for iid in ids:
            victim=next((v for v in b['actors'] if v['id']==iid),None)
            if victim:result.add(side+':'+_owner(b,victim)['id'])
    return result


def _unmarked(b,a,v,tick,claimed):
    from battle_plans import active
    owner=_owner(b,v)
    return not active(owner.get('standard_marks',{}).get(a['side']),tick) and a['side']+':'+owner['id'] not in claimed


def locks(b):
    return set()


def choose(b,a,card,foes,alive,prior,cat,board,occupied,blocked,tick):
    import veil
    from mechanics import front
    mid=card['move_id']
    if mid not in MOVES:return
    legal=lambda v:c.distance(a['pos'],v['pos'])<=card['range'] and c.visible(cat,board,a['pos'],v['pos'])
    enemies=sorted([v for v in foes if v['hp']>0 and not v.get('mechanism') and legal(v) and veil.targetable(a,v,tick)],
                   key=lambda v:(c.distance(a['pos'],v['pos']),v['id']))
    friends=[v for v in alive if _living(v) and v['side']==a['side'] and legal(v)]
    unsafe=_unsafe(prior,alive,a['side'],tick)
    if mid=='M05-A':
        if a['move_uses'].get(mid,0)>=M05_MAX_USES:return None
        next_danger=_unsafe(prior,alive,a['side'],tick,next_only=True)
        candidates=[v for v in friends if v is not a and (
            v['hp']<=M05_HP_THRESHOLD*v['stats']['hp'] or tuple(v['pos']) in next_danger)]
        if candidates:
            v=min(candidates,key=lambda v:(tuple(v['pos']) not in next_danger,v['hp']/v['stats']['hp'],
                                            bool(v.get('timed_shields')),v['id']))
            return v,[],{}
    elif mid=='H08-B':
        pressured=[v for v in friends if v['hp']<=.6*v['stats']['hp'] or tuple(v['pos']) in unsafe]
        selected=sorted(pressured,key=lambda v:(tuple(v['pos']) not in unsafe,v['hp']/v['stats']['hp'],v is a,v['id']))[:2]
        if selected:return selected[0],[],{'roster_shield_targets':[v['id'] for v in selected]}
    elif mid in MOVE_MOVES:
        from heroes import pet_locks
        held=locks(b)|pet_locks(b)
        if mid=='H08-A':
            candidates=[v for v in friends if v is not a and not v.get('pending') and v['id'] not in held
                        and (v['hp']<=.6*v['stats']['hp'] or tuple(v['pos']) in unsafe)]
        else:candidates=[a]
        for v in sorted(candidates,key=lambda v:(tuple(v['pos']) not in unsafe,v['hp']/v['stats']['hp'],v['id'])):
            if tick<=max(v.get('root_until',0),v.get('move_pause_until',0),v.get('blocked_until',0)):continue
            options=_safe_neighbors(v,cat,board,occupied,blocked,unsafe)
            if mid=='M06-A':
                flanks=[pos for pos in options if any(c.distance(pos,e['pos'])==1 and not front(e,pos) for e in foes if e['hp']>0)]
                if flanks:options=flanks
                elif tuple(v['pos']) not in unsafe and v['hp']>.6*v['stats']['hp']:options=[]
            if options:return v,[min(options)],{'roster_move_origin':v['pos'][:]}
    elif mid in MARK_MOVES:
        claimed=_claimed_marks(b,a['side']);candidates=[];owners=set()
        for v in enemies:
            owner=_owner(b,v)
            if owner['id'] not in owners and _unmarked(b,a,v,tick,claimed):candidates.append(v);owners.add(owner['id'])
        if candidates:
            first=candidates[0];selected=[first]
            if mid=='H09-A':
                second=next((v for v in candidates[1:] if c.distance(first['pos'],v['pos'])==1),None)
                if second:selected.append(second)
            return first,[v['pos'][:] for v in selected],{'roster_mark_targets':[v['id'] for v in selected]}
    elif mid=='M08-A':
        def catches(v):
            old=prior.get(v['id']);current=v.get('pending')
            return bool(old and current and old['id']==current['id'] and old.get('delayable_cast')
                        and not current.get('delayed') and current['due']>tick+card['windup'])
        if enemies:
            v=min(enemies,key=lambda v:(not catches(v),v['id']))
            return v,[v['pos'][:]],{'target_cast':v['pending']['id'] if catches(v) else None}
    elif mid=='H09-B':
        from battle_plans import active
        if enemies:
            v=min(enemies,key=lambda v:(not active(_owner(b,v).get('standard_marks',{}).get(a['side']),tick),c.distance(a['pos'],v['pos']),v['id']))
            return v,[v['pos'][:]],{}
    elif mid=='H10-A':
        options=[];enemy_cells={tuple(v['pos']) for v in enemies}
        for v in enemies:
            facing=c.direction(a['pos'],v['pos'])
            for offsets in ((-1,0),(0,1)):
                cells=[(a['pos'][0]+c.DIRS[(facing+d)%6][0],a['pos'][1]+c.DIRS[(facing+d)%6][1]) for d in offsets]
                if all(_walkable(cat,board,pos) and c.visible(cat,board,a['pos'],pos) for pos in cells):
                    options.append((-sum(pos in enemy_cells for pos in cells),tuple(cells),v['id'],v,facing))
        if options:
            _,cells,_,v,facing=min(options,key=lambda row:row[:3])
            return v,list(cells),{'facing':facing}
    elif mid=='H10-B' and enemies:
        v=enemies[0];return v,[v['pos'][:]],{}


def movement(actions,b,alive,cat,board,tick,log):
    from spatial_moves import active_edges,crossed
    blocked=active_edges(b,tick)
    moves=[];occupied={tuple(v['pos']) for v in alive if v['hp']>0}
    pending={v['id']:v.get('pending') for v in alive}
    for a,action in actions:
        mid=action['move_id']
        if mid not in MOVE_MOVES:continue
        v=next((v for v in alive if v['id']==action['target']),None)
        dest=tuple(action['cells'][0]) if action.get('cells') else None
        reason=None
        if not v or not _living(v) or v['side']!=a['side']:reason='target_unavailable'
        elif mid=='H08-A' and (v is a or v.get('pending')):reason='target_busy_or_self'
        elif v['pos']!=action.get('roster_move_origin'):reason='target_moved'
        elif c.distance(a['pos'],v['pos'])>action['range'] or not c.visible(cat,board,a['pos'],v['pos']):reason='out_of_range_or_sight'
        elif tick<=max(v.get('root_until',0),v.get('move_pause_until',0),v.get('blocked_until',0)):reason='movement_disabled'
        elif dest is None or c.distance(v['pos'],dest)!=1 or not _walkable(cat,board,dest):reason='invalid_path'
        elif dest in occupied or crossed(v['pos'],dest,blocked):reason='occupied_or_closed_edge'
        elif dest in _unsafe(pending,alive,v['side'],tick):reason='destination_no_longer_safe'
        if reason:
            action['roster_move_failed']=reason
            log('roster_move_failed',actor=a['id'],target=action['target'],move=mid,action_id=action['id'],reason=reason)
            continue
        if mid=='M06-A':v['roster_self_move_action']=action['id']
        moves.append((v,list(dest),'hero_move'))
    return moves


def shielded(b,a,v,action,added,tick,log):
    if not enabled(a,'M05') or added<=0 or v['id']==a['id'] or action.get('derived') or action.get('kind')!='private_shield':return
    st=state(a)
    if st['M05-P']:return
    st['M05-P']=1;_shield_later(b,a,a,passive_value('M05-P',8),'M05-P',action['id'],tick)


def mark_created(b,a,v,action_id,effect,tick,log):
    if not enabled(a,'M07') or effect not in ('M07-A','BK04','BK09','SK-BK04','SK-BK09'):return
    st=state(a)
    if st['M07-P']:return
    st['M07-P']=1;_shield_later(b,a,a,passive_value('M07-P',10),'M07-P',action_id,tick)


def _private_now(b,a,v,amount,effect,action,tick,log):
    from heroes import add_shield
    before=max((p['amount'] for p in v['timed_shields'] if p['effect']==effect and p['expires']>=tick),default=0)
    add_shield(b,a,v,amount,effect,action,tick,log)
    shielded(b,a,v,action,max(0,amount-before),tick,log)


def release(b,a,action,alive,cat,board,tick,log):
    import veil
    mid=action['move_id']
    if mid=='M07-A':return # The actual positive hit queues its mark after damage.
    if mid not in MOVES:return
    if mid in MOVE_MOVES:
        v=next((v for v in alive if v['id']==action['target']),None)
        moved=bool(v and not action.get('roster_move_failed') and action.get('cells')
                   and v['pos']==list(action['cells'][0]) and v.get('last_moved_tick')==tick)
        if not moved:
            if not action.get('roster_move_failed'):log('skill_miss',actor=a['id'],target=action['target'],move=mid,action_id=action['id'])
            return
        if mid=='H08-A' and enabled(a,'H08') and v is not a and state(a)['H08-P']<2:
            state(a)['H08-P']+=1;_shield_later(b,a,a,6,'H08-P',action['id'],tick)
        return
    if mid not in {'M05-A','H08-B'}|MARK_MOVES:return
    ids=action.get('roster_mark_targets') if mid in MARK_MOVES else action.get('roster_shield_targets')
    ids=ids if ids is not None else [action['target']]
    accepted=[]
    for iid in ids:
        v=next((v for v in alive if v['id']==iid and v['hp']>0),None)
        valid=bool(v and c.distance(a['pos'],v['pos'])<=action['range'] and c.visible(cat,board,a['pos'],v['pos']))
        if mid in ('M05-A','H08-B'):
            valid=valid and _living(v) and v['side']==a['side'] and (mid!='M05-A' or v is not a)
            if valid:_private_now(b,a,v,action.get('shield',24),mid,action,tick,log);accepted.append(v)
        else:
            valid=valid and v['side']!=a['side'] and not v.get('mechanism') and veil.targetable(a,v,tick)
            if valid and accepted and mid=='H09-A':valid=c.distance(accepted[0]['pos'],v['pos'])==1
            if valid:
                owner=_owner(b,v)
                from battle_plans import active
                valid=not active(owner.get('standard_marks',{}).get(a['side']),tick)
            if valid:
                _queue(b,{'kind':'mark','source':a['id'],'target':owner['id'],'effect':mid,
                          'action_id':action['id'],'created':tick,'starts':tick+1,'expires':tick+2})
                accepted.append(v)
    if not accepted:log('skill_miss',actor=a['id'],target=action['target'],move=mid,action_id=action['id'])


def targets(a,action,alive,cat,board,tick):
    import veil
    enemies=[v for v in alive if v['hp']>0 and v['side']!=a['side'] and not v.get('mechanism')
             and c.distance(a['pos'],v['pos'])<=action['range'] and c.visible(cat,board,a['pos'],v['pos'])
             and veil.targetable(a,v,tick)]
    if action['move_id']=='H10-A':
        return [v for pos in action['cells'] for v in enemies if v['pos']==list(pos)][:2]
    return [v for v in enemies if v['id']==action['target']][:1]


def moved(a,reason):
    if enabled(a,'M06') and (reason in SELF_MOVES or reason=='hero_move' and a.get('roster_self_move_action')):
        state(a)['M06-ready']=True


def attack_bonus(a,v,action,tick):
    from mechanics import front
    if not enabled(a,'M06') or action.get('move_id')!='BASIC' or action.get('derived'):return 0
    if action.get('roster_m06_target')==v['id']:return passive_value('M06-P',.35)
    st=state(a)
    if st['M06-P']>=2 or not st['M06-ready'] or c.distance(a['pos'],v['pos'])!=1:return 0
    if front(v,action.get('projectile_origin',action.get('origin',a['pos']))):return 0
    if c.stat(a,action.get('damage_type','physical')+'_attack',tick)<=0:return 0
    st['M06-P']+=1;st['M06-ready']=False;action['roster_m06_target']=v['id']
    return passive_value('M06-P',.35)


def defense(a,v,action,alive,tick,log):
    return 0


def hit(b,a,v,action,amount,tick,log):
    if amount<=0 or action.get('derived'):return
    if action['move_id']=='M08-A' and enabled(a,'M08') and not state(a)['M08-P']:
        state(a)['M08-P']=1;_shield_later(b,a,a,passive_value('M08-P',10),'M08-P',action['id'],tick)
    if action['move_id']=='M07-A' and enabled(a,'M07'):
        owner=_owner(b,v)
        _queue(b,{'kind':'mark','source':a['id'],'target':owner['id'],'effect':'M07-A',
                  'action_id':action['id'],'created':tick,'starts':tick+1,'expires':tick+2})


def consumed(b,consumer,v,action,mark,tick,log):
    return None # H09 now uses an independent non-consuming contract debuff.


def end_tick(b,tick,log):
    from battle_plans import active,emit
    for a in b['actors']:
        due=a.pop('roster_block_due',0)
        actionable=a['hp']>0 and tick>=a.get('active_from',1)
        if actionable and due:a['blocked_until']=max(a['blocked_until'],due)
        if not actionable:state(a)['M06-ready']=False
        a['roster_self_move_action']=None
    ids={a['id']:a for a in b['actors']};queue=b.setdefault('roster_queue',[])
    while queue:
        row=queue.pop(0);a=ids.get(row['source']);v=ids.get(row['target'])
        if not a or not v or v['hp']<=0:continue
        consumer=row.get('caused_by_consumer',False)
        if row['kind']=='mark':
            v=_owner(b,v)
            existing=v.get('standard_marks',{}).get(a['side'])
            if existing and existing['expires']>=tick:continue
            rid=emit(b,log,'roster_mark_created',actor=a['id'],target=v['id'],origin_action_id=row['action_id'],
                     producer_effect_id=row['effect'],starts=row['starts'],expires=row['expires'],caused_by_consumer=False,generation_depth=1)
            v.setdefault('standard_marks',{})[a['side']]={'starts':row['starts'],'expires':row['expires'],'resource_id':rid,
                'source':a['id'],'producer_effect_id':row['effect'],'caused_by_consumer':False}
            mark_created(b,a,v,row['action_id'],row['effect'],tick,log)
        else:
            existing=[p for p in v['timed_shields'] if p['effect']==row['effect'] and p['expires']>=tick]
            before=max((p['amount'] for p in existing),default=0);amount=max(before,row['amount'])
            starts=min([row['starts']]+[p.get('starts',1) for p in existing])
            expires=max([row['expires']]+[p['expires'] for p in existing])
            rid=emit(b,log,'roster_shield_created',actor=a['id'],target=v['id'],origin_action_id=row['action_id'],
                     producer_effect_id=row['effect'],starts=starts,expires=expires,added=amount-before,
                     caused_by_consumer=consumer,generation_depth=2 if consumer else 1,
                     **({'consumed_resource_id':row['parent_resource']} if row.get('parent_resource') else {}))
            v['timed_shields'][:]=[p for p in v['timed_shields'] if p['effect']!=row['effect']]
            v['timed_shields'].append({'effect':row['effect'],'amount':amount,'source':a['id'],
                'created':row['created'],'starts':starts,'expires':expires,'resource_id':rid,'caused_by_consumer':consumer})
