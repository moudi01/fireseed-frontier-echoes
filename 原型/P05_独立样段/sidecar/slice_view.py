"""Restricted tutorial presentation over the frozen domain runtime."""
import re


COMMANDS = {'quest', 'tutorial', 'move', 'fight', 'step', 'return', 'deploy',
            'place', 'retreat', 'flee', 'walkto', 'interact'}
SITES = {'I', 'A', 'B_SUPPORT', 'B_MATERIAL', 'C', 'D', 'G', 'X'}
TUTORIAL = {('recommend', 'CONFIRM'), ('start',), ('observe',), ('materials',),
            ('materials', 'CLAIM'), ('materials', 'PASS')}


def valid_tutorial(args):
    if tuple(args) in TUTORIAL:
        return True
    if len(args) != 2:
        return False
    key, value = args
    return ((key == 'support' and bool(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value)))
            or (key == 'plan' and value in ('PL01', 'PL02', 'PL05', 'PASS'))
            or (key == 'cache' and value in ('EF03', 'EF05', 'EF07', 'PASS')))


def valid_command(command, args):
    if command == 'tutorial':
        return valid_tutorial(args)
    if command == 'quest':
        return args == ['commission', 'CONFIRM']
    if command in ('return', 'flee'):
        return args == ['CONFIRM']
    if command in ('fight', 'step', 'retreat'):
        return not args
    if command in ('move', 'interact'):
        return len(args) == 1 and args[0] in SITES
    if command == 'deploy':
        return len(args) == 2 and args[1] in ('on', 'off')
    if command == 'place':
        return len(args) == 4 and all(re.fullmatch(r'-?\d{1,3}', x) for x in args[1:])
    if command == 'walkto':
        return len(args) == 2 and all(re.fullmatch(r'-?\d{1,3}', x) for x in args)
    return False


def member_view(m):
    return {key: m.get(key) for key in ('instance_id', 'unit_id', 'name', 'hp', 'deployed', 'position', 'facing', 'injury_days')}


def route_view(game):
    import region_space as space
    layout = game.layout
    current = game.current
    state = game.s
    details = space.current(game)
    contact = details['contact']
    here = state['site']
    blocked = bool(contact and contact['site'] not in current['cleared'])
    neighbors = []
    nearby = []
    if state['phase'] == 'EXPLORE' and not blocked:
        neighbors = [b if here == a else a for a, b in layout['edges'] if here in (a, b)]
        nearby = [n for n in details['objects_seen']
                  if space.distance(details['position'], details['anchors'][n]) <= 2
                  and space.sight(details, details['position'], details['anchors'][n])]
    visible = space.visible(game)
    lit = {space.key(cell) for lamp in details['lamps'].values()
           if space.key(lamp['position']) in visible
           for cell in space.disk(lamp['position'], lamp['radius'])
           if space.sight(details, lamp['position'], cell)}
    return {'neighbors': neighbors, 'nearby': nearby, 'contact_pending': blocked,
            'links': [edge for edge in layout['edges'] if all(x in details['objects_seen'] for x in edge)],
            'lit_cells': [space.point(cell) for cell in sorted(lit & visible) if cell in details['ground']],
            'safe_return': state['phase'] == 'EXPLORE' and (here == 'I' or (here == 'X' and 'G' in current['cleared'])),
            'cleared': current['cleared']}


def _save_version(ledger, primary):
    return max((row['response']['state_version'] for row in ledger['entries'].values()
                if row['status'] == 'COMMITTED' and row['response']['files']['save.json'] == primary
                and row['before']['files']['save.json'] != primary), default=0)


def make_view(game, ledger, primary):
    state = game.s
    facts = state['campaign']['facts']
    trip = state.get('tutorial_trip') or {}
    party = [member_view(m) for m in state['party']]
    battle = state.get('battle')
    active = state['phase'] in ('EXPLORE', 'BATTLE') and state['mission'] == 'TUTORIAL'
    route = route_view(game) if active else {}
    board_id = 'OPEN'
    summary = state.get('summary')
    cap = (state.get('manifest') or {}).get('caps', {}).get('gear_claims', 0)
    opening = state['narrative']['records'].get('opening', {})
    return {'phase': state['phase'], 'site': state['site'], 'day': state['day'],
            'supply': state['bank']['supply'], 'departure_cost': 1,
            'save_version': _save_version(ledger, primary),
            'commissioned': 'ST-101' in facts, 'complete': 'ST-102' in facts,
            'party': party, 'budget': state['budget'], 'route': route,
            'opening_lines': opening.get('lines', []),
            'town_deploy_cells': game.cat.boards[board_id]['player_deploy_cells'],
            'town_board_cells': game.cat.boards[board_id]['cells'],
            'observation': trip.get('observation'), 'choices': trip.get('choices', {}),
            'plans': [p for p in ('PL01', 'PL02', 'PL05') if p not in state['plans_owned']]
                     if 'A' in route.get('cleared', []) else [],
            'gear_offers': trip.get('gear_offers', []) if 'G' in route.get('cleared', []) else [],
            'gear_claims': cap - state['debits'].get('gear_claims', 0),
            'settlement': summary,
            'battle_results': [{key: row.get(key) for key in ('encounter_id', 'battle_id', 'result', 'tick')}
                               for row in state['battle_reports']],
            'actors': [{key: a.get(key) for key in ('id', 'kind', 'name', 'side', 'pos', 'hp', 'facing')}
                       for a in battle['actors']] if battle else []}
