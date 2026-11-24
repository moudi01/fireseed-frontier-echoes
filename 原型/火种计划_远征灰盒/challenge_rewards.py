"""Frozen highest-contract G stipends; ordinary rewards/pity stay independent.

The bonus is earned by an actual non-debug G victory, carried in the existing
pending/material ledgers and settled by their existing return/defeat paths.
No new root-state wallet, reward currency, event quota or party scaling exists.
"""
from copy import deepcopy
import hashlib
import json

import depth_growth

VERSION = 'CHALLENGE-GOAL-0.71'
BANDS = (
    {'minimum_level': 6, 'copper': 4, 'crystal': 0, 'crystal_shard': 0},
    {'minimum_level': 7, 'copper': 8, 'crystal': 1, 'crystal_shard': 0},
    {'minimum_level': 8, 'copper': 12, 'crystal': 2, 'crystal_shard': 2},
    {'minimum_level': 9, 'copper': 16, 'crystal': 3, 'crystal_shard': 4},
)
SHARD_CAPS = {'SHORT': 0, 'MEDIUM': 2, 'LONG': 6}
KEYS = ('copper', 'crystal', 'crystal_shard')
RECEIPT = 'challenge_reward_receipt'


def check(ok, message):
    if not ok:
        raise ValueError('最高险境津贴：' + message)


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def _zero():
    return {key: 0 for key in KEYS}


def _amount(level, remaining_shards):
    check(type(level) is int and level >= 1, '实际威胁须为正整数。')
    result = _zero()
    for band in BANDS:
        if level >= band['minimum_level']:
            result = {key: band[key] for key in KEYS}
    result['crystal_shard'] = min(result['crystal_shard'], max(0, remaining_shards))
    return result


def _contract(cat, profile, pressure, difficulty, paths, rules):
    check(profile in SHARD_CAPS, '普通远征长度无效。')
    pressure = pressure or {}
    active = (pressure.get('chapter', 0) >= 3 and difficulty == 'D2'
              and pressure.get('milestone') == 'FINALE_READY')
    source = {key: pressure.get(key) for key in
              ('route_id', 'chapter', 'milestone', 'stage_floor', 'hp_percent', 'attack_percent')}
    source['difficulty'] = difficulty
    quotes = []
    cap = SHARD_CAPS[profile] if active else 0
    for path in sorted(paths):
        levels = depth_growth.path_levels(rules, path)
        remaining = cap
        total = _zero()
        gates = []
        for rid, level in zip(path, levels):
            amount = _amount(level, remaining) if active else _zero()
            remaining -= amount['crystal_shard']
            for key in KEYS:
                total[key] += amount[key]
            gates.append(dict(region=rid, effective_threat=level, bonus=amount))
        quotes.append(dict(path=list(path), levels=levels, goals=gates, total_bonus=total))
    return dict(version=VERSION, active=active, source=source, profile=profile,
                frozen_at='departure', scale_by_party=False, bands=deepcopy(list(BANDS)),
                independent_shard_cap=cap, path_quotes=quotes,
                event_material_quota_unchanged=True, original_rewards_unchanged=True,
                quality_pity_unchanged=True,
                claim_rule='real_non_debug_G_victory_then_carry_then_actual_settlement')


def bind(cat, manifest):
    """Call after late_pressure.bind and before the final manifest digest."""
    manifest['challenge_rewards'] = _contract(cat, manifest['profile'],
        manifest.get('progression_pressure'), manifest['tier']['id'],
        manifest['paths'], manifest['depth_growth'])


def preview(game):
    """Town quote from public route/facts only; never call tiers.public here."""
    from expedition_tiers import TIERS
    from check_multi_region import routes
    import late_pressure
    route = next(row for row in game.cat.config['routes'] if row['route_id'] == game.s['route'])
    profile = route['profile']
    rules = depth_growth.policy(game.cat)
    rules['tier_floor'] = TIERS[game.s.get('difficulty', 'D0')]['floor']
    pressure = late_pressure.preview(game, rules)
    world = {row['region_id']: set(row['neighbors']) for row in game.cat.multi['regions']}
    allowed = {row['region_id'] for row in game.cat.multi['regions']
               if set(row['access_requires_all']) <= set(route['facts'])}
    paths = list(routes(world, allowed, game.cat.multi['profiles'][profile]['region_count'],
                        route['selected_path'][0], route['selected_path'][-1]))
    return _contract(game.cat, profile, pressure, game.s.get('difficulty', 'D0'), paths, rules)


def _receipts(regions):
    rows = [region[RECEIPT] for region in regions.values() if RECEIPT in region]
    return sorted(rows, key=lambda row: row['source']['region_index'])


def _total(rows):
    return {key: sum(row['bonus'][key] for row in rows) for key in KEYS}


def _frozen(game):
    manifest = game.s.get('manifest') or {}
    return manifest.get('challenge_rewards') if game.s.get('mission') == 'ORDINARY' else None


def award_goal(game, battle):
    """Call AFTER original G grant, clear marker and battle-report append.

    This function never settles bank/warehouse or debits event material quota.
    An exact duplicate is a read-only receipt lookup, not another payment.
    """
    s = game.s
    contract = _frozen(game)
    if not contract or not contract['active']:
        return None
    check(s.get('site') == 'G' and battle.get('result') == 'VICTORY', '仅真实G胜利可授予津贴。')
    if s.get('debug_tainted') or battle.get('debug_tainted'):
        return None
    region = s['regions'][s['region']]
    check('G' in region['cleared'], '须先提交本区G胜利。')
    check(any(row == battle for row in s['battle_reports']), '缺少本趟真实已归档战报。')
    binding = battle.get('world_binding') or {}
    check(binding.get('region') == s['region'] and binding.get('site') == 'G', '战报不属于当前G现场。')
    level = region['growth']['effective_threat']
    check(type(level) is int and level == battle.get('effective_threat'), '战报与本区冻结威胁不一致。')
    check(battle['encounter_id'] == s['manifest']['regions'][s['region']]['encounters']['G']['encounter_id'], '不是冻结G敌阵。')
    source = dict(expedition=s['expedition_no'], region=s['region'], site='G',
        region_index=region['growth']['region_index'], battle_id=battle['battle_id'],
        encounter_id=battle['encounter_id'], effective_threat=level,
        contract_digest=_digest(contract))
    if RECEIPT in region:
        check(region[RECEIPT]['source'] == source, '本区已有不同来源的津贴回执。')
        return deepcopy(region[RECEIPT])
    used = _total(_receipts(s['regions']))['crystal_shard']
    amount = _amount(level, contract['independent_shard_cap'] - used)
    row = dict(version=VERSION, source=source, bonus=amount, status='PENDING')
    for key in ('copper', 'crystal'):
        s['pending'][key] += amount[key]
    if amount['crystal_shard']:
        s['materials']['crystal_shard'] = s['materials'].get('crystal_shard', 0) + amount['crystal_shard']
    region[RECEIPT] = row
    game.log('challenge_goal_bonus', receipt=deepcopy(row))
    return deepcopy(row)


def _summary(contract, rows, outcome, reason, summary):
    material = (summary.get('materials', {}) if outcome == 'BANKED'
                else summary.get('lost_cargo', {}).get('materials', {}))
    return dict(version=VERSION, active=bool(contract and contract['active']),
                outcome=outcome, reason=reason, awarded=_total(rows), receipts=deepcopy(rows),
                carried_materials_at_settlement=deepcopy(material),
                material_note='津贴碎晶可按原规则途中使用；本表为已获得额，实际入库或丢失以结算剩余携材为准，不重复转账。')


def settle(game, safe, reason):
    """Call after summary construction, before clearing trip state/cargo.

    Currency/material transfer remains entirely in the original settlement.
    BANKED marks safe contract settlement; fungible shards already spent during
    the trip are not claimed again as warehouse income or refunded on defeat.
    """
    check(type(safe) is bool, '结算标志无效。')
    contract = _frozen(game)
    rows = _receipts(game.s.get('regions', {}))
    if not rows and not (contract and contract['active']):
        return None
    outcome = 'BANKED' if safe else 'LOST'
    for row in rows:
        check(row['status'] in ('PENDING', outcome), '津贴已按另一结果结算。')
        row['status'] = outcome
    return _summary(contract, rows, outcome, reason, game.s.get('summary') or {})


def _validate_trip(game, trip, current=False):
    regions = trip.get('regions') or {}
    rows = _receipts(regions)
    manifest = trip.get('manifest') or {}
    contract = manifest.get('challenge_rewards')
    if trip.get('mission') != 'ORDINARY' or not manifest:
        check(not rows, '固定任务或无出发合同不能有津贴回执。')
        return
    check(isinstance(contract, dict), '普通远征缺少出发冻结合同。')
    expected = _contract(game.cat, manifest['profile'], manifest.get('progression_pressure'),
                         manifest['tier']['id'], manifest['paths'], manifest['depth_growth'])
    check(contract == expected, '出发冻结津贴规格被改动。')
    if not contract['active']:
        check(not rows, '非最高险境合同不得领取津贴。')
    summaries = trip.get('summary') or {}
    settled = summaries.get('challenge_rewards')
    outcome = settled.get('outcome') if isinstance(settled, dict) else 'PENDING'
    check(outcome in ('PENDING', 'BANKED', 'LOST'), '结算状态无效。')
    if settled is not None:
        expected_outcome = 'LOST' if summaries.get('result') == 'DEFEAT' else 'BANKED'
        check(outcome == expected_outcome, '津贴与原远征结算结果不一致。')
        if current:
            check(trip.get('phase') not in ('EXPLORE', 'BATTLE'), '途中不能提前标记归城或败战结算。')
    remaining = contract['independent_shard_cap']
    visited = trip.get('visited_regions', [])
    reports = trip.get('battle_reports', [])
    expected_regions = []
    for rid in visited:
        region = regions[rid]
        matches = [b for b in reports if b.get('world_binding', {}).get('region') == rid
                   and b.get('world_binding', {}).get('site') == 'G'
                   and b.get('result') == 'VICTORY' and not b.get('debug_tainted')]
        if contract['active'] and 'G' in region['cleared'] and matches:
            expected_regions.append(rid)
        row = region.get(RECEIPT)
        if row is None:
            continue
        check(contract['active'] and rid in expected_regions and len(matches) == 1, '回执缺少唯一真实G胜利来源。')
        battle = matches[0]
        level = region['growth']['effective_threat']
        source = dict(expedition=trip['expedition_no'], region=rid, site='G',
            region_index=region['growth']['region_index'], battle_id=battle['battle_id'],
            encounter_id=battle['encounter_id'], effective_threat=level,
            contract_digest=_digest(contract))
        check(battle.get('effective_threat') == level and battle['encounter_id'] == manifest['regions'][rid]['encounters']['G']['encounter_id'], '回执战报与冻结G内容不一致。')
        amount = _amount(level, remaining)
        check(row == dict(version=VERSION, source=source, bonus=amount, status=outcome), '津贴回执来源、数额或状态被改动。')
        remaining -= amount['crystal_shard']
    check({row['source']['region'] for row in rows} == set(expected_regions), '真实G胜利与津贴回执不同步。')
    check(_total(rows)['crystal_shard'] <= contract['independent_shard_cap'], '超过独立碎晶上限。')
    if settled is not None:
        check(settled == _summary(contract, rows, outcome, settled.get('reason'), summaries), '归城津贴摘要与来源回执不同步。')
    elif rows:
        check(all(row['status'] == 'PENDING' for row in rows), '途中津贴不能提前结算。')


def validate(game):
    """No mutation; current and archived same-version source proofs survive town."""
    try:
        _validate_trip(game, game.s, True)
        for trip in game.s.get('completed_history', []):
            _validate_trip(game, trip)
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError('最高险境津贴：存档合同或来源回执结构不完整。') from exc


def public(game):
    contract = (_frozen(game) if game.s.get('phase') != 'TOWN' else None)
    if contract is None:
        if game.s.get('mission') != 'ORDINARY':
            return dict(version=VERSION, active=False, fixed_mission=True)
        contract = preview(game)
    result = deepcopy(contract)
    rows = _receipts(game.s.get('regions', {}))
    result.update(awarded=_total(rows), receipts=deepcopy(rows))
    return result


def describe(game):
    row = public(game)
    if not row.get('active'):
        return '最高险境津贴：本合同无额外津贴；原奖励、材料领取额度与品质保底沿原规则。'
    text = ('最高险境G胜利额外津贴：L6 +4铜；L7 +8铜1晶；L8 +12铜2晶2碎晶；L9及以上 +16铜3晶4碎晶。'
            f"本趟额外碎晶独立上限{row['independent_shard_cap']}，不占普通事件材料额度；原奖励与品质保底不变。"
            '须真实战胜G后携带，安全归城才入库；败战剩余钱材照旧丢失，出发、接敌或撤退不发未赢门奖。')
    if row.get('path_quotes'):
        totals = row['path_quotes'][0]['total_bonus']
        text += f" 当前长度完整通关示例额外{totals['copper']}铜{totals['crystal']}晶{totals['crystal_shard']}碎晶，以实际路线威胁和已赢G为准。"
    if any(row.get('awarded', {}).values()):
        text += ' 已实际获得津贴：' + str(row['awarded']) + '；碎晶途中使用后不重复入库。'
    return text
