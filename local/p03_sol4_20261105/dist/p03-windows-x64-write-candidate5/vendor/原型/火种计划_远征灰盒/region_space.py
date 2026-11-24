"""Persistent hex-ground exploration; battle boards are translated into this ground.

The old site graph supplies content constraints, not movement shortcuts. All
movement follows ground cells and stops at the first unresolved encounter.
"""
from collections import deque
from copy import deepcopy
import heapq
import math
from data import keyed_rng

DIRS=((1,0),(0,1),(-1,1),(-1,0),(0,-1),(1,-1))
VERSION='SPACE-1'

def check(ok,text):
    if not ok:raise ValueError(text)
def key(p):return f'{p[0]},{p[1]}'
def point(k):return tuple(map(int,k.split(',')))
def distance(a,b):return max(abs(a[0]-b[0]),abs(a[1]-b[1]),abs(sum(a)-sum(b)))
def neighbors(p):return [(p[0]+q,p[1]+r) for q,r in DIRS]
def disk(p,r):return [(p[0]+q,p[1]+s) for q in range(-r,r+1) for s in range(-r,r+1) if max(abs(q),abs(s),abs(q+s))<=r]
def current(game):return game.s.get('regions',{}).get(game.s.get('region'),{}).get('space')
def active(game):return current(game) is not None and game.s['phase'] in ('EXPLORE','BATTLE')
def walkable(game,space,p):return key(p) in space['ground'] and game.cat.terrain[space['ground'][key(p)]]['walkable']


def astar(start,end,allowed,bounds):
    queue=[(distance(start,end),0,start)];cost={start:0};parent={start:None}
    while queue:
        _,g,p=heapq.heappop(queue)
        if g!=cost[p]:continue
        if p==end:
            path=[]
            while p is not None:path.append(p);p=parent[p]
            return path[::-1]
        for n in neighbors(p):
            if not(bounds[0]<=n[0]<=bounds[1] and bounds[2]<=n[1]<=bounds[3]) or not allowed(n):continue
            if g+1<cost.get(n,10**9):
                cost[n]=g+1;parent[n]=p;heapq.heappush(queue,(g+1+distance(n,end),g+1,n))
    raise ValueError('连续地图道路不能合法连通；拒绝生成孤岛或穿越其他战场。')


def centers(game):
    if game.s['mission']=='TUTORIAL':
        return {'I':(0,0),'A':(0,26),'B_SUPPORT':(-16,44),'B_MATERIAL':(16,44),'C':(0,62),'D':(0,82),'G':(0,106),'X':(0,128)}
    layout=game.layout['template_id'];first='A' if layout.endswith('-A') else 'B';second='B' if first=='A' else 'A'
    rows={'I':(0,0),'U':(0,28),'B1':(0,52),'V':(0,78),'S':(-24,94),
          'B2':(0,116),'W':(0,142),'T':(0,178),'G':(0,204),'X':(0,230),
          first:(-24,14),'D':(-9,14),second:(-24,78),'C':(-24,160),'L':(24,160)}
    if game.s['region']=='RG08':rows.update(T=(-24,166),C=(0,182),L=(24,166),G=(-24,204),X=(-24,230))
    rng=keyed_rng(game.s['seed'],'space:'+game.s['region']+':'+layout)
    # Whole-map shear/reflection preserves the layout, while real boards retain
    # their authored orientation. Jitter stays well below room separation.
    flip=rng.choice([-1,1]);stretch=rng.choice([0,1])
    return {n:(flip*(q+r//3*stretch),r) for n,(q,r) in rows.items()}


def generate(game):
    check(game.s['mission'] in ('ORDINARY','TUTORIAL'),'此固定专线保持自己的移动规则。')
    sites=centers(game);ground={};rooms={};boards={};anchors={};lamps={};props=[]
    for n,c in sites.items():
        binding=game.manifest_region['encounters'].get(n)
        if binding:
            b=game.cat.boards[binding['board_id']];origin=[c[0]-3,c[1]-4]
            cells={(x['q']+origin[0],x['r']+origin[1]):x['terrain_id'] for x in b['cells']}
            boards[n]={'board_id':b['board_id'],'origin':origin}
            local=b['player_deploy_cells'][len(b['player_deploy_cells'])//2]
            anchors[n]=[local[0]+origin[0],local[1]+origin[1]]
        else:cells={p:'GROUND' for p in disk(c,3)};anchors[n]=list(c)
        check(not set(map(key,cells))&ground.keys(),'战场边界发生重叠。')
        ground.update({key(p):t for p,t in cells.items()});rooms[n]=list(map(key,cells))
        event=game.manifest_region['events'].get(n)
        if event and game.cat.events[event['event_id']].get('site_lighting',{}).get('required'):
            lamps[n]={'position':anchors[n][:],'radius':4,'source':game.cat.events[event['event_id']]['site_lighting']['source']}
        if game.s['mission']=='TUTORIAL' and n=='B_SUPPORT':
            lamps[n]={'position':anchors[n][:],'radius':4,'source':'STATION_LANTERN'}
        if event and event['event_id']=='EV04':
            for number,delta in [(1,-2),(2,2)]:
                props.append({'id':n+':bell'+str(number),'site':n,'name':str(number)+'号钟面',
                              'position':[c[0]+delta,c[1]],'command':'rub '+str(number),'kind':'bell'})
    bounds=(min(p[0] for p in sites.values())-60,max(p[0] for p in sites.values())+60,-60,max(p[1] for p in sites.values())+60)
    paths={};road_owner={}
    for a,b in game.layout['edges']:
        other=set(p for n,c in sites.items() if n not in (a,b) for p in disk(c,9))
        def allowed(p):
            if p in other:return False
            if key(p) in ground and not game.cat.terrain[ground[key(p)]]['walkable']:return False
            for x in [p]+neighbors(p):
                for u,v in road_owner.get(x,[]):
                    common=set((a,b))&set((u,v))
                    if not any(distance(p,sites[n])<=8 for n in common):return False
            return True
        path=astar(tuple(anchors[a]),tuple(anchors[b]),allowed,bounds)
        paths[a+'|'+b]=[list(p) for p in path]
        for p in path:
            ground.setdefault(key(p),'GROUND');road_owner.setdefault(p,[]).append((a,b))
    space={'version':VERSION,'ground':ground,'centers':{k:list(v) for k,v in sites.items()},
           'anchors':anchors,'rooms':rooms,'boards':boards,'paths':paths,'lamps':lamps,'props':props,
           'position':anchors['I'][:],'facing':1,'discovered':[],'objects_seen':['I'],
           'contact':None,'last_site':'I','steps':0,'travel_cost':0,'last_walk':[]}
    game.current['space']=space;reveal(game)
    return space


def line(a,b):
    n=distance(a,b)
    for i in range(1,n+1):
        q=a[0]+(b[0]-a[0])*i/n;r=a[1]+(b[1]-a[1])*i/n;s=-q-r
        x,y,z=round(q),round(r),round(s)
        errors=[abs(x-q),abs(y-r),abs(z-s)]
        if errors[0]==max(errors):x=-y-z
        elif errors[1]==max(errors):y=-x-z
        yield (x,y)


def sight(space,a,b):
    for p in list(line(a,b))[:-1]:
        if space['ground'].get(key(p),'HIGH_OBSTACLE')=='HIGH_OBSTACLE':return False
    return True


def visible(game):
    s=current(game);pos=s['position']
    found={key(p) for p in disk(pos,8) if sight(s,pos,p)}
    for lamp in s['lamps'].values():
        if key(lamp['position']) in found:
            found.update(key(p) for p in disk(lamp['position'],lamp['radius']) if sight(s,lamp['position'],p))
    contact=s['contact']
    if contact and contact['site'] not in game.current['cleared']:
        found.update(s['rooms'][contact['site']])
    if game.s['phase']=='BATTLE' and game.s['site'] in s['rooms']:found.update(s['rooms'][game.s['site']])
    return found


def reveal(game):
    s=current(game);seen=visible(game);s['discovered']=sorted(set(s['discovered'])|seen)
    for n,p in s['anchors'].items():
        if key(p) in seen and n not in s['objects_seen']:s['objects_seen'].append(n)


def can_walk(game):
    game.noncombat();s=current(game);check(s,'当前固定专线不使用连续探索。')
    if s['contact'] and s['contact']['site'] not in game.current['cleared']:
        raise ValueError('已到接敌边界；可fight布阵开战，或retreat退回边界外。')
    s['contact']=None
    return s


def advance(game,p):
    s=current(game);old=s['position'][:]
    check(distance(old,p)==1 and walkable(game,s,p),'前方不可通行。')
    s['position']=list(p);s['facing']=DIRS.index((p[0]-old[0],p[1]-old[1]));s['steps']+=1
    s['travel_cost']+=2 if s['ground'][key(p)]=='SHALLOW_WATER' else 1
    import book_rewards
    book_rewards.leave_site(game,game.s.get('region'),game.s.get('site'))
    game.s['site']=None
    for n in s['boards']:
        if n not in game.current['cleared'] and distance(p,s['centers'][n])<=8:
            s['contact']={'site':n,'outside':old};game.arrive(n,s['last_site']);s['last_site']=n;reveal(game);return False
    reveal(game);return True


def travel(game,path):
    s=can_walk(game);count=0;s['last_walk']=[s['position'][:]]
    for p in path:
        if not walkable(game,current(game),p):break
        count+=1
        proceed=advance(game,p);s['last_walk'].append(s['position'][:])
        if not proceed:break
    if count:game.log('spatial_walk',steps=count,position=current(game)['position'])
    return f"实际移动{count}格，位置{current(game)['position']}。"+('已到接敌边界，fight或retreat。' if current(game)['contact'] else '前方不可通行。' if not count else '靠近对象后interact交互。')


def legacy_move(game,destination):
    s=can_walk(game);origin=game.s['site']
    check(origin and any(set(e)=={origin,destination} for e in game.layout['edges']),'move兼容指令只从现场沿相邻道路逐格走；路上请用walk/walkto。')
    route=s['paths'].get(origin+'|'+destination)
    if route is None:route=list(reversed(s['paths'][destination+'|'+origin]))
    # From a battle boundary, first route through the now-cleared physical room.
    path=astar(tuple(s['position']),tuple(s['anchors'][destination]),lambda p:walkable(game,s,p),bounds(s))
    result=travel(game,path[1:])
    if not s['contact']:game.arrive(destination,s['last_site']);s['last_site']=destination
    return result


def bounds(s):
    cells=list(map(point,s['ground']));return(min(p[0] for p in cells)-1,max(p[0] for p in cells)+1,min(p[1] for p in cells)-1,max(p[1] for p in cells)+1)


def handle(game,command,args):
    s=current(game);check(active(game),'当前没有连续区域地图。')
    if command=='map':return describe(game)
    if command=='interact':
        can_walk(game);check(len(args)<=1,'interact [附近地点ID]')
        choices=[n for n,p in s['anchors'].items() if distance(s['position'],p)<=2 and sight(s,s['position'],p)]
        n=args[0].upper() if args else (choices[0] if len(choices)==1 else None)
        check(n in choices,'需走近现场（2格内）再交互；附近：'+str(choices))
        game.arrive(n,s['last_site']);s['last_site']=n;return '已与现场交互：'+n
    if command=='walk':
        check(1<=len(args)<=2,'walk 方向0..5 [1..12格]');d=int(args[0]);count=int(args[1]) if len(args)==2 else 1
        check(0<=d<6 and 1<=count<=12,'方向0..5，每次1..12格。')
        q,r=DIRS[d];p=s['position'];return travel(game,[(p[0]+q*i,p[1]+r*i) for i in range(1,count+1)])
    if command=='walkto':
        can_walk(game);check(len(args)==2,'walkto q r，仅走已揭示道路，最多32格后暂停。')
        p=tuple(map(int,args));known=set(s['discovered']);check(key(p) in known and walkable(game,s,p),'目标尚未发现或不可通行。')
        route=astar(tuple(s['position']),p,lambda n:key(n) in known and walkable(game,s,n),bounds(s))
        return travel(game,route[1:33])
    raise ValueError('未知地图指令。')


def retreat(game):
    s=current(game);game.noncombat();check(s['contact'] and s['contact']['site'] not in game.current['cleared'],'当前没有待处理接敌。')
    s['position']=s['contact']['outside'];s['contact']=None;game.s['site']=None;reveal(game)
    game.log('spatial_retreat',position=s['position']);return '已退回接敌边界外；敌阵与地形不刷新。'


def bind_battle(game):
    s=current(game)
    if s and game.s['site'] in s['boards']:game.s['battle']['world_binding']={'region':game.s['region'],'site':game.s['site'],**deepcopy(s['boards'][game.s['site']])}


def prepare_rub(game,args):
    s=can_walk(game);check(len(args)==1 and args[0] in ('1','2'),'rub 1或rub 2')
    near=[p for p in s['props'] if p['command']=='rub '+args[0] and distance(p['position'],s['position'])<=1]
    check(near,'需要走到对应钟面旁（1格内）拓印，不能在另一面钟前远程完成。')
    game.arrive(near[0]['site'],s['last_site']);s['last_site']=near[0]['site']


def describe(game):
    s=current(game)
    now=visible(game);names={n['id']:n['name'] for n in game.layout['nodes']}
    lines=[f"连续探索 位置{s['position']} 朝向{s['facing']}；累计{s['steps']}格（不推进日历／侵蚀）。"
           'walk 0..5 [格数]、walkto q r、interact [地点]。']
    for n in s['objects_seen']:
        p=s['anchors'][n]
        kind='enemy' if n in s['boards'] else 'event' if n in game.manifest_region['events'] else 'site'
        lines.append(f"{n} {names.get(n,n)} 坐标({p[0]},{p[1]}) {kind}"
                     f"{' 已清' if n in game.current['cleared'] else ''}"
                     f"{' 可见' if key(p) in now else ' 未探明'}")
    if not s['objects_seen']:lines.append('尚未发现地点。')
    return '\n'.join(lines)


def public(game):
    if not active(game):return None
    s=current(game);now=visible(game);objects=[]
    names={n['id']:n['name'] for n in game.layout['nodes']}
    for n in s['objects_seen']:
        p=s['anchors'][n];kind='enemy' if n in s['boards'] else 'event' if n in game.manifest_region['events'] else 'site'
        objects.append({'id':n,'name':names.get(n,n),'position':p,'kind':kind,'visible':key(p) in now,
                        'cleared':n in game.current['cleared'],'near':distance(s['position'],p)<=2,
                        'lamp':s['lamps'].get(n)})
    for prop in s['props']:
        if key(prop['position']) in s['discovered']:
            objects.append({**deepcopy(prop),'visible':key(prop['position']) in now,
                            'near':distance(prop['position'],s['position'])<=1,'lamp':None,'cleared':False})
    binding=s['boards'].get(game.s['site'])
    preview=[]
    if s['contact'] and s['contact']['site'] not in game.current['cleared'] and game.s['phase']=='EXPLORE':
        import depth_growth
        preview=deepcopy(depth_growth.current_encounter(game,s['contact']['site'])['units'])
    return {'version':s['version'],'position':s['position'],'facing':s['facing'],'steps':s['steps'],
            'cells':[{'q':point(k)[0],'r':point(k)[1],'terrain_id':s['ground'].get(k,'HIGH_OBSTACLE'),
                      'visible':k in now,'walkable':walkable(game,s,point(k))} for k in s['discovered']],
            'objects':objects,'contact':deepcopy(s['contact']),'battle_binding':binding,'preview':preview,'last_walk':s['last_walk'],
            'deploy_cells':game.cat.boards[binding['board_id']]['player_deploy_cells'] if binding and s['contact'] else [],
            'battle_cells':game.cat.boards[binding['board_id']]['cells'] if binding and (s['contact'] or game.s['phase']=='BATTLE') else [],
            'summary':describe(game)}


def validate(game):
    for region in game.s.get('regions',{}).values():
        s=region.get('space')
        if not s:continue
        check(s['version']==VERSION and walkable(game,s,s['position']),'连续地图版本或落脚位置无效。')
        check(s['steps']>=0 and 0<=s['facing']<6,'连续移动记录无效。')
        for n,binding in s['boards'].items():
            for cell in game.cat.boards[binding['board_id']]['cells']:
                p=(cell['q']+binding['origin'][0],cell['r']+binding['origin'][1])
                check(s['ground'].get(key(p))==cell['terrain_id'],'探索地形与原地战斗地形不一致。')
