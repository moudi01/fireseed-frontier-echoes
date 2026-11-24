"""Fixed original-object recovery and a two-stop rescue itinerary.

Registered quest objects remain protected. A story producer must explicitly
register an uncollected original; there is no player command that drops one.
"""
from copy import deepcopy
import campaign
import combat
import facilities
import rescue
import town

MISSIONS={'RECOVERY','JOINT_RECOVERY'}


def check(ok,text):
    if not ok:raise ValueError(text)


def initialize(game):
    game.s['original_recovery']={'targets':{},'active':None,'attempts':[]}


def state(game):return game.s['original_recovery']


def recovery_cost(game):
    return 0 if facilities.level(game,'rescue_post')>=2 and facilities.branch(game,'rescue_post')=='B' else 1


def register_original(game,uid,source):
    """Story adapter only: reserve the original, never remove an owned item.

    source must contain the actual scene/holder's loss statement. Registration
    is idempotent and pays the original collection cost once, not each attempt.
    """
    s=game.s;check(campaign.active(game) and s['phase']=='TOWN','原物线索须在城镇任务中登记。')
    check(not s['debug_tainted'],'调试档不能登记正式原物线索。')
    check(uid in campaign.QUESTS,'未知执念原物。')
    q=campaign.QUESTS[uid];row=s['campaign']['quests'].get(uid,{})
    check(q['gate'] in s['campaign']['facts'],'该线索尚未开放。')
    check({'record','witness'}<=row.keys(),'先查阅登记并核实证词。')
    check(isinstance(source,dict) and set(source)=={'scene_id','statement'} and all(isinstance(v,str) and v for v in source.values()),'缺少明确的剧情失落来源。')
    targets=state(game)['targets']
    if uid in targets:
        check(targets[uid]['source']==source,'同一原物不能换锚或重写来源。');return targets[uid]
    check('collect' not in row and 'OBS-'+uid not in s['campaign']['task_items'],'已取得任务物受保护，不能登记为失落。')
    for k,v in q['cost'].items():check((s['bank'] if k=='copper' else s['warehouse']).get(k,0)>=v,'原委托交接材料不足：'+str(q['cost']))
    for k,v in q['cost'].items():(s['bank'] if k=='copper' else s['warehouse'])[k]-=v
    region=next(g['region_id'] for g in game.cat.rules['generals'] if g['general_id']==uid)
    target={'id':uid,'item_id':'OBS-'+uid,'name':q['item'],'source':deepcopy(source),
            'anchor':{'region':region,'site':'ORIGINAL-'+uid,'encounter_id':'GR02E','board_id':'OPEN'},
            'registered_day':s['day'],'paid':deepcopy(q['cost']),
            'status':'MISSING','receipt':None}
    targets[uid]=target
    game.log('original_registered',target=deepcopy(target));return target


def plan(game,uid,batch_id=None):
    s=game.s;target=state(game)['targets'].get(uid)
    check(target and target['status']=='MISSING','没有这个仍待找回的原物。')
    check(target['anchor']['region'] in {r['region_id'] for r in game.cat.multi['regions']},'原物地点无效。')
    result={'target':uid,'anchor':deepcopy(target['anchor']),'settles_on':s['day']+1,
            'recovery_supply':recovery_cost(game),'rescue_supply':0,'rescue_target':None,
            'facility_level':facilities.level(game,'rescue_post'),'facility_branch':facilities.branch(game,'rescue_post')}
    if batch_id:
        check(facilities.level(game,'rescue_post')>=3,'联办需搜救所Lv3；独立追回不要求建筑。')
        batch=next((b for b in rescue.batches(s) if b['id']==batch_id),None)
        check(batch,'没有这个可救援批次。')
        check(batch['origin_region']==target['anchor']['region'],'只有同一区域走廊的救人点与原物点可联办。')
        check(batch['deadline']>=s['day']+1,'结算日超过救援期限。')
        result['rescue_supply']=facilities.rescue_cost(game)
        result['rescue_target']={'batch_id':batch_id,'member_ids':batch['members'][:],
            'deadline':batch['deadline'],'encounter_id':'GR02E','settles_on':s['day']+1}
    return result


def describe(game):
    data=state(game);lines=['原物找回：已取得任务物继续受保护；只办理剧情登记的未领取原物。']
    for uid,t in data['targets'].items():
        lines.append(f"{uid} {t['name']}：{t['status']}；{t['anchor']['region']}/{t['anchor']['site']}；来源：{t['source']['statement']}")
    if not data['targets']:lines.append('暂无已登记失物；没有来源时不会生成空追回任务。')
    a=data['active']
    if a:
        lines.append(f"当前{a['stage']}；结算第{a['settles_on']}日。已成功的救人点会独立兑现；后点失败不会撤销前点救援。")
        if game.s['phase']=='RECOVERY_STOP':lines.append('recover continue CONFIRM 前往原物点；recover return CONFIRM 仅带已救者返城。可先deploy/place/stance/skill调整原随队人员，不回血补员。')
    else:lines.append('recover quote 原物ID [CAP批次]；recover start 原物ID [CAP批次] CONFIRM。独立1战，联办先救人再取物共2战，均1日；两点补给分别计费。')
    return '\n'.join(lines)


def start_battle(game,stage):
    s=game.s;a=state(game)['active'];game.validate_deployment('OPEN')
    a['stage']=stage;s.update(phase='BATTLE',site=stage)
    s['battle']=combat.create(game.cat,game.cat.encounter_for_board('GR02E','OPEN'),'OPEN',s['party'],s['seed']+(1 if stage=='ORIGINAL' else 0),[],s['preparations'])
    # Existing permanent preparation applies in both encounters; no extra loot.
    import outfitting
    outfitting.start_battle(game,s['battle']);facilities.start_battle(game,s['battle'])
    game.log('recovery_battle_started',stage=stage,target=a['target'],battle_id=s['battle']['battle_id'])


def handle(game,args):
    if not args or args==['status']:return describe(game)
    s=game.s;data=state(game);action=args[0]
    if action in ('continue','return'):
        check(args==[action,'CONFIRM'] and s['phase']=='RECOVERY_STOP' and data['active'],'需处于联办点间停留。')
        if action=='continue':start_battle(game,'ORIGINAL')
        else:finish(game,'PARTIAL_RETURN')
        return describe(game)
    check(action in ('quote','start'),'recover status / quote / start / continue / return')
    check(s['phase']=='TOWN' and not data['active'],'请先返回城镇。')
    parts=args[1:]
    if action=='start':
        check(parts and parts[-1]=='CONFIRM','出发需追加CONFIRM；两点风险分别结算。');parts=parts[:-1]
    check(len(parts) in (1,2),'recover quote 原物ID [CAP批次]；recover start 原物ID [CAP批次] CONFIRM')
    p=plan(game,*parts);cost=p['recovery_supply']+p['rescue_supply']
    if action=='quote':
        return f"{p}；合计{cost}补给、1行动日；救人点败则旧期限继续，原物点败则原物留原锚；无首奖、钱晶或经验。"
    check(not s['debug_tainted'],'调试档不能追回正式原物。')
    game.validate_deployment('OPEN');check(s['bank']['supply']>=cost,f'需要{cost}份仓库补给。')
    s['bank']['supply']-=cost
    p.update(id=f"REC-{s['expedition_no']:04d}",started_day=s['day'],paid_supply=cost,
             rescue_won=False,original_won=False,battles=[])
    data['active']=p
    s.update(mission='JOINT_RECOVERY' if p['rescue_target'] else 'RECOVERY',region=None,site=None,
             manifest=None,request=None,rescue_target=deepcopy(p['rescue_target']))
    game.erosion(5);start_battle(game,'RESCUE' if p['rescue_target'] else 'ORIGINAL')
    game.log('recovery_departed',attempt=deepcopy(p));return '已出发；run/step 推进实际战斗。'


def finish_battle(game,b):
    if game.s['mission'] not in MISSIONS:return False
    a=state(game)['active'];stage=a['stage']
    a['battles'].append({'stage':stage,'battle_id':b['battle_id'],'result':b['result']})
    if b['result']=='VICTORY':
        check(not game.s['debug_tainted'],'不能用调试胜利发放任务原物。')
        if stage=='RESCUE':
            a['rescue_won']=True;game.s['phase']='RECOVERY_STOP'
            for m in game.s['party']:
                if m['hp']<=0:m['deployed']=False
        else:a['original_won']=True;finish(game,'RECOVERY_SUCCESS')
    else:finish(game,'DEFEAT' if b['result']=='DEFEAT' else 'COMBAT_RETREAT')
    return True


def finish(game,result):
    s=game.s;data=state(game);a=data['active'];rescued=[]
    if a['rescue_won']:rescued=rescue.detach_success(game,a['rescue_target'])
    if result=='DEFEAT':
        s['region']=a['anchor']['region']
        rescue.settle_defeat(game,defer_ending=True)
    else:game.settle_return(result,defer_ending=True)
    if rescued:rescue.restore_success(game,rescued,a['rescue_target'])
    if a['original_won']:
        target=data['targets'][a['target']];uid=a['target'];c=s['campaign']
        receipt={'day':s['day'],'paid':deepcopy(target['paid']),'item':target['item_id'],'name':target['name']}
        check('collect' not in c['quests'][uid] and target['item_id'] not in c['task_items'],'原物已领取，拒绝重复发放。')
        c['quests'][uid]['collect']=receipt;c['task_items'][target['item_id']]=deepcopy(receipt)
        campaign.sync_evidence(game)
        target['status']='RECOVERED';target['receipt']={'attempt':a['id'],'settlement_id':s['last_settlement_id'],'item':deepcopy(receipt)}
        s['summary']['recovered_original']=target['item_id']
    a.update(result=result,settlement_id=s['last_settlement_id'],settled_day=s['day'])
    s['summary']['original_recovery']=deepcopy(a);data['attempts'].append(deepcopy(a));data['active']=None
    game.log('recovery_settled',receipt=deepcopy(a))
    rescue.check_ending(game)


def validate(game):
    import clues
    data=state(game);s=game.s
    check(set(data)=={'targets','active','attempts'},'原物追回账结构无效。')
    if not campaign.active(game):
        check(not data['targets'] and not data['active'] and not data['attempts'],'试验档不能有正式原物任务。');return
    ids=[a['id'] for a in data['attempts']]
    check(len(ids)==len(set(ids)),'追回行动重复结算。')
    for uid,t in data['targets'].items():
        q=campaign.QUESTS.get(uid);row=s['campaign']['quests'].get(uid,{})
        check(q and {'record','witness'}<=row.keys() and t['paid']==q['cost'],'原物来源或原交接费用缺失。')
        check(t['source']==clues.field_source(uid),'线索来源与固定剧情记录不符。')
        region=next(g['region_id'] for g in game.cat.rules['generals'] if g['general_id']==uid)
        check(t['id']==uid and t['item_id']=='OBS-'+uid and t['name']==q['item'] and t['anchor']=={'region':region,'site':'ORIGINAL-'+uid,'encounter_id':'GR02E','board_id':'OPEN'},'原物身份或固定锚无效。')
        check(t['status'] in ('MISSING','RECOVERED'),'原物状态无效。')
        if t['status']=='MISSING':check(not t['receipt'] and 'collect' not in row,'失物不能同时位于任务物库存。')
        else:
            r=t['receipt'];a=next((x for x in data['attempts'] if x['id']==r['attempt']),None)
            check(a and a['target']==uid and a['original_won'] and r['settlement_id']==a['settlement_id'] and r['item']==row.get('collect'),'原物领取缺少实际追回回执。')
    reports=s['battle_reports']+[b for h in s['completed_history'] for b in h['battle_reports']]
    for a in data['attempts']+([data['active']] if data['active'] else []):
        check(a['target'] in data['targets'] and a['anchor']==data['targets'][a['target']]['anchor'],'追回行动目标不一致。')
        check(a['settles_on']==a['started_day']+1 and a['paid_supply']==a['rescue_supply']+a['recovery_supply'],'追回费用或日期无效。')
        check(a['facility_level'] in (0,1,2,3) and a['facility_branch'] in (None,'A','B'),'追回设施快照无效。')
        check(a['recovery_supply']==(0 if a['facility_level']>=2 and a['facility_branch']=='B' else 1),'原物点补给费用与出发设施不符。')
        if a['rescue_target']:
            t=a['rescue_target'];batch=next((b for b in s['capture_batches'] if b['id']==t['batch_id']),None)
            check(a['facility_level']==3 and a['rescue_supply']==0 and batch and batch['origin_region']==a['anchor']['region'] and t['deadline']==batch['deadline']>=a['settles_on'],'联办缺少同走廊来源、设施或期限。')
        else:check(not a['rescue_won'] and a['rescue_supply']==0,'独立调查不能附带救人回执。')
        stages=[b['stage'] for b in a['battles']]
        expected=['RESCUE','ORIGINAL'] if a['rescue_target'] else ['ORIGINAL']
        check(stages==expected[:len(stages)],'调查点顺序或次数无效。')
        for b in a['battles']:
            check(any(r['battle_id']==b['battle_id'] and r['result']==b['result'] and r['encounter_id']=='GR02E' and not r.get('debug_tainted') for r in reports),'追回缺少实际战报。')
        check(a['rescue_won']==any(b['stage']=='RESCUE' and b['result']=='VICTORY' for b in a['battles']) and a['original_won']==any(b['stage']=='ORIGINAL' and b['result']=='VICTORY' for b in a['battles']),'追回成功状态与战报不符。')
        if 'settled_day' in a:check(a['settled_day']==a['settles_on'],'追回重复推进行动日。')
    if data['active']:check(s['mission'] in MISSIONS and s['phase'] in ('BATTLE','RECOVERY_STOP'),'追回行动与当前阶段不一致。')
