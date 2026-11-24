"""Fixed research quest receipts and the unique Agla assembly transaction.

Terminal experiments are authored narrative interactions, not hardware simulations.
Provenance checks bind fragments to quest receipts; they are not cryptography.
"""
from copy import deepcopy
import campaign
import facilities
import town

FACTS={'RESEARCH_TASKS_COMPLETE','RESEARCH_SERIES_COMPLETE','ST-303','CH3_COMPLETE'}
FRAGMENTS=('KS01','KS02','KS03')


def check(ok,text):
    if not ok:raise ValueError(text)


def initialize(game):
    game.s['research']={'steps':{},'delivery':None,'assembly':None}


def item_spec(game,iid):
    return next(row for row in game.cat.loot['quest_items'] if row['item_id']==iid)


def name(game,iid):
    row=item_spec(game,iid);names=row.get('display_names_by_knowledge')
    if names:return names['after_ST303' if 'ST-303' in game.s['unlocked_facts'] else 'before_ST303']
    return row['name']


def fragment(game,iid,source):
    row=item_spec(game,iid)
    return {'item_id':iid,'task_id':row['task_id'],'save_id':game.s['id'],
            'source':source,'authorization_origin':row['authorization_origin']}


def archive(game):
    """Called only by the actual ST-104 archive delivery, including safe retries."""
    c=game.s['campaign'];r=game.s['research']
    check('ST-104' in c['facts'],'先交存旧档案。')
    if 'archive' not in r['steps']:
        r['steps']['archive']={'fact':'ST-104','evidence':deepcopy(c['facts']['ST-104']['evidence'])}
        c['task_items']['KS01']=fragment(game,'KS01','ST-104')


def reports(game):
    return {uid:deepcopy(game.s['campaign']['returned_reports'][uid])
            for uid in campaign.QUESTS if uid in game.s['campaign']['returned_reports']}


def expected_items(game):
    r=game.s['research'];items={}
    for step,iid,source in (('archive','KS01','ST-104'),('analysis','KS02','Q-KS02')):
        if step in r['steps']:items[iid]=fragment(game,iid,source)
    if r['delivery']:items['KS03']=fragment(game,'KS03','ST303_RESEARCH_DELIVERY')
    if r['assembly']:items['KEY-AGLA']=deepcopy(r['assembly']['item'])
    return items


def missing(game):
    c=game.s['campaign'];recipe=game.cat.loot['agla_recipe'];r=game.s['research'];out=[]
    if facilities.level(game,'lamp_store')<recipe['requires_observatory_level']:out.append('观测站Lv3')
    if facilities.level(game,'armory')<recipe['building_level']:out.append('工坊Lv3')
    if not r['delivery']:out.append('研究交付：research deliver CONFIRM')
    for uid in recipe['requires_awakened_general_ids']:
        if uid+'_AWAKENED' not in c['facts']:out.append(uid+'觉醒（原物/证词齐后 remember '+uid+'）')
    for iid in recipe['requires_fragment_ids']:
        if iid not in c['task_items']:out.append(name(game,iid))
    for key,amount in recipe['materials'].items():
        if game.s['warehouse'].get(key,0)<amount:out.append(f'{key} {game.s["warehouse"].get(key,0)}/{amount}')
    if game.s['bank']['copper']<recipe['copper']:out.append(f'铜币 {game.s["bank"]["copper"]}/{recipe["copper"]}')
    return out


def describe(game):
    if not campaign.active(game):return '研究任务需要 --campaign 自然开局；试验许可不算任务完成。'
    r=game.s['research'];s=r['steps'];facts=game.s['campaign']['facts']
    lines=['研究记录：'+('、'.join(name(game,i) for i in FRAGMENTS if i in game.s['campaign']['task_items']) or '尚无档案片')]
    if 'archive' not in s:lines.append('先完成侦路与旧日志核对，再 quest archive CONFIRM。')
    elif 'analysis' not in s:lines.append('观测站Lv2后 research analyze CONFIRM：解析旧终端。')
    elif 'CH2_COMPLETE' not in facts:lines.append('交齐前两将报告，开启固定研究任务。')
    elif 'correlation' not in s:lines.append('观测站Lv3后 research correlate 队员完整ID CONFIRM：核对一位当前队员与旧终端记录。')
    elif 'isolation' not in s:lines.append('research test CONFIRM：在空闲链路执行隔离验证，不占用队员。')
    elif not r['delivery']:lines.append('四将报告齐全后 research deliver CONFIRM：交付验证结果。')
    else:
        lines.append(f"ST-303已交付；当前指挥预算{game.s['budget']['expedition']}/{game.s['budget']['battle']}。agla status 查看合成缺项。")
        lines.append('培养舱生命支持独立于实验网络；魔王是管理员的迭代候选，具有同源竞争资格。')
    return '\n'.join(lines)


def agla_status(game):
    if not campaign.active(game):return describe(game)
    if not game.s['research']['delivery']:return describe(game)+'\n完成最终研究交付后可查看应急载体的制造条件。'
    if game.s['research']['assembly']:return 'Agla已合成；当前'+('封存在城镇' if game.s['finale']['sealed'] else '自动携带')+'。不占背包、不可出售或丢弃，三片来源保留。finale status 查看终战准备。'
    recipe=game.cat.loot['agla_recipe']
    return (f"Agla：{recipe['materials']}＋{recipe['copper']}铜，0行动日；不消耗觉醒或因子。\n"
            +'缺项：'+('；'.join(missing(game)) or '无，可 agla craft CONFIRM'))


def handle(game,command,args):
    if args in ([],['status'],['quote']):return agla_status(game) if command=='agla' else describe(game)
    check(campaign.active(game),'研究必须来自自然开局中的真实任务。')
    s=game.s;c=s['campaign'];r=s['research'];steps=r['steps'];facts=c['facts']
    check(s['phase']=='TOWN' and not c['remembrance'],'请先回城并结束追忆。')
    check(not s['debug_tainted'],'调试污染档不能交付正式研究。')
    validate(game)
    if command=='agla':
        check(args==['craft','CONFIRM'],'agla status / agla craft CONFIRM')
        if r['assembly']:return agla_status(game)
        check(r['delivery'],'先完成最终研究交付。')
        check(not missing(game),'尚缺：'+'；'.join(missing(game)))
        recipe=game.cat.loot['agla_recipe']
        for key,amount in recipe['materials'].items():s['warehouse'][key]-=amount
        s['bank']['copper']-=recipe['copper']
        item={'item_id':'KEY-AGLA','save_id':s['id'],'recipe_id':'RC-AGLA','carried':True,
              'fragments':{i:deepcopy(c['task_items'][i]) for i in FRAGMENTS}}
        r['assembly']={'item':item,'paid':{'materials':deepcopy(recipe['materials']),'copper':recipe['copper']},
                       'day':s['day'],'awakened':list(recipe['requires_awakened_general_ids']),
                       'workshop_level':facilities.level(game,'armory'),'action_days':0}
        c['task_items']['KEY-AGLA']=deepcopy(item)
        game.log('agla_assembled',receipt=r['assembly'])
        return agla_status(game)
    action=args[0]
    if action=='correlate':
        check(len(args)==3 and args[2]=='CONFIRM','research correlate 队员完整ID CONFIRM')
    else:check(args==[action,'CONFIRM'] and action in ('analyze','test','deliver'),'research analyze/test/deliver CONFIRM')
    step={'analyze':'analysis','correlate':'correlation','test':'isolation'}.get(action)
    if step in steps:return '该项已完成，沿用原回执。\n'+describe(game)
    if action=='deliver' and r['delivery']:return '研究已交付，不重复发放。\n'+describe(game)
    check('archive' in steps,'先 quest archive CONFIRM，取得旧档案片。')
    if action=='analyze':
        check(facilities.level(game,'lamp_store')>=2,'解析需要观测站Lv2，A/B分支均可。')
        steps['analysis']={'source_fragment':deepcopy(c['task_items']['KS01']),
                           'observatory_level':facilities.level(game,'lamp_store'),
                           'terminal_log':'READ_ONLY_DURING_RUN;MAINTENANCE_AFTER_COMPLETION'}
        c['task_items']['KS02']=fragment(game,'KS02','Q-KS02')
        text='许苇完成旧终端解析：运行时只读，维护须等本轮结束。取得旧终端解析片。'
    else:
        check('analysis' in steps and 'CH2_COMPLETE' in facts,'需先完成终端解析及前两将战后报告。')
        check(facilities.level(game,'lamp_store')>=3,'需要已竣工的观测站Lv3。')
        if action=='correlate':
            iid=args[1];m=next((m for m in s['party'] if m['instance_id']==iid),None)
            check(m is not None and m['unit_id']!='PET-H04','选择当前队伍中的人类队员完整ID；不能使用随兽、被俘者或纪念名册。')
            steps['correlation']={'member_id':iid,'unit_id':m['unit_id'],'source_fragment':deepcopy(c['task_items']['KS02']),
                                  'reports':{uid:reports(game)[uid] for uid in ('MG01','MG02')}}
            text=f'已核对队员{iid}与旧终端的唯一编号；记录封存，待隔离验证与四将报告齐全后共同解读。'
        elif action=='test':
            check('correlation' in steps,'先核对一位当前队员的记录。')
            steps['isolation']={'source':'fixed_idle_link_test','occupied_subjects':[],
                                'experiment_permission':'REVOKED_ON_IDLE_LINK',
                                'life_support':['breathing','nutrition','mechanical_door_control'],
                                'result':'INDEPENDENT_CONTROLS_PRESERVED'}
            campaign.fact(game,'RESEARCH_TASKS_COMPLETE',deepcopy(steps))
            text='空闲链路验证通过：撤销测试端权限后，三路独立控制仍正常。未使用队员、未增加因子或行动日。'
        else:
            check('CH3_BATTLES_COMPLETE' in facts and 'RESEARCH_TASKS_COMPLETE' in facts,'还需四将战后报告与固定研究任务。')
            r['delivery']={'batch_id':'ST303_RESEARCH_DELIVERY','reports':reports(game),
                           'steps':deepcopy(steps),'observatory_level':facilities.level(game,'lamp_store')}
            c['task_items']['KS03']=fragment(game,'KS03','ST303_RESEARCH_DELIVERY')
            campaign.deliver(game,'ST-303',r['delivery'])
            campaign.fact(game,'RESEARCH_SERIES_COMPLETE',{'batch_id':r['delivery']['batch_id']})
            campaign.fact(game,'CH3_COMPLETE',{'delivery':'ST-303'})
            text=('许苇展示对应矩阵：这里是虚拟实验场；舱位仍在，不等于原人格仍在。'
                  '空闲链路验证表明，撤销实验与收割权限不会停止呼吸、营养和舱门机械控制。'
                  '旧人类的独立舱控授权可装入应急程序，虚拟域权限不能代签。\n'
                  '魔王是管理员的迭代候选，具有同源竞争资格；候选运行期间直接维护被隔离，须等待进程结束回执。'
                  '本次同时取得校验片并完成ST-303；预算20/15。未自动制造Agla，也未进入终战。')
    game.log('research_action',action=action)
    return text


def validate(game):
    r=game.s['research'];steps=r['steps']
    check(set(r)=={'steps','delivery','assembly'} and set(steps)<={'archive','analysis','correlation','isolation'},'研究记录结构无效。')
    if not campaign.active(game):
        check(not steps and not r['delivery'] and not r['assembly'],'试验许可不能生成真实研究回执。');return
    c=game.s['campaign'];facts=c['facts']
    check(('ST-104' in facts)==('archive' in steps),'旧档案交存与封存档案片回执不一致。')
    if 'archive' in steps:
        check('ST-104' in facts and steps['archive']=={'fact':'ST-104','evidence':facts['ST-104']['evidence']},'档案片缺少真实交存。')
    if 'analysis' in steps:
        a=steps['analysis']
        check('archive' in steps and facilities.level(game,'lamp_store')>=2 and a=={
            'source_fragment':fragment(game,'KS01','ST-104'),'observatory_level':a['observatory_level'],
            'terminal_log':'READ_ONLY_DURING_RUN;MAINTENANCE_AFTER_COMPLETION'} and a['observatory_level'] in (2,3),'终端解析回执或来源无效。')
    if 'correlation' in steps:
        a=steps['correlation'];all_members=town.roster(game)+game.s['memorial']
        check('analysis' in steps and 'CH2_COMPLETE' in facts and facilities.level(game,'lamp_store')>=3,'记录核对缺少研究前置。')
        check(any(m['instance_id']==a['member_id'] and m['unit_id']==a['unit_id']!='PET-H04' for m in all_members),'核对对象缺少原名册去向。')
        check(a['source_fragment']==fragment(game,'KS02','Q-KS02') and a['reports']=={u:reports(game)[u] for u in ('MG01','MG02')},'核对缺少来源片或两将报告。')
    check(('RESEARCH_TASKS_COMPLETE' in facts)==('isolation' in steps),'研究完成事实与试验回执不一致。')
    if 'isolation' in steps:
        check('correlation' in steps and steps['isolation']=={'source':'fixed_idle_link_test','occupied_subjects':[],
            'experiment_permission':'REVOKED_ON_IDLE_LINK','life_support':['breathing','nutrition','mechanical_door_control'],
            'result':'INDEPENDENT_CONTROLS_PRESERVED'},'空闲链路试验不完整。')
        check(facts['RESEARCH_TASKS_COMPLETE']['evidence']==steps,'研究事实与步骤证据不一致。')
    for key in ('ST-303','CH3_COMPLETE','RESEARCH_SERIES_COMPLETE'):
        check((key in facts)==bool(r['delivery']),'研究批次部分写入：'+key)
    if r['delivery']:
        check('CH3_BATTLES_COMPLETE' in facts and 'isolation' in steps,'最终交付缺少四将报告或研究完成。')
        check(r['delivery']=={'batch_id':'ST303_RESEARCH_DELIVERY','reports':reports(game),'steps':steps,'observatory_level':3},'研究交付证据不一致。')
        check(facts['ST-303']['evidence']==r['delivery'] and facts['CH3_COMPLETE']['evidence']=={'delivery':'ST-303'} and
              facts['RESEARCH_SERIES_COMPLETE']['evidence']=={'batch_id':'ST303_RESEARCH_DELIVERY'},'研究事实来源不一致。')
    if r['assembly']:
        a=r['assembly'];recipe=game.cat.loot['agla_recipe']
        check(r['delivery'] and facilities.level(game,'armory')==3 and all(u+'_AWAKENED' in facts for u in campaign.QUESTS),'Agla缺少真实资格。')
        check(a['item']=={'item_id':'KEY-AGLA','save_id':game.s['id'],'recipe_id':'RC-AGLA','carried':True,
                         'fragments':{i:fragment(game,i,source) for i,source in zip(FRAGMENTS,('ST-104','Q-KS02','ST303_RESEARCH_DELIVERY'))}},'Agla唯一实例或片段来源无效。')
        check(a['paid']=={'materials':recipe['materials'],'copper':recipe['copper']} and a['action_days']==0 and
              a['workshop_level']==3 and a['awakened']==recipe['requires_awakened_general_ids'],'Agla合成回执无效。')
    actual={k:v for k,v in c['task_items'].items() if k in (*FRAGMENTS,'KEY-AGLA')}
    check(actual==expected_items(game),'研究任务原物与取得回执不一致。')
