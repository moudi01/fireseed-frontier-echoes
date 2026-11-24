"""Reserve-led evacuation: protected people, retained commitment, no cargo teleport."""
from copy import deepcopy


def initialize(s):
    s.update(escorted=[],escort_receipts=[],escort_reserved_cost=0)


def preview(game):
    s=game.s
    wounded=[m['instance_id'] for m in s['party'] if m['hp']<=0]
    leaders=[m['instance_id'] for m in s['party'] if not m['deployed'] and m['hp']>0
             and m['erosion']<100 and m['injury_days']==0]
    safe={mid for r in s['escort_receipts'] if r['status']=='SAFE_EXIT_LOCKED' for mid in r['member_ids']}
    return {'wounded':wounded,'leaders':leaders,'protected':[m['instance_id'] for m in s['escorted'] if m['instance_id'] in safe],
            'reserved_cost':s['escort_reserved_cost'],
            'committed_cost':s['escort_reserved_cost']+sum(m['cost'] for m in s['party']),
            'settles_on':s['day']+1}


def handle(game,args):
    s=game.s;game.noncombat()
    if s['mission']!='ORDINARY':raise ValueError('护送用于普通远征的战外阶段。')
    if len(args)!=2 or args[1]!='CONFIRM':raise ValueError('escort 预备队员ID CONFIRM：护送全部倒地者，原装备随人、共享包留队。')
    leader=game.member(args[0]);p=preview(game)
    if leader['instance_id'] not in p['leaders']:raise ValueError('护送者需为当前随行、未部署、仍可行动且侵蚀低于100的预备队员。')
    if not p['wounded']:raise ValueError('当前没有倒地者需要护送。')
    leaving=[m for m in s['party'] if m['hp']<=0 or m is leader]
    remaining=[m for m in s['party'] if m not in leaving]
    if not any(m['hp']>0 and m['erosion']<100 and m['injury_days']==0 for m in remaining):
        raise ValueError('余队至少保留1名可行动队员；请改为全队返回入口安全归城。')
    send(game,leaving,leader)
    return f"已安全护送{len(leaving)-1}名倒地者；护送者同时离队。余队{len(remaining)}人，共享包保留，整趟仍结算1行动日。"


def send(game,leaving,leader,status='SAFE_EXIT_LOCKED',purpose='WOUNDED'):
    s=game.s
    earned={m['instance_id']:[rid for rid in s['completed_regions'] if m['instance_id'] in s['regions'][rid]['deployed_here']] for m in leaving}
    receipt={'id':f"ESC-{s['expedition_no']:04d}-{len(s['escort_receipts'])+1:02d}",
             'leader':leader['instance_id'],'wounded':[m['instance_id'] for m in leaving if m['hp']<=0],
             'member_ids':[m['instance_id'] for m in leaving],
             'status':status,'purpose':purpose,'region':s['region'],'site':s['site'],
             'action_day':s['day']+1,'departure_snapshot':deepcopy(leaving),
             'earned_regions':earned,'reserved_cost':sum(m['cost'] for m in leaving),
             'preparations':{m['instance_id']:deepcopy(s['preparations'].get(m['instance_id'],[])) for m in leaving}}
    for m in leaving:
        m['deployed']=False
        m['escort_injury']=m['hp']<=0 or m['instance_id'] in s['downed_this_trip']
        s['preparations'].pop(m['instance_id'],None)
    s['party']=[m for m in s['party'] if m not in leaving];s['escorted'].extend(leaving)
    s['escort_reserved_cost']+=receipt['reserved_cost'];s['escort_receipts'].append(receipt)
    game.log('escort_safe_exit' if status=='SAFE_EXIT_LOCKED' else 'escort_departed',receipt=deepcopy(receipt))
    return receipt


def settle(game):
    """After old-wound/day advancement, register new injuries exactly once."""
    s=game.s;rows=[]
    for receipt in s['escort_receipts']:
        if receipt['status']!='SAFE_EXIT_LOCKED':continue
        for mid in receipt['member_ids']:
            m=next(m for m in s['escorted'] if m['instance_id']==mid)
            injured=m.pop('escort_injury')
            m['injury_days']=game.cat.rules['time']['injury_hospital' if s['hospital_level'] else 'injury'] if injured else 0
            m['hp']=0 if injured else m['stats']['hp'];m['erosion']=max(0,m['erosion']-20)
            xp=len(receipt['earned_regions'][mid]);m['xp']+=xp
            s['escorted'].remove(m);s['home_roster'].append(m)
            rows.append({'id':mid,'injury_days':m['injury_days'],'xp':xp,'equipment':m['gear'][:]})
        receipt.update(status='SETTLED',settlement_id=s['last_settlement_id'],settled_day=s['day'])
    if rows:game.log('escort_return_settled',people=deepcopy(rows),settlement_id=s['last_settlement_id'])
    return rows
