"""Read-only, actionable briefings from the encounter that will actually fight."""
from copy import deepcopy
import depth_growth

VERSION = 'ENEMY-INTEL-0.68'
STATS = ('hp','physical_attack','magic_attack','healing_power','physical_defense','magic_defense')
SHAPES = {
    'stage_locked_person':'起手附着本人；无弹道直接命中，标记后换格或遮挡仍追踪',
    'stage_locked_circle':'起手最远目标原格及周围1格；预警不追踪',
    'front_two_cells':'前方两格直线','front_three_cells':'前方三格直线',
    'one_cell':'一个锁定格','locked_cell':'一个锁定格','locked_axis':'锁定直线',
    'locked_adjacent_target':'相邻目标的原格','locked_rear_target':'侧后相邻目标原格',
    'last_real_basic_attack_cell':'自身真实普攻曾命中的格','last_two_real_basic_cells':'最近两次真实普攻命中格',
    'historic_front_axis':'已公开的历史轴线','two_public_anchor_cells':'两处预先公开的锚点',
    'two_lowest_hp_ratio_cells':'生命比例较低者的原格','locked_remains':'已锁定的遗骸格',
    'locked_bones':'已锁定的骨堆','private_shield':'本人私盾',
    'front_adjacent_fan_three':'前方相邻三格扇面',
    'last_two_real_basic_attack_cells':'最近两次真实普攻命中格',
    'locked_side_lane':'起手锁定的侧向通道','public_side_adjacent_two':'公开的侧向相邻两格',
    'public_three_cell_line':'公开的三格直线','three_locked_cells':'起手锁定的三格',
    'two_adjacent_cells':'两处相邻格','two_public_adjacent_cells':'公开的两处相邻格',
    'boss_threat_circle':'首领起手位置周围半径3的公开锁区',
    'peril_locked_circle':'起手锁原格半径1内圈；残留人类才引爆公开半径3外圈',
    'peril_conditional_circle':'起手锁原格半径1内圈；残留人类才引爆公开半径3外圈',
}
TARGETS = {'nearest_then_stable_id':'最近合法目标',
    'lowest_hp_ratio_then_stable_id_lock_original_cells':'生命比例最低者，锁起手格',
    'self':'自身','self_and_lowest_hp_adjacent_ally':'自身及相邻最低生命比例友军',
    'lowest_hp_ratio_actionable_allies_in_range_then_stable_id':'范围内生命比例较低的存活友军',
    'own_committed_basic_hit_history':'自身实际普攻命中历史',
    'nearest_actionable_human_positions_then_stable_id_lock_at_start':'最近可行动人类，锁起手格',
    'nearest_reachable_empty_flank_cell':'最近可抵达的侧翼空格',
    'self_and_nearest_adjacent_ally':'自身及最近的相邻友军'}
TARGETS['locked_boss_origin_then_distance_then_stable_id']='锁定首领起手位置，按距离与ID取目标'
TARGETS['farthest_actionable_human_then_stable_id_lock_at_start']='射程内最远可见人类，同距按ID；锁起手原格'
TARGETS['farthest_actionable_human_then_stable_id_lock_person_at_start']='射程内最远可见站立人类，同距按ID；锁本人，不改选'


def _skill(card):
    import battle_enrage
    card=battle_enrage.unlimited_sustain([deepcopy(card)])[0]
    value={key:deepcopy(card[key]) for key in (
        'move_id','name','kind','damage_type','coefficient','range','windup','cooldown',
        'cast_limit','max_targets','first_eligible_tick','locks_cells','interruptible',
        'delayable_cast','shield','duration_ticks','shared_pool','heal_base',
        'healing_power_coefficient','revive_percent','pressure_radius','outer_radius','locked_anchor_cells','locks_target') if key in card}
    value['shape']=SHAPES.get(card.get('shape'),card.get('shape','按技能目标规则'))
    value['target']=TARGETS.get(card.get('target_rule'),card.get('target_rule','按合法目标与原技能规则'))
    details=[];kind=card.get('kind')
    value['range_display']='随被复制技能' if kind=='boss_mimic' else str(card.get('range',0))+'格'
    if card.get('mechanic_summary'):details.append(card['mechanic_summary'])
    if kind=='damage':details.append(('魔法' if card.get('damage_type')=='magic' else '物理')+f"攻击×{card.get('coefficient',1):g}")
    if card.get('max_targets'):details.append(f"至多{card['max_targets']}个目标")
    if card.get('locks_cells'):details.append('起手锁格，释放前可设法离开该范围')
    if card.get('locks_target'):details.append('起手需射程／视线；标记附着后离开射程或遮挡仍追踪原人，倒地则落空；可打断、延后，盾与减伤有效')
    if card.get('pressure_radius'):details.append(f"公开预警向外扩{card['pressure_radius']}格")
    if card.get('delayable_cast'):
        details.append('可被合法延后施法；1拍起手通常需提前压制' if card.get('windup',0)<=1 else '可用合法施法延后争取时间')
    if card.get('shared_pool'):details.append('多个目标共用盾池')
    if card.get('shield') is not None:details.append(f"盾量{card['shield']}，持续{card.get('duration_ticks','按卡')}拍")
    if kind=='heal':details.append(f"治疗{card.get('heal_base',0)}＋治疗强度×{card.get('healing_power_coefficient',0):g}，不复起")
    if kind=='revive':details.append(f"复起既有遗骸至{card.get('revive_percent',50)}%生命，仍需合法空格")
    if kind=='summon':details.append('调用预留援军，处理召唤源可以阻止后续兵力')
    value['details']='；'.join(details)
    return value


def _unit(cat, unit):
    template=cat.enemy_templates.get(unit['enemy_id'],{})
    skills=[_skill(card) for card in unit.get('moves',[])]
    basic=deepcopy(unit.get('basic_attack',template.get('basic_attack',{})))
    row=dict(id=unit.get('instance_id',unit['enemy_id']+'（预留类型）'),enemy_id=unit['enemy_id'],
        name=unit.get('name') or template.get('name',unit['enemy_id']),
        position=deepcopy(unit.get('position')),facing=unit.get('facing'),
        stats={key:unit['stats'].get(key,0) for key in STATS},basic=basic,skills=skills,
        briefing=unit.get('briefing') or template.get('briefing',''),
        weak_point=deepcopy(unit.get('weak_point') or template.get('weak_point',{})),
        phases=deepcopy(unit.get('phases',[])),boss_parts=deepcopy(unit.get('boss_parts',[])),
        innate_life_steal=deepcopy(unit.get('innate_life_steal')),
        immune_stun=bool(unit.get('immune_stun')),immune_movement_block=bool(unit.get('immune_movement_block')))
    hints=[];kinds={card.get('kind') for card in unit.get('moves',[])}
    if 'revive' in kinds:hints.append('优先压制复起者；占住遗骸格可限制复起落位。')
    if 'summon' in kinds:hints.append('先看召唤源与预留援军，考虑处理骨堆或集火召唤者。')
    if 'heal' in kinds:hints.append('留意治疗者位置；可考虑绕过前排施压，短蓄力需要提前准备反制。')
    if 'shield' in kinds:hints.append('考虑集火或削盾；共享盾会被多个受护者共同消耗。' if any(c.get('shared_pool') for c in unit.get('moves',[])) else '留意护盾持续时间，选择爆发或等盾到期。')
    if any(c.get('locks_target') for c in unit.get('moves',[])):
        hints.append('追印起手前可避开射程／视线；标记附着后换格、离开射程或遮挡仍追踪本人。可打断、合法延后，或用护盾、减伤及合法护卫代受承接。')
    if any('line' in str(c.get('shape','')) or 'axis' in str(c.get('shape','')) or str(c.get('shape','')).startswith('front_') for c in unit.get('moves',[])):
        hints.append('避免多人排成同一直线；可用分散站位与避险姿态应对锁线。')
    elif any(c.get('max_targets',1)>1 or c.get('pressure_radius') for c in unit.get('moves',[])):
        hints.append('留出分散和撤离空间，避免多人同时落入扩展锁区。')
    if row['weak_point'].get('requires_side_or_rear'):
        point=row['weak_point'];condition=point.get('active_condition','')
        when='自身定根期间' if 'rooted' in condition else '对应主动释放后的下一拍' if 'one_tick_after' in condition else '弱点激活时'
        reductions=[]
        for key,label in (('physical_defense_modifier','物防'),('magic_defense_modifier','魔防')):
            if point.get(key,0)<0:reductions.append(label+str(point[key]))
        hints.append(f"{point.get('name','弱点')}：{when}从侧后利用"+('、'.join(reductions) if reductions else '其公开弱点')+'。')
    if row['innate_life_steal']:hints.append('吸血依赖实际生命伤害；护盾承伤与集中击倒可限制回复。')
    if row['immune_stun']:hints.append('该单位免疫眩晕，调整为走位、集火或其余合法反制。')
    row['counterplay']=list(dict.fromkeys(hints))
    return row


def _encounters(game, requested=None):
    s=game.s;phase=s['phase'];f=s.get('finale',{})
    if phase=='TOWN' and f.get('preparation') and not f.get('run'):
        import finale
        return [('DEMON',finale.BOARD,finale.lock_demon(game),'终战准备，进入前可调整整备')]
    if phase=='FINAL_CHOICE' and f.get('run'):
        import finale
        return [('DEMON',finale.BOARD,deepcopy(f['run']['encounter']),'已锁定的魔王敌阵')]
    if phase=='FINAL_REGROUP':
        import finale
        return [('ADMIN',finale.BOARD,game.cat.encounter_for_board('BATTLE-ADMIN',finale.BOARD),
                 '连续终战：仅可重布原随队幸存者，生命、冷却与次数保持')]
    if phase!='EXPLORE' or not s.get('manifest') or not s.get('region'):return []
    bindings=game.manifest_region.get('encounters',{})
    visible=set(game.current.get('revealed_battles',[]))|{s.get('site')}
    if requested:
        if requested not in bindings or requested not in visible:
            raise ValueError('该敌阵尚未公开；需实际接近或使用已有探路服务。')
        slots=[requested]
    elif s.get('site') in bindings and s['site'] not in game.current['cleared']:
        slots=[s['site']]
    else:slots=sorted(slot for slot in visible if slot in bindings)
    return [(slot,bindings[slot]['board_id'],depth_growth.current_encounter(game,slot),
             '已公开的本区冻结敌阵；开战前可直接调整') for slot in slots if slot not in game.current['cleared']]


def public(game, slot=None):
    import battle_enrage
    encounters=[]
    for site,board_id,encounter,notice in _encounters(game,slot):
        board=game.cat.boards[board_id]
        encounters.append(dict(site=site,encounter_id=encounter['encounter_id'],
            name=encounter.get('name',encounter['encounter_id']),board_id=board_id,board_name=board['name'],
            threat=encounter.get('effective_threat'),notice=notice+'；'+battle_enrage.rule_text(),
            units=[_unit(game.cat,u) for u in encounter['units']],
            mechanisms=[_unit(game.cat,u) for u in encounter.get('mechanisms',[])],
            reserves=[_unit(game.cat,u) for u in encounter.get('spawn_options',[])],
            board_parts=deepcopy(encounter.get('board_parts',[])),
            stage_backline_lock=deepcopy(encounter.get('stage_backline_lock')),
            deployment_cells=deepcopy(board['player_deploy_cells'])))
    return dict(version=VERSION,encounters=encounters,
        can_adjust=game.s['phase'] in ('TOWN','EXPLORE'),
        adjustments='部署/朝向/姿态；随行者已学书槽、技能顺序与开关；已拥有的3项方案；实际携带装备与战外物品。学书、采购、远程仓库换装仍需城镇。')


def describe(game, slot=None):
    info=public(game,slot)
    if not info['encounters']:return '暂无已公开待战敌阵；实际接近或探路后可用intel查看。'
    lines=['战前敌情（读取真实冻结面板，不推进时间或刷新敌阵）']
    for encounter in info['encounters']:
        lines.append(f"{encounter['site']} {encounter['name']}／{encounter['board_name']}：{encounter['notice']}")
        for kind,rows in (('敌人',encounter['units']),('场景机制',encounter['mechanisms']),('召唤预留',encounter['reserves'])):
            for u in rows:
                s=u['stats'];basic=u['basic']
                lines.append(f"{kind} {u['id']} {u['name']} 格{u['position']} {u['facing']}｜生命{s['hp']} 物/魔攻{s['physical_attack']}/{s['magic_attack']} 治疗{s['healing_power']} 物/魔防{s['physical_defense']}/{s['magic_defense']}")
                lines.append(f"  普攻：{'魔法' if basic.get('damage_type')=='magic' else '物理'}，射程{basic.get('range','—')}格，间隔{basic.get('attack_interval','—')}拍")
                for move in u['skills']:
                    limit='无限次' if move.get('cast_limit') is None else f"每场{move['cast_limit']}次"
                    lines.append(f"  {move.get('name',move['move_id'])}：起手{move.get('windup',0)}拍／冷却{move.get('cooldown',0)}拍／射程{move['range_display']}／{limit}；目标：{move['target']}；{move['shape']}；{move['details']}")
                if u['briefing']:lines.append('  能力说明：'+u['briefing'])
                lines.extend('  应对：'+hint for hint in u['counterplay'])
        if encounter['board_parts']:lines.append('首领部位与本体共享生命；同次范围攻击按同一生命主体去重。')
    if info['can_adjust']:lines.append('可调整：'+info['adjustments'])
    if game.s['phase']=='EXPLORE' and game.s.get('site') in game.manifest_region.get('encounters',{}):
        lines.append('fight开战；retreat退离接敌。阅读情报和战前配置不会触发战斗。')
    return '\n'.join(lines)
