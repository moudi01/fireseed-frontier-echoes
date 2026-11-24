"""Finite plan engines. Resources commit at tick end; consumers add no action."""
from copy import deepcopy
import combat as c

ALL={f'PL{i:02}' for i in range(1,13)}


def has(b,a,plan):
    from skill_books import ALIASES
    return a['side']=='player' and (plan in b['plans'] or ALIASES.get(plan) in a.get('books_equipped',[]))
def active(row,tick):return row and row.get('starts',1)<=tick<=row.get('expires',10**9)


def emit(b,log,kind,**data):
    b['plan_sequence']+=1
    event=f"{b['battle_id']}:plan:{b['plan_sequence']}"
    resource=data.pop('resource_id',event)
    origin=data.get('origin_action_id',data.get('action_id',data.get('cast_id')))
    parent=resource if resource!=event else next((e['event_id'] for e in reversed(b['events']) if e.get('action_id')==origin and origin and 'event_id' in e),None)
    effects={'plan_guard_bypass':'PL03','plan_pursuit':'PL04','plan_second_heal':'PL06','plan_mark_paid':'PL07','plan_mark_created':'PL07',
             'plan_shield_created':'PL08','plan_cast_delayed':'PL09','plan_window_spent':'PL10','plan_crit_created':'PL11','plan_crit_spent':'PL11',
             'plan_move_paid':'PL12','plan_dodge_created':'PL12','standard_mark_consumed':'STANDARD_MARK'}
    effect=data.pop('producer_effect_id',effects.get(kind,'CAST_DELAY'))
    from skill_books import ALIASES
    actor=next((a for a in b['actors'] if a['id']==data.get('actor')),None)
    if actor and effect not in b['plans'] and ALIASES.get(effect) in actor.get('books_equipped',[]):effect=ALIASES[effect]
    log(kind,event_id=event,battle_id=b['battle_id'],actor_id=data.get('actor'),target_id=data.get('target'),
        producer_effect_id=effect,parent_event_id=parent,
        resource_id=resource,caused_by_consumer=data.pop('caused_by_consumer',data.get('generation_depth',1)==2),generation_depth=data.pop('generation_depth',1),**data)
    return event


def budget(a,key,limit,tick):return a['plan_uses'].get(key,0)<limit and a['plan_last'].get(key)!=tick
def spend(a,key,tick):
    a['plan_uses'][key]=a['plan_uses'].get(key,0)+1;a['plan_last'][key]=tick


def private(a,tick,cost,pay=True,for_mark=False):
    pools=sorted([p for p in a['timed_shields'] if active(p,tick) and p.get('created',0)<tick and p['amount']>0 and not (for_mark and p.get('caused_by_consumer'))],key=lambda p:(p['expires'],p.get('created',0),p.get('id',p.get('effect','')),p.get('source','')))
    if a['shield']+sum(p['amount'] for p in pools)<cost:return False
    if not pay:return True
    for pool in pools:
        used=min(cost,pool['amount']);pool['amount']-=used;cost-=used
    a['shield']-=cost;return True


def start_tick(b,tick):
    b['plan_queue']=[];b['mark_reserved']=[]
    for a in b['actors']:
        a['standard_marks']={side:row for side,row in a['standard_marks'].items() if active(row,tick) and a['hp']>0}
        for key in ('plan_crit','plan_dodge','book_dodge'):
            if a.get(key) and a[key]['expires']<tick:a[key]=None
    casts={a['pending']['id'] for a in b['actors'] if a['hp']>0 and a['pending']}
    b['cast_windows']={key:row for key,row in b['cast_windows'].items() if key in casts}


def attack_attempt(b,a,action,tick,log):
    if action.get('kind')!='damage':return
    # Consume preparation at the legal action attempt, before deflection,
    # evasion or target loss. Keep its paired bonus on this action, so all
    # recipients of one attack share it and later actions cannot inherit it.
    # A separate stamp also handles preserved pending actions whose plan
    # attempt was already recorded by an earlier runtime.
    if not action.get('prepared_crit_checked'):
        action['prepared_crit_checked']=True
        prepared=next((p for p in a['prep'] if p['type']=='next_battle_paired_crit' and not p.get('used')),None)
        if prepared and not action.get('derived'):
            prepared['used']=True
            action['prepared_crit']={k:prepared[k] for k in ('critical_chance','extra_critical_damage')}
            log('critical_preparation_consumed',actor=a['id'],action_id=action['id'],move=action['move_id'],
                source=prepared.get('buff_id','CO-CRIT-PREP'))
    if action.get('plan_attempted'):return
    action['plan_attempted']=True
    if not action.get('derived') and active(a.get('plan_crit'),tick):
        action['plan_crit']=a['plan_crit'];a['plan_crit']=None
        emit(b,log,'plan_crit_spent',actor=a['id'],action_id=action['id'],resource_id=action['plan_crit']['resource_id'],generation_depth=2)


def basic_start(b,a,v,action,tick,front,log):
    attack_attempt(b,a,action,tick,log)
    melee=(a['medium']=='near' or a['kind']=='M01') and c.distance(a['pos'],v['pos'])==1
    from bosses import owner_of
    surface=v;v=owner_of(b,v)
    if has(b,a,'PL03') and melee and not front(surface,a['pos']) and budget(a,'PL03',1,tick):
        spend(a,'PL03',tick);action['guard_bypass_target']=surface['id']
        emit(b,log,'plan_guard_bypass',actor=a['id'],target=v['id'],action_id=action['id'])
    stance=0
    if has(b,a,'PL04') and melee and active(v.get('strong_window'),tick) and not a['pursued_enemies'].get(v['id']):
        a['pursued_enemies'][v['id']]=True;action['plan_pursuit_target']=v['id']
        emit(b,log,'plan_pursuit',actor=a['id'],target=v['id'],action_id=action['id'])
    if has(b,a,'PL05') and a['medium']=='projectile' and a['kind'] not in ('M01','M04') and tick-max(a['last_moved_tick'],a['last_basic_attempt'])>=2:stance=max(stance,.25)
    action['plan_stance']=stance;a['last_basic_attempt']=tick
    cast=v['pending'];window=b['cast_windows'].get(cast['id']) if cast else None
    if has(b,a,'PL10') and cast and cast['due']>tick and cast.get('delayed') and window and window['starts']<=tick and not window['used'] and budget(a,'PL10',2,tick):
        spend(a,'PL10',tick);window['used']=True;action['plan_window_target']=v['id']
        emit(b,log,'plan_window_spent',actor=a['id'],target=v['id'],action_id=action['id'],resource_id=window['resource_id'],generation_depth=2)
    key=a['side']+':'+v['id']
    if has(b,a,'PL07') and not action.get('plan_crit') and not v['standard_marks'].get(a['side']) and key not in b['mark_reserved'] and budget(a,'PL07',2,tick) and private(a,tick,6,for_mark=True):
        spend(a,'PL07',tick);b['mark_reserved'].append(key);action['plan_mark_paid']=True
        emit(b,log,'plan_mark_paid',actor=a['id'],target=v['id'],action_id=action['id'],cost=6)


def heal_ready(b,a,card,ready):
    if has(b,a,'PL06') and card['kind'] in ('heal','hero_group_heal') and (card.get('cast_limit') is None or card.get('cast_limit',0)>=2) and card['cooldown']>2 and a['move_uses'].get(card['move_id'],0)==1 and not a['plan_uses'].get('PL06'):
        return ready-1
    return ready


def begin(b,a,action,tick,log):
    if has(b,a,'PL06') and action['kind'] in ('heal','hero_group_heal') and (action.get('cast_limit') is None or action.get('cast_limit',0)>=2) and action['cooldown']>2 and a['move_uses'][action['move_id']]==2 and not a['plan_uses'].get('PL06'):
        spend(a,'PL06',tick);emit(b,log,'plan_second_heal',actor=a['id'],action_id=action['id'],interval=max(2,action['cooldown']-1))
    attack_attempt(b,a,action,tick,log)
    if action.get('start_delay'):delayed(b,a,action,tick,log,action['start_delay']['action_id'],'EN11-A')


def delayed(b,v,cast,tick,log,origin_action_id=None,producer='CAST_DELAY'):
    if cast['id'] in b['cast_windows']:return
    rid=emit(b,log,'plan_cast_window',actor=v['id'],cast_id=cast['id'],origin_action_id=origin_action_id,starts=tick+1,producer_effect_id=producer)
    b['cast_windows'][cast['id']]={'owner':v['id'],'starts':tick+1,'used':False,'resource_id':rid}


def released(b,a,action,tick):
    if a['side']=='enemy' and action['move_id'] not in ('BASIC','CMD-EXTRA'):
        a['strong_window']={'starts':tick+1,'expires':tick+2}


def mark_damage(b,a,v,action,amount,tick,log):
    mark=v['standard_marks'].get(a['side'])
    if amount<=0 or action.get('derived') or not active(mark,tick):return 0
    del v['standard_marks'][a['side']]
    emit(b,log,'standard_mark_consumed',actor=a['id'],target=v['id'],action_id=action['id'],resource_id=mark['resource_id'],flat=4,generation_depth=2)
    if action['move_id']!='CMD-EXTRA' and has(b,a,'PL11') and budget(a,'PL11',2,tick):
        spend(a,'PL11',tick);b['plan_queue'].append(('crit',a['id'],a['id'],action['id']))
    import skill_books
    skill_books.consumed(b,a,action,tick)
    return 4


def hit(b,a,v,action,amount,tick,log,mark_consumed=False):
    if amount<=0 or action.get('derived') or action['move_id']!='BASIC':return
    if action.get('plan_mark_paid') and not mark_consumed and not v.get('mechanism') and not v['standard_marks'].get(a['side']):
        b['plan_queue'].append(('mark',a['id'],v['id'],action['id']))
    cast=v['pending']
    if has(b,a,'PL09') and not action.get('plan_window_target') and cast and cast.get('delayable_cast') and not cast.get('delayed') and cast['due']>tick and b['plan_delay_uses']<2 and b['plan_delay_tick']!=tick:
        cast['due']+=1;cast['delayed']=True;b['plan_delay_uses']+=1;b['plan_delay_tick']=tick
        emit(b,log,'plan_cast_delayed',actor=a['id'],target=v['id'],action_id=action['id'],cast_id=cast['id'],release_tick=cast['due'])
        delayed(b,v,cast,tick,log,action['id'],'PL09')
        import protection
        protection.delayed(v,a,tick,log)


def extend_move(b,a,dest,reason,foes,catalog,board,occupied,blocked,tick,next_cell,log,danger):
    if reason not in ('move','evade') or not has(b,a,'PL12') or not budget(a,'PL12',2,tick) or not private(a,tick,4):return dest,reason
    spend(a,'PL12',tick);path=[tuple(dest)]
    import veil
    reached=any(c.distance(dest,v['pos'])<=a['range'] and c.visible(catalog,board,dest,v['pos']) and veil.targetable(a,v,tick,dest) for v in foes)
    if board[tuple(dest)]!='SHALLOW_WATER' and not reached:
        shadow={**a,'pos':list(dest)}
        nxt=next_cell(catalog,board,shadow,foes,occupied|{tuple(a['pos'])},blocked,tick)
        if nxt and c.distance(dest,nxt)==1 and (reason!='evade' or nxt not in danger):path.append(nxt)
    emit(b,log,'plan_move_paid',actor=a['id'],action_id=f"{a['id']}:move:{tick}",cost=4,path=[list(p) for p in path],caused_by_consumer=True)
    return path,'plan_move'


def moved(b,a,reason,tick,log):
    origin=a['pending']['id'] if a['pending'] and reason in ('short_dash','book_dash','side_step','charge_move','hero_move','hero_path','hero_flash') else f"{a['id']}:move:{tick}"
    if reason=='plan_move':b['plan_queue'].append(('dodge',a['id'],a['id'],origin))
    elif has(b,a,'PL08') and reason in ('move','evade','short_dash','book_dash','side_step','charge_move','hero_move','hero_path','hero_flash') and budget(a,'PL08',3,tick):
        spend(a,'PL08',tick);b['plan_queue'].append(('shield',a['id'],a['id'],origin))


def end_tick(b,tick,log):
    ids={a['id']:a for a in b['actors']}
    for kind,source,target,action_id in b['plan_queue']:
        a=ids[source];v=ids[target]
        if v['hp']<=0:continue
        mark=kind in ('mark','book_mark')
        if mark:
            from bosses import owner_of
            v=owner_of(b,v);target=v['id']
        if mark and v['standard_marks'].get(a['side']):continue
        expires=tick+(3 if kind=='crit' else 2)
        consumer=kind in ('crit','dodge','mark_shield')
        effect={'book_mark':next((e['move'][3:] for e in reversed(b['events']) if e['type']=='windup' and e.get('action_id')==action_id),'BK04'),'support_shield':'BK14','mark_shield':'BK16'}.get(kind)
        if not effect:
            plan={'mark':'PL07','crit':'PL11','dodge':'PL12','shield':'PL08'}[kind]
            from skill_books import ALIASES
            effect=plan if plan in b['plans'] else ALIASES.get(plan,plan)
        rid=emit(b,log,'plan_'+kind+'_created',actor=source,target=target,origin_action_id=action_id,starts=tick+1,expires=expires,caused_by_consumer=consumer,generation_depth=2 if consumer else 1,producer_effect_id=effect)
        row={'starts':tick+1,'expires':expires,'resource_id':rid,'source':source,'caused_by_consumer':consumer}
        if mark:
            v['standard_marks'][a['side']]=row
            if kind=='book_mark':
                import roster_skills
                roster_skills.mark_created(b,a,v,action_id,effect,tick,log)
        elif kind=='crit':v['plan_crit']=row
        elif kind=='dodge':v['plan_dodge']=row
        else:v['timed_shields'].append({**row,'effect':effect,'amount':6 if kind=='mark_shield' else 4,'created':tick})
    b['plan_queue']=[]


def describe(b):
    lines=['行军方案：'+', '.join(b['plans'])]
    for a in b['actors']:
        if a['hp']<=0:continue
        if a['standard_marks']:lines.append('标准标记 '+a['id']+' '+str(a['standard_marks']))
        if a['plan_uses'] or a['plan_crit'] or a['plan_dodge']:lines.append('方案状态 '+a['id']+' '+str({k:a[k] for k in ('plan_uses','plan_crit','plan_dodge')}))
    return '\n'.join(lines)
