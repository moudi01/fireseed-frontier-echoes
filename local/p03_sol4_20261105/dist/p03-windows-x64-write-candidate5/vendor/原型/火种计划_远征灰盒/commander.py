"""H07 Lu Heng: campaign commander; CMD remains an isolated legacy fixture."""
from copy import deepcopy
import combat as c
import veil

SOLDIERS = {'S01','S02','S03'}
KINDS = {'H07','CMD'}
NAME = '陆衡'
INTRO = '暮汀护运队的队正。陆衡关心的是把应召士兵带回来；他要求号令清楚、撤退有路，不要求队员为陌生人宣誓。'
PROFILE = dict(stats=dict(hp=48,physical_attack=8,magic_attack=0,healing_power=0,physical_defense=14,magic_defense=8),
               growth=dict(hp=6,physical_attack=1,magic_attack=0,healing_power=0,physical_defense=1,magic_defense=1),
               attack_type='physical',range=1,interval=3)


def install(catalog):
    """Runtime overlay; the frozen historical content files are not rewritten."""
    catalog.rules['hero_templates']['H07']=deepcopy(PROFILE)
    for item in catalog.gear.values():
        if item['family_id'] in ('EF02','EF07','EF08') and 'H07' not in item['allowed_unit_ids']:
            item['allowed_unit_ids'].append('H07')


def enabled(actor):return actor['kind'] in KINDS and actor.get('hero_enabled',True)

CARDS = [
    dict(move_id='CMD-A', name='指定突破', kind='command_mark', range=4, cooldown=4),
    dict(move_id='CMD-B', name='齐发号令', kind='command_volley', range=3, cooldown=5),
]
for card in CARDS:
    card.update(windup=1, cast_limit=None, first_eligible_tick=1)


def cards(): return deepcopy(CARDS)


def soldiers(owner, actors):
    return [a for a in actors if a['hp']>0 and a['side']==owner['side'] and a['kind'] in SOLDIERS and c.distance(a['pos'],owner['pos'])<=3]


def attackable(a, enemy, catalog, board, tick=0):
    from mechanics import front
    return (enemy['side']!=a['side'] and enemy['hp']>0 and c.distance(a['pos'],enemy['pos'])<=a['range']
            and c.visible(catalog,board,a['pos'],enemy['pos']) and veil.targetable(a,enemy,tick)
            and not (a['kind']=='S01' and a['stance']=='hold' and not front(a,enemy['pos'])))


def preferred(actor, foes, mark):
    target=mark['target'] if mark and actor['kind'] in SOLDIERS and actor['id'] in mark['members'] else None
    return sorted(foes,key=lambda b:(b['id']!=target,c.distance(actor['pos'],b['pos']),b['id']))


def damage_bonus(battle, actor, victim, action, tick):
    """The published roster gains direct damage only against its original mark."""
    mark=battle.get('command_mark')
    if (not mark or tick<mark.get('starts',0) or tick>mark['expires']
            or actor['kind'] not in SOLDIERS or actor['id'] not in mark['members']
            or victim['id']!=mark['target'] or victim['side']==actor['side']
            or action.get('kind')!='damage' or action.get('derived')):return 0
    owner=next((a for a in battle['actors'] if a['id']==mark['owner']),None)
    if not owner or owner['hp']<=0 or not enabled(owner) or owner['side']!=actor['side']:return 0
    return .5


def volley_candidates(owner, actors, mark, catalog, board, tick=0):
    # A soldier need not have a legal attack yet: it can wait within the token's
    # two response ticks. This preview never caps or freezes the release roster.
    return [a['id'] for a in sorted(soldiers(owner,actors),key=lambda a:(c.distance(owner['pos'],a['pos']),a['id']))
            if not a.get('command_token')]


def start_tick(battle, alive, tick, log):
    ids={a['id']:a for a in alive};mark=battle.get('command_mark')
    if mark and (mark['expires']<tick or mark['owner'] not in ids or mark['target'] not in ids):
        log('command_mark_end',target=mark['target']);battle['command_mark']=None
    for a in battle['actors']:
        token=a.get('command_token')
        if token and (token['expires']<tick or a['hp']<=0 or (battle.get('retreat_requested') and a['side']=='player')):
            log('command_token_lost',actor=a['id'],reason='expired' if token['expires']<tick else 'down_or_retreat')
            a['command_token']=None
        sources=[owner for owner in alive if enabled(owner) and a['hp']>0 and a in soldiers(owner,alive)]
        bonus=a['stats']['physical_attack']*35//100 if sources else 0
        reduction=.2 if sources else 0
        source=sources[0]['id'] if sources else None
        if bonus!=a.get('command_attack_bonus',0) or source!=a.get('command_attack_source') or reduction!=a.get('command_damage_reduction',0):
            log('command_aura',actor=a['id'],source=source,amount=bonus,damage_reduction=reduction)
        a['command_attack_bonus']=bonus;a['command_attack_source']=source
        a['command_damage_reduction']=reduction


def release(owner, action, battle, alive, tick, catalog, board, log):
    ids={a['id']:a for a in alive}
    if action['move_id']=='CMD-A':
        target=ids.get(action['target']);members=soldiers(owner,alive)
        if target and target['side']!=owner['side'] and target['hp']>0 and c.distance(owner['pos'],target['pos'])<=4 and c.visible(catalog,board,owner['pos'],target['pos']) and veil.targetable(owner,target,tick) and members:
            battle['command_mark']={'owner':owner['id'],'target':target['id'],'members':[a['id'] for a in members],'starts':tick,'expires':tick+3,'cast_id':action['id']}
            log('command_mark',**battle['command_mark'])
        else:log('skill_miss',actor=owner['id'],move='CMD-A',action_id=action['id'])
    elif action['move_id']=='CMD-B':
        granted=[]
        for a in sorted(soldiers(owner,alive),key=lambda a:a['id']):
            if a.get('command_token'):continue
            a['command_token']={'source':owner['id'],'cast_id':action['id'],'valid_from':tick+1,'expires':tick+2}
            granted.append(a['id'])
        log('command_grant',actor=owner['id'],cast_id=action['id'],members=granted,valid_from=tick+1,expires=tick+2)


def extra_actions(battle, alive, actions, moves, mark, tick, catalog, board, action_id, log):
    busy={a['id'] for a,_,_ in moves}|{a['id'] for a,act in actions if act['move_id']!='BASIC'}
    for a in alive:
        token=a.get('command_token')
        if not token or tick<token['valid_from'] or tick>token['expires'] or a['id'] in busy or a.get('pending'):continue
        stun=a.get('hero_stun')
        if (a['kind'] not in SOLDIERS or a['hp']<=0 or tick<a.get('active_from',1)
                or a.get('command_response_tick')==tick or tick<=a.get('stun_until',0)
                or (stun and stun.get('starts',0)<=tick<=stun['expires'])
                or (battle.get('retreat_requested') and a['side']=='player')):continue
        foes=preferred(a,[b for b in alive if attackable(a,b,catalog,board,tick)],mark)
        if not foes:continue
        # Spend before creating the independent action; it cannot feed another
        # response and never touches the soldier's ordinary attack timer.
        a['command_token']=None;a['command_response_tick']=tick
        victim=foes[0];aid=action_id(a)
        actions.append((a,{'id':aid,'move_id':'CMD-EXTRA','kind':'damage','target':victim['id'],'cells':[],
                          'coefficient':1.5,'damage_type':'physical','range':a['range'],'medium':a['medium'],
                          'max_targets':1,'origin':a['pos'][:],'command_cast':token['cast_id']}))
        a['command_responses']=a.get('command_responses',0)+1
        log('command_response',actor=a['id'],target=victim['id'],action_id=aid,cast_id=token['cast_id'])


def end_tick(battle, tick, log):
    ids={a['id'] for a in battle['actors'] if a['hp']>0}
    mark=battle.get('command_mark')
    if mark and (mark['expires']<=tick or mark['owner'] not in ids or mark['target'] not in ids):
        log('command_mark_end',target=mark['target']);battle['command_mark']=None
    for a in battle['actors']:
        token=a.get('command_token')
        if token and (token['expires']<=tick or a['hp']<=0):
            log('command_token_lost',actor=a['id'],reason='down' if a['hp']<=0 else 'expired')
            a['command_token']=None


def install_fixture(game):
    """Borrow H01's Lv2 numeric panel only; no named hero or recruitment adoption."""
    from balance_v062 import gear_modifiers
    cata=game.cat;base=cata.rules['hero_templates']['H01'];m=game.s['party'][0]
    stats={key:value+base['growth'][key] for key,value in base['stats'].items()}
    gear=cata.config['equipment_profiles']['Q1_CONTROL']['H01'][:]
    for gid in gear:
        for key,value in gear_modifiers(cata,gid,'CMD').items():stats[key]+=value
    m.update(unit_id='CMD',cost=4,stats=stats,hp=stats['hp'],gear=gear,attack_type=base['attack_type'],range=base['range'],interval=base['interval'],skill_mode='auto')
    import equipment
    game.s['gear_storage'].extend(m['gear_instances']);m['gear_instances']=[]
    for template in gear:equipment.issue(game,template,m['gear_instances'],{'kind':'commander_fixture','randomized':False})
    battle_cost=sum(row['cost'] for row in game.s['party'] if row['deployed'])
    expedition_cost=sum(row['cost'] for row in game.s['party'])
    game.s['budget']={**game.s['budget'],'battle':battle_cost,'expedition':max(expedition_cost,battle_cost+4)}
    game.s['team_id']='CMD';game.s['fixture_notice']+=' CMD测试位借H01 Lv2/Q1面板，仅借数值，不绑定洛恩人物或采用其技能；无正式获得节点。'
