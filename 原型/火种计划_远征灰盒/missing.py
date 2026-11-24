"""Evidence-led search for real roster members whose transfer point is unknown.

Missing and confirmed captives share the unavailable-person storage, but have
distinct statuses and entry points. Searching never creates or replaces people.
"""
from copy import deepcopy
import campaign
import facilities
import rescue
import town


def check(ok,text):
    if not ok:raise ValueError(text)


def initialize(game):game.s['missing_search']={'cases':{},'active':None,'attempts':[]}
def state(game):return game.s['missing_search']


def needs_search(game):
    s=game.s;b=s['battle_reports'][-1] if s['battle_reports'] else None
    return (campaign.active(game) and not s['debug_tainted'] and s['mission']=='ORDINARY'
            and b and b['result']=='DEFEAT' and not b['encounter_id'].startswith('BATTLE-MG'))


def register(game,batch,ids):
    b=game.s['battle_reports'][-1]
    row={'id':batch['id'],'members':ids[:],'last_seen':{'region':batch['origin_region'],'site':batch['origin_site']},
         'source_battle':b['battle_id'],'source_expedition':game.s['expedition_no'],
         'missing_day':batch['capture_day'],'deadline':batch['deadline'],'steps':{},'located':None}
    check(row['id'] not in state(game)['cases'],'同一批失联人员不能重复登记。')
    state(game)['cases'][row['id']]=row
    game.log('missing_registered',case=deepcopy(row))


def people(game,cid):
    return [m for m in game.s['captives'] if m['capture']['batch_id']==cid]


def label(game,row):
    if people(game,row['id']):return '转运点已确认，待救援' if row['located'] else '失联，去向待查'
    lost=[m for m in game.s['memorial'] if m['instance_id'] in row['members'] and m['capture']['batch_id']==row['id']]
    return '期限届满，原人已不可恢复' if lost else '本批已救回，当前去向见名册'


def describe(game):
    data=state(game);lines=['搜救所·失联调查（人员名册与搜救记录）']
    for cid,row in data['cases'].items():
        lines.append(f"{cid} {label(game,row)}：{row['members']}；最后出现于{row['last_seen']['region']}/{row['last_seen']['site']}；最迟第{row['deadline']}日救回；已记录{list(row['steps'])}。")
    a=data['active']
    if a:
        lines.append(f"调查{a['case_id']}，回城结算到第{a['settles_on']}日。rescue investigate inspect tracks 核对原地点痕迹，再 rescue investigate inspect marker 沿交接标记确认转运点；rescue investigate return CONFIRM 结束本趟。已有调查记录保留，但调查不暂停期限。")
    elif data['cases']:lines.append('rescue investigate quote CAP批次；rescue investigate start CAP批次 CONFIRM；确认转运点后 rescue CAP批次 CONFIRM。')
    else:lines.append('暂无去向未明的现役人员；序章旧名册不是可凭空补发的当前队员。')
    return '\n'.join(lines)


def plan(game,cid):
    s=game.s;row=state(game)['cases'].get(cid)
    check(row and people(game,cid),'没有仍可调查的失联批次。')
    check(not row['located'],'转运点已确认，请直接办理救援。')
    return {'case_id':cid,'last_seen':deepcopy(row['last_seen']),'supply':facilities.rescue_cost(game),
            'settles_on':s['day']+1,'earliest_rescue_day':s['day']+2,'deadline':row['deadline'],
            'rescue_in_time':s['day']+2<=row['deadline'],'other_due':rescue.due_next(s)}


def handle(game,args):
    if not args or args==['status']:return describe(game)
    s=game.s;data=state(game);action=args[0]
    if action in ('quote','start'):
        check(s['phase']=='TOWN' and not data['active'],'先回城整备，不能同时开始两次调查。')
        check(len(args)==(3 if action=='start' else 2) and (action!='start' or args[-1]=='CONFIRM'),'missing quote CAP批次 / missing start CAP批次 CONFIRM')
        p=plan(game,args[1])
        if action=='quote':
            warning='' if p['rescue_in_time'] else ' 警告：先调查再另行救援已赶不上原期限；继续调查不会延期或复活。'
            return f"{p}；固定调查0战／1日，基础1补给，搜救所Lv1减免；没有钱晶、物品或经验奖励。"+warning
        check(not s['debug_tainted'],'调试档不能办理正式失联调查。')
        game.validate_deployment('OPEN')
        check(s['bank']['supply']>=p['supply'],f"调查需要{p['supply']}份仓库补给。")
        s['bank']['supply']-=p['supply']
        p.update(id=f"SEARCH-{s['expedition_no']:04d}",started_day=s['day'],steps=[],
                 rescue_post_level=facilities.level(game,'rescue_post'))
        data['active']=p
        s.update(mission='MISSING_SEARCH',phase='MISSING_SEARCH',manifest=None,request=None,
                 region=None,site='LAST_SEEN',rescue_target=None)
        game.erosion(5);game.log('missing_search_started',attempt=deepcopy(p))
        return describe(game)
    check(s['phase']=='MISSING_SEARCH' and data['active'],'当前不在失联调查专线。')
    a=data['active'];row=data['cases'][a['case_id']]
    if action=='inspect':
        check(len(args)==2 and args[1] in ('tracks','marker'),'missing inspect tracks / marker')
        step=args[1]
        if step in row['steps']:return '沿用已保存的现场记录；没有额外费用、日期或奖励。'
        if step=='marker':check('tracks' in row['steps'],'先在最后出现地点核对痕迹，再沿交接标记追查。')
        receipt={'attempt':a['id'],'day':s['day'],'last_seen':deepcopy(row['last_seen']),
                 'source_battle':row['source_battle'],'step':step}
        row['steps'][step]=receipt;a['steps'].append(step);s['site']='TRACKS' if step=='tracks' else 'TRANSFER_MARKER'
        game.log('missing_search_inspected',case_id=row['id'],receipt=deepcopy(receipt))
        return ('已核对该批队员遗留的行进痕迹；交接标记指向同一条转运支路。' if step=='tracks'
                else '已把支路交接号与原队名册核对一致；回城交存后可确认救援地点。没有释放队员，也没有重置期限。')
    check(action=='return' and args==['return','CONFIRM'],'missing return CONFIRM：结束调查并结算1日。')
    game.settle_return('SEARCH_RETURN')
    live=people(game,row['id'])
    if {'tracks','marker'}<=row['steps'].keys() and live:
        row['located']={'attempt':a['id'],'day':s['day'],'settlement_id':s['last_settlement_id'],
                        'source_battle':row['source_battle'],'encounter_id':'GR02E'}
        batch=next(b for b in s['capture_batches'] if b['id']==row['id']);batch['location_known']=True
        for m in live:m['capture'].update(status='CAPTURED',location_known=True)
        s['summary']['result']='LOCATION_CONFIRMED'
    elif not live:s['summary']['result']='SEARCH_EXPIRED'
    a.update(result=s['summary']['result'],settled_day=s['day'],settlement_id=s['last_settlement_id'])
    s['summary']['missing_search']=deepcopy(a);data['attempts'].append(deepcopy(a));data['active']=None
    game.log('missing_search_settled',attempt=deepcopy(a))
    return describe(game)


def validate(game):
    s=game.s;data=state(game)
    check(set(data)=={'cases','active','attempts'},'失联调查结构无效。')
    if not campaign.active(game):
        check(not data['cases'] and not data['active'] and not data['attempts'],'独立试验队保持已知转运场景，不能伪造自然失联来源。');return
    reports=s['battle_reports']+[b for h in s['completed_history'] for b in h['battle_reports']]
    members=town.roster(game)+s['memorial'];all_ids={m['instance_id'] for m in members}
    attempts=data['attempts']+([data['active']] if data['active'] else [])
    indexed={a['id']:a for a in attempts}
    check(len(indexed)==len(attempts),'失联调查行动重复。')
    for cid,row in data['cases'].items():
        batch=next((b for b in s['capture_batches'] if b['id']==cid),None)
        check(batch and row['id']==cid and row['missing_day']==batch['capture_day'] and row['deadline']==batch['deadline'],'失联期限与原批次不一致。')
        check(row['last_seen']=={'region':batch['origin_region'],'site':batch['origin_site']} and batch['source']=='unknown_patrol_destination','失联来源或原地点无效。')
        check(row['members'] and set(row['members'])<=all_ids and len(row['members'])==len(set(row['members'])),'失联名册缺失或重复造人。')
        battle=next((b for b in reports if b['battle_id']==row['source_battle'] and b['result']=='DEFEAT' and not b.get('debug_tainted')),None)
        check(battle and row['members']==[m['instance_id'] for m in battle['after']],'失联线索缺少原败战随队名册。')
        for iid in row['members']:
            m=next(m for m in members if m['instance_id']==iid)
            origins=m.get('capture_history',[])+([m['capture']] if 'capture' in m else [])
            check(any(c['batch_id']==cid and c['deadline']==row['deadline'] and c['source']=='unknown_patrol_destination' for c in origins),'失联人员缺少原批次去向。')
        check(set(row['steps'])<={'tracks','marker'} and ('marker' not in row['steps'] or 'tracks' in row['steps']),'调查步骤或先后无效。')
        for step,r in row['steps'].items():
            a=indexed.get(r['attempt'])
            check(a and a['case_id']==cid and step in a['steps'] and r=={'attempt':a['id'],'day':a['started_day'],'last_seen':row['last_seen'],'source_battle':row['source_battle'],'step':step},'调查记录缺少实际到场来源。')
        check(bool(row['located'])==batch['location_known'],'转运地点确认记录缺失。')
        if row['located']:
            r=row['located'];a=indexed.get(r['attempt'])
            check({'tracks','marker'}<=row['steps'].keys() and a and a['result']=='LOCATION_CONFIRMED' and r=={'attempt':a['id'],'day':a['settled_day'],'settlement_id':a['settlement_id'],'source_battle':row['source_battle'],'encounter_id':'GR02E'},'转运点不能跳过调查直接出现。')
            check(r['day']<row['deadline'],'确认地点不能重置或跨过原期限。')
        for m in people(game,cid):
            check(m['instance_id'] in row['members'] and m['capture']['deadline']==row['deadline'] and m['capture']['status']==('CAPTURED' if row['located'] else 'MISSING'),'失联人员状态与确认记录不一致。')
    for a in attempts:
        check(a['case_id'] in data['cases'] and a['settles_on']==a['started_day']+1 and a['rescue_post_level'] in (0,1,2,3),'失联行动前置或日期无效。')
        check(a['supply']==(0 if a['rescue_post_level'] else 1) and a['last_seen']==data['cases'][a['case_id']]['last_seen'],'调查费用或地点不符。')
        check(len(set(a['steps']))==len(a['steps']) and set(a['steps'])<={'tracks','marker'},'调查记录重复。')
        if 'settled_day' in a:check(a['settled_day']==a['settles_on'],'调查重复结算日期。')
    if data['active']:check(s['phase']==s['mission']=='MISSING_SEARCH','调查中途状态不一致。')
