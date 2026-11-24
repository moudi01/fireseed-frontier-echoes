"""SKILL-PAIR-1.0 overlay and bounded skill geometry, separate from frozen JSON."""
from copy import deepcopy
import combat as c
import roster_skills as roster

CORE = {
    'M01': dict(move_id='M01-A', name='封路刺', kind='damage', damage_type='physical',
                coefficient=1.1, range=2, medium='near', shape='locked_axis_target', cooldown=3),
    'M02': dict(move_id='M02-A', name='急救剂', kind='heal', range=2,
                medium='medical', cooldown=3, heal_base=8),
    'M03': dict(move_id='M03-A', name='破障铆射', kind='damage', damage_type='physical',
                coefficient=1.25, range=3, medium='projectile', shape='locked_axis', cooldown=4),
    'M04': dict(move_id='M04-A', name='雾绊', kind='damage', damage_type='magic',
                coefficient=.8, range=3, medium='spell', shape='locked_target', cooldown=4),
}
CORE.update(roster.MERC_CARDS)
for card in CORE.values():
    card.update(windup=1, cast_limit=2, first_eligible_tick=1, max_targets=1,interruptible=True,delayable_cast=card['medium']=='spell')

ECHO_IDS = {'EN06-A', 'EL03-A'}


def overlay(encounters):
    """Change every expanded payload with the same ID; never mutate source files."""
    for encounter in encounters.values():
        for actor in encounter['units']:
            for card in actor.get('moves', []):
                if card['move_id'] in ECHO_IDS:
                    card['windup'] = 3
                    card['target_rule'] = 'own_committed_basic_hit_history'
                    card['record_capacity'] = 2 if card['move_id'] == 'EL03-A' else 1
                    card['rule_overlay'] = 'SKILL-PAIR-1.0'


def core_cards(kind):
    import heroes
    return [deepcopy(CORE[kind])] if kind in CORE else heroes.cards(kind)


def axis(origin, end):
    q, r = end[0]-origin[0], end[1]-origin[1]
    return (q != 0 or r != 0) and (q == 0 or r == 0 or q+r == 0)


def echo_cells(actor, card, catalog, board):
    recent = actor['basic_history'][-card['record_capacity']:]
    unique = []
    for record in recent:
        pos = tuple(record['cell'])
        if pos not in unique and c.distance(actor['pos'], pos) <= card['range'] and c.visible(catalog, board, actor['pos'], pos):
            unique.append(pos)
    return unique


def flank_paths(actor, foes, catalog, board, occupied, blocked_edges=()):
    """At most two walkable steps, stop at water; return two public candidates."""
    from spatial_moves import crossed
    origin = tuple(actor['pos']); paths = {}; todo = [(origin, [])]
    while todo:
        pos, path = todo.pop(0)
        if path:
            side = any(c.distance(pos, f['pos']) == 1 and
                       c.direction(f['pos'], pos) not in {(f['facing']+d)%6 for d in (-1, 0, 1)} for f in foes)
            if side:
                previous = paths.get(pos)
                if previous is None or (len(path), path) < (len(previous), previous): paths[pos] = path
        if len(path) == 2 or (path and board[pos] == 'SHALLOW_WATER'): continue
        for dq, dr in c.DIRS:
            nxt = (pos[0]+dq, pos[1]+dr)
            if crossed(pos,nxt,blocked_edges):continue
            if nxt == origin or nxt in path or nxt in occupied or nxt not in board or not catalog.terrain[board[nxt]]['walkable']: continue
            todo.append((nxt, path+[nxt]))
    return [path for _, path in sorted(paths.items(), key=lambda row: (len(row[1]), row[0], row[1]))[:2]]
