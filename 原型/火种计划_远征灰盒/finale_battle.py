"""Global formatting clock and ordinary-action interface access, saved in battle."""
from copy import deepcopy
import heapq
import combat as c
import spatial_moves as spatial


def attach(b,run,stage,rules):
    b['finale']={'id':run['id'],'route':run['route'],'stage':stage,'executor':run['executor'],
                'target':rules['B_executor_core_cell'][:],'channel_ticks':rules['B_executor_channel_ticks'],
                'duration':rules['formatting_countdown_ticks'],'started':None,'remaining':None,
                'channel':{'executor':None,'progress':0,'last_tick':None,'complete':False},'intent':{},'cause':None}


def mobile(a,tick):
    return a['hp']>0 and not a.get('pending') and tick>max(a['move_pause_until'],a['root_until'],a['blocked_until'])


def path(cat,board,origin,target,blocked,edges):
    queue=[(0,origin,())];best={origin:0}
    while queue:
        cost,pos,steps=heapq.heappop(queue)
        if pos==target:return steps
        if cost!=best[pos]:continue
        for nxt in sorted(spatial.neighbors(pos)):
            if nxt not in board or not cat.terrain[board[nxt]]['walkable'] or nxt in blocked or spatial.crossed(pos,nxt,edges):continue
            n=cost+(2 if board[nxt]=='SHALLOW_WATER' else 1)
            if n<best.get(nxt,float('inf')):best[nxt]=n;heapq.heappush(queue,(n,nxt,steps+(nxt,)))
    return ()


def intents(cat,b,alive,board,edges,tick,log):
    f=b.get('finale')
    if not f:return {}
    f['intent']={}
    if f['stage']!='ADMIN' or f['route']!='B' or f['started'] is None or f['channel']['complete']:return {}
    target=tuple(f['target']);occupied={tuple(a['pos']):a for a in alive}
    humans=sorted([a for a in alive if a['side']=='player' and a['kind']!='PET-H04'],key=lambda a:a['id'])
    if not humans:return {}
    occupant=occupied.get(target)
    executor=occupant if occupant in humans else next((a for a in humans if a['id']==f['executor']),humans[0])
    f['executor']=executor['id']
    if occupant in humans:
        if not executor['pending']:
            f['intent'][executor['id']]={'kind':'channel'}
    elif occupant and occupant['side']=='player':
        # One move from the empty end of the shortest friendly clearing chain.
        # Pending/rooted allies are walls; no same-tick chain sliding.
        if mobile(occupant,tick):
            danger={tuple(p) for a in alive if a['side']=='enemy' and a['pending'] and a['pending']['due']==tick+1 for p in a['pending'].get('cells',[])}
            todo=[(target,())];seen={target};choices=[]
            while todo:
                pos,chain=todo.pop(0)
                for nxt in sorted(spatial.neighbors(pos)):
                    if nxt in seen or nxt not in board or not cat.terrain[board[nxt]]['walkable'] or spatial.crossed(pos,nxt,edges):continue
                    seen.add(nxt);other=occupied.get(nxt)
                    if not other:choices.append((len(chain),nxt in danger,nxt,pos))
                    elif other['side']=='player' and mobile(other,tick):todo.append((nxt,chain+(nxt,)))
            if choices:
                _,risk,dest,origin=min(choices);a=occupied[origin]
                f['intent'][a['id']]={'kind':'move','cell':list(dest)}
                log('interface_yield',actor=a['id'],destination=list(dest),risk=risk)
    elif occupant and occupant['side']=='enemy':
        # The target cell can be blocked by ADMIN/minions. A standing human
        # adjacent to the interface may connect from that cell instead.
        adjacent=[a for a in humans if c.distance(a['pos'],target)==1 and mobile(a,tick)]
        if adjacent:
            worker=min(adjacent,key=lambda a:a['id'])
            f['intent'][worker['id']]={'kind':'channel'}
            log('interface_adjacent',actor=worker['id'],target_cell=list(target),
                blocker=occupant['id'])
        elif not executor['pending']:
            f['intent'][executor['id']]={'kind':'wait'}
    else:
        if not executor['pending']:
            f['intent'][executor['id']]={'kind':'wait'}
            if not occupant and mobile(executor,tick):
                route=path(cat,board,tuple(executor['pos']),target,set(occupied)-{tuple(executor['pos'])},edges)
                if route:f['intent'][executor['id']]={'kind':'move','cell':list(route[0])}
    return f['intent']


def settle(b,tick,log):
    f=b.get('finale')
    if not f:return False
    live=[a for a in b['actors'] if a['hp']>0 and not a.get('mechanism')]
    humans=[a for a in live if a['side']=='player' and a['kind']!='PET-H04']
    if f['stage']=='ADMIN':
        core=next(a for a in b['actors'] if a['kind']=='ADMIN')
        if f['started'] is None and core['hp']<=core['stats']['hp']*.25:
            f['started']=tick;f['remaining']=f['duration']
            log('formatting_started',remaining=f['remaining'],target_cell=f['target'] if f['route']=='B' else None)
        elif f['started'] is not None:f['remaining']=max(0,f['remaining']-1)
        channel=f['channel']
        if not channel['complete']:
            worker=next((a for a in humans if f['intent'].get(a['id'],{}).get('kind')=='channel'
                         and c.distance(a['pos'],f['target'])<=1),None)
            if worker:
                continuous=channel['executor']==worker['id'] and channel['last_tick']==tick-1
                channel.update(executor=worker['id'],progress=channel['progress']+1 if continuous else 1,last_tick=tick)
                channel['complete']=channel['progress']>=f['channel_ticks']
                log('interface_channel',actor=worker['id'],progress=channel['progress'],complete=channel['complete'])
            else:channel.update(executor=None,progress=0,last_tick=None)
        if f['remaining']==0:f['cause']='FORMATTING_FAILED'
    if not humans:f['cause']='BATTLE_DEFEAT'
    if f['cause']:b['result']='DEFEAT'
    elif not any(a['side']=='enemy' for a in live):
        if f['stage']=='DEMON' or f['route']=='A' or f['channel']['complete']:b['result']='VICTORY'
    return True


def describe(b):
    f=b.get('finale')
    if not f:return ''
    if f['stage']=='DEMON':return '终战第一战：击败初生魔王及护卫；全体上场人类失能即C，不能回城。'
    goal='击败管理员及护卫' + ('，并在(3,5)或占格被敌人占据时的相邻格完成两拍接入' if f['route']=='B' else '')
    return f"{f['route']}路线：{goal}；格式化剩余{f['remaining'] if f['started'] is not None else '未启动'}拍；接入{f['channel']['progress']}/{f['channel_ticks']}，执行者{f['executor']}。"


def validate(b):
    if not b or 'finale' not in b:return
    f=b['finale'];ch=f['channel']
    if f['stage'] not in ('DEMON','ADMIN') or f['route'] not in ('A','B'):raise ValueError('终战阶段或路线损坏。')
    if f['started'] is not None:
        if not (0<=f['started']<=b['tick'] and f['remaining']==max(0,f['duration']-(b['tick']-f['started']))):raise ValueError('格式化时钟损坏。')
    if not 0<=ch['progress']<=f['channel_ticks'] or ch['complete']!=(ch['progress']==f['channel_ticks']):raise ValueError('接入进度损坏。')
