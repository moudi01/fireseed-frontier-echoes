"""Offline acceptance reference. No game files, player saves or world geometry are executed."""
from pathlib import Path
import copy,hashlib,itertools,json,math
from event_catalog import load_catalog
from check_multi_region import routes

H=Path(__file__).resolve().parent
def read(name):return json.loads((H/name).read_text(encoding='utf-8'))
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def score(seed,key,weight=1):
    # Stable exponential-race ordering; no Python hash() or process-global RNG.
    n=int(hashlib.sha256((str(seed)+'|'+key).encode()).hexdigest()[:13],16)
    u=(n+1)/(16**13+1)
    return -math.log(u)/weight


class ReferenceSampler:
    # Extension hook: the original acceptance fixture remains two units.
    goal_material_units = 2

    def __init__(self):
        self.multi=read('多区域远征配置.json');self.layout=read('八区联合布点.json')
        events,bundles=load_catalog();self.events={e['event_id']:e for e in events};self.bundles={b['bundle_id']:b for b in bundles}
        self.regions={r['region_id']:r for r in self.layout['regions']}
        self.world={r['region_id']:set(r['neighbors']) for r in self.multi['regions']}
        self.encounters={e['encounter_id']:e for e in read('敌人与遭遇.json')['encounters']}
        self.map_regions={r['region_id']:r for r in read('地图地形.json')['regions']}
        self.weights={**read('内容池抽样初始配置.json')['event_weights'],**read('普通事件扩展.json')['event_weights']}

    def generate(self,request):
        self.req=copy.deepcopy(request);self.seed=request['seed'];self.nodes=0;self.limit=request.get('search_limit',20000);self.filtered={}
        self.recent=set().union(*(set(x) for x in request.get('history',[])[-2:]))
        profile=request['profile'];self.p=self.multi['profiles'][profile]
        facts=set(request['facts']);allowed={r['region_id'] for r in self.multi['regions'] if set(r['access_requires_all'])<=facts}
        self.paths=sorted(routes(self.world,allowed,self.p['region_count'],request['start'],request['target']))
        if not self.paths:return self.fail('NO_EXACT_ROUTE','所选起终点无法按指定长度连接；未扣出发物资。')
        self.used_regions=sorted(set().union(*(set(p) for p in self.paths)))
        self.conflict={(a,b) for p in self.paths for a in p for b in p}
        self.caps={'material_units':self.p['reward_caps']['materials_by_difficulty'][request.get('difficulty','D0')],
            'gear_claims':self.p['reward_caps']['equipment'],'book_claims':self.p['reward_caps']['books'],
            'event_bonus_copper':self.p['reward_caps']['ordinary_event_copper'],'event_bonus_crystal':self.p['reward_caps']['ordinary_event_crystal'],
            'event_found_consumable_claims':self.p['reward_caps']['event_found_consumable_claims'],'event_recovery_claims':self.p['reward_caps']['event_recovery_claims']}
        # This acceptance profile reserves two material units at each ordinary goal;
        # it does not claim to implement all equipment/quality drop tables.
        self.reservations={rid:{'material_units':self.goal_material_units} for rid in self.used_regions}
        for rid,values in request.get('pre_reserved_by_region',{}).items():
            if rid not in self.used_regions or any(k not in self.caps or not isinstance(v,int) or v<0 for k,v in values.items()):
                return self.fail('INVALID_RESERVATION','预留须属于本次可达地区、已知资源且为非负整数。')
            for k,v in values.items():self.reservations.setdefault(rid,{})[k]=self.reservations.get(rid,{}).get(k,0)+v
        if not self.budget_ok({}):return self.fail('PRE_RESERVED_BUDGET_EXCEEDED','既有奖励预留已经超过路径预算。')
        self.filtered={};self.domains={}
        for rid in self.used_regions:
            for slot in 'ABCD':
                values=[]
                for eid in self.regions[rid]['event_candidates_by_region_only']:
                    reason=self.filter_reason(rid,slot,eid)
                    if reason:self.filtered[rid+'/'+slot+'/'+eid]=reason
                    else:values.append(eid)
                self.domains[rid,slot]=values
        directed=request.get('directed_case')
        if directed:
            if directed not in self.events or self.events[directed]['type']!='humanity':return self.fail('INVALID_DIRECTED_CASE','指定案件不存在或不是人性案件。')
            if request.get('case_states',{}).get(directed,'OPEN') in ['PROTECTED','EXPLOITED']:
                return self.fail('CASE_ALREADY_TERMINAL','已交割案件不能作为未交割委托重新生成。')
            if not any(directed in self.domains[r,s] for r in self.used_regions for s in 'ABC'):
                return self.fail('DIRECTED_CASE_INELIGIBLE','案件章节、地区、知识、冷却或接收处不满足；未换成其他案件。')
        variables=[(rid,s) for rid in self.used_regions for s in 'ABC']
        # A separate ordinary-only certificate prevents humanity/variant cards from filling base density gaps.
        cold=self.solve(variables,{},ordinary_only=True,allow_recent=False,budget=False)
        if cold=='LIMIT':return self.fail('SEARCH_LIMIT','普通候选校核达到搜索上限，不能据此宣称无解。')
        fallback=cold is None
        certificate=cold if not fallback else self.solve(variables,{},ordinary_only=True,allow_recent=True,budget=False)
        if certificate=='LIMIT':return self.fail('SEARCH_LIMIT','回补候选搜索达到上限，未自动放行。')
        if certificate is None:return self.fail('BASE_EVENT_CAPACITY','基础3处无法联合分配合法普通卡；未降为2处或填空观察。')
        solution=None
        reserve_choices=[None]
        if directed:
            common_regions=set.intersection(*(set(p) for p in self.paths))
            reserve_choices=sorted([v for v in variables if v[0] in common_regions and directed in self.domains[v]],key=lambda v:score(self.seed,'directed/'+str(v)))
            if not reserve_choices:return self.fail('DIRECTED_ROUTE_NOT_COVERED','参考模型只在所有分支必经地区安排指定案件；本路线没有适用地点，未静默丢弃案件。')
        for reserve in reserve_choices:
            forced={reserve:directed} if reserve else {}
            solution=self.solve(variables,{},ordinary_only=False,allow_recent=fallback,budget=True,forced=forced)
            if solution=='LIMIT':return self.fail('SEARCH_LIMIT','事件与预算联合搜索达到上限；不等于内容池无解。')
            if solution is not None:break
        if solution is None:return self.fail('JOINT_BUDGET_OR_BINDING','存在普通候选，但事件、敌阵或已开放选项的完整预留无法联合成立。')
        omissions={};extra_fallback=[]
        if request.get('fourth_sites',True):
            for rid in sorted(self.used_regions,key=lambda r:score(self.seed,'fourth/'+r)):
                var=(rid,'D')
                # Incremental fourth sites are optional; this is not a maximum-density optimizer.
                cold_extra=self.candidates(var,solution,False,False)
                allow_recent=not cold_extra
                if allow_recent:extra_fallback.append(rid)
                found=self.solve([var],solution,ordinary_only=False,allow_recent=allow_recent,budget=True)
                if found=='LIMIT':return self.fail('SEARCH_LIMIT','可选第四地点搜索达到上限；未提交不完整计划。')
                if found is None:omissions[rid]='NO_ADDITIONAL_CARD' if not self.candidates(var,solution,False,True) else 'BUDGET_OR_BINDING'
                else:solution=found
        frozen={}
        for rid in self.used_regions:
            candidates=self.encounter_choices(rid,[v['event_id'] for k,v in solution.items() if k[0]==rid])
            if not candidates:return self.fail('ENCOUNTER_BINDING','事件分配缺少兼容敌阵，未生成替代敌人。')
            chosen=min(candidates,key=lambda x:score(self.seed,'encounters/'+rid+'/'+canonical(x)))
            template=min(self.regions[rid]['templates'],key=lambda x:score(self.seed,'template/'+rid+'/'+x['template_id']))
            elite=min([rid+'-E01',rid+'-E02'],key=lambda x:score(self.seed,'elite/'+rid+'/'+x))
            chosen['L']={'encounter_id':elite,'board_id':self.encounters[elite]['board_id']}
            frozen[rid]={'template_id':template['template_id'],'events':{s:solution[rid,s] for s in 'ABCD' if (rid,s) in solution},'encounters':chosen,'fixed_station':'S','nonfinal_camp':'X',
                'combat_rewards':{'G':{'bundle_ids':(['RB-MAT2'] if self.goal_material_units else []),'pending_commission':{'copper':16,'crystal':2}},'L':{'actual_win_increment':{'copper':8,'crystal':2}}}}
        manifest={'version':'JOINT-SAMPLE-1.0','seed':self.seed,'profile':profile,'start':request['start'],'target':request['target'],
            'paths':self.paths,'regions':frozen,'ordinary_certificate':{r:{s:certificate[r,s]['event_id'] for s in 'ABC'} for r in self.used_regions},
            'caps':self.caps,'pre_reserved_by_region':self.reservations,
            'cold_baseline_failed':fallback,'fourth_history_fallback_regions':extra_fallback,'omitted_fourth_sites':omissions,
            'departure_supply_cost':self.p['departure_supply_cost'],'runtime_implemented':False,
            'scope':'offline_assignment_and_reward_reservation_only_no_geometry_or_combat_proof'}
        manifest['manifest_sha256']=digest(manifest)
        return {'status':'SUCCESS','manifest':manifest,'search_nodes':self.nodes,'filter_reasons':self.filtered,'charged_supply':0}

    def fail(self,code,message):
        return {'status':'FAILURE','reason':code,'message':message,'charged_supply':0,'search_nodes':self.nodes,'filter_reasons':getattr(self,'filtered',{})}

    def filter_reason(self,rid,slot,eid):
        e=self.events[eid];chapter=self.req['chapter'];facts=set(self.req['facts'])
        if slot not in self.regions[rid]['event_site_compatibility'][eid]:return 'INCOMPATIBLE_SITE'
        if e['min_chapter']>chapter or (eid!=self.req.get('directed_case') and e['max_chapter'] is not None and chapter>e['max_chapter']):return 'CHAPTER'
        if e.get('knowledge_gate') and e['knowledge_gate']['required_completed_fact'] not in facts:return 'KNOWLEDGE'
        if eid in self.req.get('missing_props',[]):return 'MISSING_SCENE_PROPS'
        if eid in self.req.get('exclude_events',[]):return 'EXPLICIT_FIXTURE_EXCLUSION'
        role=e.get('gameplay_role');service=self.req.get('services',{}).get(rid,{})
        gate={'scouting':'scouting','field_consumable_crafting':'workbench','prelocked_route_choice':'variant'}.get(role)
        if gate and service.get(gate,True) is False:return 'MISSING_'+gate.upper()
        if role=='prelocked_route_choice' and not self.common_boards(rid,e['variant_candidates']):return 'NO_COMMON_BOARD'
        if e['type']=='humanity':
            state=self.req.get('case_states',{}).get(eid,'OPEN')
            if state in ['PROTECTED','EXPLOITED']:return 'CASE_TERMINAL'
            if state=='PROTECTION_PENDING' and eid!=self.req.get('directed_case'):return 'PENDING_REQUIRES_DIRECTED_RESUME'
            if service.get('receiver',True) is False:return 'MISSING_RECEIVER'
            if eid in self.recent and eid!=self.req.get('directed_case'):return 'HUMANITY_COOLDOWN'
        return None

    def common_boards(self,rid,pair):
        sets=[set(self.encounters[x]['allowed_board_variants']) for x in pair]+[set(self.map_regions[rid]['board_ids'])]
        override=self.req.get('fault_board_allowlist',{}).get(rid)
        if override is not None:sets.append(set(override))
        return sorted(set.intersection(*sets))

    def encounter_choices(self,rid,eids):
        variant=next((self.events[x] for x in eids if self.events[x].get('gameplay_role')=='prelocked_route_choice'),None)
        normals=[rid+'-N'+str(i).zfill(2) for i in range(1,5)];result=[]
        if variant:
            pair=variant['variant_candidates'];rest=sorted(set(normals)-set(pair))
            combos=[(pair[0],b2,g,board) for b2,g in itertools.permutations(rest) for board in self.common_boards(rid,pair)]
        else:combos=[(b1,b2,g,self.encounters[b1]['board_id']) for b1,b2,g in itertools.permutations(normals,3)]
        for b1,b2,g,board in combos:
            if 'EV08' in eids and not any(u['enemy_id']=='EN04' for u in self.encounters[b2]['units']):continue
            first={'default_encounter_id':b1,'board_id':board,'candidate_ids':variant['variant_candidates'] if variant else [b1]}
            result.append({'B1':first,'B2':{'encounter_id':b2,'board_id':self.encounters[b2]['board_id']},'G':{'encounter_id':g,'board_id':self.encounters[g]['board_id']}})
        return result

    def candidates(self,var,assigned,ordinary_only,allow_recent):
        rid,slot=var;values=[]
        for eid in self.domains[var]:
            e=self.events[eid]
            if ordinary_only and (e['type']=='humanity' or e.get('gameplay_role')=='prelocked_route_choice'):continue
            if not allow_recent and eid in self.recent and eid!=self.req.get('directed_case'):continue
            if any(v['event_id']==eid and (rid,k[0]) in self.conflict for k,v in assigned.items()):continue
            if not self.encounter_choices(rid,[eid]+[v['event_id'] for k,v in assigned.items() if k[0]==rid]):continue
            values.append(eid)
        return sorted(values,key=lambda eid:(score(self.seed,'event/'+rid+'/'+slot+'/'+eid,self.weights[eid]*(.25 if eid in self.recent else 1)),eid))

    def option_debits(self,eid,option):
        d={};bid=option.get('reward_bundle_id')
        if bid:
            for k,v in self.bundles[bid]['budget_debits'].items():d[k]=d.get(k,0)+v
        for effect in option['effects']:
            for k,v in effect.get('budget_debits',{}).items():d[k]=d.get(k,0)+v
            if effect['type']=='resolve_protection_action' and effect['mode']=='CARGO':d['material_units']=d.get('material_units',0)+2
        return d

    def masks(self,eid):
        substantive=[o for o in self.events[eid]['options'] if o['option_id']!='PASS']
        if self.events[eid]['type']=='humanity' and self.req.get('case_states',{}).get(eid)=='PROTECTION_PENDING':
            substantive=[o for o in substantive if o['option_id']=='HUMANITY']
        choices=[substantive]
        if self.events[eid]['type']!='humanity' and self.req.get('budget_policy','explicit_option_limits')=='explicit_option_limits':
            # Only reward-bearing options may be budget-limited. Do not remove a
            # zero-debit protection choice in order to make exploitation attractive.
            for o in sorted(substantive,key=lambda o:score(self.seed,'mask/'+eid+'/'+o['option_id'])):
                omitted=[x for x in substantive if x is not o]
                if all(self.option_debits(eid,x) for x in omitted):choices.append([o])
        seen=set()
        for opts in choices:
            ids=tuple(o['option_id'] for o in opts)
            if ids in seen:continue
            seen.add(ids);reservation={}
            for o in opts:
                for k,v in self.option_debits(eid,o).items():reservation[k]=max(reservation.get(k,0),v)
            disabled={o['option_id']:('PENDING_CASE_ACTION' if o['option_id']=='EXPLOIT' and self.req.get('case_states',{}).get(eid)=='PROTECTION_PENDING' else 'PREVIEWED_BUDGET_LIMIT') for o in self.events[eid]['options'] if o['option_id']!='PASS' and o['option_id'] not in ids}
            yield {'event_id':eid,'enabled_options':list(ids)+['PASS'],'disabled_options':disabled,'reserved_debits':reservation,'history_fallback':eid in self.recent and self.events[eid]['type']!='humanity','directed_cooldown_exception':eid==self.req.get('directed_case') and eid in self.recent}

    def budget_ok(self,assigned):
        for path in self.paths:
            used={}
            for rid in path:
                for k,v in self.reservations.get(rid,{}).items():used[k]=used.get(k,0)+v
            for (rid,_),choice in assigned.items():
                if rid in path:
                    for k,v in choice['reserved_debits'].items():used[k]=used.get(k,0)+v
            if any(k not in self.caps or v>self.caps[k] for k,v in used.items()):return False
        return True

    def solve(self,variables,initial,ordinary_only,allow_recent,budget,forced=None):
        forced=forced or {};assigned=copy.deepcopy(initial);remaining=[v for v in variables if v not in assigned]
        min_cost={eid:{k:min(v['reserved_debits'].get(k,0) for v in self.masks(eid)) for k in self.caps} for eid in self.events} if budget else {}
        def possible(domains):
            # Necessary per-path matching and optimistic budget bounds. Neither is
            # used as a substitute for the final shared-instance CSP solution.
            for path in self.paths:
                slots=[v for v in domains if v[0] in path];matching={}
                def augment(slot,seen):
                    for eid in domains[slot]:
                        if eid in seen:continue
                        seen.add(eid)
                        if eid not in matching or augment(matching[eid],seen):matching[eid]=slot;return True
                    return False
                if any(not augment(v,set()) for v in slots):return False
                if budget:
                    pool=set().union(*(set(domains[v]) for v in slots)) if slots else set()
                    used={k:sum(self.reservations.get(r,{}).get(k,0) for r in path)+sum(ch['reserved_debits'].get(k,0) for (r,_),ch in assigned.items() if r in path) for k in self.caps}
                    for k,cap in self.caps.items():
                        lower=sum(min_cost[e][k] for e in pool) if len(pool)==len(slots) else sum(min(min_cost[e][k] for e in domains[v]) for v in slots)
                        if used[k]+lower>cap:return False
            return True
        def walk(left):
            if not left:return copy.deepcopy(assigned)
            if self.nodes>=self.limit:return 'LIMIT'
            self.nodes+=1;domains={v:self.candidates(v,assigned,ordinary_only,allow_recent) for v in left}
            for var,eid in forced.items():
                if var in domains:domains[var]=[eid] if eid in domains[var] else []
            if not possible(domains):return None
            var=min(left,key=lambda v:(len(domains[v]),score(self.seed,'variable/'+str(v))))
            for eid in domains[var]:
                values=self.masks(eid) if budget else [{'event_id':eid,'reserved_debits':{}}]
                for choice in values:
                    assigned[var]=choice
                    if not budget or self.budget_ok(assigned):
                        answer=walk([v for v in left if v!=var])
                        if answer is not None:return answer
                    assigned.pop(var,None)
            return None
        return walk(remaining)


def resume_manifest(serialized):
    saved=json.loads(serialized);expected=saved.pop('manifest_sha256')
    if digest(saved)!=expected:raise ValueError('CORRUPT_LOCKED_MANIFEST')
    saved['manifest_sha256']=expected
    return saved


def service_options(manifest,rid,slot,state):
    """Read-only presentation projection; target state never reruns generation."""
    choice=manifest['regions'][rid]['events'][slot]
    if state.get('resolved_receipt') is not None:return {'saved_receipt':state['resolved_receipt']}
    result={'enabled':list(choice['enabled_options']),'disabled':dict(choice['disabled_options'])}
    events={e['event_id']:e for e in load_catalog()[0]};role=events[choice['event_id']].get('gameplay_role')
    invalid=[]
    if role=='scouting' and state.get('target_revealed'):invalid=['PRIMARY']
    if role=='prelocked_route_choice' and (state.get('target_revealed') or state.get('target_started')):invalid=['PRIMARY','SECONDARY']
    if role=='field_consumable_crafting' and not state.get('inputs_and_capacity_valid',True):invalid=['PRIMARY']
    for option in invalid:
        if option in result['enabled']:result['enabled'].remove(option)
        result['disabled'][option]='CURRENT_SERVICE_CONDITION'
    return result
