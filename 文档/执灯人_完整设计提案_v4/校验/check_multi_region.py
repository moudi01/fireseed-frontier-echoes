"""Validate MULTI-1.1 topology, arithmetic and local state counterexamples, not the game."""
from pathlib import Path
import json,hashlib,re,copy,sys
from urllib.parse import unquote
H=Path(__file__).resolve().parent;B=H.parent;R=B.parent.parent;checks=[];inputs={}
def read(p):
 raw=p.read_bytes();inputs[p.relative_to(R).as_posix()]=hashlib.sha256(raw).hexdigest();return raw
def load(p):return json.loads(read(p))
def check(n,ok,detail=''):checks.append({'name':n,'passed':bool(ok),'detail':detail})
def routes(adjacency,allowed,length,first=None,last=None):
 result=[]
 def walk(path):
  if len(path)==length:
   if last is None or path[-1]==last:result.append(path)
   return
  for target in adjacency[path[-1]]:
   if target in allowed and target not in path:walk(path+[target])
 for start in ([first] if first else sorted(allowed)):
  if start in allowed:walk([start])
 return result
def transfer(state,target,remaining_paths,*,saved=True):
 out=copy.deepcopy(state);key=state['region']
 if key in state['receipts']:return out,'duplicate' if state['receipts'][key]==target else 'conflict'
 if not saved or not state['goal_complete'] or target not in {p[1] for p in remaining_paths if len(p)>1 and p[0]==state['region']}:return out,'rejected'
 out['receipts'][key]=target;out['region']=target;out['visited'].append(target);out['goal_complete']=False
 return out,'committed'
def run():
 c=load(H/'多区域远征配置.json');sp=load(H/'连续区域地图合同.json');regions={r['region_id']:r for r in c['regions']};adj={r:set() for r in regions}
 check('八区无圈层与配对字段',len(regions)==8 and all('region_ring' not in r and 'paired_region_id' not in r for r in regions.values()) and c['region_structure']['ring_partition'] is None and not c['region_structure']['paired_outer_inner_rule'])
 edgekeys={tuple(sorted(e)) for e in c['edges']};check('14条无重复无自连合法边',len(edgekeys)==len(c['edges'])==14 and all(len(e)==2 and e[0]!=e[1] and set(e)<=set(regions) for e in c['edges']))
 for a,b in c['edges']:adj[a].add(b);adj[b].add(a)
 check('相邻表与边双向一致',all(set(r['neighbors'])==adj[k] for k,r in regions.items()))
 check('四将原驻地保留且不构成圈层',{k:r['general_id'] for k,r in regions.items() if r['general_id']}=={'RG02':'MG01','RG03':'MG02','RG04':'MG03','RG05':'MG04'})
 old=load(H/'地图地形.json');check('区域名章节档位与开放事实保留',all(all(regions[r['region_id']][k]==r[k] for k in ['name','chapter_id','threat_rank_id','access_requires_all','general_id']) for r in old['regions']))
 reachable={'RG01'}
 while True:
  nxt=reachable|set().union(*(adj[k] for k in reachable))
  if nxt==reachable:break
  reachable=nxt
 check('八区网络连通',reachable==set(regions))
 stages={'ST101':{'RG01'},'ST102':{'RG01','RG06','RG07','RG08'},'ST104':{'RG01','RG06','RG07','RG08','RG02','RG03'},'CH2_COMPLETE':set(regions)}
 counts={}
 for stage,allowed in stages.items():
  counts[stage]={}
  for key,p in c['profiles'].items():
   paths=routes(adj,allowed,p['region_count']);counts[stage][key]=len(paths)
   check(stage+' '+key+'路线长度与解锁',all(len(path)==len(set(path))==p['region_count'] and set(path)<=allowed for path in paths) and bool(paths)==(stage!='ST101'))
   if paths:
    example=paths[0];sub=routes(adj,allowed,p['region_count'],first=example[0],last=example[-1]);check(stage+' '+key+'目标端点可筛',example in sub and all(path[0]==example[0] and path[-1]==example[-1] for path in sub))
 check('短中长区数2/3/4且空间合同同步',[c['profiles'][k]['region_count'] for k in ['SHORT','MEDIUM','LONG']]==[2,3,4] and sp['regions_per_expedition']=={'SHORT':2,'MEDIUM':3,'LONG':4} and sp['current_expedition_contract']=='多区域远征配置.json')
 for ex in c['examples']:check('示例路径 '+str(ex['regions']),ex['regions'] in routes(adj,set(regions),c['profiles'][ex['profile']]['region_count']))
 for key,p in c['profiles'].items():
  n=p['region_count'];check(key+'数量与预算计算',p['battle_range']==[3*n,4*n] and p['event_sites_range']==[3*n,4*n] and p['inter_region_camps']==n-1 and p['regional_supply_uses_max']==n and p['departure_supply_cost']==n and p['reward_caps']['materials_by_difficulty']=={'D0':4*n,'D1':6*n,'D2':8*n} and p['calendar_days_per_final_settlement']==1)
  before_return=5*n+5*4*n-15*(n-1);main_only=5*n+5*3*n-15*(n-1)
  check(key+'侵蚀有限算例',before_return=={2:35,3:45,4:55}[n] and main_only=={2:25,3:30,4:35}[n] and before_return-20<100,{'full_optional_before_return':before_return,'after_return':before_return-20,'main_only_before_return':main_only})
 check('营地与区内补给限次且不复活',c['supply']['regional_station']['uses_per_region']==c['supply']['boundary_camp']['uses_per_completed_boundary']==1 and not c['supply']['regional_station']['revives'] and not c['supply']['boundary_camp']['revives'] and not c['supply']['boundary_camp']['repeat_or_reload_refreshes'])
 placement=c['supply']['regional_station']['placement']
 check('区内补给首战后第二战前可达且不要求额外交易',placement['reachable_after_first_mandatory_battle_before_second'] and not placement['requires_extra_battle_payment_or_humanity_choice'] and placement['use_is_optional_and_can_be_deferred_within_same_region'])
 density=c['events']['density_allocation'];interact=c['events']['interaction_revalidation'];joint=c['events']['encounter_service_allocation']
 check('基础三处与额外第四处须联合合法匹配',density['baseline_sites_per_region']==3 and density['optional_fourth_site_max']==1 and density['baseline_requires_joint_ordinary_card_assignment_excluding_route_variant_and_humanity'] and density['fourth_requires_additional_distinct_eligible_card_after_baseline_assignment'] and density['all_departure_branches_must_pass_with_consistent_region_instances'])
 check('自由探索后的服务选项再次检查且保留免费退出',interact['when']==['on_open','on_confirm_before_atomic_commit'] and interact['PASS_always_free'] and interact['other_valid_options_remain'] and interact['all_substantive_options_invalid']=='ordinary_aftermath_no_reroll_no_reward')
 check('侦察目标与双候选改路槽不冲突',joint['route_variant_reserves_both_candidate_ids_in_one_unresolved_normal_slot'] and joint['other_mandatory_slots_exclude_both_reserved_ids'] and joint['scout_target_must_differ_from_route_variant_target'] and not joint['adds_battles_or_reward_budget'])
 check('药品预备上限及普通技能范围不因换区重置',c['supply']['carried_consumable_and_preparation_total_cap']==4 and not c['continuity']['camp_resets_skill_counts'] and c['continuity']['ordinary_skill_counter_scope'].startswith('battle_id') and not c['continuity']['new_region_resets_inventory_claims_or_plans'])
 check('事件整趟唯一和普通回补不能重开人性',c['events']['same_event_id_once_per_whole_run'] and c['events']['terminal_humanity_case_never_reopens_on_region_change'] and c['events']['recent_ordinary_fallback']['humanity_cases_excluded_from_fallback'] and c['events']['recent_ordinary_fallback']['fallback_weight_multiplier']==.25 and c['events']['recent_ordinary_fallback']['does_not_override_same_run_unique'])
 state={'region':'RG01','goal_complete':True,'visited':['RG01'],'receipts':{},'HP':72,'erosion':20,'items':3,'claimed_materials':4,'plans':['P1'],'calendar':0,'banked_copper':0}
 check('不合法的四区起终点组合不能降为两区',not routes(adj,stages['ST102'],4,first='RG01',last='RG07') and bool(routes(adj,stages['ST102'],2,first='RG01',last='RG07')))
 paths=routes(adj,stages['ST102'],4,first='RG01',last='RG06');dest=paths[0][1];out,result=transfer(state,dest,paths)
 check('跨区只写位置进度不洗资源或入库',result=='committed' and out['visited']==['RG01',dest] and all(out[k]==state[k] for k in ['HP','erosion','items','claimed_materials','plans','calendar','banked_copper']))
 check('目标未完成拒绝跨区',transfer({**state,'goal_complete':False},dest,paths)[1]=='rejected')
 check('非相邻或无法按剩余长度抵达拒绝',transfer(state,'RG05',paths)==(state,'rejected'))
 check('跨区保存失败不部分写入',transfer(state,dest,paths,saved=False)==(state,'rejected'))
 # Replay the original exit request against its saved source-state receipt.
 replay={**out,'region':'RG01'};check('重复出口请求不二次写入与不同载荷拒绝',transfer(replay,dest,paths)==(replay,'duplicate') and transfer(replay,'RG03',paths)==(replay,'conflict'))
 check('日期、工单和入库只在整趟结算',c['settlement']['calendar_days']==c['settlement']['workshop_job_progress']==1 and c['settlement']['once_at_whole_run_end'] and c['settlement']['region_complete_does_not_bank_loot'])
 check('七主源文件保留供内容与固定任务基线',all(hashlib.sha256((B/rel).read_bytes()).hexdigest()==v for rel,v in c['base_source_sha256'].items()))
 snap=R/c['snapshot'];m=load(snap/'快照哈希.json');check('修订前63文件快照未变',len(m)==c['snapshot_files']==63 and all(hashlib.sha256((snap/p).read_bytes()).hexdigest()==v for p,v in m.items()))
 for rel in [c['authority'],'专项/多区域远征耗损与事件承载校核.md','样图/灰栎边道_连续小地图_样图02.md','专项/八区域外围与内围结构.md']:
  p=B/rel;t=read(p).decode('utf-8');missing=[]
  for ref in re.findall(r'\]\(([^)]+)\)',t):
   if not ref.startswith(('https://','http://','#')) and not (p.parent/unquote(ref.split('#')[0])).exists() and not ref.endswith('多区域远征校核结果.json'):missing.append(ref)
  check('正文链接 '+rel,not missing,missing)
 sample=load(B/'样图/灰栎边道_样图02_布点.json');check('灰栎02适配每区3+1且出口明确',len(sample['mandatory_encounters'])==3 and len(sample['optional_encounters'])==1 and sample['maximum_distinct_battles']==4 and sample['baseline_supply_points']==['S1'] and 'goal_exit' in sample)
 return counts
if __name__=='__main__':
 read(Path(__file__));counts={}
 try:counts=run()
 except Exception as ex:check('完整执行',False,repr(ex))
 failed=[x for x in checks if not x['passed']];result={'version':'MULTI-1.1','passed':len(checks)-len(failed),'failed':len(failed),'checks':checks,'legal_directed_path_counts':counts,'input_sha256':inputs,'scope':'design_consistency_topology_arithmetic_and_abstract_transfer_only','not_proven':['runtime_generator','navigation_mesh','combat_balance','resource_balance','save_storage_atomicity','event_density_after_all_gates','player_choices']}
 (H/'多区域远征校核结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(f'Multi-region checks: {result["passed"]}/{len(checks)} passed; {len(failed)} failed')
 for x in failed:print('FAIL',x['name'],x['detail'])
 sys.exit(bool(failed))
