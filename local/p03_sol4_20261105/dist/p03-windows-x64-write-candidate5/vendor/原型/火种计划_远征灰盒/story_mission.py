"""Fixed first investigation, using the existing battle and return transactions."""
from copy import deepcopy
import json
from data import DOC,keyed_rng
import campaign
import depth_growth
import rescue
import equipment_rolls
import expedition_tiers as tiers

LAYOUT='RT2_TUT01'
EDGES=[['I','A'],['A','B_SUPPORT'],['A','B_MATERIAL'],['B_SUPPORT','C'],
       ['B_MATERIAL','C'],['C','D'],['D','G'],['G','X']]


def install(cat):
    source=json.loads((DOC.parent/'样片/首次远征流程.json').read_text(encoding='utf-8'))
    cat.tutorial=source
    root=deepcopy(cat.encounters['INTRO-EN01']);root.update(encounter_id='TUT01-ROOT',threat_budget=2)
    root['units']=[]
    for spec in source['encounters'][1]['units']:
        unit=deepcopy(cat.encounters['INTRO-EN01']['units'][0])
        unit.update(instance_id=spec['local_instance_id'],hp_owner_id=spec['local_instance_id'],position=spec['position'])
        root['units'].append(unit)
    cat.encounters['TUT01-ROOT']=root
    names=['I','A','B_SUPPORT','B_MATERIAL','C','D','G','X']
    cat.layouts[LAYOUT]={'template_id':LAYOUT,'name':'灰栎边道固定侦路','edges':EDGES,
       'nodes':[{'id':n,'name':n,'role':'fixed_tutorial'} for n in names],
       'mandatory_battles':['A','G'],'entry':'I','goal_exit':'X','station':None}


def start(game,args):
    s=game.s;c=s['campaign']
    campaign.check(s['phase']=='TOWN','需在城镇出发。')
    campaign.check('ST-101' in c['facts'] and 'ST-102' not in c['facts'],'先受任；已交付教学调查后不能重刷教程。')
    rescue.confirm_day(s,args);game.validate_deployment('OPEN')
    campaign.check(s['bank']['supply']>=1,'固定侦路需1补给；无额外物资赠送。')
    s['bank']['supply']-=1
    rng=keyed_rng(s['seed'],'tutorial-gear-offer')
    s['tutorial_trip']={'expedition':s['expedition_no'],'observation':None,'choices':{},
                        'gear_offers':rng.sample(['EF03','EF05','EF07'],2)}
    manifest={'profile':'TUTORIAL','start':'RG01','target':'RG01','paths':[['RG01']],
      'departure_supply_cost':1,'caps':{'gear_claims':1,'book_claims':0,'material_units':2},
      'depth_growth':depth_growth.policy(game.cat),
      'regions':{'RG01':{'template_id':LAYOUT,'events':{},'encounters':{
         'A':{'encounter_id':'INTRO-EN01','board_id':'OPEN'},'G':{'encounter_id':'TUT01-ROOT','board_id':'OPEN'}},
         'combat_rewards':{},'fixed_station':None,'nonfinal_camp':None}}}
    from joint_sampling_model import digest
    manifest['manifest_sha256']=digest(manifest)
    s.update(mission='TUTORIAL',manifest=manifest,request={'kind':'fixed_tutorial','seed':s['seed']})
    game.enter_region('RG01')
    return '固定侦路已出发：I→A→B_SUPPORT或B_MATERIAL→C→D→G→X。D处 tutorial observe；入口可早返。'


def handle(game,args):
    campaign.check(campaign.active(game),'tutorial 需 --campaign 自然开局。')
    campaign.check(not game.s['debug_tainted'],'调试档不能交付真实教学调查。')
    campaign.check(args,'tutorial start / recommend CONFIRM / observe / support 队员ID / materials / cache 底型 / plan PL01')
    action=args[0];s=game.s
    if action=='start':return start(game,args[1:])
    if action=='recommend':
        campaign.check(args==['recommend','CONFIRM'] and s['phase']=='TOWN','tutorial recommend CONFIRM 仅城镇采用建议。')
        campaign.check('ST-102' not in s['campaign']['facts'],'教学已完成，请直接编队。')
        # Use only present original soldiers. Never refill losses or move captives.
        desired=['INIT-S01-A','INIT-S01-B','INIT-S02-A','INIT-S02-B','INIT-S03-A','INIT-S03-B']
        chosen=[m for iid in desired for m in s['party'] if m['instance_id']==iid and m['hp']>0 and m['injury_days']==0]
        campaign.check(chosen,'无可用初始队员；按实际名册自行编队。')
        for m in s['party']:m['deployed']=False
        for i,m in enumerate(chosen):m.update(deployed=True,position=list(game.cat.formation[i]),stance='advance')
        game.validate_deployment('OPEN');return '已为实际在队的初始成员填入建议部署；可自由修改。'
    campaign.check(s['mission']=='TUTORIAL' and s['phase']=='EXPLORE','需在教学地图战外进行。')
    trip=s['tutorial_trip'];choices=trip['choices']
    if action=='observe':
        campaign.check(args==['observe'] and s['site']=='D','在远眺D处使用 tutorial observe。')
        if not trip['observation']:
            trip['observation']={'expedition':s['expedition_no'],'site':'D','source':'fixed_observation_task',
                'observed':'依照侦路单观察远处巡行：抬手、停步、转向的次序与废岗石刻上的旧口令相似。',
                'learning_evidence':False}
            game.log('field_observation',receipt=trip['observation'])
        return trip['observation']['observed']+' 已记录现场，归城后可请许苇对照旧日志。'
    sites={'support':'B_SUPPORT','materials':'B_MATERIAL','cache':'G','plan':'A'}
    campaign.check(action in sites and s['site']==sites[action],'请到对应地点处理：'+str(sites))
    if action in choices:return '已有选择：'+str(choices[action])
    campaign.check(len(args)>=2 if action in ('support','cache','plan') else len(args) in (1,2),'缺少目标、底型或方案；可用PASS放弃。')
    value=args[1] if len(args)>1 else 'CLAIM'
    campaign.check(len(args)<=2,'参数过多。')
    if action in ('cache','plan'):campaign.check(s['site'] in game.current['cleared'],'先真实击败此处敌人。')
    if action=='materials':campaign.check(value in ('CLAIM','PASS'),'tutorial materials 或 tutorial materials PASS。')
    receipt={'choice':value,'site':s['site']}
    if value!='PASS':
        if action=='support':
            if 'G' not in game.current['cleared']:
                m=game.standing(value);campaign.check(m in s['party'],'目标须实际随队。')
                s['preparations'].setdefault(m['instance_id'],[]).append({'type':'next_battle_private_shield','amount':12})
                receipt['shield']={'target':m['instance_id'],'amount':12}
            if 'G' not in game.current['revealed_battles'] and 'G' not in game.current['cleared']:
                game.current['revealed_battles'].append('G');receipt['preview']='G'
            receipt['light_source']='station_lantern'
        elif action=='materials':game.grant('RB-MAT2',{})
        elif action=='plan':
            campaign.check(value in ('PL01','PL02','PL05'),'本次候选PL01/PL02/PL05，或PASS。')
            campaign.check(value not in s['plans_owned'],'已经拥有该方案。')
            s['plans_owned'].append(value)
        elif action=='cache':
            campaign.check(value in trip['gear_offers'],'锁定底型：'+','.join(trip['gear_offers'])+'；或PASS。')
            game.debit({'gear_claims':1})
            quote=tiers.quality(game,'cache');weights=quote['effective_weights']
            rng=keyed_rng(s['seed'],'tutorial-cache-quality');quality=rng.choices(list(weights),list(weights.values()))[0]
            item=equipment_rolls.drop(game,value+'-'+quality,{'kind':'tutorial_cache','expedition':s['expedition_no']},f"tutorial-cache:{s['expedition_no']}")
            tiers.claimed(game,quality);receipt.update(item=item['instance_id'],quality_quote=quote)
    choices[action]=receipt;game.log('tutorial_choice',action=action,receipt=receipt)
    return str(receipt)


def finish_battle(game,battle):
    if game.s['mission']!='TUTORIAL':return False
    if battle['result']=='VICTORY':
        slot=game.s['site'];campaign.check(slot not in game.current['cleared'],'该战已结算。')
        game.current['cleared'].append(slot)
        reward={'copper':6 if slot=='A' else 10,'crystal':0 if slot=='A' else 2}
        for k,v in reward.items():game.s['pending'][k]+=v
        if slot=='G':game.s['completed_regions'].append('RG01')
        game.log('tutorial_segment_reward',slot=slot,pending=reward)
    elif battle['result']=='RETREAT':game.settle_return('COMBAT_RETREAT')
    else:rescue.settle_defeat(game)
    return True


def on_return(game):
    s=game.s
    if s['mission']!='TUTORIAL':return
    trip=s['tutorial_trip'];victories={b['encounter_id']:b['battle_id'] for b in s['battle_reports'] if b['result']=='VICTORY' and not b['debug_tainted']}
    if {'INTRO-EN01','TUT01-ROOT'}<=victories.keys() and trip['observation']:
        campaign.fact(game,'ST-102',{'battles':victories,'observation':deepcopy(trip['observation']),
                                   'settlement_id':s['last_settlement_id']})


def describe(game):
    s=game.s
    if s.get('mission')!='TUTORIAL' or s['phase'] not in ('EXPLORE','BATTLE'):return ''
    return ('固定侦路：两战，安全归城1日；支路可回访。D处 tutorial observe 记录调查。\n'
            'A胜后 tutorial plan PL01/PL02/PL05/PASS；护运站有灯，tutorial support 队员ID/PASS；材料匣 tutorial materials。\n'
            'G胜后 tutorial cache '+ '/'.join(s['tutorial_trip']['gear_offers'])+'/PASS；未领取不阻止返城。'
            '回城后先 gear list、equip 队员 实例ID 再出发；教程战利品未穿上不会在下一趟生效。')
