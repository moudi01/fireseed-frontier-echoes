"""Conservative edits to existing deployments and fixed historical aim points."""
from copy import deepcopy
import combat as c
import spatial_moves as spatial

NAMES=['正轴守矛','后列环护','分翼照面','迎矢环面','雾幕后列','沉角迎刃','刺灯问药','压盾守轴','环后留前','环护留印','矛角前压','分道解缠','侧门锁轴','灯口驻蜂','盐弧候步','后环待锋','双锚拖拍','末段留压']
COSTS=['放弃另一侧锁线','前排少一层保护','两翼分兵，单翼火力减少','另一侧失去环卫后援','靠拢邻友，攻击仍会显形','放弃最近目标与另一冲线','另一侧缺少蜂支援','另一侧不受矛轴覆盖','前排失去后护','其他友军不优先环护','放弃后方遮挡与保护','每条线人数减少','原正路覆盖减少','原主轴少一个蜂位','放弃最近目标水线','早期可先拆裸露前排','两处锚点暴露','前段不应用此回应']
COUNTERS=['走另一侧或诱使旧锁线落空','先拆前排或转到未护侧','集中一翼先拆，保留中路','绕侧、用魔法或先拆环卫','接近显露、拆孢母或攻击未罩敌','侧移避开旧冲线','换救护站位或先拆蜂','分散承伤或让旧矛线打空','先拆前排再逼近后护','换标其他敌人或耗盾再打','先处理暴露的前置单位','集中拆一线，控制仍有效','走正路或另一侧','换另一条既有接近线或先拆蜂','换落点或先拆鳗','保留次数或先拆前排','集中一路后再接另一锚点','提前返城、留技能或改变路线']


def lane(pos,board):
    xs=[p['q'] for p in board['cells'] if p['r']==pos[1]] or [p['q'] for p in board['cells']]
    value=(pos[0]-min(xs))/max(1,max(xs)-min(xs))
    return 'left' if value<.4 else 'right' if value>.6 else 'center'


def carrier(cat,enc,card,history,last=False):
    """Return a deterministic patch or None. Reads no current party or path."""
    aid=card['adaptation_id'];n=int(aid[2:]);board=cat.boards[enc['board_id']]
    if n==18 and not last:return None
    original=enc['units'];eligible=[u for u in original if u['enemy_id'] in card['allowed_enemy_ids']
        and any(m['move_id'] in card['allowed_move_ids'] for m in u['moves'])]
    if not eligible:return None
    for kind,count in card.get('required_min_enemy_counts',{}).items():
        if sum(u['enemy_id']==kind for u in original)<count:return None
    if n==17 and not {'EN01','EN06'}<={u['enemy_id'] for u in original}:return None
    if n==12 and len(eligible)<2:return None
    if n in (2,4,5,9,10,16,18) and len(original)<2:return None
    hist_lane=history.get('lane','center')
    cells={tuple(p) for p in board['enemy_deploy_cells']}
    terrain={(p['q'],p['r']):p['terrain_id'] for p in board['cells']}
    cells={p for p in cells if cat.terrain[terrain[p]]['walkable']}
    if not cells:return None
    units=deepcopy(original);byid={u['instance_id']:u for u in units};u=byid[eligible[0]['instance_id']]
    occupied={tuple(v['position']) for v in original+enc.get('mechanisms',[])+enc.get('board_parts',[])}
    changes={};rules={};front=min(p[1] for p in cells);back=max(p[1] for p in cells)
    def place(unit,candidates,key):
        free=[p for p in candidates if p not in occupied and p!=tuple(unit['position'])]
        if not free:return False
        dest=min(free,key=key);occupied.discard(tuple(unit['position']));occupied.add(dest)
        unit['position']=list(dest);changes[unit['instance_id']]=list(dest);return True
    def sidekey(p):return (lane(p,board)!=hist_lane,abs(p[0]-u['position'][0]),p)
    def anchor():
        points=[tuple(p) for p in board['player_deploy_cells']]
        # A historical relative lane maps to a fixed legal coordinate, never the new party.
        return min(points,key=lambda p:(lane(p,board)!=hist_lane,-p[1],p)) if points else None
    if n in (1,6,7,8,13,15) or (n==18 and u['enemy_id']=='EN17'):
        point=anchor()
        if point is None:return None
        mid=next(m['move_id'] for m in u['moves'] if m['move_id'] in card['allowed_move_ids'])
        if n==15 and not any(t=='SHALLOW_WATER' for t in terrain.values()):return None
        rules[u['instance_id']]={'move_id':mid,'anchor':list(point),'card':aid}
    elif n in (3,12,17):
        chosen=eligible[:2] if n!=17 else [next(v for v in units if v['enemy_id']==kind) for kind in ('EN01','EN06')]
        chosen=[byid[v['instance_id']] for v in chosen]
        for unit,side in zip(chosen,('left','right')):
            candidates=[p for p in cells if lane(p,board)==side]
            if n==17:candidates=[p for p in candidates if p[1]==front]
            if not place(unit,candidates,lambda p:(p[1],p)):return None
    elif n==11:
        # Move one original non-spell unit forward; do not create or promote a new unit.
        if not place(u,[p for p in cells if p[1]<u['position'][1]],lambda p:(-p[1],c.distance(p,u['position']),p)):return None
    elif n==14:
        if not place(u,[p for p in cells if lane(p,board)==hist_lane],lambda p:(p[1],p)):return None
    else:
        allies=[v for v in units if v is not u]
        if n==10:
            allies=[v for v in allies if v.get('role','normal')==history.get('role')]
            if not allies:return None
        if n in (2,5,9,16) or n==18:
            # Protect an original rear ally, explicitly giving up front coverage.
            allies=[v for v in allies if v['position'][1]>front]
        if not allies:return None
        friend=min(allies,key=lambda v:(lane(v['position'],board)!=hist_lane,-v['position'][1] if n!=4 else v['position'][1],v['instance_id']))
        positions=[p for p in cells if c.distance(p,friend['position'])==1]
        if n in (2,5,9,16,18):positions=[p for p in positions if p[1]>front]
        if n==4:positions=[p for p in positions if p[1]==front]
        if not place(u,positions,sidekey):return None
        rules[u['instance_id']]={'move_id':'EN08-A' if n==5 else 'EN04-A','ally':friend['instance_id'],'card':aid}
    # Occupiers cannot seal all approaches. Preserve access from every deploy origin
    # to at least two different free cells adjacent to the original opposing force.
    walk={p for p,t in terrain.items() if cat.terrain[t]['walkable'] and p not in occupied}
    targets={p for q in occupied for p in spatial.neighbors(q) if p in walk}
    for start in board['player_deploy_cells']:
        if tuple(start) not in walk:return None
        reached={tuple(start)};todo=[tuple(start)]
        while todo:
            for p in spatial.neighbors(todo.pop()):
                if p in walk and p not in reached:reached.add(p);todo.append(p)
        if len(targets&reached)<2:return None
    return {'card':aid,'family':card['family'],'name':NAMES[n-1],'positions':changes,'rules':rules,
            'history':deepcopy(history),'cost':COSTS[n-1],'counterplay':COUNTERS[n-1],
            'enemy_ids':[v['enemy_id'] for v in eligible],
            'move_ids':sorted({m['move_id'] for v in eligible for m in v['moves'] if m['move_id'] in card['allowed_move_ids']})}


def apply(enc,patch):
    result=deepcopy(enc)
    if not patch:return result
    for unit in result['units']:
        iid=unit['instance_id']
        if iid in patch['positions']:unit['position']=patch['positions'][iid][:]
        if iid in patch['rules']:unit['adaptation_rule']=deepcopy(patch['rules'][iid])
    result['adaptation']=deepcopy(patch);return result


def aim(actor,card,cat,board):
    """Existing attack at a historical cell. Empty locked cells can miss normally."""
    rule=actor.get('adaptation_rule')
    if not rule or rule['move_id']!=card['move_id'] or 'anchor' not in rule:return False,None
    p=tuple(rule['anchor']);legal=lambda q:q in board and c.distance(actor['pos'],q)<=card['range'] and c.visible(cat,board,actor['pos'],q)
    facing=c.direction(actor['pos'],p)
    # Axis responses aim a direction, not a distant unit. Only original in-range
    # cells are locked; requiring the old deployment cell itself in range would
    # suppress every spear attack after the front lines had advanced.
    if card.get('shape','').startswith('front_'):
        from mechanics import line
        points=[q for q in line(actor['pos'],facing,card['range']) if legal(q)]
        return True,(None,points,{'facing':facing,'adaptation_card':rule['card']}) if points else None
    if not legal(p):return True,None
    if card['move_id']=='EN05-A':
        neighbors=[q for q in spatial.neighbors(p) if legal(q) and q!=tuple(actor['pos'])]
        return True,(None,[p,min(neighbors)],{'facing':facing,'adaptation_card':rule['card']}) if neighbors else None
    points=[p]
    return True,(None,points,{'facing':facing,'adaptation_card':rule['card']})
