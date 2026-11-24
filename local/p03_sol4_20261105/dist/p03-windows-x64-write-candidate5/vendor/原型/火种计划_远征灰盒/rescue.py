"""Known patrol captures, dated rescue batches and permanent loss receipts.

The fixed GR02E line uses real roster members. Unknown transfer destinations
must first be established through the rescue office's personnel investigation.
"""
from copy import deepcopy
import combat
import town
import escort
import refugee
import water
import equipment
import facilities
import supplies

COMMANDS={'rescue','capture_mode'}


def describe(game):
    import missing
    lines=[missing.describe(game)]
    for batch in batches(game.s):
        lines.append(f"已确认转运点 {batch['id']}：{batch['members']}；最晚第{batch['deadline']}日救回；rescue {batch['id']} CONFIRM，1战／1日，当前{facilities.rescue_cost(game)}补给。")
    if not batches(game.s):lines.append('暂无待救援的已确认转运点。')
    return '\n'.join(lines)


def initialize(s):
    s.update(captives=[],memorial=[],capture_batches=[],capture_mode='standard',
             mission='ORDINARY',rescue_target=None,last_settlement_id=None,ending=None)


def due_next(s):
    secured=pending_success_ids(s)
    return [m['instance_id'] for m in s['captives'] if m['capture']['deadline']<=s['day']+1 and m['instance_id'] not in secured]


def pending_success_ids(s):
    active=s.get('original_recovery',{}).get('active')
    return set(active['rescue_target']['member_ids']) if active and active['rescue_won'] else set()


def confirm_day(s,args):
    due=due_next(s)
    town.check(args in ([],['CONFIRM']),'可用 CONFIRM 确认推进行动日。')
    town.check(not due or args==['CONFIRM'],
               f"本次结算到第{s['day']+1}日，以下人员将超过救援期限：{due}。确认继续请追加 CONFIRM；也可先安排救援。")


def expire(game):
    """Called after this day's rescue, before old wounds and NEW captures."""
    s=game.s
    for m in list(s['captives']):
        if m['capture']['deadline']>s['day']:continue
        s['captives'].remove(m)
        m['capture'].update(status='LOST',lost_day=s['day'],settlement_id=s['last_settlement_id'],equipment_state='lost')
        s['memorial'].append(m)
        game.log('permanent_loss',member=m['instance_id'],capture=deepcopy(m['capture']),
                 equipment=m['gear'][:],source_snapshot=deepcopy(m),cause='capture_deadline_expired')


def check_ending(game):
    s=game.s
    import save_validation
    members,locations=save_validation.validate_enrollment(game)
    if s.get('ending') or s.get('finale',{}).get('ending'):return
    humans={iid for iid,m in members.items() if not m['unit_id'].startswith('PET')}
    lost={iid for iid in humans if locations[iid]=='memorial'}
    recoverable=humans-lost
    if humans and lost==humans and not recoverable:
        import campaign, finale
        if campaign.active(game):
            finale.outcome(game,'FIN-C','HUMANITY_EXTINCT');return
        s['ending']='FIN-C';s['phase']='FIN_C'
        game.log('campaign_ended',ending='FIN-C',cause='all_enrolled_humans_irrecoverable_no_rescue_targets')


def batches(s):
    result=[]
    for batch in s['capture_batches']:
        if not batch.get('location_known',True):continue
        people=[m for m in s['captives'] if m['capture']['batch_id']==batch['id']]
        if people:result.append({**batch,'members':[m['instance_id'] for m in people]})
    return result


def settle_defeat(game,*,defer_ending=False):
    s=game.s
    import expedition_peril
    rested_unfit=expedition_peril.clear(game,'DEFEAT')
    import cases, missing
    unknown=missing.needs_search(game)
    refugee.before_settlement(game,False)
    cases.before_settlement(game,False)
    water.before_settlement(game,False)
    lost={'pending':deepcopy(s['pending']),'materials':deepcopy(s['materials']),
          'gear':s['gear_bag'][:],'consumables':s['pouch'][:],'medical':s['medical']}
    town.advance_day(game,s['home_roster'])
    escorted=escort.settle(game)
    batch_id=f"CAP-{s['expedition_no']:04d}"
    window=game.cat.rules['difficulty_profiles'][s['capture_mode']]['capture_window']
    batch={'id':batch_id,'capture_day':s['day'],'deadline':s['day']+window,
           'mode':s['capture_mode'],'origin_region':s['region'],'origin_site':s['site'],
           'source':'unknown_patrol_destination' if unknown else 'post_battle_patrol_transfer',
           'location_known':not unknown,'encounter_id':'GR02E'}
    s['capture_batches'].append(batch)
    ids=[m['instance_id'] for m in s['party']]
    for m in s['party']:
        m['deployed']=False
        m['capture']={**batch,'batch_id':batch_id,'status':'MISSING' if unknown else 'CAPTURED','equipment_state':'captured_locked',
                      'settlement_id':s['last_settlement_id']}
        s['captives'].append(m)
    s['party']=[]
    s['summary']={'result':'DEFEAT','day':s['day'],'settlement_id':s['last_settlement_id'],
                  'captured_ids':[] if unknown else ids,'missing_ids':ids if unknown else [],'capture_batch':deepcopy(batch),'banked':{},'lost_cargo':lost,
                  'lost_pending':deepcopy(lost['pending']),
                  'expired_plans':s['plans_owned'][:],'balance_eligible':False,
                  'campaign_loss_resolution':'UNKNOWN_DESTINATION' if unknown else 'KNOWN_PATROL_CAPTURE','debug_tainted':s['debug_tainted'],
                  'battles':len(s['battle_reports'])}
    s['summary']['escorted_home']=escorted
    s['summary']['rested_unfit']=rested_unfit
    import challenge_rewards
    challenge_summary=challenge_rewards.settle(game,False,'DEFEAT')
    if challenge_summary is not None:s['summary']['challenge_rewards']=challenge_summary
    material_summary=supplies.settle_material_bonus(game,False,'DEFEAT')
    if material_summary is not None:s['summary']['material_commission_bonus']=material_summary
    import event_conditions
    s['summary']['expired_conditions']=event_conditions.settle(game,'DEFEAT')
    equipment.lose_bag(game,'defeat_cargo')
    s.update(phase='FAILED',pending={'copper':0,'crystal':0},materials={},gear_bag=[],pouch=[],medical=0,
             plans_owned=[],plans_equipped=[],preparations={},used_prep_slots=0)
    supplies.settle(game,False)
    if unknown:missing.register(game,batch,ids)
    game.log('defeat_settled',summary=deepcopy(s['summary']))
    if not defer_ending:check_ending(game)


def detach_success(game,target):
    s=game.s
    import save_validation
    save_validation.validate_enrollment(game)
    validate_target(target)
    ids=target['member_ids']
    town.check(ids and len(ids)==len(set(ids)), '救援目标身份重复或为空。')
    rescued=[m for m in s['captives'] if m['instance_id'] in ids]
    town.check({m['instance_id'] for m in rescued}==set(ids) and all(m['capture']['batch_id']==target['batch_id'] and m['capture']['deadline']==target['deadline'] for m in rescued), '救援目标缺项或原批次/期限不一致。')
    town.check(rescued and all(m['capture']['status']=='CAPTURED' and m['capture']['deadline']>=s['day']+1 for m in rescued),'救援目标尚未确认或期限不合法。')
    # Remove these targets BEFORE the expiry pass; the deadline day is valid.
    for m in rescued:s['captives'].remove(m)
    return rescued


def restore_success(game,rescued,target):
    s=game.s
    import save_validation
    validate_target(target)
    ids=[m['instance_id'] for m in rescued];wanted=target['member_ids']
    town.check(ids and len(ids)==len(set(ids)) and set(ids)==set(wanted) and len(wanted)==len(set(wanted)), '恢复目标重复或缺项。')
    present=[m['instance_id'] for roster in save_validation.ROSTERS for m in s[roster]]
    town.check(not set(ids)&set(present) and set(s['enrollment_register'])-set(present)==set(ids), '恢复目标重复或加入全集缺项。')
    town.check(all(m.get('capture',{}).get('status')=='CAPTURED' and m['capture']['batch_id']==target['batch_id'] and m['capture']['deadline']==target['deadline'] and m['unit_id']==s['enrollment_register'][m['instance_id']]['unit_id'] for m in rescued), '恢复目标来源错误。')
    injury=facilities.injured_days(game,rescued=True)
    for m in rescued:
        capture=deepcopy(m.pop('capture'));capture.update(status='RESCUED',rescued_day=s['day'],equipment_state='equipped')
        m.setdefault('capture_history',[]).append(capture)
        m.update(hp=0,injury_days=injury,deployed=False,erosion=max(0,m['erosion']-20))
        s['home_roster'].append(m)
    s['summary'].update(rescued_ids=[m['instance_id'] for m in rescued],rescue_target=deepcopy(target),
                        rescued_injury_days=injury)
    save_validation.validate_enrollment(game)
    game.log('rescue_completed',summary=deepcopy(s['summary']))


def finish_success(game):
    target=game.s['rescue_target'];rescued=detach_success(game,target)
    # Rescued people temporarily leave the captive list to beat deadline
    # expiry. Judge extinction only after the same people have returned, with
    # fresh wounds registered AFTER this action day's recovery pass.
    game.settle_return('RESCUE_SUCCESS',defer_ending=True)
    restore_success(game,rescued,target)
    check_ending(game)


def handle(game,command,args):
    s=game.s
    town.check(s['phase']=='TOWN','请先回城并进入整备。')
    if command=='capture_mode':
        town.check(len(args)==1 and args[0] in game.cat.rules['difficulty_profiles'],'capture_mode standard/relaxed')
        town.check(not s['captives'],'仍有被俘者，不能修改捕获期限模式。')
        s['capture_mode']=args[0];game.log('capture_mode_changed',mode=args[0]);return
    town.check(len(args)==2 and args[1]=='CONFIRM','rescue CAP-0001 CONFIRM：固定救援1战／1补给／1行动日')
    batch=next((b for b in batches(s) if b['id']==args[0]),None)
    town.check(batch is not None,'没有这个已确认且仍可救援的转运批次；去向未明者先到搜救所：rescue status。')
    town.check(batch['deadline']>=s['day']+1,'本次救援结算日已超过期限。')
    game.validate_deployment('OPEN');cost=facilities.rescue_cost(game)
    town.check(s['bank']['supply']>=cost,f'固定救援需{cost}份仓库补给。')
    s['bank']['supply']-=cost;s['mission']='RESCUE'
    s['rescue_target']={'batch_id':batch['id'],'member_ids':batch['members'][:],
                        'deadline':batch['deadline'],'encounter_id':'GR02E','settles_on':s['day']+1}
    s.update(region=None,site='RESCUE',manifest=None,request=None,phase='BATTLE')
    game.erosion(5)
    s['battle']=combat.create(game.cat,game.cat.encounter_for_board('GR02E','OPEN'),'OPEN',s['party'],s['seed'],[],s['preparations'])
    game.log('rescue_departed',target=deepcopy(s['rescue_target']),supply_cost=cost)
    return '已出发前往确认的转运点；战胜巡队才能救回本批原人。撤退不视为救援成功。'


def validate_target(target):
    town.check(isinstance(target,dict) and isinstance(target.get('batch_id'),str)
               and type(target.get('deadline')) is int
               and isinstance(target.get('member_ids'),list)
               and all(isinstance(iid,str) and iid for iid in target['member_ids']),
               '救援目标来源/身份列表/期限字段无效。')
