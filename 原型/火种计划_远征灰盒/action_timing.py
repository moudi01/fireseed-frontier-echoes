"""Petal exposure, one future-start delay, and alternating root lanes."""
import combat as c

PETAL='EN10-A'
DELAY='EN11-A'
ROOT='EL02-A'
BRIEFINGS={
    'EN10':'落蕊：2拍起手、射程3、1.1物理，锁定两相邻格、最多2人，C6／2次。释放后下一拍物防−6（不限受击方向）；无飞行或持续地伤，预警不追踪。',
    'EN11':'噤纹：1拍起手、射程3、C5／2次；对未在起手且仍有已启用主动的目标施加3拍印记。下一次合法主动起手延后1拍，不预扣次数；普攻、移动、撤退照常。每目标每场最多承受一次，过期不续、不改已起手动作。',
    'EL02':'双囊收根：1拍起手、射程2、1.2物理、最多1人，C5／2次。首条轴线固定基准，第二次转相邻一轴，只公开一条两格线；空线不追踪。释放后自身定根2拍，侧后物防−4。',
}


class DeferredStart(Exception):
    """Skip active selection for this tick, then allow ordinary behavior."""


def install(cat):
    tags={'EN10':set(),'EN11':{'trigger_delay'},'EL02':{'elite_behavior'}}
    for uid,text in BRIEFINGS.items():
        cat.enemy_templates[uid]['briefing']=text
        cat.enemy_templates[uid]['calibration_unsupported_mechanics']=[x for x in cat.enemy_templates[uid].get('calibration_unsupported_mechanics',[]) if x not in tags[uid]]
    for e in cat.encounters.values():
        completed=set()
        for u in e['units']:
            uid=u['enemy_id']
            if uid not in BRIEFINGS:continue
            u['briefing']=BRIEFINGS[uid];completed.update(tags[uid])
            u['calibration_unsupported_mechanics']=[x for x in u.get('calibration_unsupported_mechanics',[]) if x not in tags[uid]]
        e['calibration_unsupported_mechanics']=[x for x in e.get('calibration_unsupported_mechanics',[]) if x not in completed]


def has_active(actor):
    mode=actor.get('skill_mode','auto')
    if mode=='off':return False
    if actor['kind'] in ('S02','S03') and not actor['skill_used']:return True
    return any(card['move_id'] in c.SUPPORTED_MOVES and (card.get('cast_limit') is None or actor['move_uses'].get(card['move_id'],0)<card['cast_limit'])
               and not (actor['kind']=='CMD' and mode in ('mark','volley') and card['move_id']!=('CMD-A' if mode=='mark' else 'CMD-B'))
               for card in actor['moves'])


def eligible(actor,tick):
    return (actor['hp']>0 and tick>=actor.get('active_from',1) and not actor.get('mechanism')
            and not actor['pending'] and not actor.get('trigger_delay_seen',0) and has_active(actor))


def start_tick(alive,catalog,board,tick,log):
    for a in alive:
        row=a.get('trigger_delay')
        if row and row['expires']<tick:
            a['trigger_delay']=None;log('trigger_delay_expired',actor=a['id'],source=row['source'])
        if a.get('petal_exposure') and a['petal_exposure']['expires']<tick:a['petal_exposure']=None
    for a in alive:
        action=a['pending']
        if not action or action['move_id']!=DELAY or action['due']>tick:continue
        victim=next((b for b in alive if b['id']==action['target']),None)
        if not victim or victim['side']==a['side'] or not eligible(victim,tick) or c.distance(a['pos'],victim['pos'])>action['range'] or not c.visible(catalog,board,a['pos'],victim['pos']):
            log('trigger_delay_failed',actor=a['id'],target=action['target'],action_id=action['id']);continue
        victim['trigger_delay_seen']+=1
        victim['trigger_delay']={'source':a['id'],'action_id':action['id'],'starts':tick,'expires':tick+action['duration_ticks']-1,'delay':action['delay_ticks']}
        log('trigger_delay_ready',actor=a['id'],target=victim['id'],expires=victim['trigger_delay']['expires'],action_id=action['id'])
    # Selection eligibility uses the same start-of-tick snapshot for both ID orders.
    return {a['id'] for a in alive if eligible(a,tick)}


def choose_delay(actor,card,foes,battle,catalog,board,eligible_ids):
    reserved={a['pending']['target'] for a in battle['actors'] if a['hp']>0 and a['pending'] and a['pending']['move_id']==DELAY}
    rows=[a for a in foes if a['id'] in eligible_ids and a['id'] not in reserved and c.distance(actor['pos'],a['pos'])<=card['range'] and c.visible(catalog,board,actor['pos'],a['pos'])]
    return min(rows,key=lambda a:(c.distance(actor['pos'],a['pos']),a['id'])) if rows else None


def before_begin(actor,card,tick,log,on_defer=None):
    deferred=actor.get('deferred_start')
    if deferred and tick<deferred['until']:raise DeferredStart()
    row=actor.get('trigger_delay')
    if row and row['starts']<=tick<=row['expires']:
        actor['trigger_delay']=None
        actor['deferred_start']={'source':row['source'],'action_id':row['action_id'],'attempted_move':card['move_id'],'until':tick+row['delay']}
        log('active_start_deferred',actor=actor['id'],move=card['move_id'],**actor['deferred_start'])
        if on_defer:on_defer(row['source'])
        raise DeferredStart()
    actor['deferred_start']=None
    return deferred


def root_choice(actor,card,foes,catalog,board):
    from mechanics import line
    index=actor['move_uses'].get(ROOT,0);base=actor.get('root_axis_base')
    for victim in sorted(foes,key=lambda a:(c.distance(actor['pos'],a['pos']),a['id'])):
        if c.distance(actor['pos'],victim['pos'])>card['range'] or not c.visible(catalog,board,actor['pos'],victim['pos']):continue
        initial=c.direction(actor['pos'],victim['pos']) if base is None else base
        facing=(initial+card['axis_offset_sequence'][index])%6
        cells=line(actor['pos'],facing,card['range'])
        if base is None and tuple(victim['pos']) not in cells:continue
        if all(p in board and catalog.terrain[board[p]]['walkable'] and c.visible(catalog,board,actor['pos'],p) for p in cells):return victim,cells,facing,initial
    return None


def released(actor,action,tick,log):
    if action['move_id']!=PETAL:return
    row=action['after_release_exposure']
    actor['petal_exposure']={'starts':tick+1,'expires':tick+row['duration_ticks'],'modifier':row['physical_defense_modifier']}
    log('petal_exposure',actor=actor['id'],**actor['petal_exposure'])


def defense_modifier(actor,dtype,tick):
    row=actor.get('petal_exposure')
    return row['modifier'] if dtype=='physical' and row and row['starts']<=tick<=row['expires'] else 0


def describe(battle):
    result=[]
    for a in battle['actors']:
        if a['hp']<=0:continue
        if a.get('trigger_delay'):result.append('噤纹印记 '+a['id']+'：'+str(a['trigger_delay']))
        if a.get('deferred_start'):result.append('主动起手延后 '+a['id']+'：'+str(a['deferred_start']))
        if a.get('petal_exposure'):result.append('落蕊物防窗口 '+a['id']+'：'+str(a['petal_exposure']))
        if a['kind']=='EL02':result.append('双囊轴线 '+a['id']+'：基准'+str(a.get('root_axis_base'))+' 已用'+str(a['move_uses'].get(ROOT,0)))
    return '\n'.join(result)
