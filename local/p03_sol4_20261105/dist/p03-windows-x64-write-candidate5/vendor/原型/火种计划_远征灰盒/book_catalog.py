"""SB-REWORK-1.1: personal books with cooldown-only active sustain.

This module contains data only.  Combat, acquisition receipts and personal
libraries live in book_combat, book_rewards and skill_books respectively.
"""
from copy import deepcopy

VERSION = 'SB-REWORK-1.1'
STAGE_PRICES = {'B': 8, 'I': 12, 'E': 16, 'X': 20}
STAGE_FACTS = {'B': 'ST-101', 'I': 'ST-104', 'E': 'CH2_COMPLETE'}
BOOKS = {}


def _add(code, name, category, stage, requires=(), *, w=1, c=4, r=1,
         kind='book_support', coefficient=None, damage_type=None, **effect):
    bid = 'SB-' + code
    passive = category == 'passive'
    card = None if passive else dict(
        move_id='SK-' + bid, book_id=bid, source='book', name=name,
        kind=kind, book_effect=bid, windup=w, cooldown=c, range=r,
        cast_limit=None,
        first_eligible_tick=1, interruptible=w > 0,
        delayable_cast=w > 0, max_targets=1, target_mode='single',
        medium='spell' if damage_type == 'magic' or category in ('heal', 'shield', 'buff') else 'tool',
    )
    if card is not None:
        if coefficient is not None: card['coefficient'] = coefficient
        if damage_type is not None: card['damage_type'] = damage_type
        card.update(deepcopy(effect))
        card['delayable_cast'] = w > 0 and card['medium'] == 'spell'
    BOOKS[bid] = dict(id=bid, name=name, category=category, stage=stage,
                     requires=list(requires), price=STAGE_PRICES[stage],
                     required_fact=STAGE_FACTS.get(stage), card=card,
                     effects=deepcopy(effect), effect=deepcopy(effect))


# Looping attacks.  "A" is resolved from the user's basic attack attribute,
# not their most favourable stat; the fixed physical/magic cards stay fixed.
_add('D01', '快刃', 'damage', 'B', ('physical_near',), w=0, c=4, r=1,
     kind='damage', coefficient=1.3, damage_type='physical', medium='near')
_add('D02', '重劈', 'damage', 'B', ('physical_near',), w=1, c=3, r=1,
     kind='damage', coefficient=2.2, damage_type='physical', medium='near', main_default=True)
_add('D03', '横扫', 'damage', 'I', ('physical_near',), w=1, c=5, r=1,
     kind='damage', coefficient=.9, damage_type='physical', medium='near',
     target_mode='fan', shape='book_fan', max_targets=3)
_add('D04', '破甲刺', 'damage', 'E', ('physical_near',), w=1, c=5, r=2,
     kind='damage', coefficient=1.9, damage_type='physical', medium='near', ignore_defense=.4)
_add('D05', '瞄准射击', 'damage', 'B', ('physical_projectile',), w=1, c=3, r=4,
     kind='damage', coefficient=1.8, damage_type='physical', medium='projectile')
_add('D06', '散射', 'damage', 'I', ('physical_projectile',), w=0, c=5, r=3,
     kind='damage', coefficient=1, damage_type='physical', medium='projectile',
     target_mode='multi', max_targets=2)
_add('D07', '贯线矢', 'damage', 'E', ('physical_projectile',), w=1, c=5, r=4,
     kind='damage', coefficient=1.6, damage_type='physical', medium='projectile',
     target_mode='line', shape='book_line', max_targets=2, second_coefficient=.8, penetration=1)
_add('D08', '追创射击', 'damage', 'E', ('physical_projectile',), w=0, c=5, r=4,
     kind='damage', coefficient=1.4, damage_type='physical', medium='projectile',
     execute_threshold=.35, execute_coefficient=2.1)
_add('D09', '火矢', 'damage', 'B', ('magic',), w=1, c=3, r=3,
     kind='damage', coefficient=1.7, damage_type='magic', medium='spell')
_add('D10', '近咒震击', 'damage', 'I', ('magic',), w=1, c=3, r=1,
     kind='damage', coefficient=2.4, damage_type='magic', medium='spell', main_default=False)
_add('D11', '碎火环', 'damage', 'I', ('magic',), w=1, c=5, r=3,
     kind='damage', coefficient=1.1, damage_type='magic', medium='spell',
     target_mode='ground', shape='book_area', radius=1, area=True, max_targets=3)
_add('D12', '蓄雷术', 'damage', 'E', ('magic',), w=2, c=5, r=4,
     kind='damage', coefficient=3.2, damage_type='magic', medium='spell',
     target_mode='locked_cell', shape='book_locked_cell')

# Standing, living allies only. Healing repeats on its own unchanged W/CD;
# there is no per-battle start limit and no additional revival permission.
_add('H01', '急救包扎', 'heal', 'B', w=0, c=4, r=1, kind='heal',
     heal_base=10, healing_power_coefficient=.5, max_hp_coefficient=.10, hp_threshold=.65)
_add('H02', '疗愈祷言', 'heal', 'B', w=1, c=4, r=3, kind='heal',
     heal_base=6, healing_power_coefficient=1.2, max_hp_coefficient=.10, hp_threshold=.6)
_add('H03', '群体急救', 'heal', 'I', w=2, c=6, r=3, kind='heal',
     heal_base=4, healing_power_coefficient=.8, max_hp_coefficient=.08,
     target_mode='friendly_area', radius=1, max_targets=3)
_add('H04', '回春印记', 'heal', 'E', w=1, c=6, r=3, kind='heal',
     heal_base=3, healing_power_coefficient=.6, max_hp_coefficient=.04,
     duration=3, heal_over_time=True, hp_threshold=.7)

_add('S01', '护身屏障', 'shield', 'B', w=0, c=5, r=0,
     target_mode='self', shield_base=8, max_hp_coefficient=.18, duration=3)
_add('S02', '隔位护持', 'shield', 'B', w=1, c=5, r=2,
     shield_base=6, max_hp_coefficient=.15, healing_power_coefficient=.6, duration=3)
_add('S03', '并肩护阵', 'shield', 'I', w=1, c=6, r=0,
     target_mode='friendly_area', radius=1, max_targets=3,
     shield_base=4, max_hp_coefficient=.12, healing_power_coefficient=.35, duration=3)
_add('S04', '不动壁垒', 'shield', 'E', w=1, c=7, r=0,
     target_mode='self', shield_base=8, max_hp_coefficient=.35, duration=4, breaks_on_move=True)

_add('M01', '疾行', 'move', 'B', ('walking',), w=0, c=5, r=0,
     kind='move', target_mode='path', steps=2)
_add('M02', '脱身步', 'move', 'I', ('walking',), w=0, c=5, r=0,
     kind='move', target_mode='path', steps=1, dodge_bonus=.3, duration=2)
_add('M03', '冲锋步', 'move', 'I', ('walking', 'near'), w=1, c=6, r=3,
     kind='move', target_mode='path', steps=3, approach_only=True)
_add('M04', '牵引救援', 'move', 'E', w=0, c=6, r=3,
     target_mode='ally_pull', steps=1, recipient_action_lock=True)

_add('C01', '震退', 'control', 'B', ('near',), w=0, c=5, r=1,
     kind='damage', coefficient=.8, damage_type='A', push=1, medium='near')
_add('C02', '缚足术', 'control', 'I', ('magic',), w=1, c=6, r=3,
     root_duration=3, medium='spell')
_add('C03', '延咒击', 'control', 'I', ('magic',), w=1, c=4, r=4,
     kind='damage', coefficient=.8, damage_type='magic', delay=1, medium='spell')
_add('C04', '封口击', 'control', 'E', ('near',), w=1, c=6, r=1,
     kind='damage', coefficient=1.2, damage_type='A', interrupt=True, medium='near')

_add('B01', '振奋战吼', 'buff', 'B', w=0, c=6, r=0,
     target_mode='friendly_area', radius=1, max_targets=3, attack_bonus=.15, duration=3)
_add('B02', '瞄准准备', 'buff', 'I', ('physical_projectile',), w=0, c=6, r=0,
     target_mode='self', range_bonus=1, ignore_defense=.25, duration=3)
_add('B03', '护行令', 'buff', 'E', w=0, c=6, r=3, movement_immunity=2, duration=2)
_add('B04', '会心蓄势', 'buff', 'E', w=0, c=7, r=0,
     target_mode='self', guaranteed_critical=True, extra_critical_damage=.5, duration=3)

_add('P01', '连击心得', 'passive', 'B', every=3, basic_coefficient_bonus=.7)
_add('P02', '机动护身', 'passive', 'I', ('walking',),
     trigger_interval=4, shield_base=4, max_hp_coefficient=.12, duration=2, delay_ticks=1)
_add('P03', '勤施护持', 'passive', 'E',
     trigger_interval=4, shield_base=4, max_hp_coefficient=.12, duration=3, delay_ticks=1)
_add('P04', '破盾反击', 'passive', 'E',
     trigger_interval=4, duration=3, basic_coefficient_bonus=1)

_add('X01', '守誓回斩', 'boss', 'X', ('near',), w=1, c=5, r=2,
     kind='damage', coefficient=1.8, damage_type='A', medium='near',
     protect_radius=2, max_hp_coefficient=.2, duration=3)
_add('X02', '猎踪突刺', 'boss', 'X', ('physical_near', 'walking'), w=1, c=5, r=3,
     kind='damage', coefficient=2, damage_type='physical', medium='near',
     target_mode='charge', steps=2)
_add('X03', '续命灯', 'boss', 'X', w=1, c=6, r=3, kind='heal',
     heal_base=8, healing_power_coefficient=1, max_hp_coefficient=.25,
     hp_threshold=.6, critical_hp_threshold=.3, shield_max_hp_coefficient=.2, duration=3)
_add('X04', '破律震击', 'boss', 'X', w=2, c=6, r=2,
     kind='damage', coefficient=1.6, damage_type='A', medium='spell',
     target_mode='ground', shape='book_area', radius=1, area=True, max_targets=3,
     shield_strip_coefficient=.6)
for i, fact in enumerate(('ST-201', 'ST-202', 'ST-301', 'ST-302'), 1):
    BOOKS[f'SB-X{i:02}'].update(boss_id=f'MG{i:02}', required_fact=fact)
_add('Z01', '缄默回执', 'counter', 'X', w=0, c=20, r=6,
     kind='counter_next_attack', target_mode='high_threat',
     medium='spell', hidden=True)
BOOKS['SB-Z01'].update(purchasable=False, hidden=True)

SUMMARIES = {
    'D01': '1格原目标1.3P物伤。',
    'D02': '1格原目标2.2P物伤，可设为主攻接敌。',
    'D03': '前方3格扇形，最多3个不同主体各0.9P物伤。',
    'D04': '2格原目标1.9P物伤，本击忽略40%物防。',
    'D05': '4格原目标1.8P物伤，优先可确认击杀者。',
    'D06': '3格内至多2个不同目标各1.0P物伤，不重复击中同主体。',
    'D07': '直线4格，首敌1.6P、次敌0.8P物伤；最多2主体，可穿1低障，高墙截断。',
    'D08': '4格原目标1.4P物伤；当前HP≤35%时改为2.1P，击杀不返冷却。',
    'D09': '3格原目标1.7M魔伤。',
    'D10': '1格原目标2.4M魔伤；默认贴脸备用，显式主攻才主动接近1格。',
    'D11': '中心3格、半径1，起手锁格，最多3主体各1.1M魔伤。',
    'D12': '4格锁原格，单主体3.2M魔伤；离格可躲。',
    'H01': '1格活友恢复floor(10+0.5H+0.10V)；可自救，优先HP≤65%。',
    'H02': '3格活友恢复floor(6+1.2H+0.10V)；可自救，优先HP≤60%。',
    'H03': '中心3格、半径1，最多3活友各恢复floor(4+0.8H+0.08V)。',
    'H04': '3格活友随后3拍拍末各恢复floor(3+0.6H+0.04V)；同名不叠，战末停止。',
    'S01': '本人获得floor(8+0.18V)私盾3拍；危险或HP≤60%时使用。',
    'S02': '2格单友（含本人）获得floor(6+0.15V+0.6H)私盾3拍。',
    'S03': '本人周围1格最多3友（含本人）各获得floor(4+0.12V+0.35H)私盾3拍。',
    'S04': '本人获得floor(8+0.35V)私盾4拍；真实移动立即弃盾。',
    'M01': '沿合法路径最多自主移动2格，无攻击；用于接敌或离开公开锁区。',
    'M02': '自主移动1格，生效拍及下一拍增加30个百分点闪避，总闪避上限50%。',
    'M03': '向可见目标最多前进3格取得近击位置，无攻击，不进入已公开危险格。',
    'M04': '3格可见站立友军向更接近施法者的安全邻格移动1格；占其本拍动作；不拉起手、预约位移、架阵或硬控者。',
    'C01': '1格原目标0.8A对应伤害，命中后向外推1格；受阻无额外伤害或眩晕。',
    'C02': '3格原敌随后3拍定根，不阻止普攻或已合法施法；成功后遵守书籍控制抗性。',
    'C03': '4格原目标0.8M魔伤；及时命中可延后施法1拍，同次施法只延后一次。',
    'C04': '1格原目标1.2A对应伤害，真正打断仍未释放且可打断的原技能；不绕过特殊破招条件。',
    'B01': '本人周围1格最多3友（含本人）物攻、魔攻+15%共3拍；同名不叠，不递乘自身加成。',
    'B02': '准备完成后的3个后续拍内，下次物理投射伤害动作射程+1、本击忽略25%物防；起手消费，落空不退。',
    'B03': '3格单友解除受阻与定根，并免疫新同类限制2拍；不解眩晕、伤势、侵蚀、重创或点名。',
    'B04': '准备完成后的3个后续拍内，下次非派生直接伤害动作必暴击，额外暴伤至少50%（上限100%）；起手一次消费，多目标共享。',
    'P01': '每第3次有效普攻，原主目标本击系数+0.7；按动作计数，落空不累计，不强化副目标。',
    'P02': '真实自主移动后次拍获得floor(4+0.12V)私盾2拍，触发间隔4拍；推移与失败移动不触发。',
    'P03': '主动治疗实际回血或护持实际增盾后，次拍本人获得floor(4+0.12V)私盾3拍，间隔4拍；群体一次只触发一次。',
    'P04': '本人私盾被敌伤或明确破盾击破后，3拍内下次普攻主目标系数+1.0，间隔4拍；支付、到期、弃盾不触发。',
    'X01': '2格原目标1.8A对应伤害；若其公开伤害动作威胁本人2格内同伴，再护其中1人20%V私盾3拍。',
    'X02': '目标3格，沿起手锁定合法路径最多移动2格；抵达邻格后2.0P物伤，未贴身不命中，无击杀返还。',
    'X03': '3格活友恢复floor(8+1.0H+0.25V)；起手HP≤30%则再给20%V私盾3拍，不复起。',
    'X04': '中心2格、半径1锁格，最多3主体先各剥floor(0.6A)实际盾，再各1.6A对应伤害；闪避落空不剥盾。',
    'Z01': '6格内选定一名高威胁敌人；其下一次伤害动作完全无效并被消耗。冷却20拍，按动作循环，不造成伤害。',
}
AUTO_SUMMARIES = {
    'D01': '当前合法接敌目标，快速填补攻击空档。',
    'D02': '按主攻射程接敌，选择有效单体伤害最高的合法目标。',
    'D03': '按不同主体覆盖数与有效总伤选择朝向；低收益可跳过。',
    'D04': '优先高物防且本击确有收益的目标。',
    'D05': '优先可确认击杀目标，其次稳定有效伤害。',
    'D06': '优先双目标；只有一敌时与普攻、其他可用攻击比较。',
    'D07': '按合法射线总伤选方向，检查墙与同主体去重。',
    'D08': '优先可斩杀者，其次低HP比例者。',
    'D09': '稳定合法单体输出，不等待未来暴击或闪避结果。',
    'D10': '默认只作贴脸备用，设为主攻后才按1格接敌。',
    'D11': '按公开中心的有效覆盖与总伤选点，起手后不追踪。',
    'D12': '优先公开起手或定根持续覆盖预计释放拍的原目标。',
    'H01': '优先HP≤65%的活友，也可自救。',
    'H02': '优先HP≤60%的活友，比较有效恢复量与公开危险。',
    'H03': '优先至少2名缺血者；单人仅在危急且其他救护不可用时施放。',
    'H04': '选择缺血≥30%或已公开持续承压者，不无效刷新同名回春。',
    'S01': '本人已被锁入公开危险或HP≤60%时使用，不覆盖更高同名盾。',
    'S02': '优先即将承伤者，再按缺血与现有盾选择。',
    'S03': '优先覆盖多名实际承压友军，不为满状态空耗动作。',
    'S04': '已在有效作战位置且当前无需避险时使用，后来仍可弃盾避险。',
    'M01': '接近选定攻击的合法位置或离开公开危险，已可行动时不空走。',
    'M02': '优先脱离公开锁区或近身威胁。',
    'M03': '只服务近击攻击意图，不穿人、不进入已公开危险。',
    'M04': '优先拉出公开锁区，只选择可被安全移动且本拍未忙的活友。',
    'C01': '优先推开逼近后排或需要保持距离的敌人。',
    'C02': '优先追击脆皮的敌人或可配合锁格输出者，不对免疫者空放。',
    'C03': '优先仍来得及延后的公开长起手；否则按纯伤害收益决定。',
    'C04': '优先真实可破招窗口，仍遵守Boss特定打断资格。',
    'B01': '优先覆盖正在接敌或准备伤害动作的友军。',
    'B02': '按增程后的合法攻击机会决定；完成后的3个后续拍可消费，不修改永久射程。',
    'B03': '优先受阻或定根且处于公开危险的活友。',
    'B04': '存在即将执行的有效直接伤害动作才准备；完成后的3个后续拍可消费。',
    'P01': '自动按有效普攻动作计数，多目标不加速。',
    'P02': '自动响应真实自主移动，同动作回放不重复触发。',
    'P03': '只响应实际有效主动治疗或增盾，派生、过量、无效刷新不触发。',
    'P04': '自动记录敌方破盾，再由下次有效普攻主目标消费。',
    'X01': '优先正在威胁同伴的可见敌人，护人条件不成立仍可正常攻击。',
    'X02': '优先合法可斩杀目标，其次当前目标；路径受阻停止。',
    'X03': '优先危急活友，自救合法；低血条件在起手冻结。',
    'X04': '优先有盾敌群，无盾仍比较有效范围伤害。',
    'Z01': '优先正在公开起手的高威胁首领；无合法目标时不空放。',
}
for code, text in SUMMARIES.items():
    row = BOOKS['SB-' + code]
    row['effect'] = text
    row['summary'] = text
    row['auto_summary'] = AUTO_SUMMARIES[code]
    if row['card'] is not None:
        row['card']['mechanic_summary'] = text

NAMES = {bid: row['name'] for bid, row in BOOKS.items()}
ACTIVE_IDS = tuple(bid for bid, row in BOOKS.items() if row['card'] is not None)
PASSIVE_IDS = tuple(bid for bid, row in BOOKS.items() if row['card'] is None)
ACTIVE = {bid: BOOKS[bid]['card'] for bid in ACTIVE_IDS}
STAGE_BOOKS = {stage: tuple(b for b, row in BOOKS.items()
                            if row['stage'] == stage and not row.get('hidden'))
               for stage in STAGE_PRICES}
REGION_THEMES = {
    'RG01': ('D01', 'D02', 'D03', 'H01', 'S01', 'M01', 'P01'),
    'RG02': ('D02', 'D04', 'S02', 'S04', 'C01', 'C04', 'P04'),
    'RG03': ('D09', 'D10', 'D11', 'D12', 'C02', 'C03', 'B04'),
    'RG04': ('H02', 'H03', 'H04', 'S03', 'M04', 'B03'),
    'RG05': ('D04', 'D07', 'D12', 'S04', 'C04', 'B02', 'P04'),
    'RG06': ('D01', 'D05', 'D06', 'M01', 'M02', 'M03', 'P02'),
    'RG07': ('H01', 'H02', 'H03', 'S02', 'S03', 'B01', 'B03', 'P03'),
    'RG08': ('D02', 'D05', 'D07', 'D08', 'S01', 'S04', 'B02', 'P01'),
}
REGION_THEMES = {rid: tuple('SB-' + b for b in ids) for rid, ids in REGION_THEMES.items()}
TASK_CHOICES = {
    'ST-104': STAGE_BOOKS['B'],
    'SB-T01': ('SB-D03', 'SB-D10', 'SB-M03'),
    'SB-T02': ('SB-D06', 'SB-B02', 'SB-M02'),
    'SB-T03': ('SB-H03', 'SB-S03', 'SB-P02'),
    'ST-303': STAGE_BOOKS['E'],
    **{f'ST-{n}': (f'SB-X{i:02}',) for i, n in enumerate((201, 202, 301, 302), 1)},
}


def card(book, member=None):
    """Return a detached card; resolve A only when a real user is supplied."""
    if book not in BOOKS or BOOKS[book]['card'] is None:
        raise ValueError('请选择新目录中的主动技能书。')
    result = deepcopy(BOOKS[book]['card'])
    if result.get('damage_type') == 'A' and member is not None:
        result['damage_type'] = member.get('attack_type', 'physical')
    return result


def install(cat):
    """Overlay the library in memory; never edit the historical JSON."""
    cat.rules['skill_books'] = {
        'version': VERSION, 'ids': list(BOOKS), 'slots': 2,
        'fixed_first_delivery': {}, 'catalog': deepcopy(BOOKS),
        'stage_prices': deepcopy(STAGE_PRICES), 'stage_facts': deepcopy(STAGE_FACTS),
        'region_themes': deepcopy(REGION_THEMES), 'task_choices': deepcopy(TASK_CHOICES),
        'drop_chances': {'goal': 25, 'elite': 50},
        'run_caps': {'SHORT': 1, 'MEDIUM': 2, 'LONG': 3},
    }


def describe(book):
    row = BOOKS[book]; item = row['card']
    requirement = '、'.join({'physical_near': '物理近击', 'physical_projectile': '物理投射',
                           'magic': '魔法', 'near': '近击', 'walking': '步行'}[x]
                          for x in row['requires']) or '通用'
    if item is None: timing = '被动'
    else:
        limit = item.get('cast_limit')
        timing = f"W{item['windup']}/C{item['cooldown']}，" + ('按冷却循环，不限次数' if limit is None else f'每战{limit}次')
    price = '隐藏' if row.get('hidden') else f"{row['price']}铜"
    return (f"{book} {row['name']}（{row['stage']}，{price}，{requirement}；{timing}）"
            + row['summary'] + ' 自动：' + row['auto_summary'])
