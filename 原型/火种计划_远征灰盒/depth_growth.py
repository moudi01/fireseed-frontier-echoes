"""DEPTH-GROWTH-1.0: deterministic route growth, never party-based scaling."""
from copy import deepcopy

VERSION = 'DEPTH-GROWTH-1.0'
# Integer percentages avoid ceil(100 * 1.1) == 111 floating-point surprises.
HP = (100, 120, 140, 165, 190)
ATTACK = (100, 110, 125, 140, 155)


def policy(catalog):
    return {'version': VERSION, 'scale_by_party': False, 'scale_by_route_depth': True,
            'native_minimum': {rid: int(r['threat_rank_id'][2:]) for rid, r in catalog.regions.items()},
            'hp_percent': list(HP), 'attack_percent': list(ATTACK),
            'hp_step_after_5': 25, 'attack_step_after_5': 15, 'defense_step': 2}


def next_level(rules, rid, previous=None):
    native = rules['native_minimum'][rid]
    floor=max(rules.get('tier_floor',1),rules.get('stage_floor',1))
    return max(native,floor) if previous is None else max(native, previous + 1,floor)


def path_levels(rules, path):
    levels = []
    for rid in path:
        levels.append(next_level(rules, rid, levels[-1] if levels else None))
    return levels


def scaled_stats(base, level, rules, elite=False):
    if type(level) is not int or level < 1:
        raise ValueError('有效威胁必须为正整数。')
    hp = rules['hp_percent'][min(level, 5)-1] + max(0, level-5)*rules['hp_step_after_5']
    attack = rules['attack_percent'][min(level, 5)-1] + max(0, level-5)*rules['attack_step_after_5']
    stats = deepcopy(base)
    stats['hp'] = (base['hp']*hp + 99)//100
    if elite:
        stats['hp'] = (stats['hp']*5 + 3)//4
    for key in ('physical_attack', 'magic_attack'):
        stats[key] = base[key]*attack//100
    for key in ('physical_defense', 'magic_defense'):
        stats[key] = base[key] + rules['defense_step']*(level-1)
    return stats


def scale_unit(catalog, unit, level, rules, summoned=False):
    result = deepcopy(unit)
    template = catalog.enemy_templates[unit['enemy_id']]
    if template.get('stats_are_fixed_for_story_battle'):
        result['growth_scope'] = 'FIXED_STORY'
        return result
    base_id = template.get('base_enemy_id', unit['enemy_id'])
    elite = not summoned and (unit['enemy_id'] in catalog.elite_ids or unit.get('elite_promoted', False))
    result['stats'] = scaled_stats(catalog.enemy_templates[base_id]['stats'], level, rules, elite)
    result.update(effective_threat=level, growth_base_id=base_id, growth_elite=elite,
                  growth_scope='ROUTE_DEPTH')
    return result


def encounter(catalog, source, level, rules):
    result = deepcopy(source)
    # Fixed story encounters, including their escorts, retain their authored values.
    fixed = any(catalog.enemy_templates[u['enemy_id']].get('stats_are_fixed_for_story_battle')
                for u in source['units'])
    if fixed:
        result['growth_scope'] = 'FIXED_STORY'
        return result
    # Only route-depth encounters rebuild their stats. Fixed payloads must keep
    # the normalization marker so actor initialization preserves later boss and
    # adaptation changes instead of rebuilding from balance_source_stats.
    result.pop('balance_rebase',None)
    result.pop('contract_pressure',None)
    result['units'] = [scale_unit(catalog, u, level, rules) for u in source['units']]
    if 'spawn_options' in source:
        result['spawn_options'] = [scale_unit(catalog, u, level, rules, summoned=True)
                                   for u in source['spawn_options']]
    result.update(effective_threat=level, growth_rule_version=rules['version'], growth_scope='ROUTE_DEPTH')
    # threat_rank_id continues to identify the authored pool; budgets and rewards are untouched.
    from balance_v062 import enemy_for
    from late_pressure import route_encounter
    return route_encounter(enemy_for(catalog,result,level=level),rules)


def freeze_region(game, rid):
    from late_pressure import gate_source
    rules = game.s['manifest']['depth_growth']
    previous = (game.s['regions'][game.s['visited_regions'][-1]]['growth']['effective_threat']
                if game.s['visited_regions'] else None)
    level = next_level(rules, rid, previous)
    result = {'rule_version': rules['version'], 'region_index': len(game.s['visited_regions'])+1,
              'previous_threat': previous, 'native_minimum': rules['native_minimum'][rid],
              'effective_threat': level, 'stage_floor':rules.get('stage_floor',1),
              'progression_pressure':deepcopy(rules.get('progression_pressure')), 'encounters': {}}
    for slot, binding in game.s['manifest']['regions'][rid]['encounters'].items():
        ids = set(binding.get('candidate_ids', []))
        ids.update(binding[k] for k in ('encounter_id', 'default_encounter_id') if k in binding)
        frozen={}
        for eid in sorted(ids):
            source=game.cat.encounter_for_board(eid,binding['board_id'])
            if game.s.get('mission')=='ORDINARY':
                source=gate_source(game.cat,source,binding['board_id'],level,rules,slot)
            frozen[eid]=encounter(game.cat,source,level,rules)
        result['encounters'][slot]=frozen
    return result


def current_encounter(game, slot):
    binding = game.manifest_region['encounters'][slot]
    eid = (game.current['variant'] or binding['default_encounter_id']) if slot == 'B1' else binding['encounter_id']
    if game.s['mission'] == 'ORDINARY':
        import learning,adaptation_geometry
        return adaptation_geometry.apply(game.current['growth']['encounters'][slot][eid],learning.patch_for(game,slot,eid))
    return game.cat.encounter_for_board(eid, binding['board_id'])


def public(game):
    if game.s['mission'] != 'ORDINARY':
        return None
    if game.s['phase'] == 'TOWN':
        route = next(r for r in game.cat.config['routes'] if r['route_id'] == game.s['route'])
        rules = policy(game.cat)
        from expedition_tiers import TIERS
        rules['tier_floor']=TIERS[game.s.get('difficulty','D0')]['floor']
        import late_pressure
        pressure=late_pressure.preview(game,rules)
        return {'rule_version': VERSION, 'example_path': route['selected_path'],
                'example_levels': path_levels(rules, route['selected_path']),
                'progression_pressure':pressure,
                'notice': '示例路线；实际分支仍由原规则抽样与选择。'}
    if not game.s['manifest'] or not game.s['region']:
        return None
    frozen = game.current['growth']
    result = {k: deepcopy(v) for k, v in frozen.items() if k != 'encounters'}
    result['next'] = [{'region_id': rid, 'name': game.cat.regions[rid]['name'],
                       'native_minimum': game.s['manifest']['depth_growth']['native_minimum'][rid],
                       'effective_threat': next_level(game.s['manifest']['depth_growth'], rid, frozen['effective_threat'])}
                      for rid in game.next_regions()]
    # Only reveal encounters at the current site or explicitly scouted sites.
    visible = set(game.current['revealed_battles']) | {game.s['site']}
    visible.discard(None)
    result['enemy_preview'] = {}
    for slot in sorted(visible):
        if slot not in game.manifest_region['encounters'] or slot in game.current['cleared']:
            continue
        battle = current_encounter(game, slot)
        result['enemy_preview'][slot] = {
            'encounter_id': battle['encounter_id'], 'effective_threat': battle.get('effective_threat'),
            'mechanisms':deepcopy(battle.get('mechanisms',[])),
            'spawn_options':deepcopy(battle.get('spawn_options',[])),
            'units': [{'instance_id': u['instance_id'], 'enemy_id': u['enemy_id'],
                       'name': game.cat.enemy_templates[u['enemy_id']]['name'],
                       'briefing': game.cat.enemy_templates[u['enemy_id']].get('briefing', ''),
                       'stats': deepcopy(u['stats'])} for u in battle['units']]}
    return result


def describe(game):
    info = public(game)
    if not info:
        return ''
    if 'example_levels' in info:
        return '深入成长示例：' + ' → '.join(f'{r}(L{v})' for r,v in zip(info['example_path'], info['example_levels'])) + '；实际分支以出口预览为准。'
    lines = [f"第{info['region_index']}区 | 实际威胁L{info['effective_threat']} | 地区下限L{info['native_minimum']} | 委任阶段下限L{info.get('stage_floor',1)}；同区回访不涨级。"]
    if game.s['site'] == 'X':
        lines.append('下一地区威胁：' + ('、'.join(f"{x['region_id']} {x['name']} L{x['effective_threat']}（下限L{x['native_minimum']}）" for x in info['next']) or '本趟终点'))
    for slot, preview in info['enemy_preview'].items():
        lines.append(f"敌情 {slot} {preview['encounter_id']} L{preview['effective_threat']}（本区冻结面板）：")
        for unit in preview['units']:
            s = unit['stats']
            lines.append(f"  {unit['instance_id']} {unit['name']} HP{s['hp']} 物攻{s['physical_attack']} 魔攻{s['magic_attack']} 治疗{s['healing_power']} 物防{s['physical_defense']} 魔防{s['magic_defense']}")
            if unit['briefing']: lines.append('    '+unit['briefing'])
        for obj in preview['mechanisms']:
            lines.append(f"  机制 {obj['instance_id']} {obj['name']} HP{obj['stats']['hp']} 格{obj['position']}：{obj['briefing']}")
        if preview['spawn_options']:
            for unit in preview['spawn_options']:
                lines.append(f"  召唤预留 {unit['enemy_id']}：本区冻结面板{unit['stats']}；下一拍行动，无额外奖励。")
    return '\n'.join(lines)
