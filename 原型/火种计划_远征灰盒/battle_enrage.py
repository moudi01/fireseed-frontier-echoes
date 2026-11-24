"""Unlimited active sustain and a deterministic per-encounter enrage clock."""
VERSION = 'SUSTAIN-ENRAGE-0.75'
NORMAL_TICKS = 120
TIER_INTERVAL = 10
SUSTAIN_KINDS = {'heal', 'shield', 'private_shield', 'hero_heal', 'hero_group_heal',
                 'hero_shield', 'hero_group_shield', 'hero_support'}


def unlimited_sustain(cards):
    """Only active healing/shield cards; revive and one-use effects stay intact."""
    for card in cards:
        if card.get('kind') in SUSTAIN_KINDS:
            card['cast_limit'] = None
    return cards


def install(catalog):
    import battle_skills
    unlimited_sustain(battle_skills.CORE.values())
    import roster_content
    for identity in ('M02', 'M05'):
        for active in roster_content.PERSONAS.get(identity, {}).get('actives', []):
            active['description'] = active['description'].replace('每战2次', '按冷却循环，不限次数')

    def walk(value):
        if isinstance(value, dict):
            if 'move_id' in value:
                unlimited_sustain([value])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for value in (catalog.rules, catalog.enemy_templates, catalog.encounters):
        walk(value)


def initialize(battle, entry_tick=0):
    if type(entry_tick) is not int or not 0 <= entry_tick <= battle['tick']:
        raise ValueError('狂暴入场时钟无效。')
    battle['enrage'] = dict(version=VERSION, entry_tick=entry_tick,
                            normal_ticks=NORMAL_TICKS, tier_interval=TIER_INTERVAL)


def level(battle, tick=None):
    if battle is None:
        return 0
    tick = battle['tick'] if tick is None else tick
    entry = battle.get('enrage', {}).get('entry_tick', 0)
    age = tick - entry
    return max(0, (age - NORMAL_TICKS - 1) // TIER_INTERVAL + 1)


def damage_multiplier(battle, actor, tick=None):
    return 1 + level(battle, tick) if actor['side'] == 'enemy' else 1


def start_tick(battle, tick, log):
    if 'enrage' not in battle:
        initialize(battle)
    tier = level(battle, tick)
    if tier > level(battle, tick - 1):
        log('enrage_started' if tier == 1 else 'enrage_escalated',
            tier=tier, damage_multiplier=1 + tier,
            elapsed_ticks=tick - battle['enrage']['entry_tick'],
            entry_tick=battle['enrage']['entry_tick'],
            normal_ticks=NORMAL_TICKS, tier_interval=TIER_INTERVAL)


def rule_text():
    return ('每场前120拍正常；第121拍怪物造成伤害×2，此后每10拍再增加1倍基础伤害，'
            '不封顶。狂暴不提高治疗、护盾或施法速度，不跳过护盾与减伤；'
            '不按超时直接判负。魔王与管理员各自计时，连续生命与冷却保持。')


def public(battle=None):
    result = dict(version=VERSION, normal_ticks=NORMAL_TICKS,
                  starts_at_elapsed_tick=NORMAL_TICKS + 1,
                  tier_interval=TIER_INTERVAL, rule=rule_text())
    if battle is not None:
        tier = level(battle)
        elapsed = battle['tick'] - battle.get('enrage', {}).get('entry_tick', 0)
        result.update(elapsed_ticks=elapsed, tier=tier, active=tier > 0,
                      damage_multiplier=1 + tier,
                      ticks_to_enrage=max(0, NORMAL_TICKS + 1 - elapsed))
    return result


def describe(battle):
    row = public(battle)
    if row['active']:
        return (f"狂暴{row['tier']}阶：怪物伤害×{row['damage_multiplier']}；"
                f"本场{row['elapsed_ticks']}拍，每10拍再升1阶。")
    return (f"本场{row['elapsed_ticks']}/120拍；第121拍开始狂暴，"
            '怪物伤害×2，此后每10拍再加1倍基础伤害。')


def validate(battle):
    if battle is None:
        return True
    row = battle.get('enrage')
    expected_keys = {'version', 'entry_tick', 'normal_ticks', 'tier_interval'}
    if (not isinstance(row, dict) or set(row) != expected_keys
            or row.get('version') != VERSION
            or type(row.get('entry_tick')) is not int
            or not 0 <= row['entry_tick'] <= battle['tick']
            or type(row.get('normal_ticks')) is not int or row['normal_ticks'] != NORMAL_TICKS
            or type(row.get('tier_interval')) is not int or row['tier_interval'] != TIER_INTERVAL):
        raise ValueError('狂暴规则或时钟损坏。')
    admin = battle.get('encounter_id') == 'BATTLE-ADMIN'
    expected_entry = battle.get('boss_threats', {}).get('entry_tick') if admin else 0
    if row['entry_tick'] != expected_entry:
        raise ValueError('狂暴入场时钟与本场来源不符。')
    return True
