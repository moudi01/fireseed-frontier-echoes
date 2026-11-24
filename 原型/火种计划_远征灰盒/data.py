"""Read-only adapter for TINDER documents. No dependency on older game saves."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import random
import sys
from board_geometry import build_boards, adapt_encounter, DEFAULT_FORMATION

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / '文档' / '执灯人_完整设计提案_v4' / '校验'
sys.path.insert(0, str(DOC))
from event_catalog import load_catalog
from choice_sampling_model import ChoiceSampler
from joint_sampling_model import digest


# Explicit production inventory: extend here when adding a runtime dependency.
RUNTIME_FILES = (
    'data.py',
    'narrative.py',
    'narrative_view.js',
    'region_space.py',
    'save_storage.py',
    'drill_lab.py',
    'drills.py',
    'missing.py',
    'clues.py',
    'recovery.py',
    'finale.py',
    'finale_battle.py',
    'research.py',
    'learning.py',
    'adaptation_geometry.py',
    'campaign.py',
    'story_mission.py',
    'facilities.py',
    'supplies.py',
    'expedition_tiers.py',
    'depth_growth.py',
    'fantasy_enemies.py',
    'necromancy.py',
    'reinforcements.py',
    'enemy_support.py',
    'spatial_moves.py',
    'sweeps.py',
    'veil.py',
    'action_timing.py',
    'protection.py',
    'battle_plans.py',
    'skill_books.py',
    'heroes.py',
    'hero_fixtures.py',
    'bosses.py',
    'plan_offers.py',
    'board_geometry.py',
    'combat.py',
    'mechanics.py',
    'battle_skills.py',
    'battle_lab.py',
    'commander.py',
    'gear_affixes.py',
    'equipment.py',
    'equipment_rolls.py',
    'workshop.py',
    'reforge.py',
    'construction.py',
    'outfitting.py',
    'engine.py',
    'town.py',
    'rescue.py',
    'escort.py',
    'event_memory.py',
    'refugee.py',
    'water.py',
    'medicine.py',
    'cases.py',
    'civilian.py',
    'civilian_text.json',
    'app.py',
    'smoke.py',
    'web.py',
    'index.html',
    'space_view.js',
    'roster_content.py',
    'roster_skills.py',
    'hero_refinements.py',
    'balance_v062.py',
    'hero_power_v062.py',
    'late_pressure.py',
    'event_conditions.py',
    'rogue_events.py',
    'enemy_intel.py',
    'hidden_thread.py',
    'fortune_mechanics.py',
    'boss_mimic.py',
    'boss_threats.py',
    'stage_balance.py',
    'expedition_peril.py',
    'save_validation.py',
    'challenge_rewards.py',
    'book_catalog.py',
    'book_combat.py',
    'book_rewards.py',
    'battle_enrage.py',
    'board_gallery.py',
)


class CampaignSampler(ChoiceSampler):
    """EVENT-LINK-1.0 overlay; historical acceptance model remains reproducible."""
    def generate(self, request):
        req = deepcopy(request)
        # Human cases retain their own lifecycle rules. Ordinary cards repeat at
        # full weight, even when every card was shown on the previous expedition.
        req['history'] = [[eid for eid in trip if self.events[eid]['type'] == 'humanity']
                          for trip in req.get('history', [])]
        from expedition_tiers import caps
        profiles=deepcopy(self.multi['profiles'])
        try:
            for profile in self.multi['profiles'].values():profile['reward_caps']=caps(profile,req.get('difficulty','D0'))
            return super().generate(req)
        finally:self.multi['profiles']=profiles

    def filter_reason(self, rid, slot, eid):
        origin = self.req.get('case_origins', {}).get(eid) or (self.req.get('refugee_origin') if eid=='EV03' else None)
        if origin and rid != origin:
            return 'ORIGINAL_CASE_LOCATION'
        return super().filter_reason(rid,slot,eid)


def read(name):
    return json.loads((DOC / name).read_text(encoding='utf-8'))


def keyed_rng(seed, key):
    return random.Random(int(hashlib.sha256(f'{seed}:{key}'.encode()).hexdigest(), 16))


class Catalog:
    def __init__(self):
        self.rules = read('规则样例.json')
        self.multi = read('多区域远征配置.json')
        self.loot = read('战利品.json')
        self.config = read('完整远征验证配置.json')
        self.build = read('构筑与学习.json')
        self.maps = read('地图地形.json')
        self.events, bundles = load_catalog()
        self.events = {e['event_id']: e for e in self.events}
        from civilian import apply
        apply(self.events)
        self.event_links = read('近期事件联动.json')
        for event in self.events.values():
            if event['type'] != 'humanity':
                event['repeat']['cooldown_completed_expeditions'] = 0
                for option in event['options']:
                    if option['option_id'] == 'PASS':
                        option['mechanical_summary'] = '0支付、0收益、0新增战斗和行动日；仅暂离，本区可回访，已有进度保留。'
        self.bundles = {b['bundle_id']: b for b in bundles}
        self.terrain = {t['terrain_id']: t for t in self.maps['terrain_types']}
        enemy_data = read('敌人与遭遇.json')
        self.enemy_templates = {e['enemy_id']: e for group in ('enemies', 'elites', 'bosses') for e in enemy_data[group]}
        self.elite_ids = {e['enemy_id'] for e in enemy_data['elites']}
        self.encounters = {e['encounter_id']: e for e in enemy_data['encounters']}
        from battle_skills import overlay
        overlay(self.encounters)
        self.boards = build_boards(self.maps['boards'], self.terrain)
        self.formation = DEFAULT_FORMATION
        self.layouts = {t['template_id']: t for r in read('八区联合布点.json')['regions'] for t in r['templates']}
        from refugee import LAYOUT
        self.layouts[LAYOUT['template_id']]=deepcopy(LAYOUT)
        from water import LAYOUT as WATER_LAYOUT
        self.layouts[WATER_LAYOUT['template_id']]=deepcopy(WATER_LAYOUT)
        from medicine import LAYOUT as MEDICINE_LAYOUT
        self.layouts[MEDICINE_LAYOUT['template_id']]=deepcopy(MEDICINE_LAYOUT)
        import cases
        for eid in cases.CONFIG:self.layouts[cases.layout(eid)['template_id']]=cases.layout(eid)
        self.regions = {r['region_id']: r for r in self.multi['regions']}
        self._install_encounter_rules(enemy_data['fixtures'])
        self.gear = {g['template_id']: g for g in self.loot['equipment_templates']}
        self.items = {c['consumable_id']: c for c in self.loot['consumables']}
        self.recipes = {r['recipe_id']: r for r in self.loot['recipes']}
        self.plans = {p['plan_id']: p for p in self.build['plans']}
        self._install_build_rules()
        names = ['规则样例.json', '多区域远征配置.json', '战利品.json', '构筑与学习.json',
                 '地图地形.json', '远征事件池.json', '普通事件扩展.json', '敌人与遭遇.json',
                 '八区联合布点.json', '完整远征验证配置.json', '事件回访与结算合同.json',
                 '奖励预留与事件配比配置.json', '联合抽样验收配置.json', '连续区域地图合同.json',
                 'choice_sampling_model.py', 'joint_sampling_model.py', 'event_catalog.py', '近期事件联动.json']
        self.hashes = {n: hashlib.sha256((DOC / n).read_bytes()).hexdigest() for n in names}
        tutorial_path=DOC.parent/'样片/首次远征流程.json'
        self.hashes['../样片/首次远征流程.json']=hashlib.sha256(tutorial_path.read_bytes()).hexdigest()
        self.runtime_hashes = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                               for name in RUNTIME_FILES}

    def _install_encounter_rules(self, fixtures):
        """Apply encounter overlays in their historical dependency order."""
        from fantasy_enemies import install
        install(self)
        from expedition_tiers import install as install_tiers
        install_tiers(self)
        from reinforcements import install as install_reinforcements
        install_reinforcements(self,fixtures)
        from enemy_support import install as install_support
        install_support(self)
        from spatial_moves import install as install_spatial
        install_spatial(self)
        from sweeps import install as install_sweeps
        install_sweeps(self)
        from veil import install as install_veil
        install_veil(self)
        from action_timing import install as install_timing
        install_timing(self)
        from protection import install as install_protection
        install_protection(self)
        from bosses import install as install_bosses
        install_bosses(self)
        import campaign,story_mission
        campaign.install(self);story_mission.install(self)

    def _install_build_rules(self):
        """Apply party, balance and final rule overlays after item catalogues."""
        import commander
        commander.install(self)
        import roster_content
        roster_content.install(self)
        import hero_power_v062
        hero_power_v062.install(self)
        import balance_v062
        balance_v062.install(self)
        import late_pressure
        late_pressure.install(self)
        import stage_balance
        stage_balance.install(self)
        import event_conditions
        event_conditions.install(self)
        import boss_mimic, boss_threats
        boss_mimic.install(self)
        boss_threats.install(self)
        import expedition_peril
        expedition_peril.install(self)
        import book_catalog
        book_catalog.install(self)
        import battle_enrage
        battle_enrage.install(self)

    def encounter_for_board(self, encounter_id, board_id):
        from balance_v062 import enemy_for
        from late_pressure import fixed_encounter
        return fixed_encounter(enemy_for(self,adapt_encounter(self.encounters[encounter_id], self.boards[board_id])))

    def team(self, team_id, birth='MID', equipment='Q1_CONTROL'):
        spec = next(t for t in self.config['teams'] if t['team_id'] == team_id)
        bases = {x['id']: x for x in self.rules['units'].values()}
        bases.update(self.rules['mercenaries']); bases.update(self.rules['hero_templates'])
        team = []
        for i, member in enumerate(spec['members']):
            uid = member['unit_id']; base = bases[uid]
            stats = dict(base['stats']) if 'stats' in base else {k: (v[0] if birth == 'LOW' else sum(v) // 2) for k, v in base['ranges'].items()}
            stats = {k: v + (spec['level'] - 1) * base['growth'][k] for k, v in stats.items()}
            gear = self.config['equipment_profiles'][equipment].get(uid, [])
            for g in gear:
                from balance_v062 import gear_modifiers
                for k, v in gear_modifiers(self,g,uid).items(): stats[k] += v
            team.append({**member, 'stats': stats, 'hp': stats['hp'], 'erosion': 0, 'xp': 0,
                         'deployed': i in spec['initial_deployed_indices'], 'gear': list(gear),
                         'cost': 1 if uid.startswith('S') or uid.startswith('PET-') else 2 if uid.startswith('M') else 4,
                         'attack_type': base['attack_type'], 'range': base['range'], 'interval': base['interval'],
                         'position': list(self.formation[i]), 'stance': 'advance', 'facing': 1, **{k:base[k] for k in ('basic_medium','locomotion') if k in base}})
        budget = [x for x in self.rules['command_budgets'] if x['milestone'] in spec['facts']][-1]
        used=0
        for member in team:
            if member['deployed'] and used+member['cost']<=budget['battle']:used+=member['cost']
            else:member['deployed']=False
        return spec, team, budget

    def manifest(self, route_id, seed, history=None, case=None, directed=False, water_case=None, directed_water=False, medicine_case=None, directed_medicine=False, local_cases=None, directed_local=None, difficulty='D0', tier_facts=None, campaign_facts=None, guaranteed_case=None):
        route = next(r for r in self.config['routes'] if r['route_id'] == route_id)
        import expedition_tiers as tiers
        actual_facts=tier_facts if tier_facts is not None else route['facts']
        tiers.check(difficulty,actual_facts)
        # Controlled ordinary-loop fixture; no assumptions about the user's morality.
        chapter=(3 if 'CH2_COMPLETE' in campaign_facts else 2 if 'ST-104' in campaign_facts else 1) if campaign_facts is not None else route['chapter']
        req = {'chapter': chapter, 'facts': campaign_facts if campaign_facts is not None else route['facts'], 'profile': route['profile'],
               'start': route['selected_path'][0], 'target': route['selected_path'][-1], 'seed': seed,
               'difficulty': difficulty, 'history': history or [], 'ordinary_repeat_policy': 'ALLOW_FULL_WEIGHT',
               'case_states': {e: 'PROTECTED' for e, v in self.events.items() if v['type'] == 'humanity'}}
        original_directed=req.get('directed_case')
        if case and case['enabled']:
            req['case_states']['EV03']=case['state']
            if case['anchor']:req['refugee_origin']=case['anchor']['region']
            if directed and case['state'] not in ('PROTECTED','EXPLOITED'):req['directed_case']='EV03'
        if water_case and water_case['enabled']:
            req['case_states']['EV09'] = water_case['state']
            if water_case['anchor']: req.setdefault('case_origins', {})['EV09'] = water_case['anchor']['region']
            if directed_water and water_case['state'] not in ('PROTECTED','EXPLOITED'): req['directed_case'] = 'EV09'
        if medicine_case and medicine_case['enabled']:
            req['case_states']['EV19']=medicine_case['state']
            if medicine_case['anchor']:req.setdefault('case_origins',{})['EV19']=medicine_case['anchor']['region']
            if directed_medicine and medicine_case['state'] not in ('PROTECTED','EXPLOITED'):req['directed_case']='EV19'
        for eid,c in (local_cases or {}).items():
            if c['enabled']:
                req['case_states'][eid]=c['state']
                if c['anchor']:req.setdefault('case_origins',{})[eid]=c['anchor']['region']
                if directed_local==eid and c['state'] not in ('PROTECTED','EXPLOITED'):req['directed_case']=eid
        if guaranteed_case and not req.get('directed_case'):
            req['directed_case']=guaranteed_case
            req['case_guarantee']=guaranteed_case
        result = CampaignSampler().generate(req)
        if result['status']!='SUCCESS' and req.get('directed_case'):
            if guaranteed_case and not original_directed:
                raise ValueError('本路线无法安排保底案件 '+guaranteed_case+'；尚未扣出发物资。')
            prefix = {'EV03':'case','EV09':'water','EV19':'medicine'}.get(req['directed_case'],'event '+req['directed_case'])
            raise ValueError('本路线无法安排原接洽处的续办。请选择包含原区域的路线，或使用 '+prefix+' visit CONFIRM；尚未扣出发物资。')
        if result['status'] != 'SUCCESS': raise ValueError('无法生成合法远征：' + str(result))
        for region in result['manifest']['regions'].values():
            for binding in region['events'].values():
                import cases
                if binding['event_id'] in cases.CONFIG:binding['case_service']=cases.service(binding['event_id'])
                binding['site_lighting'] = deepcopy(self.events[binding['event_id']]['site_lighting'])
        if req.get('directed_case') == 'EV09': result['manifest']['water_capacity_reserved'] = True
        from depth_growth import policy
        result['manifest']['depth_growth'] = policy(self)
        tiers.bind(self,result['manifest'],difficulty,actual_facts,seed,keyed_rng)
        import late_pressure
        late_pressure.bind(result['manifest'],route,actual_facts)
        import challenge_rewards
        challenge_rewards.bind(self,result['manifest'])
        import event_conditions
        event_conditions.bind(self,result['manifest'])
        import rogue_events
        rogue_events.bind(self,result['manifest'])
        result['manifest'].pop('manifest_sha256', None)
        result['manifest']['manifest_sha256'] = digest(result['manifest'])
        return result['manifest'], req
