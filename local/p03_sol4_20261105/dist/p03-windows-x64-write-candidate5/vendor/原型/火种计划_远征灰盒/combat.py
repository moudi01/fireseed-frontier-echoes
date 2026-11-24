"""Serializable, deterministic greybox combat; deliberately NOT balance-certified.

Hex movement, static terrain/LOS, cooldowns and simultaneous damage are real.
Authored moves, sixteen books, eight professions and ten hero kits execute; CMD remains a legacy fixture.
Every report retains that limitation even if the simulation reaches a victory.
"""
from copy import deepcopy
import math
import hashlib
import json
import gear_affixes as gear

DIRS = [(1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1)]
OMISSIONS = ['other_control_skills','full_affix_loot_pool']
SUPPORTED_PLANS = {f'PL{i:02}' for i in range(1,13)}
SUPPORTED_MOVES = {'EN01-A', 'EN02-A', 'EN03-A', 'EN04-A', 'EN06-A', 'EN12-A', 'EN13-A', 'EN17-A', 'EL03-A',
                   'EN14-A', 'EL06-A', 'EN15-A', 'EN05-A', 'EN16-A', 'EN18-A', 'EN07-A', 'EL04-B', 'EL01-B', 'EN08-A', 'EN09-A', 'EL05-A', 'EN10-A', 'EN11-A', 'EL02-A',
                   'M01-A', 'M02-A', 'M03-A', 'M04-A', 'CMD-A', 'CMD-B', 'RESCUE-SPEAR', 'RESCUE-SHIELD',
                   'EN19-A', 'EN20-A', 'EN21-A', 'EN22-A', 'EN23-A', 'EN24-A', 'EN24-B', 'EN25-A'} | {'SK-BK'+n for n in ('02','03','04','05','08','09','12')} | {f'H{i:02}-{s}' for i in (*range(1,7),8,9,10,11,12) for s in 'AB'} | {f'M{i:02}-A' for i in range(5,9)} | {'PET-H04-A'} | {u+'-'+s for u in ('BX01','BX02','BX03','MG01','MG02','MG03','MG04','DEMON','ADMIN') for s in ('AB' if u.startswith('BX') else 'ABC')}
SUPPORTED_MOVES.update({'DEMON-MIMIC','DEMON-D','ADMIN-D','C3-REAR-LOCK'})
from book_catalog import ACTIVE as BOOK_ACTIVES
SUPPORTED_MOVES.update('SK-'+bid for bid in BOOK_ACTIVES)


def distance(a, b):
    q, r = a[0] - b[0], a[1] - b[1]
    return max(abs(q), abs(r), abs(q + r))


def direction(a, b):
    return min(range(6), key=lambda i: (distance([a[0] + DIRS[i][0], a[1] + DIRS[i][1]], b), i))


def rounded_cube(q, r):
    vals = [q, -q-r, r]
    rounded = [math.floor(x + .5) if x >= 0 else math.ceil(x - .5) for x in vals]
    index = max(range(3), key=lambda i: (abs(vals[i] - rounded[i]), -i))
    rounded[index] = -sum(rounded[i] for i in range(3) if i != index)
    return (rounded[0], rounded[2])


def enemy_actor(e):
    basic = e['basic_attack']
    return {'id': e['instance_id'], 'kind': e['enemy_id'], 'name': e.get('name', e['enemy_id']), 'side': 'enemy', 'stats': deepcopy(e['stats']),
                   'adaptation_rule': deepcopy(e.get('adaptation_rule')),
                   'hp': e['stats']['hp'], 'pos': list(e['position']), 'facing': int(e.get('facing', 'D4')[1:]), 'stance': 'flank' if e['enemy_id']=='EN19' else 'advance',
                   'immune_movement_block': e.get('immune_movement_block', False), 'immune_stun':e.get('immune_stun',False),
                   'innate_life_steal': deepcopy(e.get('innate_life_steal')),
                   'range': basic['range'], 'interval': basic['attack_interval'],
                   'attack_type': basic['damage_type'], 'shield': 0, 'prep': [],
                   'medium': basic.get('medium', 'near'), 'moves': deepcopy(e.get('moves', [])),
                   'weak_point': deepcopy(e.get('weak_point', {})), 'mechanism':e.get('mechanism',False),
                   'raise_count':0, 'active_from':1,
                   **{k:deepcopy(e.get(k,[] if k in ('phases','boss_parts') else {} if k=='awakening' else None)) for k in ('phases','boss_parts','awakening','obsession_item_ref')}}


def initialize_actor(a):
    import heroes
    import bosses
    import roster_skills
    heroes.initialize(a)
    roster_skills.initialize(a)
    bosses.initialize(a)
    a.update(next_attack=1, pending=None, skill_used=0, stationary=0, move_pause_until=0, skill_ready=1, healing_first=True)
    a.update(anchor=a['pos'][:], root_until=0, weak_until=0, weak_from=0, move_uses={}, move_ready={}, action_sequence=0)
    a.update(basic_history=[], blocked_until=0, last_moved_tick=0, footing_used=False,
             armor_check_used=False, timed_shields=[])
    a.update(command_token=None, command_responses=0, command_attack_bonus=0, command_attack_source=None)
    a.update(affix_uses={},affix_last_tick={},gear_dodge=None)
    a.update(heat_charge=None,heat_exposure=None,completed_moves={},initial_side_step=None)
    a.update(concealment=None,conceal_view=None,view_tick=0,deflection=None)
    a.update(trigger_delay=None,trigger_delay_seen=0,deferred_start=None,petal_exposure=None,root_axis_base=None)
    a.update(steady_used=False,guard_uses=0,guard_last_tick=0,guard_ward=None)
    a.update(plan_uses={},plan_last={},standard_marks={},plan_crit=None,plan_dodge=None,strong_window=None,pursued_enemies={},last_basic_attempt=0)
    a.update(book_dodge=None,book_flanked=[],book_last_hit=0,book_guard_used=False)
    a.setdefault('books_equipped',[])
    a.setdefault('disabled_skills',[])
    a.setdefault('gear_instances',[])
    a.setdefault('moves', [])
    import battle_enrage
    battle_enrage.unlimited_sustain(a['moves'])
    a.setdefault('weak_point', {})
    a.setdefault('medium', 'projectile' if a['range'] > 1 else 'near')
    for p in a['prep']:
        if p['type'] == 'next_battle_private_shield': a['shield'] += p['amount']
    import boss_mimic
    boss_mimic.initialize(a)
    import book_combat
    book_combat.initialize(a)


def create(catalog, encounter, board_id, party, seed, plans, preparations, boss_context=None):
    from balance_v062 import enemy_for
    encounter=enemy_for(catalog,encounter,level=encounter.get('effective_threat'))
    if len(plans)>3 or len(plans)!=len(set(plans)) or not set(plans)<=SUPPORTED_PLANS:raise ValueError('方案最多3项、不得重复且必须已接入。')
    from battle_skills import core_cards
    import skill_books
    import heroes
    import commander
    gear.validate_party(catalog,party)
    if sum(m['deployed'] and m['unit_id'] in commander.KINDS for m in party)>1:
        raise ValueError('同场只能部署一名专职指挥英雄；旧CMD测试位不能与陆衡叠加。')
    deployed_kinds=[m['unit_id'] for m in party if m['deployed']]
    if any(deployed_kinds.count(uid)>1 for uid in heroes.IDS | {'PET-H04'}):raise ValueError('同一英雄或伴兽不能重复部署。')
    actors = []
    for m in party:
        if not m['deployed']: continue
        skill_books.validate_member(m)
        a = {'id': m['instance_id'], 'kind': m['unit_id'], 'side': 'player', 'cost':m['cost'], 'stats': deepcopy(m['stats']),
             'hp': m['hp'], 'pos': list(m['position']), 'facing': m['facing'], 'stance': m['stance'],
             'range': m['range'], 'interval': m['interval'], 'attack_type': m['attack_type'], 'shield': 0,
             'prep': deepcopy(preparations.get(m['instance_id'], [])),
             'gear_instances':deepcopy(m.get('gear_instances',[])),
             'hero_options':deepcopy(m.get('hero_options',{})), 'hero_enabled':m.get('hero_enabled',True),
             'books_equipped':deepcopy(m.get('books_equipped',[])), 'disabled_skills':deepcopy(m.get('disabled_skills',[])),
             'main_attack':m.get('main_attack','AUTO'),
             'basic_medium': 'near' if skill_books.capabilities(m)['near'] else 'projectile' if skill_books.capabilities(m)['projectile'] else 'spell',
             **({'medium':m['basic_medium']} if 'basic_medium' in m else {}),
             'moves': skill_books.cards(m,commander.cards() if m['unit_id']=='CMD' else core_cards(m['unit_id'])), 'skill_mode': m.get('skill_mode', 'counter' if m['unit_id']=='M04' else 'auto')}
        actors.append(a)
    import necromancy
    import reinforcements
    necromancy.validate(encounter)
    reinforcements.validate(encounter)
    actors.extend(enemy_actor(e) for e in encounter['units']+encounter.get('mechanisms',[]))
    import bosses
    for a in actors: initialize_actor(a)
    bosses.attach_parts(actors,encounter)
    board = catalog.boards[board_id]
    walkable = {(c['q'],c['r']) for c in board['cells'] if catalog.terrain[c['terrain_id']]['walkable']}
    positions = [tuple(a['pos']) for a in actors]
    if len(set(positions)) != len(positions) or any(p not in walkable for p in positions):
        raise ValueError('棋盘部署重叠、越界或落在不可走格：'+encounter['encounter_id'])
    if 'PL01' in plans:
        guards = sorted([a for a in actors if a['hp']>0 and a['side'] == 'player' and a['kind'] in ['S01', 'M01', 'H01', 'M05']],key=lambda a:a['id'])
        if guards:
            guard = guards[0]; guard['shield'] += 12
            neighbors = sorted([a for a in actors if a['hp']>0 and a['side'] == 'player' and a != guard and distance(a['pos'], guard['pos']) == 1],key=lambda a:a['id'])
            if neighbors: neighbors[0]['shield'] += 12
    if 'PL02' in plans:
        for a in actors:
            if a['hp']>0 and a['side'] == 'player' and not any(b['hp']>0 and b != a and b['side'] == a['side'] and distance(a['pos'], b['pos']) == 1 for b in actors):
                a['shield'] += 8
    battle_id=hashlib.sha256(json.dumps([encounter,board_id,party,seed,plans,preparations],ensure_ascii=False,sort_keys=True).encode('utf8')).hexdigest()[:24]
    result = {'tick': 0, 'result': None, 'seed': seed, 'board_id': board_id, 'encounter_id': encounter['encounter_id'], 'battle_id':battle_id,
            'effective_threat': encounter.get('effective_threat'),
            'growth_rule_version': encounter.get('growth_rule_version'),
            'growth_scope': encounter.get('growth_scope', 'FIXED_ENCOUNTER'),
            'spawn_options_snapshot': deepcopy(encounter.get('spawn_options', [])),
            'necromancy': deepcopy(encounter.get('necromancy', {})),
            'reinforcements': deepcopy(encounter.get('reinforcements', {})),
            'closed_edge':None, 'edge_reservation':None,
            'plan_sequence':0,'plan_queue':[],'mark_reserved':[],'cast_windows':{},'plan_delay_uses':0,'plan_delay_tick':0,
            'actors': actors, 'events': [], 'plans': plans[:], 'no_change': 0, 'shared_shields': [], 'command_mark':None,
            'geometry_version': board['geometry_version'], 'board_cells': deepcopy(board['cells']),
            'measurement_class': 'GREYBOX_APPROXIMATION', 'balance_eligible': False,
            'omissions': sorted(set(OMISSIONS + encounter.get('calibration_unsupported_mechanics', []))),
            'before': deepcopy(party)}
    bosses.prepare(result,boss_context)
    import learning
    learning.prepare_battle(catalog,result,encounter)
    import boss_threats
    boss_threats.initialize(result,entry_tick=0,catalog=catalog)
    import expedition_peril
    expedition_peril.initialize(result,encounter)
    import battle_enrage
    battle_enrage.initialize(result)
    return result


def stat(a, name, tick):
    value = a['stats'][name]
    if name=='physical_attack':value+=a.get('command_attack_bonus',0)
    for p in a['prep']:
        if p['type'] == 'next_battle_stat_buff' and p['stat'] == name and tick <= p['duration_ticks']: value += p['flat']
    if name in ('physical_defense','magic_defense'):
        value=max(0,value+a.get('town_defense_bonus',0)-gear.defense_penalty(a)+a.get('boss_rule',{}).get(name+'_offset',0))
    import book_combat
    return book_combat.stat(a,name,value,tick)


def has_uses(actor,card):
    limit=card.get('cast_limit')
    return limit is None or actor['move_uses'].get(card['move_id'],0)<limit


def cells(catalog, battle):
    return {(c['q'], c['r']): c['terrain_id'] for c in catalog.boards[battle['board_id']]['cells']}


def enter_shallow(actor,terrain,tick,log):
    """Apply terrain recovery only after movement has actually landed.

    A wading preparation waives this entry's shallow-water pause, never an
    existing pause or a later independent equipment movement penalty.
    """
    if terrain!='SHALLOW_WATER':return
    wade=next((p for p in actor['prep']
               if p['type']=='next_battle_shallow_recovery_waiver' and p.get('charges',0)>0),None)
    if wade:
        wade['charges']-=1
        log('shallow_waiver_used',actor=actor['id'],position=actor['pos'][:],remaining=wade['charges'],
            preserved_pause_until=actor['move_pause_until'])
    else:actor['move_pause_until']=max(actor['move_pause_until'],tick+1)


def visible(catalog, board, a, b, penetration=0):
    n = distance(a, b)
    if not n: return True
    allowance = max(penetration, int(board.get(tuple(a)) == 'HIGH_GROUND' or board.get(tuple(b)) == 'HIGH_GROUND'))
    low = set()
    for i in range(1, n):
        c = rounded_cube(a[0] + (b[0]-a[0])*i/n, a[1] + (b[1]-a[1])*i/n)
        terrain = board.get(c, 'HIGH_OBSTACLE')
        if terrain == 'HIGH_OBSTACLE': return False
        if terrain == 'LOW_OBSTACLE': low.add(c)
    return len(low) <= allowance


def step(catalog, battle):
    from mechanics import step as execute_tick
    execute_tick(catalog, battle)
