"""Snapshot intents, bounded skills, movement, then simultaneous settlement."""
from copy import deepcopy
import hashlib
import heapq
import json
import math
import combat as c
import battle_skills as skills
import commander
import gear_affixes as gear
import fantasy_enemies as fantasy
import necromancy
import reinforcements
import enemy_support as support
import spatial_moves as spatial
import sweeps
import veil
import action_timing as timing
import protection
import battle_plans as plans
import skill_books as books
import book_combat as sb
import heroes
import bosses
import finale_battle
import roster_skills as roster
import hero_refinements
import event_conditions
import fortune_mechanics as fortune
import boss_mimic as mimic
import boss_threats as threats
import expedition_peril as peril

ROSTER_MOVES={c['move_id'] for c in roster.MERC_CARDS.values()}


def ray(origin, end):
    n = c.distance(origin, end)
    return [c.rounded_cube(origin[0]+(end[0]-origin[0])*i/n,
                           origin[1]+(end[1]-origin[1])*i/n) for i in range(1, n+1)] if n else []


def line(origin, facing, length):
    dq, dr = c.DIRS[facing]
    return [(origin[0]+dq*i, origin[1]+dr*i) for i in range(1, length+1)]


def roll(seed, action, target, kind):
    data = json.dumps([seed, action, target, kind], ensure_ascii=False, separators=(',', ':')).encode('utf8')
    return int.from_bytes(hashlib.sha256(data).digest()[:8], 'big') / 2**64


def front(victim, origin):
    path = [tuple(origin)] + ray(origin, victim['pos'])
    incoming = path[-2] if len(path) > 1 else origin
    return c.direction(victim['pos'], incoming) in {(victim['facing']+d)%6 for d in (-1, 0, 1)}


def weak_active(actor, tick):
    condition = actor.get('weak_point', {}).get('active_condition', '')
    if condition == 'while_EN01_A_rooted': return tick <= actor['root_until']
    if condition == 'while_EN04_A_windup':
        return bool(actor['pending'] and actor['pending']['move_id'] == 'EN04-A')
    if condition == 'while_EN06_A_windup':
        return bool(actor['pending'] and actor['pending']['move_id'] in skills.ECHO_IDS)
    return condition.startswith('one_tick_after_') and actor['weak_from'] <= tick <= actor['weak_until']


def spend_shields(victim, shared, amount, tick=None):
    """Private and shared timed shields share one expiry/creation ordering."""
    pools = [p for p in shared if victim['id'] in p['members']] + victim['timed_shields']
    if tick is not None:pools=[p for p in pools if p.get('starts',1)<=tick<=p['expires']]
    for pool in sorted(pools, key=lambda p: (p['expires'], p.get('created', 0), p.get('id', p.get('effect', '')), p.get('source', ''))):
        used = min(pool['amount'], amount); pool['amount'] -= used; amount -= used
    used = min(victim['shield'], amount); victim['shield'] -= used
    return amount-used


def fragile_ranged(actor):
    """Thin ranged humans value survival over closing for a short book."""
    return (actor.get('side')=='player' and not str(actor.get('kind','')).startswith('PET')
            and actor.get('range',1)>1 and actor.get('stats',{}).get('hp',999)<=50)


def avoid_telegraphed_cells(actor,danger):
    """Return a movement shadow that refuses telegraphed damage cells."""
    if actor['stance']=='evade' or fragile_ranged(actor):
        return {**actor,'book_avoid_cells':set(actor.get('book_avoid_cells',()))|danger[actor['side']]}
    return actor


def consume_next_attack_null(actor,tick,log,action=None):
    """Consume the hidden counter: the actor's next damage action is void."""
    row=actor.get('next_attack_null')
    if not row or not row['starts']<=tick<=row['expires']:return False
    actor.pop('next_attack_null',None)
    details={'source':row.get('source'),'expires':row['expires']}
    if action is not None:
        details.update(move=action.get('move_id'),action_id=action.get('id'))
    log('next_attack_nullified',actor=actor['id'],**details)
    return True


def next_cell(catalog, board, actor, foes, occupied, blocked_edges=(), tick=None):
    """Weighted shortest path; hold remains within one cell of deployment anchor."""
    origin = tuple(actor['pos']); queue = [(0, origin, origin)]; best = {origin: 0}; candidates = []
    minimum = None
    while queue:
        cost, pos, first = heapq.heappop(queue)
        if cost != best[pos] or (minimum is not None and cost > minimum): continue
        legal = [b for b in foes if c.distance(pos, b['pos']) <= actor['range'] and c.visible(catalog, board, pos, b['pos']) and (tick is None or veil.targetable(actor,b,tick,pos))]
        if actor.get('book_support_avoid') and any(c.distance(pos,p)<=1 for p in actor['book_support_avoid']):
            legal=[]
        if pos != origin and legal:
            minimum = cost
            flank = any(not front(b, pos) for b in legal)
            candidates.append((0 if actor['stance'] == 'flank' and flank else 1, first, pos)); continue
        for dq, dr in c.DIRS:
            nxt = (pos[0]+dq, pos[1]+dr)
            if nxt in actor.get('book_avoid_cells',()):continue
            if spatial.crossed(pos,nxt,blocked_edges):continue
            if actor.get('boss_part_offsets'):
                if not bosses.can_move(actor,pos,nxt,occupied,catalog,board,blocked_edges):continue
            elif nxt in occupied or nxt not in board or not catalog.terrain[board[nxt]]['walkable']: continue
            if actor['stance'] == 'hold' and c.distance(nxt, actor['anchor']) > 1: continue
            new_cost = cost + (2 if board[nxt] == 'SHALLOW_WATER' else 1)
            if new_cost < best.get(nxt, math.inf):
                best[nxt] = new_cost; heapq.heappush(queue, (new_cost, nxt, nxt if pos == origin else first))
    return min(candidates)[1] if candidates else None


def step(catalog, battle):
    if battle['result'] or bosses.paused(battle): return
    battle['tick'] += 1; tick = battle['tick']; board = c.cells(catalog, battle)
    alive = sorted([a for a in battle['actors'] if a['hp'] > 0], key=lambda a: a['id'])
    ids = {a['id']: a for a in alive}; occupied = {tuple(a['pos']) for a in alive}
    prior_pending = {a['id']: deepcopy(a['pending']) for a in alive}
    echo_weak = {a['id']: weak_active(a, tick) for a in alive if a['kind'] in ('EN06', 'EL03')}
    moves = []; actions = []; heals = []; facing_updates = {}; released = []; movement_blocks = []; pushes=[]
    initial = json.dumps([(a['id'], a['hp'], a['shield'], a['pos']) for a in alive])
    import learning
    import adaptation_geometry
    def log(kind, **kw):
        event={'tick': tick, 'type': kind, 'event_id':f"{battle['battle_id']}:event:{len(battle['events'])+1}", **kw}
        battle['events'].append(event)
        learning.observe(catalog,battle,event)
    import battle_enrage
    battle_enrage.start_tick(battle,tick,log)
    learning.tick_start(catalog,battle)
    def legal(a, b, distance=None, penetration=0):
        return c.distance(a['pos'], b['pos']) <= (a['range'] if distance is None else distance) and c.visible(catalog, board, a['pos'], b['pos'], penetration)
    def action_id(a):
        a['action_sequence'] += 1
        return f"{a['id']}:{a['action_sequence']}"
    def begin(a, card, victim=None, locked=(), **extra):
        deferred=timing.before_begin(a,card,tick,log,lambda source: protection.delayed(a,next((b for b in battle['actors'] if b['id']==source),None),tick,log))
        aid = action_id(a); mid = card['move_id']
        a['move_uses'][mid] = a['move_uses'].get(mid, 0) + 1
        a['pending'] = {**deepcopy(card), 'id': aid, 'due': tick+card['windup'],
                        'target': victim['id'] if victim else a['id'],
                        'cells': [list(p) for p in locked], 'origin': a['pos'][:],
                        'facing': c.direction(a['pos'], victim['pos']) if victim else a['facing'], **extra}
        if mid in heroes.DATA or mid in ('CMD-A','CMD-B'):
            a['move_ready'][mid]=tick+card['cooldown']
        heroes.started(battle,a,a['pending'],tick,log)
        if deferred:
            a['pending'].update(start_delay=deferred,delayed=True)
            log('delayed_start_committed',actor=a['id'],move=mid,action_id=aid)
        if mimic.is_copy(a['pending']):mimic.started(battle,a,a['pending'],tick,log)
        else:bosses.started(a,card)
        threats.started(battle,a,a['pending'],tick,log)
        peril.started(battle,a,a['pending'],tick,log)
        books.begin(battle,a,a['pending'],tick,log)
        plans.begin(battle,a,a['pending'],tick,log)
        facing_updates[a['id']] = a['pending']['facing']
        a['stationary'] = 0
        if mid in support.HEAT:support.start(a,card,tick,log)
        log('windup', actor=a['id'], move=mid, action_id=aid, target=a['pending']['target'],
            cells=a['pending']['cells'], release_tick=a['pending']['due'], **extra)
        if a['pending']['due']<=tick:
            actions.append((a,deepcopy(a['pending'])));released.append(a)

    plans.start_tick(battle,tick)
    threats.start_tick(battle,tick,log)
    heroes.start_tick(battle,tick,log)
    heals.extend(sb.start_tick(battle,catalog,board,tick,log))
    spatial.start_tick(battle,catalog,board,tick,log)
    blocked_edges=spatial.active_edges(battle,tick)
    finale_intents=finale_battle.intents(catalog,battle,alive,board,blocked_edges,tick,log)
    veil.start_tick(alive,catalog,board,tick,log)
    delay_eligible=timing.start_tick(alive,catalog,board,tick,log)
    commander.start_tick(battle,alive,tick,log)
    prior_mark=deepcopy(battle.get('command_mark'))

    # Passive footing reads the previous complete tick, not this tick's future move.
    for a in alive:
        a['timed_shields'][:] = [p for p in a['timed_shields'] if p['expires'] >= tick and p['amount'] > 0]
        if a['kind'] == 'M01' and not a['footing_used'] and tick > 1 and a['last_moved_tick'] < tick-1:
            neighbors = sorted([b for b in alive if b['side']==a['side'] and b!=a and c.distance(a['pos'],b['pos'])==1], key=lambda b:b['id'])
            for recipient in [a]+neighbors[:1]:
                if not any(p['effect']=='M01-P' for p in recipient['timed_shields']):
                    recipient['timed_shields'].append({'effect':'M01-P','source':a['id'],'amount':6,'expires':tick+1,'created':tick})
                    log('private_shield', actor=a['id'], target=recipient['id'], amount=6, expires=tick+1)
            a['footing_used'] = True

    # Only prior-tick telegraphs are visible to evade. Same-tick starts cannot be anticipated.
    danger = {side: {tuple(p) for a in alive if a['side'] != side and a['pending']
                     and (a['pending']['due'] == tick or a['pending'].get('pressure_radius') and a['pending']['due']<=tick+a['pending'].get('threat_evasion_horizon',1))
                     and a['pending']['kind'] == 'damage'
                     for p in a['pending']['cells']} for side in ('player', 'enemy')}
    def next_movement_cell(catalog, board, actor, foes, occupied, blocked_edges=(), tick=None):
        # Use the same prior-warning window as evasion; a safe actor must not
        # approach through it again. Copies also cover PL12/fortune extensions.
        # Thin ranged humans also refuse to walk into a telegraphed area attack
        # merely to bring a short-range book into reach.
        actor = avoid_telegraphed_cells(actor, danger)
        return next_cell(catalog, board, actor, foes, occupied, blocked_edges, tick)
    def intent_order(actor):
        rescue_book=any(card['move_id']=='SK-SB-M04' and card['move_id'] not in actor.get('disabled_skills',[])
                        and actor['move_ready'].get(card['move_id'],0)<=tick for card in actor.get('moves',[]))
        return (not rescue_book,actor['kind']!='H08')
    for a in sorted(alive,key=intent_order):
        if a['id'] in sb.held(battle,actions,tick):continue
        if a.get('mechanism') or a.get('boss_part') or tick<a.get('active_from',1) or a['id'] in heroes.pet_locks(battle):continue
        stun=a.get('hero_stun')
        if stun and stun['starts']<=tick<=stun['expires']:
            if threats.control_immune(a):
                log('admin_super_armor_immune',actor=a['id'],effect='stun')
                a.pop('hero_stun',None)
            else:
                if a.get('pending'):
                    log('hero_stun_cancel',actor=a['id'],cast_id=a['pending']['id'])
                    if a['kind']=='ADMIN': threats.admin_interrupted(battle,a,tick,log)
                a['pending']=None;a.pop('hero_chain_due',None);a['hero_shadow']=False
                if a['kind']=='DEMON':a['mimic_chain']=None;a['mimic_shadow']=False
                continue
        a['stationary'] += 1
        all_foes=commander.preferred(a,[b for b in alive if b['side']!=a['side']],prior_mark)
        if not all_foes and not battle.get('finale'):continue
        # While an administrator law is active, its owner is the first target
        # for player targeting; guards and minions remain legal fallbacks.
        boss_focus=threats.priority_boss(battle,a)
        if boss_focus:all_foes=sorted(all_foes,key=lambda b:(b['id']!=boss_focus,b['id']))
        foes=[b for b in all_foes if veil.targetable(a,b,tick) and heroes.targetable(a,b,tick) and mimic.targetable(a,b,tick)]
        if boss_focus:
            focus=[b for b in foes if b['id']==boss_focus]
            if focus:foes=focus
        approach=foes or all_foes
        if a.get('mimic_chain') and not battle.get('retreat_requested'):
            action=mimic.chain_action(battle,a,alive,catalog,board,tick,log)
            if action:
                action['id']=action_id(a)
                a['move_uses'][action['move_id']]=a['move_uses'].get(action['move_id'],0)+1
                actions.append((a,action));released.append(a)
                log('mimic_chain_start',actor=a['id'],move=action['move_id'],action_id=action['id'])
                continue
        if a.get('hero_chain_due') is not None and a['hero_chain_due']<=tick and not battle.get('retreat_requested'):
            action=heroes.chain_action(battle,a,alive,catalog,board,tick,log)
            if action:
                action['id']=action_id(a)
                a['move_uses']['H11-A']=a['move_uses'].get('H11-A',0)+1
                actions.append((a,action));released.append(a)
                log('hero_chain_start',actor=a['id'],move='H11-A',action_id=action['id'])
                continue
            a['hero_shadow']=False
        if a['pending']:
            if a['pending']['due'] <= tick:
                actions.append((a, deepcopy(a['pending']))); released.append(a)
            continue
        if a['id'] in finale_intents:
            intent=finale_intents[a['id']]
            if intent['kind']=='move':moves.append((a,tuple(intent['cell']),'interface_move'))
            else:actions.append((a,{'id':action_id(a),'move_id':'INTERFACE','kind':'interface','cells':[]}))
            continue
        if not all_foes:continue
        if battle.get('retreat_requested') and a['side'] == 'player': continue
        if (a['stance'] == 'evade' or fragile_ranged(a)) and tuple(a['pos']) in danger[a['side']] and tick > max(a['move_pause_until'], a['root_until'], a['blocked_until']):
            safe = [(a['pos'][0]+dq, a['pos'][1]+dr) for dq, dr in c.DIRS]
            safe = [p for p in safe if p in board and catalog.terrain[board[p]]['walkable'] and p not in occupied and p not in danger[a['side']] and not spatial.crossed(a['pos'],p,blocked_edges)]
            if safe:
                moves.append((a, min(safe, key=lambda p: (min(c.distance(p, b['pos']) for b in approach), p)), 'evade'))
                continue
            from late_pressure import early_escape
            step=early_escape(a,alive,danger[a['side']],catalog,board,occupied,blocked_edges,tick)
            if step:
                moves.append((a,step,'evade'));continue
        try:
            started = False
            cards=mimic.prioritize(battle,a,bosses.cards(a),tick)
            cards=threats.prioritize(battle,a,cards,tick)
            cards=peril.prioritize(battle,a,cards,tick)
            for original_card in cards:
                card=sb.prepare_card(a,original_card,tick)
                mid = card['move_id']
                if a.get('skill_mode') == 'off' or mid in a.get('disabled_skills',[]): continue
                if a['kind'] in commander.KINDS and mid.startswith('CMD-'):
                    if not commander.enabled(a):continue
                    if a.get('skill_mode') in ('mark','volley') and mid!=('CMD-A' if a['skill_mode']=='mark' else 'CMD-B'):continue
                if mid not in c.SUPPORTED_MOVES or not c.has_uses(a,card) or tick < max(card['first_eligible_tick'], plans.heal_ready(battle,a,card,a['move_ready'].get(mid, 0))): continue
                if mid in heroes.DATA and not heroes.enabled(a):continue
                adapted,aim=adaptation_geometry.aim(a,card,catalog,board)
                if adapted:
                    if aim:
                        victim,locked,extra=aim;begin(a,card,victim,locked,**extra);started=True
                elif mid in threats.MOVES:
                    chosen=threats.choose(battle,a,card,foes,catalog,board,tick)
                    if chosen:
                        victim,locked,extra=chosen;begin(a,card,victim,locked,**extra);started=True
                elif mid in peril.MOVES:
                    chosen=peril.choose(battle,a,card,foes,catalog,board,tick)
                    if chosen:
                        victim,locked,extra=chosen;begin(a,card,victim,locked,**extra);started=True
                elif mid==mimic.GATE:
                    chosen=mimic.choose(battle,a,foes,alive,prior_pending,catalog,board,occupied,blocked_edges,tick)
                    if chosen:
                        copy_card,victim,locked,extra=chosen;begin(a,copy_card,victim,locked,**extra);started=True
                elif mid in bosses.MOVES:
                    chosen=bosses.choose(battle,a,card,foes,catalog,board)
                    if chosen:
                        victim,locked,extra=chosen;begin(a,card,victim,locked,**extra);started=True
                elif mid in ROSTER_MOVES:
                    chosen=roster.choose(battle,a,card,all_foes,alive,prior_pending,catalog,board,occupied,blocked_edges,tick)
                    if chosen:
                        victim,locked,extra=chosen;begin(a,card,victim,locked,**extra);started=True
                elif mid in heroes.DATA:
                    chosen=heroes.choose(battle,a,card,all_foes,alive,prior_pending,catalog,board,occupied,blocked_edges,tick)
                    if chosen:
                        victim,locked,extra=chosen;begin(a,card,victim,locked,**extra);started=True
                elif mid.startswith('SK-SB-'):
                    chosen=books.choose(battle,a,card,foes,alive,prior_pending,catalog,board,occupied,blocked_edges,tick,next_cell)
                    if chosen:
                        victim,locked,extra=chosen;begin(a,card,victim,locked,**extra);started=True
                elif mid==timing.DELAY:
                    victim=timing.choose_delay(a,card,foes,battle,catalog,board,delay_eligible)
                    if victim:begin(a,card,victim);started=True
                elif mid==timing.ROOT:
                    chosen=timing.root_choice(a,card,foes,catalog,board)
                    if chosen:
                        victim,locked,facing,base=chosen
                        begin(a,card,victim,locked,facing=facing,axis_base=base,axis_offset=card['axis_offset_sequence'][a['move_uses'].get(mid,0)])
                        a['root_axis_base']=base;started=True
                elif mid==veil.CONCEAL:
                    targets=veil.conceal_targets(a,card,alive,catalog,board)
                    begin(a,card,locked=[b['pos'] for b in targets],targets=[b['id'] for b in targets]);started=True
                elif mid in veil.DEFLECT:
                    chosen=veil.deflect_choice(a,card,alive,catalog,board)
                    if chosen:
                        dest,facing=chosen;begin(a,card,destination=list(dest),deflect_facing=facing);started=True
                elif mid==sweeps.STEP:
                    if a['initial_side_step']:continue
                    chosen=sweeps.sidestep_choice(a,foes,catalog,board,occupied,blocked_edges,tick)
                    if chosen:
                        victim,dest=chosen;begin(a,card,victim,[dest]);started=True
                    else:
                        a['initial_side_step']={'status':'skipped','tick':tick}
                        log('side_step_skipped',actor=a['id'],reason='no_legal_step')
                elif mid in sweeps.SWEEPS:
                    chosen=sweeps.sweep_choice(a,card,foes,catalog,board,tick)
                    if chosen:
                        victim,locked,facing=chosen
                        extra={'facing':facing}
                        if mid=='EN07-A':extra['push_destinations']=sweeps.push_preview(a,locked,catalog,board,occupied,blocked_edges)
                        begin(a,card,victim,locked,**extra);started=True
                elif mid in spatial.AREAS:
                    chosen=spatial.area_choice(a,card,foes,catalog,board)
                    if chosen:
                        victim,locked=chosen;begin(a,card,victim,locked);started=True
                elif mid==spatial.EDGE:
                    chosen=spatial.edge_choice(a,card,foes,battle,catalog,board)
                    if chosen:
                        victim,edge=chosen;begin(a,card,victim,edge=[list(p) for p in edge]);spatial.reserve(battle,a);started=True
                elif mid==reinforcements.MOVE:
                    position=reinforcements.choose(a,card,battle,catalog,board)
                    if position is not None:begin(a,card,locked=[position]);started=True
                elif mid in necromancy.MOVES:
                    chosen=necromancy.choose(a,card,battle,catalog,board)
                    if chosen is not None:
                        victim,locked=chosen
                        begin(a,card,victim,locked);started=True
                elif mid in fantasy.MOVES:
                    chosen = fantasy.start_target(a, card, foes, alive, catalog, board)
                    if chosen is not None:
                        victim, locked = chosen
                        begin(a, card, victim, locked); started = True
                elif mid=='CMD-A':
                    targets=[b for b in foes if legal(a,b,4)]
                    if targets and commander.soldiers(a,alive):
                        begin(a,card,targets[0]);started=True
                elif mid=='CMD-B':
                    members=commander.volley_candidates(a,alive,prior_mark,catalog,board,tick)
                    if members:begin(a,card,members=members);started=True
                elif mid in skills.ECHO_IDS:
                    locked = skills.echo_cells(a, card, catalog, board)
                    if locked: begin(a, card, locked=locked); started=True
                elif mid == 'EN12-A':
                    if tick <= max(a['move_pause_until'],a['root_until'],a['blocked_until']): continue
                    paths=skills.flank_paths(a,foes,catalog,board,occupied,blocked_edges)
                    if paths:
                        begin(a,card,locked=paths[0],paths=[[list(pos) for pos in path] for path in paths]);started=True
                elif mid==support.HEAL:
                    targets=support.heal_targets(a,card,alive,catalog,board,tick)
                    if targets:
                        begin(a,card,targets[0],locked=[b['pos'] for b in targets],targets=[b['id'] for b in targets]);started=True
                elif card['kind'] == 'heal':
                    injured=[b for b in alive if not b.get('mechanism') and not b.get('boss_part') and b['side']==a['side'] and b['hp']<=.6*b['stats']['hp'] and legal(a,b,card['range'])]
                    if injured:
                        victim=min(injured,key=lambda b:(b['hp']/b['stats']['hp'],b['id']))
                        begin(a,card,victim,locked=[victim['pos']]);started=True
                elif mid == 'M04-A':
                    candidates=[b for b in foes if legal(a,b,card['range'])]
                    if a.get('skill_mode','counter') == 'counter':
                        candidates=[b for b in candidates if prior_pending[b['id']] and prior_pending[b['id']].get('delayable_cast')
                                    and not prior_pending[b['id']].get('delayed') and prior_pending[b['id']]['due']>tick+card['windup']]
                        candidates.sort(key=lambda b:(prior_pending[b['id']]['due'],c.distance(a['pos'],b['pos']),b['id']))
                    if candidates:
                        victim=candidates[0];cast=prior_pending[victim['id']]
                        begin(a,card,victim,[victim['pos']],target_cast=cast['id'] if cast else None);started=True
                elif mid in ('M01-A','M03-A'):
                    for victim in foes:
                        if not skills.axis(a['pos'],victim['pos']) or not legal(a,victim,card['range'],int(mid=='M03-A')):continue
                        length=card['range'] if mid=='M01-A' else c.distance(a['pos'],victim['pos'])
                        begin(a,card,victim,line(a['pos'],c.direction(a['pos'],victim['pos']),length));started=True;break
                else:
                    if card['kind'] == 'shield':
                        begin(a, card); started = True
                    else:
                        for victim in foes:
                            if not legal(a, victim, card['range']): continue
                            facing = c.direction(a['pos'], victim['pos'])
                            locked = line(a['pos'], facing, card['range']) if card['shape'].startswith('front_') else [tuple(victim['pos'])]
                            if tuple(victim['pos']) not in locked: continue
                            begin(a, card, victim, locked); started = True; break
                if started: break
            if started: continue
            if a['kind'] in ('S02', 'S03') and not a['skill_used']:
                for victim in foes:
                    if not legal(a, victim, 4 if a['kind'] == 'S03' else 1, int(a['kind'] == 'S03')): continue
                    if a['kind'] == 'S02' and not any(b != a and b['side'] == a['side'] and b['medium'] == 'near' and legal(b, victim) for b in alive): continue
                    card = {'move_id': a['kind']+'-A', 'kind': 'damage', 'windup': 1, 'cooldown': 0,
                            'coefficient': 1.5 if a['kind'] == 'S02' else 1.25, 'damage_type': 'physical',
                            'range': 4 if a['kind'] == 'S03' else 1, 'medium': a['medium'], 'max_targets': 1}
                    locked = ray(a['pos'], victim['pos']) if a['kind'] == 'S03' else [tuple(victim['pos'])]
                    begin(a, card, victim, locked); a['skill_used'] = 1; started = True; break
            if started: continue
        except timing.DeferredStart:
            pass  # The ordinary attack/move below still runs. No active was started.
        support_intent=sb.support_intent(a,alive,catalog,board,tick)
        if support_intent and not a.get('hero_setup') and tick>max(a['move_pause_until'],a['root_until'],a['blocked_until']):
            recipient,support_range=support_intent
            supporter={**a,'range':support_range,'book_avoid_cells':danger[a['side']],
                       'book_support_avoid':[tuple(v['pos']) for v in foes] if a.get('basic_medium',a['medium'])!='near' else []}
            step=next_movement_cell(catalog,board,supporter,[recipient],occupied,blocked_edges,tick)
            if step:moves.append((a,step,'move'));continue
        # A short book can be the deliberate attack plan even when a longer
        # basic is already in reach. Native global/dynamic aim stays above.
        attack_intent=sb.attack_intent(a,foes,catalog,board,tick)
        intent_range=attack_intent['range'] if attack_intent else a['range']
        if attack_intent and attack_intent.get('target_mode')=='ground':
            intent_range+=attack_intent.get('radius',0)
        intent_targets=[v for v in foes if legal(a,v,intent_range,attack_intent.get('penetration',0) if attack_intent else 0)]
        closing=bool(attack_intent and attack_intent.get('book_id') and not intent_targets
                     and not a.get('hero_setup')
                     and tick>max(a['move_pause_until'],a['root_until'],a['blocked_until']))
        if closing:
            mover={**a,'range':intent_range}
            step=next_movement_cell(catalog,board,mover,approach,occupied,blocked_edges,tick)
            if step:moves.append((a,step,'move'));continue
        basic_card=sb.prepare_card(a,{'move_id':'BASIC','kind':'damage','damage_type':a['attack_type'],
                                    'range':a['range'],'medium':a['medium']},tick)
        in_range = [b for b in foes if legal(a, b,basic_card['range']) and not (a['kind'] == 'S01' and a['stance'] == 'hold' and not front(a, b['pos']))]
        if in_range and tick >= a['next_attack'] and fortune.basic_allowed(a,tick):
            victim = in_range[0]
            action={'id': action_id(a), 'move_id': 'BASIC', 'kind': 'damage',
                               'target': victim['id'], 'cells': [], 'coefficient': 1, 'damage_type': a['attack_type'],
                               'range': basic_card['range'], 'medium': a['medium'], 'max_targets': 1, 'origin': a['pos'][:]}
            if basic_card.get('book_range_bonus'):action['book_range_bonus']=basic_card['book_range_bonus']
            sb.attack_attempt(battle,a,action,tick,log)
            plans.basic_start(battle,a,victim,action,tick,front,log)
            action['roster_stance']=roster.attack_bonus(a,victim,action,tick)
            windup=fortune.prepare_basic(a,victim,action,catalog,board,tick,log)
            log('basic_start',actor=a['id'],target=victim['id'],action_id=action['id'])
            if windup:a['pending']=deepcopy(action)
            else:actions.append((a,action))
            a['next_attack'] = tick+windup+a['interval']+fortune.interval_penalty(a,action); continue
        if in_range or tick <= max(a['move_pause_until'], a['root_until'], a['blocked_until']): continue
        focus=next((b for b in foes if prior_mark and b['id']==prior_mark['target'] and a['id'] in prior_mark['members']),None)
        dest = next_movement_cell(catalog,board,a,[focus],occupied,blocked_edges,tick) if focus and a['stance'] in ('advance','flank') else None
        if not dest and a['kind']=='EN19': dest = next_movement_cell(catalog,board,a,approach[:1],occupied,blocked_edges,tick)
        book_holds_setup=bool(a.get('hero_setup') and attack_intent and intent_targets)
        if not dest and (not a.get('hero_setup') or not book_holds_setup and heroes.should_advance(a,foes,catalog,board,tick)):
            dest = next_movement_cell(catalog, board, {**a,'range':intent_range}, approach, occupied,blocked_edges,tick)
        if dest: moves.append((a, dest, 'move'))

    held=heroes.pet_locks(battle)|set(sb.held(battle,actions,tick))
    moves=[row for row in moves if row[0]['id'] not in held]
    actions=[row for row in actions if row[0]['id'] not in held]
    moves.extend(heroes.movement(actions,battle,alive,catalog,board,tick,log))
    moves.extend(mimic.movement(actions,battle,alive,catalog,board,tick,log))
    moves.extend(sb.movement(actions,battle,alive,catalog,board,tick,log))
    moves.extend(roster.movement(actions,battle,alive,catalog,board,tick,log))
    for a,action in actions:
        if action['move_id']=='SK-BK03':moves.append((a,action['cells'],'book_dash'))
        if action['move_id']=='EN12-A':moves.append((a,action['cells'],'short_dash'))
        if action['move_id']==sweeps.STEP:moves.append((a,action['cells'][0],'side_step'))
    claimed = set()
    for a, dest, reason in sorted(moves, key=lambda x: x[0]['id']):
        old_position=tuple(a['pos'])
        original_reason=reason
        avoided=[p['id'] for other,p in prior_pending.items() if p and ids[other]['side']!=a['side'] and p['due']==tick and p['kind']=='damage' and old_position in [tuple(q) for q in p.get('cells',[])]] if reason=='evade' else []
        if reason!='interface_move':dest,reason=plans.extend_move(battle,a,dest,reason,[b for b in alive if b['side']!=a['side']],catalog,board,occupied,blocked_edges,tick,next_movement_cell,log,danger[a['side']])
        fortune_path=fortune.extend_move(a,dest,reason,original_reason,[b for b in alive if b['side']!=a['side']],catalog,board,occupied,blocked_edges,tick,next_movement_cell,danger[a['side']])
        is_path=bool(dest and isinstance(dest[0],(tuple,list)))
        path = fortune_path if fortune_path is not None else [tuple(p) for p in dest] if is_path else [tuple(dest)]
        end=None;previous=tuple(a['pos']);actual_path=[]
        if reason in ('short_dash','book_dash','side_step','hero_move','hero_path','hero_pull') and tick<=max(a['move_pause_until'],a['root_until'],a['blocked_until']):path=[]
        for pos in path:
            # Wide-warning escape may need dangerous intermediate cells. Once
            # safe, autonomous evade movement cannot cross back into danger.
            if a['stance']=='evade' and original_reason in ('move','evade') and previous not in danger[a['side']] and pos in danger[a['side']]:break
            if c.distance(previous,pos)!=1 or spatial.crossed(previous,pos,blocked_edges):break
            if a.get('boss_part_offsets'):
                if bosses.footprint(a,pos)&claimed or not bosses.can_move(a,previous,pos,occupied,catalog,board,blocked_edges):break
                claimed.update(bosses.footprint(a,pos))
            elif pos in claimed or pos in occupied or pos not in board or not catalog.terrain[board[pos]]['walkable']:break
            claimed.add(pos);end=pos;previous=pos;actual_path.append(pos)
            if board[pos]=='SHALLOW_WATER':break
        if end is None:log('move_blocked',actor=a['id'],reason='blocked_or_reserved',move='EN12-A' if reason=='short_dash' else sweeps.STEP if reason=='side_step' else reason);continue
        facing_updates[a['id']] = c.direction(a['pos'], end)
        a['pos'] = list(end); a['stationary'] = 0;a['last_moved_tick']=tick
        bosses.moved(battle,a)
        c.enter_shallow(a,board[end],tick,log)
        log(reason, actor=a['id'], position=list(end),action_id=a['pending']['id'] if a['pending'] else f"{a['id']}:move:{tick}",
            danger_ids=avoided if tuple(end) not in danger[a['side']] else [])
        gear.moved(a,tick,log)
        heroes.moved(a,reason,tick)
        mimic.moved(a,reason,tick)
        roster.moved(a,reason)
        plans.moved(battle,a,reason,tick,log)
        sb.moved(battle,a,reason,tick,log)
        fortune.moved(a,actual_path,original_reason,tick,log)

    # Extra attacks join the same damage batch. New orders cannot be used this tick.
    commander.extra_actions(battle,alive,actions,moves,prior_mark,tick,catalog,board,action_id,log)
    mimic.extra_actions(battle,alive,actions,moves,tick,catalog,board,action_id,log)
    for a,action in actions:
        sb.attack_attempt(battle,a,action,tick,log)
        plans.attack_attempt(battle,a,action,tick,log)
        heroes.attack_attempt(battle,a,action,tick,log)

    veil.reveal_attacks(alive,actions,tick,log)

    # Existing links can break but never attach to a new recipient or refill.
    pools = battle['shared_shields']
    for pool in pools:
        owner = ids.get(pool['owner'])
        pool['members'] = [mid for mid in pool['members'] if mid in ids and owner and c.distance(ids[mid]['pos'], owner['pos']) <= 1]
    pools[:] = [p for p in pools if p['expires'] >= tick and p['members'] and p['amount'] > 0]
    for a, action in actions:
        if action['kind'] != 'shield': continue
        if action['move_id'] in bosses.MOVES:
            bosses.shield(a,action,tick,log);continue
        if action['move_id'] in support.HEAT:
            support.release(a,action,tick,log);continue
        if action['move_id']=='EN21-A':
            a['timed_shields'].append({'effect':'EN21-A','source':a['id'],'amount':action['shield'],
                                       'expires':tick+action['duration_ticks']-1,'created':tick})
            log('private_shield',actor=a['id'],target=a['id'],amount=action['shield'],expires=tick+action['duration_ticks']-1)
            continue
        neighbors = sorted([b for b in alive if not b.get('mechanism') and not b.get('boss_part') and b['side'] == a['side'] and b != a and c.distance(a['pos'], b['pos']) == 1], key=lambda b: (b['hp']/b['stats']['hp'], b['id']))
        if a.get('adaptation_rule',{}):
            neighbors.sort(key=lambda b:b['id']!=a['adaptation_rule'].get('ally'))
        members = [a['id']]+[b['id'] for b in neighbors[:action['max_targets']-1]]
        pools[:] = [p for p in pools if p['owner'] != a['id']]
        pools.append({'id': action['id'], 'owner': a['id'], 'members': members, 'amount': action['shield'], 'expires': tick+action['duration_ticks']-1, 'created':tick})
        log('shared_shield', actor=a['id'], members=members, amount=action['shield'], expires=tick+action['duration_ticks']-1)

    hits = []
    for a, action in actions:
        mid = action['move_id']
        if mid=='INTERFACE':continue
        if mid=='BASIC' and action.get('fortune_mode')=='burst':
            a['next_attack']=max(a['next_attack'],tick+a['interval'])
            log('fortune_burst_release',actor=a['id'],action_id=action['id'],condition_ids=action.get('fortune_sources',[]),center=action['fortune_center'],cells=action['cells'])
        if mid not in ('BASIC','CMD-EXTRA','MIMIC-CMD-EXTRA'):
            if mid not in heroes.DATA and mid not in ('CMD-A','CMD-B'):
                a['move_ready'][mid] = tick+action['cooldown']
            a['completed_moves'][mid]=tick
            if mid==sweeps.STEP:a['initial_side_step']={'status':'finished','tick':tick,'moved':a['last_moved_tick']==tick}
            if mid in support.HEAT:a['next_attack']=max(a['next_attack'],tick+1)
            elif mid != 'EN12-A': a['next_attack'] = max(a['next_attack'], tick+a['interval'])
            if mid in ('EN01-A',timing.ROOT): a['root_until'] = tick+action['root_self_ticks']-1
            timing.released(a,action,tick,log)
            plans.released(battle,a,action,tick)
            if mid in ('EN02-A', 'EN03-A', 'EN05-A', 'EN17-A'): a['weak_from'] = a['weak_until'] = tick+1
            log('release', actor=a['id'], move=mid, action_id=action['id'],
                **{key:action[key] for key in ('derived','extra_chain','boss_mimic') if action.get(key)})
            mimic.observe(battle,a,action,tick,log)
            threats.observe_release(battle,a,action,tick,log)
        books.release(battle,a,action,ids,catalog,board,tick,log)
        heroes.release(battle,a,action,alive,catalog,board,tick,log)
        mimic.release(battle,a,action,alive,catalog,board,tick,log)
        if mid in ROSTER_MOVES:roster.release(battle,a,action,alive,catalog,board,tick,log)
        if mid in ('CMD-A','CMD-B'):
            commander.release(a,action,battle,alive,tick,catalog,board,log)
        if mimic.is_copy(action):
            for victim,amount in mimic.heals(battle,a,action,alive,catalog,board,tick):heals.append((a,victim,amount,action))
        elif action['kind'] in ('heal','hero_group_heal') and mid in heroes.DATA:
            for victim,amount in heroes.heals(battle,a,action,alive,catalog,board,tick):heals.append((a,victim,amount,action))
        elif action.get('source')=='book' and action['kind']=='heal':
            for victim,amount in sb.heals(battle,a,action,alive,catalog,board,tick):
                heals.append((a,victim,amount,action))
        elif action['kind']=='heal':
            targets=action['targets'] if mid==support.HEAL else [action['target']]
            for target_id in targets:
                victim=ids.get(target_id)
                if victim and victim['side']==a['side'] and not victim.get('mechanism') and legal(a,victim,action['range']):
                    amount=math.floor(action['heal_base']+action.get('healing_power_coefficient',1)*c.stat(a,'healing_power',tick))
                    heals.append((a,victim,amount,action))
                else:log('skill_miss',actor=a['id'],move=mid,action_id=action['id'],target=target_id)
        nullified=consume_next_attack_null(a,tick,log,action) if action['kind']=='damage' else False
        if action['kind'] != 'damage': continue
        if mid=='H06-A':
            tracked=ids.get(action['target'])
            action['release_target_position']=tracked['pos'][:] if tracked else None
        # A pushed caster fires from its current cell, not its windup origin.
        action['projectile_origin']=a['pos'][:]
        if action.get('source')=='book':action['book_hit_origin']=a['pos'][:]
        action['heat_bonus']=support.consume(a,action,ids.get(action['target']),tick,front,log)
        foes = [b for b in alive if b['side'] != a['side']]
        victims = []
        if action.get('source')=='book':
            victims=sb.targets(a,action,alive,catalog,board,tick) or []
        elif mimic.is_copy(action):
            victims=mimic.targets(a,action,alive,catalog,board,tick)
        elif mid in threats.MOVES:
            victims=threats.targets(a,action,alive,catalog,board)
        elif mid in peril.MOVES:
            victims=peril.targets(a,action,alive,catalog,board,battle=battle,tick=tick,log=log)
        elif mid in ROSTER_MOVES:
            victims=roster.targets(a,action,alive,catalog,board,tick)
        elif mid in bosses.MOVES:
            victims=bosses.targets(a,action,alive,catalog,board)
        elif mid in heroes.DATA:
            victims=heroes.targets(a,action,alive,catalog,board,tick)
        elif mid in sweeps.SWEEPS:
            victims=sweeps.targets(a,action,alive,catalog,board)
        elif mid in spatial.AREAS:
            victims=spatial.targets(a,action,alive,catalog,board)
        elif mid in fantasy.MOVES:
            victims = fantasy.targets(a, action, alive, catalog, board)
        elif mid in ('BASIC', 'CMD-EXTRA', 'S02-A', 'M01-A', 'M04-A'):
            victim = ids.get(action['target'])
            if victim and legal(a, victim, action['range']) and (mid!='M01-A' or victim['pos'] in action['cells']): victims = [victim]
        else:
            path = [tuple(p) for p in action['cells']]
            victims = sorted([b for b in foes if tuple(b['pos']) in path and legal(a, b, action['range'], int(mid in ('S03-A','M03-A')))], key=lambda b: (path.index(tuple(b['pos'])), b['id']))[:action['max_targets']]
        if mid=='BASIC':
            area=heroes.basic_targets(a,action,alive,catalog,board,tick)
            if area is not None:victims=area
        if action['medium'] == 'projectile' and mid not in fantasy.MOVES and mid not in heroes.DATA and not mimic.is_copy(action) and action.get('source')!='book':
            endpoint = ids[action['target']]['pos'] if mid in ('BASIC','CMD-EXTRA') and action['target'] in ids else action['cells'][-1] if action['cells'] else None
            if endpoint is not None:
                path = ray(a['pos'], endpoint)
                victims = sorted([b for b in foes if tuple(b['pos']) in path and legal(a, b, action['range'], int(mid in ('S03-A','M03-A')))], key=lambda b: (path.index(tuple(b['pos'])), b['id']))[:1]
        expanded=fortune.basic_targets(a,action,victims,alive,catalog,board,tick,log)
        if expanded is not None:victims=expanded
        if nullified:victims=[]
        if action.get('fortune_mode')=='pierce':
            penalty=fortune.interval_penalty(a,action)
            a['next_attack']=max(a['next_attack'],action['fortune_base_ready']+penalty)
            log('fortune_pierce_interval',actor=a['id'],action_id=action['id'],
                condition_ids=action['fortune_sources'],extra_owner_ids=action['fortune_extra_owners'],
                penalty=penalty,base_ready=action['fortune_base_ready'],next_attack=a['next_attack'])
        if mid=='BASIC' and a['kind'] in bosses.IDS and victims:
            bosses.basic_record(a,action,victims[0]['pos'],tick)
        for victim in victims: hits.append((a, victim, action, action.get('book_hit_origin',action.get('peril_hit_origin',action.get('threat_hit_origin',action.get('fortune_hit_origin',action.get('hero_hit_origin',action['origin'])))))[:]))
        if not victims and mid != 'BASIC': log('skill_miss', actor=a['id'], move=mid, action_id=action['id'])
        if mid in ('BASIC','CMD-EXTRA') and victims and a['stance'] != 'hold': facing_updates[a['id']] = c.direction(a['pos'], victims[0]['pos'])
        if mid == 'EN02-A':
            # Attack sweeps the locked line; locomotion separately stops at first blocker.
            occupied_now = {tuple(b['pos']) for b in alive if b != a}; dest = None; previous=tuple(a['pos'])
            for pos in map(tuple, action['cells']):
                if c.distance(previous,pos)!=1 or spatial.crossed(previous,pos,blocked_edges):break
                if pos not in board or pos in occupied_now or not catalog.terrain[board[pos]]['walkable']: break
                dest = pos; previous=pos
                if board[pos] == 'SHALLOW_WATER': break
            if dest:
                a['pos'] = list(dest); a['stationary'] = 0
                a['last_moved_tick']=tick
                c.enter_shallow(a,board[dest],tick,log)
                log('charge_move', actor=a['id'], position=list(dest),action_id=action['id'])
                gear.moved(a,tick,log)
                heroes.moved(a,'charge_move',tick)
                plans.moved(battle,a,'charge_move',tick,log)

    damage = {}; healing = {}; leech_credits = {}; bandages = []
    heal_sources = {}; settled_heal_actions = set()
    for a, victim, amount, action in heals:
        active_heal=not action.get('derived',False)
        source=a
        if active_heal:
            key=(a['id'],action['id'])
            if key not in heal_sources:
                # All recipients of one action share its source-side first-heal
                # state, even after the first effective recipient consumes it.
                heal_sources[key]={**a,'affix_uses':dict(a.get('affix_uses',{}))}
            source=heal_sources[key]
        first_bonus=active_heal and source['kind']=='M02' and source['healing_first']
        from balance_v062 import passive_value
        amount += passive_value('M02-P',6) if first_bonus else 0
        boosted=gear.outgoing_heal(source,amount) if active_heal else amount
        if active_heal:boosted=event_conditions.active_heal(a,boosted)
        after_received=gear.received_recovery(victim,boosted)
        effective = min(after_received, max(0, victim['stats']['hp']-victim['hp']-healing.get(victim['id'], 0)))
        if effective>0 and first_bonus:a['healing_first']=False
        healing[victim['id']] = healing.get(victim['id'], 0)+effective
        log('heal', actor=a['id'], target=victim['id'], move=action['move_id'], action_id=action['id'], requested=amount, after_outgoing=boosted, after_received=after_received,effective=effective)
        if active_heal:
            books.support_success(battle,a,action,effective,tick,log,target=victim,kind='heal')
            heroes.healed(battle,a,victim,action,effective,tick,log)
            if effective>0 and key not in settled_heal_actions:
                gear.active_heal_settled(a,effective,tick,log)
                settled_heal_actions.add(key)
            gear.queue_bandage(a,victim,effective,tick,action['id'],bandages,log)
        elif action.get('book_hot'):
            sb.support_success(battle,a,action,effective,tick,log,target=victim,kind='heal')
    boss_hit_owners=set();death_credits={}
    for a, victim, action, origin in protection.resolve(hits,alive,tick,front,log):
        surface=victim;victim=bosses.owner_of(battle,surface)
        hit_cell=surface['pos'][:]
        key=(a['id'],action['id'],victim['id'])
        if key in boss_hit_owners:
            log('boss_owner_hit_merged',actor=a['id'],target=victim['id'],surface=surface['id'],action_id=action['id']);continue
        boss_hit_owners.add(key)
        if action['move_id']=='BASIC' and 'sb_primary_recipient' not in action:
            action['sb_primary_recipient']=victim['id']
        if veil.deflect(a,victim,action,action['projectile_origin'],alive,catalog,board,tick,front,log):
            heroes.projectile_deflected(battle,a,victim,action,tick,log)
            mimic.projectile_deflected(battle,a,victim,action,tick,log)
            continue
        dtype = action['damage_type']; attack = c.stat(a, dtype+'_attack', tick)
        attack=mimic.attack(a,action,attack)
        crit = action.get('prepared_crit')
        dodge=min(.5,gear.dodge(victim,tick)+(.2 if plans.active(victim.get('plan_dodge'),tick) else 0)+(.3 if plans.active(victim.get('book_dodge'),tick) else 0))
        if dodge and roll(battle['seed'],action['id'],victim['id'],'evade')<dodge:
            log('evaded',actor=a['id'],target=victim['id'],action=action['move_id'],action_id=action['id'])
            continue
        book_hit=sb.before_hit(battle,a,victim,action,tick,log,spend_shields,attack=attack)
        if 'had_shield_before' in book_hit:
            snapshot=action.setdefault('sb_had_shield_before',{})
            snapshot[victim['id']]=snapshot[surface['id']]=book_hit['had_shield_before']
        part_defense=surface.get('boss_rule',{}).get(dtype+'_defense_offset',0)
        defense = c.stat(victim, dtype+'_defense', tick)+part_defense
        heat_defense=support.defense_modifier(victim,origin,dtype,tick,front)
        petal_defense=timing.defense_modifier(victim,dtype,tick)
        defense+=heat_defense+petal_defense
        weak = echo_weak.get(victim['id'], weak_active(victim, tick)) and not front(victim, origin)
        if weak: defense += victim['weak_point'].get(dtype+'_defense_modifier', 0)
        if action.get('plan_window_target')==victim['id']:defense=max(0,defense-8)
        hero_defense=heroes.defense(a,surface,action,tick,log) if attack>0 else 0
        hero_defense=max(hero_defense,mimic.defense(a,surface,action,tick,log) if attack>0 else 0)
        defense=max(0,defense-hero_defense)
        defense*=book_hit.get('defense_factor',1)
        reduction = .25 if victim['kind'] == 'S01' and victim['stance'] == 'hold' and victim['stationary'] > 0 and front(victim, origin) else 0
        conditional=max(heroes.attack_bonus(a,action),heroes.attack_increase(battle,a,surface,action,tick,origin),commander.damage_bonus(battle,a,victim,action,tick),action.get('plan_stance',0),action.get('roster_stance',0) if action.get('roster_m06_target')==surface['id'] else 0,.25 if action.get('plan_pursuit_target')==victim['id'] else 0,books.increase(a,victim,action,tick,front,log) if attack>0 else 0)
        conditional=max(conditional,mimic.damage_bonus(battle,a,victim,action,tick))
        increase=gear.increase(a,action,prior_pending.get(victim['id']),tick,conditional+action.get('heat_bonus',0)+event_conditions.increase(a,action,victim,tick,origin,hit_cell),log) if attack>0 else 0
        reduction=min(.75,reduction+heroes.damage_reduction(battle,victim,alive,tick)+event_conditions.damage_reduction(victim,tick))
        reduction=gear.reduction(victim,tick,reduction,log) if attack>0 else reduction
        if attack>0 and not action.get('derived'):reduction=books.reduction(victim,reduction,tick,log)
        chance,extra=gear.critical(a)
        if action.get('plan_crit'):chance+=.25;extra+=.5
        if crit:chance+=crit['critical_chance'];extra+=crit['extra_critical_damage']
        chance=min(.75,chance);extra=min(1,extra)
        extra=min(1,max(extra,book_hit.get('critical_extra_min',0)))
        critical=bool(attack>0 and (book_hit.get('force_critical') or chance>0 and extra>0 and roll(battle['seed'],action['id'],victim['id'],'crit')<chance))
        bonus=(1+increase)*(1+extra if critical else 1)
        outgoing_factor,incoming_factor=gear.damage_factors(a,victim,action)
        outgoing_factor*=heroes.outgoing_factor(a,tick)*heroes.damage_multiplier(battle,a,surface,action,tick,origin)
        outgoing_factor*=event_conditions.outgoing_factor(a,action,victim,tick,origin,hit_cell)
        outgoing_factor*=battle_enrage.damage_multiplier(battle,a,tick)
        incoming_factor*=heroes.incoming_factor(victim,tick)
        incoming_factor*=event_conditions.incoming_factor(victim,tick)
        coefficient=action.get('fortune_coefficients',{}).get(surface['id'],action.get('hero_coefficients',{}).get(surface['id'],action['coefficient']))
        coefficient+=book_hit.get('coefficient_add',0)
        amount = max(1, math.floor(attack*coefficient*bonus*100/(100+max(0, defense))*(1-reduction)*outgoing_factor*incoming_factor)) if attack > 0 else 0
        mark_bonus=plans.mark_damage(battle,a,victim,action,amount,tick,log)
        amount+=mark_bonus
        had_shield = victim['shield']>0 or any(p['amount']>0 for p in victim['timed_shields']) or any(victim['id'] in p['members'] and p['amount']>0 for p in pools)
        remaining = spend_shields(victim, pools, amount,tick)
        remaining = fortune.relay(battle,victim,remaining,alive,catalog,board,tick,action,damage,healing,spend_shields,log)
        # Credit only finite HP available before leech; shared lethal hits cannot
        # each claim the victim's full life, and leech cannot feed itself this tick.
        actual_hp_damage=min(remaining,max(0,victim['hp']+healing.get(victim['id'],0)-damage.get(victim['id'],0)))
        if actual_hp_damage>0 and victim['id'] not in death_credits and damage.get(victim['id'],0)+remaining>=victim['hp']+healing.get(victim['id'],0):
            death_credits[victim['id']]=(a,victim,action)
        if not victim.get('mechanism'):gear.leech_credit(a,action,actual_hp_damage,leech_credits)
        if actual_hp_damage>0 and victim.get('nursing') and not victim['nursing']['used']:
            victim['nursing']['used']=True;victim['nursing_pending']=victim['nursing']['amount']
        damage[victim['id']] = damage.get(victim['id'], 0)+remaining
        if surface.get('boss_part'):surface['boss_damage']+=actual_hp_damage
        log('hit', actor=a['id'], target=victim['id'], damage_type=dtype,hit_distance=c.distance(origin,hit_cell),flank=not front(victim,origin), **({'surface':surface['id'],'part_defense_modifier':part_defense} if surface.get('boss_part') else {}), action=action['move_id'], action_id=action['id'], raw=amount, absorbed=amount-remaining, hp_damage=remaining, actual_hp_damage=actual_hp_damage, weak_point=weak, reduction=reduction, critical=critical, increase=increase, heat_defense_modifier=heat_defense,petal_defense_modifier=petal_defense,outgoing_factor=outgoing_factor,incoming_factor=incoming_factor,standard_mark_bonus=mark_bonus,hero_defense_reduction=hero_defense,enrage_multiplier=battle_enrage.damage_multiplier(battle,a,tick),plan_defense_reduction=8 if action.get('plan_window_target')==victim['id'] else 0)
        threats.damage(battle,a,victim,action,actual_hp_damage,tick,log)
        peril.hit(battle,a,victim,action,actual_hp_damage,tick,log)
        plans.hit(battle,a,victim,action,amount,tick,log,mark_consumed=bool(mark_bonus))
        heroes.hit(battle,a,victim,action,amount,tick,log,spend_shields)
        mimic.hit(battle,a,victim,action,amount,tick,log,spend_shields)
        if a['kind'] in roster.MERC_CARDS:roster.hit(battle,a,victim,action,amount,tick,log)
        sb.after_hit(battle,a,victim,action,amount,tick,log,context=book_hit)
        if action['move_id']=='BASIC':
            if amount>0:a['book_last_hit']=tick
            if a['kind'] not in bosses.IDS:
                a['basic_history'].append({'action_id':action['id'],'tick':tick,'cell':hit_cell})
                a['basic_history'][:]=a['basic_history'][-2:]
            if a['kind'] in ('EN06','EL03'):log('echo_record',actor=a['id'],cell=victim['pos'][:],action_id=action['id'])
            if a['kind']=='M03' and not a['armor_check_used'] and had_shield:
                from balance_v062 import passive_value
                strip=passive_value('M03-P',6)
                a['armor_check_used']=True;left=spend_shields(victim,pools,strip,tick)
                log('armor_check',actor=a['id'],target=victim['id'],removed=strip-left)
        if amount>0 and action['move_id']=='EN07-A':pushes.append((a,victim,action))
        if amount>0 and action['move_id']=='M01-A' and not sb.movement_control_immune(victim,tick) and not threats.control_immune(victim):
            victim['blocked_until']=max(victim['blocked_until'],tick+1)
            log('movement_block',actor=a['id'],target=victim['id'],until=tick+1)
        if amount>0 and action['move_id'] in ('EN20-A','EN23-A'):
            movement_blocks.append((a,victim,action))
        if amount>0 and action['move_id'] in ('M04-A','M08-A'):
            cast=victim['pending']
            if cast and cast['id']==action.get('target_cast') and cast.get('delayable_cast') and not cast.get('delayed') and cast['due']>tick and not threats.control_immune(victim):
                cast['due']+=1;cast['delayed']=True
                log('cast_delayed',actor=a['id'],target=victim['id'],cast_id=cast['id'],release_tick=cast['due'])
                protection.delayed(victim,a,tick,log)
                plans.delayed(battle,victim,cast,tick,log,action['id'],action['move_id'])
    for a in released: a['pending'] = None
    for a in alive:
        if a.get('boss_part'):continue
        a['hp'] = max(0, min(a['stats']['hp'], a['hp']+healing.get(a['id'], 0)-damage.get(a['id'], 0)))
        if a['id'] in facing_updates: a['facing'] = heroes.facing(a,tick,veil.fixed_facing(a,tick,facing_updates[a['id']]))
        if not a['hp']: a['pending'] = None; a['downed_tick']=tick; log('down', actor=a['id'])
    for attacker,victim,action in death_credits.values():
        if victim['hp']<=0:
            log('death_credit',actor=attacker['id'],target=victim['id'],action_id=action['id'],move=action['move_id'])
            heroes.on_kill(battle,attacker,victim,action,tick,log)
            mimic.on_kill(battle,attacker,victim,action,tick,log)
    for a in alive:
        amount=a.pop('nursing_pending',0)
        if amount and a['hp']>0:
            incoming=gear.received_recovery(a,amount)
            healed=min(incoming,a['stats']['hp']-a['hp']);a['hp']+=healed
            log('town_nursing',target=a['id'],requested=amount,after_received=incoming,effective=healed)
    for actor, victim, action in movement_blocks:
        if victim['hp']>0 and not victim.get('immune_movement_block',False) and not sb.movement_control_immune(victim,tick) and not threats.control_immune(victim):
            victim['blocked_until']=max(victim['blocked_until'],tick+1)
            log('movement_block',actor=actor['id'],target=victim['id'],move=action['move_id'],until=tick+1)
    sweeps.settle_pushes(pushes,battle,catalog,board,blocked_edges,tick,log)
    gear.settle_leech(leech_credits,log)
    gear.settle_bandages(bandages,tick,log)
    veil.end_tick(actions,alive,catalog,board,tick,log)
    commander.end_tick(battle,tick,log)
    necromancy.settle(actions,battle,catalog,board,tick,log)
    reinforcements.settle(actions,battle,catalog,board,tick,log)
    heroes.end_tick(actions,battle,catalog,board,tick,log)
    mimic.end_tick(actions,battle,catalog,board,tick,log)
    plans.end_tick(battle,tick,log)
    roster.end_tick(battle,tick,log)
    sb.end_tick(battle,tick,log,catalog,board)
    spatial.cancel_invalid(battle,log)
    bosses.end_tick(battle,tick,log)
    threats.end_tick(battle,tick,log)
    peril.end_tick(battle,tick,log)
    sides = {a['side'] for a in battle['actors'] if a['hp'] > 0 and not a.get('mechanism')}
    if finale_battle.settle(battle,tick,log):pass
    elif any(a['kind'] in bosses.IDS for a in battle['actors']):
        bosses.settle(battle)
    elif 'player' not in sides: battle['result'] = 'DEFEAT'
    elif battle.get('retreat_requested'): battle['result'] = 'RETREAT'
    elif 'enemy' not in sides and not reinforcements.pending(battle): battle['result'] = 'VICTORY'
    changed = initial != json.dumps([(a['id'], a['hp'], a['shield'], a['pos']) for a in alive])
    progressing = actions or heals or any(a['pending'] or a['next_attack'] > tick or a['skill_ready'] > tick or any(v > tick for v in a['move_ready'].values()) for a in alive)
    battle['no_change'] = 0 if changed or progressing else battle['no_change']+1
    if tick == 120 or battle['no_change'] == 6: log('diagnostic', reason='120_tick' if tick == 120 else 'no_progress')
    if battle['result']: log('result', result=battle['result'])
