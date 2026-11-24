"""Actual location-specific board masks, not a rendering transform.

Legacy JSON remains a historical content source. Terrain and deployment below
supersede its 7x9 coordinates for this prototype version.
"""
from copy import deepcopy

VERSION = 'MULTI-BOARD-2.0-COST'
CENTER = (3, 4)
RADIUS = 4
DIRS = ((1,0),(0,1),(-1,1),(-1,0),(0,-1),(1,-1))
FRONT_FORMATION = ((2,1),(4,1),(5,1),(7,1),(4,0),(6,0),(3,1),(5,0))
REAR_COLUMNS = tuple(range(2,8))
REAR_ROWS = 3


def default_formation(count=24):
    """Generate deployment slots behind the unchanged original front eight."""
    if type(count) is not int or count < 0:
        raise ValueError('默认布阵数量必须为非负整数。')
    positions = list(FRONT_FORMATION)
    row = -1
    while len(positions) < count:
        positions.extend((q,row) for q in REAR_COLUMNS)
        row -= 1
    return tuple(positions[:count])


DEFAULT_FORMATION = default_formation(24)


def mask():
    return [(q,r) for r in range(CENTER[1]-RADIUS,CENTER[1]+RADIUS+1)
            for q in range(CENTER[0]-RADIUS,CENTER[0]+RADIUS+1)
            if max(abs(q-CENTER[0]),abs(r-CENTER[1]),abs(q+r-sum(CENTER))) <= RADIUS]


SPECS = {
    'OPEN': ('RECTANGLE',8,8,1),
    'DOUBLE_BRIDGE': ('LONG_RECTANGLE',6,10,2),
    'DRY_ISLAND': ('REGULAR_HEXAGON',None,None,None),
    'DUAL_FLANK': ('REGULAR_HEXAGON',None,None,None),
    'SALT_CROSSING': ('WIDE_RECTANGLE',9,8,1),
    'MIRROR_COURT': ('NEAR_SQUARE',8,9,1),
    'FORGE_CROSSING': ('WIDE_RECTANGLE',9,8,1),
    'CITADEL_RING': ('NEAR_SQUARE',8,9,1),
}
SHAPE_NAMES = {'RECTANGLE':'矩形','LONG_RECTANGLE':'狭长矩形','REGULAR_HEXAGON':'正六边形',
               'WIDE_RECTANGLE':'宽矩形','NEAR_SQUARE':'近正方形'}


def build_boards(sources, terrain):
    boards={}
    for source in sources:
        bid=source['board_id'];shape,columns,rows,origin=SPECS[bid]
        at=lambda col,row:(col+origin-row//2,row)
        if shape=='REGULAR_HEXAGON':
            positions=mask()
            layouts = {
                'DRY_ISLAND': {'DEEP_WATER':[(3,3),(4,3),(2,4),(3,4)],
                              'SHALLOW_WATER':[(2,3),(5,3),(1,4),(4,4),(1,5),(4,5)]},
                'DUAL_FLANK': {'HIGH_OBSTACLE':[(4,2),(3,3),(3,4)]},
            }[bid]
        else:
            positions=[at(col,row) for row in range(rows) for col in range(columns)]
            local = {
                'OPEN': {},
                'DOUBLE_BRIDGE': {'HIGH_OBSTACLE':[(0,5),(3,5)],
                                  'FIXED_BRIDGE':[(col,5) for col in (1,2,4,5)],
                                  'SHALLOW_WATER':[(1,4),(3,4),(5,4)]},
                'SALT_CROSSING': {'SHALLOW_WATER':[(col,3) for col in range(9)],
                                  'HIGH_GROUND':[(1,2),(7,2)],'LOW_OBSTACLE':[(2,4),(6,4)]},
                'MIRROR_COURT': {'HIGH_OBSTACLE':[(3,4),(4,4)],'LOW_OBSTACLE':[(2,4),(5,4)],
                                 'HIGH_GROUND':[(1,3),(6,3),(1,5),(6,5)]},
                'FORGE_CROSSING': {'HIGH_OBSTACLE':[(2,3),(6,3)],'LOW_OBSTACLE':[(3,4),(5,4)],
                                   'HIGH_GROUND':[(0,4),(8,4)]},
                'CITADEL_RING': {'HIGH_OBSTACLE':[(3,4),(4,4)],'LOW_OBSTACLE':[(2,3),(5,3)],
                                 'HIGH_GROUND':[(1,4),(6,4)]},
            }[bid]
            layouts={t:[at(col,row) for col,row in ps] for t,ps in local.items()}
        # Add real ground only behind r=0. Enemy rows, bridges, chokepoints and
        # all original terrain retain exactly their old coordinates.
        rear = [(q,r) for r in range(-1,-REAR_ROWS-1,-1) for q in REAR_COLUMNS]
        positions += [pos for pos in rear if pos not in positions]
        overrides={p:t for t,ps in layouts.items() for p in ps}
        assert set(overrides)<=set(positions), bid+' terrain outside mask'
        cells=[{'q':q,'r':r,'terrain_id':overrides.get((q,r),'GROUND')} for q,r in positions]
        walkable={(c['q'],c['r']) for c in cells if terrain[c['terrain_id']]['walkable']}
        enemy_rows=(7,9) if bid=='DOUBLE_BRIDGE' else (5,7)
        boards[bid]={
            'board_id':bid,'name':source['name'],'geometry_version':VERSION,
            'shape':shape,'shape_name':SHAPE_NAMES[shape], 'columns':columns,'rows':rows,'column_origin':origin,
            'center':list(CENTER) if shape=='REGULAR_HEXAGON' else None,
            'radius':RADIUS if shape=='REGULAR_HEXAGON' else None,'cell_count':len(cells),
            'cells':cells,'player_deploy_cells':[[q,r] for q,r in positions if r<=1 and (q,r) in walkable],
            'enemy_deploy_cells':[[q,r] for q,r in positions if enemy_rows[0]<=r<=enemy_rows[1] and (q,r) in walkable],
            'source_geometry':'LEGACY_7x9_NOT_USED','terrain_overrides':layouts,
            'rear_deploy_rows':REAR_ROWS,
        }
        assert len(boards[bid]['player_deploy_cells']) >= 20, bid+' insufficient deployment'
        assert set(DEFAULT_FORMATION) <= {tuple(p) for p in boards[bid]['player_deploy_cells']}, bid+' default formation outside deployment'
    return boards


def adapt_encounter(source, board):
    """Place an existing formation on the selected board, preserving IDs and stats."""
    e=deepcopy(source);e['geometry_version']=VERSION
    def transform(position):
        col,row=position
        if board['shape']=='REGULAR_HEXAGON':q=col+2-row//2
        else:
            if board['board_id']=='DOUBLE_BRIDGE':
                col={1:0,2:1,3:2,4:4,5:5}[col];row+=2
            else:col+=(board['columns']-7)//2
            q=col+board['column_origin']-row//2
        return [q,row]
    def anchor(position):
        transformed=transform(position)
        # Public fixed targets must remain occupiable after replacing 7x9 terrain.
        legal=[(cell['q'],cell['r']) for cell in board['cells'] if cell['terrain_id'] not in ('HIGH_OBSTACLE','LOW_OBSTACLE','DEEP_WATER')]
        def key(pos):
            q,r=pos[0]-transformed[0],pos[1]-transformed[1]
            return (max(abs(q),abs(r),abs(q+r)),abs(r),pos)
        return list(min(legal,key=key))
    for unit in e['units']+e.get('mechanisms',[])+e.get('spawn_options',[])+e.get('board_parts',[]):
        if 'position' in unit:
            unit['source_position']=unit['position'][:]
            unit['position']=transform(unit['position'])
        if 'position_candidates' in unit:unit['position_candidates']=[transform(p) for p in unit['position_candidates']]
        for card in unit.get('moves',[]):
            if 'position_candidates' in card:card['position_candidates']=[transform(p) for p in card['position_candidates']]
            if 'locked_anchor_cells' in card:card['locked_anchor_cells']=[anchor(p) for p in card['locked_anchor_cells']]
    for link in e.get('reinforcements',{}).get('bindings',{}).values():
        link['candidates']=[transform(p) for p in link['candidates']]
    return e
