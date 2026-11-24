"""Witnessed action ledger and next-departure, finite enemy responses."""
from copy import deepcopy
from collections import Counter
import hashlib
import json
import combat as c
import adaptation_geometry as geometry
from data import keyed_rng


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def check(ok,message):
    if not ok:raise ValueError(message)
def initialize(game):
    game.s['learning']={'battles':[],'seen_moves':[],'applications':[],'departures':{},'completed_departures':[],
                        'passages':[],'camp_uses':[],'route_recording':False}
def state(game):return game.s['learning']


def observers(enc):
    return [u['instance_id'] for u in enc['units'] if u.get('source')=='M']


def prepare_battle(cat,b,enc):
    # The tutorial apparition arrives after combat; it cannot witness earlier actions.
    enabled=not enc['encounter_id'].startswith(('INTRO-','TUT'))
    b['learning']={'observers':observers(enc) if enabled else [],'events':[],'seen_moves':[],
                   'deployment_recorded':False,'passages':[],'camp_uses':[],'application':None,'counterplay':[]}
    b['adaptation']=deepcopy(enc.get('adaptation'))
    for a in b['actors']:
        if a['side']=='enemy':a['observation_role']=next((u.get('role','normal') for u in enc['units'] if u['instance_id']==a['id']),'normal')


def witnessed(cat,b,actor,target=None):
    data=b.get('learning')
    if not data or not actor:return []
    board=c.cells(cat,b)
    return [a['id'] for a in b['actors'] if a['id'] in data['observers'] and a['hp']>0 and not a.get('boss_part')
            and c.visible(cat,board,a['pos'],actor['pos']) and (not target or c.visible(cat,board,a['pos'],target['pos']))]


def add(cat,b,metric,event,actor,target=None,value=1,**extra):
    witness=witnessed(cat,b,actor,target)
    if not witness:return
    eid=event.get('event_id',event.get('action_id'))+':'+metric
    if any(r['id']==eid for r in b['learning']['events']):return
    row={'id':eid,'metric':metric,'battle_id':b['battle_id'],'event_id':event.get('event_id'),
         'action_id':event.get('action_id',event.get('origin_action_id',event.get('cast_id',eid))),
         'actor':actor['id'],'target':target['id'] if target else None,'position':actor['pos'][:],
         'lane':geometry.lane(actor['pos'],cat.boards[b['board_id']]),'witnesses':witness,'tick':b['tick'],'value':value,**extra}
    b['learning']['events'].append(row)


def tick_start(cat,b):
    data=b.get('learning')
    if not data or data['deployment_recorded']:return
    data['deployment_recorded']=True
    players=[a for a in b['actors'] if a['side']=='player' and a['hp']>0]
    deploy=cat.boards[b['board_id']]['player_deploy_cells'];front=max(p[1] for p in deploy)
    for a in players:
        event={'event_id':b['battle_id']+':deployment:'+a['id'],'action_id':'deployment:'+a['id']}
        if a['pos'][1]>=front:add(cat,b,'front_axis_actors',event,a)
        elif any(x is not a and x['pos'][1]<front and c.distance(a['pos'],x['pos'])==1 for x in players):add(cat,b,'rear_cluster_actors',event,a)


def observe(cat,b,event):
    data=b.get('learning')
    if not data:return
    actors={a['id']:a for a in b['actors']};a=actors.get(event.get('actor',event.get('actor_id')));v=actors.get(event.get('target',event.get('target_id')))
    kind=event['type'];mid=event.get('move',event.get('action'))
    if a and a['side']=='enemy' and kind=='release':
        board=c.cells(cat,b)
        if any(p['hp']>0 and p['side']=='player' and c.visible(cat,board,p['pos'],a['pos']) for p in b['actors']):
            if mid not in data['seen_moves']:data['seen_moves'].append(mid)
    if a and a['side']=='player':
        if kind=='basic_start':add(cat,b,'basic_starts',event,a,v)
        if kind=='windup':
            add(cat,b,'finite_active_starts',event,a,v)
            if b['tick']<=2:add(cat,b,'finite_active_starts_in_first_two_ticks',event,a,v)
        if kind=='hit' and v and v['side']=='enemy' and event.get('raw',0)>0:
            amount=event.get('actual_hp_damage',0)+event.get('absorbed',0)
            if amount>0:
                add(cat,b,'direct_damage',event,a,v,amount)
                dtype=event.get('damage_type',a['attack_type']);ranged=event.get('hit_distance',0)>1
                if dtype=='physical':
                    add(cat,b,'physical_direct_hits',event,a,v);add(cat,b,'physical_direct_damage',event,a,v,amount)
                elif ranged:
                    add(cat,b,'ranged_magic_direct_hits',event,a,v);add(cat,b,'ranged_magic_direct_damage',event,a,v,amount)
                if mid=='BASIC' and event.get('hit_distance')==1:
                    add(cat,b,'adjacent_basic_hits',event,a,v)
                    if event.get('flank'):add(cat,b,'adjacent_flank_hits',event,a,v)
        if kind=='heal' and event.get('effective',0)>0:add(cat,b,'effective_heals',event,a,v)
        if kind=='standard_mark_consumed':add(cat,b,'standard_marks_consumed',event,a,v,role=v.get('observation_role','normal') if v else 'normal')
        if kind in ('plan_cast_delayed','cast_delayed','book_cast_delayed'):add(cat,b,'distinct_casts_delayed',event,a,v,cast_id=event.get('cast_id'))
        if kind=='movement_block':add(cat,b,'move_blocks_inflicted',event,a,v)
        if kind in ('evade','plan_move') and event.get('danger_ids'):
            add(cat,b,'danger_avoid_moves',event,a,danger_ids=event['danger_ids'])
    if kind=='hit' and a and a['side']=='enemy' and v and v['side']=='player' and event.get('absorbed',0)>0:
        add(cat,b,'shield_damage_absorbed',event,v,a,event['absorbed'])
    patch=b.get('adaptation')
    if patch and patch.get('components'):
        for component in patch['components']:
            if a and a['id'] in component['rules'] and kind=='windup' and mid==component['rules'][a['id']]['move_id']:
                data.setdefault('applications',{}).setdefault(component['card'],{'event_id':event['event_id'],'tick':b['tick'],'kind':'original_move_started'})
    elif patch and a and a['id'] in patch['rules'] and kind=='windup' and mid==patch['rules'][a['id']]['move_id']:
        if not data['application']:data['application']={'event_id':event['event_id'],'tick':b['tick'],'kind':'original_move_started'}
    if patch and data['application'] and a and a['side']=='player' and event.get('danger_ids'):
        adapted_actions={e['action_id'] for e in b['events'] if e['type']=='windup' and e.get('adaptation_card')==patch['card']}
        if adapted_actions&set(event['danger_ids']):data['counterplay'].append({'event_id':event['event_id'],'kind':'left_locked_historical_attack','action_id':event.get('action_id')})
    if patch and data['application'] and kind=='hit' and a and a['side']=='player' and event.get('actual_hp_damage',0)>0 and geometry.lane(a['pos'],cat.boards[b['board_id']])!=patch['history'].get('lane'):
        data['counterplay'].append({'event_id':event['event_id'],'kind':'damage_from_other_lane','action_id':event.get('action_id')})


def window(game):return state(game)['battles'][-6:]


def evidence(game,card):
    rows=window(game);spec=card['evidence'];metric=spec['metric']
    events=[r for b in rows for r in b['events'] if r['metric']==metric]
    # A cast or gateway can only count once per completed battle.
    if metric in ('distinct_casts_delayed','same_gateway_entries','side_lamp_passages'):
        unique={}
        for r in events:unique.setdefault((r['battle_id'],r.get('cast_id',r.get('approach_tag',r['id']))),r)
        events=list(unique.values())
    def total(m):return sum(r['value'] for b in rows for r in b['events'] if r['metric']==m)
    if sum(r['value'] for r in events)<spec['min_events'] or len({r['battle_id'] for r in events})<spec['min_distinct_battles']:return None
    if 'share_metric' in spec:
        denominator=total('direct_damage');numerator=total(spec['share_metric'].replace('_share',''))
        if not denominator or numerator/denominator<spec['min_share']:return None
    if 'at_most_metric' in spec and total(spec['at_most_metric'])>spec['max_events']:return None
    if metric in ('same_gateway_entries','side_lamp_passages'):
        tags=Counter(r['approach_tag'] for r in events);tag=min(tags,key=lambda x:(-tags[x],x));events=[r for r in events if r['approach_tag']==tag]
        if len(events)<spec['min_events'] or len({r['battle_id'] for r in events})<spec['min_distinct_battles']:return None
    lanes=Counter(r['lane'] for r in events);chosen=min(lanes,key=lambda x:(-lanes[x],x))
    roles=Counter(r.get('role','normal') for r in events)
    return {'battle_ids':list(dict.fromkeys(r['battle_id'] for r in events)), 'event_ids':[r['id'] for r in events],
            'lane':chosen,'role':min(roles,key=lambda x:(-roles[x],x)), 'metric':metric,'value':sum(r['value'] for r in events)}


def eligible(game,enc,last=False):
    data=state(game);rank=min(5,enc.get('effective_threat',int(enc.get('threat_rank_id','TH1')[2:])));kinds={u['enemy_id'] for u in enc['units']}
    if kinds&{'BX01','BX02','BX03','ADMIN'}:return []
    slots=game.cat.build['adaptation_contract']['normal_slots_by_threat_rank'].get('TH'+str(rank),0)
    if kinds&{'MG01','MG02','MG03','MG04'}:slots=1
    if not slots:return []
    recent=[x['card'] for x in data['applications'][-2:]];result=[]
    for card in game.cat.build['adaptations']:
        aid=card['adaptation_id']
        if rank<card['min_threat_rank'] or aid in recent:continue
        uses=[u for u in data['applications'] if u['card']==aid]
        if uses and sum(n>uses[-1]['departure'] for n in data['completed_departures'])<2:continue
        seen=set(data['seen_moves'])&set(card['allowed_move_ids'])
        if not seen or (aid=='AD17' and len(seen)<2):continue
        proof=evidence(game,card)
        if not proof:continue
        # All modified actors must use moves actually seen, not just another move on the card.
        patch=geometry.carrier(game.cat,enc,card,proof,last)
        if not patch or not set(patch['move_ids'])<=set(data['seen_moves']):continue
        patch['last_applied']=uses[-1]['departure'] if uses else -1
        result.append(patch)
    return result


def bind(game,manifest):
    import depth_growth
    data=state(game);locked={};number=game.s['expedition_no']
    floors={rid:min(level for path in manifest['paths'] for node,level in zip(path,depth_growth.path_levels(manifest['depth_growth'],path)) if node==rid) for rid in manifest['regions']}
    for rid,region in manifest['regions'].items():
        for node,binding in region['encounters'].items():
            ids=set(binding.get('candidate_ids',[]))|{binding[k] for k in ('encounter_id','default_encounter_id') if k in binding}
            for eid in sorted(ids):
                enc=game.cat.encounter_for_board(eid,binding['board_id']);enc['board_id']=binding['board_id']
                if not any(u['enemy_id'].startswith(('MG','BX')) for u in enc['units']):enc['effective_threat']=floors[rid]
                candidates=eligible(game,enc,last=rid==manifest['target'] and node=='G')
                key=rid+':'+node+':'+eid
                if candidates:
                    rng=keyed_rng(game.s['seed'],'adaptation:'+key);rng.shuffle(candidates)
                    locked[key]=min(candidates,key=lambda x:x['last_applied'])
                    locked[key]['public_threat_floor']=enc.get('effective_threat',int(enc['threat_rank_id'][2:]))
    payload={'departure':number,'seed':game.s['seed'],'locked':locked,'history_battles':[r['battle_id'] for r in window(game)],
             'seen_moves':data['seen_moves'][:],'route_recording':data['route_recording']}
    payload['sha256']=digest(payload);data['departures'][str(number)]=deepcopy(payload)
    manifest['learning']=payload
    from joint_sampling_model import digest as manifest_digest
    manifest.pop('manifest_sha256',None);manifest['manifest_sha256']=manifest_digest(manifest)


def patch_for(game,slot,eid):
    manifest=game.s.get('manifest') or {}
    return manifest.get('learning',{}).get('locked',{}).get(game.s['region']+':'+slot+':'+eid)


def battle_started(game,b):
    data=b.get('learning')
    if not data:return
    s=game.s
    data['passages']=[deepcopy(p) for p in state(game)['passages'] if p['departure']==s['expedition_no'] and p['region']==s['region'] and p['target']==s['site']]
    data['camp_uses']=[deepcopy(p) for p in state(game)['camp_uses'] if p['departure']==s['expedition_no'] and not p.get('battle_id')]
    if b.get('adaptation') and b['adaptation']['positions']:
        data['application']={'event_id':b['battle_id']+':adaptation_deployed','tick':0,'kind':'original_deployment_changed'}
    for patch in (b.get('adaptation') or {}).get('components',[]):
        if patch['positions']:data.setdefault('applications',{})[patch['card']]={'event_id':b['battle_id']+':'+patch['card']+':deployed','tick':b['tick'],'kind':'original_deployment_changed'}


def passage(game,origin,destination):
    if game.s['mission']!='ORDINARY':return
    data=state(game);manifest=game.s['manifest'];watch=[]
    # Existing M patrols publicly observe only the entrance to their own encounter.
    if destination in game.manifest_region['encounters'] and destination not in game.current['cleared']:
        import depth_growth
        enc=depth_growth.current_encounter(game,destination);watch=observers(enc)
    if manifest.get('learning',{}).get('route_recording'):
        watch.append('DECLARED-ROUTE-LEDGER:'+game.s['region'])
    # The existing road's relative approach is stable; no future branch is consulted.
    tag='left' if origin in ('A','C') else 'right' if origin in ('B','D','L') else 'center'
    key=f"{game.s['expedition_no']}:{game.s['region']}:{origin}:{destination}:{game.s['sequence']}"
    data['passages'].append({'id':key,'departure':game.s['expedition_no'],'region':game.s['region'],'origin':origin,'target':destination,
        'approach_tag':tag,'witnesses':watch,'witness_context_id':game.s['region']+':'+destination,'passage_tx_id':key})


def camp(game):
    s=game.s
    if s['mission']=='ORDINARY' and s['manifest'].get('learning',{}).get('route_recording'):
        state(game)['camp_uses'].append({'id':f"{s['expedition_no']}:{s['region']}:camp",'departure':s['expedition_no'],'region':s['region'],
          'witnesses':['DECLARED-ROUTE-LEDGER:'+s['region']],'battle_id':None})


def completed(game,b):
    data=state(game);raw=b.get('learning')
    if game.s['debug_tainted'] or not raw or not b['result'] or b['tick']<1:return
    if any(x['battle_id']==b['battle_id'] for x in data['battles']):return
    events=deepcopy(raw['events'])
    for p in raw['passages']:
        if not p['witnesses']:continue
        for metric in ('same_gateway_entries','side_lamp_passages'):
            eid=b['battle_id']+':'+metric+':'+p['approach_tag']
            if any(e['id']==eid for e in events):continue
            events.append({'id':eid,'event_id':p['id'],'action_id':p['passage_tx_id'],'metric':metric,'battle_id':b['battle_id'],
              'actor':'EXPEDITION','target':p['target'],'position':None,'lane':p['approach_tag'],'approach_tag':p['approach_tag'],
              'witnesses':p['witnesses'][:],'witness_context_id':p['witness_context_id'],'value':1,'tick':0,'passage_id':p['id']})
    for p in raw['camp_uses']:
        original=next(x for x in data['camp_uses'] if x['id']==p['id'])
        if original['battle_id']:continue
        original['battle_id']=b['battle_id']
        events.append({'id':b['battle_id']+':'+p['id'],'event_id':p['id'],'action_id':p['id'],'metric':'camp_supply_uses',
          'battle_id':b['battle_id'],'actor':'EXPEDITION','target':p['region'],'position':None,'lane':'center','witnesses':p['witnesses'][:],'value':1,'tick':0})
    row={'battle_id':b['battle_id'],'departure':game.s['expedition_no'],'result':b['result'],'events':events,
         'seen_moves':raw['seen_moves'][:],'ticks':b['tick'],'counterplay':deepcopy(raw['counterplay'])}
    row['sha256']=digest(row);data['battles'].append(row)
    data['seen_moves']=sorted(set(data['seen_moves'])|set(raw['seen_moves']))
    patch=b.get('adaptation')
    for component in (patch.get('components',[patch]) if patch else []):
        receipt=raw.get('applications',{}).get(component['card']) if patch.get('components') else raw['application']
        if receipt and not any(x['departure']==game.s['expedition_no'] and x['card']==component['card'] for x in data['applications']):
            data['applications'].append({'card':component['card'],'departure':game.s['expedition_no'],'battle_id':b['battle_id'],
                                         'receipt':deepcopy(receipt)})


def settle_departure(game):
    if game.s.get('mission')!='ORDINARY':return
    number=game.s['expedition_no'];data=state(game)
    # Leaving from the starting point without completing combat is not a cooldown farm.
    if game.s['battle_reports'] and not game.s['debug_tainted'] and number not in data['completed_departures']:data['completed_departures'].append(number)


def handle(game,args):
    data=state(game)
    if args and args[0]=='route':
        check(game.s['phase']=='TOWN' and len(args)==2 and args[1] in ('on','off'),'learning route on/off：城内选择下一趟公开路账记录。')
        check('ST-104' in game.s['unlocked_facts'],'公开路账需旧路档案ST-104。')
        data['route_recording']=args[1]=='on';return '下一趟路账选择已保存；实际通行/营地使用且关联完成战斗才产生证据。'
    if args==['cards']:
        return '\n'.join(f"AD{i+1:02} {name}：代价{geometry.COSTS[i]}；反制{geometry.COUNTERS[i]}" for i,name in enumerate(geometry.NAMES))
    if args==['history']:
        return json.dumps({'window':[{'battle_id':r['battle_id'],'events':len(r['events']),'result':r['result']} for r in window(game)],
                           'seen_moves':data['seen_moves'],'applied':data['applications']},ensure_ascii=False,indent=2)
    if args==['preview']:
        if game.s['phase']=='TOWN':
            import campaign,event_memory,supplies
            # Generate the same manifest from permitted public/history inputs only; no payment or party inspection.
            shadow=deepcopy(game.s)
            try:
                s=game.s
                m,_=game.cat.manifest(s['route'],s['seed'],event_memory.presented_history(game),s['refugee'],s['directed_refugee'],s['water'],s['directed_water'],s['medicine'],s['directed_medicine'],s['cases'],s['directed_local'],difficulty=s['difficulty'],tier_facts=s['unlocked_facts'],campaign_facts=s['unlocked_facts'] if campaign.active(game) else None)
                campaign.bind_challenge(game,m);supplies.bind(game,m);bind(game,m)
            finally:game.s=shadow
            return json.dumps(m['learning'],ensure_ascii=False,indent=2)
        return json.dumps((game.s.get('manifest') or {}).get('learning',{}),ensure_ascii=False,indent=2)
    check(not args or args==['status'],'learning status/history/cards/preview；learning route on/off')
    return describe(game)


def describe(game):
    data=state(game);s=game.s
    result=f"战术回应：已结算观察{len(data['battles'])}场，证据窗口最近6场；路账{'开' if data['route_recording'] else '关'}。learning history/preview查看已知记录。"
    if s['phase']=='EXPLORE' and s['site'] in game.manifest_region['encounters']:
        import depth_growth
        enc=depth_growth.current_encounter(game,s['site']);watch=observers(enc)
        result+='\n本场公开魔王哨兵：'+(','.join(watch) or '无；不追认场外视角')
        patch=enc.get('adaptation')
        if patch:result+='\n'+patch['card']+' '+patch['name']+'；证据 '+','.join(patch['history']['battle_ids'])+'；代价 '+patch['cost']+'；可用反制 '+patch['counterplay']
        else:result+='\n本场基础阵容，无已锁回应。'
    return result


def validate(game):
    data=state(game);ids=[]
    for row in data['battles']:
        check(row['sha256']==digest({k:v for k,v in row.items() if k!='sha256'}),'观察回执内容变化。')
        check(row['ticks']>0 and row['result'] in ('VICTORY','DEFEAT','RETREAT','STALEMATE'),'观察缺少实际战斗结算。')
        ids.append(row['battle_id']);eids=[]
        for e in row['events']:
            check(e['battle_id']==row['battle_id'] and e['witnesses'] and e['action_id'] and e['value']>0,'观察缺少动作或当时见证。');eids.append(e['id'])
        check(len(eids)==len(set(eids)),'观察事件重复。')
    check(len(ids)==len(set(ids)),'重复战斗进入证据窗口。')
    check(data['seen_moves']==sorted({m for r in data['battles'] for m in r['seen_moves']}),'已见招式缺少结算凭据。')
    uses=set()
    for a in data['applications']:
        check(a['battle_id'] in ids and (a['departure'],a['card']) not in uses,'适应采用凭据缺失或重复。');uses.add((a['departure'],a['card']))
    for n,d in data['departures'].items():
        check(str(d['departure'])==n and d['sha256']==digest({k:v for k,v in d.items() if k!='sha256'}),'出征锁卡凭据变化。')
        check(set(d['history_battles'])<=set(ids),'锁卡引用不存在的历史。')
        for patch in d['locked'].values():check(patch['card'] in {a['adaptation_id'] for a in game.cat.build['adaptations']} and set(patch['history']['battle_ids'])<=set(d['history_battles']),'回应引用本趟新证据。')
    manifest=game.s.get('manifest') or {}
    if 'learning' in manifest:check(manifest['learning']==data['departures'][str(manifest['learning']['departure'])],'地图与锁卡回执不一致。')
