"""Public expedition tiers; fixed trial floors, never scaled by party strength."""
from copy import deepcopy
import combat
import depth_growth
import necromancy

VERSION='EXPEDITION-TIER-0.1'
TIERS={
    'D0':dict(name='常规',floor=1,requires='ST-102',probability=[1,5]),
    'D1':dict(name='强敌',floor=2,requires='CH1_COMPLETE',probability=[1,2]),
    'D2':dict(name='险境',floor=4,requires='CH2_COMPLETE',probability=[3,4]),
}
# Explicit per-region squads and costs, not an automatic multiplier on headcount.
SQUADS={
    'RG01':(['EN04','EN23','EN20','EN19'],6),
    'RG06':(['EN12','EN20','EN19','EN01'],5),
    'RG07':(['EN23','EN21','EN22','EN20'],6),
    'RG08':(['EN23','EN22','EN20','EN21'],6),
    'RG02':(['EN04','EN23','EN22'],6),
    'RG03':(['EN25','EN23','EN22','EN20'],8),
    'RG04':(['EN24','EN23','EN22','EN21'],9),
    'RG05':(['EN25','EN24','EN23','EN21'],10),
}


def unlocked(difficulty,facts):
    if difficulty not in TIERS:return False
    facts=set(facts)
    if 'ST-104' in facts:facts.add('CH1_COMPLETE')
    return TIERS[difficulty]['requires'] in facts


def check(difficulty,facts):
    if difficulty not in TIERS:raise ValueError('远征档位须为D0／D1／D2。')
    if not unlocked(difficulty,facts):raise ValueError('档位未解锁：'+TIERS[difficulty]['requires'])


def caps(profile,difficulty):
    result=deepcopy(profile['reward_caps'])
    result['books']={2:1,3:2,4:3}[profile['region_count']]
    if difficulty=='D2':
        result['equipment']=max(result['equipment'],3)
        result['books']=max(result['books'],2)
    return result


def install(cat):
    positions=[[2,5],[4,5],[3,6],[5,6]]
    for rid,(members,budget) in SQUADS.items():
        source=deepcopy(cat.encounters['FX-'+rid+'-N01'])
        eid='TIER2-'+rid+'-N01'
        source.update(encounter_id=eid,name='险境协同·'+source['name'],units=[],
                      threat_budget=budget,required_briefed_species=list(dict.fromkeys(members)))
        for i,uid in enumerate(members):
            unit=deepcopy(cat.enemy_templates[uid]);pi=1-i if rid=='RG05' and i<2 else i
            unit.update(instance_id=f'{uid}-T2-{i+1}',hp_owner_id=f'{uid}-T2-{i+1}',position=positions[pi][:],facing='D4',role='normal',elite_promoted=False)
            if any(m['move_id'] not in combat.SUPPORTED_MOVES for m in unit['moves']):raise ValueError('高档新编队含未实现招式：'+uid)
            source['units'].append(unit)
        if 'EN24' in members:
            owner=next(u['instance_id'] for u in source['units'] if u['enemy_id']=='EN24')
            bone_id='FX02-T2-'+rid;spawn=deepcopy(cat.enemy_templates['EN21'])
            spawn.update(instance_id='EN21-T2-SUMMON-'+rid,position=[1,6],facing='D4',role='normal',elite_promoted=False)
            source.update(spawn_options=[spawn],mechanisms=[necromancy.bone(bone_id,[1,6])],spawn_reserve_cost=1,spawn_limit=1,
                necromancy={'bindings':{owner:{'bone':bone_id,'spawn':spawn['instance_id']}},'revive_per_caster':2,'revive_per_body':1,'revive_hp_percent':50})
        if sum(u['threat_cost'] for u in source['units']+source.get('spawn_options',[]))!=budget:raise ValueError('高档预算不符：'+eid)
        if len(source['units'])+len(source.get('spawn_options',[]))>6:raise ValueError('高档人数超限：'+eid)
        necromancy.validate(source)
        cat.encounters[eid]=depth_growth.encounter(cat,source,int(source['threat_rank_id'][2:]),depth_growth.policy(cat))


def bind(cat,manifest,difficulty,facts,seed,rng_factory):
    check(difficulty,facts)
    tier=deepcopy(TIERS[difficulty])
    manifest['tier']={'version':VERSION,'id':difficulty,**tier,'unlock_facts':sorted(set(facts)),
        'trial_parameters':True,'balance_certified':False}
    manifest['depth_growth']['tier_floor']=tier['floor']
    manifest['loot_policy']={'difficulty':difficulty,'tables':deepcopy([t for t in cat.loot['quality_tables'] if t['difficulty_id']==difficulty]),
        'pity':deepcopy(cat.loot['quality_contract']['pity'])}
    if difficulty=='D0':
        from fantasy_enemies import bind_manifest
        bind_manifest(cat,manifest,seed,rng_factory);return
    decisions={}
    for rid,region in sorted(manifest['regions'].items()):
        pool=['FX-'+rid+'-N01'] if difficulty=='D1' else ['FX-'+rid+'-N01','TIER2-'+rid+'-N01']
        if any(eid not in cat.encounters for eid in pool):raise ValueError('高档候选缺失：'+rid)
        events={e['event_id'] for e in region['events'].values()}
        options=[];excluded={}
        for slot in ('B1','B2','G'):
            binding=region['encounters'][slot]
            for eid in pool:
                reason=None;encounter=cat.encounters[eid]
                if slot=='B1' and len(binding.get('candidate_ids',[]))>1:reason='PRELOCKED_EVENT_VARIANTS'
                elif binding['board_id'] not in encounter['allowed_board_variants']:reason='BOARD_NOT_ALLOWED'
                elif slot=='B2' and 'EV08' in events and not any(u['enemy_id']=='EN04' for u in encounter['units']):reason='EV08_REQUIRES_GUARD'
                if reason:excluded[slot+'/'+eid]=reason
                else:options.append([slot,eid])
        if not options:raise ValueError('高档编队没有合法战槽：'+rid)
        rng=rng_factory(seed,'tier/'+VERSION+'/'+difficulty+'/'+rid)
        numerator,denominator=tier['probability']
        decision={'pool':pool,'eligible':options,'excluded':excluded,'selected_slot':None,'encounter_id':None}
        if rng.randrange(denominator)<numerator:
            slot,eid=rng.choice(options);binding=region['encounters'][slot]
            decision.update(selected_slot=slot,encounter_id=eid,original_binding=deepcopy(binding))
            if slot=='B1':binding.update(default_encounter_id=eid,candidate_ids=[eid])
            else:binding['encounter_id']=eid
        decisions[rid]=decision
    manifest['tier_pool']={'version':VERSION,'probability':tier['probability'],'max_replaced_per_region':1,'decisions':decisions,
        'scope':'one ordinary-slot overlay; other encounters and optional elites retain baseline omissions'}


def quality(game,band,preview_difficulty=None):
    s=game.s;manifest=s.get('manifest') or {}
    frozen=manifest.get('loot_policy') if s.get('mission')=='ORDINARY' else None
    difficulty=preview_difficulty or (frozen['difficulty'] if frozen else 'D0')
    if preview_difficulty:frozen=None
    tables=frozen['tables'] if frozen else game.cat.loot['quality_tables']
    table=next(t for t in tables if t['difficulty_id']==difficulty and t['event_band']==band)
    rules=frozen['pity'] if frozen else game.cat.loot['quality_contract']['pity']
    prior=deepcopy(s['quality_pity']);weights=deepcopy(table['weights'])
    if prior['non_q3']>=rules['Q3_after_non_Q3_streak']:weights={'Q1':0,'Q2':0,'Q3':100}
    elif prior['q1']>=rules['Q2_after_Q1_streak']:weights['Q2']+=weights['Q1'];weights['Q1']=0
    return {'difficulty':difficulty,'table_id':table['table_id'],'base_weights':deepcopy(table['weights']),
        'prior_pity':prior,'effective_weights':weights,'minimum':'Q3' if weights['Q3']==100 else 'Q2' if weights['Q1']==0 else 'Q1'}


def claimed(game,quality_value):
    old=game.s['quality_pity']
    game.s['quality_pity']={'q1':old['q1']+1 if quality_value=='Q1' else 0,'non_q3':old['non_q3']+1 if quality_value!='Q3' else 0}


def public(game):
    s=game.s;ordinary=s.get('mission')=='ORDINARY';frozen=(s.get('manifest') or {}).get('tier') if ordinary else None
    chosen=frozen['id'] if frozen and s['phase']!='TOWN' else s['difficulty']
    route=next(r for r in game.cat.config['routes'] if r['route_id']==s['route'])
    profile=game.cat.multi['profiles'][route['profile']]
    limits=caps(profile,chosen)
    reward_limits={'materials':limits['materials_by_difficulty'][chosen],'equipment':limits['equipment'],'books':limits['books']}
    if frozen and s['phase']!='TOWN':
        saved=s['manifest']['caps']
        reward_limits={'materials':saved['material_units'],'equipment':saved['gear_claims'],'books':saved['book_claims']}
    from check_multi_region import routes
    world={r['region_id']:set(r['neighbors']) for r in game.cat.multi['regions']}
    allowed={r['region_id'] for r in game.cat.multi['regions'] if set(r['access_requires_all'])<=set(route['facts'])}
    paths=list(routes(world,allowed,profile['region_count'],route['selected_path'][0],route['selected_path'][-1]))
    rules=deepcopy(s['manifest']['depth_growth']) if frozen and s['phase']!='TOWN' else depth_growth.policy(game.cat)
    if not frozen or s['phase']=='TOWN':rules['tier_floor']=TIERS[chosen]['floor']
    import late_pressure
    pressure=(s['manifest'].get('progression_pressure') if frozen and s['phase']!='TOWN'
              else late_pressure.preview(game,rules))
    ends=[depth_growth.path_levels(rules,path)[-1] for path in paths]
    import challenge_rewards
    return {'selected':chosen,'floor':frozen['floor'] if frozen and s['phase']!='TOWN' else TIERS[chosen]['floor'],
        'fixed_mission':not ordinary,'can_change':s['phase']=='TOWN','progression_pressure':pressure,
        'choices':[{'id':d,**deepcopy(t),'unlocked':unlocked(d,s['unlocked_facts'])} for d,t in TIERS.items()],
        'quality_pity':deepcopy(s['quality_pity']),
        'challenge_rewards':challenge_rewards.public(game),
        'length':profile['region_count'],'end_level_range':[min(ends),max(ends)] if ends else [],
        'reward_limits':reward_limits,
        'quality_preview':[quality(game,band,chosen if s['phase']=='TOWN' else None) for band in ('salvage','cache','danger_cache')] if ordinary else []}


def describe(game):
    row=public(game);d=row['selected'];rule=TIERS[d]
    if row['fixed_mission']:return '固定任务沿自身规则；普通远征预选'+d+'，不对本任务加档位倍率。'
    text=f"远征档位 {d} {rule['name']} | 起始底线L{row['floor']}（试验参数） | 可用 "+'、'.join(t['id'] for t in row['choices'] if t['unlocked'])
    pressure=row.get('progression_pressure') or {}
    if pressure and (pressure.get('stage_floor',1)>1 or pressure.get('attack_percent',100)!=100):
        origin=pressure.get('milestone') or '路线第'+str(pressure['chapter'])+'章'
        text+=f"\n{pressure.get('stage_name','后期委任')}公开下限L{pressure['stage_floor']}（{origin}）；与地区及档位取最高。"
        text+=f"普通敌人委任系数：生命{pressure['hp_percent']}%、攻击{pressure['attack_percent']}%；固定首领沿独立内容数值。"
    text+='\n品质保底（跨档／跨趟）：'+str(row['quality_pity'])+'；实际领取推进，失败不回退。'
    text+=f"\n长度{row['length']}区，合法路线终点L区间{row['end_level_range']}；领取上限{row['reward_limits']}（非保发）。"
    if d=='D2' and pressure.get('chapter')==3 and pressure.get('milestone')=='FINALE_READY':
        text+='\nL8及以上G门有一次断阵重击：W3，锁最远可见人类原格半径1；释放时内圈仍有人会引爆公开半径3外圈、最多4人，撤空则整招落空。可避险/打断/延后；单击实际入血达本人最大HP一半或被该招击倒会重创，本场仍可救治，战后本趟休战至归城。'
    text+='\n高档只提高已登记协作编队的投放机会，每区至多替换一场；其他敌阵与可选精英仍保留原机制缺项。'
    import challenge_rewards
    text+='\n'+challenge_rewards.describe(game)
    for q in row['quality_preview']:text+=f"\n{q['table_id']} 基础{q['base_weights']} → 本次有效{q['effective_weights']}，最低{q['minimum']}"
    return text
