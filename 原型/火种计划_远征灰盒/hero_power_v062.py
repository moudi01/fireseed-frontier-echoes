"""Cost-4 hero kits. Native actions have cooldowns, never battle charge caps.

The tick executor owns scheduling, damage, death receipts and stun eligibility.
This module owns hero intent, geometry, delivered effects and serializable state.
"""
from copy import deepcopy
import math
import combat as c

IDS={f'H{i:02}' for i in range(1,13)}
SELF_MOVES={'move','evade','short_dash','book_dash','side_step','charge_move','plan_move','interface_move','hero_path'}


def _card(mid,**fields):
    row=dict(move_id=mid,name=mid,kind='damage',windup=1,cooldown=4,cast_limit=None,
             first_eligible_tick=1,max_targets=1,range=1,medium='near',damage_type='physical',
             coefficient=1,interruptible=True,shape='locked_target')
    row.update(fields);row['delayable_cast']=row['medium']=='spell'
    return row


DATA={
 'H01-A':_card('H01-A',name='合壁',kind='hero_shield',windup=0,range=2,duration_ticks=3),
 'H01-B':_card('H01-B',name='截锋',range=2,cooldown=3,coefficient=1.8),
 'H02-A':_card('H02-A',name='破影箭',windup=0,range=5,cooldown=2,coefficient=1.5,medium='projectile',reveal_ticks=3),
 'H02-B':_card('H02-B',name='贯林箭',range=5,coefficient=1.8,medium='projectile',shape='hero_line',area=True,max_targets=None,penetration=1),
 'H03-A':_card('H03-A',name='回暖',kind='heal',windup=0,range=3,cooldown=2,medium='spell',heal_base=16,healing_power_coefficient=1.8),
 'H03-B':_card('H03-B',name='归队之光',kind='hero_group_heal',range=3,cooldown=6,medium='spell',radius=1,heal_base=10,healing_power_coefficient=1),
 'H04-A':_card('H04-A',name='荆矢',windup=0,range=4,cooldown=3,coefficient=1.5,medium='projectile',max_targets=2,area=True,shape='hero_multishot'),
 'H04-B':_card('H04-B',name='回哨',windup=0,range=4,coefficient=1.2,medium='projectile'),
 'H05-A':_card('H05-A',name='断棱',coefficient=3),
 'H05-B':_card('H05-B',name='百炼架势',kind='hero_stance',range=0,cooldown=6,duration_ticks=3),
 'H06-A':_card('H06-A',name='定星',range=4,coefficient=2,medium='spell',damage_type='magic',radius=1,area=True,max_targets=None,shape='hero_area'),
 'H06-B':_card('H06-B',name='坠星',range=4,cooldown=5,coefficient=2.8,medium='spell',damage_type='magic'),
 'H08-A':_card('H08-A',name='牵引接应',kind='hero_support',range=4,duration_ticks=4),
 'H08-B':_card('H08-B',name='搭手护持',kind='hero_group_shield',range=3,cooldown=6,duration_ticks=4),
 'H09-A':_card('H09-A',name='并签',range=4,coefficient=1.8,medium='spell',damage_type='magic',radius=1,area=True,max_targets=None,shape='hero_area'),
 'H09-B':_card('H09-B',name='断契击',range=4,coefficient=3,medium='spell',damage_type='magic'),
 'H10-A':_card('H10-A',name='震地落锤',coefficient=2.5,range=1,radius=1,area=True,max_targets=None,shape='hero_adjacent'),
 'H10-B':_card('H10-B',name='封口锤',coefficient=3.2,cooldown=5),
 'H11-A':_card('H11-A',name='遁影追命',range=0,global_target=True,coefficient=2,cooldown=5),
 'H11-B':_card('H11-B',name='飞刃闪身',range=0,global_target=True,coefficient=.8,cooldown=3,medium='projectile'),
 'H12-A':_card('H12-A',name='定炉法阵',kind='hero_setup',range=0,cooldown=2,medium='spell'),
 'H12-B':_card('H12-B',name='流星火雨',range=4,coefficient=1.6,medium='spell',damage_type='magic',radius=1,area=True,max_targets=None,shape='hero_area'),
 'PET-H04-A':_card('PET-H04-A',name='扑咬',coefficient=1.2,cooldown=3),
}

PASSIVES={
 'H01':('誓线','本人直接承伤降低30%；相邻站立友军降低15%，同类光环取高。'),
 'H02':('量线','本人至少3格的直接物伤提高50%。'),
 'H03':('余温','每次原生有效治疗或扶起，受益者得2×本人Cost私盾3拍；不产连锁收益。'),
 'H04':('熟路','真实自主移动后，下一次普攻或原生射击增伤50%，同组取高；一动作多目标共用。'),
 'H05':('量缝','本人直接物伤对命中前有盾敌提高100%，无盾提高30%。'),
 'H06':('压星','普攻与原生技能正命中使敌人随后2拍直接输出降低25%。'),
 'H07':('列阵号令','3格普通士兵物攻提高35%、减伤20%，不设整场响应总额。'),
 'H08':('稳桥','3格活友包含本人直接减伤25%，同类光环取高。'),
 'H09':('留契','普攻与原生技能附3拍25%契痕；A为40%，取高刷新，不是标准印。'),
 'H10':('横扫','普攻三格扇形，原目标1.4物伤、另外两格各1.0；一个动作每生命owner一击。'),
 'H11':('背袭','本人后方三向直接攻击独立×2；A亲手击杀后次拍直接额外A，可无限接续。'),
 'H12':('炉心增幅','法阵持续期间本人魔法直接伤害独立×1.5；移动或倒地使法阵消散，B不消耗法阵。'),
}
PERSONAS={
 'H11':dict(name='祁岚',title='逐隙刃客',background='曾穿过封闭货道送信的刃客，学着为同行者留出回路。',motivation='让自己抢先走出的每一步都有同伴接手。',fear='只盯残血，忘记背后的人。',relationships=['与薇拉核对回撤路，同陆衡约定退点。'],role='背袭与遁影连续收割',strengths=['背后三向翻倍；亲手A击杀可逐拍无限接续。'],weaknesses=['低双防，受控制与落格限制；友军击杀不续链。']),
 'H12':dict(name='殷砚',title='赤炉法师',background='从旧窑场带来固定控火法阵的法师，先说清危险，再集中释放。',motivation='让大范围火术为队伍打开空间。',fear='执着于法阵位置而错过转移。',relationships=['同赛琳交换测量记录，与弩手讨论攻击范围。'],role='常驻法阵与大范围火术',strengths=['法阵期间魔法直接伤害独立1.5倍；强化火雨统一覆盖19格。'],weaknesses=['身板脆弱，公开锁格不追人；移位消阵且可取消未到期法术。']),
}


def install(cat):
    import roster_content
    stats=lambda vals:dict(zip(('hp','physical_attack','magic_attack','healing_power','physical_defense','magic_defense'),vals))
    rows={'H11':((40,15,0,0,6,6),(5,2,0,0,1,0),'physical',1,2,('EF02','EF07','EF08')),
          'H12':((34,2,16,3,3,12),(4,0,3,1,0,1),'magic',3,3,('EF04','EF07','EF08'))}
    for uid,(base,growth,dtype,rng,interval,families) in rows.items():
        cat.rules['hero_templates'][uid]=dict(stats=stats(base),growth=stats(growth),attack_type=dtype,range=rng,interval=interval)
        for item in cat.gear.values():
            if item['family_id'] in families and uid not in item['allowed_unit_ids']:item['allowed_unit_ids'].append(uid)
    cat.rules['hero_templates']['H06']['stats']['magic_attack']=14
    cat.rules['hero_ids']=sorted(set(cat.rules.get('hero_ids',[]))|IDS)
    for uid in sorted(IDS):
        p=deepcopy(roster_content.PERSONAS.get(uid,PERSONAS.get(uid,{})))
        name,description=PASSIVES[uid];p['passive']=dict(id=uid+'-P',name=name,description=description)
        p['actives']=[dict(id=row['move_id'],name=row['name'],description=describe_card(row)) for row in cards(uid)]
        if uid in PERSONAS:p.update(deepcopy(PERSONAS[uid]));p['passive']=dict(id=uid+'-P',name=name,description=description);p['actives']=[dict(id=row['move_id'],name=row['name'],description=describe_card(row)) for row in cards(uid)]
        p['role']= {'H06':'群体压制与单点硬控','H09':'契痕易伤与直接爆发','H10':'顺劈与近场群锤'}.get(uid,p.get('role','英雄'))
        p['role']={'H01':'持续整队防护与近场截锋','H02':'远距压制、破隐与贯线','H03':'高频治疗与可循环原人群救',
                   'H04':'实际移动、双目标射击与真实伴兽接应','H05':'正面破防强攻与强自保','H06':'群体压制与单点硬控',
                   'H07':'普通士兵专职统帅','H08':'范围减伤、大盾与便利接应','H09':'单一契痕易伤与爆发','H10':'顺劈与近场群锤',
                   'H11':'全场遁影、背袭与逐拍无限收割','H12':'常驻法阵与19格范围火术'}[uid]
        p['strengths']=[description,'原生主动无整场次数帽，只受冷却、动作与合法性约束。']
        p['weaknesses']=[{'H01':'保护有范围，不能回溯取消已合法到时动作。','H02':'近身失去远距被动，实墙仍阻线。',
            'H03':'需真实治疗资格与复起落格，本人倒地不能自起。','H04':'不能穿人，牵引犬不赠扑咬。','H05':'近击仍需接近，护盾与减伤不治疗。',
            'H06':'锁格不追人，控制免疫由真实敌卡声明。','H07':'只指挥普通士兵，响应遵守本人射程与LOS。','H08':'盾不回血，移动失败不代表穿人或免控。',
            'H09':'契痕下一拍起效，不是标准印，不生产消费者盾。','H10':'近场范围有限，Boss同owner只命中一次。',
            'H11':'低双防，控制／无落格／未亲手A击杀都会停链。','H12':'身板脆弱，真实移动使法阵消散并可取消未到期火术。'}[uid]]
        roster_content.PERSONAS[uid]=p


def describe_card(row):
    mid=row['move_id'];extra=DESCRIPTIONS.get(mid,'')
    return f"W{row['windup']}／C{row['cooldown']}，无限次；"+extra


DESCRIPTIONS={
 'H01-A':'2格活友各7×Cost私盾3拍。','H01-B':'2格1.8物伤，来得及时真正打断，无施法也伤害。',
 'H02-A':'5格1.5物伤、显露3拍；可射公开位置的隐匿虚影，仍验LOS。','H02-B':'5格锁线各1.8物伤，穿一薄不穿墙。',
 'H03-A':'3格最低生命比例活友恢复floor(16+1.8H)。','H03-B':'3格中心半径1全部活友恢复floor((10+H)×Cost/4)，至多扶起一原人至35%生命。',
 'H04-A':'4格最多2敌各1.5物伤，下一拍受阻。','H04-B':'本人安全后退最多2格并4格射击1.2物伤；护兽仅在犬处于本拍或下拍锁区，或半血内贴敌时安全拉1格，否则只射击。犬须4格内可见且未起手、未受控，并占犬本拍行动。',
 'H05-A':'相邻3物伤，忽略本击一半物防。','H05-B':'本人50%最大生命私盾与30%减伤，持续3拍。',
 'H06-A':'4格中心半径1各2魔伤、随后2拍受阻。','H06-B':'4格2.8魔伤、真正打断并使下一拍眩晕。',
 'H08-A':'4格活友50%最大生命盾4拍；可安全调动时再移1格，不预约待命。','H08-B':'3格全部活友各40%最大生命私盾4拍。',
 'H09-A':'4格中心半径1各1.8魔伤、40%契痕3拍。','H09-B':'4格3魔伤，拍初已有契痕则4魔伤，不消耗。',
 'H10-A':'本人六邻格各2.5物伤、随后2拍受阻。','H10-B':'相邻3.2物伤，真打断与下一拍眩晕，无突进。',
 'H11-A':'遁影1拍，出影选全场最低比例合法敌，闪其邻格2物伤；击杀次拍直接额外A。','H11-B':'最低比例射线目标0.8物伤，伤害批后闪到刀实际落点邻格。',
 'H12-A':'脚下建立持续法阵，真实位移或倒地使其消散。','H12-B':'未布阵：中心4格内、半径1各1.6倍魔法伤害、W1；已布阵：中心5格内、半径2各2.5倍魔法伤害、W2；C4，施放不消耗法阵。',
 'CMD-A':'4格原目标标记4拍，发布时3格普通士兵集火并对原目标直伤提高50%。',
 'CMD-B':'3格所有普通士兵次拍起各一次1.5倍额外攻击，无整场响应帽，每兵每拍至多一份。',
 'PET-H04-A':'真实犬相邻1.2物伤，C3反复扑咬，不是画外免费攻击。',
}


def cards(kind):
    if kind=='H07':
        import commander
        return commander.cards()
    return [deepcopy(row) for mid,row in DATA.items() if mid.rsplit('-',1)[0]==kind]


def enabled(a,kind=None):return a.get('hero_enabled',True) and (kind is None or a.get('kind')==kind)
def active(row,tick):return bool(row and row.get('starts',1)<=tick<=row.get('expires',tick))
def cost(a):return a.get('cost',4 if a.get('kind','').startswith('H') or a.get('kind')=='CMD' else 2 if a.get('kind','').startswith('M') else 1)
def neighbors(pos):return [(pos[0]+dq,pos[1]+dr) for dq,dr in c.DIRS]
def living(a):return a.get('hp',0)>0 and not a.get('mechanism') and not a.get('boss_part')
def walkable(cat,board,pos):return tuple(pos) in board and cat.terrain[board[tuple(pos)]]['walkable']


def initialize(a):
    a.update(hero_uses={},hero_exposed=None,hero_route=False,hero_facing=None,hero_revived=False,downed_tick=None,
             hero_shadow=False,hero_chain_due=None,hero_setup=False,hero_setup_origin=None,hero_stance=None,
             hero_stun=None,hero_suppression=None,hero_contract=None,hero_contract_pending=None,hero_block_due=0)
    a.setdefault('hero_options',{});a.setdefault('hero_enabled',True)


def add_shield(b,a,v,amount,effect,action,tick,log,active=True,duration=2,starts=None):
    import skill_books
    starts=tick if starts is None else starts;amount=max(0,math.floor(amount))
    if not amount:return 0
    old=[p for p in v['timed_shields'] if p.get('effect')==effect and p['expires']>=tick]
    before=max((p['amount'] for p in old),default=0)
    v['timed_shields'][:]=[p for p in v['timed_shields'] if p.get('effect')!=effect]
    row={'effect':effect,'source':a['id'],'amount':max(before,amount),'created':tick,
         'starts':min([starts]+[p.get('starts',1) for p in old]),'expires':max([starts+duration-1]+[p['expires'] for p in old])}
    v['timed_shields'].append(row);added=max(0,amount-before)
    log('hero_shield',actor=a['id'],target=v['id'],move=effect,action_id=action['id'],added=added,amount=row['amount'],starts=row['starts'],expires=row['expires'])
    if active:skill_books.support_success(b,a,action,added,tick,log,target=v,kind='private_shield')
    return added


def shields(b,a,tick=None):
    tick=b.get('tick',0) if tick is None else tick
    if a.get('boss_part'):a=next(v for v in b['actors'] if v['id']==a['boss_owner'])
    return a.get('shield',0)+sum(p['amount'] for p in a.get('timed_shields',[]) if p.get('starts',1)<=tick<=p['expires'])+sum(p['amount'] for p in b.get('shared_shields',[]) if a['id'] in p['members'] and p.get('starts',1)<=tick<=p['expires'])


def targetable(observer,target,tick,origin=None):
    return observer['side']==target['side'] or not ((enabled(target,'H11') and target.get('hero_shadow')) or target.get('mimic_shadow',False))


def started(b,a,action,tick,log):
    if action['move_id']=='H11-A' and not action.get('extra_chain'):
        a['hero_shadow']=True;log('hero_shadow',actor=a['id'],action_id=action['id'],release_tick=action['due'])
    if action['move_id']=='H12-A':action['hero_anchor']=a['pos'][:]
    if action['move_id']=='H12-B':
        action['due']=tick+action.get('hero_windup',action['windup']);action['windup']=action.get('hero_windup',action['windup'])


def start_tick(b,tick,log):
    for a in b['actors']:
        pending_contract=a.get('hero_contract_pending')
        if pending_contract and pending_contract['starts']<=tick:
            a['hero_contract']=pending_contract;a['hero_contract_pending']=None
        if a.get('hp',0)<=0:
            a['hero_setup']=False;a['hero_shadow']=False;a['hero_chain_due']=None
        if a.get('hero_chain_due') is not None and a['hero_chain_due']<tick:
            a['hero_chain_due']=None;a['hero_shadow']=False


def chain_action(b,a,alive,cat,board,tick,log):
    if not enabled(a,'H11') or a.get('hero_chain_due')!=tick:return None
    a['hero_chain_due']=None
    if a['hp']<=0 or active(a.get('hero_stun'),tick) or a.get('skill_mode')=='off' or 'H11-A' in a.get('disabled_skills',[]):
        a['hero_shadow']=False;return None
    act=deepcopy(DATA['H11-A']);act.update(extra_chain=True,windup=0,due=tick,target=a['id'],cells=[],origin=a['pos'][:],facing=a['facing'])
    return act


def _owner(v,actors):
    return next((x for x in actors if x['id']==v.get('boss_owner')),v) if v.get('boss_part') else v


def _ratio(v,actors=None):
    v=_owner(v,actors) if actors is not None else v
    return (v['hp']/max(1,v['stats']['hp']),v['hp'],v['id'])


def _unsafe(prior,actors,side,tick):
    return {tuple(p) for other in actors if other['side']!=side
            for pending in [prior.get(other['id'])] if pending and pending.get('kind')=='damage'
            and tick<=pending['due']<=tick+1 for p in pending.get('cells',[])}


def _legal(a,v,cat,board,tick,rng,penetration=0,reveal=False):
    import veil
    return (v['hp']>0 and c.distance(a['pos'],v['pos'])<=rng and c.visible(cat,board,a['pos'],v['pos'],penetration)
            and (reveal or veil.targetable(a,v,tick)) and (reveal or targetable(a,v,tick)))


def _circle(center,radius,board):return sorted(pos for pos in board if c.distance(center,pos)<=radius)


def _movement_disabled(a,tick):
    return active(a.get('hero_stun'),tick) or tick<=max(a.get('root_until',0),a.get('blocked_until',0),a.get('move_pause_until',0))


def _safe_paths(v,cat,board,occupied,blocked,unsafe,length=1):
    from spatial_moves import crossed
    result=[];todo=[(tuple(v['pos']),[])]
    while todo:
        here,path=todo.pop(0)
        if path and here not in unsafe:result.append(path)
        if len(path)>=length or path and board[here]=='SHALLOW_WATER':continue
        for dest in neighbors(here):
            if dest==tuple(v['pos']) or dest in path or not walkable(cat,board,dest) or dest in occupied or crossed(here,dest,blocked):continue
            todo.append((dest,path+[dest]))
    return result


def _landing(a,v,actors,cat,board,unsafe=()):
    occupied={tuple(x['pos']) for x in actors if x['hp']>0 and x['id']!=a['id']}
    legal=[pos for pos in neighbors(v['pos']) if walkable(cat,board,pos) and pos not in occupied]
    def key(pos):
        direction=c.direction(v['pos'],pos);offset=(direction-v['facing'])%6
        return (0 if offset==3 else 1 if offset in (2,4) else 2,pos in unsafe,pos)
    return min(legal,key=key) if legal else None


def _blink_choice(b,a,cat,board,tick):
    import veil
    rows=[]
    for v in b['actors']:
        if v['hp']<=0 or v['side']==a['side'] or v.get('boss_broken'):continue
        if not targetable(a,v,tick) or not veil.targetable(a,v,tick):continue
        # Visibility is shared by actual standing allies, not unexplored fog.
        if not any(x['hp']>0 and x['side']==a['side'] and c.visible(cat,board,x['pos'],v['pos']) for x in b['actors']):continue
        pos=_landing(a,v,b['actors'],cat,board)
        if pos is not None:rows.append((_ratio(v,b['actors']),v['id'],v,pos))
    if not rows:return None
    _,_,v,pos=min(rows,key=lambda row:row[:2]);return v,pos


def _area_choice(a,foes,cat,board,tick,rng,radius):
    options=[]
    for center in board:
        if c.distance(a['pos'],center)>rng or not c.visible(cat,board,a['pos'],center):continue
        victims=[v for v in foes if v['hp']>0 and c.distance(center,v['pos'])<=radius and c.visible(cat,board,a['pos'],v['pos'])]
        if victims:options.append((-len({_owner(v,foes)['id'] for v in victims}),center,min(victims,key=lambda v:_ratio(v,foes))))
    if not options:return None
    _,center,v=min(options,key=lambda row:(row[0],row[1]));return v,_circle(center,radius,board),{'hero_center':list(center)}


def _h12_attack_reaches(a,foes,cat,board,tick):
    """Forecast output from this emplacement, not an unavailable cannon.

    Basic attacks still work when native abilities are switched off. A usable
    cannon retains its emplacement while cooling down; cooldowns are not lost
    capabilities. Current book actives are support/movement, not damage, so
    their target ranges must not hold a turret outside its basic attack range.
    """
    if any(_legal(a,v,cat,board,tick,a['range']) for v in foes):return True
    if not enabled(a,'H12') or a.get('skill_mode')=='off' or 'H12-B' in a.get('disabled_skills',[]):return False
    cannon=next((card for card in a.get('moves',[]) if card['move_id']=='H12-B' and card['kind']=='damage'),None)
    return bool(cannon and c.has_uses(a,cannon) and _area_choice(a,foes,cat,board,tick,5,2))


def choose(b,a,card,foes,alive,prior,cat,board,occupied,blocked,tick):
    mid=card['move_id'];rng=card['range'];unsafe=_unsafe(prior,alive,a['side'],tick)
    enemies=sorted([v for v in foes if _legal(a,v,cat,board,tick,rng,card.get('penetration',0),mid=='H02-A')],key=lambda v:(c.distance(a['pos'],v['pos']),v['id']))
    friends=[v for v in alive if living(v) and v['side']==a['side'] and c.distance(a['pos'],v['pos'])<=rng and c.visible(cat,board,a['pos'],v['pos'])]
    if mid in ('H01-A','H08-B'):
        fraction=None if mid=='H01-A' else .4
        candidates=[v for v in friends if not any(p.get('effect')==mid and p['expires']>=tick and p['amount']>=(7*cost(v) if fraction is None else math.floor(v['stats']['hp']*fraction)) for p in v['timed_shields'])]
        if candidates:return a,[],{}
    elif mid=='H03-A':
        injured=[v for v in friends if v['hp']<v['stats']['hp']]
        if injured:return min(injured,key=_ratio),[],{}
    elif mid=='H03-B':
        reserved={x['pending'].get('hero_revive_target') for x in alive if x.get('pending') and x['pending']['move_id']==mid}
        fallen=[v for v in b['actors'] if v is not a and not v.get('mechanism') and not v.get('boss_part') and v['side']==a['side'] and v['hp']<=0 and v.get('downed_tick') is not None and v['id'] not in reserved]
        options=[]
        for center in board:
            if c.distance(a['pos'],center)>rng or not c.visible(cat,board,a['pos'],center):continue
            injured=[v for v in alive if living(v) and v['side']==a['side'] and c.distance(center,v['pos'])<=1 and c.visible(cat,board,a['pos'],v['pos']) and v['hp']<v['stats']['hp']]
            dead=[v for v in fallen if c.distance(center,v['pos'])<=1 and c.visible(cat,board,a['pos'],v['pos'])]
            corpse=None;dest=None
            for v in sorted(dead,key=lambda v:(c.distance(a['pos'],v['pos']),v['id'])):
                dest=next((p for p in [tuple(v['pos'])]+sorted(neighbors(v['pos'])) if walkable(cat,board,p) and p not in occupied),None)
                if dest is not None:corpse=v;break
            score=sum(min(v['stats']['hp']-v['hp'],(10+c.stat(a,'healing_power',tick))*cost(v)/4) for v in injured)
            if corpse:score+=corpse['stats']['hp']*.35
            if score>0:options.append((-score,center,corpse,dest,injured))
        if options:
            _,center,v,dest,injured=min(options,key=lambda row:(row[0],row[1]))
            extra={'hero_center':list(center)}
            if v:extra.update(hero_revive_target=v['id'],hero_corpse_origin=v['pos'][:],hero_revive_position=list(dest))
            return v or injured[0],[center],extra
    elif mid=='H04-B':
        v=a
        pet_mode=a.get('hero_options',{}).get('recall','self')=='pet'
        if pet_mode:
            v=next((v for v in friends if v['kind']=='PET-H04' and not v.get('pending')),None)
        # A healthy safe companion keeps its own action. Only an announced
        # impact or a wounded adjacent melee threat warrants a rescue pull.
        rescue=bool(v and (not pet_mode or tuple(v['pos']) in unsafe or
                    v['hp']*2<=v['stats']['hp'] and any(_legal(v,f,cat,board,tick,1) for f in foes)))
        paths=[]
        if rescue and not _movement_disabled(v,tick):
            # Companion movement executes only the first cell, so evaluate that
            # actual cell rather than the endpoint of a hypothetical long path.
            paths=_safe_paths(v,cat,board,occupied,blocked,unsafe,1 if pet_mode else 2)
        if paths:
            def retreat_key(path):
                closest=min((c.distance(path[-1],f['pos']) for f in foes if f['hp']>0),default=0)
                return (-closest,-len(path),path)
            path=min(paths,key=retreat_key)
        else:path=[]
        shoot=sorted([f for f in foes if _legal({**a,'pos':list(path[-1]) if path and v is a else a['pos']},f,cat,board,tick,4)],key=lambda f:(c.distance(a['pos'],f['pos']),f['id']))
        if path or shoot:
            return shoot[0] if shoot else a,[],{'hero_move_target':v['id'] if v else a['id'],'hero_move_origin':v['pos'][:] if v else a['pos'][:],
                'hero_path':[list(p) for p in path],'hero_shot_target':shoot[0]['id'] if shoot else None}
    elif mid=='H05-B':
        if not active(a.get('hero_stance'),tick):return a,[],{}
    elif mid=='H08-A':
        eligible=sorted(friends,key=lambda v:(tuple(v['pos']) not in unsafe,*_ratio(v),v['id']))
        for v in eligible:
            if any(p.get('effect')==mid and p['expires']>=tick and p['amount']>=math.floor(v['stats']['hp']*.5) for p in v['timed_shields']):continue
            paths=[] if v.get('pending') or _movement_disabled(v,tick) else _safe_paths(v,cat,board,occupied,blocked,unsafe)
            return v,[],{'hero_move_target':v['id'],'hero_move_origin':v['pos'][:],'hero_path':[list(p) for p in min(paths)] if paths else []}
    elif mid in ('H06-A','H09-A'):
        return _area_choice(a,foes,cat,board,tick,rng,1)
    elif mid=='H10-A':
        cells=neighbors(a['pos']);victims=[v for v in enemies if tuple(v['pos']) in cells]
        if victims:return victims[0],cells,{}
    elif mid=='H11-A':
        if _movement_disabled(a,tick):return None
        row=_blink_choice(b,a,cat,board,tick)
        if row:return row[0],[],{}
    elif mid=='H11-B':
        candidates=[v for v in foes if v['hp']>0 and _legal(a,v,cat,board,tick,c.distance(a['pos'],v['pos']))]
        if candidates:
            v=min(candidates,key=lambda v:_ratio(v,b['actors']));return v,[v['pos'][:]],{}
    elif mid=='H12-A':
        if not a.get('hero_setup'):
            # The demon borrows this active without becoming H12 or owning
            # native H12-B. Its copy adapter keeps the original cannon geometry.
            reaches=(_h12_attack_reaches(a,foes,cat,board,tick) if a.get('kind')=='H12'
                     else _area_choice(a,foes,cat,board,tick,5,2))
            if reaches:return a,[],{'hero_anchor':a['pos'][:]}
    elif mid=='H12-B':
        setup=bool(a.get('hero_setup'));rng=5 if setup else 4;radius=2 if setup else 1
        chosen=_area_choice(a,foes,cat,board,tick,rng,radius)
        if chosen:
            v,cells,extra=chosen;extra.update(range=rng,radius=radius,coefficient=2.5 if setup else 1.6,hero_windup=2 if setup else 1,
                hero_entrenched=setup,hero_anchor=a['pos'][:])
            return v,cells,extra
    elif mid=='H02-B':
        options=[]
        for facing in range(6):
            dq,dr=c.DIRS[facing];cells=[(a['pos'][0]+dq*i,a['pos'][1]+dr*i) for i in range(1,6)]
            victims=[v for v in foes if tuple(v['pos']) in cells and _legal(a,v,cat,board,tick,5,1)]
            if victims:options.append((-len(victims),facing,min(victims,key=lambda v:(cells.index(tuple(v['pos'])),v['id'])),cells))
        if options:
            _,facing,v,cells=min(options,key=lambda row:row[:2]);return v,cells,{'facing':facing}
    elif mid=='H04-A':
        if enemies:
            selected=enemies[:2];return selected[0],[v['pos'][:] for v in selected],{'hero_targets':[v['id'] for v in selected]}
    elif enemies:
        if mid in ('H01-B','H06-B','H10-B'):
            def priority(v):
                pending=prior.get(v['id']);catch=bool(pending and pending['due']>tick+card['windup'] and pending.get('interruptible'))
                return (not catch,pending['due'] if catch else 999,c.distance(a['pos'],v['pos']),v['id'])
            v=min(enemies,key=priority)
            return v,[v['pos'][:]],{'target_cast':v['pending']['id'] if v.get('pending') else None}
        v=min(enemies,key=lambda v:(not active(_owner(v,b['actors']).get('hero_contract'),tick),*_ratio(v,b['actors']))) if mid=='H09-B' else enemies[0]
        return v,[v['pos'][:]],{}


def movement(actions,b,alive,cat,board,tick,log):
    from spatial_moves import active_edges,crossed
    blocked=active_edges(b,tick);occupied={tuple(v['pos']) for v in alive if v['hp']>0};moves=[]
    for a,act in actions:
        if act['move_id'] not in ('H04-B','H08-A'):continue
        v=next((v for v in alive if v['id']==act.get('hero_move_target')),None);path=act.get('hero_path',[])
        if not v or not path or v['hp']<=0 or v['pos']!=act.get('hero_move_origin') or _movement_disabled(v,tick):continue
        if v is not a and (v.get('pending') or c.distance(a['pos'],v['pos'])>act['range'] or not c.visible(cat,board,a['pos'],v['pos'])):continue
        old=tuple(v['pos']);valid=[]
        for raw in path:
            pos=tuple(raw)
            if c.distance(old,pos)!=1 or not walkable(cat,board,pos) or pos in occupied or crossed(old,pos,blocked):break
            valid.append(pos);old=pos
            if board[pos]=='SHALLOW_WATER':break
        if valid:
            if v is a:moves.append((v,[list(p) for p in valid],'hero_path'))
            else:moves.append((v,list(valid[0]),'hero_pull'))
    return moves


def _relocate(b,a,pos,action,cat,board,tick,log,reason='hero_flash'):
    pos=tuple(pos)
    if _movement_disabled(a,tick) or not walkable(cat,board,pos) or any(x['hp']>0 and x['id']!=a['id'] and tuple(x['pos'])==pos for x in b['actors']):return False
    if pos==tuple(a['pos']):return True
    import gear_affixes as gear
    import battle_plans
    import roster_skills
    old=a['pos'][:];a['pos']=list(pos);a['stationary']=0;a['last_moved_tick']=tick
    c.enter_shallow(a,board[pos],tick,log);moved(a,reason,tick)
    gear.moved(a,tick,log);roster_skills.moved(a,reason);battle_plans.moved(b,a,reason,tick,log)
    import book_combat
    book_combat.moved(b,a,reason,tick,log)
    log(reason,actor=a['id'],origin=old,position=a['pos'][:],action_id=action['id'],move=action['move_id'])
    return True


def release(b,a,action,alive,cat,board,tick,log):
    mid=action['move_id']
    if mid not in DATA:return
    if mid in ('H01-A','H08-B'):
        for v in alive:
            if not living(v) or v['side']!=a['side'] or c.distance(a['pos'],v['pos'])>action['range'] or not c.visible(cat,board,a['pos'],v['pos']):continue
            amount=7*cost(v) if mid=='H01-A' else max(1,math.floor(v['stats']['hp']*.4))
            add_shield(b,a,v,amount,mid,action,tick,log,duration=3 if mid=='H01-A' else action.get('duration_ticks',3))
    elif mid=='H05-B':
        add_shield(b,a,a,max(1,math.floor(a['stats']['hp']*.5)),mid,action,tick,log,duration=3)
        a['hero_stance']={'starts':tick,'expires':tick+2,'source':a['id'],'amount':.3}
        log('hero_stance',actor=a['id'],action_id=action['id'],reduction=.3,expires=tick+2)
    elif mid=='H08-A':
        v=next((v for v in alive if v['id']==action['target'] and living(v) and v['side']==a['side']),None)
        if v and c.distance(a['pos'],v['pos'])<=4 and c.visible(cat,board,a['pos'],v['pos']):
            add_shield(b,a,v,max(1,math.floor(v['stats']['hp']*.5)),mid,action,tick,log,duration=action.get('duration_ticks',3))
        else:log('skill_miss',actor=a['id'],move=mid,action_id=action['id'])
    elif mid=='H09-B':
        v=next((v for v in alive if v['id']==action['target']),None)
        action['coefficient']=4 if v and active(_owner(v,alive).get('hero_contract'),tick) else 3
    elif mid=='H11-A':
        a['hero_shadow']=False
        chosen=None if _movement_disabled(a,tick) else _blink_choice(b,a,cat,board,tick)
        if not chosen:action['hero_target_failed']=True;log('hero_shadow_failed',actor=a['id'],action_id=action['id'],reason='no_legal_target_or_landing');return
        v,pos=chosen
        if not _relocate(b,a,pos,action,cat,board,tick,log):action['hero_target_failed']=True;return
        action.update(target=v['id'],hero_owner_target=_owner(v,b['actors'])['id'],cells=[v['pos'][:]],origin=a['pos'][:],hero_hit_origin=a['pos'][:],projectile_origin=a['pos'][:])
        a['facing']=c.direction(a['pos'],v['pos'])
        log('hero_shadow_strike',actor=a['id'],target=v['id'],action_id=action['id'],extra_chain=bool(action.get('extra_chain')),position=a['pos'][:])
    elif mid=='H12-A':
        if a['pos']!=action.get('hero_anchor',action['origin']):
            action['hero_target_failed']=True;log('hero_setup_failed',actor=a['id'],action_id=action['id'],reason='anchor_moved');return
        a['hero_setup']=True;a['hero_setup_origin']=a['pos'][:]
        log('hero_setup',actor=a['id'],action_id=action['id'],position=a['pos'][:])
    elif mid=='H12-B' and a['pos']!=action.get('hero_anchor',action['origin']):
        action['hero_target_failed']=True;log('hero_cannon_cancel',actor=a['id'],action_id=action['id'],reason='anchor_moved')


def _unique_surfaces(victims,actors,coefficients=None):
    result={}
    for v in victims:
        owner=_owner(v,actors)['id'];score=(coefficients or {}).get(v['id'],1)
        old=result.get(owner)
        if old is None or score>(coefficients or {}).get(old['id'],1) or score==(coefficients or {}).get(old['id'],1) and v['id']<old['id']:result[owner]=v
    return list(result.values())


def targets(a,action,alive,cat,board,tick):
    from mechanics import ray
    mid=action['move_id'];foes=[v for v in alive if v['side']!=a['side'] and v['hp']>0]
    if action.get('hero_target_failed'):return []
    action['hero_hit_origin']=a['pos'][:];action['projectile_origin']=a['pos'][:]
    if mid=='H11-B':
        end=action['cells'][-1] if action.get('cells') else None
        if end is None:return []
        victim=None;impact=None;low=0
        for pos in ray(a['pos'],end):
            if pos not in board:break
            impact=pos;terrain=board[pos]
            if terrain=='HIGH_OBSTACLE':break
            if terrain=='LOW_OBSTACLE':
                low+=1
                if low>int(board.get(tuple(a['pos']))=='HIGH_GROUND' or board.get(tuple(end))=='HIGH_GROUND'):break
            victim=next((v for v in sorted(foes,key=lambda v:v['id']) if tuple(v['pos'])==pos),None)
            if victim:break
        action['hero_knife_impact']=list(impact) if impact is not None else None
        if victim:action['hero_knife_owner']=_owner(victim,alive)['id'];action['hero_knife_surface']=victim['id']
        return [victim] if victim else []
    if mid=='H02-B':
        path=list(map(tuple,action['cells']));victims=[v for v in foes if tuple(v['pos']) in path and _legal(a,v,cat,board,tick,5,1,True)]
        return _unique_surfaces(sorted(victims,key=lambda v:(path.index(tuple(v['pos'])),v['id'])),alive)
    if mid=='H04-A':
        victims=[v for iid in action.get('hero_targets',[]) for v in foes if v['id']==iid and _legal(a,v,cat,board,tick,4,reveal=True)]
        return _unique_surfaces(victims,alive)
    if mid=='H04-B':
        choices=[v for v in foes if _legal(a,v,cat,board,tick,4,reveal=True)]
        if not choices:return []
        v=min(choices,key=lambda v:(v['id']!=action.get('hero_shot_target'),c.distance(a['pos'],v['pos']),v['id']))
        action['target']=v['id'];action['hero_shot_target']=v['id'];return [v]
    if mid in ('H06-A','H09-A','H12-B','H10-A'):
        center=action.get('hero_center',action.get('origin',a['pos']))
        if mid!='H10-A' and (c.distance(a['pos'],center)>action['range'] or not c.visible(cat,board,a['pos'],center)):return []
        cells=set(map(tuple,action['cells']))
        victims=[v for v in foes if tuple(v['pos']) in cells and c.visible(cat,board,a['pos'],v['pos']) and (mid!='H10-A' or c.distance(a['pos'],v['pos'])<=1)]
        return _unique_surfaces(sorted(victims,key=lambda v:v['id']),alive)
    if mid=='H11-A':
        return [v for v in foes if v['id']==action['target'] and c.distance(a['pos'],v['pos'])==1 and c.visible(cat,board,a['pos'],v['pos'])][:1]
    if mid in DATA:
        return [v for v in foes if v['id']==action['target'] and _legal(a,v,cat,board,tick,action['range'],reveal=True)][:1]
    return []


def basic_targets(a,action,alive,cat,board,tick):
    if not enabled(a,'H10') or action['move_id']!='BASIC':return None
    primary=next((v for v in alive if v['id']==action['target'] and v['hp']>0),None)
    if primary is None:return []
    facing=c.direction(a['pos'],primary['pos'])
    cells={(a['pos'][0]+c.DIRS[(facing+d)%6][0],a['pos'][1]+c.DIRS[(facing+d)%6][1]) for d in (-1,0,1)}
    victims=[v for v in alive if v['side']!=a['side'] and v['hp']>0 and tuple(v['pos']) in cells and c.visible(cat,board,a['pos'],v['pos'])]
    coefficients={v['id']:1.4 if v['id']==primary['id'] else 1 for v in victims}
    action['hero_coefficients']=coefficients;action['area']=True;action['max_targets']=None
    return _unique_surfaces(sorted(victims,key=lambda v:(v['id']!=primary['id'],v['id'])),alive,coefficients)


def heals(b,a,action,alive,cat,board,tick):
    mid=action['move_id']
    if mid=='H03-A':
        v=next((v for v in alive if v['id']==action['target'] and living(v) and v['side']==a['side']),None)
        if v and c.distance(a['pos'],v['pos'])<=3 and c.visible(cat,board,a['pos'],v['pos']):return [(v,math.floor(16+1.8*c.stat(a,'healing_power',tick)))]
    elif mid=='H03-B':
        center=action.get('hero_center',action['cells'][0] if action['cells'] else a['pos'])
        if c.distance(a['pos'],center)>3 or not c.visible(cat,board,a['pos'],center):return []
        return [(v,math.floor((10+c.stat(a,'healing_power',tick))*cost(v)/4)) for v in alive
                if living(v) and v['side']==a['side'] and c.distance(center,v['pos'])<=1 and c.visible(cat,board,a['pos'],v['pos'])]
    return []


def healed(b,a,v,action,effective,tick,log):
    if effective>0 and enabled(a,'H03') and action['move_id'] in ('H03-A','H03-B') and not action.get('derived'):
        add_shield(b,a,v,2*cost(v),'H03-P',action,tick,log,False,duration=3,starts=tick+1)


def moved(a,reason=None,tick=None):
    if enabled(a,'H04') and reason in SELF_MOVES:a['hero_route']=True
    if a.get('kind')=='H12':
        a['hero_setup']=False;a['hero_setup_origin']=None
        pending=a.get('pending')
        if pending and pending['move_id'] in ('H12-A','H12-B') and (tick is None or pending['due']>tick):
            a['pending']=None;a['hero_cannon_cancelled']=pending['id']


def attack_attempt(b,a,action,tick,log):
    if not enabled(a,'H04') or action.get('derived') or action.get('kind')!='damage' or action['move_id'] not in ('BASIC','H04-A','H04-B'):return
    if action['move_id']=='H04-B' and action.get('hero_shot_target') is None:return
    if 'hero_route_bonus' not in action:
        action['hero_route_bonus']=.5 if a.get('hero_route') else 0
        if action['hero_route_bonus']:
            a['hero_route']=False;log('hero_route_spent',actor=a['id'],action_id=action['id'],move=action['move_id'],increase=.5)


def attack_bonus(a,action):
    return action.get('hero_route_bonus',0) if enabled(a,'H04') else 0


def attack_increase(b,a,v,action,tick,origin=None):
    if action.get('derived') or action.get('kind')!='damage':return 0
    import commander
    result=commander.damage_bonus(b,a,v,action,tick)
    if not enabled(a):return result
    origin=origin if origin is not None else action.get('hero_hit_origin',action.get('origin',a['pos']))
    if enabled(a,'H02') and action['damage_type']=='physical' and c.distance(origin,v['pos'])>=3:result=max(result,.5)
    if enabled(a,'H05') and action['damage_type']=='physical':
        had_shield=action.get('sb_had_shield_before',{}).get(v['id'],shields(b,v,tick)>0)
        result=max(result,1 if had_shield else .3)
    return max(result,attack_bonus(a,action))


def damage_multiplier(b,a,v,action,tick,origin=None):
    if not enabled(a) or action.get('derived') or action.get('kind')!='damage':return 1
    from mechanics import front
    factor=1;origin=origin if origin is not None else action.get('hero_hit_origin',action.get('origin',a['pos']))
    if enabled(a,'H11') and not front(v,origin):factor*=2
    if enabled(a,'H12') and a.get('hero_setup') and action['damage_type']=='magic':factor*=1.5
    return factor


def damage_reduction(b,v,alive,tick):
    if v.get('hp',0)<=0:return 0
    own=.3 if enabled(v,'H01') else 0
    if active(v.get('hero_stance'),tick):own+=v['hero_stance'].get('amount',.3)
    aura=0
    for a in alive:
        if a['hp']<=0 or a['side']!=v['side'] or not enabled(a):continue
        if a['kind']=='H01' and a is not v and c.distance(a['pos'],v['pos'])==1:aura=max(aura,.15)
        if a['kind'] in ('H07','CMD') and v['kind'] in ('S01','S02','S03') and c.distance(a['pos'],v['pos'])<=3:aura=max(aura,.2)
        if a['kind']=='H08' and c.distance(a['pos'],v['pos'])<=3:aura=max(aura,.25)
    return own+aura


def should_advance(a,foes,cat,board,tick):
    return bool(a.get('kind')=='H12' and a.get('hero_setup') and not _h12_attack_reaches(a,foes,cat,board,tick))
def outgoing_factor(a,tick):return .75 if active(a.get('hero_suppression'),tick) else 1
def incoming_factor(v,tick):return 1+v['hero_contract']['amount'] if active(v.get('hero_contract'),tick) else 1
def defense(a,v,action,tick,log):
    if not enabled(a,'H05') or action['move_id']!='H05-A':return 0
    return max(0,c.stat(v,'physical_defense',tick)+v.get('boss_rule',{}).get('physical_defense_offset',0))*.5


def interrupt(b,v,cast_id,tick,log,source):
    pending=v.get('pending')
    if not pending or pending['id']!=cast_id or pending['due']<=tick or not pending.get('interruptible',False):return False
    v['pending']=None;v['next_attack']=max(v.get('next_attack',1),tick+1)
    # Native cooldown starts at accepted start; interrupt does not start it again.
    log('hero_interrupt',actor=source,target=v['id'],cast_id=cast_id,move=pending['move_id'])
    return True


def _debuff(v,key,amount,duration,a,action,tick):
    old=v.get(key);old=old if old and old['expires']>=tick else None
    future=v.get(key+'_pending') if key=='hero_contract' else None
    if key=='hero_contract' and old and active(old,tick) and (amount>old.get('amount',0) or future):
        rows=[row for row in (old,future) if row and row['expires']>=tick]
        row={'starts':tick+1,'expires':max([tick+duration]+[row['expires'] for row in rows]),'source':a['id'],
             'action_id':action['id'],'amount':max([amount]+[row.get('amount',0) for row in rows])}
        v[key+'_pending']=row;return row
    v[key]={'starts':min(tick+1,old.get('starts',tick+1)) if old else tick+1,'expires':max(tick+duration,old['expires']) if old else tick+duration,
            'source':a['id'],'action_id':action['id'],'amount':max(amount,old.get('amount',0)) if old else amount}
    return v[key]


def hit(b,a,v,action,amount,tick,log,spend_shields=None):
    if amount<=0 or action.get('derived'):return
    mid=action['move_id']
    if mid=='H02-A':
        v['hero_exposed']={'starts':tick+1,'expires':tick+3,'source':a['id']}
        log('hero_reveal',actor=a['id'],target=v['id'],action_id=action['id'],starts=tick+1,expires=tick+3)
    if mid in ('H01-B','H06-B','H10-B'):interrupt(b,v,action.get('target_cast'),tick,log,a['id'])
    if mid in ('H06-B','H10-B') and not v.get('immune_stun',False):
        _debuff(v,'hero_stun',1,1,a,action,tick)
        log('hero_stun',actor=a['id'],target=v['id'],action_id=action['id'],starts=tick+1,expires=tick+1)
    if mid in ('H04-A','H06-A','H10-A') and not v.get('immune_movement_block',False):
        duration=1 if mid=='H04-A' else 2;v['hero_block_due']=max(v.get('hero_block_due',0),tick+duration)
        log('hero_movement_block',actor=a['id'],target=v['id'],action_id=action['id'],until=tick+duration)
    if enabled(a,'H06') and (mid=='BASIC' or mid.startswith('H06-')):
        _debuff(v,'hero_suppression',.25,2,a,action,tick)
        log('hero_suppression',actor=a['id'],target=v['id'],action_id=action['id'],starts=tick+1,expires=tick+2,amount=.25)
    if enabled(a,'H09') and (mid=='BASIC' or mid.startswith('H09-')):
        row=_debuff(v,'hero_contract',.4 if mid=='H09-A' else .25,3,a,action,tick)
        log('hero_contract',actor=a['id'],target=v['id'],action_id=action['id'],starts=tick+1,expires=row['expires'],amount=row['amount'])
    if mid=='H11-B' and v['id']!=action.get('hero_knife_owner'):action['hero_knife_impact']=v['pos'][:]


def projectile_deflected(b,a,v,action,tick,log):
    if action['move_id']=='H11-B':
        row=v.get('deflection');action['hero_knife_impact']=list(row['destination']) if row else None


def on_kill(b,a,v,action,tick,log):
    if not enabled(a,'H11') or action['move_id']!='H11-A' or action.get('derived') or a['hp']<=0 or action.get('hero_kill_awarded'):return
    action['hero_kill_awarded']=True;a['hero_chain_due']=tick+1;a['hero_shadow']=True
    log('hero_chain_queued',actor=a['id'],target=v['id'],action_id=action['id'],due=tick+1)


def end_tick(actions,b,cat,board,tick,log):
    import book_combat
    for a in b['actors']:
        until=a.pop('hero_block_due',0)
        if a['hp']>0 and until and not book_combat.movement_control_immune(a,tick):
            a['blocked_until']=max(a.get('blocked_until',0),until)
        if a['hp']<=0:a['hero_setup']=False;a['hero_shadow']=False;a['hero_chain_due']=None
    for a,act in actions:
        mid=act['move_id']
        if mid=='H11-B' and a['hp']>0 and act.get('hero_knife_impact') is not None:
            impact=act['hero_knife_impact'];occupied={tuple(v['pos']) for v in b['actors'] if v['hp']>0 and v['id']!=a['id']}
            options=[p for p in neighbors(impact) if walkable(cat,board,p) and p not in occupied]
            target=next((v for v in b['actors'] if v['id']==act.get('hero_knife_surface',act['target'])),None)
            def key(pos):
                offset=(c.direction(target['pos'],pos)-target['facing'])%6 if target else 0
                return (0 if offset==3 else 1 if offset in (2,4) else 2,pos)
            if options:_relocate(b,a,min(options,key=key),act,cat,board,tick,log)
        if mid!='H03-B' or not act.get('hero_revive_target'):continue
        v=next((v for v in b['actors'] if v['id']==act['hero_revive_target']),None);pos=tuple(act['hero_revive_position']);center=act['hero_center']
        reason=None
        if not v or v is a or v['hp']>0 or v.get('downed_tick') is None:reason='target_unavailable'
        elif v['pos']!=act['hero_corpse_origin']:reason='corpse_moved'
        elif c.distance(a['pos'],center)>3 or c.distance(center,v['pos'])>1 or not c.visible(cat,board,a['pos'],v['pos']):reason='out_of_range_or_sight'
        elif not walkable(cat,board,pos) or any(x['hp']>0 and tuple(x['pos'])==pos for x in b['actors']):reason='landing_blocked'
        if reason:log('hero_revive_failed',actor=a['id'],target=act['hero_revive_target'],action_id=act['id'],reason=reason);continue
        v.update(hp=max(1,math.floor(v['stats']['hp']*.35)),pos=list(pos),active_from=tick+1,pending=None,shield=0,timed_shields=[],
            hero_revived=True,hero_shadow=False,hero_chain_due=None,hero_setup=False,hero_setup_origin=None,hero_route=False,hero_stance=None,
            hero_stun=None,hero_suppression=None,hero_contract=None,hero_contract_pending=None,hero_exposed=None,root_until=0,blocked_until=0,move_pause_until=0,
            command_token=None,plan_crit=None,plan_dodge=None,book_dodge=None,gear_dodge=None,concealment=None,conceal_view=None,deflection=None,
            trigger_delay=None,deferred_start=None,petal_exposure=None,heat_charge=None,heat_exposure=None,standard_marks={},stationary=0)
        v['next_attack']=max(v.get('next_attack',1),tick+1)
        add_shield(b,a,v,2*cost(v),'H03-P',act,tick,log,False,duration=3,starts=tick+1)
        log('hero_revive',actor=a['id'],target=v['id'],action_id=act['id'],hp=v['hp'],position=v['pos'][:],active_from=tick+1)
