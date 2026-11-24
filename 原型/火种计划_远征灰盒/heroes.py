"""Hero configuration and compatibility helpers.

Live combat hooks are exported once from hero_power_v062. Scheduling and final
settlement belong to mechanics; see 模块开发约定.md before adding a hook.
"""
import combat as c


def check(ok,text):
    if not ok:raise ValueError(text)


def validate(game):
    import town
    for m in town.roster(game):
        check(type(m.get('hero_enabled',True)) is bool,'英雄能力开关无效。')
        opts=m.get('hero_options',{});uid=m['unit_id']
        allowed={'H04':{'recall'}}.get(uid,set())
        check(isinstance(opts,dict) and set(opts)<=allowed,'英雄策略与人物不符。')
        check(opts.get('recall','self') in ('self','pet'),'英雄触发策略无效。')


def configure(game,args):
    from roster_content import PERSONAS
    if args==['catalog']:
        return '\n'.join(uid+' '+PERSONAS[uid]['name']+' · '+PERSONAS[uid]['title']+'｜'+PERSONAS[uid]['role'] for uid in sorted(IDS))
    if not args or args==['list']:
        rows=[]
        for m in game.s['party']+game.s['home_roster']:
            if m['unit_id'] not in IDS:continue
            p=PERSONAS[m['unit_id']]
            rows.append(f"{m['instance_id']} {m['unit_id']} {p['name']}｜Cost{m.get('cost',4)} Lv{m['level']} "
                        f"HP{m['hp']}/{m['stats']['hp']} {'上阵' if m['deployed'] else '预备'}｜{p['role']}")
        return '\n'.join(rows) or '当前没有已取得英雄。'
    if len(args)==2 and args[1]=='info':
        m=game.member(args[0]);check(m['unit_id'] in IDS,'请选择现役英雄。')
        p=PERSONAS[m['unit_id']]
        lines=[p['name']+' · '+p['title']+'｜Cost'+str(m.get('cost',4))+'｜Lv'+str(m['level']),p['background'],
               '动机：'+p['motivation'],'顾虑：'+p['fear'],'定位：'+p['role'],
               '当前面板：'+str(m['stats']),'普攻：'+m['attack_type']+'／'+str(m['range'])+'格／'+str(m['interval'])+'拍',
               '被动 '+p['passive']['name']+'：'+p['passive']['description']]
        lines+=['主动 '+x['id']+' '+x['name']+'：'+x['description'] for x in p['actives']]
        lines+=['长处：'+'；'.join(p['strengths']),'短板：'+'；'.join(p['weaknesses']),
                '关系线索：'+'；'.join(p['relationships']),'武器／防具各1槽；自由技能书2槽。队列与逐项开关：book show/queue/auto。']
        return '\n'.join(lines)
    check(game.s['phase']=='TOWN','英雄策略只在城内配置。')
    check(len(args)==3,'hero ID recall self/pet | power on/off')
    m=game.member(args[0]);check(m['unit_id'] in IDS,'请选择现役英雄。')
    key,value=args[1:];opts=m.setdefault('hero_options',{})
    if key=='power':check(value in ('on','off'),'power on/off用于同面板对照。');m['hero_enabled']=value=='on'
    elif key in ('shield','facing'):raise ValueError('0.62已退役合壁开场／半血和赛琳转向配置；请用book queue/auto安排新技能。')
    elif key=='recall':
        check(m['unit_id']=='H04' and value in ('self','pet'),'薇拉支持 self/pet。')
        check(value=='self' or any(x['unit_id']=='PET-H04' and x['deployed'] for x in game.s['party']),'护兽需已有实际部署的伴兽。');opts[key]=value
    else:raise ValueError('未知英雄策略。')
    game.log('hero_config',member=m['instance_id'],key=key,value=value)


def weak(a,tick):
    from mechanics import weak_active
    return (a.get('boss_part',False) and not a.get('boss_broken',False)) or weak_active(a,tick) or bool(a.get('hero_exposed') and a['hero_exposed']['starts']<=tick<=a['hero_exposed']['expires'] and a.get('weak_point'))


def danger(prior,actors,side,tick):
    return {tuple(p) for v in actors if v['side']!=side and prior.get(v['id']) and prior[v['id']]['kind']=='damage' and tick<=prior[v['id']]['due']<=tick+1 for p in prior[v['id']]['cells']}


def adjacent(pos):return [(pos[0]+dq,pos[1]+dr) for dq,dr in c.DIRS]


def safe_cell(a,b,board,cat,occupied,blocked,unsafe,rear=False):
    import spatial_moves
    options=[p for p in adjacent(a['pos']) if p in board and cat.terrain[board[p]]['walkable'] and p not in occupied and p not in unsafe and not spatial_moves.crossed(a['pos'],p,blocked)]
    if rear:options=[p for p in options if c.direction(a['pos'],p) in {(a['facing']+d)%6 for d in (2,3,4)}]
    return min(options) if options else None


def mirror_path(a,end,mirror,cat,board):
    from mechanics import ray
    pivots=[tuple(a['pos'])]+([tuple(mirror)] if mirror is not None else [])+[tuple(end)]
    if mirror is not None and (c.distance(a['pos'],mirror)>2 or tuple(mirror) not in board or not cat.terrain[board[tuple(mirror)]]['walkable']):return None
    if sum(c.distance(x,y) for x,y in zip(pivots,pivots[1:]))>4:return None
    path=[];low=set()
    for x,y in zip(pivots,pivots[1:]):
        segment=ray(x,y)
        for pos in segment[:-1]:
            if board.get(pos,'HIGH_OBSTACLE')=='HIGH_OBSTACLE':return None
            if board[pos]=='LOW_OBSTACLE':low.add(pos)
        path+=segment
    if len(low)>1 or len(path)!=len(set(path)):return None
    return path


# Authoritative live execution; preserve the exact exported object identities.
from hero_power_v062 import (IDS,DATA,cards,enabled,initialize,choose,movement,release,targets,
    add_shield,shields,attack_bonus,defense,interrupt,hit,healed,moved,end_tick,started,
    start_tick,chain_action,heals,basic_targets,attack_attempt,attack_increase,
    damage_multiplier,damage_reduction,outgoing_factor,incoming_factor,on_kill,targetable,projectile_deflected,should_advance)


def pet_locks(b):
    # Only the actual W0 recall tick occupies the real dog's action. There is
    # no multi-tick support reservation and H08 never locks a recipient.
    return {a['pending']['hero_move_target'] for a in b['actors'] if a['hp']>0 and a.get('pending')
            and a['pending']['move_id']=='H04-B' and a['pending']['due']<=b['tick']
            and a['pending'].get('hero_path') and a['pending'].get('hero_move_target')!=a['id']}


def facing(a,tick,proposed):return proposed


__all__ = (
    'IDS',
    'DATA',
    'cards',
    'enabled',
    'initialize',
    'choose',
    'movement',
    'release',
    'targets',
    'add_shield',
    'shields',
    'attack_bonus',
    'defense',
    'interrupt',
    'hit',
    'healed',
    'moved',
    'end_tick',
    'started',
    'start_tick',
    'chain_action',
    'heals',
    'basic_targets',
    'attack_attempt',
    'attack_increase',
    'damage_multiplier',
    'damage_reduction',
    'outgoing_factor',
    'incoming_factor',
    'on_kill',
    'targetable',
    'projectile_deflected',
    'should_advance',
    'check',
    'validate',
    'configure',
    'weak',
    'danger',
    'adjacent',
    'safe_cell',
    'mirror_path',
    'pet_locks',
    'facing',
)
