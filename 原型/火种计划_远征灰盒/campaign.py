"""Real campaign receipts; fixture permissions never count as completed quests."""
from copy import deepcopy
import re
from data import keyed_rng
import town
import bosses

HEROES=tuple(f'H{i:02}' for i in range(1,13))
NAMES=dict(zip(HEROES,('洛恩','米拉','莉安','薇拉','赫铎','赛琳','陆衡','陶岑','闻笺','阮钧','祁岚','殷砚')))
QUESTS={
 'MG01':dict(gate='ST-101',item='裂口铜哨',cost={'copper':4},
   record='沈砚介绍你到修钟匠处查阅旧巡逻名册和寄存单。铜哨裂口与登记相符。',
   witness='秦姨核对旧照片：阿铎曾吹集合哨叫厨房开饭，哨口的缺口早在那时就有。'),
 'MG02':dict(gate='ST-104',item='缝补红围巾',cost={'fiber':2},
   record='秦姨展示旧衣认领单与缝补顺序；保管人签名和红围巾的针脚吻合。',
   witness='曾受援的镇民当面指认那道后补的针脚，并与认领单逐项核对。'),
 'MG03':dict(gate='ST-104',item='缺页药簿',cost={'herb':2},
   record='医舍的誊药委托附有镇民寄存记录；缺页的页码与捐赠条目可以接上。',
   witness='医舍保管人与捐药镇民共同核对页码：怕黑、空腹禁药和捎信的嘱托确实出自同一本药簿。'),
 'MG04':dict(gate='CH2_COMPLETE',item='刻名扳手',cost={'iron':2},
   record='秦姨取出工具归还单，刻名和借用日期与扳手相符。',
   witness='最后保管人到场核对借用单，确认刻名、交接日期与工具上的修补痕。'),
}


def check(ok,message):
    if not ok:raise ValueError(message)


def active(game):return bool(game.s.get('campaign'))


def initialize(game):
    s=game.s
    s.update(party=[],home_roster=[],bank=dict(copper=0,crystal=0,supply=0),
             warehouse={},unlocked_facts=[],workshop_level=0,
             budget=dict(milestone='UNCOMMISSIONED',expedition=8,battle=6),
             fixture_notice='自然开局：任务事实与真实名册；无试验装备、材料或建筑赠送。',
             team_id='CAMPAIGN',boss_evidence={'items':[],'verified_testimonies':[]},boss_records={})
    s['campaign']={'facts':{},'quests':{},'task_items':{},'testimonies':{},'seals':0,
                   'ever_recruited_hero_ids':[],'summon_sequence':0,'summons':{},
                   'companion':None,'challenge':None,'victories':{},'returned_reports':{},
                   'remembrance':None,'initial_roster_seed':s['campaign_seed']}
    fact(game,'ST-000',{'source':'new_campaign','text':'暮汀北门独返；旧名册记着失踪者。'})


def fact(game,key,evidence):
    c=game.s['campaign']
    if key in c['facts']:return False
    c['facts'][key]={'day':game.s['day'],'expedition':game.s['expedition_no'],'evidence':deepcopy(evidence)}
    game.s['unlocked_facts'].append(key)
    budgets=[b for b in game.cat.rules['command_budgets'] if b['milestone'] in c['facts']]
    if budgets:game.s['budget']=deepcopy(budgets[-1])
    game.log('campaign_fact',fact=key,evidence=evidence)
    return True


def member(game,uid,iid,index=0,initial=False):
    bases={x['id']:x for x in game.cat.rules['units'].values()}
    bases.update(game.cat.rules['hero_templates']);bases['PET-H04']=game.cat.rules['companion_template']
    base=bases[uid]
    rng=keyed_rng(game.s['campaign']['initial_roster_seed'],'initial_roster_seed:'+iid)
    stats=deepcopy(base['stats']) if 'stats' in base else {k:rng.randint(*v) for k,v in base['ranges'].items()}
    return dict(instance_id=iid,unit_id=uid,stats=stats,birth_stats=deepcopy(stats),hp=stats['hp'],
                level=1,xp=0,injury_days=0,erosion=0,cost=4 if uid in HEROES else 1,
                gear=[],gear_instances=[],deployed=False,position=list(game.cat.formation[index]),
                stance='advance',facing=1,attack_type=base['attack_type'],range=base['range'],interval=base['interval'],
                **{k:base[k] for k in ('basic_medium','locomotion') if k in base},
                acquisition='initial_commission' if initial else 'hero_seal' if uid in HEROES else 'companion_registration')


def deliver(game,key,evidence):
    if not fact(game,key,evidence):return
    c=game.s['campaign'];c['seals']+=game.cat.rules['recruitment']['milestone_seals'].get(key,0)
    import book_rewards
    book_rewards.first_delivery(game,key)
    if key=='ST-104':fact(game,'CH1_COMPLETE',{'delivery':key})
    if {'ST-201','ST-202'}<=c['facts'].keys():fact(game,'CH2_COMPLETE',{'reports':['ST-201','ST-202']})
    if {'ST-201','ST-202','ST-301','ST-302'}<=c['facts'].keys():
        fact(game,'CH3_BATTLES_COMPLETE',{'reports':['ST-201','ST-202','ST-301','ST-302']})


def sync_evidence(game):
    c=game.s['campaign']
    game.s['boss_evidence']={'items':sorted(i for i in c['task_items'] if i.startswith('OBS-')),'verified_testimonies':sorted(c['testimonies'])}


def install(cat):
    # Each dedicated hunt still traverses a normal two-region expedition.
    for i,g in enumerate(cat.rules['generals']):
        gate='ST-104' if i<2 else 'CH2_COMPLETE'
        cat.config['routes'].append(dict(route_id='HUNT-'+g['general_id'],chapter=2 if i<2 else 3,
            facts=['ST-101','ST-102','ST-104']+([] if i<2 else ['CH2_COMPLETE']),profile='SHORT',
            selected_path=['RG06' if i==1 else 'RG07',g['region_id']],general_id=g['general_id'],gate=gate))


def bind_challenge(game,manifest):
    if not active(game):return
    c=game.s['campaign'];uid=c['challenge']
    if not uid:return
    check(uid not in c['victories'],'魔将已有真实击败记录；使用 remember 追忆。')
    g=next(g for g in game.cat.rules['generals'] if g['general_id']==uid)
    check(manifest['target']==g['region_id'],'讨伐目标和路线终点不一致；重新选择 challenge。')
    binding=manifest['regions'][g['region_id']]['encounters']['G']
    previous=deepcopy(binding)
    binding.clear();binding.update(encounter_id='BATTLE-'+uid,board_id=bosses.ENCOUNTERS['BATTLE-'+uid])
    manifest['challenge']={'general_id':uid,'replaces':previous,'slot':'G','region':g['region_id'],
                           'extra_ordinary_goal':False,'reward_policy':'existing_goal_allocation_only'}
    from joint_sampling_model import digest
    manifest.pop('manifest_sha256',None);manifest['manifest_sha256']=digest(manifest)


def after_battle(game,battle):
    if not active(game) or game.s['debug_tainted']:return
    c=game.s['campaign']
    for uid,receipt in battle.get('boss_receipts',{}).items():
        if uid not in QUESTS:continue
        if uid not in c['victories']:
            c['victories'][uid]={'battle':deepcopy(battle),'expedition':game.s['expedition_no']}
        game.s['boss_records'][uid]=deepcopy(receipt)
        fact(game,uid+'_DEFEATED',{'battle_id':battle['battle_id']})
        if receipt['awakened']:fact(game,uid+'_AWAKENED',{'battle_id':battle['battle_id']})


def on_return(game):
    if not active(game) or game.s['debug_tainted']:return
    c=game.s['campaign']
    # Recorded intel survives an ordinary loss, but first delivery waits for a safe return.
    for uid,v in c['victories'].items():
        c['returned_reports'].setdefault(uid,{'battle_id':v['battle']['battle_id'],
                         'settlement_id':game.s['last_settlement_id'],'day':game.s['day']})
    import story_mission
    story_mission.on_return(game)


def handle(game,command,args):
    check(active(game),'任务与应召使用 --campaign 自然开局；试验队许可不能冒充任务回执。')
    s=game.s;c=s['campaign']
    if command=='quest' and (not args or args==['status']):return describe(game)
    check(s['phase']=='TOWN','请在真实归城结算后使用 town 进入整备。')
    check(not s['debug_tainted'],'该档已使用调试胜利，不能生成真实任务／人物获取凭据。')
    if c['remembrance'] and command!='remember':raise ValueError('先完成或关闭当前追忆：remember close。')
    if command=='summon':
        check(len(args)==2 and args[1]=='CONFIRM','summon 请求ID CONFIRM；随机应召一名未曾获得的英雄。')
        oid=args[0];check(re.fullmatch(r'[A-Za-z0-9_-]{1,64}',oid),'请求ID使用1—64位字母、数字、下划线或短横线。')
        if oid in c['summons']:return '既有应召回执：'+str(c['summons'][oid])
        pool=[uid for uid in HEROES if uid not in c['ever_recruited_hero_ids']]
        check(pool,'十二名英雄均已应召过；离队、被俘或永久损失不会重入池。')
        check(c['seals']>=1,'需要1枚应召印。')
        seq=c['summon_sequence']+1;uid=keyed_rng(s['campaign_seed'],f'hero-summon:{seq}').choice(pool)
        m=member(game,uid,'HERO-'+uid);s['home_roster'].append(m)
        c['seals']-=1;c['summon_sequence']=seq;c['ever_recruited_hero_ids'].append(uid)
        c['summons'][oid]={'sequence':seq,'hero_id':uid,'instance_id':m['instance_id'],'seal_cost':1,'pool':pool}
        import save_validation
        save_validation.enroll(game,m,'SUMMON',oid)
        game.log('hero_summoned',request=oid,receipt=c['summons'][oid])
        text=f'{NAMES[uid]}（{uid}）已应召，在城镇待命；Lv1，Cost4。'
        if uid=='H07':
            from commander import INTRO
            text+='\n'+INTRO+'\n指挥只支援S01/S02/S03普通士兵；与佣兵、英雄或伴兽同行不会把它们算作士兵。'
        elif uid in ('H08','H09','H10','H11','H12'):
            from roster_content import PERSONAS
            p=PERSONAS[uid];text+='\n'+p['background']+'\n'+p['motivation']+'\n'+p['role']
        return text
    if command=='companion':
        check(args==['register','CONFIRM'],'companion register CONFIRM：灰鬃犬免费登记，Cost1、独立名额。')
        if c['companion']:return '既有随兽登记：'+str(c['companion'])
        check('H04' in c['ever_recruited_hero_ids'],'薇拉尚未实际应召。')
        check(any(m['unit_id']=='H04' for m in town.available(game)),'薇拉须实际在城中或队伍中办理登记。')
        m=member(game,'PET-H04','COMPANION-H04');s['home_roster'].append(m)
        c['companion']={'instance_id':m['instance_id'],'owner':'H04','cost':0,'day':s['day']}
        import save_validation
        save_validation.enroll(game,m,'COMPANION','H04')
        game.log('companion_registered',receipt=c['companion']);return '灰鬃犬已登记；未消耗应召印。'
    if command=='challenge':
        if args==['cancel']:
            c['challenge']=None;s['route']='R01';return '已取消尚未出发的讨伐。'
        check(len(args)==1 and args[0] in QUESTS,'challenge MG01/MG02/MG03/MG04；选定后 depart。')
        uid=args[0];gate='ST-104' if uid in ('MG01','MG02') else 'CH2_COMPLETE'
        check(gate in c['facts'],'尚未完成前置：'+gate)
        check(uid not in c['victories'],'已击败；使用 remember，不重复生成物资或首交奖励。')
        c['challenge']=uid;s['route']='HUNT-'+uid
        return '已选择两区域讨伐，终点G替换为该魔将；depart 出发，途中可合法早返。'
    if command=='remember':return remembrance(game,args)
    check(command=='quest' and args,'quest status / commission / review / archive / report / MG01..MG04')
    action=args[0]
    if action=='commission':
        check(args==['commission','CONFIRM'],'quest commission CONFIRM：一次性领取委任与初始名册。')
        if 'ST-101' in c['facts']:return '委任已领取；沿用现有名册与资产。'
        units=['S01']*3+['S02']*3+['S03']*2;counts={}
        for i,uid in enumerate(units):
            counts[uid]=counts.get(uid,0)+1
            m=member(game,uid,f'INIT-{uid}-'+chr(64+counts[uid]),i,True)
            s['party'].append(m)
            import save_validation
            save_validation.enroll(game,m,'COMMISSION','ST-101:'+str(i+1))
        s['bank'].update(copper=60,crystal=12,supply=6)
        fact(game,'ST-101',{'source':'commission','initial_ids':[m['instance_id'] for m in s['party']],
                          'initial_roster_seed':c['initial_roster_seed'],'resources':deepcopy(s['bank'])})
        return '已配发3盾、3近、2弓及60铜/12晶/6补给。tutorial recommend CONFIRM 可采用建议部署。'
    if action=='review':
        check(args==['review','CONFIRM'],'quest review CONFIRM：与许苇核对实际调查及旧日志。')
        check('ST-102' in c['facts'],'尚未交回完整调查；在教学地图D使用 tutorial observe 后安全归城。')
        observation=c['facts']['ST-102']['evidence']['observation']
        fact(game,'ST-103',{'source':'witnessed_field_observation_compared_with_old_log','observation':observation})
        return '许苇把现场次序与旧日志逐项对照：相似，但还不能判断谁在重复谁；未记录候选学习成果。'
    if action=='archive':
        check(args==['archive','CONFIRM'],'quest archive CONFIRM：交存侦路报告与旧名册核对记录。')
        check({'ST-102','ST-103'}<=c['facts'].keys(),'需实际完成ST-102和ST-103。')
        deliver(game,'ST-104',{'source':'archive_delivery','prerequisites':['ST-102','ST-103']})
        import research
        research.archive(game)
        return '档案中四个名字被同色墨覆盖；取得封存档案片。秦姨提供铜哨寄存线索，实物仍需付费取回。首交1印与基础技能书自选权益，出征/战斗预算12/8。'
    if action=='report':
        check(len(args)==3 and args[1] in QUESTS and args[2]=='CONFIRM','quest report MG01 CONFIRM')
        uid=args[1];check(uid in c['returned_reports'],'缺实际胜利及安全归城记录；不能仅凭许可或追忆领取。')
        g=next(g for g in game.cat.rules['generals'] if g['general_id']==uid)
        deliver(game,g['defeat_fact'],c['returned_reports'][uid]);return '报告已交存；首交奖励仅结算一次。'
    check(action in QUESTS,'未知委托；quest status 查看。')
    uid=action;q=QUESTS[uid]
    check(q['gate'] in c['facts'],'委托尚未开放：'+q['gate'])
    check(len(args)>=2,'quest '+uid+' record / witness / collect CONFIRM')
    stage=args[1];check(stage in ('record','witness','collect'),'委托步骤为record、witness、collect。')
    check(args==[uid,stage]+(['CONFIRM'] if stage=='collect' else []),'参数不符；只有collect需CONFIRM。')
    row=c['quests'].setdefault(uid,{})
    if stage in row:return '已有步骤回执：'+str(row[stage])
    if stage=='record':row[stage]={'day':s['day'],'text':q['record']}
    elif stage=='witness':
        check('record' in row,'先查阅登记，才能逐项核实证词。')
        row[stage]={'day':s['day'],'text':q['witness']};c['testimonies'][uid]=deepcopy(row[stage])
    else:
        check({'record','witness'}<=row.keys(),'先完成查阅登记与证词核实。')
        check(uid not in s['original_recovery']['targets'],'已选择现场自取；请从线索册的固定地点取回同件原物，不重复代领。')
        for k,v in q['cost'].items():check((s['bank'] if k=='copper' else s['warehouse']).get(k,0)>=v,'实际库存不足：'+str(q['cost']))
        for k,v in q['cost'].items():(s['bank'] if k=='copper' else s['warehouse'])[k]-=v
        row[stage]={'day':s['day'],'paid':deepcopy(q['cost']),'item':'OBS-'+uid,'name':q['item']}
        c['task_items']['OBS-'+uid]=deepcopy(row[stage])
    sync_evidence(game);game.log('obsession_quest_step',quest='Q-OBS-'+uid,stage=stage,receipt=row[stage])
    return str(row[stage])


def remembrance(game,args):
    c=game.s['campaign'];session=c['remembrance']
    if args==['close']:
        c['remembrance']=None;return '已退出追忆，已提交选择保留；没有新战斗、报酬或行动日。'
    if len(args)==1 and args[0] in QUESTS:
        uid=args[0];check(not session,'请先完成或关闭当前追忆。')
        check(uid in c['victories'],'需先真实击败该魔将。')
        sync_evidence(game);context=game.s['boss_evidence']
        check('OBS-'+uid in context['items'] and uid in context['verified_testimonies'],'仍缺原物或已核实证词。')
        b=deepcopy(c['victories'][uid]['battle']);m=b['boss_memory'][uid]
        m.update(eligible=True,source=deepcopy(context));bosses.recall(b)
        if not bosses.paused(b):return '该魔将的两次记忆选择已经完成。'
        c['remembrance']={'general_id':uid,'battle':b};return bosses.describe(b)
    check(session and len(args)==2,'remember MG01；remember evidence/retain/skip MG01-W1；remember close')
    b=session['battle'];uid=session['general_id'];bosses.dialogue(b,args[0],args[1])
    c['victories'][uid]['battle']=deepcopy(b)
    # The saved victory must remain a settled snapshot; only the session owns its queue.
    c['victories'][uid]['battle']['boss_dialogue_queue']=[]
    game.s['boss_records'][uid]=deepcopy(b['boss_receipts'][uid])
    if b['boss_receipts'][uid]['awakened']:fact(game,uid+'_AWAKENED',{'source':'remembrance','battle_id':b['battle_id']})
    text=bosses.describe(b)
    if not bosses.paused(b):c['remembrance']=None
    return text


def describe(game):
    if not active(game):return ''
    c=game.s['campaign'];s=game.s
    lines=['任务事实：'+', '.join(c['facts']),f"应召印 {c['seals']}；曾应召 {c['ever_recruited_hero_ids']}；任务原物 {list(c['task_items'])}",
           f"当前讨伐 {c['challenge'] or '无'}；已击败 {list(c['victories'])}；可交报告 {list(c['returned_reports'])}"]
    for uid,q in QUESTS.items():
        stages=c['quests'].get(uid,{})
        lines.append(f"{uid} {q['item']}："+('未开放（'+q['gate']+'）' if q['gate'] not in c['facts'] else ', '.join(stages) or '可查阅登记')+f"；取回成本{q['cost']}")
    if 'ST-101' not in c['facts']:lines.append('下一步：quest commission CONFIRM')
    elif 'ST-102' not in c['facts']:lines.append('下一步：tutorial recommend CONFIRM；tutorial start（远眺D处 tutorial observe，清除两战后安全归城）')
    elif 'ST-103' not in c['facts']:lines.append('下一步：quest review CONFIRM')
    elif 'ST-104' not in c['facts']:lines.append('下一步：quest archive CONFIRM')
    else:lines.append('应召：summon 请求ID CONFIRM；讨伐：challenge MG01；报告：quest report MG01 CONFIRM；追忆：remember MG01')
    if c['remembrance']:lines.append(bosses.describe(c['remembrance']['battle']))
    import research
    lines.append(research.describe(game))
    return '\n'.join(lines)


def validate(game):
    if not active(game):return
    c=game.s['campaign'];s=game.s
    import research
    import finale
    known=research.FACTS|finale.FACTS|{'ST-000','ST-101','ST-102','ST-103','ST-104','ST-201','ST-202','ST-301','ST-302',
           'CH1_COMPLETE','CH2_COMPLETE','CH3_BATTLES_COMPLETE'}|{u+k for u in QUESTS for k in ('_DEFEATED','_AWAKENED')}
    check(set(c['facts'])<=known,'出现本模块未完成的章节事实。')
    check(set(s['unlocked_facts'])==set(c['facts']),'自然开局许可与任务事实不一致。')
    expected_budget=[b for b in game.cat.rules['command_budgets'] if b['milestone'] in c['facts']]
    if expected_budget:check(s['budget']==expected_budget[-1],'指挥预算与实际章节不一致。')
    import book_rewards
    check(set(s['book_rewards']['deliveries'])==book_rewards.DELIVERY_FACTS&set(c['facts']),'新版首交书权益与章节不一致。')
    ever=c['ever_recruited_hero_ids'];rows=list(c['summons'].values())
    check(len(ever)==len(set(ever)) and set(ever)<=set(HEROES),'英雄永久去重记录无效。')
    check(c['summon_sequence']==len(rows)==len(ever),'应召序号或回执数量不一致。')
    check(sorted(r['sequence'] for r in rows)==list(range(1,len(rows)+1)),'应召序号不连续。')
    check({r['hero_id'] for r in rows}==set(ever),'应召回执与曾获得名单不一致。')
    earned=sum(v for k,v in game.cat.rules['recruitment']['milestone_seals'].items() if k in c['facts'])
    check(type(c['seals']) is int and c['seals']==earned-len(rows)>=0,'应召印余额与首交／应召账不一致。')
    pool=list(HEROES)
    for r in sorted(rows,key=lambda r:r['sequence']):
        expected=keyed_rng(s['campaign_seed'],f"hero-summon:{r['sequence']}").choice(pool)
        check(r['pool']==pool and r['hero_id']==expected and r['instance_id']=='HERO-'+expected and r['seal_cost']==1,'应召结果与固定抽取序列不一致。')
        pool.remove(expected)
    all_members=town.roster(game)+s['memorial'];ids=[m['instance_id'] for m in all_members]
    check(not any(m['unit_id']=='CMD' for m in all_members),'旧CMD测试位不能进入正常周目；指挥英雄使用实际应召的H07。')
    check(len(ids)==len(set(ids)),'名册存在重复实例。')
    if 'ST-101' in c['facts']:
        grant=c['facts']['ST-101']['evidence']
        check(grant['source']=='commission' and len(set(grant['initial_ids']))==8 and set(grant['initial_ids'])<=set(ids),'初始配发缺少唯一原始成员或去向记录。')
    if 'ST-102' in c['facts']:
        delivery=c['facts']['ST-102']['evidence']
        reports=s['battle_reports']+[b for trip in s['completed_history'] for b in trip['battle_reports']]
        wins={(b['encounter_id'],b['battle_id']) for b in reports if b['result']=='VICTORY' and not b.get('debug_tainted')}
        check(set(delivery['battles'])=={'INTRO-EN01','TUT01-ROOT'} and set(delivery['battles'].items())<=wins,'侦路交付缺少两场真实胜利记录。')
        check(delivery['observation']['site']=='D' and delivery['observation']['source']=='fixed_observation_task','侦路缺少实际远眺调查。')
        settlements=[s['summary']]+[trip['summary'] for trip in s['completed_history']]
        check(any(r and r.get('settlement_id')==delivery['settlement_id'] and r.get('result')!='DEFEAT' for r in settlements),'侦路缺少安全归城回执。')
    if 'ST-103' in c['facts']:
        check('ST-102' in c['facts'] and c['facts']['ST-103']['evidence']['observation']==c['facts']['ST-102']['evidence']['observation'],'旧日志核对缺少实际调查。')
    for uid in ever:check(sum(m['unit_id']==uid for m in all_members)==1,'曾应召英雄缺少唯一现役／损失记录。')
    check(not any(m['unit_id'] in HEROES and m['unit_id'] not in ever for m in all_members),'英雄缺少实际应召回执。')
    if c['companion']:check(sum(m['unit_id']=='PET-H04' for m in all_members)==1 and 'H04' in ever,'随兽登记与名册不符。')
    else:check(not any(m['unit_id']=='PET-H04' for m in all_members),'随兽缺少登记。')
    expected_items={};testimonies={}
    for uid,row in c['quests'].items():
        check(uid in QUESTS and QUESTS[uid]['gate'] in c['facts'],'委托或前置无效。')
        if 'witness' in row:check('record' in row,'证词缺少查阅登记。');testimonies[uid]=row['witness']
        if 'collect' in row:
            check('witness' in row and row['collect']['paid']==QUESTS[uid]['cost'] and row['collect']['item']=='OBS-'+uid,'原物缺少核实或支付回执。')
            expected_items['OBS-'+uid]=row['collect']
    check(c['task_items']==dict(expected_items,**research.expected_items(game)) and c['testimonies']==testimonies,'原物／证词与委托回执不一致。')
    check(s['boss_evidence']=={'items':sorted(expected_items),'verified_testimonies':sorted(testimonies)},'魔将证据与真实任务来源不一致。')
    for uid,v in c['victories'].items():
        b=v['battle'];bosses.validate(b)
        check(b['result']=='VICTORY' and not b.get('debug_tainted') and uid in b['boss_receipts'],'魔将记录缺少真实胜利。')
        check(uid+'_DEFEATED' in c['facts'],'击败事实缺失。')
    for uid,r in c['returned_reports'].items():
        check(uid in c['victories'] and r['battle_id']==c['victories'][uid]['battle']['battle_id'],'战后报告缺少胜利来源。')
    for g in game.cat.rules['generals']:
        if g['defeat_fact'] in c['facts']:check(g['general_id'] in c['returned_reports'],'章节报告缺少归城凭据。')
        if g['general_id']+'_AWAKENED' in c['facts']:
            check(g['general_id'] in c['victories'] and c['victories'][g['general_id']]['battle']['boss_receipts'][g['general_id']]['awakened'],'觉醒事实缺少真实记忆选择。')
    for key,prereqs in {'ST-104':['ST-102','ST-103'],'CH1_COMPLETE':['ST-104'],
                        'CH2_COMPLETE':['ST-201','ST-202'],'CH3_BATTLES_COMPLETE':['ST-201','ST-202','ST-301','ST-302']}.items():
        if key in c['facts']:check(set(prereqs)<=c['facts'].keys(),'章节前置缺失：'+key)
    if c['remembrance']:bosses.validate(c['remembrance']['battle'])
