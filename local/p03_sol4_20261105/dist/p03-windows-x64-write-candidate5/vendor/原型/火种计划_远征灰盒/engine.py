"""Transactional expedition state machine for isolated greybox experiments."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import math
import os
import shlex
import time
import uuid

from data import Catalog, keyed_rng
import combat
import town
import rescue
import escort
import event_memory
import refugee
import water
import medicine
import cases
import gear_affixes
import equipment
import equipment_rolls
import workshop
import construction
import outfitting
import depth_growth
import expedition_tiers as tiers
import plan_offers
import skill_books
import book_rewards
import book_combat
import heroes
import bosses
import campaign
import story_mission
import facilities
import supplies
import learning
import research
import finale
import recovery
import clues
import missing
import drills
import save_storage
import archive_cache
import region_space
import narrative
import event_conditions
import rogue_events
import enemy_intel
import hidden_thread
import boss_threats
import challenge_rewards

VERSION = 'TINDER-GREYBOX-0.98'
BASE = Path(__file__).resolve().parent


def require(condition, message):
    if not condition: raise ValueError(message)


def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('xb') as handle:
            handle.write(value if type(value) is bytes else save_storage.encode(value))
            handle.flush(); os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _snapshot_state(state):
    """Copy the saved JSON graph, preserving deepcopy's aliases and fallbacks."""
    memo = {}
    keep_alive = []
    memo[id(memo)] = keep_alive
    missing = object()
    atoms = {str, int, float, bool, type(None)}

    def clone(value):
        kind = type(value)
        if kind in atoms or kind is archive_cache.ArchivedRecord:
            return value
        cached = memo.get(id(value), missing)
        if cached is not missing:
            return cached
        if kind is dict:
            copied = {}
            memo[id(value)] = copied
            for key, child in value.items():
                copied[key if type(key) is str else deepcopy(key, memo)] = clone(child)
        elif kind is list:
            copied = []
            memo[id(value)] = copied
            copied.extend(clone(child) for child in value)
        else:
            return deepcopy(value, memo)
        keep_alive.append(value)
        return copied

    return clone(state)


class Game:
    developer_drills = False
    def __init__(self, catalog=None, state=None, save_path=None):
        self.cat = catalog or Catalog(); self.s = state; self.save_path = Path(save_path) if save_path else None

    @classmethod
    def new(cls, route='R01', team='T01', pack='P1', seed=11, birth='MID', save_path=None, catalog=None, case_mode='NONE',difficulty='D0', campaign_mode=False):
        game = cls(catalog=catalog, save_path=save_path)
        c = game.cat; spec, members, budget = c.team(team, birth)
        route_data = next(r for r in c.config['routes'] if r['route_id'] == route)
        require(set(route_data['facts']) <= set(spec['facts']), '该试验队伍未取得路线要求的许可，请选择对应阶段队伍。')
        pack_data = next(p for p in c.config['packs'] if p['pack_id'] == pack)
        # Owned test fixture, explicitly distinct from the natural campaign economy.
        bank = {'copper': 60, 'crystal': 12, 'supply': 6}
        warehouse = {k: 24 for k in ['herb', 'fiber', 'iron', 'crystal_shard']}
        for item in pack_data['items']:
            recipe = c.recipes['RC-' + item]; bank['copper'] -= recipe['copper']
            for k, v in recipe['materials'].items(): warehouse[k] -= v
        bank['supply'] -= pack_data['paid_medical_supply_carried']
        game.s = {'version': VERSION, 'id': uuid.uuid4().hex, 'source_sha256': c.hashes, 'runtime_sha256': c.runtime_hashes,
                  'phase': 'TOWN', 'seed': int(seed), 'route': route, 'team_id': team, 'pack': pack, 'birth': birth,
                  'fixture_notice': '拥有指定队伍和装备的试验档；初始60铜/12晶/6补给及每种24材料，工坊Lv2。不是自然开局或获取难度结论。',
                  'bank': bank, 'warehouse': warehouse, 'party': members, 'budget': budget,
                  'pouch': list(pack_data['items']), 'used_prep_slots': 0, 'preparations': {},
                  'medical': pack_data['paid_medical_supply_carried'], 'manifest': None, 'request': None,
                  'region': None, 'visited_regions': [], 'site': None, 'regions': {}, 'pending': {'copper': 0, 'crystal': 0},
                  'materials': {}, 'gear_bag': [], 'plans_owned': [], 'plans_equipped': [], 'notes': [],
                  'plan_offers':{},'plan_undo':None,'plan_spell_seen':False,
                  'debits': {}, 'battle': None, 'battle_reports': [], 'journal': [], 'completed_regions': [],
                  'summary': None, 'debug_tainted': False, 'sequence': 0, 'day': 0, 'completed_history': [], 'event_memory': {},
                  'difficulty':difficulty,'quality_pity':{'q1':0,'non_q3':0},'case_mode':case_mode}
        town.initialize(game,spec)
        if campaign_mode:
            game.s['party']=[]
        else:tiers.check(difficulty,game.s['unlocked_facts'])
        skill_books.initialize(game)
        equipment.initialize(game)
        workshop.initialize(game)
        construction.initialize(game)
        outfitting.initialize(game)
        event_conditions.initialize(game)
        rogue_events.initialize(game)
        facilities.initialize(game)
        supplies.initialize(game)
        book_rewards.initialize(game)
        learning.initialize(game)
        require(case_mode in ('NONE','BOTH','ALL')+cases.ALL_IDS,'事件试验支持 NONE / EV03 / EV09 / 十项事件ID / BOTH / ALL。')
        refugee.initialize(game.s,case_mode in ('EV03','BOTH','ALL'))
        water.initialize(game.s,case_mode in ('EV09','BOTH','ALL'))
        medicine.initialize(game.s,case_mode in ('EV19','ALL'))
        cases.initialize(game.s,list(cases.CONFIG) if case_mode=='ALL' else [case_mode])
        if campaign_mode:campaign.initialize(game)
        research.initialize(game)
        finale.initialize(game)
        recovery.initialize(game)
        missing.initialize(game)
        drills.initialize(game)
        hidden_thread.initialize(game)
        import save_validation
        save_validation.initialize_enrollment(game)
        narrative.initialize(game)
        game.log('campaign_created' if campaign_mode else 'fixture_created', route=route, team=team, pack=pack, seed=seed)
        game.persist(); return game

    @classmethod
    def new_campaign(cls, seed=11, save_path=None, catalog=None):
        return cls.new(seed=seed,pack='P0',save_path=save_path,catalog=catalog,case_mode='ALL',campaign_mode=True)

    @classmethod
    def load(cls, path, catalog=None):
        raw,state = save_storage.read(path)
        try:game=cls.from_state(state,catalog,path)
        except (KeyError,TypeError,IndexError,AttributeError) as exc:
            raise ValueError('存档结构不完整或字段类型异常；原件未改动，可用 save_tools.py inspect 检查备份。') from exc
        archive_cache.seal_validated(game.s,decoded_json=True)
        archive_cache.seal_loaded_journal(game.s)
        archive_cache.warm_archives(game.s)
        game._disk_snapshot=(str(Path(path).resolve()),save_storage.digest(raw))
        game._backup_signature=(game._disk_snapshot,save_storage._backup_state_digest(game.s))
        finale.warm_retry_checkpoint(game)
        return game

    @classmethod
    def from_state(cls, state, catalog=None, path=None):
        game = cls(catalog, state, path)
        import save_validation
        require(state.get('version') == VERSION, '存档版本不兼容；0.98仅新建档，请使用匹配的0.97旧入口；原档未修改。')
        save_validation.validate(game)
        require(bool(state.get('developer_drill_only')) == cls.developer_drills, '开发演练与正常周目存档不可互载；演练仅使用drill_lab.py。')
        require(state['version'] == VERSION, '存档版本不兼容；请另建试验档。')
        require(state['source_sha256'] == game.cat.hashes, '设计数据已变化，拒绝混用旧试验存档；请保留旧档并新建试验。')
        if state.get('runtime_sha256') != game.cat.runtime_hashes:
            # Exact pre-correction 0.49 build only. No gameplay/state schema change:
            # preserve every saved business field and refresh only its code stamp.
            profile=BASE/'compatibility/v049_before_rescue_entry.json'
            prior=json.loads(profile.read_text(encoding='utf-8')) if profile.exists() else None
            presentation_files={'engine.py','clues.py','missing.py','rescue.py','facilities.py','app.py'}
            compatible=(VERSION=='TINDER-GREYBOX-0.49' and prior is not None
                        and state.get('runtime_sha256')==prior
                        and set(prior)==set(game.cat.runtime_hashes)
                        and all(prior[n]==v for n,v in game.cat.runtime_hashes.items() if n not in presentation_files))
            require(compatible,'灰盒代码版本已变化；旧记录保留供查阅，请使用匹配版本或新建试验。')
            state['runtime_sha256']=deepcopy(game.cat.runtime_hashes)
        equipment.validate(game)
        plan_offers.validate(game)
        skill_books.validate(game)
        book_combat.validate_battle(game.s.get('battle'))
        book_rewards.validate(game)
        heroes.validate(game)
        bosses.validate(game.s.get('battle'))
        boss_threats.validate(game.s.get('battle'),game.cat)
        import expedition_peril
        expedition_peril.validate_game(game)
        campaign.validate(game)
        facilities.validate(game)
        supplies.validate(game)
        learning.validate(game)
        research.validate(game)
        hidden_thread.validate(game)
        finale.validate(game)
        recovery.validate(game)
        missing.validate(game)
        drills.validate(game)
        region_space.validate(game)
        narrative.validate(game)
        event_conditions.validate(game)
        rogue_events.validate(game)
        challenge_rewards.validate(game)
        require(state.get('difficulty') in tiers.TIERS,'档位存档无效。')
        require(all(type(state.get('quality_pity',{}).get(k)) is int and state['quality_pity'][k]>=0 for k in ('q1','non_q3')),'品质保底存档无效。')
        if state.get('mission')=='ORDINARY' and state.get('manifest') and state['phase']!='TOWN':
            require(state['manifest']['tier']['id']==state['difficulty']==state['manifest']['loot_policy']['difficulty'],'档位与锁定奖励不一致。')
        return game

    def persist(self):
        import save_validation
        save_validation.validate(self)
        equipment.validate(self)
        plan_offers.validate(self)
        skill_books.validate(self)
        book_combat.validate_battle(self.s.get('battle'))
        book_rewards.validate(self)
        heroes.validate(self)
        bosses.validate(self.s.get('battle'))
        boss_threats.validate(self.s.get('battle'),self.cat)
        import expedition_peril
        expedition_peril.validate_game(self)
        campaign.validate(self)
        facilities.validate(self)
        supplies.validate(self)
        learning.validate(self)
        research.validate(self)
        hidden_thread.validate(self)
        finale.validate(self)
        recovery.validate(self)
        missing.validate(self)
        drills.validate(self)
        region_space.validate(self)
        narrative.validate(self)
        event_conditions.validate(self)
        rogue_events.validate(self)
        challenge_rewards.validate(self)
        if self.save_path:
            archive_cache.seal_validated(self.s)
            save_storage.save(self,atomic_json)

    def build_manifest(self, guaranteed_case=None):
        s=self.s
        return self.cat.manifest(
            s['route'],s['seed'],event_memory.presented_history(self),
            s['refugee'],s['directed_refugee'],s['water'],s['directed_water'],
            s['medicine'],s['directed_medicine'],s['cases'],s['directed_local'],
            difficulty=s['difficulty'],tier_facts=s['unlocked_facts'],
            campaign_facts=s['unlocked_facts'] if campaign.active(self) else None,
            guaranteed_case=guaranteed_case)

    def log(self, kind, **details):
        self.s['sequence'] += 1
        self.s['journal'].append({'seq': self.s['sequence'], 'type': kind, 'region': self.s.get('region'), 'site': self.s.get('site'), 'day':self.s.get('day',0), 'expedition_no':self.s.get('expedition_no',1), **details})

    def execute(self, command):
        """Any validation or disk failure rolls back ALL changes, including receipts."""
        before = _snapshot_state(self.s)
        try:
            equipment.validate(self)
            parts = shlex.split(command)
            require(parts, '请输入命令。')
            result = self.dispatch(parts[0].lower(), parts[1:])
            if before['phase']=='TOWN' and self.s['phase'] in ('EXPLORE','BATTLE','MISSING_SEARCH'):
                outfitting.depart(self)
                facilities.depart(self)
                if self.s['phase']=='BATTLE':
                    outfitting.start_battle(self,self.s['battle'])
                    facilities.start_battle(self,self.s['battle'])
            if self.s['battle'] and (not before.get('battle') or before['battle']['battle_id'] != self.s['battle']['battle_id']):
                event_conditions.start_battle(self,self.s['battle'])
            if self.s['finale']['ending'] and not before['finale']['ending']:
                self.s['finale']['expired_conditions']=event_conditions.settle(self,'FINALE_ENDED')
            hidden_thread.sync(self)
            narrative.sync(self,before,[parts[0].lower()]+parts[1:],result)
            if self.s != before: self.log('command_committed', command=command)
            self.persist()
            return result or '已完成。'
        except Exception:
            self.s = before
            raise

    @property
    def current(self): return self.s['regions'][self.s['region']]
    @property
    def manifest_region(self): return self.s['manifest']['regions'][self.s['region']]
    @property
    def layout(self): return self.cat.layouts[self.manifest_region['template_id']]

    def noncombat(self): require(self.s['phase'] == 'EXPLORE', '需要处于远征非战斗状态。')

    def member(self, key):
        matches = [m for m in town.available(self) if m['instance_id'] == key or m['instance_id'].endswith('-' + key.zfill(2))]
        require(len(matches) == 1, '队员不存在；使用名单中的完整ID或实例编号后缀。')
        return matches[0]

    def standing(self, key):
        m = self.member(key); require(m['hp'] > 0, '倒地队员不是合法目标。')
        require(self.s['phase']=='TOWN' or m in self.s['party'],'不能在野外操作留城人员。'); return m

    def erosion(self, delta, standing_only=False):
        for m in self.s['party']:
            if not standing_only or m['hp'] > 0: m['erosion'] = max(0, min(100, m['erosion'] + delta))

    def heal(self, members, fraction=None, amount=None):
        receipts = []
        for m in members:
            if m['hp'] <= 0: continue
            maximum = amount if amount is not None else max(1, math.floor(m['stats']['hp']*fraction))
            maximum = gear_affixes.received_recovery(m,maximum)
            effective = min(maximum, m['stats']['hp'] - m['hp'])
            if effective > 0: m['hp'] += effective; receipts.append({'id': m['instance_id'], 'heal': effective})
        return receipts

    def validate_deployment(self, board=None):
        from balance_v062 import unit_cost
        require(all(type(m['cost']) is int and m['cost']==unit_cost(m) for m in self.s['party']),'人员Cost必须符合兵种1／佣兵2／英雄4。')
        require(not facilities.training_ids(self)&{m['instance_id'] for m in self.s['party']},'补训者本次行动必须留城。')
        require(0<len(self.s['party']) and sum(m['cost'] for m in self.s['party'])+self.s['escort_reserved_cost']<=self.s['budget']['expedition'],'出征Cost不合法；护送离队不返还本趟Cost。')
        require(all(m['injury_days']==0 for m in self.s['party']),'有伤员尚未恢复；请让其留城或先结算休整。')
        deployed = [m for m in self.s['party'] if m['deployed']]
        import expedition_peril
        expedition_peril.check_deployment(self)
        require(bool(deployed) and sum(m['cost'] for m in deployed) <= self.s['budget']['battle'], '部署Cost不合法。')
        bad=[m['instance_id'] for m in deployed if m['hp']<=0 or m['erosion']>=100]
        require(not bad, '部署中有倒地或侵蚀100：'+'、'.join(bad)+'；先 deploy 该ID off 或换预备。')
        positions = [tuple(m['position']) for m in deployed]
        require(len(set(positions)) == len(positions), '部署格重复，请重新布阵。')
        allowed = {tuple(p) for p in self.cat.boards[board or 'OPEN']['player_deploy_cells']}
        require(all(p in allowed for p in positions), '部署格不属于当前棋盘的己方部署区：'+str(self.cat.boards[board or 'OPEN']['player_deploy_cells']))
        if board:
            terrain = {(c['q'], c['r']): c['terrain_id'] for c in self.cat.boards[board]['cells']}
            require(all(self.cat.terrain[terrain[p]]['walkable'] for p in positions), '部署落在不可行走的地形上。')

    def enter_region(self, rid):
        require(rid not in self.s['visited_regions'], '本趟已进入过该地区，不能重建现场或重复增长。')
        book_rewards.leave_site(self,self.s.get('region'),self.s.get('site'))
        event_conditions.enter_region(self,rid)
        growth = depth_growth.freeze_region(self, rid)
        import expedition_peril
        expedition_peril.freeze(self,growth,rid)
        self.s.update(region=rid, site='I', phase='EXPLORE')
        self.s['visited_regions'].append(rid)
        self.s['regions'][rid] = {'cleared': [], 'seen': ['I'], 'revealed_battles': [], 'station_used': False,
                                 'camp_used': False, 'deployed_here': [], 'variant': None, 'growth': growth,
                                 'events': {slot: {'state': 'UNSEEN', 'steps': [], 'receipt': None} for slot in self.s['manifest']['regions'][rid]['events']}}
        if self.s['mission'] in ('ORDINARY','TUTORIAL'):region_space.generate(self)
        self.erosion(self.cat.multi['erosion']['first_danger_entry_per_region_instance'])
        self.log('enter_region', erosion_delta=5, effective_threat=growth['effective_threat'],
                 native_minimum=growth['native_minimum'], growth_rule_version=growth['rule_version'])

    def arrive(self,destination,origin=None):
        s=self.s
        if destination!=s.get('site'):book_rewards.leave_site(self,s.get('region'),s.get('site'))
        s['previous_site'] = origin; s['site'] = destination
        if destination not in self.current['seen']: self.current['seen'].append(destination)
        if destination in self.manifest_region['encounters']:
            if destination not in self.current['cleared']:s['plan_undo']=None
            if destination not in self.current['revealed_battles']:self.current['revealed_battles'].append(destination)
        if destination in self.current['events'] and self.current['events'][destination]['state'] == 'UNSEEN':
            self.current['events'][destination]['state'] = 'OPEN'
            self.log('event_presented', event=self.manifest_region['events'][destination]['event_id'])
            event_memory.record(self)
            refugee.seen(self)
            water.seen(self)
            medicine.seen(self)
            for eid in cases.CONFIG:cases.seen(self,eid)
        plan_offers.freeze(self)
        learning.passage(self,origin,destination)
        self.log('walk', origin=origin, destination=destination)
        return '到达 ' + destination

    def event_info(self):
        self.noncombat(); slot = self.s['site']
        require(slot in self.manifest_region['events'], '当前位置没有事件。')
        binding = self.manifest_region['events'][slot]
        state = self.current['events'][slot]
        event = deepcopy(event_memory.card(self.cat.events[binding['event_id']], binding))
        event = rogue_events.card(self,event,binding)
        if event['event_id'] in cases.CONFIG:event['scene']=cases.scene_text(self,event['event_id'])
        if event['event_id']=='EV03': event['scene']=refugee.scene_text(self)
        if event['event_id']=='EV09': event['scene']=water.scene_text(self)
        if event['event_id']=='EV19': event['scene']=medicine.scene_text(self)
        return event, binding, state

    def debit(self, debits, cargo=False):
        for key, amount in debits.items():
            reserved = water.reserved(self) if key=='material_units' and not cargo else 0
            require(self.s['debits'].get(key, 0) + amount + reserved <= self.s['manifest']['caps'].get(key, 0), f'本趟{key}额度不足。可以暂离或选择其他方案。')
        for key, amount in debits.items(): self.s['debits'][key] = self.s['debits'].get(key, 0) + amount

    def offer(self, event, option):
        return plan_offers.offer(self,event,option)

    def grant(self, bundle_id, context, chosen_plan=None):
        bundle = self.cat.bundles[bundle_id]; effect = bundle['effect']; kind = effect['type']
        self.debit(bundle['budget_debits'])
        rng = keyed_rng(self.s['seed'], f"{self.s['region']}:{self.s['site']}:{bundle_id}:{context.get('option_id', '')}")
        if kind == 'eligible_region_materials':
            if supplies.material_reward(self,bundle_id,context):return
            weights = next(w['weights'] for w in self.cat.loot['region_material_weights'] if w['region_id'] == self.s['region'])
            for material in rng.choices(list(weights), list(weights.values()), k=effect['units']):
                self.s['materials'][material] = self.s['materials'].get(material, 0) + 1
        elif kind == 'carried_operating_resource':
            for key in ['copper', 'crystal']: self.s['pending'][key] += effect[key]
        elif kind == 'grant_existing_consumable':
            require(len(self.s['pouch']) + self.s['used_prep_slots'] < 4, '携行袋已满；暂离后腾出空间可回来领取。')
            self.s['pouch'].append(effect['consumable_id'])
        elif kind == 'existing_plan_offer':
            plan_offers.freeze(self)
            event, _, _ = self.event_info(); choices = self.offer(event, context)
            require(chosen_plan in choices, '请指定方案：' + ', '.join(choices) + '；例如 choose PRIMARY 01 PL01。')
            require(chosen_plan not in self.s['plans_owned'], '已经拥有该方案，可选其他方案或暂离。')
            self.s['plans_owned'].append(chosen_plan)
        elif kind == 'fixed_template_gear_drop':
            gear_effect = next((e for e in context.get('effects', []) if e.get('bundle_id') == bundle_id), {})
            families = gear_effect.get('family_pool', ['EF01', 'EF03', 'EF07'])
            quality_quote=tiers.quality(self,gear_effect.get('quality_band','salvage'))
            weights=quality_quote['effective_weights']
            quality = rng.choices(list(weights), list(weights.values()))[0]
            template=rng.choice(families)+'-'+quality
            reward_key=f"{self.s['expedition_no']}:{self.s['region']}:{self.s['site']}:{bundle_id}:{gear_effect.get('claim_slot','primary')}"
            item=equipment_rolls.drop(self,template,
                {'kind':'existing_event_drop','bundle':bundle_id,'region':self.s['region'],'site':self.s['site'],
                 'expedition_no':self.s['expedition_no'],'randomized':True},reward_key)
            tiers.claimed(self,quality)
            self.log('quality_claim',item=item['instance_id'],quality=quality,quote=quality_quote,after_pity=deepcopy(self.s['quality_pity']))
            self.log('gear_received',item=item['instance_id'],template=item['template_id'],destination='gear_bag')
        else: raise ValueError('此奖励尚未接入灰盒：' + kind)

    def choose(self, option_id, target='01', plan=None):
        if option_id=='BOOK':return supplies.claim_book(self)
        event, binding, state = self.event_info()
        if event['type']=='humanity' and option_id!='PASS':
            raise ValueError('请使用该事件的护送／装载／交易专用入口；许诺不算完成交付。')
        if option_id == 'PASS':
            self.log('event_suspend', event=event['event_id'], progress=state['steps']); return '已暂离；本区回访保留进度。'
        if state['state'] in ['RESOLVED', 'DECLINED']: return '事件已有最终结果，不会重复结算。'
        require(option_id in binding['enabled_options'], '该选项受到出发时预算限制：' + str(binding['disabled_options'].get(option_id)))
        option = next(o for o in event['options'] if o['option_id'] == option_id)
        require(not (state['state'] == 'ACTIVE' and option_id != 'PRIMARY'), '已经开始拓印，不能改领另一互斥结果；可以暂离。')
        if event['event_id'] == 'EV04' and option_id == 'PRIMARY':
            require(set(state['steps']) == {'bell_1', 'bell_2'}, '需要在此事件使用 rub 1 和 rub 2 完成两处拓印，可中途暂离。')
        costs = option['costs']
        copper = costs.get('banked_copper', 0)
        require(self.s['bank']['copper'] >= copper, '已入库铜不足，不能使用途中待结算佣金。')
        self.s['bank']['copper'] -= copper
        materials = dict(costs.get('carried_materials', {}))
        if costs.get('carried_material_units_selected'):
            remaining = costs['carried_material_units_selected']
            # Explicit selection via material1,material2,... argument, never silently choose rare inputs.
            selected = target.split(','); require(len(selected) == remaining, '请输入4份材料名，用逗号分隔，例如 fiber,fiber,iron,herb。')
            materials = dict(Counter(selected))
        for material, amount in materials.items():
            require(self.s['materials'].get(material, 0) >= amount, f'实际携带{material}不足{amount}，可暂离后寻找。')
            self.s['materials'][material] -= amount
        for item, amount in costs.get('carried_consumables', {}).items():
            require(self.s['pouch'].count(item) >= amount, '缺少未使用的消耗品：' + item)
            for _ in range(amount): self.s['pouch'].remove(item)
        result_message = None
        for effect in option['effects']:
            kind = effect['type']
            if kind in ['claim_reward', 'existing_plan']: self.grant(effect['bundle_id'], option, plan)
            elif kind == 'erosion': self.erosion(effect['amount'])
            elif kind == 'record_note': self.s['notes'].append(effect['note_id'])
            elif kind == 'event_heal_fraction':
                m = self.standing(target); healed = self.heal([m], effect['numerator']/effect['denominator'])
                require(healed, '没有实际治疗效果，不扣额度、不关闭事件。'); self.debit(effect['budget_debits'])
            elif kind == 'event_erosion_relief':
                require(any(m['hp'] > 0 and m['erosion'] > 0 for m in self.s['party']), '当前没有侵蚀可降低。')
                self.erosion(-effect['amount'], standing_only=True); self.debit(effect['budget_debits'])
            elif kind == 'event_hp_exertion':
                m = self.standing(target); loss = max(1, math.ceil(m['stats']['hp']*effect['loss_numerator']/effect['loss_denominator']))
                require(m['hp'] > loss, '该队员无法安全承担搬运消耗。'); m['hp'] -= loss
            elif kind == 'craft_event_consumable':
                require(len(self.s['pouch']) + self.s['used_prep_slots'] < 4, '携行袋已满；已使用准备品仍占位。')
                self.s['pouch'].append(self.cat.recipes[effect['recipe_id']]['output_id'])
            elif kind == 'reveal_existing_node_detail':
                require('B2' not in self.current['revealed_battles'], '目标已经揭示，没有新的侦察效果。')
                self.current['revealed_battles'].append('B2')
            elif kind == 'commit_prelocked_encounter_variant':
                require('B1' not in self.current['revealed_battles'], '目标已揭示或开战，不能再改换巡队。')
                require(effect['candidate_encounter_id'] in self.manifest_region['encounters']['B1']['candidate_ids'], '候选不属于已锁定敌阵。')
                self.current['variant'] = effect['candidate_encounter_id']
            elif kind == 'journey_choice':
                event_conditions.choose(self,effect['choice'],target)
            elif kind == 'rogue_choice':
                result_message = rogue_events.choose(self,target)
            else: raise ValueError('此效果尚未接入：' + kind)
        state.update(state='RESOLVED', receipt={'option': option_id, 'target': target, 'plan': plan})
        self.log('event_committed', event=event['event_id'], receipt=state['receipt'], costs=costs)
        event_memory.record(self)
        supplies.award_material_bonus(self)
        return result_message or option['result_text']

    def finish_battle(self):
        b = self.s['battle']; require(b and b['result'], '战斗尚未结束。')
        event_conditions.finish_battle(self,b)
        if self.s['mission']=='FINALE':return finale.finish_battle(self)
        plan_offers.seen_battle(self,b)
        if not self.s['debug_tainted']:
            for uid,receipt in b.get('boss_receipts',{}).items():
                self.s.setdefault('boss_records',{}).setdefault(uid,deepcopy(receipt))
        self.s['downed_this_trip']=sorted(set(self.s['downed_this_trip'])|{a['id'] for a in b['actors'] if a['side']=='player' and (a['hp']<=0 or a.get('downed_tick') is not None)})
        for actor in b['actors']:
            if actor['side'] == 'player':
                member=self.member(actor['id']); member['hp'] = actor['hp']
                if member['hp']<=0: member['deployed']=False
        import expedition_peril
        expedition_peril.settle_battle(self,b)
        self.erosion(self.cat.multi['erosion']['per_actual_battle_result'])
        slot = self.s['site']; self.s['phase'] = 'EXPLORE'
        b['after'] = deepcopy(self.s['party']); b['logical_seconds'] = b['tick']*.5
        b['debug_tainted'] = self.s['debug_tainted']
        self.s['battle_reports'].append(deepcopy(b)); self.s['battle'] = None
        self.log('battle_result', result=b['result'], ticks=b['tick'], encounter=b['encounter_id'])
        campaign.after_battle(self,b)
        book_rewards.battle_victory(self,b)
        facilities.record_battle(self,b)
        learning.completed(self,b)
        # Only deployed members consume their next-battle preparation; reserves retain theirs.
        for actor in b['actors']:
            if actor['side'] == 'player': self.s['preparations'].pop(actor['id'], None)
        if self.s['mission']=='RESCUE' and b['result']=='VICTORY':
            rescue.finish_success(self);return
        if recovery.finish_battle(self,b):return
        if story_mission.finish_battle(self,b):return
        if b['result'] == 'VICTORY':
            require(slot not in self.current['cleared'], '此敌阵已结算。')
            self.current['cleared'].append(slot)
            if slot == 'G':
                self.s['completed_regions'].append(self.s['region'])
                reward = self.manifest_region['combat_rewards']['G']
                for k, v in reward['pending_commission'].items(): self.s['pending'][k] += v
                for bundle in reward['bundle_ids']: self.grant(bundle, {})
                challenge_rewards.award_goal(self,b)
            elif slot == 'L':
                for k, v in self.manifest_region['combat_rewards']['L']['actual_win_increment'].items(): self.s['pending'][k] += v
                supplies.award_material_bonus(self)
        elif b['result'] == 'RETREAT':
            self.settle_return('COMBAT_RETREAT')
        else:
            rescue.settle_defeat(self)

    def settle_return(self, reason='SAFE_RETURN', *, defer_ending=False):
        book_rewards.leave_site(self,self.s.get('region'),self.s.get('site'))
        refugee.before_settlement(self, True)
        cases.before_settlement(self, True)
        water.before_settlement(self, True)
        s = self.s; returned = deepcopy(s['pending'])
        import expedition_peril
        rested_unfit=expedition_peril.clear(self,reason)
        for k, v in returned.items(): s['bank'][k] += v
        for k, v in s['materials'].items(): s['warehouse'][k] = s['warehouse'].get(k, 0) + v
        # A safely carried downed person is returned, not killed or replaced.
        for rid in s['completed_regions']:
            for m in s['party']:
                if m['instance_id'] in s['regions'][rid]['deployed_here']:m['xp']+=1
        s['bank']['supply'] += s['medical']; s['medical'] = 0
        before_treatment,downed=town.safe_return_health(self)
        escorted=escort.settle(self)
        self.erosion(-20); s['phase'] = 'RETURNED'
        s['summary'] = {'result': reason, 'completed_regions': s['completed_regions'][:], 'banked': returned,
                        'materials': deepcopy(s['materials']), 'battles': len(s['battle_reports']),
                        'returned_loose_equipment': s['gear_bag'][:], 'returned_consumables': s['pouch'][:],
                        'logic_seconds': sum(b['logical_seconds'] for b in s['battle_reports']),
                        'balance_eligible': False, 'debug_tainted': s['debug_tainted'], 'day': s['day'],
                        'returned_downed': downed, 'before_town_recovery':before_treatment,
                        'expired_plans':s['plans_owned'][:],
                        'post_return_injury_treatment': 'STANDING_FULL_HP_DOWNED_TIMED_RECOVERY'}
        s['summary']['settlement_id']=s['last_settlement_id']
        challenge_summary=challenge_rewards.settle(self,True,reason)
        if challenge_summary is not None:s['summary']['challenge_rewards']=challenge_summary
        material_summary=supplies.settle_material_bonus(self,True,reason)
        if material_summary is not None:s['summary']['material_commission_bonus']=material_summary
        s['summary']['rested_unfit']=rested_unfit
        s['summary']['escorted_home']=escorted
        s['summary']['expired_conditions']=event_conditions.settle(self,reason)
        s['pending'] = {'copper': 0, 'crystal': 0}; s['materials'] = {}; s['preparations'] = {}; s['used_prep_slots'] = 0
        s['plans_owned']=[];s['plans_equipped']=[];s['plan_undo']=None
        self.log('safe_return', summary=s['summary'])
        campaign.on_return(self)
        supplies.settle(self,True)
        if not defer_ending:rescue.check_ending(self)

    def dispatch(self, command, args):
        s = self.s
        require(not self.s.get('developer_drill_only'), '开发演练存档不能推进正式周目。')
        require(command!='drill', '完整演练仅供开发测试，正常周目不开放。')
        if command=='dialogue':return narrative.handle(self,args)
        if command=='intel':
            require(len(args)<=1,'intel [已公开敌阵节点]：查看实际冻结敌情。')
            return enemy_intel.describe(self,args[0].upper() if args else None)
        if command=='thread' and (not args or args[0] in ('status','read')):
            return hidden_thread.handle(self,args)
        if command=='conditions':
            require(args in ([],['status']),'conditions status：查看本趟状态；处理状态需到休整事件。')
            return event_conditions.describe(self)
        if command=='fortune':
            require(args in ([],['status']),'fortune status：查看当前行军约定与现场候选。')
            return rogue_events.describe(self)
        if command=='finale':return finale.handle(self,args)
        if command=='rescue' and args in ([],['status']):return rescue.describe(self)
        if command=='rescue' and args and args[0]=='investigate':command,args='missing',args[1:]
        if command=='clue' and args in ([],['status']):return clues.describe(self)
        if command=='missing' and args in ([],['status']):return missing.describe(self)
        if s['finale']['ending']:raise ValueError('本轮结局已提交；finale status 可回看，不能修改。')
        if missing.state(self)['active']:
            require(command=='missing' or command=='clue' and args in ([],['status']),'调查专线请使用搜救所调查／返城入口；不能远程救人、招募或补给。')
        if recovery.state(self)['active']:
            require(command in ('recover','clue','step','run','flee','deploy','place','stance','skill'), '调查专线不能离线补给、换装或另开任务；recover status 查看继续／返城。')
            if command=='clue':require(args in ([],['status']),'调查途中只能查看线索册。')
        if s['mission']=='FINALE':
            require(command in ('step','run') and s['phase']=='BATTLE','终战只可使用finale命令及战斗step/run；不能补给、换装、撤退或回城。')
        if campaign.active(self) and s['campaign']['remembrance']:
            require(command=='remember' or (command=='quest' and args in ([],['status'])), '先完成或关闭当前追忆：remember close。')
        if command=='quest' and args in ([],['status']):return campaign.handle(self,command,args)
        if command=='thread':return hidden_thread.handle(self,args)
        if command=='difficulty':
            if not args:return tiers.describe(self)
            require(s['phase']=='TOWN','只能在城镇、出发前选择档位。')
            require(len(args)==1,'difficulty D0/D1/D2')
            difficulty=args[0].upper();tiers.check(difficulty,s['unlocked_facts'])
            s['difficulty']=difficulty;self.log('difficulty_selected',difficulty=difficulty)
            return tiers.describe(self)
        if command=='gear' and args==['list']:return equipment.describe(self)
        if command=='workshop' and args==['status']:return workshop.describe(self)
        if command=='construction' and args==['status']:return construction.describe(self)
        if command=='outfit' and args==['status']:return outfitting.describe(self)
        require(s['phase']!='FIN_C','本轮已结束：整份人类名册已永久损失。请另建独立试验。')
        if command in ('quest','summon','companion','challenge','remember'):return campaign.handle(self,command,args)
        if command in ('research','agla'):return research.handle(self,command,args)
        if command=='clue':return clues.handle(self,args)
        if command=='recover':return recovery.handle(self,args)
        if command=='missing':return missing.handle(self,args)
        if command=='tutorial':return story_mission.handle(self,args)
        if command=='facility':return facilities.handle(self,args)
        if command=='service':return facilities.service(self,args)
        if command=='scout':return facilities.scout(self,args)
        if command=='supply':return supplies.handle(self,args)
        if command=='workshop':return workshop.handle(self,args)
        if command=='construction':return construction.handle(self,args)
        if command=='outfit':return outfitting.handle(self,args)
        if command in ('equip','unequip','gear'):return equipment.handle(self,command,args)
        if command=='escort':return escort.handle(self,args)
        if command=='event':return cases.handle(self,args)
        if command=='case':return refugee.handle(self,args)
        if command=='water':return water.handle(self,args)
        if command=='medicine':return medicine.handle(self,args)
        if command in rescue.COMMANDS:return rescue.handle(self,command,args)
        if command == 'memory':
            require(s['phase']=='BATTLE' and len(args)==2,'memory evidence/retain/skip 窗口ID')
            bosses.dialogue(s['battle'],args[0],args[1])
            if s['battle']['result']:self.finish_battle()
            return '记忆窗口已提交；未推进逻辑拍。'
        if command == 'hero':return heroes.configure(self,args)
        if command == 'learning':return learning.handle(self,args)
        if command == 'book':
            if args and args[0].lower() in ('target','task','choice','claim','drop','status'):
                return book_rewards.handle(self,args)
            return skill_books.handle(self,args)
        if command in town.COMMANDS:return town.handle(self,command,args)
        if command == 'depart':
            require(s['phase'] == 'TOWN', '请先进入城镇整备；安全归城后使用 town。')
            rescue.confirm_day(s,args)
            if campaign.active(self):
                require('ST-102' in s['campaign']['facts'],'先用 tutorial start 完成固定侦路；普通短途在ST-102后开放。')
                route=next(r for r in self.cat.config['routes'] if r['route_id']==s['route'])
                require(set(route['facts'])<=set(s['unlocked_facts']),'缺少路线实际许可。')
                require(not s['route'].startswith('HUNT-') or s['campaign']['challenge']==s['route'][5:],'请用 challenge 选定讨伐。')
            self.validate_deployment()
            candidates=cases.guarantee_candidates(self) if campaign.active(self) else []
            attempts=list(candidates)+[None]
            manifest=request=None;last_error=None
            for candidate in attempts:
                try:
                    manifest,request=self.build_manifest(candidate)
                    break
                except ValueError as exc:
                    last_error=exc;continue
            if manifest is None:raise last_error
            guarantee=request.get('case_guarantee') if request else None
            if guarantee:self.log('case_guarantee',event=guarantee,expedition=s['expedition_no'])
            target=s.get('case_mode')
            if target not in (None,'NONE','BOTH','ALL'):
                present=any(binding.get('event_id')==target for region in manifest['regions'].values()
                            for binding in region['events'].values())
                require(present,f"当前 route/team/seed 组合不含 {target}；请使用 --route/--team/--seed 指定已知可达组合，"
                                f"或先在自然流程中遇见该案后用 event {target} visit CONFIRM。尚未扣出发物资。")
            campaign.bind_challenge(self,manifest)
            supplies.bind(self,manifest)
            learning.bind(self,manifest)
            event_memory.freeze(self, manifest)
            book_rewards.bind_manifest(self,manifest)
            require(s['bank']['supply'] >= manifest['departure_supply_cost'], '出发补给不足。')
            s['bank']['supply'] -= manifest['departure_supply_cost']; s['manifest'] = manifest; s['request'] = request
            hidden_thread.depart(self)
            self.enter_region(manifest['start'])
            return ('已出发，地图和随机结果已锁定。'
                    +(f" 本趟保底安排新道德线索：{guarantee}。" if guarantee else ''))
        if command in ('map','walk','walkto','interact'):return region_space.handle(self,command,args)
        if command == 'move':
            if region_space.active(self):
                require(len(args)==1,'move 地点ID');return region_space.legacy_move(self,args[0].upper())
            self.noncombat(); require(len(args) == 1, 'move 地点ID')
            destination = args[0].upper(); origin = s['site']
            require(origin not in self.manifest_region['encounters'] or origin in self.current['cleared'], '敌阵尚未处理；可 retreat 回到来路，不能穿过。')
            require(any(set(edge) == {origin, destination} for edge in self.layout['edges']), '只能沿本地图相邻道路移动。')
            return self.arrive(destination,origin)
        if command == 'retreat':
            if region_space.active(self):return region_space.retreat(self)
            self.noncombat(); require(s['site'] in self.manifest_region['encounters'] and s['site'] not in self.current['cleared'], '这里只用于接敌后不开战返回来路。')
            s['site'] = s['previous_site']; self.log('encounter_avoided'); return
        if command in ['deploy', 'place', 'stance', 'skill']:
            require(s['phase'] in ['TOWN', 'EXPLORE', 'RECOVERY_STOP'], '战中不能改编队。')
            require(len(args) >= 2, command + ' 队员 参数')
            m = self.member(args[0])
            require(m in s['party'],'请先通过 squad 完整ID on 将该人编入随行队伍。')
            if command == 'deploy':
                require(args[1] in ['on', 'off'], 'deploy 01 on/off')
                import expedition_peril
                require(args[1]=='off' or expedition_peril.deployable(m),'该队员本趟重创休战，需安全归城休整；可部署其他预备。')
                m['deployed'] = args[1] == 'on'
                deployed = [x for x in s['party'] if x['deployed']]
                require(sum(x['cost'] for x in deployed) <= s['budget']['battle'], '超过部署Cost；先取消另一人的部署。')
            elif command == 'place':
                require(len(args) in [3, 4], 'place 01 q r [朝向0..5]'); m['position'] = [int(args[1]), int(args[2])]
                bid = self.manifest_region['encounters'][s['site']]['board_id'] if s['phase']=='EXPLORE' and s['site'] in self.manifest_region['encounters'] else 'OPEN'
                require(m['position'] in self.cat.boards[bid]['player_deploy_cells'], '可用部署格：'+str(self.cat.boards[bid]['player_deploy_cells']))
                if len(args) == 4: require(0 <= int(args[3]) < 6, '朝向为0..5。'); m['facing'] = int(args[3])
            elif command == 'skill':
                require(m['unit_id'] in self.cat.rules['mercenaries'] or m['unit_id'] in heroes.IDS or m['unit_id']=='CMD', '请选择现役佣兵或英雄。')
                allowed = ('auto','mark','volley','off') if m['unit_id'] in ('CMD','H07') else ('counter','damage','off') if m['unit_id']=='M04' else ('auto','off')
                require(len(args)==2 and args[1] in allowed, 'skill 队员 '+ '/'.join(allowed))
                m['skill_mode']=args[1]
            else:
                require(args[1] in ['advance', 'hold', 'flank', 'evade'], 'stance 01 advance/hold/flank/evade'); m['stance'] = args[1]
            self.log(command, member=m['instance_id'], args=args[1:]); return
        if command == 'fight':
            self.noncombat(); slot = s['site']; require(slot in self.manifest_region['encounters'] and slot not in self.current['cleared'], '当前位置没有待战敌阵。')
            binding = self.manifest_region['encounters'][slot]
            eid = (self.current['variant'] or binding['default_encounter_id']) if slot == 'B1' else binding['encounter_id']
            self.validate_deployment(binding['board_id'])
            encounter = depth_growth.current_encounter(self, slot)
            s['battle'] = combat.create(self.cat, encounter, binding['board_id'], s['party'], s['seed'], s['plans_equipped'], s['preparations'],boss_context=s.get('boss_evidence'))
            outfitting.start_battle(self,s['battle'])
            facilities.start_battle(self,s['battle'])
            learning.battle_started(self,s['battle'])
            s['phase'] = 'BATTLE'
            region_space.bind_battle(self)
            self.current['deployed_here'] = sorted(set(self.current['deployed_here']) | {m['instance_id'] for m in s['party'] if m['deployed']})
            self.log('battle_started', encounter=eid, board=binding['board_id']); return '进入逐拍战斗；step 或 run。'
        if command in ['step', 'run', 'debug_win']:
            require(s['phase'] == 'BATTLE', '当前没有战斗。')
            if command == 'debug_win':
                require(args == ['CONFIRM'], '仅流程调试：debug_win CONFIRM；整个试验会标为使用作弊，不能用于平衡。')
                s['debug_tainted'] = True; s['battle']['result'] = 'VICTORY'; self.log('DEBUG_FORCED_VICTORY')
            else:
                count = int(args[0]) if args else (1 if command == 'step' else 120)
                require(1 <= count <= 600, '单次推进1至600拍。')
                start = time.perf_counter()
                for _ in range(count):
                    combat.step(self.cat, s['battle'])
                    narrative.windup(self)
                    if s['battle']['result'] or bosses.paused(s['battle']): break
                s['battle']['compute_seconds'] = s['battle'].get('compute_seconds', 0) + time.perf_counter() - start
            last_battle=s['battle']
            result=last_battle.get('result')
            if result: self.finish_battle()
            import battle_enrage
            if result:
                label={'VICTORY':'胜利','DEFEAT':'败北','RETREAT':'撤退'}.get(result,result)
                return f"战斗结束：{label}；本场{last_battle['tick']}拍。"
            return '战斗推进完成。未分胜负可继续；'+battle_enrage.describe(last_battle)
        if command == 'withdraw':
            require(s['phase'] == 'BATTLE' and args == ['CONFIRM'], 'withdraw CONFIRM：仅中止试验，不冒充撤退、归城或救援。')
            s['phase'] = 'ABORTED'; self.log('experiment_aborted_in_battle'); return
        if command == 'flee':
            require(s['phase'] == 'BATTLE' and args == ['CONFIRM'], 'flee CONFIRM：执行1拍公开追击，仍有人站立则全队安全返城，否则败战。')
            require(not bosses.paused(s['battle']),'先回应或跳过记忆窗口，再执行撤退追击。')
            s['battle']['retreat_requested'] = True
            combat.step(self.cat, s['battle']); self.finish_battle(); return '追击与返程已按实际结果结算。'
        if command == 'choose':
            require(args, 'choose PRIMARY/SECONDARY/PASS [队员01] [方案PLxx]')
            return self.choose(args[0].upper(), args[1] if len(args) > 1 else '01', args[2].upper() if len(args) > 2 else None)
        if command == 'rub':
            if region_space.active(self):region_space.prepare_rub(self,args)
            event, binding, state = self.event_info(); require(event['event_id'] == 'EV04' and state['state'] in ['OPEN', 'ACTIVE'], '此处没有未完成的双钟拓印。')
            require('PRIMARY' in binding['enabled_options'], '拓印选项受本趟预算限制，不能先提交中间步骤。')
            require(len(args) == 1 and args[0] in ['1', '2'], 'rub 1 或 rub 2')
            step = 'bell_' + args[0]
            if step not in state['steps']: state['steps'].append(step); self.log('event_step', step=step)
            state['state'] = 'ACTIVE'; event_memory.record(self)
            return '拓印已保存，可暂离；两份齐全后 choose PRIMARY 提交。'
        if command == 'decline':
            _, _, state = self.event_info(); require(args == ['CONFIRM'], 'decline CONFIRM 永久关闭本趟事件；普通离开用PASS。')
            require(state['state'] == 'OPEN', '已有持久进度或最终结果，不能按未开始事件放弃。')
            state['state'] = 'DECLINED'; self.log('event_declined'); event_memory.record(self)
            return '本趟已明确放弃该现场；案件仍保留，可回城续办。'
        if command in ['station', 'camp', 'medical']:
            self.noncombat()
            recovery_fraction=.3
            if command == 'station':
                require(s['site'] == 'S' and not self.current['station_used'], '需要到本区未使用的补给站S。')
                recovery_fraction=outfitting.station_rate(self)
                receipts = self.heal(s['party'], recovery_fraction); require(receipts, '全队没有可恢复生命，不消耗补给站。')
                outfitting.station_used(self,receipts); self.current['station_used'] = True
            elif command == 'camp':
                require(s['site'] == 'X' and 'G' in self.current['cleared'] and len(s['visited_regions']) < self.cat.multi['profiles'][s['manifest']['profile']]['region_count'] and not self.current['camp_used'], '需要在非末区已完成目标的出口，且本边界营地未用。')
                require(not args or len(args)==2 and args[0].upper()=='CLEANSE','camp 或 camp CLEANSE 状态ID：本次营地恢复和状态处理二选一。')
                if args:
                    removed=event_conditions.cleanse(self,args[1],source='CAMP')
                    self.current['camp_used']=True
                    learning.camp(self)
                    self.log('camp_condition_cleanse',condition=removed,forfeited_hp_fraction=.3,forfeited_erosion_relief=15)
                    return str(removed)
                receipts = self.heal(s['party'], .3); self.erosion(-15, standing_only=True); self.current['camp_used'] = True
                learning.camp(self)
            else:
                require(s['medical'] > 0, '没有额外医疗补给。'); receipts = self.heal(s['party'], .3)
                require(receipts, '没有合法治疗效果。'); s['medical'] -= 1
            self.log(command, effective_heal=receipts, recovery_fraction=recovery_fraction); return str(receipts)
        if command == 'use':
            require(s['phase'] in ['TOWN', 'EXPLORE'], '只能在战外使用。')
            require(args, 'use CO01 [队员01或逗号分隔多个队员]'); item = args[0].upper()
            require(item in s['pouch'], '没有该未使用物品。')
            effect = deepcopy(self.cat.items[item]['effect']); kind = effect['type']
            if kind == 'journey_condition_consumable':
                require(len(args)==1,'use '+item+'：全队准备品，无需指定单人目标。')
                result=event_conditions.use_item(self,item)
                self.log('item_used',item=item,targets='PARTY',condition=deepcopy(result))
                return str(result)
            ids = (args[1] if len(args) > 1 else '01').split(','); members = [self.standing(key) for key in ids]
            require(len({m['instance_id'] for m in members}) == len(members) <= effect['max_targets'], '目标重复或数量超限。')
            if kind in ['heal_flat', 'heal_fraction']:
                receipts = self.heal(members, amount=effect['amount']) if kind == 'heal_flat' else self.heal(members, effect['numerator']/effect['denominator'])
                require(receipts, '没有实际治疗效果，不消耗物品。')
            else:
                m = members[0]; preparations = s['preparations'].setdefault(m['instance_id'], [])
                group = effect.get('buff_id', effect.get('effect_id', kind))
                require(not any(p.get('buff_id', p.get('effect_id', p['type'])) == group for p in preparations), '已有同组准备；本灰盒不支持替换覆盖，请换目标或留到下一战。')
                preparations.append(effect); s['used_prep_slots'] += 1
            s['pouch'].remove(item); self.log('item_used', item=item, targets=ids); return
        if command == 'discard':
            require(s['phase'] in ['TOWN', 'EXPLORE'] and args, 'discard COxx：丢弃一个未使用物品。')
            item = args[0].upper(); require(item in s['pouch'], '未携带该物品。'); s['pouch'].remove(item); self.log('discard', item=item); return
        if command == 'craft':
            require(s['phase'] == 'TOWN' and args, '城内 craft CO01；野外需要到对应事件选择制作。')
            recipe = self.cat.recipes.get('RC-' + args[0].upper()); require(recipe is not None, '没有该配方。')
            require(s['workshop_level'] >= recipe.get('requires_building_level', 1), f"制作需要已竣工工坊Lv{recipe.get('requires_building_level', 1)}；在建等级不生效。")
            require(len(s['pouch']) + s['used_prep_slots'] < 4, '携行袋已满。')
            require(s['bank']['copper'] >= recipe['copper'], '铜不足。')
            for k, v in recipe['materials'].items(): require(s['warehouse'].get(k, 0) >= v, '仓库材料不足：' + k)
            s['bank']['copper'] -= recipe['copper']
            for k, v in recipe['materials'].items(): s['warehouse'][k] -= v
            s['pouch'].append(recipe['output_id']); self.log('town_craft', recipe=recipe['recipe_id']); return
        if command == 'plan':return plan_offers.configure(self,[a if a in ('clear','undo','list') else a.upper() for a in args])
        if command == 'next':
            self.noncombat(); require(len(args) == 2 and args[1] == 'CONFIRM', 'next RGxx CONFIRM：跨区后不能回到本区。')
            require(s['site'] == 'X' and 'G' in self.current['cleared'], '需要先完成本区目标并到出口X。')
            candidates = self.next_regions(); require(args[0] in candidates, '不属于当前前缀的合法后续区域：' + ','.join(candidates))
            self.log('region_sealed', pending_events=[k for k, v in self.current['events'].items() if v['state'] not in ['RESOLVED', 'DECLINED']])
            self.enter_region(args[0]); return
        if command == 'return':
            self.noncombat(); require(args == ['CONFIRM'], 'return CONFIRM：确认安全返城，本趟未完成事件封存。')
            require(s['site'] == 'I' or (s['site'] == 'X' and 'G' in self.current['cleared']), '请走回入口I或已完成目标的出口X返城。')
            self.settle_return(); return '已安全返城并一次性入账。'
        raise ValueError('未知命令：' + command)

    def next_regions(self):
        prefix = self.s['visited_regions']; n = len(prefix)
        return sorted({p[n] for p in self.s['manifest']['paths'] if p[:n] == prefix and len(p) > n})

    def describe(self):
        import battle_enrage
        if self.s['mission']=='FINALE' or self.s['finale']['ending']:
            intel='\n'+enemy_intel.describe(self) if self.s['phase'] in ('FINAL_CHOICE','FINAL_REGROUP') else ''
            letters='\n'+hidden_thread.describe(self) if hidden_thread.public(self)['discovered'] else ''
            pressure='\n'+battle_enrage.describe(self.s['battle']) if self.s.get('battle') else ''
            return finale.view(self)+intel+letters+pressure+'\n'+narrative.describe(self)
        s = self.s; out = [f"{VERSION} | {s['phase']} | {s['route']} / {s['team_id']} / {s['pack']} / seed={s['seed']}",
                              f"行动日{s['day']} | 第{s['expedition_no']}趟 | 已归档{len(s['completed_history'])}趟",
                              '战斗为简化实算，不能用于正式胜率/难度结论。', s['fixture_notice'],
                              f"已入库 {s['bank']} | 待结算 {s['pending']} | 额外救护 {s['medical']}",
                              f"材料 {s['materials']} | 物品 {s['pouch']} | 已用准备占位 {s['used_prep_slots']}/4",
                              f"方案 拥有{s['plans_owned']} / 生效{s['plans_equipped']} | 战利品{list(enumerate(equipment.label(i) for i in s['gear_bag']))}"]
        if s['phase']=='TOWN':
            out.append(town.relief_description(self))
            out.append(town.shelter_text(self))
            if campaign.active(self):
                due=cases.guarantee_due(self)
                if due:out.append('案件保底候选：下一趟优先安排未遇案件 '+due+'（显式定向续办优先，路线不适用时改试其他未遇案件）。')
        if campaign.active(self):out.append(narrative.describe(self))
        if hidden_thread.public(self)['discovered']:out.append(hidden_thread.describe(self))
        if campaign.active(self):out.append(campaign.describe(self))
        if campaign.active(self):out.append(clues.describe(self))
        if missing.state(self)['cases']:out.append(rescue.describe(self))
        if recovery.state(self)['targets']:out.append(recovery.describe(self))
        if story_mission.describe(self):out.append(story_mission.describe(self))
        out.append(facilities.describe(self))
        out.append(learning.describe(self))
        if supplies.describe_site(self):out.append(supplies.describe_site(self))
        out.append(workshop.describe(self))
        out.append(tiers.describe(self))
        if s['phase']=='TOWN' and s['finale'].get('preparation') and not s['finale'].get('run'):
            out.append(enemy_intel.describe(self))
        out.append(event_conditions.describe(self))
        if s['phase'] in ('TOWN', 'EXPLORE', 'BATTLE'):
            growth_text = depth_growth.describe(self)
            if growth_text: out.append(growth_text)
        out.append(f"工坊分支 {s['workshop_branch'] or '未选'} | 今日服务 {len(outfitting.today(self))}/2 | 整备 {s['active_outfit'] or '无'}（outfit status）")
        out.append('施工：'+(', '.join(r['id'] for r in facilities.ongoing(self)) or '空闲')+'；facility status查看全部工地。')
        live = {a['id']: a for a in s['battle']['actors']} if s['battle'] else {}
        for m in s['party']:
            actor = live.get(m['instance_id'], {})
            out.append(f"{'上阵' if m['deployed'] else '预备'} {m['instance_id']} {m['unit_id']} Lv{m['level']} HP {actor.get('hp', m['hp'])}/{m['stats']['hp']} 伤势{m['injury_days']}日 侵蚀{m['erosion']} XP{m['xp']} 格{actor.get('pos', m['position'])} 朝向D{actor.get('facing', m['facing'])} {m['stance']}")
            if m['unit_id'].startswith('M'):out.append('  核心模式：'+m.get('skill_mode','counter' if m['unit_id']=='M04' else 'auto'))
        if s['escorted']:
            safe=escort.preview(self)['protected']
            out.append(f"已确认安全退出：{safe}；仍在护送途中：{[m['instance_id'] for m in s['escorted'] if m['instance_id'] not in safe]}；保留本趟Cost {s['escort_reserved_cost']}，共享包仍在余队。")
            for m in s['escorted']:out.append(f"护送锁定 {m['instance_id']} HP{m['hp']} 侵蚀{m['erosion']} 装备{m['gear']}；接收确认前不计作安全退出。")
        for row in cases.public(self):
            out.append('边境见闻：'+row['text'])
            if row['open'] and row['equipment_quotes']:out.append('装备实物报价（确认前可选）：\n'+equipment_rolls.describe(self,row['id']))
        if refugee.public(self):out.append('边境见闻：'+refugee.public(self)['text'])
        if medicine.public(self):out.append('边境见闻：'+medicine.public(self)['text'])
        if water.public(self):
            w=water.public(self);out.append('边境见闻：'+w['text'])
            if s['phase'] in ('EXPLORE','BATTLE'):out.append(f"材料额度 {w['used']}/{w['capacity']}，运水待装预留 {w['reserved']}；到暮汀实际交货才完成。")
        if s['phase'] in ('TOWN','RETURNED','FAILED','FIN_C'):
            out.append(f"现役{len(town.roster(self))}，随行{len(s['party'])}（仅限Cost）；医舍Lv{s['hospital_level']}，施工剩余{s['hospital_progress']}日，待结算伤护{s['care_target']}")
            for m in s['home_roster']:
                out.append(f"留城 {m['instance_id']} {m['unit_id']} Lv{m['level']} HP{m['hp']}/{m['stats']['hp']} 伤势{m['injury_days']}日 侵蚀{m['erosion']} XP{m['xp']}")
            out.append(f"城内材料{s['warehouse']}\n城内物品{s['item_storage']}\n城内装备{list(enumerate(equipment.label(i) for i in s['gear_storage']))}")
        if s['captives']:
            out.append(f"救援期限模式：{s['capture_mode']}；下一行动结算第{s['day']+1}日；届时到期{rescue.due_next(s)}")
            for batch in rescue.batches(s):
                out.append(f"已确认转运点 {batch['id']}：{batch['members']}，第{batch['capture_day']}日被俘，最晚第{batch['deadline']}日救回；固定GR02E一战，1补给／1日，无铜晶经验奖励。")
            for m in s['captives']:
                label='已解救，待本趟归城结算' if m['instance_id'] in rescue.pending_success_ids(s) else '失联，去向待查' if m['capture']['status']=='MISSING' else '被俘'
                out.append(f"{label} {m['instance_id']} {m['unit_id']} Lv{m['level']} XP{m['xp']} 侵蚀{m['erosion']} 装备锁定{m['gear']}")
        if s['memorial']:out.append('永久失去（原装备一并损失）：'+str([m['instance_id'] for m in s['memorial']]))
        if s['ending']:out.append('本轮结束 FIN-C：整份人类名册均已不可恢复，且无救援对象。')
        if s['phase'] in ['EXPLORE', 'BATTLE']:
            if s['mission']=='ORDINARY':
                out.append('配置审查标记：' + s['manifest']['choice_policy']['authoring_gate'])
                out.append(f"区域 {s['region']} {self.cat.regions[s['region']]['name']} | 地点 {s['site']} | 已清{self.current['cleared']}")
            elif s['mission']=='MEDICINE_VISIT':out.append('药箱固定续办：送医立即全队归城，计1行动日，无普通战斗或奖励。')
            elif s['mission']=='WATER_VISIT':out.append('运水固定续办：归城计1行动日，无普通战斗、佣金或经验。')
            elif s['mission']=='LOCAL_VISIT':out.append('原案件固定接洽：归城计1行动日，无普通战斗、佣金或经验；按现场委托完成实际动作。')
            elif s['mission']=='CASE_VISIT':out.append('避难者固定续办：归城计1行动日，无普通战斗、佣金或经验。')
            elif s['mission']=='TUTORIAL':out.append('灰栎边道固定侦路；支路回访不重刷奖励。')
            else:out.append('固定救援专线：'+str(s['rescue_target']))
            if s['phase'] == 'EXPLORE':
                neighbors = [b if a == s['site'] else a for a, b in self.layout['edges'] if s['site'] in [a, b]]
                out.append(region_space.describe(self) if region_space.active(self) else '相邻道路：' + ', '.join(neighbors))
                if s['site'] in self.manifest_region['events']:
                    event, binding, state = self.event_info(); out.extend([event['name'] + ' [' + state['state'] + ']', event['scene']])
                    if event['event_id']=='EV03':out.append(refugee.public(self)['text'])
                    elif event['event_id']=='EV09':out.append(water.public(self)['text'])
                    elif event['event_id'] in cases.CONFIG:out.append(cases.get(self.s,event['event_id'])['custody'])
                    elif event['event_id']=='EV19':out.append(medicine.public(self)['text'])
                    elif state['state'] in ['RESOLVED', 'DECLINED']: out.append('本趟已关闭，回执：' + str(state.get('receipt')))
                    for option in ([] if state['state'] in ['RESOLVED', 'DECLINED'] or event['type']=='humanity' else event['options']):
                        extra = ''
                        if option.get('reward_bundle_id') == 'RB-PLAN': extra = ' 候选' + str([plan_offers.label(self,p) for p in self.offer(event, option)]) + '（十二项已接；最多装3项，plan list查看）'
                        if option.get('target_choices'):
                            extra += '\n'+'\n'.join('  '+c['id']+': '+c['label'] for c in option['target_choices'])
                        out.append(option['option_id'] + ': ' + option['label'] + ' | ' + option.get('mechanical_summary', '') + extra + (' [预算限制]' if option['option_id'] not in binding['enabled_options'] else ''))
                    if event['event_id'] == 'EV04' and state['state'] not in ['RESOLVED', 'DECLINED']: out.append('已拓印：' + str(state['steps']) + '；rub 1 / rub 2 / choose PRIMARY')
                if s['site'] in self.manifest_region['encounters']:
                    binding = self.manifest_region['encounters'][s['site']]
                    board = self.cat.boards[binding['board_id']]
                    out.append(f"棋盘 {board['name']} / {board['shape_name']} / {board['cell_count']}格；己方部署格 {board['player_deploy_cells']}")
                    out.append(enemy_intel.describe(self))
                if s['site'] == 'X': out.append('后续区域：' + str(self.next_regions()) + '；跨区必须CONFIRM，或安全返城。')
            else:
                b = s['battle']; out.append(f"战斗 {b['encounter_id']} 地形 {b['board_id']} 第{b['tick']}拍")
                out.append(battle_enrage.describe(b))
                out.extend(f"{a['id']} {a['side']} HP{a['hp']} 盾{a['shield']+sum(p['amount'] for p in a['timed_shields'])} 物防{combat.stat(a,'physical_defense',b['tick'])} 魔防{combat.stat(a,'magic_defense',b['tick'])}（整备双防+{a.get('town_defense_bonus',0)}） 格{a['pos']}" for a in b['actors'])
                for a in b['actors']:
                    if a['hp'] <= 0 or not a['pending']:continue
                    warning=a['pending']
                    target=f"锁定本人 {warning['target']}（换格仍锁人）" if warning.get('locks_target') else str(warning['cells'])
                    out.append(f"预警 {a['id']} {warning['move_id']} → {target}，第{warning['due']}拍释放")
                out.extend(f"条件外圈 {a['id']}：{a['pending']['peril_outer_cells']}；释放时内圈仍有人才引爆，内圈撤空则整招落空。" for a in b['actors'] if a['hp']>0 and a.get('pending') and a['pending'].get('peril_outer_cells'))
                out.append(bosses.describe(b))
                import expedition_peril
                if expedition_peril.describe(b):out.append(expedition_peril.describe(b))
                out.append('共享盾：' + str(b['shared_shields']))
                out.extend(f"旧声记录 {a['id']}：{a['basic_history']}" for a in b['actors'] if a['kind'] in ('EN06','EL03'))
                out.extend(f"短冲候选 {a['id']}：{a['pending']['paths']}，已锁{a['pending']['cells']}" for a in b['actors'] if a['pending'] and a['pending'].get('paths'))
                out.extend(str(e) for e in b['events'][-8:])
                import necromancy
                if necromancy.describe(b):out.append(necromancy.describe(b))
                import reinforcements
                if reinforcements.describe(b):out.append(reinforcements.describe(b))
                import enemy_support
                if enemy_support.describe(b):out.append(enemy_support.describe(b))
                import spatial_moves
                if spatial_moves.describe(b):out.append(spatial_moves.describe(b))
                import sweeps
                if sweeps.describe(b):out.append(sweeps.describe(b))
                import veil
                if veil.describe(b):out.append(veil.describe(b))
                import action_timing
                if action_timing.describe(b):out.append(action_timing.describe(b))
                import protection
                if protection.describe(b):out.append(protection.describe(b))
                import battle_plans
                out.append(battle_plans.describe(b))
        import expedition_peril
        if expedition_peril.describe_game(self):out.append(expedition_peril.describe_game(self))
        if s['summary']: out.append('结算：' + json.dumps(s['summary'], ensure_ascii=False))
        out.append(skill_books.describe(self))
        out.append(book_rewards.describe(self))
        return '\n'.join(out)

    def export(self, path):
        atomic_json(path, {'version': VERSION, 'experiment': self.s, 'evidence_scope': 'Executed greybox only; no official win-rate or timing claim.'})
