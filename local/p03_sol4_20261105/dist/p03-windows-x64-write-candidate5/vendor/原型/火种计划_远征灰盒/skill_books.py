"""Personal SB libraries, two slots and pre-battle automation; no BK migration."""
from copy import deepcopy
import book_catalog as catalog

NAMES = catalog.NAMES
ACTIVE = {b: catalog.BOOKS[b]['card'] for b in catalog.ACTIVE_IDS}
PASSIVE_IDS = catalog.PASSIVE_IDS
ALIASES = {}
DEPENDENCIES = {}


def check(ok, message):
    if not ok: raise ValueError(message)


def _uid(m): return m.get('unit_id', m.get('kind', ''))


def _core(m):
    import battle_skills, commander
    uid = _uid(m)
    return commander.cards() if uid == 'CMD' else battle_skills.core_cards(uid)


def capabilities(m):
    """Permanent medium/native capability, never live targets or cooldowns."""
    uid = _uid(m)
    medium = m.get('basic_medium', m.get('medium'))
    if medium is None:
        medium = 'near' if m.get('range', 1) == 1 or uid == 'M01' else 'projectile'
    dtype = m.get('attack_type', 'physical')
    magic = dtype == 'magic'
    if not magic:
        magic = any(x.get('kind') == 'damage' and x.get('damage_type') == 'magic'
                    for x in _core(m))
    return {'near': medium == 'near', 'projectile': medium == 'projectile',
            'physical_near': medium == 'near' and dtype == 'physical',
            'physical_projectile': medium == 'projectile' and dtype == 'physical',
            'magic': magic, 'walking': m.get('locomotion', 'walking') == 'walking'}


def reason(m, book):
    if book not in NAMES: return '不属于当前SB技能书目录。'
    uid = _uid(m)
    if not (uid.startswith(('M', 'H')) or uid == 'CMD'):
        return '普通士兵与伴兽没有技能书槽'
    cap = capabilities(m)
    labels = {'near': '近击', 'physical_near': '物理近击',
              'physical_projectile': '物理投射', 'magic': '魔法', 'walking': '步行'}
    missing = [labels[x] for x in catalog.BOOKS[book]['requires'] if not cap[x]]
    return '缺少' + '、'.join(missing) + '能力' if missing else ''


def has(a, book):
    return a.get('side', 'player') == 'player' and book in a.get('books_equipped', [])


def card(book, member=None): return catalog.card(book, member)


def cards(m, core):
    available = deepcopy(core) + [card(b, m) for b in m.get('books_equipped', []) if b in ACTIVE]
    order = {mid: i for i, mid in enumerate(m.get('skill_queue', []))}
    return [x for _, x in sorted(enumerate(available),
            key=lambda row: (order.get(row[1]['move_id'], len(order) + row[0]), row[0]))]


def active_ids(m): return [x['move_id'] for x in cards(m, _core(m))]


def main_ids(m):
    """Only equipped, enabled looping damage books drive explicit approach."""
    return [x['move_id'] for x in cards(m, []) if x['kind'] == 'damage'
            and x.get('cast_limit') is None and x['move_id'] not in m.get('disabled_skills', [])]


def _reconcile(m):
    available = active_ids({**m, 'skill_queue': []})
    old = m.get('skill_queue', [])
    m['skill_queue'] = [x for x in old if x in available]
    m['skill_queue'] += [x for x in available if x not in m['skill_queue']]
    m['disabled_skills'] = [x for x in m.get('disabled_skills', []) if x in available]
    if m.get('main_attack', 'AUTO') not in ('AUTO', 'BASIC') and m['main_attack'] not in main_ids(m):
        m['main_attack'] = 'AUTO'


def initialize(game):
    import town
    game.s['book_stock'] = {}
    for m in town.roster(game):
        m.setdefault('books_learned', [])
        m.setdefault('books_equipped', [])
        m.setdefault('main_attack', 'AUTO')


def validate_member(m):
    learned = m.get('books_learned', []); equipped = m.get('books_equipped', [])
    check(isinstance(learned, list) and all(isinstance(x, str) for x in learned), '个人学习库无效。')
    check(len(learned) == len(set(learned)) and set(learned) <= NAMES.keys(), '个人学习库无效。')
    check(all(not reason(m, b) for b in learned), '学习库与本人能力不符。')
    check(isinstance(equipped, list) and all(isinstance(x, str) for x in equipped), '技能书槽无效。')
    check(len(equipped) == len(set(equipped)) <= 2 and set(equipped) <= set(learned),
          '书槽必须是已学技能，最多两项且不重复。')
    available = active_ids(m)
    for key in ('skill_queue', 'disabled_skills'):
        value = m.get(key, [])
        check(isinstance(value, list) and all(isinstance(x, str) for x in value), '自动队列或关闭项无效。')
        check(len(value) == len(set(value)) and set(value) <= set(available), '自动队列或关闭项包含未装备技能。')
    check(not m.get('skill_queue') or set(m['skill_queue']) == set(available), '自动队列须包含全部现有主动。')
    main = m.get('main_attack', 'AUTO')
    check(isinstance(main, str) and (main in ('AUTO', 'BASIC') or main in main_ids(m)),
          '主攻必须是AUTO、BASIC或本人已装备且启用的循环伤害书。')


def validate(game):
    import town
    stock = game.s.get('book_stock')
    check(isinstance(stock, dict) and set(stock) <= NAMES.keys()
          and all(type(n) is int and n >= 0 for n in stock.values()), '书库存无效。')
    check(not game.s.get('book_receipts'), '旧版首次领书记录不属于当前目录。')
    for m in town.roster(game): validate_member(m)


def describe(game, member=None):
    import town
    rows = ['技能书库存 ' + str(game.s.get('book_stock', {}))
            + '；基础8/进阶12/专精16/魔将20铜。采购与学习分开，学习耗1本、不耗日；本人两书槽。']
    for m in ([member] if member else town.available(game)):
        rows.append(m['instance_id'] + ' 已学' + str(m.get('books_learned', []))
                    + ' 两槽' + str(m.get('books_equipped', [])) + ' 队列' + str(active_ids(m))
                    + ' 关闭' + str(m.get('disabled_skills', [])) + ' 主攻' + m.get('main_attack', 'AUTO'))
    return '\n'.join(rows)


def visible(game, book):
    row = catalog.BOOKS[book]
    if not row.get('hidden'):
        return True
    if game.s.get('book_stock', {}).get(book, 0) > 0:
        return True
    people = game.s.get('party', []) + game.s.get('home_roster', [])
    return any(book in m.get('books_learned', []) or book in m.get('books_equipped', [])
               for m in people)


def handle(game, args):
    import book_rewards
    s = game.s
    books = [b for b in NAMES if visible(game, b)]
    if not args or args == ['list']:
        return '\n'.join(catalog.describe(b) + ('；已开放' if book_rewards.unlocked(game, b)
                         else '；开放条件：' + book_rewards.requirement(game, b))
                         for b in books) + '\n' + describe(game)
    if args[0] == 'show' and len(args) == 2:
        m = game.member(args[1])
        return describe(game, m) + '\n' + '\n'.join(catalog.describe(b) + '：' + (reason(m, b) or '适配') for b in books)
    op = args[0]
    configuring = op in ('equip', 'queue', 'auto', 'main')
    if configuring:
        check(s['phase'] in ('TOWN', 'EXPLORE'), '开战后不能更换书槽、队列、开关或主攻。')
    else:
        check(s['phase'] == 'TOWN', '技能书采购和学习需在城镇进行。')
    check(op in ('buy', 'learn', 'equip', 'queue', 'auto', 'main') and len(args) >= 2,
          'book show/buy/learn/equip/queue/auto/main 队员ID；任务与自选领取请用book奖励命令。')
    m = game.member(args[1]); items = [x.upper() for x in args[2:]]
    if s['phase'] == 'EXPLORE':
        check(m in s['party'] and m['hp'] > 0, '野外只能调整仍在随行队伍中的站立队员。')
    if op in ('buy', 'learn'):
        check(len(items) == 1 and items[0] in NAMES, '请选择当前SB技能书ID，旧BK不在新目录。')
        book = items[0]
        check(not reason(m, book), reason(m, book))
        check(book not in m.get('books_learned', []), '本人已学，不重复扣书或采购。')
        if op == 'buy':
            check(not catalog.BOOKS[book].get('hidden'), '隐藏技能书不能购买；保全十案后获得。')
            check(book_rewards.unlocked(game, book), '采购资格未取得：' + book_rewards.requirement(game, book) + '。')
            amount = book_rewards.price(game, book)
            check(s['bank']['copper'] >= amount, f'采购需{amount}铜。')
            s['bank']['copper'] -= amount
            s['book_stock'][book] = s['book_stock'].get(book, 0) + 1
        else:
            check(s['book_stock'].get(book, 0) > 0, '库存没有这本书；先采购或领取。')
            s['book_stock'][book] -= 1
            m.setdefault('books_learned', []).append(book)
        game.log('book_' + op, member=m['instance_id'], book=book)
        return describe(game, m)
    if op == 'equip':
        if items == ['CLEAR']: items = []
        check(len(items) == len(set(items)) <= 2 and set(items) <= set(m.get('books_learned', [])),
              '最多装两本已学书；clear可留空。')
        m['books_equipped'] = items; _reconcile(m)
    elif op == 'queue':
        check(len(items) == len(set(items)) and set(items) == set(active_ids(m)),
              '队列需按希望的顺序列全本人现有主动ID。')
        m['skill_queue'] = items; _reconcile(m)
    elif op == 'auto':
        check(len(items) == 2 and items[0] in active_ids(m) and items[1] in ('ON', 'OFF'),
              'book auto 队员 SK-SB-D02 on/off；也可指定职业核心ID。')
        disabled = m.setdefault('disabled_skills', [])
        if items[0] in disabled: disabled.remove(items[0])
        if items[1] == 'OFF': disabled.append(items[0])
        _reconcile(m)
    elif op == 'main':
        check(len(items) == 1 and (items[0] in ('AUTO', 'BASIC') or items[0] in main_ids(m)),
              'book main 队员 AUTO|BASIC|已装备且启用的SK-SB伤害招。')
        m['main_attack'] = items[0]
    game.log('book_' + op, member=m['instance_id'], items=items)
    return describe(game, m)


# Lazy compatibility bridge for existing native support producers. New book
# mechanics are executed once by book_combat; retired BK/PL budgets stay absent.
def choose(*args, **kwargs):
    from book_combat import choose as fn
    return fn(*args, **kwargs)


def begin(*args, **kwargs):
    from book_combat import begin as fn
    return fn(*args, **kwargs)


def release(*args, **kwargs):
    from book_combat import release as fn
    return fn(*args, **kwargs)


def support_success(*args, **kwargs):
    from book_combat import support_success as fn
    return fn(*args, **kwargs)


def increase(*args, **kwargs): return 0


def reduction(a, amount, tick, log): return amount


def consumed(*args, **kwargs): return None
