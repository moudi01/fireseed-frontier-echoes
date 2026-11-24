"""Implemented fantasy troop cards; separate from immutable baseline documents."""
from copy import deepcopy
import combat as c

VERSION = 'FANTASY-TROOPS-0.3'
# Adding a region does not reroll the existing regions' independent lottery.
SAMPLING_VERSION = 'FANTASY-TROOPS-0.1'
STAT_KEYS = ('hp','physical_attack','magic_attack','healing_power','physical_defense','magic_defense')
ROWS = {
    'EN19': ('哥布林劫掠者',1,[46,7,0,0,4,4],1,3,'near'),
    'EN20': ('哥布林弩手',1,[40,6,0,0,2,4],3,4,'projectile'),
    'EN21': ('骷髅刀兵',1,[54,6,0,0,8,4],1,3,'near'),
    'EN22': ('骷髅弓手',2,[52,7,0,0,6,6],4,3,'projectile'),
    'EN23': ('腐尸卫兵',2,[100,6,0,0,10,4],1,4,'near'),
    'EN24': ('死灵术士',3,[64,0,8,0,4,12],3,3,'magic'),
    'EN25': ('吸血鬼剑士',3,[84,9,0,0,10,12],1,3,'near'),
}
CARDS = {
    'EN19': dict(name='侧袭短刀',kind='damage',coefficient=1.2,range=1,windup=1,cooldown=5,cast_limit=2,shape='locked_rear_target'),
    'EN20': dict(name='钉脚弩',kind='damage',coefficient=1.0,range=3,windup=2,cooldown=6,cast_limit=2,shape='locked_cell'),
    'EN21': dict(name='列骨架刀',kind='shield',coefficient=0,range=1,windup=1,cooldown=6,cast_limit=1,shape='private_shield',shield=10,duration_ticks=3),
    'EN22': dict(name='穿阵骨箭',kind='damage',coefficient=.9,range=4,windup=2,cooldown=6,cast_limit=2,shape='locked_axis'),
    'EN23': dict(name='拖拽抱击',kind='damage',coefficient=1.1,range=1,windup=2,cooldown=6,cast_limit=2,shape='locked_adjacent_target'),
    'EN24': dict(name='唤骨',kind='summon',coefficient=0,range=3,windup=2,cooldown=8,cast_limit=1,shape='locked_bones'),
    'EN25': dict(name='饮血刺',kind='damage',coefficient=1.3,range=1,windup=1,cooldown=5,cast_limit=2,shape='locked_adjacent_target'),
}
BRIEFINGS = {
    'EN19': '侧后相邻才起手，锁格1拍；离开锁格可躲。包抄只在最短路并列时优先，不穿人。',
    'EN20': '钉脚弩锁一格，2拍后发射；单位与障碍可挡，命中后仅限制下一拍移动。',
    'EN21': '有相邻友军且正面接敌才架刀；1拍后本人得10盾、持续3拍，不共享。不会自行复起；死灵术士可将遗骸拉起一次。',
    'EN22': '穿阵骨箭锁4格直线，2拍后最多伤前2敌；遇友军或不透射地形停止。',
    'EN23': '抱击锁相邻一格，起手2拍；离开可躲，命中后仅限制下一拍移动，不拉人。',
    'EN24': '唤骨2拍、每战1次，摧毁骨堆可阻止。另可复起骷髅／腐尸：2拍、每战2次，每具最多1次、半血且技能次数不刷新；占住遗骸格或提前击倒术士可阻止，两种施法均可被雾绊延后一次。',
    'EN25': '饮血刺锁相邻一格，1拍后释放，全场2次；离开锁格可躲。普攻与饮血刺按实际生命伤害20%回复，向下取整；盾伤不吸血，同拍致死不能靠吸血复起。',
}
FORMATIONS = {
    'RG01': ('路卡劫掠队',['EN04','EN19','EN20']),
    'RG06': ('林道伏兵',['EN19','EN19','EN20','EN01']),
    'RG07': ('沉船守骨',['EN21','EN21','EN22']),
    'RG08': ('灰场尸哨',['EN23','EN21','EN21']),
    'RG02': ('骨盾驻防',['EN04','EN21','EN22']),
    'RG03': ('废宅猎队',['EN25','EN12','EN20','EN20']),
    'RG04': ('旧墓唤骨',['EN24','EN23','EN22']),
    'RG05': ('军需护送',['EN25','EN24','EN21']),
}
MOVES = {uid+'-A' for uid in ROWS}


def install(catalog):
    import depth_growth
    import necromancy
    for uid,(name,cost,stats,distance,interval,medium) in ROWS.items():
        card={**CARDS[uid], 'move_id':uid+'-A','damage_type':'physical','medium':medium,
              'first_eligible_tick':2,'max_targets':2 if uid=='EN22' else 1,
              'interruptible':True,'delayable_cast':False,'locks_cells':True}
        catalog.enemy_templates[uid]={'enemy_id':uid,'name':name,'source':'M','threat_cost':cost,
            'stats':dict(zip(STAT_KEYS,stats)), 'moves':[card], 'briefing':BRIEFINGS[uid],
            'basic_attack':{'move_id':'BASIC','damage_type':'physical','coefficient':1,
                            'range':distance,'attack_interval':interval,'medium':medium}}
        if uid=='EN25':
            catalog.enemy_templates[uid]['innate_life_steal']={
                'source_id':'EN25-P','percent':20,'eligible_moves':['BASIC','EN25-A']}
        if uid=='EN24':
            card.update(damage_type='magic',delayable_cast=True)
            catalog.enemy_templates[uid]['basic_attack']['damage_type']='magic'
            catalog.enemy_templates[uid]['moves'].insert(0,deepcopy(necromancy.RAISE_CARD))
    # Reuse a formation whose legacy positions already adapt legally to all 8 boards.
    positions=[u['position'] for u in catalog.encounters['RG01-E01']['units']]
    for rid,(name,members) in FORMATIONS.items():
        source=deepcopy(catalog.encounters[rid+'-N01']);eid='FX-'+rid+'-N01'
        source.update(encounter_id=eid,name=name,units=[],required_seen_species=[],required_briefed_species=list(dict.fromkeys(members)),
                      calibration_unsupported_mechanics=[],fantasy_version=VERSION)
        for i,uid in enumerate(members):
            unit=deepcopy(catalog.enemy_templates[uid])
            position_index=1-i if rid=='RG05' and i<2 else i
            unit.update(instance_id=f'{uid}-FX-{i+1}',position=positions[position_index][:],facing='D4',role='normal',elite_promoted=False)
            unit['hp_owner_id']=unit['instance_id'];source['units'].append(unit)
        if 'EN24' in members:
            owner=next(u['instance_id'] for u in source['units'] if u['enemy_id']=='EN24')
            bone_id='FX02-'+rid;spawn=deepcopy(catalog.enemy_templates['EN21'])
            spawn.update(instance_id='EN21-SUMMON-'+rid,position=positions[3][:],facing='D4',role='normal',elite_promoted=False)
            source['spawn_options']=[spawn]
            source.update(spawn_reserve_cost=1,spawn_limit=1)
            source['mechanisms']=[necromancy.bone(bone_id,positions[3])]
            source['necromancy']={'bindings':{owner:{'bone':bone_id,'spawn':spawn['instance_id']}},'revive_per_caster':2,'revive_per_body':1,'revive_hp_percent':50}
        # Standalone laboratory entry uses the native regional tier; expedition
        # growth later reconstructs from raw templates once, not from these stats.
        source=depth_growth.encounter(catalog,source,int(source['threat_rank_id'][2:]),depth_growth.policy(catalog))
        if sum(u['threat_cost'] for u in source['units']+source.get('spawn_options',[])) != source['threat_budget']:
            raise ValueError('奇幻编队预算不符：'+eid)
        necromancy.validate(source)
        catalog.encounters[eid]=source


def bind_manifest(catalog, manifest, seed, rng_factory):
    """Trial 1/5 chance per eligible region, then choose one legal ordinary slot.

    Post-selection overlay preserves all event/reward allocations and prelocked
    route-choice candidates. The trial weight is explicit, not balance-certified.
    """
    decisions={}
    for rid,region in sorted(manifest['regions'].items()):
        if rid not in FORMATIONS:continue
        eid='FX-'+rid+'-N01';source=catalog.encounters[eid];eligible=[];excluded={}
        event_ids={e['event_id'] for e in region['events'].values()}
        for slot in ('B1','B2','G'):
            binding=region['encounters'][slot]
            if slot=='B1' and len(binding.get('candidate_ids',[]))>1:
                excluded[slot]='PRELOCKED_EVENT_VARIANTS';continue
            if binding['board_id'] not in source['allowed_board_variants']:
                excluded[slot]='BOARD_NOT_ALLOWED';continue
            if slot=='B2' and 'EV08' in event_ids and not any(u['enemy_id']=='EN04' for u in source['units']):
                excluded[slot]='EV08_REQUIRES_GUARD';continue
            eligible.append(slot)
        rng=rng_factory(seed,'fantasy/'+SAMPLING_VERSION+'/'+rid)
        selected=rng.randrange(5)==0
        record={'candidate':eid,'eligible_slots':eligible,'excluded_slots':excluded,'selected_slot':None}
        if selected and eligible:
            slot=rng.choice(eligible);binding=region['encounters'][slot]
            record.update(selected_slot=slot,original_binding=deepcopy(binding))
            if slot=='B1':binding.update(default_encounter_id=eid,candidate_ids=[eid])
            else:binding['encounter_id']=eid
        decisions[rid]=record
    manifest['fantasy_pool']={'version':VERSION,'sampling_version':SAMPLING_VERSION,'trial_region_probability':[1,5],
                              'max_added_per_region':1,'balance_certified':False,'decisions':decisions}


def start_target(actor, card, foes, alive, catalog, board):
    """None means wait/use ordinary behavior, (target, locked_cells) starts once."""
    from mechanics import front, line, ray
    mid=card['move_id']
    if mid=='EN21-A':
        friend=any(b is not actor and not b.get('mechanism') and b['side']==actor['side'] and c.distance(actor['pos'],b['pos'])==1 for b in alive)
        enemy=any(c.distance(actor['pos'],b['pos'])==1 and front(actor,b['pos']) for b in foes)
        return (None,[]) if friend and enemy else None
    for victim in foes:
        if c.distance(actor['pos'],victim['pos'])>card['range'] or not c.visible(catalog,board,actor['pos'],victim['pos']):continue
        if mid=='EN19-A' and front(victim,actor['pos']):continue
        if mid=='EN20-A':
            middle=set(ray(actor['pos'],victim['pos'])[:-1])
            if any(tuple(b['pos']) in middle for b in alive if b is not actor):continue
        if mid=='EN22-A':
            locked=line(actor['pos'],c.direction(actor['pos'],victim['pos']),card['range'])
            if tuple(victim['pos']) not in locked:continue
            if not targets(actor,{**card,'cells':[list(p) for p in locked]},alive,catalog,board):continue
            return victim,locked
        return victim,[tuple(victim['pos'])]
    return None


def targets(actor, action, alive, catalog, board):
    """Locked cells never track a dodging target; projectiles respect live blockers."""
    from mechanics import ray
    mid=action['move_id'];locked=[tuple(p) for p in action['cells']]
    if not locked:return []
    if mid in ('EN19-A','EN23-A','EN25-A'):
        return [b for b in alive if b['id']==action['target'] and b['side']!=actor['side']
                and tuple(b['pos']) in locked and c.distance(actor['pos'],b['pos'])==1
                and c.visible(catalog,board,actor['pos'],b['pos'])]
    path=locked if mid=='EN22-A' else ray(actor['pos'],locked[-1])
    by_pos={tuple(b['pos']):b for b in alive if b is not actor};victims=[]
    for pos in path:
        if pos not in board or c.distance(actor['pos'],pos)>action['range'] or not c.visible(catalog,board,actor['pos'],pos):break
        target=by_pos.get(pos)
        if not target:continue
        if target['side']==actor['side']:break
        if mid=='EN20-A' and pos!=locked[-1]:break
        victims.append(target)
        if len(victims)>=action['max_targets']:break
    return victims
