"""Developer-only, isolated practice of the three authored build engines.

The session owns copied combat actors. It never calls expedition battle-result
or town settlement hooks, and never grants plans/books to the real inventory.
"""
from copy import deepcopy
from collections import Counter
import hashlib
import json
import campaign
import combat
from data import keyed_rng

EXERCISES={
 'ENG01':{'name':'盾印会心','plans':['PL01','PL07','PL11'],'encounter':'GR02E',
          'stages':{'plan_mark_created':'花盾造印','standard_mark_consumed':'正伤命中耗印','plan_crit_created':'取得后续会心','plan_crit_spent':'后续攻击使用会心'},
          'hint':'让能取得私盾的队员先攻击，再由同伴后续命中耗印；会心用于下一击，不保底暴击。'},
 'ENG02':{'name':'行护折返','plans':['PL08','PL12','PL02'],'encounter':'GR02E',
          'stages':{'plan_shield_created':'真实移动产盾','plan_move_paid':'后续移动花盾','plan_dodge_created':'取得有限闪避窗口'},
          'hint':'需要可走路径与后续普通移动；派生移动不会再次产盾，闪避窗口不保证躲过每次攻击。'},
 'ENG03':{'name':'压拍破防','plans':['PL09','PL10'],'encounter':'INTRO-EN06',
          'stages':{'plan_cast_delayed':'实际延后施法','plan_cast_window':'形成利用窗口','plan_window_spent':'后续攻击消费窗口'},
          'hint':'在钟壳螺施法释放前命中，再用后续攻击消费窗口；过早击倒目标或错过释放时点就接不上。'},
}


def check(ok,text):
    if not ok:raise ValueError(text)


def initialize(game):game.s['drill']={'sequence':0,'active':None,'reports':[]}
def state(game):return game.s['drill']


def world_digest(game):
    world={k:v for k,v in game.s.items() if k not in ('drill','journal','sequence')}
    return hashlib.sha256(json.dumps(world,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def ready(m):return m['hp']>0 and m['injury_days']==0 and m['erosion']<100


def deployment(game,a):
    selected=[m for m in a['members'] if m['deployed']]
    check(bool(selected) and sum(m['cost'] for m in selected)<=game.s['budget']['battle'],'演练部署需符合现有战斗Cost。')
    check(all(ready(m) for m in selected),'倒地、受伤或侵蚀100的队员不能上场；演练不会治疗正式队员。')
    allowed=game.cat.boards['OPEN']['player_deploy_cells'];positions=[tuple(m['position']) for m in selected]
    check(len(set(positions))==len(positions) and all(list(p) in allowed for p in positions),'演练部署格重复或越界；可 drill recommend。')
    return selected


def recommend(game,a):
    # Keep the player's existing deployment when feasible; otherwise fill from
    # actual squad members in a round-robin of unit types, never a trial roster.
    selected=[m for m in a['members'] if m['deployed'] and ready(m)]
    if not selected or sum(m['cost'] for m in selected)>game.s['budget']['battle']:
        groups={}
        for m in a['members']:
            if ready(m):groups.setdefault(m['unit_id'],[]).append(m)
        candidates=[rows[i] for i in range(max(map(len,groups.values()),default=0)) for rows in groups.values() if i<len(rows)]
        selected=[]
        for m in candidates:
            if sum(x['cost'] for x in selected)+m['cost']<=game.s['budget']['battle']:selected.append(m)
    check(selected,'当前随队没有可用队员，先在城镇正常整备。')
    for m in a['members']:m['deployed']=m in selected
    for i,m in enumerate(selected):m.update(position=list(game.cat.formation[i]),facing=1)


def report(a,result=None):
    b=a['battle'];spec=EXERCISES[a['exercise']];counts=Counter(e['type'] for e in b['events']) if b else Counter()
    return {'id':a['id'],'exercise':a['exercise'],'name':spec['name'],
            'result':result or ((b['result'] or 'RUNNING') if b else 'NOT_STARTED'),'ticks':b['tick'] if b else 0,
            'stages':{name:counts[k] for k,name in spec['stages'].items()},
            'events':deepcopy(b['events']) if b else [],'seed':a['seed'],
            'scope':'SAFE_DRILL_NO_WORLD_REWARDS_OR_LEARNING'}


def show_report(row):
    return (f"{row['id']} {row['name']}：演练战果{row['result']}，{row['ticks']}拍。\n"
            +'；'.join(f'{name} {count}次' for name,count in row['stages'].items())
            +'\n以上仅统计本次实际触发，不把胜利等同于组合完整成功；正式人员、资源和日期均不变。')


def describe(game):
    data=state(game);a=data['active']
    if not a:
        lines=['开发组合试验（不开放给玩家）：使用测试队伍及其装备、已配技能书，临时试用指定方案；不带入一次性准备品或下一趟城镇整备。']
        lines.extend(f"{key} {spec['name']} / {','.join(spec['plans'])}：{spec['hint']}" for key,spec in EXERCISES.items())
        lines.append('drill start ENG01；drill report 回看上次结果。演练不耗日、不产资源/经验，不产生伤亡、观察学习或主线事实。')
        return '\n'.join(lines)
    spec=EXERCISES[a['exercise']]
    lines=[f"安全演练 {a['id']} {spec['name']} / {a['stage']}；临时方案{spec['plans']}；固定敌阵{spec['encounter']}，OPEN棋盘。",spec['hint']]
    b=a['battle']
    if b:
        lines.append(f"第{b['tick']}拍；{b['result'] or '尚未结束'}")
        lines.extend(f"{x['side']} {x['id']} {x['kind']} HP{x['hp']}/{x['stats']['hp']} 格{x['pos']}" for x in b['actors'] if not x.get('boss_part'))
        lines.append(show_report(report(a)))
        lines.extend(str(e) for e in b['events'][-6:])
    else:
        lines.extend(f"{'上阵' if m['deployed'] else '预备'} {m['instance_id']} {m['unit_id']} HP{m['hp']} 格{m['position']} {m['stance']}" for m in a['members'])
    lines.append('drill deploy ID on/off；drill place ID q r [朝向]；drill stance ID advance/hold/flank/evade；drill recommend；drill fight；drill step/run [拍数]；drill report；drill exit CONFIRM。布阵只在开战前，每次推进后自动暂停保存；随时退出无损，quit后读取存档继续原拍数。')
    return '\n'.join(lines)


def handle(game,args):
    check(getattr(game,'developer_drills',False) and game.s.get('developer_drill_only'), '完整演练仅限独立开发工具。')
    if not args or args==['status']:return describe(game)
    data=state(game);a=data['active'];action=args[0]
    if action=='report':
        check(args==['report'],'drill report')
        if a:return show_report(report(a))
        return show_report(data['reports'][-1]) if data['reports'] else '尚无演练记录。'
    check(game.s['phase']=='TOWN' and not game.s['finale']['ending'],'演练只在城镇进行，不能代替归城或终战。')
    if action=='start':
        check(len(args)==2 and args[1] in EXERCISES,'drill start ENG01/ENG02/ENG03')
        check(not a,'先 drill exit CONFIRM 结束当前演练；不会覆盖中途存档。')
        check(campaign.active(game) and 'ST-101' in game.s['campaign']['facts'],'先领取委任与真实队伍；独立战斗试验请使用原battle_lab入口。')
        check(not game.s['campaign']['remembrance'],'先结束当前追忆。')
        check(game.s['party'] and sum(m['cost'] for m in game.s['party'])<=game.s['budget']['expedition'],'演练使用符合当前出征预算的实际随队人员。')
        seq=data['sequence']+1
        a={'id':f'DRILL-{seq:04d}','exercise':args[1],'stage':'SETUP',
           'seed':keyed_rng(game.s['campaign_seed'],'safe-drill:'+args[1]).randrange(2**31),
           'members':deepcopy(game.s['party']),'battle':None,'world_sha256':world_digest(game)}
        recommend(game,a);data['sequence']=seq;data['active']=a
        return describe(game)
    check(a,'先选择演练：drill start ENG01/ENG02/ENG03。')
    if action=='exit':
        check(args==['exit','CONFIRM'],'drill exit CONFIRM：退出演练，不更改正式队伍。')
        row=report(a, 'STOPPED' if a['stage']!='FINISHED' else None)
        check(world_digest(game)==a['world_sha256'],'演练期间正式状态发生变化，拒绝无依据结算。')
        data['reports'].append(row);data['active']=None
        return show_report(row)+'\n已返回开发场景选择；不能继续正式周目。'
    if action in ('step','run'):
        check(a['stage']=='RUNNING' and len(args)<=2,'先 drill fight；已结束战斗可回看或退出。')
        count=int(args[1]) if len(args)==2 else (1 if action=='step' else 120)
        check(1<=count<=600,'单次推进1—600拍；达到上限不强行判胜负。')
        for _ in range(count):
            if a['battle']['result']:break
            combat.step(game.cat,a['battle'])
        if a['battle']['result']:a['stage']='FINISHED'
        return describe(game)
    check(a['stage']=='SETUP','开战后不能改布阵；可退出后重新安排。')
    if action=='recommend':
        check(args==['recommend'],'drill recommend');recommend(game,a)
    elif action=='fight':
        check(args==['fight'],'drill fight');deployment(game,a)
        spec=EXERCISES[a['exercise']]
        a['battle']=combat.create(game.cat,game.cat.encounter_for_board(spec['encounter'],'OPEN'),'OPEN',
                                 deepcopy(a['members']),a['seed'],spec['plans'],{})
        a['battle']['learning']['observers']=[]
        a['stage']='RUNNING'
    else:
        check(action in ('deploy','place','stance') and len(args)>=3,'drill deploy/place/stance 队员完整ID 参数')
        m=next((m for m in a['members'] if m['instance_id']==args[1]),None);check(m,'只能使用本次原随队人员。')
        if action=='deploy':
            check(len(args)==3 and args[2] in ('on','off'),'drill deploy ID on/off')
            check(args[2]=='off' or ready(m),'这名队员当前不能上阵。');m['deployed']=args[2]=='on'
            selected=[x for x in a['members'] if x['deployed']]
            check(sum(x['cost'] for x in selected)<=game.s['budget']['battle'],'先取消另一人的部署，不能超过当前预算。')
        elif action=='place':
            check(len(args) in (4,5),'drill place ID q r [朝向0..5]')
            pos=[int(args[2]),int(args[3])];check(pos in game.cat.boards['OPEN']['player_deploy_cells'],'不在OPEN棋盘部署区。')
            facing=int(args[4]) if len(args)==5 else m['facing'];check(0<=facing<=5,'朝向为0..5。')
            m.update(position=pos,facing=facing)
        else:
            check(len(args)==3 and args[2] in ('advance','hold','flank','evade'),'drill stance ID advance/hold/flank/evade')
            m['stance']=args[2]
    return describe(game)


def validate(game):
    data=state(game);check(set(data)=={'sequence','active','reports'},'演练记录结构无效。')
    check(type(data['sequence']) is int and data['sequence']==len(data['reports'])+int(data['active'] is not None),'演练序号或退出回执重复。')
    for i,r in enumerate(data['reports'],1):
        check(r['id']==f'DRILL-{i:04d}' and r['exercise'] in EXERCISES and r['scope']=='SAFE_DRILL_NO_WORLD_REWARDS_OR_LEARNING','演练记录不能冒充正式战报。')
    a=data['active']
    if not a:return
    check(game.s['phase']=='TOWN' and a['exercise'] in EXERCISES and a['id']==f"DRILL-{data['sequence']:04d}",'演练场景与当前状态不符。')
    check(world_digest(game)==a['world_sha256'],'演练改动了正式队伍、资金、日期或剧情状态。')
    transient={'deployed','position','facing','stance'}
    check([{k:v for k,v in m.items() if k not in transient} for m in a['members']]==[{k:v for k,v in m.items() if k not in transient} for m in game.s['party']],'演练不能添加人物或修改原面板、装备与技能库。')
    check(a['stage'] in ('SETUP','RUNNING','FINISHED'),'演练阶段无效。')
    b=a['battle']
    if a['stage']=='SETUP':check(b is None,'准备阶段不能保留已开战对象。')
    else:
        spec=EXERCISES[a['exercise']]
        check(b and b['encounter_id']==spec['encounter'] and b['board_id']=='OPEN' and b['plans']==spec['plans'] and b['seed']==a['seed'],'演练敌阵、方案或种子被改写。')
        check(not b['learning']['observers'],'安全演练不能有正式学习见证者。')
        check((a['stage']=='FINISHED')==bool(b['result']),'演练战果与状态不一致。')
        check([x['id'] for x in b['actors'] if x['side']=='player']==[m['instance_id'] for m in a['members'] if m['deployed']],'演练上阵者与原队不一致。')
