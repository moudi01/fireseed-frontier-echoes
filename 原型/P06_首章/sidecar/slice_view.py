"""Presentation for the first chapter and Ado's expedition."""
from ast import literal_eval
import math
import re
from collections import Counter


COMMANDS = {'quest', 'tutorial', 'move', 'fight', 'step', 'return', 'deploy', 'deploy_at',
            'place', 'retreat', 'flee', 'walkto', 'interact', 'recruit', 'squad', 'route',
            'town', 'book', 'summon', 'equip', 'unequip', 'dialogue', 'challenge', 'depart',
            'next', 'station', 'camp', 'medical', 'memory', 'remember', 'buy_supply',
            'pack_medical', 'rest', 'heal', 'level_up', 'care', 'stance', 'plan', 'maintain', 'rescue', 'choose',
            'facility', 'service', 'outfit', 'craft', 'stash', 'take', 'use', 'discard', 'supply', 'research', 'finale',
            'event', 'agla'}
MEMBER_ID = r'[A-Za-z0-9_-]{1,80}'
CONSUMABLE_TARGETS = rf'{MEMBER_ID}(?:,{MEMBER_ID}){{0,5}}'
CONSUMABLE_CODES = tuple(f'CO{number:02}' for number in range(1, 13))
PARTY_CONSUMABLES = ('CO11', 'CO12')
MATERIAL_GOALS = ('MAT-IRON', 'MAT-SHARD', 'MAT-FIBER', 'MAT-HERB')
OUTFIT_TARGETS = rf'{MEMBER_ID}(?:,{MEMBER_ID}){{0,2}}'
SERVICE_ORDER_ID = r'P06-SVC-[0-9]{1,12}'
BOOK_ID = r'SB-[A-Z0-9]{2,10}'
BUILD_ORDER_ID = r'P06-BLD-[0-9]{1,12}'
BUILDING_EFFECTS = {
    'hospital': '普通新伤恢复期缩短至 1 日，首次竣工时已有伤势额外减 1 日。',
    'lamp_store': '随队救护携带上限从 2 份增至 3 份。',
    'rescue_post': '失联调查和原人救援的基础补给从 1 份降至 0 份。',
    'council': '可暂停 1 项在建工程，保留已付材料和施工进度。',
    'barracks': '可为有出战记录的留城成员安排补训。',
    'armory': '可制作随身道具，也可购买下趟远征的防御整备。',
}
MULTILEVEL_BUILDINGS = ('lamp_store', 'armory')
CONSTRUCTION_ACTIONS = ('cancel', 'pause', 'resume')
BOOK_RESEARCH = {
    'SB-T01': ('近战研习', '每场胜利至少有一次己方近击使敌人掉血或消耗敌方护盾。'),
    'SB-T02': ('远击研习', '每场胜利至少有一次一格以外的己方投射或术法命中，使敌人掉血或消耗敌方护盾。'),
    'SB-T03': ('战地照护', '每场胜利至少有一次己方主动治疗实际回血或主动护盾实际增加。'),
}
MOVE_ID = r'[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+'
GEAR_ID = r'EQ-[0-9]{1,12}'
GEAR_SLOTS = ('weapon', 'armor')
SUMMON_ID = r'P06-ST104-[0-9]{1,8}'
BATCH_ID = r'CAP-[0-9]{4,10}'
SEARCH_ACTIONS = {('investigate', 'inspect', 'tracks'), ('investigate', 'inspect', 'marker'),
                  ('investigate', 'return', 'CONFIRM')}
ADO_MOVES = {'MG01-A', 'MG01-B', 'MG01-C'}
INFANTRY_MOVES = {'S02-A', 'S03-A', 'M02-A', 'M03-A', 'M04-A'}
HERO_MOVES = {
    'H01-A', 'H01-B', 'H02-A', 'H02-B', 'H03-A', 'H03-B',
    'H04-A', 'H04-B', 'H05-A', 'H05-B', 'H06-A', 'H06-B',
    'CMD-A', 'CMD-B', 'H08-A', 'H08-B',
    'H09-A', 'H09-B', 'H10-A', 'H10-B', 'H11-A', 'H11-B',
    'H12-A', 'H12-B',
}
ECHO_MOVE = 'EN06-A'
STING_MOVE = 'EN03-A'
ENEMY_SPEAR = 'EN17-A'
BONE_ARROW = 'EN22-A'
BONE_GUARD = 'EN21-A'
DUAL_SAC_ROOT = 'EL02-A'
ENEMY_MOVES = {ECHO_MOVE, STING_MOVE, ENEMY_SPEAR, BONE_ARROW, BONE_GUARD, DUAL_SAC_ROOT}
ORDINARY_ROUTES = {f'R{number:02}' for number in range(1, 10)}
HUNT_GENERALS = ('MG01', 'MG02', 'MG03', 'MG04')
FINALE_IDENTITY_ACTIONS = {('choice', 'KEEP_SELF'), ('choice', 'ACCEPT_MERGER'), ('merge', 'CONFIRM'), ('cancel',)}
FINALE_AGLA_ACTIONS = {('seal',), ('seal', 'CONFIRM'), ('carry', 'CONFIRM')}
FINALE_FIXED_ACTIONS = FINALE_IDENTITY_ACTIONS | FINALE_AGLA_ACTIONS | {
    ('prepare', 'CONFIRM'), ('enter', 'CONFIRM'), ('fight', 'CONFIRM'),
}
FINALE_COORDINATE = r'-?[0-9]{1,2}'
LATER_EVIDENCE_GENERALS = ('MG03', 'MG04')
QUEST_ACTIONS = {('commission', 'CONFIRM'), ('review', 'CONFIRM'), ('archive', 'CONFIRM'),
                 *((general, *step) for general in HUNT_GENERALS
                   for step in (('record',), ('witness',), ('collect', 'CONFIRM'))),
                 *(('report', general, 'CONFIRM') for general in HUNT_GENERALS)}
SITES = {'I', 'A', 'B', 'B1', 'B2', 'B_SUPPORT', 'B_MATERIAL', 'C', 'D', 'U', 'V', 'W',
         'T', 'S', 'L', 'G', 'X'}
STANCES = {'advance': '推进', 'hold': '固守', 'flank': '包抄', 'evade': '避险'}
UNIT_NAMES = {'S01': '盾兵', 'S02': '近战兵', 'S03': '弓兵',
              'M01': '护运枪卫', 'M02': '野战药师', 'M03': '弩机匠', 'M04': '雾术师'}
TUTORIAL_BATTLES = ('INTRO-EN01', 'TUT01-ROOT')
TUTORIAL_PLANS = ('PL01', 'PL02', 'PL05')
PLAN_ID = r'PL\d{2}'
MEMORY = {(choice, f'{general}-W{number}') for general in HUNT_GENERALS
          for number, choices in ((1, ('evidence', 'skip')), (2, ('retain', 'skip'))) for choice in choices}
FIXED_ACTIONS = {
    'choose': {('BOOK',), ('PRIMARY',), ('SECONDARY',), ('RUSH',)},
    'agla': {('craft', 'CONFIRM')},
    'event': {('EV07', 'receive', 'CONFIRM'), ('EV07', 'return', 'CONFIRM'),
              *(('EV07', 'trade', f'EF{number:02}', 'CONFIRM') for number in range(1, 9))},
    'route': {(route,) for route in ORDINARY_ROUTES},
    'challenge': {(general,) for general in (*HUNT_GENERALS, 'cancel')},
    'next': {(region, 'CONFIRM') for region in ('RG01', 'RG02', 'RG03', 'RG04', 'RG05', 'RG06', 'RG07', 'RG08')},
    'memory': MEMORY, 'remember': MEMORY | {(general,) for general in HUNT_GENERALS} | {('close',)},
    'dialogue': {('next',), ('skip',)}, 'buy_supply': {('1',)},
    'pack_medical': {(str(n),) for n in range(4)},
    'recruit': {(unit,) for unit in ('M01', 'M02', 'M03', 'M04')},
    **{command: {('CONFIRM',)} for command in ('return', 'flee', 'depart', 'rest', 'maintain')},
    **{command: {()} for command in ('fight', 'step', 'retreat', 'town', 'station', 'camp', 'medical')},
}
TUTORIAL = {('recommend', 'CONFIRM'), ('start',), ('start', 'CONFIRM'), ('observe',), ('materials',),
            ('materials', 'CLAIM'), ('materials', 'PASS')}


def valid_tutorial(args):
    if tuple(args) in TUTORIAL:
        return True
    if len(args) != 2:
        return False
    key, value = args
    return ((key == 'support' and bool(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value)))
            or (key == 'plan' and value in (*TUTORIAL_PLANS, 'PASS'))
            or (key == 'cache' and value in ('EF03', 'EF05', 'EF07', 'PASS')))


def valid_command(command, args):
    if command == 'tutorial':
        return valid_tutorial(args)
    if command == 'quest':
        return tuple(args) in QUEST_ACTIONS
    if command == 'supply':
        return len(args) == 2 and args[0] == 'commission' and args[1] in (*MATERIAL_GOALS, 'off')
    if command == 'craft':
        return len(args) == 1 and args[0] in CONSUMABLE_CODES[:-2]
    if command in ('stash', 'take', 'discard'):
        return len(args) == 1 and args[0] in CONSUMABLE_CODES
    if command == 'use':
        if len(args) == 1:
            return args[0] in PARTY_CONSUMABLES
        return (len(args) == 2 and args[0] in CONSUMABLE_CODES[:-2]
                and len(args[1]) <= 256 and bool(re.fullmatch(CONSUMABLE_TARGETS, args[1])))
    if command == 'finale':
        if tuple(args) in FINALE_FIXED_ACTIONS:
            return True
        if len(args) < 3 or not re.fullmatch(MEMBER_ID, args[1]):
            return False
        if args[0] == 'deploy':
            return len(args) == 3 and args[2] in ('on', 'off')
        return len(args) == 4 and args[0] == 'place' and all(re.fullmatch(FINALE_COORDINATE, value) for value in args[2:])
    if command == 'research':
        return (tuple(args) in {('analyze', 'CONFIRM'), ('test', 'CONFIRM'), ('deliver', 'CONFIRM')}
                or (len(args) == 3 and args[0] == 'correlate'
                    and bool(re.fullmatch(MEMBER_ID, args[1])) and args[2] == 'CONFIRM'))
    if command == 'facility':
        if len(args) == 5:
            return (args[0] == 'build' and args[1] in BUILDING_EFFECTS
                    and (args[2] == '1' or (args[1] in MULTILEVEL_BUILDINGS and args[2] in ('2', '3')))
                    and bool(re.fullmatch(BUILD_ORDER_ID, args[3])) and args[4] == 'CONFIRM')
        return (len(args) == 3 and args[0] in CONSTRUCTION_ACTIONS and args[2] == 'CONFIRM'
                and 1 <= len(args[1]) <= 64 and all(c.isalnum() or c in '-_' for c in args[1]))
    if command == 'service':
        return (len(args) == 4 and args[0] == 'training' and bool(re.fullmatch(MEMBER_ID + ':1', args[1]))
                and bool(re.fullmatch(SERVICE_ORDER_ID, args[2])) and args[3] == 'CONFIRM')
    if command == 'outfit':
        if len(args) == 2 and args[0] == 'targets':
            return bool(re.fullmatch(OUTFIT_TARGETS, args[1]))
        return (len(args) == 5 and args[:2] == ['buy', 'defense'] and bool(re.fullmatch(OUTFIT_TARGETS, args[2]))
                and bool(re.fullmatch(SERVICE_ORDER_ID, args[3])) and args[4] == 'CONFIRM')
    if command == 'rescue':
        if tuple(args) in SEARCH_ACTIONS:
            return True
        return (len(args) in (2, 4) and args[-1] == 'CONFIRM' and bool(re.fullmatch(BATCH_ID, args[-2]))
                and args[:-2] in ([], ['investigate', 'start']))
    if command == 'event' and args[:2] == ['EV07', 'escort']:
        return len(args) == 4 and bool(re.fullmatch(MEMBER_ID, args[2])) and args[3] == 'CONFIRM'
    if command in FIXED_ACTIONS:
        return tuple(args) in FIXED_ACTIONS[command]
    if command == 'book':
        if args in (['claim'], ['drop']):
            return True
        if len(args) == 2 and args[0] == 'target':
            return args[1] == 'clear' or bool(re.fullmatch(BOOK_ID, args[1]))
        if len(args) == 3 and args[:2] == ['task', 'accept']:
            return args[2] in BOOK_RESEARCH
        if len(args) == 4 and args[0] == 'choice' and (args[1] in ('ST-104', 'ST-303') or args[1] in BOOK_RESEARCH):
            return bool(re.fullmatch(BOOK_ID, args[2])) and args[3] == 'CONFIRM'
        if len(args) < 3 or not re.fullmatch(MEMBER_ID, args[1]):
            return False
        items = args[2:]
        if args[0] in ('buy', 'learn'):
            return len(items) == 1 and bool(re.fullmatch(BOOK_ID, items[0]))
        if args[0] == 'equip':
            return items == ['clear'] or (1 <= len(items) <= 2 and len(set(items)) == len(items)
                                          and all(re.fullmatch(BOOK_ID, book) for book in items))
        if args[0] == 'queue':
            return (1 <= len(items) <= 18 and len(set(items)) == len(items)
                    and all(re.fullmatch(MOVE_ID, move) for move in items))
        if args[0] == 'auto':
            return len(items) == 2 and bool(re.fullmatch(MOVE_ID, items[0])) and items[1] in ('on', 'off')
        return args[0] == 'main' and len(items) == 1 and (
            items[0] in ('AUTO', 'BASIC') or bool(re.fullmatch(MOVE_ID, items[0])))
    if command == 'summon':
        return len(args) == 2 and bool(re.fullmatch(SUMMON_ID, args[0])) and args[1] == 'CONFIRM'
    if command == 'equip':
        return len(args) == 2 and bool(re.fullmatch(MEMBER_ID, args[0])) and bool(re.fullmatch(GEAR_ID, args[1]))
    if command == 'unequip':
        return len(args) == 2 and bool(re.fullmatch(MEMBER_ID, args[0])) and args[1] in GEAR_SLOTS
    if command in ('heal', 'level_up', 'care'):
        return len(args) == 1 and bool(re.fullmatch(MEMBER_ID, args[0]))
    if command in ('squad', 'stance'):
        values = STANCES if command == 'stance' else ('on', 'off')
        return len(args) == 2 and bool(re.fullmatch(MEMBER_ID, args[0])) and args[1] in values
    if command == 'plan':
        return args == ['clear'] or (1 <= len(args) <= 3 and len(set(args)) == len(args)
                                     and all(re.fullmatch(PLAN_ID, plan) for plan in args))
    if command in ('move', 'interact'):
        return len(args) == 1 and args[0] in SITES
    if command == 'deploy':
        return len(args) == 2 and args[1] in ('on', 'off')
    if command == 'place':
        return len(args) == 4 and all(re.fullmatch(r'-?\d{1,3}', x) for x in args[1:])
    if command == 'deploy_at':
        return (len(args) in (4, 5) and bool(re.fullmatch(MEMBER_ID, args[0]))
                and all(re.fullmatch(r'-?\d{1,3}', x) for x in args[1:3]) and args[3] in set('012345')
                and (len(args) == 4 or bool(re.fullmatch(MEMBER_ID, args[4]))))
    if command == 'walkto':
        return len(args) == 2 and all(re.fullmatch(r'-?\d{1,3}', x) for x in args)
    return False


def member_view(m):
    from campaign import NAMES
    from expedition_peril import deployable
    row = {key: m.get(key) for key in ('instance_id', 'unit_id', 'name', 'hp', 'deployed', 'position',
                                      'facing', 'injury_days', 'cost', 'level', 'xp', 'stance', 'erosion')}
    row['name'] = row['name'] or NAMES.get(row['unit_id'])
    row['display_name'] = row['name'] or member_label(row['unit_id'], row['instance_id'])
    row['max_hp'] = m['stats']['hp']
    row['deployable'] = deployable(m) and m['hp'] > 0 and m['erosion'] < 100
    row['equipment'] = [item['instance_id'] for item in m.get('gear_instances', [])]
    return row


def member_label(kind, instance_id):
    name = UNIT_NAMES.get(kind, '队员')
    suffix = instance_id.rsplit('-', 1)[-1]
    return f'{name} {suffix}'


def gear_name(catalog, template):
    return catalog.gear.get(template, {}).get('name', template)


def equipment_view(game):
    from balance_v062 import gear_modifiers, unit_cost
    import workshop
    state = game.s
    in_town = state['phase'] == 'TOWN'
    inventory = state['gear_storage' if in_town else 'gear_bag']
    members = state['party'] + state['home_roster'] if in_town else state['party']
    lock = (workshop.active(game) or {}).get('item_id')

    def item_view(item, owners):
        template = game.cat.gear[item['template_id']]
        by_cost = {}
        for owner in owners:
            cost = str(unit_cost(owner))
            if cost not in by_cost:
                by_cost[cost] = gear_modifiers(game.cat, item, owner)
        return {'id': item['instance_id'], 'name': template['name'], 'slot': item['slot'],
                'allowed': template['allowed_unit_ids'], 'locked': item['instance_id'] == lock,
                'stats': by_cost,
                'effects': [('负面·' if effect.get('negative') else '') + effect['name']
                            for effect in item['effects']]}

    return {'location': '仓库' if in_town else '行囊',
            'inventory': [item_view(item, game.cat.gear[item['template_id']]['allowed_unit_ids'])
                          for item in inventory],
            'worn': {member['instance_id']: [item_view(item, [member]) for item in member['gear_instances']]
                     for member in members if member['gear_instances']}}


def plan_view(game, plan_ids):
    from plan_offers import RULES
    return [dict(id=key, name=game.cat.plans[key]['name'], rule=RULES.get(key, '')) for key in plan_ids]


def tutorial_choice_notes(game, choices, party):
    skipped = {'plan': '已放弃登记方案', 'support': '已放弃护运站支援',
               'materials': '已放弃材料', 'cache': '已放弃装备'}
    notes = {}
    for action, row in choices.items():
        if row['choice'] == 'PASS':
            if action in skipped:
                notes[action] = skipped[action]
        elif action == 'plan':
            notes[action] = '已登记「' + game.cat.plans[row['choice']]['name'] + '」'
        elif action == 'support':
            shield = row.get('shield')
            notes[action] = '已登记护运站支援'
            if shield:
                name = next((member['display_name'] for member in party
                             if member['instance_id'] == shield['target']), '随行队员')
                notes[action] = f"已领取支援 · {name}获得一次 {shield['amount']} 点战前护盾"
        elif action == 'materials':
            notes[action] = '已领取材料 · 安全归城后入库'
        elif action == 'cache':
            item = next((item for item in game.s['gear_bag'] if item['instance_id'] == row.get('item')), None)
            template = item['template_id'] if item else row['choice'] + '-Q1'
            notes[action] = '已领取「' + gear_name(game.cat, template) + '」'
    return notes


def settlement_view(game):
    from book_catalog import BOOKS

    state = game.s
    summary = state.get('summary')
    if summary is None:
        return None
    ids = {member for key in ('missing_ids', 'captured_ids', 'rescued_ids') for member in summary.get(key, [])}
    people = {}
    if ids:
        for roster in ('party', 'home_roster', 'captives', 'memorial', 'escorted'):
            for member in state.get(roster, []):
                if member['instance_id'] in ids:
                    people[member['instance_id']] = member_view(member)['display_name']
    equipment = [gear_name(game.cat, item['template_id']) for item in summary.get('returned_loose_equipment', [])]
    settlement = summary.get('settlement_id')
    expired = [member_view(member)['display_name'] for member in state['memorial']
               if settlement and member['capture']['settlement_id'] == settlement]
    lost = summary.get('lost_cargo') or {}
    receipt = summary.get('book_rewards') or {}
    trip = state['book_rewards']['departures'].get(str(receipt.get('expedition'))) or {}
    target = trip.get('contract', {}).get('target')
    progress = ({'name': BOOKS[target]['name'], 'before': receipt['progress_before'], 'after': receipt['progress_after'],
                 'target_banked': receipt['safe'] and target in receipt['books'],
                 'target_lost': not receipt['safe'] and target in receipt['books']}
                if target and receipt.get('books') else {})
    research = []
    counts = Counter(key for key, _ in receipt.get('task_battles', []))
    for key, count in counts.items():
        entitlement = state['book_rewards']['entitlements'].get(key)
        research.append({'name': BOOK_RESEARCH[key][0], 'count': count, 'banked': receipt['safe'],
                         'reward_ready': bool(entitlement and not entitlement['selected'])})
    return {**summary, 'member_labels': people, 'returned_gear_names': equipment, 'expired_rescue_names': expired,
            'banked_book_names': book_names(summary.get('books_banked', {})),
            'lost_book_names': book_names(summary.get('books_lost', {})),
            'book_target_progress': progress,
            'book_research_settlement': research,
            'lost_gear_names': [gear_name(game.cat, item['template_id']) for item in lost.get('gear', [])],
            'lost_consumable_names': [game.cat.items[item]['name'] for item in lost.get('consumables', [])],
            'returned_consumable_names': [game.cat.items[item]['name'] for item in summary.get('returned_consumables', [])]}


def book_names(counts):
    from book_catalog import BOOKS
    return {BOOKS[key]['name']: count for key, count in sorted(counts.items()) if count > 0}


def field_book_rewards(game):
    import book_rewards
    from book_catalog import BOOKS

    state = game.s
    trip = state['book_rewards']['departures'].get(str(state['expedition_no']))
    if not trip or trip['settled'] or state['phase'] not in ('EXPLORE', 'BATTLE'):
        return {}
    carried = Counter(row['book_id'] for row in trip['claims'] if row['status'] == 'CARRIED')
    offer = book_rewards.offer(game) if trip['pending_drop'] else None
    result = {'carried': book_names(carried), 'offer': dict(offer, book=book_info(offer['book_id'])) if offer else {}}
    if state['phase'] == 'EXPLORE':
        contract = trip['contract']
        result.update(used=len(trip['claims']), cap=contract['cap'])
        target = contract['target']
        if target:
            result['target'] = {'name': BOOKS[target]['name'], 'progress': contract['progress'],
                                'guaranteed': contract['replacement_enabled'] and not any(row['used_target'] for row in trip['claims']),
                                'carried': bool(carried[target])}
    return result


FIELD_EVENT_CHOICES = {'EV40': frozenset(('PRIMARY', 'SECONDARY')), 'EV59': frozenset(('RUSH',))}


def field_event_choice(game, event_id, option, binding, material_room):
    key = option['option_id']
    if event_id == 'EV40' and key in ('PRIMARY', 'SECONDARY'):
        candidate = next((effect['candidate_encounter_id'] for effect in option['effects']
                          if effect['type'] == 'commit_prelocked_encounter_variant'), None)
        encounters = game.manifest_region['encounters'].get('B1', {}).get('candidate_ids', ())
        if 'B1' in game.current['revealed_battles']:
            blocker = '前方巡队已经揭示，不能更换。'
        elif candidate not in encounters:
            blocker = '本趟未锁定这支巡队。'
        else:
            blocker = ''
        confirmation = f"{option['label']}。这将锁定前方的巡队，本现场只能选择一次。"
    elif event_id == 'EV59' and key == 'RUSH':
        from event_conditions import SPECS

        material_cost, claim_cost = 2, 1
        effect = SPECS[key]
        state = game.s
        claims = state['manifest']['caps'].get('event_found_consumable_claims', 0)
        free_claims = claims - state['debits'].get('event_found_consumable_claims', 0)
        if len(state['pouch']) + state['used_prep_slots'] >= 4:
            blocker = '携行袋已满，领取成品需要 1 个空位。'
        elif material_room < material_cost:
            blocker = f'本趟可用材料额度不足 {material_cost}。'
        elif free_claims < claim_cost:
            blocker = '本趟拾获成品额度已用完。'
        else:
            blocker = ''
        name = game.cat.items['CO12']['name']
        confirmation = (f'领取 1 份{name}，占 1 个携行格。'
                        f'消耗本趟材料额度 {material_cost}、拾获成品额度 {claim_cost}。\n'
                        f'在随身道具中使用后，接下来最多 {effect["battles"]} 场完整战斗中，'
                        f'实际出战者直接伤害 +{effect["positive"]["direct_damage_increase"]:.0%}，'
                        f'承伤 +{effect["negative"]["incoming_increase"]:.0%}。')
    else:
        return None
    if key not in binding['enabled_options']:
        blocker = binding['disabled_options'].get(key) or '本趟远征清单未开放该选项。'
    return {'id': key, 'label': option['label'], 'confirmation': confirmation,
            'blocker': blocker, 'allowed': not blocker}


def handbook_event_view(game):
    import book_rewards
    import water

    state = game.s
    if state['phase'] != 'EXPLORE' or state['mission'] != 'ORDINARY':
        return {}
    binding = game.manifest_region['events'].get(state['site'], {})
    source = binding.get('book_offer')
    fixed = binding.get('material_commission') or {}
    has_site_choices = binding.get('event_id') in FIELD_EVENT_CHOICES
    if not source and not fixed and not has_site_choices:
        return {}
    event, binding, visit = game.event_info()
    result = {'name': event['name'], 'description': event['scene']}
    if visit['state'] in ('RESOLVED', 'DECLINED'):
        receipt = visit.get('receipt') or {}
        choice = receipt.get('option')
        result['resolved'] = (book_info(receipt['book_id'])['name'] if choice == 'BOOK' else
                              next((option['label'] for option in event['options']
                                    if option['option_id'] == choice), '已处理'))
        return result
    offer = book_rewards.offer(game, source['source_key']) if source else None
    if not offer and not fixed and not has_site_choices:
        return {}
    caps = state['manifest']['caps']
    debits = state['debits']
    material_room = caps['material_units'] - debits.get('material_units', 0) - water.reserved(game)
    gear_room = caps['gear_claims'] - debits.get('gear_claims', 0)
    choices = []
    for option in event['options']:
        key = option['option_id']
        site_choice = field_event_choice(game, event['event_id'], option, binding, material_room) if has_site_choices else None
        if site_choice:
            choices.append(site_choice)
            continue
        if key not in binding['enabled_options'] or (key,) not in FIXED_ACTIONS['choose']:
            continue
        if not offer and key not in fixed.get('options', ()):
            continue
        effects = option['effects']
        grants = [effect['bundle_id'] for effect in effects if effect['type'] == 'claim_reward']
        if len(grants) != 1 or grants[0] not in ('RB-MAT2', 'RB-GEAR') or any(option['costs'].values()) \
                or any(effect['type'] not in ('claim_reward', 'erosion') for effect in effects):
            continue
        bundle_id = grants[0]
        bundle = game.cat.bundles[bundle_id]
        row = {'id': key, 'label': option['label'],
               'erosion': sum(effect['amount'] for effect in effects if effect['type'] == 'erosion')}
        if bundle_id == 'RB-MAT2':
            row.update(kind='materials', units=bundle['effect']['units'],
                       allowed=material_room >= bundle['budget_debits']['material_units'],
                       fixed=fixed['materials'] if key in fixed.get('options', []) else {})
        else:
            row.update(kind='gear', allowed=gear_room >= bundle['budget_debits']['gear_claims'])
        choices.append(row)
    result['choices'] = choices
    if offer:
        result.update(book=book_info(offer['book_id']), can_claim=offer['can_claim'], remaining_books=offer['remaining_cap'])
    return result


def ev07_view(game):
    import cases
    import equipment_rolls
    import escort
    import refugee

    eid = 'EV07'
    state = game.s
    case = state.get('cases', {}).get(eid)
    if not case or not case['enabled'] or not case['encountered']:
        return {}
    phase = state['phase']
    site = state['site']
    field = phase == 'EXPLORE'
    binding = game.manifest_region['events'].get(site, {}) if field else {}
    at_scene = binding.get('event_id') == eid
    pending = case.get('pending')
    receipt = case.get('receipt') or {}
    terminal = case['state'] in cases.TERMINAL
    current_settlement = (phase in ('RETURNED', 'FAILED') and
                          receipt.get('expedition_no') == state['expedition_no'])
    report = terminal and (phase == 'TOWN' or current_settlement)
    if not (at_scene or (field and pending) or report):
        return {}

    event = game.cat.events[eid]
    config = cases.CONFIG[eid]
    result = {'name': event['name'], 'subject': config['subject'], 'receiver': config['receiver'],
              'state': case['state'], 'at_scene': at_scene}
    if terminal:
        credit = case.get('trade_credit')
        result.update(receipt=receipt, custody=case['custody'], reward=case.get('reward_text', ''))
        if credit:
            result['credit'] = {'reward': event['story_trade']['reward_text'], 'redeemed': credit['redeemed'],
                                'waiting_reason': credit.get('waiting_reason', '')}
        return result

    if at_scene and not pending and game.current['events'][site]['state'] == 'DECLINED':
        return dict(result, blocker='本趟已明确放弃接手。')
    anchor = case['active_scene'] if pending else {'region': state['region'], 'site': site}
    try:
        path = refugee.clear_path(game, anchor)
    except ValueError as exc:
        result['blocker'] = str(exc)
    else:
        region = state['manifest']['regions'][anchor['region']]
        nodes = {node['id']: node['name'] for node in game.cat.layouts[region['template_id']]['nodes']}
        result['path'] = path
        result['path_names'] = [nodes[point] for point in path]

    preview = escort.preview(game)
    result['return_day'] = preview['settles_on']
    if pending:
        dispatch = next(row for row in state['escort_receipts'] if row['id'] == pending['escort_id'])
        leader = next(m for m in state['escorted'] if m['instance_id'] == dispatch['leader'])
        return dict(result, transit={'leader': member_view(leader)['display_name'], 'cost': dispatch['reserved_cost']})

    result['description'] = cases.scene_text(game, eid)
    humans = [m for m in state['party'] if not m['unit_id'].startswith('PET') and m['hp'] > 0
              and m['erosion'] < 100 and m['injury_days'] == 0]
    if len(humans) > 1:
        result['leaders'] = [member_view(m) for m in humans if m['instance_id'] in preview['leaders']]
        result['deployed'] = [member_view(m) for m in humans if m['deployed']]

    if case['state'] == 'OPEN' and 'EXPLOIT' in binding['enabled_options']:
        terms = event['story_trade']
        slots = equipment_rolls.public_quotes(game, eid)
        if len(slots) == 1:
            quality = terms['reward']['equipment']['quality']
            quotes = [dict(quote, name=gear_name(game.cat, quote['selection'] + '-' + quality))
                      for quote in slots[0] if (eid, 'trade', quote['selection'], 'CONFIRM') in FIXED_ACTIONS['event']]
            if quotes:
                result['trade'] = {'quotes': quotes,
                                   'warning': refugee.source_options(game, eid)['EXPLOIT']['confirmation_text']}
    return result


def deployment_error(game, board=None):
    try:
        game.validate_deployment(board)
    except ValueError as exc:
        return str(exc).split('：[[')[0].rstrip('。')
    return ''


def ordinary_routes_view(game):
    state = game.s
    facts = set(state['unlocked_facts'])
    profiles = game.cat.multi['profiles']
    rows = []
    for route in game.cat.config['routes']:
        route_id = route['route_id']
        if route_id not in ORDINARY_ROUTES or not facts.issuperset(route['facts']):
            continue
        profile = route['profile']
        path = [game.cat.regions[region]['name'] for region in route['selected_path']]
        rows.append({'id': route_id, 'start': path[0], 'target': path[-1], 'path': path,
                     'profile': profile, 'cost': profiles[profile]['departure_supply_cost'],
                     'selected': route_id == state['route']})
    return rows


def departure_cost(game):
    state = game.s
    if state.get('manifest'):
        return state['manifest']['departure_supply_cost']
    selected = next(route for route in game.cat.config['routes'] if route['route_id'] == state['route'])
    return game.cat.multi['profiles'][selected['profile']]['departure_supply_cost']


def route_view(game):
    import region_space as space
    layout = game.layout
    current = game.current
    state = game.s
    details = space.current(game)
    contact = details['contact']
    here = state['site']
    blocked = bool(contact and contact['site'] not in current['cleared'])
    neighbors = []
    nearby = []
    if state['phase'] == 'EXPLORE' and not blocked:
        neighbors = [b if here == a else a for a, b in layout['edges'] if here in (a, b)]
        nearby = [n for n in details['objects_seen']
                  if space.distance(details['position'], details['anchors'][n]) <= 2
                  and space.sight(details, details['position'], details['anchors'][n])]
    lit_cells = []
    if state['phase'] == 'EXPLORE':
        visible = space.visible(game)
        lit = {space.key(cell) for lamp in details['lamps'].values()
               if space.key(lamp['position']) in visible
               for cell in space.disk(lamp['position'], lamp['radius'])
               if space.sight(details, lamp['position'], cell)}
        lit_cells = [space.point(cell) for cell in sorted(lit & visible) if cell in details['ground']]
    exit_ready = here == 'X' and 'G' in current['cleared']
    can_heal = any(0 < m['hp'] < m['stats']['hp'] for m in state['party'])
    next_regions = game.next_regions() if exit_ready and state['mission'] != 'TUTORIAL' else []
    labels = {n['id']: n['name'] for n in layout['nodes']}
    encounter = game.manifest_region['encounters'].get(here) if blocked else None
    actions = dict.fromkeys(neighbors, 'move')
    if here is None:
        actions.update(dict.fromkeys(nearby, 'interact'))
    return {'neighbors': neighbors, 'nearby': nearby, 'map_actions': actions, 'contact_pending': blocked,
            'links': [edge for edge in layout['edges'] if all(x in details['objects_seen'] for x in edge)],
            'lit_cells': lit_cells,
            'safe_return': state['phase'] == 'EXPLORE' and (here == 'I' or exit_ready),
            'site_names': labels,
            'deployment_error': deployment_error(game, encounter['board_id']) if encounter else '',
            'next_regions': [{'id': key, 'name': game.cat.regions[key]['name']} for key in next_regions],
            'camp': bool(next_regions) and not current['camp_used'],
            'station': here == 'S' and not current['station_used'] and can_heal,
            'medical': can_heal and state['medical'] > 0 and not blocked,
            'cleared': current['cleared']}


def _save_version(ledger, primary):
    return max((row['response']['state_version'] for row in ledger['entries'].values()
                if row['status'] == 'COMMITTED' and row['response']['files']['save.json'] == primary
                and row['before']['files']['save.json'] != primary), default=0)


def record_impact(impacts, event):
    kind = event['type']
    if kind == 'hit':
        damage, absorbed = event['actual_hp_damage'], event['absorbed']
        if damage or absorbed:
            row = impacts.setdefault(event['target'], {})
            row['damage'] = row.get('damage', 0) + damage
            row['absorbed'] = row.get('absorbed', 0) + absorbed
    elif kind in ('heal', 'life_steal', 'town_nursing') and event['effective'] > 0:
        receiver = event['actor'] if kind == 'life_steal' else event['target']
        row = impacts.setdefault(receiver, {})
        row['healed'] = row.get('healed', 0) + event['effective']
    elif kind == 'down':
        impacts.setdefault(event['actor'], {})['down'] = True
    elif kind == 'cast_delayed':
        impacts.setdefault(event['target'], {})['delay_until'] = event['release_tick']
    elif kind == 'guard_redirect':
        impacts.setdefault(event['actor'], {})['ward'] = event['ward']
    elif kind == 'shared_shield' and event['amount'] > 0:
        row = impacts.setdefault(event['actor'], {})
        row['shared_shield'] = row.get('shared_shield', 0) + event['amount']
    elif kind == 'private_shield' and event.get('move') == BONE_GUARD and event['amount'] > 0:
        impacts.setdefault(event['actor'], {})['bone_guard'] = event['amount']


def bone_arrow_path(game, battle, archer, locked):
    from combat import cells, distance, visible

    terrain = cells(game.cat, battle)
    tick = battle['tick']
    occupants = {tuple(actor['pos']): actor for actor in sorted(battle['actors'], key=lambda a: a['id'])
                 if actor is not archer and (actor['hp'] > 0 or actor.get('downed_tick') == tick)}
    origin = archer['pos']
    card = next((move for move in archer.get('moves', ()) if move['move_id'] == BONE_ARROW), {})
    result = {'flight_stop': [], 'blocked_by': ''}
    opponents = 0
    for cell in locked:
        pos = tuple(cell)
        if (pos not in terrain or distance(origin, pos) > card.get('range', len(locked))
                or not visible(game.cat, terrain, origin, pos)):
            break
        result['flight_stop'] = cell
        actor = occupants.get(pos)
        if actor is None:
            continue
        if actor['side'] == archer['side']:
            result['blocked_by'] = actor['id']
            break
        opponents += 1
        if opponents >= card.get('max_targets', 2):
            break
    return result


def battle_view(game):
    from campaign import NAMES
    from book_combat import _private as private_shield

    state = game.s
    battle = state.get('battle')
    from_history = False
    if battle is None:
        reports = state['battle_reports']
        if not reports and state['phase'] == 'TOWN':
            reports = next((trip['battle_reports'] for trip in reversed(state['completed_history'])
                            if trip.get('battle_reports')), [])
            from_history = bool(reports)
        if not reports:
            return None
        battle = reports[-1]
    actors = battle['actors']
    by_id = {actor['id']: actor for actor in actors}
    tick = battle['tick']
    shared_by_member = {}
    for pool in battle.get('shared_shields', ()):
        if pool['amount'] > 0 and pool.get('starts', 1) <= tick <= pool['expires']:
            pool_view = {key: pool[key] for key in ('id', 'owner', 'amount', 'expires')}
            for member in pool['members']:
                shared_by_member.setdefault(member, []).append(pool_view)
    events = []
    impacts = {}
    locks = {}
    fields = ('event_id', 'tick', 'type', 'actor', 'target', 'position', 'action',
              'action_id', 'actual_hp_damage', 'absorbed', 'move', 'cells',
              'release_tick', 'cast_id', 'until', 'surface', 'phase', 'effective',
              'ward', 'attacker', 'members', 'amount', 'expires')
    for event in ([] if from_history else battle['events']):
        if event['type'] == 'windup' and (event.get('move') in ADO_MOVES or event.get('move') in INFANTRY_MOVES
                                           or event.get('move') in ENEMY_MOVES or event.get('move') in HERO_MOVES):
            locks[event['action_id']] = event
        if event.get('tick') != battle['tick']:
            continue
        name = event['type']
        bone_guard = name == 'private_shield' and by_id.get(event.get('actor'), {}).get('kind') == 'EN21'
        if bone_guard:
            event = {**event, 'move': BONE_GUARD}
        record_impact(impacts, event)
        spear = by_id.get(event.get('target' if name == 'hero_interrupt' else 'actor'), {}).get('kind') == 'M01'
        spear_event = (spear and (name in ('hero_interrupt', 'hero_stun_cancel', 'movement_block')
                       or (event.get('move') == 'M01-A' and name in ('windup', 'release', 'skill_miss'))))
        en01_event = (by_id.get(event.get('actor'), {}).get('kind') == 'EN01'
                      and event.get('move') == 'EN01-A' and name == 'release')
        infantry_event = event.get('move') in INFANTRY_MOVES and name in ('windup', 'release', 'skill_miss')
        hero_event = event.get('move') in HERO_MOVES and name in ('windup', 'release', 'skill_miss')
        aid_heal = name == 'heal' and event.get('move') == 'M02-A'
        mist_delay = name == 'cast_delayed' and by_id.get(event.get('actor'), {}).get('kind') == 'M04'
        enemy_event = event.get('move') in ENEMY_MOVES and name in ('windup', 'release', 'skill_miss')
        ado_event = (by_id.get(event.get('actor'), {}).get('kind') == 'MG01'
                     and name in ('boss_phase', 'windup', 'release', 'skill_miss', 'boss_private_shield'))
        if name not in ('move', 'basic_start', 'hit', 'down', 'guard_redirect', 'shared_shield') and not (
                spear_event or en01_event or infantry_event or hero_event or ado_event or aid_heal or mist_delay or enemy_event or bone_guard):
            continue
        row = {key: event[key] for key in fields if key in event}
        if ado_event and name == 'release':
            windup = locks.get(event['action_id'], {})
            row['cells'] = windup.get('cells', [])
            row['facing'] = windup.get('facing')
        if (infantry_event or enemy_event or hero_event) and name == 'release':
            windup = locks.get(event['action_id'], {})
            row['target'] = windup.get('target')
            row['cells'] = windup.get('cells', [])
            if hero_event:
                row['facing'] = windup.get('facing')
            if event.get('move') == BONE_ARROW:
                row.update(bone_arrow_path(game, battle, by_id[event['actor']], row['cells']))
            if event.get('move') == DUAL_SAC_ROOT:
                row['facing'] = windup.get('facing')
        if event['type'] == 'hit':
            victim = by_id.get(event['target'], {})
            # Movement and facing resolve before hit in this tick. Use the
            # stored front/rear judgment and shield stance, never pooled reduction.
            row['front_guard'] = (victim.get('kind') == 'S01' and victim.get('stance') == 'hold'
                                  and victim.get('stationary', 0) > 0 and event.get('flank') is False)
        events.append(row)
    actor_rows = []
    ordinals = {'player': 0, 'enemy': 0}
    move_names = {'S02-A': '破隙近击', 'S03-A': '贯枝', 'M03-A': '破障铆射', 'M04-A': '雾绊'}
    for actor in actors:
        row = {key: actor.get(key) for key in ('id', 'kind', 'name', 'side', 'pos', 'hp', 'facing')}
        row['max_hp'] = actor['stats']['hp']
        if actor['hp'] > 0:
            own_shield = private_shield(actor, tick)
            if own_shield > 0:
                row['private_shield'] = own_shield
            if actor['id'] in shared_by_member:
                row['shared_protection'] = shared_by_member[actor['id']]
        side, kind = actor['side'], actor['kind']
        ordinals[side] += 1
        row['badge'] = f"{'我' if side == 'player' else '敌'}{ordinals[side]}"
        fallback = (UNIT_NAMES.get(kind) or NAMES.get(kind) if side == 'player'
                    else game.cat.enemy_templates.get(kind, {}).get('name'))
        row['display_name'] = (actor.get('name') if actor.get('name') != kind else None) or fallback or (
            '队员' if side == 'player' else '来敌')
        move_names.update({move['move_id']: move['name'] for move in actor.get('moves', [])
                           if move.get('move_id') and move.get('name')})
        pending = actor.get('pending') or {}
        if pending.get('move_id') == 'S02-A' and not battle.get('result'):
            row['melee_pending'] = {key: pending.get(key) for key in ('id', 'cells', 'facing')}
        if pending.get('move_id') in ('S03-A', 'M03-A') and not battle.get('result'):
            row['bow_pending'] = {key: pending.get(key) for key in ('id', 'cells', 'facing')}
        if pending.get('move_id') == 'M02-A' and not battle.get('result'):
            row['aid_pending'] = {key: pending.get(key) for key in ('id', 'target', 'cells', 'facing')}
        if pending.get('move_id') == 'M04-A' and not battle.get('result'):
            row['mist_pending'] = {key: pending.get(key) for key in ('id', 'target', 'cells', 'facing')}
        if pending.get('move_id') in HERO_MOVES and not battle.get('result'):
            row['hero_pending'] = {key: pending.get(key) for key in ('id', 'move_id', 'target', 'cells', 'facing')}
        if pending.get('move_id') in ('M01-A', ENEMY_SPEAR) and not battle.get('result'):
            row['spear_pending'] = {key: pending.get(key) for key in ('id', 'cells', 'origin', 'due')}
        if pending.get('move_id') == 'EN01-A' and not battle.get('result'):
            row['mimic_pending'] = pending['id']
        if kind == 'EL02' and actor['hp'] > 0 and not battle.get('result'):
            if pending.get('move_id') == DUAL_SAC_ROOT:
                row['dual_sac_pending'] = {key: pending[key] for key in ('id', 'facing', 'axis_offset') if key in pending}
            if tick > 0 and actor.get('root_until', 0) >= tick:
                row['dual_sac_rooted'] = True
        if pending.get('move_id') == ECHO_MOVE and not battle.get('result'):
            row['echo_pending'] = {key: pending.get(key) for key in ('id', 'cells', 'due')}
        if pending.get('move_id') == STING_MOVE and not battle.get('result'):
            row['sting_pending'] = {key: pending.get(key) for key in ('id', 'cells', 'due')}
        if kind == 'EN04' and actor['hp'] > 0 and not battle.get('result'):
            row['guard_active'] = any(pool['owner'] == actor['id'] and pool['amount'] > 0
                                      and pool['expires'] >= battle['tick'] and actor['id'] in pool['members']
                                      for pool in battle.get('shared_shields', ()))
        if kind == 'EN21' and actor['hp'] > 0 and not battle.get('result'):
            row['guard_active'] = any(shield['effect'] == BONE_GUARD and shield['amount'] > 0
                                      and shield['expires'] >= battle['tick'] for shield in actor['timed_shields'])
        if pending.get('move_id') == BONE_ARROW and not battle.get('result'):
            row['bone_pending'] = {key: pending.get(key) for key in ('id', 'cells', 'origin', 'due', 'facing')}
        if actor.get('town_defense_bonus', 0) > 0:
            row['town_defense_bonus'] = actor['town_defense_bonus']
        if kind in HUNT_GENERALS:
            row['boss_phase'] = actor['boss_phase']
        if kind == 'MG01':
            row['memory_pose'] = bool(battle['boss_dialogue_queue'])
            if pending.get('move_id') in ADO_MOVES and not battle.get('result'):
                row['boss_pending'] = {key: pending.get(key) for key in ('move_id', 'id', 'facing')}
            row['boss_barrier'] = sum(p['amount'] for p in actor['timed_shields']
                                      if p['effect'] == 'MG01-B' and p['expires'] >= battle['tick'])
        actor_rows.append(row)
    return {
        'id': battle['battle_id'],
        'encounter': battle['encounter_id'],
        'finished': battle.get('result') is not None,
        'result': battle.get('result'),
        'tick': battle['tick'],
        'plan_names': [game.cat.plans[key]['name'] for key in battle.get('plans', ())],
        'actors': actor_rows,
        'events': events,
        'impacts': impacts,
        'memory_reply': memory_reply(game, battle) if not from_history else {},
        'move_names': move_names,
        'recent': combat_notes(battle['events'], by_id),
    }


def combat_notes(events, by_id):
    """A bounded view of persisted combat events for the HUD and post-battle review."""
    notes = []
    last_hit = None
    for event in reversed(events):
        kind = event['type']
        if kind == 'hit' and last_hit is None:
            last_hit = event
        bone_guard = kind == 'private_shield' and by_id.get(event['actor'], {}).get('kind') == 'EN21'
        if ((not bone_guard and kind not in ('release', 'heal', 'down', 'boss_phase', 'boss_private_shield', 'skill_miss',
                                           'boss_memory_choice', 'cast_delayed', 'guard_redirect', 'shared_shield'))
                or (kind == 'release' and (not event.get('move') or event['move'] == 'BASIC'))
                or (kind == 'heal' and not event['effective'])):
            continue
        notes.append(event)
        if len(notes) >= 8:
            break
    fields = ('id', 'event_id', 'tick', 'type', 'actor', 'target', 'move', 'phase', 'amount',
              'actual_hp_damage', 'absorbed', 'effective', 'release_tick', 'ward', 'members', 'expires')
    return [{key: event[key] for key in fields if key in event}
            for event in (notes or ([last_hit] if last_hit is not None else []))]


def memory_actor(battle, general):
    return next(actor for actor in battle['actors'] if actor['kind'] == general)


def memory_lines(card, speaker):
    if card['window_id'].endswith('-W1'):
        return [{'speaker': speaker, 'text': card['question']},
                {'speaker': '指挥官', 'text': card['evidence_reply']}]
    return [{'speaker': '指挥官', 'text': card['player_reply']},
            {'speaker': speaker, 'text': card['general_reply']}]


def hunt_general(game, general_id):
    return next(row for row in game.cat.rules['generals'] if row['general_id'] == general_id)


def memory_reply(game, battle):
    # Closing a memory window can settle the battle and append a result at the same tick.
    event = next((entry for entry in reversed((battle or {}).get('events', [])[-2:])
                  if entry['type'] != 'result'), {})
    if event.get('type') != 'boss_memory_choice' or event['choice'] == 'skip' or event['boss'] not in HUNT_GENERALS:
        return {}
    actor = memory_actor(battle, event['boss'])
    card = next(row for row in actor['awakening']['dialogue_windows'] if row['window_id'] == event['window'])
    speaker = hunt_general(game, event['boss'])['human_name']
    return {'id': event['window'], 'line': memory_lines(card, speaker)[1]}


def memory_records(game, battle, general_id):
    if battle is None:
        return []
    actor = memory_actor(battle, general_id)
    progress = battle['boss_memory'][general_id]
    speaker = hunt_general(game, general_id)['human_name']
    records = []
    for card in actor['awakening']['dialogue_windows']:
        window = card['window_id']
        committed = window in progress['committed']
        records.append({'id': window, 'committed': committed, 'skipped': window in progress['skipped'],
                        'lines': memory_lines(card, speaker) if committed else []})
    return records


def memory_view(game, battle):
    from campaign import QUESTS
    queue = (battle or {}).get('boss_dialogue_queue', [])
    if not queue or queue[0]['boss'] not in HUNT_GENERALS:
        return {}
    general, window = queue[0]['boss'], queue[0]['window']
    actor = memory_actor(battle, general)
    card = next(row for row in actor['awakening']['dialogue_windows'] if row['window_id'] == window)
    progress = battle['boss_memory'][general]
    first = window.endswith('-W1')
    enabled = progress['eligible'] and (first or card['requires_prior_window'] in progress['committed'])
    speaker = hunt_general(game, general)['human_name']
    return {'id': window, 'number': 1 if first else 2, 'choice': 'evidence' if first else 'retain',
            'lead': memory_lines(card, speaker)[0] if enabled else {}, 'enabled': enabled,
            'general_id': general, 'general': speaker, 'item': QUESTS[general]['item']}


def hunt_view(game, general_id, town_memory):
    from campaign import QUESTS
    from book_catalog import BOOKS
    from book_rewards import BOSS_BOOKS
    state = game.s
    campaign = state['campaign']
    facts = campaign['facts']
    general = hunt_general(game, general_id)
    route = next(row for row in game.cat.config['routes'] if row['route_id'] == 'HUNT-' + general_id)
    if route['gate'] not in facts:
        return {}
    delivery_id = general['defeat_fact']
    book = BOSS_BOOKS[delivery_id]
    victory = facts.get(general_id + '_DEFEATED')
    returned = campaign['returned_reports'].get(general_id)
    delivered = facts.get(delivery_id)
    settlement = state.get('summary') or {}
    row = {'id': general_id, 'name': general['human_name'], 'region': general['region_id'],
           'route': [game.cat.regions[region]['name'] for region in route['selected_path']],
           'selected': campaign['challenge'] == general_id,
           'defeated': general_id in campaign['victories'], 'report_ready': returned is not None,
           'victory_day': victory['day'] if victory else None,
           'report_return_day': returned['day'] if returned else None,
           'report_delivery_day': delivered['day'] if delivered else None,
           'report_this_return': bool(returned and settlement.get('settlement_id') == returned['settlement_id']),
           'report_pending_return': bool(victory and not returned and not state['debug_tainted']),
           'reported': delivered is not None, 'awakened': general_id + '_AWAKENED' in facts,
           'report_book': {'id': book, 'name': BOOKS[book]['name'], 'count': state['book_stock'].get(book, 0)},
           'report_seals': game.cat.rules['recruitment']['milestone_seals'].get(delivery_id, 0)}
    last_battle = campaign['victories'].get(general_id, {}).get('battle')
    has_item = 'OBS-' + general_id in campaign['task_items']
    has_testimony = general_id in campaign['testimonies']
    in_town = state['phase'] == 'TOWN'
    row.update(item=QUESTS[general_id]['item'], has_item=has_item, has_testimony=has_testimony,
               evidence=has_item and has_testimony,
               memory_records=memory_records(game, last_battle, general_id) if in_town else [],
               memory_reply=memory_reply(game, last_battle) if in_town else {},
               memory=town_memory if town_memory.get('general_id') == general_id else {})
    if general_id == 'MG01':
        row['has_whistle'] = has_item
    return row


def whistle_cue(state):
    campaign = state['campaign']
    victory = campaign['victories'].get('MG01', {})
    battle = state.get('battle') or victory.get('battle') or {}
    return next((e['event_id'] for e in reversed(battle.get('events', []))
                 if e['type'] == 'boss_memory_choice' and e.get('window') == 'MG01-W1'
                 and e.get('choice') == 'evidence'), '')


def construction_view(game):
    import construction
    import facilities

    state = game.s
    funds = {key: state['bank'][key] for key in ('copper', 'crystal')}
    orders = facilities.orders(game)
    active = {row['building']: row for row in orders if row['status'] == 'ACTIVE'}
    occupied, workers = facilities.occupied(game), facilities.workers(game)
    can_start = facilities.can_start(game)
    can_pause = facilities.level(game, 'council') > 0 and not any(row.get('paused') for row in active.values())
    used_ids = {row['id'] for row in orders}
    serial = len(used_ids) + 1
    while (order_id := f'P06-BLD-{serial:04d}') in used_ids:
        serial += 1

    projects = []
    for key, effect in BUILDING_EFFECTS.items():
        level = facilities.level(game, key)
        project = {'key': key, 'name': facilities.NAMES[key], 'level': level, 'effect': effect}
        order = active.get(key)
        if order:
            paused = order.get('paused', False)
            rush = facilities.pending_rush(game, order['id'])
            project['order'] = {
                'id': order['id'], 'target': order['target_level'], 'progress': order['progress'],
                'required': order['required'], 'paused': paused, 'rush': rush,
                'refund': construction.refund(order),
                'pause': not rush and not paused and can_pause,
                'resume': not rush and paused and can_start,
            }
        elif key == 'hospital' and state['hospital_progress'] is not None:
            project['legacy_remaining'] = state['hospital_progress']
        elif level == 0 or (key in MULTILEVEL_BUILDINGS and level < 3):
            target = level + 1
            cost, required = facilities.build_cost(game, key, target)
            gate_blocker = ''
            if key == 'armory':
                unmet = [name for name, ready in construction.conditions(game, target) if not ready]
                if unmet:
                    gate_blocker = ('交存首章调查与旧名册后开放' if target == 1
                                    else '建设前置：' + '、'.join(unmet))
            elif not facilities.gate(game, key, target):
                gate_blocker = '交齐前两将讨伐报告后开放' if target == 3 else '交存首章调查与旧名册后开放'
            if gate_blocker:
                blocker = gate_blocker
            elif not can_start:
                blocker = '施工位已占用'
            elif any(funds[resource] < amount for resource, amount in cost.items()):
                blocker = '库存铜或公共结晶不足'
            else:
                blocker = ''
            project['quote'] = {'target': target, 'paid': cost, 'required': required, 'blocker': blocker}
        projects.append(project)
    return {'funds': funds, 'occupied': occupied, 'workers': workers, 'order_id': order_id, 'projects': projects}


def agla_view(game):
    import research

    state = game.s
    assembly = state['research']['assembly']
    recipe = game.cat.loot['agla_recipe']
    result = {'name': research.name(game, 'KEY-AGLA'), 'assembly': assembly or {}}
    if assembly:
        return result

    costs = dict(recipe['materials'], copper=recipe['copper'])
    funds = {key: state['warehouse'].get(key, 0) for key in recipe['materials']}
    funds['copper'] = state['bank']['copper']
    missing = research.missing(game)
    material_labels = {'crystal_shard': '晶屑', 'iron': '铁料'}
    labels = []
    for row in missing:
        if row[:4] in HUNT_GENERALS and '觉醒' in row:
            labels.append(hunt_general(game, row[:4])['human_name'] + '尚未觉醒')
        else:
            for code, label in material_labels.items():
                row = row.replace(code, label)
            labels.append(row)
    if state['debug_tainted']:
        labels.append('调试存档无法正式制造。')
    result.update(cost=costs, funds=funds, missing=labels,
                  needs_workshop='工坊Lv3' in missing,
                  needs_materials=any(funds[key] < amount for key, amount in recipe['materials'].items()),
                  needs_memories=any(row[:4] in HUNT_GENERALS for row in missing))
    return result


def campaign_research_view(game, party):
    import facilities
    import research

    state = game.s
    record = state['research']
    steps = record['steps']
    if 'archive' not in steps:
        return {}
    campaign = state['campaign']
    facts = campaign['facts']
    level = facilities.level(game, 'lamp_store')
    fragments = [research.name(game, key) for key in research.FRAGMENTS if key in campaign['task_items']]
    view = {'level': level, 'fragments': fragments,
            'delivered': bool(record['delivery']), 'required_level': 0, 'action': '', 'blocker': ''}
    if record['delivery']:
        entitlement = state['book_rewards']['entitlements'].get('ST-303') or {}
        selected = entitlement.get('selected')
        view['reward'] = {'selected': book_info(selected) if selected else {},
                          'choices': [book_info(book) for book in entitlement.get('allowed', [])] if not selected else []}
        view['agla'] = agla_view(game)
        return view

    if 'analysis' not in steps:
        view.update(action='analyze', required_level=2)
    elif 'correlation' not in steps:
        view.update(action='correlate', required_level=3,
                    members=[{'id': member['instance_id'], 'name': member['display_name']}
                             for member in party if member['unit_id'] != 'PET-H04'])
    elif 'isolation' not in steps:
        view.update(action='test', required_level=3)
    else:
        view.update(action='deliver', required_level=3)
    if state['debug_tainted']:
        view['blocker'] = '调试存档无法交付正式研究。'
    elif view['required_level'] == 3 and 'CH2_COMPLETE' not in facts:
        view['blocker'] = '交存阿铎与赛芙的讨伐报告后继续研究。'
    elif level < view['required_level']:
        view['blocker'] = f"遗迹观测站升至 Lv{view['required_level']} 后继续。"
    elif view['action'] == 'correlate' and not view['members']:
        view['blocker'] = '请在队伍中安排一名队员后核对记录。'
    elif view['action'] == 'deliver' and ('CH3_BATTLES_COMPLETE' not in facts or 'RESEARCH_TASKS_COMPLETE' not in facts):
        report_facts = [row['defeat_fact'] for row in game.cat.rules['generals']]
        count = sum(fact in facts for fact in report_facts)
        view['blocker'] = f'讨伐报告已交存 {count}/{len(report_facts)}，齐全后可交付研究。'
    return view


def preparation_view(game, members):
    import facilities
    from town import HEAL_HP_PER_COPPER
    state = game.s
    rules = game.cat.rules
    economy = rules['economy']
    levels = rules['level']
    for m in members:
        missing = m['max_hp'] - m['hp']
        m['heal_cost'] = math.ceil(missing / HEAL_HP_PER_COPPER) if missing > 0 else 0
        m['next_xp'] = levels['experience_per_step'][m['level'] - 1] if m['level'] < levels['maximum'] else 0
    archived = 'ST-104' in state['campaign']['facts']
    prepare = {
        'supply_price': economy['supply_copper'],
        'level_price': economy['level_copper'], 'care_scheduled': state['care_target'],
        'deployment_error': deployment_error(game, None if archived or state['capture_batches'] else 'OPEN'),
    }
    if archived or state['capture_batches']:
        prepare.update({
            'medical_cap': facilities.medical_cap(game),
            'recruits': [{'id': key, 'name': rules['mercenaries'][key].get('name', name)}
                         for key, name in (('M02', '野战药师'), ('M03', '弩机匠'), ('M04', '雾术师'))],
        })
    return prepare


def service_quote(game, paid, extra):
    return {'paid': paid, 'extra': extra,
            'blocker': '库存资源不足' if any(game.s['bank'][key] < amount for key, amount in paid.items()) else ''}


def town_services_view(game):
    import facilities
    import outfitting

    state = game.s
    training_level = facilities.level(game, 'barracks')
    workshop_level = facilities.level(game, 'armory')
    if not training_level and not workshop_level:
        return {}
    orders = state['town_services']
    serial = len(orders) + 1
    while (order_id := f'P06-SVC-{serial:04d}') in orders:
        serial += 1
    names = {m['instance_id']: member_view(m)['display_name'] for m in state['party'] + state['home_roster']}
    view = {'used': len(outfitting.today(game)), 'order_id': order_id, 'day_due': state['day'] + 1,
            'funds': {key: state['bank'][key] for key in ('copper', 'crystal', 'supply')},
            'defense': {}, 'training': {}}
    if training_level:
        training = {'options': [], 'pending': [], 'settled': []}
        veterans = facilities.state(game)['veterans']
        for member in state['home_roster']:
            iid = member['instance_id']
            if iid not in veterans:
                continue
            option = {'id': iid, 'name': names[iid], 'level': member['level'], 'xp': member['xp']}
            try:
                quote = literal_eval(facilities.service(game, ['quote', 'training', iid + ':1']))
            except ValueError as error:
                option['blocker'] = str(error)
            else:
                option.update(service_quote(game, quote['total_cost'], quote['second_service_extra']))
                option['cap'] = quote['effect']['cap']
            training['options'].append(option)
        for row in facilities.state(game)['services'].values():
            if row['kind'] != 'training':
                continue
            status = 'pending' if row['status'] == 'READY' else 'settled'
            if status == 'settled' and row['settlement'] != state['last_settlement_id']:
                continue
            training[status].extend({'id': iid, 'name': names.get(iid, iid), 'xp': amount}
                                    for iid, amount in row['targets'].items())
        view['training'] = training
    if workshop_level:
        order = outfitting.active(game)
        spec = order['spec'] if order else outfitting.specification(workshop_level, state['workshop_branch'], 'defense')
        defense = {'spec': spec, 'targets': [], 'ready': bool(order), 'options': [
            {'id': member['instance_id'], 'name': names[member['instance_id']], 'deployed': member['deployed']}
            for member in state['party'] if member['hp'] > 0 and member['injury_days'] == 0]}
        if order:
            party_ids = {member['instance_id'] for member in state['party']}
            defense['targets'] = [{'id': iid, 'name': names.get(iid, iid), 'travels': iid in party_ids}
                                  for iid in order['targets']]
        else:
            try:
                paid, extra = outfitting.price(game, 'outfit', {'copper': 4, 'crystal': 1})
            except ValueError as error:
                defense['blocker'] = str(error)
            else:
                defense.update(service_quote(game, paid, extra))
        view['defense'] = defense
    return view


def consumable_effect(code, effect):
    kind = effect['type']
    if kind == 'heal_flat':
        return f"最多恢复 1 名站立队员 {effect['amount']} 生命。"
    if kind == 'heal_fraction':
        return f"最多 {effect['max_targets']} 名站立队员各恢复生命上限的 1/5。"
    if kind == 'next_battle_private_shield':
        return f"下次出战时获得 {effect['amount']} 点自身护盾，战后清除。"
    if kind == 'next_battle_stat_buff':
        label = {'physical_attack': '物理攻击', 'magic_attack': '魔法攻击', 'healing_power': '治疗强度',
                 'physical_defense': '物理防御', 'magic_defense': '魔法防御'}[effect['stat']]
        return f"下次出战时{label} +{effect['flat']}，持续 {effect['duration_ticks']} 拍。"
    if code == 'CO09':
        return '下次出战首次直接攻击增加暴击机会，未命中也会用掉准备。'
    if code == 'CO10':
        return '下次出战首次进入浅水时免除下一拍的移动停顿。'
    if code == 'CO11':
        return '接下来最多两场完整战斗中，实际出战者开场获得护片。'
    if code == 'CO12':
        return '接下来最多两场完整战斗中，实际出战者获得急磨效果。'
    return ''


def consumable_targets(game, people, effect):
    from gear_affixes import received_recovery

    kind = effect['type']
    targets = []
    for member in people:
        if member['hp'] <= 0:
            continue
        iid = member['instance_id']
        maximum_hp = member['stats']['hp']
        row = {'id': iid, 'name': member_view(member)['display_name'], 'hp': member['hp'], 'max_hp': maximum_hp}
        if kind in ('heal_flat', 'heal_fraction'):
            base = effect['amount'] if kind == 'heal_flat' else max(1, math.floor(maximum_hp * (effect['numerator'] / effect['denominator'])))
            maximum = received_recovery(member, base)
            row['heals'] = min(maximum, maximum_hp - member['hp'])
            if row['heals'] <= 0:
                continue
            row['overflow'] = maximum - row['heals']
        else:
            group = effect.get('buff_id', effect.get('effect_id', kind))
            ready = game.s['preparations'].get(iid, [])
            if any(p.get('buff_id', p.get('effect_id', p['type'])) == group for p in ready):
                continue
        targets.append(row)
    return targets


def consumables_view(game, town):
    import event_conditions

    state = game.s
    pouch = Counter(state['pouch'])
    stored = Counter(state['item_storage']) if town else {}
    slots = len(state['pouch']) + state['used_prep_slots']
    if not town and not pouch and not slots:
        return {}
    people = state['party'] + (state['home_roster'] if town else [])
    level = state['workshop_level'] if town else 0
    rows = []
    for code in CONSUMABLE_CODES:
        carried, owned = pouch[code], stored.get(code, 0)
        recipe = game.cat.recipes.get('RC-' + code) if town else None
        craftable = recipe and level >= recipe.get('requires_building_level', 1)
        if not carried and not owned and not craftable:
            continue
        item = game.cat.items[code]
        effect = item['effect']
        kind = effect['type']
        row = {'id': code, 'name': item['name'], 'effect': consumable_effect(code, effect),
               'carried': carried, 'stored': owned, 'target_cap': effect.get('max_targets', 0),
               'healing': kind in ('heal_flat', 'heal_fraction'), 'targets': [], 'use_blocker': ''}
        if craftable:
            costs = {'copper': recipe['copper'], **recipe['materials']}
            short = {key: amount - (state['bank']['copper'] if key == 'copper' else state['warehouse'].get(key, 0))
                     for key, amount in costs.items()}
            row['recipe'] = {'costs': costs, 'short': {key: amount for key, amount in short.items() if amount > 0}}
        if carried:
            if code in PARTY_CONSUMABLES:
                family = event_conditions.SPECS[event_conditions.ITEM_CHOICES[code]]['family']
                if any(r['family'] == family for r in event_conditions._active(game)):
                    row['use_blocker'] = '同族准备已生效或待生效。'
                elif not town and event_conditions._item_future(game) <= 0:
                    row['use_blocker'] = '本趟已没有后续战斗。'
            else:
                row['targets'] = consumable_targets(game, people, effect)
                if not row['targets']:
                    row['use_blocker'] = '当前无人可有效治疗。' if row['healing'] else '无可用目标，同组准备不能叠加。'
        rows.append(row)
    return {'items': rows, 'slots': slots, 'reserved': state['used_prep_slots'], 'workshop': level}


def material_goal_view(game, town):
    state = game.s
    if town:
        options = []
        for spec in game.cat.loot['fixed_material_commissions']:
            gate = 'ST-104' if spec['unlock'] == 'CH2_available' else spec['unlock']
            if gate in state['unlocked_facts']:
                options.append({'id': spec['mission_id'], 'materials': spec['reward_materials'],
                                'regions': [game.cat.regions[key]['name'] for key in spec['region_ids']]})
        return {'current': state['material_commission'], 'options': options}
    target = (state.get('manifest') or {}).get('material_commission')
    if not target or state['mission'] != 'ORDINARY':
        return {}
    region, site = target['region'], target['site']
    binding = state['manifest']['regions'][region]['events'][site]['material_commission']
    scene = state['regions'].get(region, {}).get('events', {}).get(site, {})
    picked = (scene.get('receipt') or {}).get('option') in binding['options']
    return {'region': game.cat.regions[region]['name'], 'region_id': region, 'site': site,
            'materials': binding['materials'], 'picked': picked, 'closed': scene.get('state') in ('RESOLVED', 'DECLINED')}


def rescue_site_name(game, batch, manifest):
    region = ((manifest or {}).get('regions') or {}).get(batch['origin_region'], {})
    layout = game.cat.layouts.get(region.get('template_id'), {})
    site = batch['origin_site']
    return next((node['name'] for node in layout.get('nodes', ()) if node['id'] == site), site)


def rescue_view(game):
    import facilities
    import missing
    import rescue
    state = game.s
    search = missing.state(game)
    due = rescue.due_next(state)
    cost = facilities.rescue_cost(game)
    current = search['active']
    active = {'id': current['case_id'], 'returns_on': current['settles_on'],
              'due': current['other_due']} if current else {}
    target = dict(state['rescue_target'] or {})
    manifests = {}
    capture_manifests = {}
    for trip in (*state.get('completed_history', []), state):
        manifest = trip.get('manifest')
        if not manifest:
            continue
        if 'expedition_no' in trip:
            manifests[trip['expedition_no']] = manifest
        capture = (trip.get('summary') or {}).get('capture_batch') or {}
        if capture.get('id'):
            capture_manifests[capture['id']] = manifest
    live = {}
    lost = {}
    recovered = {}
    for member in state['captives']:
        live.setdefault(member['capture']['batch_id'], []).append(member)
    for member in state['memorial']:
        lost.setdefault(member['capture']['batch_id'], []).append(member)
    for member in state['party'] + state['home_roster'] + state['captives'] + state['memorial'] + state['escorted']:
        for capture in member.get('capture_history', []):
            recovered.setdefault(capture['batch_id'], []).append(member)
    batches = []
    def describe(member):
        row = member_view(member)
        row['equipment_names'] = [gear_name(game.cat, item['template_id']) for item in member.get('gear_instances', [])]
        return row

    for batch in state['capture_batches']:
        cid = batch['id']
        record = search['cases'].get(cid) or {}
        source = record.get('source_expedition')
        manifest = manifests.get(source) if source is not None else capture_manifests.get(cid)
        present = live.get(cid, [])
        members = [describe(m) for m in present]
        origin = game.cat.regions.get(batch['origin_region'], {}).get('name', '')
        if cid == active.get('id'):
            active['origin_region'] = origin
        if cid == target.get('batch_id'):
            names = {row['instance_id']: row['display_name'] for row in members}
            target['member_names'] = [names.get(iid, iid) for iid in target['member_ids']]
        absent = {m['instance_id'] for m in present}
        steps = list(record.get('steps', {}))
        known = batch.get('location_known', True)
        quote = missing.plan(game, cid) if present and not known else {}
        batches.append({
            'id': cid, 'day': batch['capture_day'], 'deadline': batch['deadline'],
            'origin_region': origin, 'origin_site': batch['origin_site'],
            'origin_site_name': rescue_site_name(game, batch, manifest),
            'members': members,
            'lost': [member_view(m) for m in lost.get(cid, [])],
            'recovered': [member_view(m) for m in recovered.get(cid, [])],
            'known': known, 'steps': steps,
            'can_finish_in_time': quote.get('rescue_in_time', state['day'] + 1 <= batch['deadline']),
            'other_due': [iid for iid in due if iid not in absent],
        })
    return {'batches': batches, 'cost': cost, 'due': due, 'active': active, 'target': target}


def commission_receipt(fact):
    grant = fact['evidence']
    resources = grant.get('resources') or {}
    return {'day': fact['day'], 'members': len(grant['initial_ids']),
            'resources': {key: resources[key] for key in ('copper', 'crystal', 'supply') if key in resources}}


def chapter_view(game, commission):
    import research

    state = game.s
    campaign = state['campaign']
    facts = campaign['facts']
    entitlement = state['book_rewards']['entitlements'].get('ST-104') or {}
    choice = entitlement.get('selected')
    selected = book_info(choice) if choice else {}
    if selected:
        claim = next((row for row in state['journal'] if row.get('type') == 'book_choice'
                      and row.get('entitlement') == 'ST-104' and row.get('book') == choice), {})
        selected.update(count=state['book_stock'].get(choice, 0), claimed_day=claim.get('day'))
    archive_item = research.name(game, 'KS01')
    archive_budget = next(budget for budget in game.cat.rules['command_budgets'] if budget['milestone'] == 'ST-104')
    archive_seals = game.cat.rules['recruitment']['milestone_seals'].get('ST-104', 0)
    scout = facts['ST-102']
    observation = scout['evidence'].get('observation', {}).get('observed', '')
    review_exchange = ''
    whistle_clue = ''
    history = []
    if 'ST-000' in facts:
        arrival = facts['ST-000']
        history.append({'id': 'ST-000', 'title': '暮汀北门独返', 'day': arrival['day'], 'text': arrival['evidence'].get('text', '')})
    if commission:
        history.append({'id': 'ST-101', 'title': '接受委任', 'day': commission['day'], 'text': '', 'commission': True})
    history.append({'id': 'ST-102', 'title': '侦路调查', 'day': scout['day'], 'text': observation})
    if 'ST-103' in facts:
        review_exchange = ('主角　我学会它之前，好像已经用过。\n'
                           '许苇　记得一个动作，和记得是谁教的，是两件事。')
        history.append({'id': 'ST-103', 'title': '旧日志核对', 'day': facts['ST-103']['day'],
                        'text': '许苇在旧日志上找到了相似的巡行次序。谁在重复谁仍待查证。\n' + review_exchange})
    if 'ST-104' in facts:
        detail = '旧名册上的四个名字被同色墨覆盖。'
        if 'KS01' in campaign['task_items']:
            detail += f'「{archive_item}」已收入任务物品。'
        whistle_clue = '秦姨拿出铜哨的旧照片和寄存登记单。阿铎从前用集合哨叫厨房开饭。'
        detail += '\n' + whistle_clue
        history.append({'id': 'ST-104', 'title': '首章交档', 'day': facts['ST-104']['day'], 'text': detail})
    if 'ST-303' in facts:
        history.append({'id': 'ST-303', 'title': '遗迹研究交付', 'day': facts['ST-303']['day'],
                        'text': f"已收入「{research.name(game, 'KS03')}」。培养舱生命支持独立于实验网络。"})
    return {
        'reviewed': 'ST-103' in facts, 'archived': 'ST-104' in facts,
        'history': history, 'observation': observation,
        'review_exchange': review_exchange, 'whistle_clue': whistle_clue,
        'archive_budget': archive_budget, 'archive_seals': archive_seals,
        'archive_item': archive_item,
        'choice_granted': bool(entitlement),
        'books': chapter_choice_books(state, entitlement.get('allowed', [])) if not choice else [],
        'book_selected': selected,
        'seals': campaign['seals'],
        'summon_id': f"P06-ST104-{campaign['summon_sequence'] + 1}",
    }


def book_info(key):
    from book_catalog import BOOKS
    row = BOOKS[key]
    formulas = {'P': '物攻', 'M': '魔攻', 'H': '治疗强度', 'V': '生命上限', 'A': '普攻所用攻击属性'}
    summary = re.sub(r'(\d+(?:\.\d+)?%?)([PMHVA])(?![A-Za-z])',
                     lambda match: match[1] + ('' if match[1].endswith('%') else '×') + formulas[match[2]],
                     row['summary'])
    card = row['card']
    timing = f"准备 {card['windup']} 拍 · 冷却 {card['cooldown']} 拍" if card else '被动'
    return {'id': key, 'name': row['name'], 'summary': summary, 'timing': timing}


def town_book_members(state):
    return [member for member in state['party'] + state['home_roster']
            if member['unit_id'].startswith(('M', 'H')) or member['unit_id'] == 'CMD']


def available_book_learners(members, key):
    import skill_books
    return [member['instance_id'] for member in members
            if key not in member.get('books_learned', []) and not skill_books.reason(member, key)]


def chapter_choice_books(state, keys):
    if not keys:
        return []
    members = town_book_members(state)
    travelling = {member['instance_id'] for member in state['party']}
    readers = {member['instance_id']: {
        'id': member['instance_id'], 'name': member_view(member)['display_name'],
        'location': '随队' if member['instance_id'] in travelling else '留城',
    } for member in members}
    offers = []
    for key in keys:
        learners = [readers[instance] for instance in available_book_learners(members, key)]
        known = [readers[member['instance_id']] for member in members if key in member.get('books_learned', [])]
        offers.append(dict(book_info(key), learners=learners, known=known))
    return offers


def book_market_view(game):
    import book_rewards
    import expedition_tiers
    from book_catalog import BOOKS

    state = game.s
    rewards = state['book_rewards']
    members = town_book_members(state)
    buyers = {member['instance_id']: member_view(member)['display_name'] for member in members}
    stock = state['book_stock']
    offers = {}
    for key, row in BOOKS.items():
        if row.get('hidden') or not book_rewards.unlocked(game, key):
            continue
        offers[key] = dict(book_info(key), stage=row['stage'], price=book_rewards.price(game, key),
                           stock=stock.get(key, 0), buyers=available_book_learners(members, key))
    target = rewards['target']
    route = next(row for row in game.cat.config['routes'] if row['route_id'] == state['route'])
    profile = game.cat.multi['profiles'][route['profile']]
    return {'offers': offers, 'buyers': buyers, 'target': book_info(target) if target else {},
            'progress': rewards['progress'], 'departure_cap': expedition_tiers.caps(profile, state['difficulty'])['books']}


def book_research_view(game):
    from book_rewards import TASKS

    state = game.s
    in_town = state['phase'] == 'TOWN'
    rewards = state['book_rewards']
    rows = []
    for key, (name, description) in BOOK_RESEARCH.items():
        task = rewards['tasks'].get(key)
        if not in_town and not task:
            continue
        battles = (task or {}).get('battles', {})
        counts = Counter(battle['status'] for battle in battles.values())
        row = {'id': key, 'name': name, 'banked': counts['BANKED'], 'pending': counts['PENDING']}
        if in_town:
            entitlement = rewards['entitlements'].get(key) or {}
            selected = entitlement.get('selected')
            row.update(description=description, accepted=task is not None,
                       candidates=[book_info(book) for book in entitlement.get('allowed', TASKS[key])],
                       claimable=bool(entitlement and not selected), selected=book_info(selected) if selected else {})
        rows.append(row)
    return rows


def skill_book_view(game):
    import skill_books
    state = game.s
    in_town = state['phase'] == 'TOWN'
    stock = {key: count for key, count in state.get('book_stock', {}).items() if count > 0} if in_town else {}
    members = state['party'] + state['home_roster'] if in_town else state['party']
    known = sorted(set(stock).union(*(set(member.get('books_learned', [])) for member in members)))
    if not known:
        return {}
    rows = {}
    for member in members:
        if not (member['unit_id'].startswith(('M', 'H')) or member['unit_id'] == 'CMD'):
            continue
        learned = member.get('books_learned', [])
        if not stock and (not learned or not in_town and member['hp'] <= 0):
            continue
        moves = skill_books.cards(member, skill_books._core(member))
        disabled = member.get('disabled_skills', [])
        rows[member['instance_id']] = {'name': member_view(member)['display_name'],
            'learned': learned, 'equipped': member.get('books_equipped', []),
            'study': [{'id': key, 'blocked': '已学会' if key in learned else skill_books.reason(member, key)} for key in stock],
            'moves': [{'id': move['move_id'], 'name': move['name'], 'enabled': move['move_id'] not in disabled}
                      for move in moves],
            'main_choices': skill_books.main_ids(member), 'main': member.get('main_attack', 'AUTO')}
    return {'stock': stock, 'catalog': {key: book_info(key) for key in known}, 'members': rows}


def whistle_view(game):
    from campaign import QUESTS
    state = game.s
    campaign = state['campaign']
    quest = QUESTS['MG01']
    if quest['gate'] not in campaign['facts']:
        return {}
    receipts = campaign['quests'].get('MG01', {})
    if 'OBS-MG01' in campaign['task_items']:
        stage = 'done'
    elif 'MG01' in state['original_recovery']['targets']:
        stage = 'field'
    elif 'witness' in receipts:
        stage = 'collect'
    else:
        stage = 'witness' if 'record' in receipts else 'record'
    collect = receipts.get('collect', {})
    collected = {'day': collect['day'], 'copper': collect['paid']['copper']} if stage == 'done' and collect else {}
    return {'stage': stage, 'price': quest['cost']['copper'],
            'record': receipts.get('record', {}).get('text', ''),
            'witness': receipts.get('witness', {}).get('text', ''), 'collection': collected}


def scarf_view(game):
    from campaign import QUESTS

    state = game.s
    campaign = state['campaign']
    quest = QUESTS['MG02']
    if quest['gate'] not in campaign['facts']:
        return {}
    receipts = campaign['quests'].get('MG02', {})
    if 'OBS-MG02' in campaign['task_items']:
        stage = 'done'
    elif 'MG02' in state['original_recovery']['targets']:
        stage = 'field'
    elif 'witness' in receipts:
        stage = 'collect'
    else:
        stage = 'witness' if 'record' in receipts else 'record'
    price = quest['cost']['fiber']
    return {'stage': stage, 'name': quest['item'], 'price': price,
            'short': max(0, price - state['warehouse'].get('fiber', 0)),
            'record': receipts.get('record', {}).get('text', ''),
            'witness': receipts.get('witness', {}).get('text', ''),
            'collection': receipts.get('collect', {})}


def later_evidence_view(game):
    from campaign import QUESTS

    state = game.s
    campaign = state['campaign']
    rows = {}
    for general_id in LATER_EVIDENCE_GENERALS:
        quest = QUESTS[general_id]
        if quest['gate'] not in campaign['facts']:
            continue
        receipts = campaign['quests'].get(general_id, {})
        target = state['original_recovery']['targets'].get(general_id)
        if 'OBS-' + general_id in campaign['task_items']:
            stage = 'done'
        elif target:
            stage = 'field'
        elif 'witness' in receipts:
            stage = 'collect'
        else:
            stage = 'witness' if 'record' in receipts else 'record'
        cost = quest['cost']
        short = {key: amount - state['warehouse'].get(key, 0) for key, amount in cost.items()
                 if state['warehouse'].get(key, 0) < amount}
        rows[general_id] = {'id': general_id, 'general': hunt_general(game, general_id)['human_name'],
                            'item': quest['item'], 'stage': stage, 'cost': cost, 'short': short,
                            'record': receipts.get('record', {}).get('text', ''),
                            'witness': receipts.get('witness', {}).get('text', ''),
                            'collection': receipts.get('collect', {}),
                            'field_location': target['source']['statement'] if target and stage == 'field' else ''}
    return rows


def scouting_view(state):
    trip = state.get('tutorial_trip')
    if not trip or state['mission'] != 'TUTORIAL' or state['phase'] not in ('EXPLORE', 'RETURNED', 'FAILED'):
        return {}
    victories = {report['encounter_id'] for report in state['battle_reports']
                 if report['result'] == 'VICTORY' and not report['debug_tainted']}
    missing = [encounter for encounter in TUTORIAL_BATTLES if encounter not in victories]
    observed = bool(trip['observation'])
    settlement = state.get('summary') or {}
    delivered = state['campaign']['facts'].get('ST-102')
    delivered_here = bool(state['phase'] == 'RETURNED' and delivered and settlement.get('settlement_id')
                          and settlement['settlement_id'] == delivered['evidence']['settlement_id'])
    return {'battles': len(TUTORIAL_BATTLES) - len(missing), 'missing_battles': missing, 'observed': observed,
            'ready': not missing and observed and not state['debug_tainted'], 'delivered_here': delivered_here}


def finale_enemy_preview(game, encounter):
    units = []
    for unit in encounter['units']:
        kind = unit['enemy_id']
        name = game.cat.enemy_templates.get(kind, {}).get('name', kind)
        moves = [{key: move.get(key) for key in ('name', 'windup', 'range')} for move in unit.get('moves', [])]
        units.append({'id': kind, 'name': name, 'hp': unit['stats']['hp'], 'moves': moves})
    return units


def finale_view(game):
    import finale

    state = game.s
    final = state['finale']
    end = final['ending']
    run = final['run']
    is_town = state['phase'] == 'TOWN'
    facts = state['campaign']['facts']
    if not end and not run and not (is_town and 'CH3_COMPLETE' in facts):
        return {}
    result = {'route': run['route'] if run else ('B' if finale.carried(game) else 'A'),
              'agla_carried': run['agla_carried'] if run else finale.carried(game),
              'risk': finale.RISK, 'stage': run['stage'] if run else 'PREPARATION',
              'reports': [{key: report[key] for key in ('encounter_id', 'battle_id', 'result', 'tick')}
                          for report in run['reports']] if run else []}
    if end:
        result['ending'] = {'id': end['ending_id'], 'title': finale.ENDINGS[end['ending_id']][0],
                            'text': finale.ending_text(game).split('\n', 1)[-1], 'cause': end['cause'],
                            'member_losses': len(end['grade']['lost']), 'held': len(end['grade']['captives'])}
        return result
    if run and run['stage'] == 'IDENTITY':
        result['identity'] = [
            '你是魔王建立的独立分身，一直借用旧指挥官的脑体。',
            '上代最后一次回头来自档案。现在由你决定是否保留独立人格。',
        ]
        contract = game.cat.rules['finale']['identity_choice_contract']
        result['merger'] = {'pending': run['merger_pending'], 'terms': contract['confirmation_text']}
    if run and run['stage'] == 'REGROUP':
        result['fatigue'] = run['reserve_fatigue']
    if state['battle'] and state['battle'].get('finale'):
        battle = state['battle']['finale']
        result['countdown'] = battle['remaining']
        result['countdown_limit'] = battle['duration']
        if battle['route'] == 'B':
            result['interface_progress'] = battle['channel']['progress']
            result['interface_required'] = battle['channel_ticks']
    if is_town or (run and run['stage'] == 'REGROUP'):
        blocker = ''
        try:
            finale.legal_party(game)
        except ValueError as error:
            blocker = str(error)
        if state['debug_tainted']:
            blocker = '调试存档无法进入正式终战。'
        if is_town:
            result['budget'] = next(row for row in game.cat.rules['command_budgets'] if row['milestone'] == 'FINALE_READY')
            preparation = final['preparation']
            result['prepared'] = bool(preparation and preparation['route'] == result['route'])
            result['preparation_stale'] = bool(preparation and not result['prepared'])
            result['agla'] = {'assembled': bool(state['research']['assembly']),
                              'sealed': final['sealed'], 'seal_pending': final['seal_pending']}
            result['previews'] = [
                {'title': title, 'units': finale_enemy_preview(game, encounter)}
                for title, encounter in (
                    ('初生魔王', finale.lock_demon(game)),
                    ('管理员', game.cat.encounter_for_board('BATTLE-ADMIN', finale.BOARD)),
                )
            ]
        result['blocker'] = blocker
    return result


def resource_view(state):
    bank, warehouse, party = state['bank'], state['warehouse'], state['party']
    return {'copper': bank['copper'], 'crystal': bank['crystal'],
            'warehouse': {material: warehouse.get(material, 0)
                          for material in ('iron', 'fiber', 'herb', 'crystal_shard')},
            'expedition_used': sum(member['cost'] for member in party) + state['escort_reserved_cost'],
            'battle_used': sum(member['cost'] for member in party if member['deployed'])}


def make_view(game, ledger, primary, committed_save_version=None):
    import region_space as space
    state = game.s
    facts = state['campaign']['facts']
    trip = state.get('tutorial_trip') or {}
    party = [member_view(m) for m in state['party']]
    battle = state.get('battle')
    active = space.active(game)
    route = route_view(game) if active else {}
    if state['phase'] == 'FINAL_REGROUP':
        from finale import BOARD as board_id
    else:
        board_id = 'OPEN'
    summary = settlement_view(game)
    cap = (state.get('manifest') or {}).get('caps', {}).get('gear_claims', 0)
    offers = trip.get('gear_offers', []) if 'G' in route.get('cleared', []) else []
    compatible = [family for family in offers
                  if any(row['unit_id'] in game.cat.gear[family + '-Q1']['allowed_unit_ids'] for row in party)]
    opening = state['narrative']['records'].get('opening', {})
    town = state['phase'] == 'TOWN' and 'ST-101' in facts
    commission = commission_receipt(facts['ST-101']) if town else {}
    hometown = [member_view(m) for m in state['home_roster']] if town else []
    prepare = preparation_view(game, party + hometown) if town else {}
    reports = state['battle_reports']
    snapshot = battle_view(game)
    rescue_board = battle['board_cells'] if battle and state['mission'] == 'RESCUE' else []
    can_plan = state['phase'] in ('TOWN', 'EXPLORE')
    tutorial_explore = state['phase'] == 'EXPLORE' and state['mission'] == 'TUTORIAL'
    session = state['campaign']['remembrance']
    town_memory = memory_view(game, session['battle']) if town and session else {}
    hunts = {general: hunt_view(game, general, town_memory) for general in HUNT_GENERALS}
    finale = finale_view(game)
    if finale.get('reports'):
        reports = finale['reports']
    return {'phase': state['phase'], 'site': state['site'], 'day': state['day'],
            'region': state['region'], 'region_name': game.cat.regions[state['region']]['name'] if active else '',
            'supply': state['bank']['supply'], 'medical': state['medical'],
            'resources': resource_view(state),
            'departure_cost': departure_cost(game),
            'ordinary_routes': ordinary_routes_view(game) if town else [],
            'save_version': _save_version(ledger, primary) if committed_save_version is None else committed_save_version,
            'commissioned': 'ST-101' in facts, 'commission_receipt': commission, 'complete': 'ST-102' in facts,
            'tutorial_area': active and state['mission'] == 'TUTORIAL',
            'tutorial_return': state['mission'] == 'TUTORIAL',
            'hunts': [hunt for hunt in hunts.values() if hunt],
            'hunt': hunts['MG01'], 'sev_hunt': hunts['MG02'], 'finale': finale,
            'rescue': rescue_view(game) if state['capture_batches'] else {},
            'rescue_board': rescue_board,
            'preparation': prepare, 'construction': construction_view(game) if town else {},
            'research': campaign_research_view(game, party) if town else {},
            'town_services': town_services_view(game) if town else {},
            'consumables': consumables_view(game, town) if town or state['phase'] == 'EXPLORE' else {},
            'material_goal': material_goal_view(game, town) if town or state['phase'] == 'EXPLORE' else {},
            'battle_memory': memory_view(game, battle), 'town_memory': town_memory,
            'whistle_cue': whistle_cue(state) if 'ST-104' in facts else '',
            'party': party, 'budget': state['budget'], 'route': route,
            'town_roster': {'copper': state['bank']['copper'],
                            'spear_price': game.cat.rules['economy']['mercenary_recruit_copper'],
                            'home': hometown} if town else {},
            'equipment': equipment_view(game) if town or state['phase'] == 'EXPLORE' else {},
            'skill_books': skill_book_view(game) if town or state['phase'] == 'EXPLORE' else {},
            'book_market': book_market_view(game) if town else {},
            'book_research': book_research_view(game) if 'ST-104' in facts and state['phase'] in ('TOWN', 'EXPLORE') else [],
            'field_book_rewards': field_book_rewards(game),
            'handbook_event': handbook_event_view(game),
            'ev07': ev07_view(game),
            'chapter': chapter_view(game, commission) if town and 'ST-102' in facts else {},
            'whistle': whistle_view(game) if state['phase'] == 'TOWN' else {},
            'scarf': scarf_view(game) if town else {},
            'later_evidence': later_evidence_view(game) if town else {},
            'opening_lines': opening.get('lines', []),
            'town_deploy_cells': game.cat.boards[board_id]['player_deploy_cells'],
            'town_board_cells': game.cat.boards[board_id]['cells'],
            'observation': trip.get('observation'),
            'choice_notes': tutorial_choice_notes(game, trip.get('choices', {}), party) if tutorial_explore else {},
            'scouting': scouting_view(state),
            'plan_offers': plan_view(game, [key for key in TUTORIAL_PLANS if key not in state['plans_owned']])
                           if tutorial_explore and state['site'] == 'A' and 'A' in route.get('cleared', []) else [],
            'owned_plans': plan_view(game, state['plans_owned']) if can_plan else [],
            'equipped_plans': state['plans_equipped'] if can_plan else [],
            'gear_offers': offers, 'gear_compatible': compatible,
            'gear_offer_names': {family: gear_name(game.cat, family + '-Q1') for family in offers},
            'gear_claims': cap - state['debits'].get('gear_claims', 0),
            'settlement': summary,
            'battle_view': snapshot,
            'battle_results': [{key: row.get(key) for key in ('encounter_id', 'battle_id', 'result', 'tick')}
                               for row in reports],
            'actors': snapshot['actors'] if battle else []}


def ready_contact_model_kinds(game, ledger, verified):
    """Suggest resources for a known contact while the client requests its full view."""
    if game.s['phase'] != 'EXPLORE' or (ledger.get('head') not in (None, verified)):
        return []
    if any(row['status'] == 'PREPARED' for row in ledger['entries'].values()):
        return []
    import depth_growth
    import region_space

    contact = (region_space.current(game) or {}).get('contact')
    if not contact or contact['site'] in game.current['cleared']:
        return []
    enemies = depth_growth.current_encounter(game, contact['site'])['units']
    members = map(member_view, game.s['party'])
    kinds = dict.fromkeys(row['enemy_id'] for row in enemies)
    kinds.update(dict.fromkeys(row['unit_id'] for row in members
                               if row['deployed'] and row['deployable'] and not row['injury_days']))
    return sorted(kinds, key=lambda kind: kind != 'MG01')


def make_presentation(game, ledger, primary, *, battle_board=None, committed_save_version=None):
    import boss_threats
    import narrative
    import region_space

    public = narrative.public(game)
    active = public['active']
    # The frozen text client records its engineering description as a receipt.
    # The native client uses the gated memory card and its committed transcript.
    if active is not None and active['id'].startswith('remembrance-'):
        active = None
    slice_view = make_view(game, ledger, primary, committed_save_version)
    line = None
    if active is not None:
        record = active['lines'][active['cursor']]
        actor_id = record.get('actor_id')
        speaker = record['speaker']
        if actor_id:
            speaker = next((member['display_name'] for member in slice_view['party']
                            if member['instance_id'] == actor_id), '随行队员')
        text = record['text']
        receipt = record['id'] == 'receipt'
        if receipt and active['id'] == 'research-deliver':
            budget = slice_view['budget']
            text = (f"研究报告已交存，观测站校验片入档。出征与战斗预算为 "
                    f"{budget['expedition']}/{budget['battle']} Cost。可在旧档案查看交付详情。")
        line = {'speaker': speaker, 'text': text, 'receipt': receipt}
    board = None
    battle = game.s.get('battle')
    if game.s['phase'] == 'BATTLE' and battle and battle.get('finale'):
        board = {'battle_cells': battle['board_cells']}
    elif game.s['phase'] == 'BATTLE':
        # Live and terminal battle views use this geometry. Exploration is
        # projected again when the battle ends, with the current fog and contacts.
        space = region_space.current(game)
        if space is not None:
            binding = space['boards'].get(game.s['site'])
            if binding and battle_board and battle and battle['battle_id'] == battle_board:
                # Both grids come from the frozen catalog throughout this battle.
                board = {'battle_board_ref': battle_board}
                del slice_view['town_board_cells'], slice_view['town_deploy_cells']
            else:
                board = {'battle_cells': game.cat.boards[binding['board_id']]['cells'] if binding else []}
    else:
        field = region_space.public(game)
        if field is not None:
            map_fields = ('version', 'position', 'facing', 'steps', 'cells', 'objects',
                          'contact', 'deploy_cells', 'battle_cells', 'summary')
            board = {key: field[key] for key in map_fields}
            if field['preview']:
                from combat import enemy_actor
                board['enemy_preview'] = [
                    {'name': game.cat.enemy_templates.get(row['kind'], {}).get('name') or row['kind'],
                     'id': row['id'], 'kind': row['kind'], 'side': row['side'],
                     'position': row['pos'], 'facing': row['facing'], 'hp': row['hp'], 'badge': f'敌{index}'}
                    for index, row in enumerate(map(enemy_actor, field['preview']), 1)
                ]
    danger = None
    if battle is not None and battle.get('result') is None:
        actions = []
        for actor in battle['actors']:
            pending = actor.get('pending')
            if actor['hp'] <= 0 or not pending:
                continue
            actions.append(dict(actor_id=actor['id'], side=actor['side'], action_id=pending['id'],
                                **{key: pending.get(key) for key in
                                   ('move_id', 'kind', 'target', 'origin', 'facing', 'due')},
                                locked_cells=pending.get('cells', []), geometry_complete=False))
        laws = []
        for row in boss_threats.public(battle)['bosses']:
            law = row['law']
            if law and law['status'] == 'ACTIVE':
                laws.append({key: law[key] for key in
                             ('id', 'boss', 'target', 'started', 'due', 'progress', 'threshold', 'status')})
        danger = dict(battle_id=battle['battle_id'], tick=battle['tick'], actions=actions, laws=laws,
                      coverage='PERSISTED_PENDING_AND_ACTIVE_LAWS', exhaustive=False)
    return dict(narrative_enabled=public['enabled'], hint=public['hint'], history=public['history'],
                active=None if active is None else dict(id=active['id'], title=active['title'], status=active['status'],
                    cursor=active['cursor'], line_count=len(active['lines']),
                    line=line),
                map=board,
                danger=danger, slice=slice_view)
