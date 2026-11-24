"""Forty source-tagged book abilities; no inventory or campaign mutation.

All effects use the ordinary action/damage/healing/movement pipeline. Actor
state survives revival and the continuous finale; fresh combat actors receive
fresh state. Books never grant BASICs, native hero casts, cooldown resets or
permanent stat/debuff layers.
"""
from copy import deepcopy
import math

import combat as c
import book_catalog as catalog

VERSION='BOOK-COMBAT-0.72'
PREFIX='SK-SB-'
PASSIVES={'SB-P01','SB-P02','SB-P03','SB-P04'}
DAMAGE_BOOKS={f'SB-D{i:02}' for i in range(1,13)}|{'SB-C01','SB-C03','SB-C04','SB-X01','SB-X02','SB-X04'}
HEAL_BOOKS={'SB-H01','SB-H02','SB-H03','SB-H04','SB-X03'}
AUTONOMOUS={'move','evade','book_dash','short_dash','side_step','hero_move','hero_path','hero_flash','plan_move','charge_move','interface_move'}


def _id(action):
    return action.get('book_id') or (action.get('move_id','')[3:] if action.get('move_id','').startswith(PREFIX) else None)
def _book(action):return bool(_id(action) in catalog.BOOKS and action.get('move_id','').startswith(PREFIX))
def _live(a,tick=0):return a.get('hp',0)>0 and not a.get('mechanism') and not a.get('boss_part') and tick>=a.get('active_from',1)
def _ratio(a):return a['hp']/a['stats']['hp']
def _active(row,tick):return bool(row and row['starts']<=tick<=row['expires'])
def _known(a,b):return b in a.get('books_equipped',[]) and a.get('side','player')=='player'
def _check(ok,message):
    if not ok:raise ValueError('技能书战斗状态无效：'+message)


def initialize(a):
    a.setdefault('book_state',{'version':VERSION,'last':{},'buffs':{},'basic_count':0,
        'basic_seen':[],'support_seen':[],'regens':[],'control_until':0,'control_source':None,'p4_ready':None})
    return a['book_state']


def _state(a):return initialize(a)
def _buff(a,key,tick):
    row=a.get('book_state',{}).get('buffs',{}).get(key)
    return row if _active(row,tick) else None


def _owner(a,actors):return next((v for v in actors if v['id']==a.get('boss_owner')),a) if a.get('boss_part') else a
def _unique(rows,actors):
    result=[];seen=set()
    for row in rows:
        key=_owner(row,actors)['id']
        if key not in seen:seen.add(key);result.append(row)
    return result


def _legal(a,v,cat,board,tick,rng,penetration=0):
    if v.get('hp',0)<=0 or tick<v.get('active_from',1) or c.distance(a['pos'],v['pos'])>rng:return False
    if not c.visible(cat,board,a['pos'],v['pos'],penetration):return False
    if v['side']!=a['side']:
        import veil,heroes
        if not veil.targetable(a,v,tick) or not heroes.targetable(a,v,tick):return False
    return True


def _danger(actors,side,tick,prior=None):
    return {tuple(p) for v in actors if v['side']!=side
            for action in [(prior or {}).get(v['id'],v.get('pending'))]
            if action and action.get('kind')=='damage' and tick<=action['due']<=tick+2
            for p in action.get('cells',[])}


def _private(a,tick):
    return a.get('shield',0)+sum(p['amount'] for p in a.get('timed_shields',[])
        if p.get('starts',1)<=tick<=p['expires'])


def _shield_total(b,a,tick):
    return _private(a,tick)+sum(p['amount'] for p in b.get('shared_shields',[])
        if a['id'] in p.get('members',[]) and p.get('starts',1)<=tick<=p['expires'])


def _same_shield(a,effect,tick):
    return max((p['amount'] for p in a.get('timed_shields',[]) if p.get('effect')==effect and p['expires']>=tick),default=0)


def _shield(b,a,v,amount,effect,action,tick,log,duration=3,starts=None,active=True):
    amount=max(0,math.floor(amount));starts=tick if starts is None else starts
    if not amount or v.get('hp',0)<=0:return 0
    old=[p for p in v.get('timed_shields',[]) if p.get('effect')==effect and p['expires']>=tick]
    previous=max((p['amount'] for p in old),default=0)
    v.setdefault('timed_shields',[])[:]=[p for p in v.get('timed_shields',[]) if p.get('effect')!=effect]
    row={'effect':effect,'source':a['id'],'amount':max(previous,amount),'created':tick,
         'starts':min([starts]+[p.get('starts',1) for p in old]),
         'expires':max([starts+duration-1]+[p['expires'] for p in old]),
         'caused_by_consumer':bool(action.get('derived') or action.get('book_passive'))}
    v['timed_shields'].append(row);added=max(0,amount-previous)
    log('book_shield',actor=a['id'],target=v['id'],move=effect,book_id=_id(action),source='book',
        action_id=action['id'],added=added,amount=row['amount'],starts=row['starts'],expires=row['expires'],derived=bool(action.get('derived') or action.get('book_passive')))
    if active and added:
        support_success(b,a,action,added,tick,log,target=v,kind='private_shield')
        import roster_skills
        roster_skills.shielded(b,a,v,{**action,'kind':'private_shield'},added,tick,log)
    return added


def _heal_amount(a,v,book,tick):
    h=c.stat(a,'healing_power',tick);maximum=v['stats']['hp']
    base,coef,ratio={'SB-H01':(10,.5,.10),'SB-H02':(6,1.2,.10),'SB-H03':(4,.8,.08),
                     'SB-H04':(3,.6,.04),'SB-X03':(8,1.,.25)}[book]
    return math.floor(base+coef*h+ratio*maximum)


def _shield_amount(a,v,book,tick):
    h=c.stat(a,'healing_power',tick);maximum=v['stats']['hp']
    base,ratio,coef={'SB-S01':(8,.18,0),'SB-S02':(6,.15,.6),'SB-S03':(4,.12,.35),
                     'SB-S04':(8,.35,0)}[book]
    return math.floor(base+ratio*maximum+coef*h)


def _direct(action):
    return action.get('kind')=='damage' and not any(action.get(k) for k in ('derived','extra_chain','boss_mimic')) and action.get('move_id') not in ('CMD-EXTRA','MIMIC-CMD-EXTRA')


def _projectile(action,a):
    return action.get('damage_type',a.get('attack_type'))=='physical' and action.get('medium',a.get('basic_medium',a.get('medium')))=='projectile'


def prepare_card(a,card,tick):
    result=deepcopy(card);book=_id(result)
    if book in catalog.BOOKS:
        result.update(source='book',book_id=book,book_effect=book)
    if result.get('damage_type')=='A':result['damage_type']=a['attack_type']
    if _buff(a,'SB-B02',tick) and _direct(result) and _projectile(result,a) and not result.get('book_range_bonus'):
        result['range']=result.get('range',a['range'])+1;result['book_range_bonus']=1
    return result


def _enabled(a,card,tick,soon=0):
    return (a.get('skill_mode')!='off' and card['move_id'] not in a.get('disabled_skills',[])
        and c.has_uses(a,card) and a.get('move_ready',{}).get(card['move_id'],0)<=tick+soon)


def _offense(a,foes,cat,board,tick,soon=0,aim=False):
    probe=deepcopy(a) if aim else a
    if aim:_state(probe)['buffs']['SB-B02']={'starts':tick,'expires':tick+2}
    cards=[]
    for raw in a.get('moves',[]):
        card=prepare_card(probe,raw,tick)
        if card.get('kind')=='damage' and _enabled(a,card,tick,soon):cards.append(card)
    basic=prepare_card(probe,dict(move_id='BASIC',kind='damage',damage_type=a['attack_type'],
        medium=a.get('basic_medium',a.get('medium','near')),range=a['range'],coefficient=1,windup=0),tick)
    if a.get('next_attack',0)<=tick+soon:cards.append(basic)
    return [card for card in cards if any(_legal(a,v,cat,board,tick,card['range'],card.get('penetration',0)) for v in foes)]


def attack_intent(a,foes,cat,board,tick):
    selected=a.get('main_attack','AUTO')
    if selected=='BASIC':return None
    candidates=[prepare_card(a,card,tick) for card in a.get('moves',[])
        if _id(card) in DAMAGE_BOOKS and _known(a,_id(card)) and a.get('skill_mode')!='off'
        and card['move_id'] not in a.get('disabled_skills',[]) and c.has_uses(a,card)]
    if selected!='AUTO':return next((card for card in candidates if card['move_id']==selected),None)
    return next((card for card in candidates if _id(card)!='SB-D10'),None)


def _walk_paths(a,cat,board,occupied,blocked,maximum,unsafe=()):
    import spatial_moves as spatial
    if max(a.get('root_until',0),a.get('blocked_until',0),a.get('move_pause_until',0))>=a.get('_book_tick',1):return []
    queue=[(tuple(a['pos']),[])];paths=[]
    while queue:
        previous,path=queue.pop(0)
        for pos in sorted(spatial.neighbors(previous)):
            if (pos not in board or not cat.terrain[board[pos]]['walkable'] or pos in occupied
                    or pos in path or pos==tuple(a['pos']) or pos in unsafe or spatial.crossed(previous,pos,blocked)):continue
            steps=path+[pos];paths.append(steps)
            if len(steps)<maximum and board[pos]!='SHALLOW_WATER':queue.append((pos,steps))
    return paths


def _area(a,foes,cat,board,tick,rng,radius,limit,actors,healing=False):
    choices=[]
    for center in sorted(board):
        if c.distance(a['pos'],center)>rng or not c.visible(cat,board,a['pos'],center):continue
        rows=[v for v in foes if _legal(a,v,cat,board,tick,99) and c.distance(center,v['pos'])<=radius]
        rows=_unique(sorted(rows,key=lambda v:(_ratio(v),v['id'])),actors)[:limit]
        if not rows:continue
        score=sum(v['stats']['hp']-v['hp'] for v in rows) if healing else len(rows)
        choices.append((-score,-len(rows),center,rows))
    if not choices:return None
    _,_,center,rows=min(choices,key=lambda row:row[:3])
    return rows[0],[list(p) for p in sorted(board) if c.distance(center,p)<=radius],{'book_center':list(center),'book_targets':[v['id'] for v in rows]}


def choose(b,a,card,foes,alive,prior,cat,board,occupied,blocked,tick,next_cell=None):
    book=_id(card)
    if book not in catalog.BOOKS:return None
    card=prepare_card(a,card,tick);rng=card['range'];unsafe=_danger(alive,a['side'],tick,prior)
    enemies=[v for v in foes if _legal(a,v,cat,board,tick,rng,card.get('penetration',0))]
    enemies.sort(key=lambda v:(_ratio(_owner(v,alive)),c.distance(a['pos'],v['pos']),v['id']))
    friend_range=1 if book in ('SB-S03','SB-B01') else rng+1 if book=='SB-H03' else rng
    friends=[v for v in alive if _live(v,tick) and v['side']==a['side'] and _legal(a,v,cat,board,tick,friend_range)]
    pressure=lambda v:tuple(v['pos']) in unsafe or _ratio(v)<=.6
    if book in HEAL_BOOKS:
        injured=[v for v in friends if v['hp']<v['stats']['hp']]
        if book=='SB-H03':
            result=_area(a,injured,cat,board,tick,rng,1,3,alive,True)
            if result and len(result[2]['book_targets'])>=2:return result
            if result and _ratio(result[0])<=.3:
                target=result[0]
                alternatives=[other for other in a.get('moves',[]) if _id(other) in {'SB-H01','SB-H02','SB-X03'}
                              and _enabled(a,other,tick) and _legal(a,target,cat,board,tick,other['range'])]
                if not alternatives:return result
            return None
        threshold={'SB-H01':.65,'SB-H02':.6,'SB-H04':.7,'SB-X03':.6}[book]
        candidates=[v for v in injured if _ratio(v)<=threshold or (book=='SB-H04' and tuple(v['pos']) in unsafe)]
        if book=='SB-H04':
            reserved={v['pending'].get('target') for v in alive if v.get('pending') and _id(v['pending'])==book}
            candidates=[v for v in candidates if v['id'] not in reserved and not _state(v)['regens']]
        if not candidates:return None
        v=min(candidates,key=lambda v:(_ratio(v),-(v['stats']['hp']-v['hp']),v['id']))
        return v,[],{'book_low_health':_ratio(v)<=.3}
    if book.startswith('SB-S'):
        if book in ('SB-S01','SB-S04'):
            if book=='SB-S01' and not pressure(a):return None
            if book=='SB-S04' and (tuple(a['pos']) in unsafe or not _offense(a,foes,cat,board,tick,2)):return None
            if _same_shield(a,card['move_id'],tick)>=_shield_amount(a,a,book,tick):return None
            return a,[],{}
        if book=='SB-S02':
            candidates=[v for v in friends if pressure(v) and _same_shield(v,card['move_id'],tick)<_shield_amount(a,v,book,tick)]
            if candidates:return min(candidates,key=lambda v:(tuple(v['pos']) not in unsafe,_ratio(v),v['id'])),[],{}
            return None
        near=[v for v in friends if c.distance(a['pos'],v['pos'])<=1]
        near.sort(key=lambda v:(not pressure(v),_ratio(v),v['id']))
        if any(pressure(v) and _same_shield(v,card['move_id'],tick)<_shield_amount(a,v,book,tick) for v in near):
            return a,[],{'book_targets':[v['id'] for v in near[:3]]}
        return None
    if book.startswith('SB-M') or book=='SB-X02':
        proxy={**a,'_book_tick':tick}
        if book=='SB-M04':
            import spatial_moves as spatial
            reserved={other['pending'].get('book_move_target') for other in alive if other.get('pending') and _id(other['pending'])=='SB-M04' and other['pending'].get('due',-1)>=tick}
            candidates=[v for v in friends if v is not a and not v.get('pending') and not v.get('hero_setup')
                and v['id'] not in reserved and not _active(v.get('hero_stun'),tick) and tick>max(v.get('root_until',0),v.get('blocked_until',0),v.get('move_pause_until',0)) and pressure(v)]
            for v in sorted(candidates,key=lambda v:(tuple(v['pos']) not in unsafe,_ratio(v),v['id'])):
                options=[p for p in spatial.neighbors(v['pos']) if p in board and cat.terrain[board[p]]['walkable'] and p not in occupied and p not in unsafe
                         and not spatial.crossed(v['pos'],p,blocked) and c.distance(a['pos'],p)<c.distance(a['pos'],v['pos'])]
                if options:return v,[],{'book_move_target':v['id'],'book_move_origin':v['pos'][:],'book_path':[list(min(options))]}
            return None
        maximum=1 if book=='SB-M02' else 2 if book in ('SB-M01','SB-X02') else 3
        paths=_walk_paths(proxy,cat,board,occupied,blocked,maximum,unsafe)
        if not paths:return None
        if book=='SB-M02':
            if tuple(a['pos']) not in unsafe and not any(c.distance(a['pos'],v['pos'])==1 for v in foes):return None
            path=min(paths,key=lambda p:(-min((c.distance(p[-1],v['pos']) for v in foes),default=0),p))
            return a,[],{'book_path':[list(p) for p in path],'book_move_origin':a['pos'][:],'book_move_target':a['id']}
        if book=='SB-M01' and tuple(a['pos']) in unsafe:
            path=min(paths,key=lambda p:(len(p),p))
            return a,[],{'book_path':[list(p) for p in path],'book_move_origin':a['pos'][:],'book_move_target':a['id']}
        if book=='SB-M01' and _offense(a,foes,cat,board,tick):return None
        if book=='SB-M03' and a.get('range',1)>2 and not attack_intent(a,foes,cat,board,tick):return None
        candidates=[]
        desired=1 if book in ('SB-M03','SB-X02') else (attack_intent(a,foes,cat,board,tick) or {}).get('range',a['range'])
        for v in foes:
            if not _legal(a,v,cat,board,tick,rng if book=='SB-X02' else 99):continue
            for path in paths:
                if c.distance(path[-1],v['pos'])<=desired and (book!='SB-X02' or c.distance(path[-1],v['pos'])==1):
                    candidates.append((c.distance(path[-1],v['pos']),len(path),_ratio(v),v['id'],path,v))
        if not candidates:return None
        _,_,_,_,path,v=min(candidates,key=lambda x:x[:5])
        if book!='SB-X02' and c.distance(a['pos'],v['pos'])<=desired:return None
        return v,[],{'book_path':[list(p) for p in path],'book_move_origin':a['pos'][:],'book_move_target':a['id']}
    if book.startswith('SB-B'):
        if book in ('SB-B02','SB-B04'):
            if _buff(a,book,tick):return None
            options=_offense(a,foes,cat,board,tick,2,book=='SB-B02')
            if book=='SB-B02':options=[x for x in options if _projectile(x,a)]
            return (a,[],{}) if options else None
        if book=='SB-B03':
            limited=[v for v in friends if max(v.get('root_until',0),v.get('blocked_until',0))>=tick]
            if limited:return min(limited,key=lambda v:(tuple(v['pos']) not in unsafe,_ratio(v),v['id'])),[],{}
            return None
        near=[v for v in friends if c.distance(a['pos'],v['pos'])<=1 and not _buff(v,'SB-B01',tick)]
        useful=[v for v in near if _offense(v,foes,cat,board,tick,1)]
        if useful:return a,[],{'book_targets':[v['id'] for v in sorted(useful,key=lambda v:(-max(v['stats']['physical_attack'],v['stats']['magic_attack']),v['id']))[:3]]}
        return None
    if book=='SB-C02':
        candidates=[v for v in enemies if not movement_control_immune(v,tick) and not v.get('immune_movement_block') and _state(v)['control_until']<tick and v.get('root_until',0)<tick]
        return (candidates[0],[],{}) if candidates else None
    if book in ('SB-D11','SB-X04'):
        result=_area(a,foes,cat,board,tick,rng,1,3,alive)
        return result
    if book=='SB-Z01':
        def threat(v):
            owner=_owner(v,alive)
            kind=str(owner.get('kind',''))
            boss=owner.get('kind') in ('DEMON','ADMIN') or kind.startswith('MG') or kind.startswith('BX')
            pending=bool(owner.get('pending') and owner['pending'].get('kind')=='damage')
            attack=max(owner.get('stats',{}).get('physical_attack',0),owner.get('stats',{}).get('magic_attack',0))
            return (boss,pending,attack,-c.distance(a['pos'],owner['pos']),owner['id'])
        # The reply is a command-level counter, not a projectile: a high-threat
        # boss within range can be selected even when minions block line of sight.
        candidates=[v for v in foes if _owner(v,alive).get('hp',0)>0
                    and c.distance(a['pos'],_owner(v,alive)['pos'])<=rng]
        high=[v for v in candidates if threat(v)[0] or threat(v)[1]]
        if not high:return None
        v=max(high,key=threat)
        owner=_owner(v,alive)
        return v,[],{'book_nullify_target':owner['id']}
    if not enemies:return None
    if book=='SB-D03':
        options=[]
        for facing in range(6):
            cells=[(a['pos'][0]+c.DIRS[(facing+d)%6][0],a['pos'][1]+c.DIRS[(facing+d)%6][1]) for d in (-1,0,1)]
            cells=[p for p in cells if p in board and c.visible(cat,board,a['pos'],p)]
            rows=_unique([v for v in enemies if tuple(v['pos']) in cells],alive)
            if rows:options.append((-len(rows),facing,rows,cells))
        if not options:return None
        _,facing,rows,cells=min(options,key=lambda x:x[:2])
        if len(rows)==1 and a.get('next_attack',0)<=tick:return None
        return rows[0],[list(p) for p in cells],{'facing':facing}
    if book=='SB-D06':
        rows=_unique(enemies,alive)[:2]
        if len(rows)==1 and a.get('next_attack',0)<=tick and c.distance(a['pos'],rows[0]['pos'])<=a['range']:return None
        return rows[0],[],{'book_targets':[v['id'] for v in rows]}
    if book=='SB-D07':
        options=[]
        for facing in range(6):
            dq,dr=c.DIRS[facing];cells=[]
            for index in range(1,rng+1):
                p=(a['pos'][0]+dq*index,a['pos'][1]+dr*index)
                if p not in board or not c.visible(cat,board,a['pos'],p,1):break
                cells.append(p)
            rows=_unique(sorted([v for v in enemies if tuple(v['pos']) in cells],key=lambda v:(c.distance(a['pos'],v['pos']),v['id'])),alive)[:2]
            if rows:options.append((-len(rows),facing,rows,cells))
        if not options:return None
        _,facing,rows,cells=min(options,key=lambda x:x[:2])
        return rows[0],[list(p) for p in cells],{'facing':facing,'book_coefficients':{_owner(v,alive)['id']:1.6 if index==0 else .8 for index,v in enumerate(rows)}}
    if book in ('SB-C03','SB-C04'):
        def interrupt(v):
            cast=prior.get(v['id'])
            return bool(cast and cast['due']>tick+card['windup'] and cast.get('delayable_cast' if book=='SB-C03' else 'interruptible') and (book!='SB-C03' or not cast.get('delayed')))
        enemies.sort(key=lambda v:(not interrupt(v),_ratio(v),v['id']))
    if book=='SB-D12':
        enemies.sort(key=lambda v:(not ((prior.get(v['id']) or {}).get('due',0)>=tick+card['windup'] or v.get('root_until',0)>=tick+card['windup']),_ratio(v),v['id']))
    if book=='SB-X01':
        enemies.sort(key=lambda v:(not bool(prior.get(v['id'])),_ratio(v),v['id']))
    victim=enemies[0];extra={'target_cast':(prior.get(victim['id']) or {}).get('id')}
    if book=='SB-C01':
        import spatial_moves as spatial
        direction=c.direction(a['pos'],victim['pos']);dq,dr=c.DIRS[direction];dest=(victim['pos'][0]+dq,victim['pos'][1]+dr)
        if dest in board and cat.terrain[board[dest]]['walkable'] and not spatial.crossed(victim['pos'],dest,blocked):extra.update(book_push_from=victim['pos'][:],book_push_to=list(dest))
    if book=='SB-X01':
        cast=prior.get(victim['id'])
        wards=[v for v in alive if _live(v,tick) and v['side']==a['side'] and c.distance(a['pos'],v['pos'])<=2 and cast and cast.get('kind')=='damage' and tuple(v['pos']) in {tuple(p) for p in cast.get('cells',[])}]
        if wards:extra['book_ward']=min(wards,key=lambda v:(_ratio(v),v['id']))['id']
    return victim,[victim['pos'][:]] if book=='SB-D12' else [],extra


def stat(a,name,value,tick):
    buff=_buff(a,'SB-B01',tick)
    return value+(buff.get('flat',{}).get(name,0) if buff else 0)


def movement_control_immune(a,tick):return bool(_buff(a,'SB-B03',tick))


def begin(b,a,action,tick,log):
    """Consume preparations at accepted start, including delayed/cancelled casts."""
    if action.get('book_attack_prepared') or not _direct(action):return
    action['book_attack_prepared']=True
    if _buff(a,'SB-B02',tick) and _projectile(action,a):
        if not action.get('book_range_bonus'):
            action['range']=action.get('range',a['range'])+1;action['book_range_bonus']=1
        action['book_ignore_defense']=.25
        del _state(a)['buffs']['SB-B02']
        log('book_prepared_consumed',actor=a['id'],book_id='SB-B02',move=action['move_id'],action_id=action['id'])
    if _buff(a,'SB-B04',tick):
        action.update(book_force_critical=True,book_critical_extra_min=.5)
        del _state(a)['buffs']['SB-B04']
        log('book_prepared_consumed',actor=a['id'],book_id='SB-B04',move=action['move_id'],action_id=action['id'])


def attack_attempt(b,a,action,tick,log):
    begin(b,a,action,tick,log)
    if action.get('move_id')=='BASIC' and not action.get('book_p4_prepared'):
        action['book_p4_prepared']=True
        row=_state(a).get('p4_ready')
        if _known(a,'SB-P04') and _active(row,tick):
            action['book_p4_bonus']=1.;_state(a)['p4_ready']=None
            log('book_counter_consumed',actor=a['id'],book_id='SB-P04',action_id=action['id'],move='BASIC')


def start_tick(b,cat,board,tick,log):
    heals=[];ids={a['id']:a for a in b['actors']}
    for a in b['actors']:
        state=_state(a)
        state['buffs']={key:row for key,row in state['buffs'].items() if row['expires']>=tick}
        if state.get('p4_ready') and state['p4_ready']['expires']<tick:state['p4_ready']=None
        keep=[]
        for row in state['regens']:
            if row['remaining']<=0 or row['expires']<tick or a['hp']<=0:continue
            if row['next']<=tick and _live(a,tick) and row['caster'] in ids:
                action=deepcopy(row['action']);action.update(derived=True,book_hot=True)
                heals.append((ids[row['caster']],a,row['amount'],action))
                row['remaining']-=1;row['next']=tick+1
                log('book_regeneration',actor=row['caster'],target=a['id'],book_id='SB-H04',action_id=action['id'],remaining=row['remaining'])
            if row['remaining']>0:keep.append(row)
        state['regens']=keep
    return heals


def held(b,actions=None,tick=None):
    return {action['book_move_target'] for _,action in (actions or [])
            if _id(action)=='SB-M04' and action.get('book_move_target')}


def movement(actions,b,alive,cat,board,tick,log):
    ids={a['id']:a for a in alive};result=[]
    for a,action in actions:
        book=_id(action)
        if book not in ('SB-M01','SB-M02','SB-M03','SB-M04','SB-X02'):continue
        v=ids.get(action.get('book_move_target'))
        if not v or not _live(v,tick) or list(v['pos'])!=action.get('book_move_origin') or not action.get('book_path'):continue
        if _active(v.get('hero_stun'),tick) or tick<=max(v.get('root_until',0),v.get('blocked_until',0),v.get('move_pause_until',0)):continue
        if book=='SB-M04':
            if v is a or v.get('pending') or v.get('hero_setup') or not _legal(a,v,cat,board,tick,3):continue
            if c.distance(a['pos'],action['book_path'][-1])>=c.distance(a['pos'],v['pos']):continue
        result.append((v,deepcopy(action['book_path']),'hero_pull' if book=='SB-M04' else 'book_dash'))
    return result


def _actors(ids):return list(ids.values()) if isinstance(ids,dict) else list(ids)


def _control_ok(v,tick,kind):
    if not _live(v,tick) or _state(v)['control_until']>=tick:return False
    if v.get('kind')=='ADMIN' and v.get('super_armor'):return False
    if kind=='root':return not v.get('immune_movement_block') and not movement_control_immune(v,tick)
    if kind=='push':return not v.get('immune_displacement') and not v.get('boss_part_offsets')
    return True


def _control(v,a,action,tick,log,ends):
    state=_state(v);state['control_until']=ends+4
    state['control_source']={'actor':a['id'],'book_id':_id(action),'action_id':action['id'],'tick':tick,'ends':ends}
    log('book_control_resistance',actor=v['id'],source=a['id'],book_id=_id(action),action_id=action['id'],starts=tick,expires=ends+4)


def release(b,a,action,ids,cat,board,tick,log):
    book=_id(action)
    if book not in catalog.BOOKS:return
    actors=_actors(ids);index={v['id']:v for v in actors};v=index.get(action.get('target'))
    if book in ('SB-S01','SB-S04'):v=a
    if book.startswith('SB-S'):
        recipients=[a] if book in ('SB-S01','SB-S04') else [index[x] for x in action.get('book_targets',[]) if x in index] if book=='SB-S03' else [v] if v else []
        for target in recipients:
            rng=1 if book=='SB-S03' else action['range']
            if _live(target,tick) and target['side']==a['side'] and _legal(a,target,cat,board,tick,rng):
                _shield(b,a,target,_shield_amount(a,target,book,tick),action['move_id'],action,tick,log,4 if book=='SB-S04' else 3)
    elif book=='SB-H04' and v and _live(v,tick) and v['side']==a['side'] and _legal(a,v,cat,board,tick,action['range']):
        if not _state(v)['regens']:
            import gear_affixes,event_conditions
            # Snapshot the source's outgoing healing once. Pulses remain
            # committed recovery, not three new active casts/first-heal procs.
            amount=event_conditions.active_heal(a,gear_affixes.outgoing_heal(a,_heal_amount(a,v,book,tick)))
            _state(v)['regens'].append({'book_id':book,'caster':a['id'],'action':deepcopy(action),'amount':amount,'next':tick+1,'expires':tick+3,'remaining':3})
            log('book_regeneration_applied',actor=a['id'],target=v['id'],book_id=book,action_id=action['id'],starts=tick+1,expires=tick+3)
    elif book=='SB-X03' and action.get('book_low_health') and v and _live(v,tick) and v['side']==a['side'] and _legal(a,v,cat,board,tick,3):
        _shield(b,a,v,math.floor(v['stats']['hp']*.2),action['move_id'],action,tick,log)
    elif book=='SB-M02' and a.get('last_moved_tick')==tick and list(a['pos'])!=action.get('book_move_origin'):
        a['book_dodge']={'starts':tick,'expires':tick+1,'source':a['id'],'action_id':action['id']}
    elif book=='SB-C02' and v and v['side']!=a['side'] and _legal(a,v,cat,board,tick,3) and _control_ok(v,tick,'root'):
        v['root_until']=max(v.get('root_until',0),tick+3)
        _control(v,a,action,tick,log,tick+3)
        log('book_root',actor=a['id'],target=v['id'],book_id=book,move=action['move_id'],action_id=action['id'],expires=tick+3)
    elif book=='SB-Z01' and v and v['side']!=a['side']:
        owner=_owner(v,ids)
        owner['next_attack_null']={'starts':tick,'expires':tick+12,'source':a['id'],'action_id':action['id']}
        log('book_next_attack_null',actor=a['id'],target=owner['id'],book_id=book,action_id=action['id'],expires=tick+12)
    elif book=='SB-B01':
        for target in [index[x] for x in action.get('book_targets',[]) if x in index]:
            if not _live(target,tick) or target['side']!=a['side'] or not _legal(a,target,cat,board,tick,1):continue
            old=_buff(target,book,tick);flat={}
            for name in ('physical_attack','magic_attack'):
                base=c.stat(target,name,tick)-(old.get('flat',{}).get(name,0) if old else 0)
                flat[name]=max(base*15/100,(old or {}).get('flat',{}).get(name,0))
            _state(target)['buffs'][book]={'starts':tick,'expires':tick+2,'flat':flat,'source':a['id'],'action_id':action['id']}
            log('book_buff',actor=a['id'],target=target['id'],book_id=book,action_id=action['id'],flat=flat,expires=tick+2)
    elif book in ('SB-B02','SB-B04'):
        _state(a)['buffs'][book]={'starts':tick,'expires':tick+3,'source':a['id'],'action_id':action['id']}
        log('book_buff',actor=a['id'],target=a['id'],book_id=book,action_id=action['id'],expires=tick+3)
    elif book=='SB-B03' and v and v['side']==a['side'] and _live(v,tick) and _legal(a,v,cat,board,tick,3):
        v['root_until']=min(v.get('root_until',0),tick-1);v['blocked_until']=min(v.get('blocked_until',0),tick-1)
        _state(v)['buffs'][book]={'starts':tick,'expires':tick+1,'source':a['id'],'action_id':action['id']}
        log('book_movement_freed',actor=a['id'],target=v['id'],book_id=book,action_id=action['id'],expires=tick+1)


def heals(b,a,action,alive,cat,board,tick):
    book=_id(action)
    if book not in HEAL_BOOKS or book=='SB-H04':return []
    ids={v['id']:v for v in alive};candidates=[]
    if book=='SB-H03':
        center=action.get('book_center',a['pos'])
        if c.distance(a['pos'],center)>action['range'] or not c.visible(cat,board,a['pos'],center):return []
        candidates=[ids[x] for x in action.get('book_targets',[]) if x in ids and c.distance(center,ids[x]['pos'])<=1]
    elif action.get('target') in ids:candidates=[ids[action['target']]]
    return [(v,_heal_amount(a,v,book,tick)) for v in candidates if _live(v,tick) and v['side']==a['side']
            and _legal(a,v,cat,board,tick,99 if book=='SB-H03' else action['range'])]


def targets(a,action,alive,cat,board,tick):
    book=_id(action)
    if book not in DAMAGE_BOOKS:return None
    foes=[v for v in alive if v['side']!=a['side'] and _legal(a,v,cat,board,tick,99,action.get('penetration',0))]
    mode=action.get('target_mode','single');rng=action['range']
    if book=='SB-X02':return [v for v in foes if v['id']==action.get('target') and c.distance(a['pos'],v['pos'])==1]
    if mode=='single':return [v for v in foes if v['id']==action.get('target') and c.distance(a['pos'],v['pos'])<=rng]
    if mode=='multi':return _unique([v for key in action.get('book_targets',[]) for v in foes if v['id']==key and c.distance(a['pos'],v['pos'])<=rng],alive)[:2]
    cells={tuple(p) for p in action.get('cells',[])}
    if mode=='ground':
        center=action.get('book_center')
        if not center or c.distance(a['pos'],center)>rng or not c.visible(cat,board,a['pos'],center):return []
    rows=[v for v in foes if tuple(v['pos']) in cells]
    if mode in ('fan','line'):rows=[v for v in rows if c.distance(a['pos'],v['pos'])<=rng]
    rows=_unique(sorted(rows,key=lambda v:(c.distance(a['pos'],v['pos']),v['id'])),alive)[:action.get('max_targets',1)]
    if mode=='line':action['book_coefficients']={_owner(v,alive)['id']:1.6 if i==0 else .8 for i,v in enumerate(rows)}
    return rows


def _main(a,v,action,b):
    if action.get('sb_primary_recipient') is not None:return v['id']==action['sb_primary_recipient']
    return _owner(v,b['actors'])['id']==next((_owner(x,b['actors'])['id'] for x in b['actors'] if x['id']==action.get('target')),action.get('target'))


def before_hit(b,a,v,action,tick,log,spend_shields=None,*,attack=None):
    book=_id(action);private=_private(v,tick)
    result={'coefficient_add':0.,'defense_factor':1.,'force_critical':bool(action.get('book_force_critical')),
            'critical_extra_min':action.get('book_critical_extra_min',0),'had_shield_before':_shield_total(b,v,tick)>0,'private_before':private}
    if attack is None:attack=c.stat(a,action.get('damage_type',a['attack_type'])+'_attack',tick)
    if book=='SB-X04' and attack>0 and spend_shields:
        requested=math.floor(.6*attack);remaining=spend_shields(v,b.get('shared_shields',[]),requested,tick)
        log('book_shield_stripped',actor=a['id'],target=v['id'],book_id=book,move=action['move_id'],action_id=action['id'],requested=requested,removed=requested-remaining)
    if book=='SB-D04':result['defense_factor']=.6
    if action.get('book_ignore_defense'):result['defense_factor']=min(result['defense_factor'],1-action['book_ignore_defense'])
    if book=='SB-D07':result['coefficient_add']+=action.get('book_coefficients',{}).get(v['id'],action['coefficient'])-action['coefficient']
    if book=='SB-D08' and _ratio(v)<=.35:result['coefficient_add']+=2.1-action['coefficient']
    if action.get('move_id')=='BASIC' and _direct(action) and attack>0:
        state=_state(a)
        if _known(a,'SB-P01') and action['id'] not in state['basic_seen']:
            state['basic_seen'].append(action['id']);state['basic_count']+=1
            if state['basic_count']%3==0:action['book_p1_bonus']=.7
            log('book_basic_counted',actor=a['id'],book_id='SB-P01',action_id=action['id'],count=state['basic_count'])
        if _main(a,v,action,b):result['coefficient_add']+=action.get('book_p1_bonus',0)+action.get('book_p4_bonus',0)
    return result


def _counter(b,v,action,tick,log):
    state=_state(v)
    if not _known(v,'SB-P04') or not _live(v,tick) or tick-state['last'].get('SB-P04',-999)<4:return
    state['last']['SB-P04']=tick;state['p4_ready']={'starts':tick+1,'expires':tick+3,'source_action':action['id']}
    log('book_counter_ready',actor=v['id'],book_id='SB-P04',action_id=action['id'],starts=tick+1,expires=tick+3)


def after_hit(b,a,v,action,amount,tick,log,context=None):
    if amount<=0:return
    book=_id(action);context=context or {}
    if v['side']!=a['side'] and context.get('private_before',0)>0:
        _state(v)['shield_hit_watch']={'tick':tick,'action':deepcopy(action),'source':a['id'],'private_before':context['private_before']}
        if _private(v,tick)<=0:_counter(b,v,action,tick,log)
    if book not in DAMAGE_BOOKS or action.get('derived'):return
    original=v['id']==action.get('target')
    if book=='SB-X01' and not action.get('book_ward_given'):
        ward=next((x for x in b['actors'] if x['id']==action.get('book_ward')),None)
        if ward and _live(ward,tick) and ward['side']==a['side'] and c.distance(a['pos'],ward['pos'])<=2:
            _shield(b,a,ward,math.floor(.2*ward['stats']['hp']),action['move_id'],action,tick,log)
            action['book_ward_given']=True
    if not original:return
    pending=v.get('pending')
    if book=='SB-C03' and pending and pending.get('id')==action.get('target_cast') and pending['due']>tick and pending.get('delayable_cast') and not pending.get('delayed'):
        pending['due']+=1;pending['delayed']=True
        log('cast_delayed',actor=a['id'],target=v['id'],move=action['move_id'],book_id=book,action_id=action['id'],cast_id=pending['id'],release_tick=pending['due'])
        import protection,battle_plans
        protection.delayed(v,a,tick,log);battle_plans.delayed(b,v,pending,tick,log,action['id'],'BOOK')
    elif book=='SB-C04' and pending and pending.get('id')==action.get('target_cast') and pending['due']>tick and pending.get('interruptible') and _control_ok(v,tick,'interrupt'):
        v['pending']=None;v['next_attack']=max(v.get('next_attack',1),tick+1)
        _control(v,a,action,tick,log,tick)
        log('book_interrupt',actor=a['id'],target=v['id'],book_id=book,move=action['move_id'],action_id=action['id'],cast_id=pending['id'])
    elif book=='SB-C01' and action.get('book_push_to') and _control_ok(v,tick,'push'):
        b.setdefault('book_pushes',[]).append({'actor':a['id'],'target':v['id'],'action':deepcopy(action)})


def moved(b,a,reason,tick,log):
    # This hook is called only after a real position change; failed paths never enter it.
    old=[p for p in a.get('timed_shields',[]) if p.get('effect')=='SK-SB-S04']
    if old:
        a['timed_shields'][:]=[p for p in a['timed_shields'] if p.get('effect')!='SK-SB-S04']
        _state(a)['shield_abandoned_tick']=tick
        log('book_stationary_shield_abandoned',actor=a['id'],book_id='SB-S04',amount=sum(p['amount'] for p in old))
    state=_state(a)
    if reason in AUTONOMOUS and _known(a,'SB-P02') and _live(a,tick) and tick-state['last'].get('SB-P02',-999)>=4:
        state['last']['SB-P02']=tick
        action={'id':f"{a['id']}:book-move:{tick}",'move_id':'SK-SB-P02','book_id':'SB-P02','source':'book','derived':True,'book_passive':True}
        _shield(b,a,a,math.floor(4+.12*a['stats']['hp']),'SK-SB-P02',action,tick,log,2,tick+1,False)


def support_success(b,a,action,amount,tick,log=None,*,target=None,kind='heal'):
    if log is None:
        def log(event,**kw):b.setdefault('events',[]).append({'type':event,'tick':tick,**kw})
    committed_hot=action.get('book_hot') is True and _id(action)=='SB-H04' and action.get('source')=='book'
    if amount<=0 or not _known(a,'SB-P03') or not _live(a,tick) or (action.get('derived') and not committed_hot) or action.get('book_passive'):return
    if kind not in ('heal','private_shield'):return
    state=_state(a);aid=action['id']
    if aid in state['support_seen']:return
    state['support_seen'].append(aid)
    if tick-state['last'].get('SB-P03',-999)<4:return
    state['last']['SB-P03']=tick
    effect={'id':aid+':P03','move_id':'SK-SB-P03','book_id':'SB-P03','source':'book','derived':True,'book_passive':True}
    _shield(b,a,a,math.floor(4+.12*a['stats']['hp']),'SK-SB-P03',effect,tick,log,3,tick+1,False)


def end_tick(b,tick,log,cat=None,board=None):
    ids={a['id']:a for a in b['actors']}
    if cat is not None and board is not None:
        import spatial_moves as spatial
        blocked=spatial.active_edges(b,tick);occupied={tuple(a['pos']) for a in b['actors'] if a['hp']>0}
        for row in b.pop('book_pushes',[]):
            a=ids.get(row['actor']);v=ids.get(row['target']);action=row['action'];dest=tuple(action['book_push_to'])
            if not a or not v or not _control_ok(v,tick,'push') or v['pos']!=action.get('book_push_from'):continue
            if dest in occupied or dest not in board or not cat.terrain[board[dest]]['walkable'] or spatial.crossed(v['pos'],dest,blocked):continue
            occupied.discard(tuple(v['pos']));occupied.add(dest);v['pos']=list(dest);v['last_moved_tick']=tick;v['stationary']=0
            import bosses,heroes,roster_skills,battle_plans,gear_affixes
            bosses.moved(b,v);c.enter_shallow(v,board[dest],tick,log);heroes.moved(v,'push',tick);roster_skills.moved(v,'push')
            battle_plans.moved(b,v,'push',tick,log);gear_affixes.moved(v,tick,log);moved(b,v,'push',tick,log)
            _control(v,a,action,tick,log,tick)
            log('book_push',actor=a['id'],target=v['id'],book_id='SB-C01',move=action['move_id'],action_id=action['id'],position=list(dest))
    for v in b['actors']:
        state=_state(v);watch=state.pop('shield_hit_watch',None)
        if watch and watch['tick']==tick and _private(v,tick)<=0 and state.get('shield_abandoned_tick')!=tick:
            _counter(b,v,watch['action'],tick,log)


def validate_battle(b):
    """Semantic validation only; never initialize or repair persisted state here."""
    if b is None:return True
    def integer(value,minimum=0):return type(value) is int and value>=minimum
    def number(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
    ids={a['id'] for a in b.get('actors',[])}
    for a in b.get('actors',[]):
        null=a.get('next_attack_null')
        if null is not None:
            _check(isinstance(null,dict) and integer(null.get('starts')) and integer(null.get('expires'))
                   and null['expires']>=null['starts'] and null.get('source') in ids,'反击无效记录')
        state=a.get('book_state')
        if state is not None:
            _check(isinstance(state,dict) and state.get('version')==VERSION,'版本')
            _check(integer(state.get('basic_count')) and integer(state.get('control_until')),'计数或控制时钟')
            for key in ('basic_seen','support_seen'):
                values=state.get(key);_check(isinstance(values,list) and all(isinstance(x,str) and x for x in values) and len(values)==len(set(values)),key)
            _check(state['basic_count']==len(state['basic_seen']),'普攻计数来源')
            _check(isinstance(state.get('last'),dict) and all(k in PASSIVES and integer(v) for k,v in state['last'].items()),'被动触发时钟')
            _check(isinstance(state.get('buffs'),dict),'增益表')
            for key,row in state['buffs'].items():
                _check(key in ('SB-B01','SB-B02','SB-B03','SB-B04') and isinstance(row,dict),'增益来源')
                _check(integer(row.get('starts')) and integer(row.get('expires')) and row['expires']>=row['starts'],'增益时限')
                if key=='SB-B01':_check(set(row.get('flat',{}))=={'physical_attack','magic_attack'} and all(number(x) for x in row['flat'].values()),'攻击增益')
            ready=state.get('p4_ready')
            if ready is not None:_check(isinstance(ready,dict) and integer(ready.get('starts')) and integer(ready.get('expires')) and ready['expires']>=ready['starts'],'破盾准备')
            _check(isinstance(state.get('regens'),list) and len(state['regens'])<=1,'回春不叠加')
            for row in state['regens']:
                _check(row.get('book_id')=='SB-H04' and row.get('caster') in ids and integer(row.get('remaining'),1) and row['remaining']<=3,'回春来源或次数')
                _check(integer(row.get('next')) and integer(row.get('expires')) and row['expires']>=row['next'] and number(row.get('amount')),'回春时钟或数值')
                _check(_id(row.get('action',{}))=='SB-H04' and row['action'].get('source')=='book' and isinstance(row['action'].get('id'),str),'回春动作')
        for mid,uses in a.get('move_uses',{}).items():
            if not mid.startswith(PREFIX):continue
            book=mid[3:];_check(book in catalog.BOOKS and catalog.BOOKS[book]['card'] is not None and integer(uses),'主动次数')
            limit=catalog.BOOKS[book]['card'].get('cast_limit');_check(limit is None or uses<=limit,'治疗书超额')
        for action in a.get('moves',[])+([a['pending']] if a.get('pending') else []):
            for key in ('book_force_critical','book_attack_prepared','book_p4_prepared'):
                if key in action:_check(type(action[key]) is bool,'准备标记')
            if 'book_range_bonus' in action:_check(type(action['book_range_bonus']) is int and action['book_range_bonus']==1,'增程准备')
            for key,expected in (('book_ignore_defense',.25),('book_critical_extra_min',.5),('book_p1_bonus',.7),('book_p4_bonus',1.)):
                if key in action:_check(type(action[key]) in (int,float) and action[key]==expected,'准备参数 '+key)
            if not action.get('move_id','').startswith(PREFIX):continue
            book=_id(action);_check(book in catalog.BOOKS and catalog.BOOKS[book]['card'] is not None,'未知主动')
            base=catalog.card(book,a)
            _check(action.get('source')=='book' and action.get('book_id')==book,'主动来源')
            for key in ('kind','windup','cooldown','cast_limit','damage_type','medium'):
                _check(action.get(key)==base.get(key),'主动参数 '+key)
            _check(type(action.get('range')) is int and action['range']==base['range']+(1 if action.get('book_range_bonus') else 0),'射程')
            if 'coefficient' in base:_check(number(action.get('coefficient')) and action['coefficient']==base['coefficient'],'伤害系数')
    return True


def support_intent(a,alive,cat,board,tick):
    """Seek a currently useful living ally, using support range, never BASIC range."""
    foes=[v for v in alive if v['side']!=a['side'] and v['hp']>0]
    unsafe=_danger(alive,a['side'],tick);candidates=[]
    for raw in a.get('moves',[]):
        book=_id(raw)
        if book not in HEAL_BOOKS|{'SB-S02','SB-S03','SB-B03'} or not _enabled(a,raw,tick):continue
        rng=1 if book=='SB-S03' else raw['range']
        for v in alive:
            if not _live(v,tick) or v['side']!=a['side'] or c.distance(a['pos'],v['pos'])<=rng:continue
            if book in HEAL_BOOKS:
                threshold={'SB-H01':.65,'SB-H02':.6,'SB-H03':.3,'SB-H04':.7,'SB-X03':.6}[book]
                if _ratio(v)>threshold or v['hp']>=v['stats']['hp']:continue
                if book=='SB-H04' and _state(v)['regens']:continue
            elif book=='SB-B03':
                if max(v.get('root_until',0),v.get('blocked_until',0))<tick:continue
            elif _ratio(v)>.6 and tuple(v['pos']) not in unsafe:continue
            # A visible recipient provides a goal; the shared path finder handles
            # walls/occupation/stance and forbids unsafe approach cells.
            if c.visible(cat,board,a['pos'],v['pos']):candidates.append((_ratio(v),c.distance(a['pos'],v['pos']),v['id'],v,rng))
    if not candidates:return None
    row=min(candidates,key=lambda row:row[:3]);return row[3],row[4]
