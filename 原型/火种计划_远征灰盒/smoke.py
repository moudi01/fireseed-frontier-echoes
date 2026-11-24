"""A disclosed main-route probe, not a model of unpredictable human players."""
from collections import deque


def walk(game, destination):
    start=game.s['site'];queue=deque([(start, [])]);seen={start}
    while queue:
        site,path=queue.popleft()
        if site==destination:
            for node in path:game.execute('move '+node)
            return
        if site in game.manifest_region['encounters'] and site not in game.current['cleared']:continue
        for a,b in game.layout['edges']:
            if site not in [a,b]:continue
            nxt=b if a==site else a
            if nxt not in seen:seen.add(nxt);queue.append((nxt,path+[nxt]))
    raise ValueError('无法合法走到 '+destination)


POLICIES = {
    'baseline': '主路；倒地才换人；全员推进；准备品首战集中使用；半血医疗',
    'rotation': '主路；每战按当前血量比例轮换；全员推进；准备品分战使用；65%血线医疗',
    'evade': 'rotation基础上全员避险；仅响应上一拍已公开预警',
    'explore': 'evade基础上尝试可达普通事件并回访；可出战少于4人时提前返城；不打精英',
}


def visit_events(game):
    for slot in ['A', 'B', 'C', 'D']:
        if slot not in game.manifest_region['events']: continue
        if game.current['events'][slot]['state'] in ['RESOLVED', 'DECLINED']: continue
        try: walk(game, slot)
        except ValueError: continue  # Unreachable behind an uncleared battle, not teleported.
        card, binding, state = game.event_info()
        if card['event_id'] == 'EV04':
            for n in (1, 2):
                if 'bell_'+str(n) not in state['steps']: game.execute('rub '+str(n))
        standing = [m for m in game.s['party'] if m['hp'] > 0]
        if not standing: return
        target = min(standing, key=lambda m: (m['hp']/m['stats']['hp'], m['instance_id']))
        for option in card['options']:
            if option['option_id'] == 'PASS' or option['option_id'] not in binding['enabled_options']: continue
            offer = game.offer(card, option) if option.get('reward_bundle_id') == 'RB-PLAN' else []
            import plan_offers
            compatible=plan_offers.capabilities(game)
            plan = next((x for x in offer if compatible[x]), offer[0] if offer else '')
            try: game.execute('choose '+option['option_id']+' '+target['instance_id']+' '+plan)
            except ValueError as error:
                game.log('probe_event_unavailable', event=card['event_id'], option=option['option_id'], reason=str(error))
                continue
            if plan:
                equipped = list(dict.fromkeys(game.s['plans_equipped']+[plan]))[-3:]
                game.execute('plan '+' '.join(equipped))
            break
        else: game.execute('choose PASS')


def play(game, debug=False, policy='baseline'):
    """Skip optional sites, use station after B1, medical below half HP, camps.
    Rotate out downed members; stop or return if no legal deployment remains.
    This procedure never heals, injects loot or forces wins unless debug=True.
    """
    if policy not in POLICIES: raise ValueError('未知探针策略：'+policy)
    game.log('probe_policy', policy=policy, description=POLICIES[policy], future_events_read=False)
    game.execute('depart')
    while game.s['phase']=='EXPLORE':
        for slot in ['B1','B2','G']:
            if policy == 'explore': visit_events(game)
            if policy == 'explore' and sum(m['hp']>0 and m['erosion']<100 for m in game.s['party']) < 4:
                walk(game,'I');game.execute('return CONFIRM');return
            for m in game.s['party']:
                if m['deployed'] and (policy != 'baseline' or m['hp']<=0 or m['erosion']>=100):game.execute('deploy '+m['instance_id']+' off')
            deployed=[m for m in game.s['party'] if m['deployed']]
            candidates=game.s['party'] if policy == 'baseline' else sorted(game.s['party'],key=lambda m:(-m['hp']/m['stats']['hp'],m['instance_id']))
            for m in candidates:
                if sum(x['cost'] for x in deployed)>=game.s['budget']['battle']:break
                if not m['deployed'] and m['hp']>0 and m['erosion']<100 and sum(x['cost'] for x in deployed)+m['cost']<=game.s['budget']['battle']:
                    game.execute('deploy '+m['instance_id']+' on');deployed.append(m)
            if not deployed:
                walk(game,'I');game.execute('return CONFIRM');return
            for i,m in enumerate(deployed):
                q,r=game.cat.formation[i]
                game.execute(f"place {m['instance_id']} {q} {r} 1")
                game.execute(f"stance {m['instance_id']} "+('evade' if policy in ('evade','explore') else 'advance'))
            threshold=.5 if policy == 'baseline' else .65
            if any(m['hp'] < m['stats']['hp']*threshold for m in deployed) and game.s['medical']:
                game.execute('medical')
            # Use existing carried tools only, with actual legal targets and slot persistence.
            prepared=False
            for item in list(game.s['pouch']):
                wounded=min(deployed,key=lambda m:m['hp']/m['stats']['hp'])
                target=wounded if item=='CO01' else deployed[0]
                if item=='CO01' and target['hp']>=target['stats']['hp']-9:continue
                if item=='CO02':
                    wounded_members=[m for m in deployed if m['hp'] < m['stats']['hp']-9]
                    if policy == 'baseline' or len(wounded_members)<2:continue
                    try:game.execute('use CO02 '+','.join(m['instance_id'] for m in wounded_members))
                    except ValueError:pass
                    continue
                if policy != 'baseline' and item not in ('CO01','CO02'):
                    if prepared:continue
                    target=max(deployed,key=lambda m:m['stats']['physical_attack']) if item in ('CO04','CO09') else wounded
                try:game.execute(f"use {item} {target['instance_id']}")
                except ValueError:pass
                else:
                    if item not in ('CO01','CO02'):prepared=True
            walk(game,slot);game.execute('fight')
            if debug:game.execute('debug_win CONFIRM')
            else:
                game.execute('run 600')
                if game.s['phase']=='BATTLE':
                    import bosses
                    if bosses.paused(game.s['battle']):
                        game.log('batch_paused_for_dialogue',window=game.s['battle']['boss_dialogue_queue'][0]['window'])
                    else:game.log('batch_diagnostic_stop',reason='600 ticks without result')
                    game.persist();return
            if game.s['phase']!='EXPLORE':return
            if slot=='B1':
                walk(game,'S')
                try:game.execute('station')
                except ValueError:pass
        if policy == 'explore':visit_events(game)
        walk(game,'X');choices=game.next_regions()
        if not choices:game.execute('return CONFIRM');return
        game.execute('camp');game.execute('next '+choices[0]+' CONFIRM')
