"""Public adjacent sweeps, one initial sidestep, and post-damage displacement."""
import combat as c
import spatial_moves as spatial
import gear_affixes as gear

SWEEPS={'EN07-A','EL01-B'}
STEP='EL04-B'
BRIEFINGS={
    'EN07':'扫喙：1拍起手、0.9物理、C5／2次；公开正面相邻三格，最多命中1人。正伤后将仍站立者推向预告的一格落点；落点被占、封边或越界则只伤害，无撞墙加伤，不推倒地者。',
    'EL04':'剪潮：先一次1拍预警、最多1格侧步，结束后下一拍才可起手扫喙；无合法侧步则跳过，不获得免费攻击。扫喙沿用EN07的锁格和推挤；侧步也受占位、定身与封边约束。',
    'EL01':'裂壳：沿用沉角冲线；冲锋释放后的后续拍，额外一次1拍预警、1.1物理侧扫，锁定左侧或右侧相邻两格，最多2人、C8。侧扫不追踪，不在冲锋释放同拍连发。',
}


def install(cat):
    tags={'EN07':{'push'},'EL04':{'elite_behavior'},'EL01':{'elite_behavior'}}
    for uid,briefing in BRIEFINGS.items():
        cat.enemy_templates[uid]['briefing']=briefing
        cat.enemy_templates[uid]['calibration_unsupported_mechanics']=[x for x in cat.enemy_templates[uid].get('calibration_unsupported_mechanics',[]) if x not in tags[uid]]
    for e in cat.encounters.values():
        completed=set()
        for u in e['units']:
            uid=u['enemy_id']
            if uid not in BRIEFINGS:continue
            u['briefing']=BRIEFINGS[uid];completed.update(tags[uid])
            u['calibration_unsupported_mechanics']=[x for x in u.get('calibration_unsupported_mechanics',[]) if x not in tags[uid]]
        if any(u['enemy_id'] in cat.elite_ids and u['enemy_id'] not in {'EL01','EL04','EL06'} for u in e['units']):completed.discard('elite_behavior')
        e['calibration_unsupported_mechanics']=[x for x in e.get('calibration_unsupported_mechanics',[]) if x not in completed]


def cell(origin,direction):
    dq,dr=c.DIRS[direction%6];return (origin[0]+dq,origin[1]+dr)


def legal_cell(pos,catalog,board):return pos in board and catalog.terrain[board[pos]]['walkable']


def sweep_choice(actor,card,foes,catalog,board,tick):
    if card['move_id']=='EL01-B':
        completed=actor['completed_moves'].get('EN02-A')
        if completed is None or completed>=tick:return None
    if card.get('requires_initial_side_step_finished_or_no_legal_step') and not actor['initial_side_step']:return None
    for victim in sorted(foes,key=lambda a:(c.distance(actor['pos'],a['pos']),a['id'])):
        if c.distance(actor['pos'],victim['pos'])!=1:continue
        if card['move_id']=='EN07-A':
            facing=c.direction(actor['pos'],victim['pos']);groups=[[-1,0,1]]
        else:facing=actor['facing'];groups=[[1,2],[4,5]]
        for group in groups:
            cells=[cell(actor['pos'],facing+d) for d in group]
            cells=[p for p in cells if legal_cell(p,catalog,board) and c.visible(catalog,board,actor['pos'],p)]
            # Board boundaries clip a fan; a side sweep still needs its public pair.
            if card['move_id']=='EL01-B' and len(cells)!=2:continue
            if tuple(victim['pos']) in cells:return victim,cells,facing
    return None


def sidestep_choice(actor,foes,catalog,board,occupied,blocked,tick):
    if actor['initial_side_step'] or tick<=max(actor['root_until'],actor['move_pause_until'],actor['blocked_until']):return None
    for victim in sorted(foes,key=lambda a:(c.distance(actor['pos'],a['pos']),a['id'])):
        if not c.visible(catalog,board,actor['pos'],victim['pos']):continue
        facing=c.direction(actor['pos'],victim['pos'])
        candidates=[cell(actor['pos'],facing+d) for d in (1,2,4,5)]
        candidates=[p for p in candidates if legal_cell(p,catalog,board) and p not in occupied and not spatial.crossed(actor['pos'],p,blocked)]
        if candidates:return victim,min(candidates,key=lambda p:(c.distance(p,victim['pos']),p))
    return None


def push_preview(actor,cells,catalog,board,occupied,blocked):
    result=[]
    for origin in cells:
        away=c.direction(actor['pos'],origin);straight=cell(origin,away)
        candidates=[p for p in spatial.neighbors(origin) if legal_cell(p,catalog,board) and p not in occupied
                    and not spatial.crossed(origin,p,blocked) and c.distance(p,actor['pos'])>c.distance(origin,actor['pos'])]
        dest=min(candidates,key=lambda p:(p!=straight,p)) if candidates else None
        result.append({'from':list(origin),'to':list(dest) if dest else None})
    return result


def targets(actor,action,alive,catalog,board):
    candidates=spatial.targets(actor,{**action,'max_targets':len(alive)},alive,catalog,board)
    return sorted(candidates,key=lambda a:(c.distance(actor['pos'],a['pos']),a['id']))[:action['max_targets']]


def settle_pushes(pushes,battle,catalog,board,blocked,tick,log):
    # Resolve after all HP settlement. Reserve old and new cells for this batch,
    # so two simultaneous pushes cannot form a chain or occupy the same cell.
    occupied={tuple(a['pos']) for a in battle['actors'] if a['hp']>0};pushed=set()
    for actor,victim,action in sorted(pushes,key=lambda row:(row[0]['id'],row[2]['id'],row[1]['id'])):
        origin=tuple(victim['pos']);row=next((p for p in action['push_destinations'] if tuple(p['from'])==origin),None)
        dest=tuple(row['to']) if row and row['to'] is not None else None
        reason=None
        if victim['hp']<=0 or victim.get('mechanism') or tick<victim.get('active_from',1):reason='not_actionable'
        elif victim.get('kind')=='ADMIN' and victim.get('super_armor'):reason='super_armor'
        elif victim['id'] in pushed:reason='already_pushed_this_tick'
        elif not dest:reason='no_public_destination'
        elif c.distance(origin,dest)!=1 or not legal_cell(dest,catalog,board):reason='illegal_destination'
        elif dest in occupied:reason='occupied'
        elif spatial.crossed(origin,dest,blocked):reason='closed_edge'
        if reason:
            log('push_blocked',actor=actor['id'],target=victim['id'],action_id=action['id'],reason=reason);continue
        occupied.add(dest);pushed.add(victim['id']);victim['pos']=list(dest);victim['stationary']=0;victim['last_moved_tick']=tick
        c.enter_shallow(victim,board[dest],tick,log)
        log('push',actor=actor['id'],target=victim['id'],action_id=action['id'],origin=list(origin),position=list(dest))
        gear.moved(victim,tick,log)
        import heroes
        heroes.moved(victim,'push',tick)


def describe(battle):
    lines=[]
    for actor in battle['actors']:
        action=actor['pending']
        if actor['hp']>0 and action and 'push_destinations' in action:
            lines.append('推挤预告 '+actor['id']+'：'+str(action['push_destinations']))
        if actor['hp']>0 and action and action['move_id']==STEP:lines.append('侧步预告 '+actor['id']+'：'+str(action['cells']))
    return '\n'.join(lines)
