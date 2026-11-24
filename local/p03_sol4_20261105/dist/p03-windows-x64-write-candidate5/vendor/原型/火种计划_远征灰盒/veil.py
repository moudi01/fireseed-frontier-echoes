"""Finite concealment and public projectile deflection, with snapshot targeting."""
from copy import deepcopy
import combat as c

CONCEAL='EN08-A'
DEFLECT={'EN09-A','EL05-A'}
BRIEFINGS={
    'EN08':'结雾：1拍起手、C7、2次；锁定自己及一名邻友，隐匿2拍。两格外不能新选中，靠近至2格可攻击；攻击起手／出手后显形。已锁格效果不取消，仍可近身；无额外闪避、免伤或灯光要求。',
    'EN09':'折光：1拍起手、C5、2次；公开一个空侧格，释放拍起2拍内偏转一次正面单体投射，无反伤。近击、范围、既已释放效果不受影响；无合法落点不启动，落点后来被占则不换格。',
    'EL05':'精英折光：3次，依次公开D4／D3／D5；释放拍末提交朝向，下一拍起防护2拍。每次只偏转一发正面单体投射，不在命中瞬间转面，无反伤，侧格失效不改落点。',
}


def install(cat):
    tags={'EN08':set(),'EN09':{'deflect'},'EL05':{'elite_behavior','deflect'}}
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
        if any(u['enemy_id'] in cat.elite_ids and u['enemy_id'] not in {'EL01','EL03','EL04','EL05','EL06'} for u in e['units']):completed.discard('elite_behavior')
        e['calibration_unsupported_mechanics']=[x for x in e.get('calibration_unsupported_mechanics',[]) if x not in completed]


def active(row,tick):return bool(row and row['starts']<=tick<=row['expires'])


def targetable(observer,target,tick,origin=None):
    if observer['side']==target['side'] or active(target.get('hero_exposed'),tick):return True
    row=target.get('conceal_view') if target.get('view_tick')==tick else target.get('concealment')
    return not active(row,tick) or c.distance(origin if origin is not None else observer['pos'],target['pos'])<=row['distance']


def conceal_targets(actor,card,alive,catalog,board):
    adjacent=[b for b in alive if b is not actor and b['side']==actor['side'] and not b.get('mechanism')
              and b['hp']>0 and c.distance(actor['pos'],b['pos'])<=card['range'] and c.visible(catalog,board,actor['pos'],b['pos'])]
    preferred=(actor.get('adaptation_rule') or {}).get('ally')
    return [actor]+sorted(adjacent,key=lambda b:(b['id']!=preferred,c.distance(actor['pos'],b['pos']),b['id']))[:card['max_targets']-1]


def side_cells(actor,facing):
    return [(actor['pos'][0]+c.DIRS[(facing+d)%6][0],actor['pos'][1]+c.DIRS[(facing+d)%6][1]) for d in (1,2,4,5)]


def valid_destination(actor,row,alive,catalog,board):
    pos=tuple(row['destination'])
    return (pos in side_cells(actor,row['facing']) and pos in board and catalog.terrain[board[pos]]['walkable']
            and not any(b['hp']>0 and tuple(b['pos'])==pos for b in alive))


def deflect_choice(actor,card,alive,catalog,board):
    index=actor['move_uses'].get(card['move_id'],0)
    facing=int(card['facing_sequence'][index][1:]) if card.get('facing_sequence') else actor['facing']
    candidates=[p for p in side_cells(actor,facing) if valid_destination(actor,{'destination':p,'facing':facing},alive,catalog,board)]
    return (min(candidates),facing) if candidates else None


def activate_deflect(actor,action,alive,catalog,board,tick,log):
    row={'destination':action['destination'],'facing':action['deflect_facing'],'origin':actor['pos'][:],
         'starts':tick,'expires':tick+action['duration_ticks']-1,'remaining':action['deflect_count'],'action_id':action['id']}
    if not valid_destination(actor,row,alive,catalog,board):
        log('deflect_failed',actor=actor['id'],action_id=action['id'],reason='invalid_public_destination');return
    actor['deflection']=row
    log('deflect_ready',actor=actor['id'],**row)


def start_tick(alive,catalog,board,tick,log):
    for a in alive:
        for key in ('concealment','deflection','hero_exposed'):
            if a.get(key) and a[key]['expires']<tick:
                log(key+'_expired',actor=a['id']);a[key]=None
    # Due defensive casts precede this tick's fresh targeting and releases.
    for a in alive:
        action=a['pending']
        if not action or action['due']>tick:continue
        if action['move_id']=='EN09-A':activate_deflect(a,action,alive,catalog,board,tick,log)
        if action['move_id']!=CONCEAL:continue
        for identity in action['targets']:
            b=next((b for b in alive if b['id']==identity),None)
            if not b or b.get('mechanism') or b['side']!=a['side'] or tick<b.get('active_from',1) or c.distance(a['pos'],b['pos'])>action['range'] or not c.visible(catalog,board,a['pos'],b['pos']):
                log('conceal_miss',actor=a['id'],target=identity,action_id=action['id']);continue
            row={'source':a['id'],'action_id':action['id'],'starts':tick,'expires':tick+action['duration_ticks']-1,
                 'distance':action['hides_only_if_distance_greater_than']}
            if not b.get('concealment') or b['concealment']['expires']<=row['expires']:b['concealment']=row
            log('conceal_ready',actor=a['id'],target=b['id'],starts=tick,expires=row['expires'])
    for a in alive:a['conceal_view']=deepcopy(a.get('concealment'));a['view_tick']=tick


def reveal_attacks(alive,actions,tick,log):
    attackers={a['id'] for a,act in actions if act['kind']=='damage'}
    attackers.update(a['id'] for a in alive if a['pending'] and a['pending']['kind']=='damage' and a['pending']['due']>tick)
    for a in alive:
        if a['id'] in attackers and active(a.get('concealment'),tick):
            a['concealment']=None;log('conceal_revealed',actor=a['id'],reason='attack')


def end_tick(actions,alive,catalog,board,tick,log):
    for a,action in actions:
        if action['move_id']!='EL05-A':continue
        a['facing']=action['deflect_facing']
        log('deflect_facing_committed',actor=a['id'],facing=a['facing'],valid_from=tick+1)
        activate_deflect(a,action,alive,catalog,board,tick+1,log)
    for a in alive:
        if a['hp']<=0:a['concealment']=None;a['conceal_view']=None;a['deflection']=None


def fixed_facing(actor,tick,proposed):
    row=actor.get('deflection')
    return row['facing'] if active(row,tick) else proposed


def deflect(attacker,victim,action,origin,alive,catalog,board,tick,front,log):
    row=victim.get('deflection')
    if not active(row,tick) or row['remaining']<=0:return False
    if action.get('already_released_effect') or action.get('released_tick',tick)<row['starts']:return False
    if action['medium']!='projectile' or action.get('max_targets',1)!=1 or action.get('area',False):return False
    # Bounded area cards remain areas even if only one victim stands inside.
    if action.get('shape','').startswith(('front_','public_','two_')):return False
    if not front({**victim,'facing':row['facing']},origin):return False
    if not valid_destination(victim,row,alive,catalog,board):
        log('deflect_unavailable',actor=victim['id'],action_id=action['id'],reason='public_destination_blocked');return False
    row['remaining']-=1
    log('projectile_deflected',actor=victim['id'],attacker=attacker['id'],action_id=action['id'],move=action['move_id'],
        destination=row['destination'],facing=row['facing'],remaining=row['remaining'])
    return True


def describe(battle):
    result=[]
    for a in battle['actors']:
        if a['hp']<=0:continue
        if active(a.get('concealment'),battle['tick']):result.append('结雾 '+a['id']+'：'+str(a['concealment']))
        if a.get('deflection') and a['deflection']['expires']>=battle['tick']:result.append('折光 '+a['id']+'：'+str(a['deflection']))
        if a['pending'] and a['pending']['move_id'] in DEFLECT:result.append('折光预告 '+a['id']+'：落点'+str(a['pending']['destination'])+' 朝向D'+str(a['pending']['deflect_facing']))
    return '\n'.join(result)
