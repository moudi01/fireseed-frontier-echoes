"""Authored regional bosses and memory generals. Adaptation uses existing escorts; no finale."""
from copy import deepcopy
import math
import combat as c

IDS = {'BX01','BX02','BX03','MG01','MG02','MG03','MG04','DEMON','ADMIN'}
MOVES = {uid+'-'+s for uid in IDS for s in ('AB' if uid.startswith('BX') else 'ABC')}
ENCOUNTERS = {'G02':'OPEN','G06':'OPEN','G10':'OPEN','BATTLE-MG01':'DUAL_FLANK',
              'BATTLE-MG02':'MIRROR_COURT','BATTLE-MG03':'SALT_CROSSING','BATTLE-MG04':'FORGE_CROSSING'}


# Controlled greybox calibration for the 10-vs-14 Cost cliff. The authored
# JSON remains the source record; these multipliers are applied at load time
# so the encounter table can be reverted without editing source documents.
COST_TUNING={
 'BATTLE-MG03':{'MG03':{'hp':.88,'physical_attack':.88,'magic_attack':.85},
                'EN06':{'hp':.90,'magic_attack':.90},
                'EN15':{'hp':.90,'healing_power':.80}},
 'BATTLE-MG04':{'MG04':{'hp':.88,'physical_attack':.85,'magic_attack':.88},
                'EN04':{'hp':.90,'physical_attack':.90},
                'EN17':{'hp':.90,'physical_attack':.90}},
}


def _tune(encounter):
    for unit in encounter['units']:
        factors=COST_TUNING.get(encounter['encounter_id'],{}).get(unit['enemy_id'],{})
        for stat,factor in factors.items():
            base=unit['stats'].get(stat)
            if base is None:continue
            unit['stats'][stat]=max(1,round(base*factor))


def install(cat):
    for encounter in cat.encounters.values():
        for unit in encounter['units']:
            if unit['enemy_id'] not in IDS: continue
            template=cat.enemy_templates[unit['enemy_id']]
            unit['phases']=deepcopy(template['phases'])
            unit['boss_parts']=deepcopy(template.get('parts',[]))
            unit['awakening']=deepcopy(template.get('awakening',{}))
            unit['obsession_item_ref']=template.get('obsession_item_ref')
        if any(u['enemy_id'] in IDS for u in encounter['units']):
            encounter['calibration_unsupported_mechanics']=[x for x in encounter.get('calibration_unsupported_mechanics',[]) if x not in ('new_story_boss','full_hex_pathfinding','dialogue_windows')]
            encounter['calibration_unsupported_mechanics']=[x for x in encounter['calibration_unsupported_mechanics'] if x!='candidate_adaptive_cards_not_connected']
        _tune(encounter)


def initialize(a):
    if a['kind'] not in IDS:return
    a.update(boss_phase=1,boss_cursor=0,boss_axis=None,boss_public_axis=a['facing'],boss_part_offsets=[])


def attach_parts(actors, encounter):
    """Targetable occupied surfaces; HP is only a mirror of their one owner."""
    by_owner={u.get('hp_owner_id',u['instance_id']):u['instance_id'] for u in encounter['units']}
    for spec in encounter.get('board_parts',[]):
        owner=next(a for a in actors if a['id']==by_owner[spec['hp_owner_id']])
        if owner['kind'] not in IDS:continue
        rule=next(p for p in owner['boss_parts'] if p['linked_move_id']==spec['linked_move_id'])
        part=deepcopy(owner)
        part.update(id=spec['instance_id'],kind='BOSS_PART',name=rule['part_id'],pos=spec['position'][:],
                    moves=[],phases=[],boss_part=True,boss_owner=owner['id'],boss_rule=deepcopy(rule),
                    boss_damage=0,boss_broken=False,boss_threshold=math.ceil(owner['stats']['hp']*rule['break_threshold_ratio']),
                    boss_part_offsets=[],pending=None)
        part['offset']=[part['pos'][i]-owner['pos'][i] for i in (0,1)]
        actors.append(part)
    refresh_offsets(actors)


def refresh_offsets(actors):
    for owner in actors:
        if owner['kind'] in IDS:
            owner['boss_part_offsets']=[p['offset'][:] for p in actors if p.get('boss_owner')==owner['id'] and not p['boss_broken'] and owner['hp']>0]


def owner_of(battle,actor):
    return next(a for a in battle['actors'] if a['id']==actor['boss_owner']) if actor.get('boss_part') else actor


def footprint(actor,pos):
    return {tuple(pos)} | {(pos[0]+q,pos[1]+r) for q,r in actor.get('boss_part_offsets',[])}


def can_move(actor,previous,pos,occupied,cat,board,edges=()):
    import spatial_moves
    others=occupied-footprint(actor,actor['pos'])
    points=footprint(actor,pos)
    dq,dr=pos[0]-previous[0],pos[1]-previous[1]
    return all(p not in others and p in board and cat.terrain[board[p]]['walkable'] and
               not spatial_moves.crossed((p[0]-dq,p[1]-dr),p,edges) for p in points)


def moved(battle,actor):
    for part in battle['actors']:
        if part.get('boss_owner')==actor['id'] and not part['boss_broken']:
            part['pos']=[actor['pos'][i]+part['offset'][i] for i in (0,1)]


def cards(a):
    if a['kind'] not in IDS:return a['moves']
    allowed=next(p['move_ids'] for p in a['phases'] if p['phase']==a['boss_phase'])
    ordered=a['moves'][a['boss_cursor']:]+a['moves'][:a['boss_cursor']]
    return [card for card in ordered if card['move_id'] in allowed and card['move_id'] not in a.get('boss_disabled',[])]


def started(a,card):
    if a['kind'] in IDS:a['boss_cursor']=(next(i for i,x in enumerate(a['moves']) if x['move_id']==card['move_id'])+1)%len(a['moves'])


def choose(battle,a,card,foes,cat,board):
    from mechanics import line
    mid=card['move_id'];shape=card.get('shape');extra={}
    def finish(target,cells,details):
        if not card.get('pressure_radius'):return target,cells,details
        from late_pressure import locked_area
        locked=locked_area(a,card,cells,cat,board)
        if card.get('pressure_radius'):
            if not any(tuple(v['pos']) in locked for v in foes):return None
            details={**details,'pressure_core_cells':[list(p) for p in cells],
                     'pressure_radius':card['pressure_radius']}
        return target,locked,details
    if card['kind']=='shield':return None,[],{}
    legal=lambda p:c.distance(a['pos'],p)<=card['range'] and c.visible(cat,board,a['pos'],p,card.get('low_obstacle_penetration',card.get('low_obstacle_penetration_budget',0)))
    targets=sorted([v for v in foes if legal(v['pos'])],key=lambda v:(c.distance(a['pos'],v['pos']),v['id']))
    if shape=='last_two_real_basic_cells':
        locked=[]
        for row in a['basic_history'][-2:]:
            if row['cell'] not in locked and legal(row['cell']):locked.append(row['cell'][:])
        if not locked:return
        extra['history_action_ids']=[r['action_id'] for r in a['basic_history'][-2:]]
        return finish(None,locked,extra)
    if shape=='historic_front_axis':
        facing=a['boss_axis']['facing'] if a['boss_axis'] else a['boss_public_axis']
        locked=[p for p in line(a['pos'],facing,card['range']) if p in board and legal(p)]
        extra.update(facing=facing,history_axis=deepcopy(a['boss_axis']),no_history=a['boss_axis'] is None)
        if locked:return finish(None,locked,extra)
        return
    if shape=='two_public_anchor_cells':
        locked=[p for p in card['locked_anchor_cells'] if tuple(p) in board and legal(p)]
        if locked:return finish(None,locked,{'public_anchors':deepcopy(card['locked_anchor_cells'])})
        return
    if not targets:return
    victim=targets[0];facing=c.direction(a['pos'],victim['pos']);extra['facing']=facing
    if shape=='two_lowest_hp_ratio_cells':
        targets.sort(key=lambda v:(v['hp']/v['stats']['hp'],v['id']))
        return finish(targets[0],[v['pos'][:] for v in targets[:2]],extra)
    if shape=='three_locked_cells':
        targets=[v for v in targets if v['kind']!='PET-H04']
        if targets:return finish(targets[0],[v['pos'][:] for v in targets[:3]],extra)
        return
    if shape=='one_cell':return finish(victim,[victim['pos'][:]],extra)
    if shape=='front_adjacent_fan_three':
        locked=[(a['pos'][0]+c.DIRS[d%6][0],a['pos'][1]+c.DIRS[d%6][1]) for d in (facing-1,facing,facing+1)]
    elif shape in ('front_two_cells','front_three_cells'):
        locked=line(a['pos'],facing,2 if shape=='front_two_cells' else 3)
    elif shape=='locked_side_lane':
        # A public line through the selected target, perpendicular to the firing axis.
        dq,dr=c.DIRS[(facing+2)%6]
        locked=[(victim['pos'][0]+dq*k,victim['pos'][1]+dr*k) for k in range(-card['range'],card['range']+1)]
    else:raise ValueError('未定义首领锁格形状：'+str(shape))
    locked=[p for p in locked if tuple(p) in board and legal(p)]
    if tuple(victim['pos']) not in [tuple(p) for p in locked]:return
    return finish(victim,locked,extra)


def targets(a,action,alive,cat,board):
    path=[tuple(p) for p in action['cells']]
    return sorted([v for v in alive if v['side']!=a['side'] and tuple(v['pos']) in path
                   and c.distance(a['pos'],v['pos'])<=action['range']
                   and c.visible(cat,board,a['pos'],v['pos'],action.get('low_obstacle_penetration',action.get('low_obstacle_penetration_budget',0)))],
                  key=lambda v:(path.index(tuple(v['pos'])),v['id']))[:action['max_targets']]


def shield(a,action,tick,log):
    a['timed_shields'].append({'effect':action['move_id'],'source':a['id'],'amount':action['shield'],
                              'expires':tick+action['duration_ticks']-1,'created':tick})
    log('boss_private_shield',actor=a['id'],move=action['move_id'],amount=action['shield'],expires=tick+action['duration_ticks']-1)


def basic_record(a,action,cell,tick):
    if a['kind'] in IDS:
        a['boss_axis']={'action_id':action['id'],'tick':tick,'facing':c.direction(a['pos'],cell)}
        a['basic_history'].append({'action_id':action['id'],'tick':tick,'cell':list(cell)})
        a['basic_history'][:]=a['basic_history'][-2:]


def end_tick(battle,tick,log):
    for part in battle['actors']:
        if not part.get('boss_part'):continue
        owner=owner_of(battle,part)
        if not part['boss_broken'] and part['boss_damage']>=part['boss_threshold']:
            part['boss_broken']=True
            mid=part['boss_rule']['linked_move_id'];owner.setdefault('boss_disabled',[]).append(mid)
            # The current tick's due action already settled. Cancel only future releases.
            if owner['pending'] and owner['pending']['move_id']==mid:
                owner['move_ready'][mid]=tick+owner['pending']['cooldown'];owner['pending']=None
                log('boss_part_cancel',actor=owner['id'],move=mid,part=part['id'])
            log('boss_part_broken',actor=owner['id'],part=part['id'],move=mid,damage=part['boss_damage'],threshold=part['boss_threshold'])
        part['hp']=0 if part['boss_broken'] else owner['hp']
    refresh_offsets(battle['actors'])
    for a in battle['actors']:
        if a['kind'] not in IDS:continue
        for phase in a['phases']:
            if phase['phase']>a['boss_phase'] and a['hp']<=a['stats']['hp']*phase['enter_hp_ratio']:
                a['boss_phase']=phase['phase']
                log('boss_phase',actor=a['id'],phase=a['boss_phase'],hp=a['hp'],effective_tick=tick+1)
                if a['kind'].startswith('MG'):
                    wid=a['kind']+'-W'+str(a['boss_phase']-1)
                    memory=battle['boss_memory'][a['kind']]
                    if wid not in memory['offered']:
                        memory['offered'].append(wid)
                        if memory['eligible']:battle['boss_dialogue_queue'].append({'boss':a['kind'],'window':wid})
                        else:log('boss_memory_unavailable',boss=a['kind'],window=wid,reason='missing_original_item_or_verified_testimony')


def prepare(battle,context=None):
    context=context or {}
    battle.update(boss_memory={},boss_dialogue_queue=[],boss_receipts={})
    for a in battle['actors']:
        if not a['kind'].startswith('MG') or a['kind'] not in IDS:continue
        eligible=a.get('obsession_item_ref') in context.get('items',[]) and a['kind'] in context.get('verified_testimonies',[])
        battle['boss_memory'][a['kind']]={'eligible':eligible,'offered':[],'committed':[],'skipped':[],
                                          'source':deepcopy(context),'retained':False}


def paused(battle):return bool(battle.get('boss_dialogue_queue'))


def recall(battle):
    if battle['result']!='VICTORY' or paused(battle):raise ValueError('追忆要求已胜利且当前没有待答窗口。')
    for uid,m in battle['boss_memory'].items():
        if not m['eligible']:raise ValueError('仍缺原物或已核实的镇民证词。')
        for n in (1,2):
            wid=uid+'-W'+str(n)
            if wid not in m['committed']:battle['boss_dialogue_queue'].append({'boss':uid,'window':wid})


def dialogue(battle,choice,window):
    if choice not in ('evidence','retain','skip'):raise ValueError('memory evidence/retain/skip 窗口ID')
    if not paused(battle):raise ValueError('没有待处理记忆窗口。')
    row=battle['boss_dialogue_queue'][0]
    if window!=row['window']:raise ValueError('只能回应当前窗口：'+row['window'])
    m=battle['boss_memory'][row['boss']]
    expected='evidence' if window.endswith('W1') else 'retain'
    if choice!='skip' and (choice!=expected or not m['eligible'] or (expected=='retain' and row['boss']+'-W1' not in m['committed'])):
        raise ValueError('证据或前一记忆窗口尚未提交；可跳过，战后再补。')
    m['skipped' if choice=='skip' else 'committed'].append(window)
    if choice=='retain':m['retained']=True
    battle['boss_dialogue_queue'].pop(0)
    battle['events'].append({'tick':battle['tick'],'type':'boss_memory_choice','event_id':f"{battle['battle_id']}:event:{len(battle['events'])+1}",**row,'choice':choice})
    previous=battle['result']
    if not paused(battle):settle(battle)
    if not previous and battle['result']:
        battle['events'].append({'tick':battle['tick'],'type':'result','result':battle['result'],
                                'event_id':f"{battle['battle_id']}:event:{len(battle['events'])+1}"})


def settle(battle):
    if paused(battle):return
    live=[a for a in battle['actors'] if a['hp']>0 and not a.get('mechanism') and not a.get('boss_part')]
    if not any(a['side']=='player' and a['kind']!='PET-H04' for a in live):battle['result']='DEFEAT'
    elif battle.get('retreat_requested'):battle['result']='RETREAT'
    elif not any(a['side']=='enemy' for a in live):battle['result']='VICTORY'
    if battle['result']=='VICTORY':
        for a in battle['actors']:
            if a['kind'] not in IDS:continue
            m=battle['boss_memory'].get(a['kind'],{})
            battle['boss_receipts'].setdefault(a['kind'],{'defeated':True,'awakened':False,
                                                         'battle_id':battle['battle_id'],'world_reset':False})
            if m.get('retained'):battle['boss_receipts'][a['kind']]['awakened']=True


def describe(battle):
    lines=[]
    for a in battle['actors']:
        if a['kind'] in IDS:lines.append(f"{a['id']} 阶段{a['boss_phase']} 可用招式{[x['move_id'] for x in cards(a)]} 禁用{a.get('boss_disabled',[])}")
        if a.get('boss_part'):lines.append(f"部位 {a['id']} 共用生命所有者 {a['boss_owner']}，累计{a['boss_damage']}/{a['boss_threshold']}，已破坏{a['boss_broken']}")
    if paused(battle):
        row=battle['boss_dialogue_queue'][0];a=next(a for a in battle['actors'] if a['kind']==row['boss'])
        card=next(w for w in a['awakening']['dialogue_windows'] if w['window_id']==row['window'])
        lines.append('逻辑暂停 '+row['window']+'：'+str(card)+'；memory '+('evidence' if row['window'].endswith('W1') else 'retain')+' '+row['window']+'，或 memory skip '+row['window'])
    if battle.get('boss_receipts'):lines.append('独立战斗回执：'+str(battle['boss_receipts']))
    import boss_mimic,boss_threats
    for text in (boss_mimic.describe(battle),boss_threats.describe(battle)):
        if text:lines.append(text)
    return '\n'.join(lines)


def validate(battle):
    if not battle:return
    import boss_mimic,boss_threats
    boss_mimic.validate(battle)
    boss_threats.validate(battle)
    ids={a['id']:a for a in battle['actors']}
    for a in battle['actors']:
        if a['kind'] in IDS:
            if a.get('boss_phase') not in (1,2,3) or not 0<=a.get('boss_cursor',-1)<len(a['moves']):
                raise ValueError('首领阶段或招式队列存档无效。')
        if a.get('boss_part'):
            owner=ids.get(a.get('boss_owner'))
            if not owner or owner['kind'] not in IDS or a['hp']!=(0 if a['boss_broken'] else owner['hp']):
                raise ValueError('首领部位生命所有者不一致。')
            if a['boss_damage']<0 or a['boss_threshold']!=math.ceil(owner['stats']['hp']*.12):raise ValueError('部位累计损伤存档无效。')
            if not a['boss_broken'] and a['pos']!=[owner['pos'][i]+a['offset'][i] for i in (0,1)]:raise ValueError('部位占格与核心脱离。')
    queued=[q['window'] for q in battle.get('boss_dialogue_queue',[])]
    if len(queued)!=len(set(queued)):raise ValueError('记忆窗口重复排队。')
    for q in battle.get('boss_dialogue_queue',[]):
        mem=battle.get('boss_memory',{}).get(q['boss'])
        if not mem or not mem['eligible'] or q['window'] not in (q['boss']+'-W1',q['boss']+'-W2') or q['window'] in mem['committed']:
            raise ValueError('记忆窗口存档无效。')
    for uid,r in battle.get('boss_receipts',{}).items():
        if battle['result']!='VICTORY' or r.get('battle_id')!=battle['battle_id']:raise ValueError('首领胜利回执缺少实际战斗结果。')
        if r.get('awakened') and not battle['boss_memory'].get(uid,{}).get('retained'):raise ValueError('觉醒回执缺少记忆选择。')
