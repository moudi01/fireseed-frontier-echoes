"""Tactical fortune effects: one original action/path and conserved shields.

Only normal BASIC and autonomous move/evade are reshaped. No native skill,
extra attack, kill receipt, shield producer or hero resource is manufactured.
"""
from copy import deepcopy


def values(actor):
    return actor.get('journey_conditions', {}) if actor.get('side')=='player' else {}


def sources(actor,key):
    return [r['id'] for r in values(actor).get('records',[])
            if r.get('positive',{}).get(key)]


def _owner(actor):
    return actor.get('boss_owner',actor['id']) if actor.get('boss_part') else actor['id']


def prepare_basic(actor,victim,action,catalog,board,tick,log):
    """Return windup extra; the caller owns action identity and cadence."""
    if (actor.get('side')!='player' or action.get('move_id')!='BASIC'
            or any(action.get(key) for key in ('derived','extra_chain','boss_mimic'))):return 0
    data=values(actor)
    radius=int(data.get('melee_pierce_radius',0))
    if radius and action.get('medium',actor['medium'])=='near':
        action.update(fortune_mode='pierce',fortune_radius=radius,
            fortune_max_extra=int(data['melee_pierce_targets']),
            fortune_extra_coefficient=data['melee_pierce_coefficient'],
            fortune_base_range=action['range'],fortune_base_ready=tick+actor['interval'],
            fortune_sources=sources(actor,'melee_pierce_radius'))
        log('fortune_pierce_prepared',actor=actor['id'],action_id=action['id'],
            condition_ids=action['fortune_sources'],target=victim['id'],cell=victim['pos'][:],
            radius=radius,max_extra=action['fortune_max_extra'],base_ready=action['fortune_base_ready'])
    elif data.get('ranged_burst_radius') and actor['range']>1 and actor['medium']!='near':
        import combat as c
        center=tuple(victim['pos']);cells=[p for p in [center]+[(center[0]+dq,center[1]+dr) for dq,dr in c.DIRS] if p in board]
        action.update(fortune_mode='burst',fortune_center=list(center),cells=[list(p) for p in cells],
            fortune_sources=sources(actor,'ranged_burst_radius'),fortune_splash=data.get('ranged_splash_coefficient',.6),
            fortune_started_tick=tick,area=True,max_targets=None,windup=1,due=tick+1,delayable_cast=False,interruptible=True)
        log('fortune_burst_windup',actor=actor['id'],action_id=action['id'],condition_ids=action['fortune_sources'],
            target=victim['id'],center=list(center),cells=deepcopy(action['cells']),release_tick=tick+1)
        return 1
    return 0


def interval_penalty(actor,action):
    return int(values(actor).get('basic_interval_penalty',0)) if action.get('fortune_mode')=='pierce' and action.get('fortune_extra_owners') else 0


def basic_allowed(actor,tick):
    return tick>actor.get('fortune_basic_block_until',0)


def basic_targets(actor,action,existing,alive,catalog,board,tick,log):
    """Return None for untouched actions; preserve native melee area targets."""
    import combat as c
    mode=action.get('fortune_mode')
    if action.get('move_id')!='BASIC' or not mode:return None
    foes=[v for v in alive if v['side']!=actor['side'] and v['hp']>0]
    coefficients={};victims=[]
    if mode=='pierce':
        primary=next((v for v in foes if v['id']==action['target']),None)
        victims=list(existing)
        owners={_owner(v) for v in victims}
        extra=[]
        # Release geometry owns both the extra targets and the cadence cost.
        # Existing native areas retain their targets and coefficients.
        if (primary and _owner(primary) in owners
                and c.distance(actor['pos'],primary['pos'])<=action['fortune_base_range']
                and c.visible(catalog,board,actor['pos'],primary['pos'])):
            candidates=sorted([v for v in foes
                if _owner(v) not in owners and tick>=v.get('active_from',1)
                and board.get(tuple(v['pos']),'HIGH_OBSTACLE')!='HIGH_OBSTACLE'
                and c.distance(primary['pos'],v['pos'])<=action['fortune_radius']
                and c.visible(catalog,board,actor['pos'],v['pos'])
                and c.visible(catalog,board,primary['pos'],v['pos'])],
                key=lambda v:(c.distance(primary['pos'],v['pos']),c.distance(actor['pos'],v['pos']),v['id']))
            for victim in candidates:
                owner=_owner(victim)
                if owner in owners:continue
                owners.add(owner);extra.append(victim)
                coefficients[victim['id']]=action['fortune_extra_coefficient']
                if len(extra)>=action['fortune_max_extra']:break
            victims.extend(extra)
        action['fortune_extra_ids']=[v['id'] for v in extra]
        action['fortune_extra_owners']=[_owner(v) for v in extra]
        action['fortune_primary_cell']=primary['pos'][:] if primary else None
        action['fortune_hit_origin']=actor['pos'][:]
    else:
        center=tuple(action['fortune_center']);origin=actor['pos'][:]
        if center not in board or c.distance(origin,center)>action['range'] or not c.visible(catalog,board,origin,center):return []
        cells={tuple(p) for p in action['cells']}
        victims=sorted([v for v in foes if tuple(v['pos']) in cells and c.visible(catalog,board,origin,v['pos'])],
            key=lambda v:(tuple(v['pos'])!=center,c.distance(center,v['pos']),v['id']))
        coefficients={v['id']:1 if tuple(v['pos'])==center else action['fortune_splash'] for v in victims}
        action['fortune_hit_origin']=origin
    action['fortune_coefficients']=coefficients
    log('fortune_basic_targets',actor=actor['id'],action_id=action['id'],condition_ids=action.get('fortune_sources',[]),
        mode=mode,targets=[dict(id=v['id'],cell=v['pos'][:],coefficient=coefficients.get(v['id'],
            action.get('hero_coefficients',{}).get(v['id'],action['coefficient']))) for v in victims],
        locked_center=action.get('fortune_center'),
        **(dict(extra_targets=action['fortune_extra_ids'],extra_owner_ids=action['fortune_extra_owners'],
                radius=action['fortune_radius'],primary_cell=action['fortune_primary_cell']) if mode=='pierce' else {}))
    return victims


def extend_move(actor,destination,reason,original_reason,foes,catalog,board,occupied,edges,tick,next_cell,danger):
    """Normalize one path to max(existing, fortune); never call PL12 again."""
    import combat as c
    import veil
    steps=int(values(actor).get('stride_steps',0))
    if steps<2 or original_reason not in ('move','evade'):return None
    path=[tuple(p) for p in destination] if reason=='plan_move' else [tuple(destination)]
    # Invalid first steps are rejected by the caller without any activation.
    while len(path)<steps:
        point=path[-1]
        if point not in board or board[point]=='SHALLOW_WATER':break
        if any(c.distance(point,v['pos'])<=actor['range'] and c.visible(catalog,board,point,v['pos'])
               and veil.targetable(actor,v,tick,point) for v in foes):break
        shadow={**actor,'pos':list(point)}
        nxt=next_cell(catalog,board,shadow,foes,occupied|{tuple(actor['pos'])}|set(path[:-1]),edges,tick)
        if not nxt or c.distance(point,nxt)!=1 or tuple(nxt) in path or (original_reason=='evade' and tuple(nxt) in danger):break
        path.append(tuple(nxt))
    return path


def moved(actor,path,original_reason,tick,log):
    if not path or original_reason not in ('move','evade') or not values(actor).get('stride_steps'):return
    actor['fortune_basic_block_until']=max(actor.get('fortune_basic_block_until',0),tick+1)
    log('fortune_stride',actor=actor['id'],action_id=f"{actor['id']}:move:{tick}",
        condition_ids=sources(actor,'stride_steps'),path=[list(p) for p in path],
        basic_start_blocked_through=tick+1)


def private_amount(actor,tick):
    return actor['shield']+sum(p['amount'] for p in actor['timed_shields']
        if p.get('starts',1)<=tick<=p['expires'] and p['amount']>0)


def relay(battle,victim,remaining,alive,catalog,board,tick,action,damage,healing,spend,log):
    """Existing private shield becomes immediate absorption, never a new pool."""
    import combat as c
    distance=int(values(victim).get('shield_relay_range',0))
    if remaining<=0 or not distance or victim.get('mechanism') or victim.get('boss_part'):return remaining
    available_hp=lambda a:a['hp']+healing.get(a['id'],0)-damage.get(a['id'],0)
    if available_hp(victim)<=0:return remaining
    donors=sorted([a for a in alive if a!=victim and a['side']==victim['side'] and not a.get('mechanism')
        and not a.get('boss_part') and available_hp(a)>0 and tick>=a.get('active_from',1)
        and a.get('fortune_relay_tick')!=tick and c.distance(a['pos'],victim['pos'])<=distance
        and c.visible(catalog,board,a['pos'],victim['pos']) and private_amount(a,tick)>0],
        key=lambda a:(c.distance(a['pos'],victim['pos']),a['id']))
    for donor in donors:
        before=private_amount(donor,tick);wanted=min(remaining,before)
        transferred=wanted-spend(donor,[],wanted,tick)
        if transferred<=0:continue
        donor['fortune_relay_tick']=tick
        donor['fortune_relay_exposure']=dict(starts=tick+1,expires=tick+1,
            amount=values(victim).get('relay_donor_exposure',.1),condition_ids=sources(victim,'shield_relay_range'))
        remaining-=transferred
        log('fortune_shield_relay',actor=donor['id'],donor=donor['id'],target=victim['id'],
            action_id=action['id'],condition_ids=sources(victim,'shield_relay_range'),
            donor_cell=donor['pos'][:],target_cell=victim['pos'][:],amount=transferred,
            donor_private_before=before,donor_private_after=private_amount(donor,tick),
            exposure_starts=tick+1,exposure_expires=tick+1)
        if remaining<=0:break
    return remaining


def incoming_extra(actor,tick):
    row=actor.get('fortune_relay_exposure')
    return row['amount'] if row and row['starts']<=tick<=row['expires'] else 0


def describe(spec):
    p=spec['positive']
    if p.get('melee_pierce_radius'):return f"近击普攻额外波及主目标周围{p['melee_pierce_radius']}格内最多{p['melee_pierce_targets']}个独立敌人，各0.6倍；双方视线均须畅通，不重复原生目标或同一Boss本体；有额外目标才使本次普攻间隔+1拍，落单不减速，护盾吸收或闪避不退款"
    if p.get('ranged_burst_radius'):return f"远程普攻多蓄力1拍，锁原目标格周围1格爆散；中心1倍、溅射{p['ranged_splash_coefficient']:g}倍，移动可躲，普攻间隔从释放起算"
    if p.get('stride_steps'):return f"普通自主移动最多{p['stride_steps']}格，与护盾疾行取最大；逐格阻挡/封边/浅水仍生效，移动后下一拍不能开始普攻，技能不受此限制"
    if p.get('shield_relay_range'):return f"受击缺口可用{p['shield_relay_range']}格内可见友军已有私盾抵扣；每供盾者每拍一次，转出多少消耗多少，供盾者下一拍承伤+10%"
    return None


def validate_actor(actor,tick,board=None):
    for key in ('fortune_basic_block_until','fortune_relay_tick'):
        if key in actor and (type(actor[key]) is not int or actor[key]<0 or actor[key]>tick+int(key=='fortune_basic_block_until')):raise ValueError('机制约定行动时点无效。')
    if actor.get('fortune_basic_block_until') and not values(actor).get('stride_steps'):
        raise ValueError('无长步来源却保留普攻约束。')
    row=actor.get('fortune_relay_exposure')
    if row and (type(row.get('starts')) is not int or row.get('expires')!=row['starts']
                or row.get('amount')!=.1 or row['starts']>tick+1 or not isinstance(row.get('condition_ids'),list)
                or not row['condition_ids'] or not set(row['condition_ids'])<=set(values(actor).get('condition_ids',[]))):
        raise ValueError('接盾暴露记录无效。')
    action=actor.get('pending')
    if action and action.get('fortune_mode'):
        import combat as c
        center=action.get('fortune_center',[])
        expected=([list(center)]+[[center[0]+dq,center[1]+dr] for dq,dr in c.DIRS]) if len(center)==2 else []
        if board is not None:expected=[p for p in expected if tuple(p) in board]
        start=action.get('fortune_started_tick')
        # B02 is consumed at accepted start. Its frozen action, rather than the
        # now-removed live buff, owns the one-point range bonus until release.
        range_bonus=0
        if 'book_range_bonus' in action:
            if (type(action['book_range_bonus']) is not int or action['book_range_bonus']!=1
                    or 'SB-B02' not in actor.get('books_equipped',[])
                    or action.get('damage_type')!='physical' or action.get('medium')!='projectile'
                    or action.get('book_attack_prepared') is not True
                    or action.get('book_ignore_defense')!=.25):
                raise ValueError('迸散普攻的瞄准增程来源不符。')
            range_bonus=1
        effective_range=actor['range']+range_bonus
        if (action.get('fortune_mode')!='burst' or action.get('move_id')!='BASIC'
                or not values(actor).get('ranged_burst_radius')
                or action.get('fortune_splash')!=values(actor).get('ranged_splash_coefficient')
                or action.get('fortune_sources')!=sources(actor,'ranged_burst_radius')
                or not isinstance(action.get('fortune_center'),list) or len(action['fortune_center'])!=2
                or any(type(n) is not int for n in action['fortune_center'])
                or type(start) is not int or not 1<=start<=tick or action.get('due')!=start+1
                or action.get('range')!=effective_range or action.get('cells')!=expected
                or c.distance(action['origin'],center)>effective_range or action.get('windup')!=1):
            raise ValueError('迸散普攻与约定冻结来源不符。')
