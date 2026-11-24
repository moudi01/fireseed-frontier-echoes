"""Owned plans, declared unlocks and deterministic team-compatible offers."""
from data import keyed_rng

RULES={
    'PL01':'开场首名护卫及一名邻友各12私盾', 'PL02':'开场无邻友者8私盾',
    'PL03':'每人首次侧后相邻近战普攻绕过代受', 'PL04':'敌强技结束后两拍内首次相邻近战普攻增伤25%，每敌一次',
    'PL05':'站定两拍后的下一次投射普攻增伤25%，攻击尝试后重计', 'PL06':'同技能第二次治疗间隔减1，最低C2，不加次数；每人一次',
    'PL07':'普攻起手花6私盾，正命中后造下拍可用的2拍标准印；每人2次', 'PL08':'真实自主移动后下拍起得4私盾／2拍；每人3次',
    'PL09':'普攻命中使未到释放拍的施法延后1拍；全队2次、同拍1次', 'PL10':'普攻预约一次已延后施法窗口，对应防御视为减8；每人2次',
    'PL11':'耗标准印后，下拍起下一直接攻击暴率25%／额外暴伤50%，期限3拍；每人2次',
    'PL12':'普通移动花4私盾，原路径最多2格并获后续两拍20%闪避；每人2次，不回产移动盾',
}


def unlocked(game):
    result={f'PL{i:02}' for i in range(1,7)}
    facts=set(game.s['unlocked_facts'])
    if 'ST-104' in facts or 'CH1_COMPLETE' in facts:result.update(('PL07','PL08','PL11','PL12'))
    if game.s.get('plan_spell_seen'):result.update(('PL09','PL10'))
    return result


def available_cards(member):
    """Use the same loadout and switches as the battle's automatic queue."""
    import battle_skills
    import commander
    import heroes
    import skill_books
    if member.get('skill_mode')=='off':return []
    core=commander.cards() if member['unit_id']=='CMD' else battle_skills.core_cards(member['unit_id'])
    cards=skill_books.cards(member,core)
    disabled=set(member.get('disabled_skills',[]))
    return [c for c in cards if c['move_id'] not in disabled
            and (member.get('hero_enabled',True) or c['move_id'] not in heroes.DATA and not c['move_id'].startswith('CMD-'))]


def capabilities(game):
    import skill_books
    import balance_v062 as balance
    import hero_power_v062 as hero
    party=[a for a in game.s['party'] if a['hp']>0 and a.get('erosion',0)<100 and a.get('injury_days',0)<=0]
    kinds={a['unit_id'] for a in party};owned=set(game.s['plans_owned'])
    loadouts=[(a,available_cards(a)) for a in party]
    cards=[c for _,moves in loadouts for c in moves];mids={c['move_id'] for c in cards}
    melee=any(skill_books.capabilities(a)['near'] for a in party)
    projectile=any(skill_books.capabilities(a)['projectile'] and a['unit_id'] not in ('M01','M04') for a in party)
    guard=bool(kinds&{'S01','M01','H01','M05'})
    walkers={a['instance_id'] for a in party if skill_books.capabilities(a)['walking']}
    walking=bool(walkers);ids={a['instance_id'] for a in party}
    # Track named producer shields per recipient, not a team-wide yes/no flag.
    # Same-name refreshes do not stack; independent payable sources may combine.
    # This is loadout feasibility, never a promise about a future hit/position.
    sources={iid:{} for iid in ids}
    def private(recipients,amount,effect):
        for iid in recipients:
            if amount>0:sources[iid][effect]=max(sources[iid].get(effect,0),amount)
    def cost(a):return a.get('cost',balance.unit_cost(a))
    if 'M01' in kinds:private(ids,6,'M01-P')
    if 'PL01' in owned and guard:private(ids,12,'PL01')
    if 'PL02' in owned:private(ids,8,'PL02')
    # Consecutive real moves can accumulate two four-point producer shields.
    if 'PL08' in owned:private(walkers,8,'MOVE-SHIELD')
    support_kinds={'heal','hero_group_heal','private_shield','hero_shield',
                   'hero_stance','hero_support','hero_group_shield'}
    for a,moves in loadouts:
        iid=a['instance_id'];active={c['move_id'] for c in moves};equipped=set(a.get('books_equipped',[]))
        enabled=a.get('hero_enabled',True)
        if 'BK11' in equipped:private({iid}&walkers,8,'MOVE-SHIELD')
        if 'SK-BK05' in active:private(ids,14,'SK-BK05')
        if 'M05-A' in active:
            amount=next(c['shield'] for c in moves if c['move_id']=='M05-A')
            private(ids-{iid},amount,'M05-A')
        if 'H01-A' in active:
            for recipient in party:private({recipient['instance_id']},7*cost(recipient),'H01-A')
        if 'H05-B' in active:private({iid},int(.5*a['stats']['hp']),'H05-B')
        for mid,fraction in (('H08-A',.5),('H08-B',.4)):
            if mid in active:
                # Both W1 actions occupy this caster. With 3-tick shields and
                # next-tick payment, their sub-threshold grants cannot be
                # stacked into a payable six-point window by this one caster.
                for recipient in party:private({recipient['instance_id']},int(fraction*recipient['stats']['hp']),'H08-SUPPORT')
        # H04/H06 no longer make private shields. H08 has no old 6-shield
        # movement passive. H03's new passive is native-heal-only and follows
        # the actual recipient's Cost, including self-healing.
        if a['unit_id']=='H03' and enabled and any(c['move_id'] in hero.DATA and c['move_id'].startswith('H03-')
                and c['kind'] in ('heal','hero_group_heal') for c in moves):
            for recipient in party:private({recipient['instance_id']},2*cost(recipient),'H03-P')
        if a['unit_id']=='M05' and enabled and len(ids)>1 and any(c['kind']=='private_shield' for c in moves):
            private({iid},balance.passive_value('M05-P'),'M05-P')
        if a['unit_id']=='M07' and enabled and active&{'M07-A','SK-BK04'}:
            private({iid},balance.passive_value('M07-P'),'M07-P')
        if 'M08-A' in active and enabled and a['stats'].get('magic_attack',0)>0:
            private({iid},balance.passive_value('M08-P'),'M08-P')
        private({iid},sum(p.get('amount',0) for p in game.s.get('preparations',{}).get(iid,[])
                if p['type']=='next_battle_private_shield'),'PREPARATION')
        if 'BK14' in equipped and any(c['kind'] in support_kinds and
                (c['move_id']!='M05-A' or len(ids)>1) for c in moves):
            private({iid},4,'BK14')
    four={iid for iid,pools in sources.items() if sum(pools.values())>=4}
    six={iid for iid,pools in sources.items() if sum(pools.values())>=6}
    # Book-paid marks need the shield on that book's wearer. A teammate's
    # self-only shield cannot be transferred to satisfy BK09's payment.
    # H09's contract vulnerability is not a standard mark and no longer grants
    # an old consumer shield. Only genuine producer cards/plans enter this chain.
    mark=bool(mids&{'SK-BK04','M07-A'}) or bool(six and 'PL07' in owned) or any(a['instance_id'] in six and any(c['move_id']=='SK-BK09' for c in moves) for a,moves in loadouts)
    for a,moves in loadouts:
        # Consumer-produced BK16 shield may fund movement, never paid marking.
        if 'BK16' in a.get('books_equipped',[]) and mark:four.update(ids)
    healing=any(c['kind'] in ('heal','hero_group_heal') and (c.get('cast_limit') is None or c.get('cast_limit',0)>=2) and c.get('cooldown',0)>2 for c in cards)
    delay=bool(mids&{'M04-A','M08-A','SK-BK08'}) or 'PL09' in owned
    spell=bool(game.s.get('plan_spell_seen'))
    if game.s.get('manifest'):
        spell=any(card.get('delayable_cast') for slot,options in game.current['growth']['encounters'].items() if slot not in game.current['cleared'] for e in options.values() for u in e.get('units',[]) for card in u.get('moves',[]))
    return {'PL01':guard,'PL02':bool(party),'PL03':melee,'PL04':melee,
            'PL05':projectile,'PL06':healing,'PL07':bool(six),'PL08':walking,
            'PL09':spell,'PL10':spell and delay,'PL11':mark,'PL12':bool(four&walkers)}


def key(game,event,option):return f"{game.s['expedition_no']}:{game.s['region']}:{event['event_id']}:{option['option_id']}"


def offer(game,event,option):
    saved=game.s.get('plan_offers',{}).get(key(game,event,option))
    if saved is not None:return [x for x in saved if x not in game.s['plans_owned']]
    flags=capabilities(game);pool=sorted(unlocked(game)-set(game.s['plans_owned']))
    ready=[p for p in pool if flags[p]]
    # Incomplete pairs can occupy only one slot; never displace every ready card.
    partial=[p for p in pool if not flags[p] and p in ('PL07','PL11','PL12')]
    rng=keyed_rng(game.s['seed'],key(game,event,option)+':plans')
    rng.shuffle(ready);rng.shuffle(partial)
    result=ready[:3]
    if result and partial:
        result=result[:2]+partial[:1]
    return result


def freeze(game):
    if game.s['site'] not in game.manifest_region['events']:return
    event,_,_=game.event_info()
    for option in event['options']:
        if option.get('reward_bundle_id')=='RB-PLAN':
            token=key(game,event,option)
            if token not in game.s['plan_offers']:
                choices=offer(game,event,option)
                # No payable offer yet: let a later legal revisit become viable.
                if choices:game.s['plan_offers'][token]=choices


def seen_battle(game,battle):
    if not battle.get('result'):return
    casts={(a['id'],card['move_id']) for a in battle['actors'] if a['side']=='enemy' for card in a['moves'] if card.get('delayable_cast')}
    if any(e['type']=='windup' and (e['actor'],e['move']) in casts for e in battle['events']):game.s['plan_spell_seen']=True


def label(game,plan):
    name=game.cat.plans[plan]['name']
    return plan+' '+name+'：'+RULES[plan]+('（当前队伍可用）' if capabilities(game)[plan] else '（暂缺组合一端，可保留）')


def configure(game,args):
    s=game.s
    if s['phase'] not in ('TOWN','EXPLORE'):raise ValueError('战斗中不能调整方案。')
    if not args or args==['list']:return '\n'.join(label(game,p) for p in sorted(s['plans_owned'])) or '尚未取得当趟方案。'
    if args==['undo']:
        if s.get('plan_undo') is None:raise ValueError('没有可撤销的战前方案调整。')
        chosen=s['plan_undo'];s['plan_undo']=None
    else:
        chosen=[] if args==['clear'] else args
        if len(chosen)!=len(set(chosen)) or len(chosen)>3 or not set(chosen)<=set(s['plans_owned']):raise ValueError('只能装备最多3项已拥有且不重复的方案。')
        s['plan_undo']=s['plans_equipped'][:]
    s['plans_equipped']=chosen[:];game.log('plans_equipped',plans=chosen)
    return '生效方案：'+', '.join(chosen)


def validate(game):
    s=game.s;owned=s['plans_owned'];equipped=s['plans_equipped']
    if len(owned)!=len(set(owned)) or not set(owned)<=set(game.cat.plans):raise ValueError('方案所有权记录无效。')
    if len(equipped)!=len(set(equipped)) or len(equipped)>3 or not set(equipped)<=set(owned):raise ValueError('生效方案必须属于本人且最多3项。')
    if s.get('plan_undo') is not None and (len(s['plan_undo'])>3 or len(s['plan_undo'])!=len(set(s['plan_undo'])) or not set(s['plan_undo'])<=set(owned)):raise ValueError('方案撤销记录无效。')
    if type(s.get('plan_spell_seen')) is not bool:raise ValueError('施法教学记录无效。')
    for values in s.get('plan_offers',{}).values():
        if len(values)>3 or len(values)!=len(set(values)) or not set(values)<=set(game.cat.plans):raise ValueError('方案候选快照无效。')
