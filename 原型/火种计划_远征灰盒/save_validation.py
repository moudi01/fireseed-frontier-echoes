"""Read-only minimum semantics shared by save loading and committing.

Content/source validators still own quests, equipment, moves and receipts.  This
module only rejects impossible scalar/container states; it never repairs a save,
requires a living party, caps shields at HP, or discards retained battle objects.
"""
import math


PHASES = frozenset(('TOWN', 'EXPLORE', 'BATTLE', 'RETURNED', 'FAILED',
                    'ABORTED', 'FIN_C', 'FINISHED', 'FINAL_CHOICE',
                    'FINAL_REGROUP', 'RECOVERY_STOP', 'MISSING_SEARCH'))
ROSTERS = ('party', 'home_roster', 'captives', 'escorted', 'memorial')
STANCES = frozenset(('advance', 'hold', 'flank', 'evade'))
RESULTS = (None, 'VICTORY', 'DEFEAT', 'RETREAT')


def _check(ok, path, rule):
    if not ok:
        raise ValueError(f'存档公共状态无效：{path} {rule}。')


def _mapping(value, path):
    _check(isinstance(value, dict), path, '须为对象')
    return value


def _list(value, path):
    _check(isinstance(value, list), path, '须为列表')
    return value


def _text(value, path):
    _check(isinstance(value, str) and bool(value.strip()), path, '须为非空字符串')


def _integer(value, path, minimum=0, maximum=None):
    _check(type(value) is int and value >= minimum
           and (maximum is None or value <= maximum), path,
           f'须为{minimum}以上真整数' if maximum is None else f'须为{minimum}至{maximum}的真整数')


def _number(value, path, minimum=0, positive=False):
    # bool is an int subclass; it is never a saved amount, HP or maximum HP.
    _check(type(value) in (int, float)
           and (type(value) is int or math.isfinite(value))
           and (value > minimum if positive else value >= minimum), path,
           '须为正有限数值' if positive else f'须为不小于{minimum}的有限数值')


def _finite_values_with_paths(root):
    """NaN/Infinity are not valid JSON state, including in optional receipts."""
    pending = [(root, 'state')]
    seen = set()
    while pending:
        value, path = pending.pop()
        if type(value) is float:
            _check(math.isfinite(value), path, '不能含NaN或无穷数')
        elif isinstance(value, (dict, list, tuple)):
            if id(value) in seen:
                continue
            seen.add(id(value))
            entries = value.items() if isinstance(value, dict) else enumerate(value)
            pending.extend((child, f'{path}.{key}') for key, child in entries)


def _finite_values(root):
    """Scan the complete graph; construct diagnostic paths only on failure."""
    pending = [root]
    seen = set()
    while pending:
        value = pending.pop()
        kind = type(value)
        if kind is float:
            if not math.isfinite(value):
                return _finite_values_with_paths(root)
        elif kind is dict or kind is list or kind is tuple:
            identity = id(value)
            if identity in seen:
                continue
            seen.add(identity)
            pending.extend(value.values() if kind is dict else value)
        elif isinstance(value, (dict, list, tuple)):
            # Preserve the old items/iteration behaviour of custom containers.
            return _finite_values_with_paths(root)


def _quantities(value, path, required=()):
    rows = _mapping(value, path)
    _check(set(required) <= rows.keys(), path, '缺少基础余额字段')
    for name, amount in rows.items():
        _text(name, path+'.key')
        _integer(amount, path+'.'+name)


def _health(row, path):
    stats = _mapping(row.get('stats'), path+'.stats')
    _number(stats.get('hp'), path+'.stats.hp', positive=True)
    for name, value in stats.items():
        _number(value, path+'.stats.'+str(name))
    hp = row.get('hp')
    _number(hp, path+'.hp')
    _check(hp <= stats['hp'], path+'.hp', '不能超过最大生命')


def _position(value, path):
    _check(isinstance(value, list) and len(value) == 2, path, '须为两个整数组成的坐标')
    for coordinate in value:
        _check(type(coordinate) is int, path, '坐标须为真整数')


def _member(row, path, roster):
    _mapping(row, path)
    _text(row.get('instance_id'), path+'.instance_id')
    _text(row.get('unit_id'), path+'.unit_id')
    _health(row, path)
    for name in ('xp', 'injury_days'):
        _integer(row.get(name), path+'.'+name)
    for name in ('level', 'cost', 'range', 'interval'):
        _integer(row.get(name), path+'.'+name, 1)
    _integer(row.get('erosion'), path+'.erosion', 0, 100)
    _integer(row.get('facing'), path+'.facing', 0, 5)
    _check(type(row.get('deployed')) is bool, path+'.deployed', '须为布尔值')
    _check(isinstance(row.get('stance'), str) and row['stance'] in STANCES,
           path+'.stance', '姿态不合法')
    _position(row.get('position'), path+'.position')
    if roster in ('captives', 'memorial'):
        capture = _mapping(row.get('capture'), path+'.capture')
        legal = ('LOST',) if roster == 'memorial' else ('CAPTURED', 'MISSING')
        _check(capture.get('status') in legal, path+'.capture.status', '与名册位置不符')


def _battle(battle, path):
    _mapping(battle, path)
    _integer(battle.get('tick'), path+'.tick')
    import battle_enrage
    battle_enrage.validate(battle)
    _check(battle.get('result') in RESULTS, path+'.result', '战果不合法')
    actors = _list(battle.get('actors'), path+'.actors')
    ids = set()
    for index, actor in enumerate(actors):
        here = f'{path}.actors[{index}]'
        _mapping(actor, here)
        _text(actor.get('id'), here+'.id')
        _check(actor['id'] not in ids, here+'.id', '战斗身份重复')
        ids.add(actor['id'])
        _text(actor.get('kind'), here+'.kind')
        _check(actor.get('side') in ('player', 'enemy'), here+'.side', '阵营不合法')
        _health(actor, here)
        _number(actor.get('shield'), here+'.shield')
        _position(actor.get('pos'), here+'.pos')
        pending = actor.get('pending')
        if pending is not None:
            _mapping(pending, here+'.pending')
            _integer(pending.get('due'), here+'.pending.due')
        for index2, shield in enumerate(_list(actor.get('timed_shields', []), here+'.timed_shields')):
            at = f'{here}.timed_shields[{index2}]'
            _mapping(shield, at)
            _number(shield.get('amount'), at+'.amount')
    for index, shield in enumerate(_list(battle.get('shared_shields', []), path+'.shared_shields')):
        here = f'{path}.shared_shields[{index}]'
        _mapping(shield, here)
        _number(shield.get('amount'), here+'.amount')


def validate(game):
    """Raise ValueError on an impossible public state without changing it."""
    state = _mapping(game.s, 'state')
    _finite_values(state)
    _check(isinstance(state.get('phase'), str) and state['phase'] in PHASES,
           'phase', '阶段不合法')
    for name in ('id', 'version', 'route', 'team_id', 'mission'):
        _text(state.get(name), name)
    _check(type(state.get('seed')) is int, 'seed', '须为真整数')
    for name in ('day', 'sequence', 'medical', 'used_prep_slots', 'escort_reserved_cost'):
        _integer(state.get(name), name)
    _integer(state.get('expedition_no'), 'expedition_no', 1)
    _check(type(state.get('debug_tainted')) is bool, 'debug_tainted', '须为布尔值')
    if 'developer_drill_only' in state:
        _check(type(state['developer_drill_only']) is bool, 'developer_drill_only', '须为布尔值')
    _quantities(state.get('bank'), 'bank', ('copper', 'crystal', 'supply'))
    for name in ('warehouse', 'pending', 'materials'):
        _quantities(state.get(name), name)
    budget = _mapping(state.get('budget'), 'budget')
    for name in ('battle', 'expedition'):
        _integer(budget.get(name), 'budget.'+name, 1)
    for name in ('pouch', 'gear_bag', 'plans_owned', 'plans_equipped', 'visited_regions',
                 'completed_regions', 'battle_reports', 'journal', 'completed_history'):
        _list(state.get(name), name)
    for name in ('regions', 'preparations', 'debits'):
        _mapping(state.get(name), name)
    ids = set()
    for roster in ROSTERS:
        for index, row in enumerate(_list(state.get(roster), roster)):
            path = f'{roster}[{index}]'
            _member(row, path, roster)
            _check(row['instance_id'] not in ids, path+'.instance_id', '人类／伴兽名册身份重复')
            ids.add(row['instance_id'])
    validate_enrollment(game)
    battle = state.get('battle')
    _check(state['phase'] != 'BATTLE' or battle is not None, 'battle', '战斗阶段缺少战斗对象')
    if battle is not None:
        _battle(battle, 'battle')
    import battle_enrage
    for report in state.get('battle_reports', []):
        battle_enrage.validate(report)
    for expedition in state.get('completed_history', []):
        for report in expedition.get('battle_reports', []):
            battle_enrage.validate(report)
    # Developer drills keep copied participants, never substitute the real roster.
    drill = state.get('drill')
    if isinstance(drill, dict) and isinstance(drill.get('active'), dict):
        active = drill['active']
        if active.get('battle') is not None:
            _battle(active['battle'], 'drill.active.battle')


def enroll(game, member, kind, ref):
    """Write only at the legal acquisition transaction, never during load."""
    register = _mapping(game.s.get('enrollment_register'), 'enrollment_register')
    iid = member['instance_id']
    _check(iid not in register, 'enrollment_register.'+iid, '加入身份已登记')
    register[iid] = dict(unit_id=member['unit_id'], source_kind=kind, source_ref=ref)


def require_new_fixture(game):
    s=game.s
    _check(not s.get('campaign') and s['phase']=='TOWN' and s['day']==0
           and s['expedition_no']==1 and s['recruit_sequence']==0
           and not any(s.get(k) for k in ('home_roster','captives','escorted','memorial',
                                          'completed_history','battle_reports','manifest','battle'))
           and len(s['journal'])==1 and s['journal'][0]['type']=='fixture_created',
           'fixture', '仅允许合法新建构造期替换，不能替换活动周目')
    validate_enrollment(game)


def initialize_enrollment(game, hero_fixture=False, commander_fixture=False):
    """Called only by new or a guarded, synchronous fixture constructor."""
    s=game.s
    _check('enrollment_register' not in s or hero_fixture or commander_fixture,
           'enrollment_register', '不得重建已有周目的加入历史')
    s['enrollment_register']={}
    if s.get('campaign'):
        _check(not any(s.get(k) for k in ROSTERS), 'enrollment_register', '未委任须为空')
        return
    prefix='HERO:' if hero_fixture else 'CMD:' if commander_fixture else 'CAT:'
    for i,m in enumerate(s['party'],1):
        enroll(game,m,'FIXTURE_INITIAL',prefix+s['team_id']+':'+str(i))


def _validate_enrollment(game):
    """Personnel-only validation, also used by the independent lab format."""
    from data import keyed_rng
    s=game.s;cat=game.cat
    register=_mapping(s.get('enrollment_register'),'enrollment_register')
    members={};locations={}
    for roster in ROSTERS:
        for m in _list(s.get(roster),roster):
            iid=m.get('instance_id');_text(iid,roster+'.instance_id')
            _check(iid not in members,iid,'名册身份重复')
            members[iid]=m;locations[iid]=roster
    _check(set(members)==set(register),'enrollment_register', '五名册与加入登记缺项或多项；临时救援窗口不能保存或判结局')
    expected={}
    def expect(iid,uid,kind,ref):
        _check(iid not in expected,iid,'来源重复')
        expected[iid]=dict(unit_id=uid,source_kind=kind,source_ref=ref)
    c=s.get('campaign')
    if c:
        grant=c['facts'].get('ST-101')
        if grant:
            counts={};initial=[]
            for i,uid in enumerate(['S01']*3+['S02']*3+['S03']*2,1):
                counts[uid]=counts.get(uid,0)+1;iid=f'INIT-{uid}-'+chr(64+counts[uid]);initial.append(iid)
                expect(iid,uid,'COMMISSION','ST-101:'+str(i))
                _check(members.get(iid,{}).get('acquisition')=='initial_commission',iid,'委任来源不符')
            evidence=grant['evidence']
            _check(evidence.get('source')=='commission' and evidence.get('initial_ids')==initial
                   and evidence.get('initial_roster_seed')==c['initial_roster_seed'], 'ST-101','初始委任精确来源不符')
        for request,r in c['summons'].items():
            expect(r['instance_id'],r['hero_id'],'SUMMON',request)
            _check(members.get(r['instance_id'],{}).get('acquisition')=='hero_seal',r['instance_id'],'应召来源不符')
        if c['companion']:
            r=c['companion'];_check(r['instance_id']=='COMPANION-H04' and r['owner']=='H04','companion','来源不符')
            expect(r['instance_id'],'PET-H04','COMPANION','H04')
            _check(members.get(r['instance_id'],{}).get('acquisition')=='companion_registration',r['instance_id'],'伴兽来源不符')
    else:
        fixture=[v for v in register.values() if isinstance(v,dict) and v.get('source_kind')=='FIXTURE_INITIAL']
        refs=[v.get('source_ref') for v in fixture]
        hero=any(isinstance(r,str) and r.startswith('HERO:') for r in refs)
        cmd=any(isinstance(r,str) and r.startswith('CMD:') for r in refs)
        _check(not (hero and cmd),'fixture','初始来源混用')
        if hero:
            from hero_fixtures import TEAMS
            _check(s['team_id'] in TEAMS,'fixture.team_id','未知试验队')
            for i,uid in enumerate(TEAMS[s['team_id']][0],1):
                expect(f'HT-{i:02}',uid,'FIXTURE_INITIAL','HERO:'+s['team_id']+':'+str(i))
        else:
            team='T02' if cmd else s['team_id']
            _check(not cmd or s['team_id']=='CMD','fixture.team_id','CMD来源不符')
            spec=next((t for t in cat.config['teams'] if t['team_id']==team),None)
            _check(spec is not None,'fixture.team_id','未知Catalog试验队')
            for i,m in enumerate(spec['members'],1):
                expect(m['instance_id'],'CMD' if cmd and i==1 else m['unit_id'],
                       'FIXTURE_INITIAL',('CMD:' if cmd else 'CAT:')+s['team_id']+':'+str(i))
    sequence=s.get('recruit_sequence');_integer(sequence,'recruit_sequence')
    bases={v['id']:v for v in cat.rules['units'].values()};bases.update(cat.rules['mercenaries'])
    recruit_refs=[]
    for iid,row in register.items():
        _mapping(row,'enrollment_register.'+iid)
        _check(set(row)=={'unit_id','source_kind','source_ref'},iid,'登记字段不符')
        if row['source_kind']!='RECRUIT':continue
        seq=row['source_ref'];_integer(seq,iid+'.source_ref',1,sequence)
        recruit_refs.append(seq);uid=row['unit_id']
        _check(iid==f'N-{seq:04d}' and uid in bases,iid,'新人序号/职业不符')
        m=members[iid];_check(type(m.get('recruit_sequence')) is int and m['recruit_sequence']==seq,iid,'新人序号不符')
        rng=keyed_rng(s['campaign_seed'],f'recruit:{seq}')
        birth={k:rng.randint(*bounds) for k,bounds in bases[uid]['ranges'].items()}
        _check(m.get('birth_stats')==birth,iid+'.birth_stats','新人出生来源不符')
        expect(iid,uid,'RECRUIT',seq)
    _check(sorted(recruit_refs)==list(range(1,sequence+1)),'recruit_sequence','新人加入全集不连续或重复')
    _check(register==expected,'enrollment_register','来源与Catalog/委任/新人/应召/伴兽双向不闭合')
    batches={}
    for b in s['capture_batches']:
        _check(b['id'] not in batches,'capture_batches','批次重复');batches[b['id']]=b
    for iid,m in members.items():
        _check(m.get('unit_id')==register[iid]['unit_id'],iid,'职业与加入登记不符')
        if locations[iid] not in ('captives','memorial'):continue
        cap=_mapping(m.get('capture'),iid+'.capture');b=batches.get(cap.get('batch_id'))
        _check(b is not None,iid+'.capture','永久损失缺原捕获批次')
        for field in ('capture_day','deadline','mode','origin_region','origin_site','source','encounter_id'):
            _check(cap.get(field)==b.get(field),iid+'.capture.'+field,'原捕获批次不符')
        _integer(cap.get('capture_day'),iid+'.capture_day')
        _integer(cap.get('deadline'),iid+'.deadline',cap['capture_day'])
        if locations[iid]=='captives':
            _check(cap.get('status') in ('CAPTURED','MISSING'),iid+'.capture','可恢复状态不符')
            continue
        _integer(cap.get('lost_day'),iid+'.lost_day',cap['deadline'],s['day'])
        _check(cap.get('status')=='LOST' and cap.get('equipment_state')=='lost'
               and cap.get('settlement_id')==f"{s['id']}:D{cap['lost_day']}",iid+'.capture','永久损失状态或结算日不符')
    return members,locations


def validate_enrollment(game):
    try:
        return _validate_enrollment(game)
    except (KeyError,TypeError,IndexError,AttributeError,StopIteration) as exc:
        raise ValueError('加入登记完整性错误：来源、名册或捕获字段缺失/类型异常。') from exc
