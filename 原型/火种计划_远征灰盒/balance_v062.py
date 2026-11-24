"""COST-REBASE-1.0 runtime overlay; historical JSON and saves stay immutable.

Install after every content installer. Fixed gear panels use a Cost4 reference;
gear_modifiers is the sole wearer-dependent panel adapter. Enemy rebasing reads
only authored content and public threat level, never a party or its equipment.
"""
from copy import deepcopy
from math import ceil

VERSION = 'COST-BALANCE-0.62'
STAT_KEYS = ('hp', 'physical_attack', 'magic_attack', 'healing_power',
             'physical_defense', 'magic_defense')


def six(*values):
    return dict(zip(STAT_KEYS, values))


# Exact final COST-REBASE-1.0 table, including the final M04/M07 ranges.
ROWS = {
    'S01': (([32,40],[5,7],[0,0],[0,0],[18,22],[8,12]), (5,1,0,0,1,1), 'physical',1,2),
    'S02': (([24,30],[6,8],[0,0],[0,0],[6,10],[2,6]), (4,1,0,0,1,0), 'physical',1,2),
    'S03': (([18,24],[6,8],[0,0],[0,0],[0,4],[2,6]), (3,1,0,0,0,1), 'physical',4,2),
    'M01': (([60,72],[12,16],[0,0],[0,0],[16,20],[8,12]), (8,2,0,0,1,1), 'physical',2,2),
    'M02': (([38,46],[5,7],[0,0],[14,18],[4,8],[10,14]), (6,1,0,2,0,1), 'physical',2,2),
    'M03': (([38,46],[16,20],[0,0],[0,0],[4,8],[2,6]), (5,3,0,0,1,0), 'physical',3,3),
    'M04': (([34,42],[1,3],[12,14],[3,5],[4,8],[8,12]), (5,0,2,1,0,1), 'magic',3,2),
    'M05': (([56,68],[7,11],[0,0],[0,0],[14,18],[10,14]), (8,2,0,0,1,1), 'physical',1,3),
    'M06': (([42,50],[12,16],[0,0],[0,0],[6,10],[4,8]), (7,2,0,0,1,0), 'physical',1,2),
    'M07': (([34,42],[2,4],[14,18],[3,5],[4,8],[10,14]), (5,0,3,1,0,1), 'magic',3,3),
    'M08': (([50,60],[2,4],[13,17],[0,0],[10,14],[12,16]), (7,0,3,0,1,1), 'magic',1,3),
}

BUDGETS = (
    {'milestone':'ST-101', 'battle':6, 'expedition':8},
    {'milestone':'ST-104', 'battle':8, 'expedition':12},
    {'milestone':'CH2_COMPLETE', 'battle':12, 'expedition':16},
    {'milestone':'CH3_COMPLETE', 'battle':16, 'expedition':20},
    {'milestone':'FINALE_READY', 'battle':20, 'expedition':24},
)

PASSIVES = {'M02-P':6, 'M03-P':6, 'M04-P':8, 'M05-P':8,
            'M06-P':.35, 'M07-P':10, 'M08-P':10}
CORE_PATCHES = {
    'M01': {'coefficient':1.5},
    'M02': {'heal_base':10, 'healing_power_coefficient':1.5},
    'M03': {'coefficient':1.6},
    'M04': {'coefficient':1.4},
    'M05': {'shield':24},
    'M07': {'kind':'damage', 'damage_type':'magic', 'coefficient':1.0,
            'mark_after_damage':True},
    'M08': {'coefficient':1.6},
}

# Q1/Q2/Q3 panels at Cost4. All positive values are divisible by four so
# Cost1/2/4 users retain the same per-Cost total without fractional base stats.
GEAR_PANELS = {
    'EF01': ({'physical_attack':4}, {'physical_attack':8}, {'physical_attack':12}),
    'EF02': ({'hp':8,'physical_attack':4}, {'hp':12,'physical_attack':8}, {'hp':16,'physical_attack':12}),
    'EF03': ({'physical_attack':4}, {'physical_attack':8}, {'physical_attack':12}),
    'EF04': ({'magic_attack':4}, {'magic_attack':8}, {'magic_attack':12}),
    'EF05': ({'hp':4,'healing_power':4}, {'hp':8,'healing_power':8}, {'hp':12,'healing_power':12}),
    'EF06': ({'physical_defense':4,'magic_defense':4}, {'physical_defense':8,'magic_defense':4}, {'physical_defense':12,'magic_defense':8}),
    'EF07': ({'hp':8,'physical_defense':4}, {'hp':16,'physical_defense':8}, {'hp':24,'physical_defense':12}),
    'EF08': ({'hp':8,'magic_defense':4}, {'hp':16,'magic_defense':8}, {'hp':24,'magic_defense':12}),
}

# Additional content rebase after the existing deterministic route-depth curve.
# L1/2 = early, L3/4 = middle, L5+ = late. Long routes have no extra multiplier:
# their already-public increasing threat levels are the only route scaling.
ENEMY_PERCENT = {
    'hp': (75,85,95,110,120),
    'attack': (90,95,100,105,110),
    'defense': (85,90,100,105,110),
}
FIXED_LEVELS = {'BX01':3, 'BX02':4, 'BX03':4, 'MG01':3, 'MG02':3,
                'MG03':5, 'MG04':5, 'DEMON':5, 'ADMIN':5}


def unit_cost(member_or_uid):
    if isinstance(member_or_uid, dict):
        uid = member_or_uid.get('unit_id', member_or_uid.get('kind', member_or_uid.get('id')))
    else:
        uid = member_or_uid
    if uid == 'PET-H04' or isinstance(uid,str) and uid.startswith('S'):
        return 1
    if isinstance(uid,str) and uid.startswith('M'):
        return 2
    if uid == 'CMD' or isinstance(uid,str) and uid.startswith('H'):
        return 4
    raise ValueError('无法确定人员Cost：'+str(uid))


def budget_for(facts):
    known = set(facts or ())
    if 'CH1_COMPLETE' in known:
        known.add('ST-104')
    available = [row for row in BUDGETS if row['milestone'] in known]
    return deepcopy(available[-1] if available else BUDGETS[0])


def passive_value(key, default=None):
    """Only numeric values; callers retain the original finite trigger guards."""
    return PASSIVES.get(key, default)


def gear_modifiers(catalog, item_or_template, member_or_uid):
    """Pure effective fixed panel. Never edits an item, affix or its owner.

    Pass the real instance dict or its template ID. Instance-specific affix
    effects remain separate and must not be folded into this fixed panel.
    """
    tid = item_or_template['template_id'] if isinstance(item_or_template,dict) else item_or_template
    base = catalog.gear[tid]
    cost = unit_cost(member_or_uid)
    values = base['stat_modifiers']
    reference = base.get('panel_reference_cost')
    if reference is None:
        return deepcopy(values)  # Explicit compatibility for a pre-overlay catalog.
    return {key: int(values.get(key,0)*cost/reference) for key in STAT_KEYS}


def _level(catalog, encounter, level, region_id):
    fixed = [FIXED_LEVELS[u['enemy_id']] for u in encounter.get('units',[])
             if u.get('enemy_id') in FIXED_LEVELS]
    if fixed:
        return max(fixed)
    if level is not None:
        if type(level) is not int or level < 1:
            raise ValueError('敌人数值威胁必须为正整数。')
        return level
    if encounter.get('effective_threat'):
        return int(encounter['effective_threat'])
    if region_id in catalog.regions:
        return int(catalog.regions[region_id]['threat_rank_id'][2:])
    rank = encounter.get('threat_rank_id','TH1')
    return int(rank[2:]) if isinstance(rank,str) and rank.startswith('TH') else 1


def _rebased_stats(base, level):
    index = min(level,5)-1
    result = deepcopy(base)
    for key in STAT_KEYS:
        value = base.get(key,0)
        group = 'hp' if key == 'hp' else 'defense' if key.endswith('_defense') else 'attack'
        percent = ENEMY_PERCENT[group][index]
        result[key] = ceil(value*percent/100) if key == 'hp' else value*percent//100
        if value > 0 and key in ('physical_attack','magic_attack'):
            result[key] = max(1,result[key])
    return result


def enemy_for(catalog, encounter, level=None, region_id=None, profile=None):
    """Return one rebased encounter, safe before/after depth and on repeat calls.

    Normal route payloads marked ROUTE_DEPTH rebuild from the original unscaled
    template through the existing public depth policy, then apply this rebase
    once. Fixed/story encounters retain their authored per-instance statistics
    as the source and use their fixed content stage. Profile is recorded for
    auditing only: SHORT/MEDIUM/LONG do not silently add a second difficulty tax.
    """
    result = deepcopy(encounter)
    threat = _level(catalog,result,level,region_id)
    context = {'version':VERSION, 'level':threat, 'region_id':region_id, 'profile':profile}
    applied = result.get('balance_rebase',{})
    # Context strings do not change difficulty. In particular, re-entering the
    # final battle boundary must not erase a learning/adaptation patch applied
    # after region freeze. A true depth rebuild invalidates this marker first.
    if applied.get('version') == VERSION and applied.get('level') == threat:
        return result
    source_templates = getattr(catalog,'_balance_enemy_sources',catalog.enemy_templates)
    fixed = any(u.get('enemy_id') in FIXED_LEVELS or
                catalog.enemy_templates.get(u.get('enemy_id'),{}).get('stats_are_fixed_for_story_battle')
                for u in result.get('units',[]))
    routed = not fixed and result.get('growth_scope') == 'ROUTE_DEPTH'
    for group in ('units','spawn_options','mechanisms'):
        for unit in result.get(group,[]):
            if 'stats' not in unit:
                continue
            source = deepcopy(unit.get('balance_source_stats',unit['stats']))
            unit.setdefault('balance_source_stats',deepcopy(source))
            if routed and group != 'mechanisms' and unit.get('enemy_id') in source_templates:
                from depth_growth import scaled_stats, policy
                template = source_templates[unit['enemy_id']]
                base_id = template.get('base_enemy_id',unit['enemy_id'])
                base = source_templates.get(base_id,template)['stats']
                elite = group != 'spawn_options' and (unit['enemy_id'] in catalog.elite_ids or unit.get('elite_promoted',False))
                source = scaled_stats(base,threat,policy(catalog),elite)
            unit['stats'] = _rebased_stats(source,threat)
            unit['balance_rebase'] = deepcopy(context)
    result['balance_rebase'] = context
    return result


def install(catalog):
    """Idempotent last-stage install; never writes frozen files or saved actors."""
    catalog.rules['party'].update(roster_cap=None,expedition=None,deployment=None)
    catalog.rules['unit_types']['hero']['cost']=4
    bases = {row['id']:row for row in catalog.rules['units'].values()}
    bases.update(catalog.rules['mercenaries'])
    for uid,(ranges,growth,damage_type,distance,interval) in ROWS.items():
        base = bases[uid]
        base.update(ranges=deepcopy(six(*ranges)),growth=six(*growth),
                    attack_type=damage_type,range=distance,interval=interval,cost=unit_cost(uid))
        if uid == 'M01':
            base['basic_medium'] = 'near'  # Preserve the existing long-spear medium.
    for uid,base in catalog.rules['hero_templates'].items():
        base['cost'] = unit_cost(uid)
    if 'companion_template' in catalog.rules:
        catalog.rules['companion_template']['cost'] = 1
    catalog.rules['command_budgets'] = deepcopy(list(BUDGETS))
    import battle_skills, roster_skills
    for uid,patch in CORE_PATCHES.items():
        battle_skills.CORE[uid].update(deepcopy(patch))
        if uid in roster_skills.MERC_CARDS:
            roster_skills.MERC_CARDS[uid].update(deepcopy(patch))
    for uid in ROWS:
        if uid.startswith('M'):
            battle_skills.CORE[uid].update(windup=1,cast_limit=2)
    for tid,base in catalog.gear.items():
        family = base.get('family_id',tid[:4])
        if family not in GEAR_PANELS:
            continue
        base.setdefault('legacy_stat_modifiers',deepcopy(base['stat_modifiers']))
        quality = int(base['quality_id'][1:])-1
        panel = GEAR_PANELS[family][quality]
        base.update(stat_modifiers={key:panel.get(key,0) for key in STAT_KEYS},
                    panel_reference_cost=4,panel_balance_version=VERSION)
    # Preserve authored sources only. Actual scaling is deliberately performed at
    # the final encounter freeze/entry boundary so route growth cannot erase it.
    if not hasattr(catalog,'_balance_enemy_sources'):
        catalog._balance_enemy_sources = deepcopy(catalog.enemy_templates)
    for template in catalog.enemy_templates.values():
        template['balance_policy'] = VERSION
    for encounter in catalog.encounters.values():
        encounter['balance_policy'] = VERSION
        for group in ('units','spawn_options','mechanisms'):
            for unit in encounter.get(group,[]):
                if 'stats' in unit:
                    unit.setdefault('balance_source_stats',deepcopy(unit['stats']))
    catalog.balance_v062 = {'version':VERSION,'costs':{'soldier':1,'mercenary':2,'hero':4,'pet':1},
                           'headcount_caps':None,'gear_reference_cost':4,
                           'enemy_percent':deepcopy(ENEMY_PERCENT),'enemy_scales_by_party':False}

