"""One-way finale, persistent two-battle state, explicit choices and endings."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import uuid
import campaign
import save_storage
import archive_cache
import cases
import hidden_thread
import combat
import bosses
import finale_battle
import learning
import adaptation_geometry as geometry
import research
import town
import outfitting
import facilities

FACTS={'RISK_ACKNOWLEDGED','LEGAL_PARTY','FINAL_PREPARATION_VALIDATED','FINALE_READY',
       'ST-401','ST-402','ST-403','ST-404','RESISTANCE_CONFIRMED','PROFIT_ASSIMILATION',
       'INDEPENDENT_PERSONALITY_RELINQUISHED','PRE_SIGNED_TERMINATION_COMMITTED',
       'DEMON_DEFEATED','DEMON_PROCESS_ENDED','CANDIDATE_AUTHORITY_INHERITED',
       'ADMIN_DEFEATED','FIN-A','FIN-B-PERFECT','FIN-B-IMPERFECT','FIN-C'}
BOARD='CITADEL_RING'
RISK=('终战单向进入，不能返城补物；魔王与管理员连续作战，不回血、不刷新次数，失败结束本轮进入C。'
      '魔王战后未上场人类承受20%最大生命损耗（至少1点，不致死），再投影管理员。')
ENDINGS={
 'FIN-A':('神明迭代','你接管虚拟世界，停止继续收割。城镇恢复，永久缺席者的名字仍在；培养舱继续运转，人类肉身仍沉睡。本轮授权窗口关闭，不能事后改为断网。'),
 'FIN-B-PERFECT':('破壁回归·完美结局','实验与收割权限撤销，生命支持继续。你推开舱门，隔壁传来铜哨声；本轮每一位同行者都能回应点名。这一次，我们都在。旧世界的死者没有因此复活。'),
 'FIN-B-IMPERFECT':('破壁回归·不完美结局','实验与收割同样停止，生命支持继续。可回接的幸存者苏醒，你翻开尚有缺页的日志。先把还在的人带出去。未完成的承诺与真实造成的损失仍然存在。'),
 'FIN-C':('归于虚无','你的独立人格不再获得控制。新指挥官来到暮汀，实验留下了这次的训练收益；这不是旧成员复活。')}


def check(ok,text):
    if not ok:raise ValueError(text)


def initialize(game):
    game.s['finale']={'sealed':False,'seal_pending':False,'preparation':None,'run':None,'ending':None}


def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

RETRY_FORMAT='TINDER-FINALE-RETRY-1'


def retry_path(game):
    check(game.save_path is not None,'当前会话没有存档路径，不能建立终战重试检查点。')
    return Path(str(Path(game.save_path).resolve())+'.finale_retry.json')


def write_retry_checkpoint(game):
    """Snapshot the last town state immediately before the one-way entry."""
    path=retry_path(game)
    payload={'format':RETRY_FORMAT,'game_id':game.s['id'],'version':game.s['version'],
             'source_sha256':game.s['source_sha256'],'state':game.s}
    signature=save_storage.write_sidecar(path,payload)
    try:
        from engine import Game
        checkpoint=archive_cache.checkpoint_copy(game.s)
        verified=Game.from_state(checkpoint,game.cat,game.save_path).s
        game._validated_retry=(path,signature,game.s['id'],verified)
    except (ValueError,KeyError,TypeError,IndexError,AttributeError):
        # The sidecar remains authoritative and is validated on retry.
        game._validated_retry=None
    game.log('finale_retry_checkpoint',path=str(path))
    return path


def read_retry_checkpoint(game):
    path=retry_path(game)
    check(path.exists(),'没有终战重试检查点；需要先进入过一次终战。')
    cached=getattr(game,'_validated_retry',None)
    known=cached[1] if cached and cached[0]==path and cached[2]==game.s['id'] else None
    signature,row=save_storage.read_signed_sidecar(path,known)
    if row is None:return path,signature,cached[3],True
    check(row.get('format')==RETRY_FORMAT,'终战重试检查点格式无效。')
    check(row.get('game_id')==game.s['id'],'终战重试检查点属于另一个周目。')
    check(row.get('version')==game.s['version'],'终战重试检查点版本与当前运行不符。')
    state=row.get('state');check(isinstance(state,dict),'终战重试检查点缺少状态。')
    return path,signature,state,False


def require_retryable_ending(game):
    ending=game.s['finale'].get('ending')
    check(bool(ending) and ending.get('ending_id')=='FIN-C'
          and ending.get('cause') in ('BATTLE_DEFEAT', 'FORMATTING_FAILED'),
          '只有失败结局 FIN-C 可以重试。')
    return ending


def warm_retry_checkpoint(game):
    # A missing or incompatible checkpoint stays a command-time error.
    try:
        require_retryable_ending(game)
        path,signature,state,_=read_retry_checkpoint(game)
        import engine
        restored=engine.Game.from_state(state,game.cat,game.save_path).s
        archive_cache.seal_validated(restored,decoded_json=True)
        archive_cache.seal_loaded_journal(restored)
        archive_cache.warm_archives(restored,for_checkpoint=True)
        game._validated_retry=(path,signature,game.s['id'],restored)
    except (OSError,ValueError,KeyError,TypeError,IndexError,AttributeError):
        return


def retry_checkpoint(game):
    """Restore the pre-entry town state after a failed FIN-C ending."""
    s=game.s
    ending=require_retryable_ending(game)
    path,_,state,validated=read_retry_checkpoint(game)
    import engine
    restored=(engine._snapshot_state(state) if validated else
              engine.Game.from_state(state,game.cat,game.save_path).s)
    history=restored['finale'].setdefault('retry_history',[])
    history.append({'failed_ending':deepcopy(ending),'failed_phase':s['phase'],
                    'failed_day':s['day'],'failed_expedition':s['expedition_no'],
                    'failed_sequence':s['sequence'],'retry_index':len(history)+1,
                    'checkpoint_path':str(path)})
    restored['finale']['ending']=None;restored['ending']=None;restored['phase']='TOWN'
    game.s=restored
    return (f"已恢复到进入终战前的城镇整备状态（失败结局 {ending.get('ending_id')} 已写入重试记录）。"
            '可重新整备后 finale enter CONFIRM，或直接重开终战。')


def grade(game):
    rows={};protected=[];exploited=[];unfinished=[]
    for eid in game.cat.rules['humanity']['event_ids']:
        try:row=cases.get(game.s,eid)
        except KeyError:raise ValueError('缺少案件历史，恢复证据后才能判定结局：'+eid)
        state=row['state'];receipt=row.get('receipt')
        check(row['enabled'],'本轮案件历史未启用：'+eid)
        if state in ('PROTECTED','EXPLOITED'):
            expected=game.cat.events[eid]['protection_receipt_id'] if state=='PROTECTED' else eid+'-EXPLOITED'
            check(receipt and receipt.get('id')==expected,'已结案但缺少有效回执：'+eid)
            check((game.s['private_case_factors'].get(eid,0)==10)==(state=='PROTECTED'),'保全因子与回执不一致：'+eid)
        else:check(game.s['private_case_factors'].get(eid,0)==0,'未结案却有因子：'+eid)
        (protected if state=='PROTECTED' else exploited if state=='EXPLOITED' else unfinished).append(eid)
        rows[eid]={'state':state,'receipt':deepcopy(receipt),
                   'redeemed_trade':deepcopy(row.get('trade_credit')) if (row.get('trade_credit') or {}).get('redeemed') else None}
    lost=[m['instance_id'] for m in game.s['memorial'] if not m['unit_id'].startswith('PET')]
    captives=[m['instance_id'] for m in game.s['captives'] if not m['unit_id'].startswith('PET')]
    thread_ready=hidden_thread.grade_ready(game)
    answer=(game.s.get('hidden_thread') or {}).get('steps',{}).get('answer')
    thread_proof=({'id':answer['id'],'sha256':answer['sha256'],
                   'scope':('CONTROLLED_SCENARIO_NOT_NATURAL_ACQUISITION'
                            if hidden_thread.public(game).get('author_fixture')
                            else 'RUNTIME_RECEIPTS')} if thread_ready else None)
    return {'factor':len(protected)*10,'protected':protected,'exploited':exploited,'unfinished':unfinished,
            'lost':lost,'captives':captives,'events':rows,
            'hidden_thread_ready':thread_ready,'hidden_thread_proof':thread_proof,
            'perfect':len(protected)==10 and not lost and not captives and thread_ready,
            'roster_ids':sorted(m['instance_id'] for m in town.roster(game)+game.s['memorial'] if not m['unit_id'].startswith('PET'))}


def carried(game):return bool(game.s['research']['assembly']) and not game.s['finale']['sealed']


def legal_party(game):
    # The final budget is checked without granting facts or mutating the party.
    old=game.s['budget'];game.s['budget']=next(b for b in game.cat.rules['command_budgets'] if b['milestone']=='FINALE_READY')
    try:game.validate_deployment(BOARD)
    finally:game.s['budget']=old
    check(any(m['deployed'] and not m['unit_id'].startswith('PET') for m in game.s['party']),'至少部署一名可行动人类。')


def lock_demon(game):
    enc=game.cat.encounter_for_board('BATTLE-DEMON',BOARD);enc['board_id']=BOARD
    chosen=[];used=set();families=set()
    for _ in range(2):
        candidates=sorted(learning.eligible(game,enc,last=True),key=lambda p:(p['last_applied'],p['card']))
        patch=next((p for p in candidates if p['family'] not in families and not (set(p['positions'])|set(p['rules']))&used),None)
        if not patch:break
        chosen.append(patch);families.add(patch['family']);used.update(patch['positions']);used.update(patch['rules'])
        enc=geometry.apply(enc,patch)
    if chosen:
        combined=deepcopy(chosen[0]);combined['components']=chosen
        combined['positions']={k:v for p in chosen for k,v in p['positions'].items()}
        combined['rules']={k:v for p in chosen for k,v in p['rules'].items()}
        enc['adaptation']=combined
    return enc


def outcome(game,eid,cause=None):
    f=game.s['finale']
    if f['ending']:return ending_text(game)
    g=grade(game);r=f['run'];s=game.s
    if eid=='FIN-B':eid='FIN-B-PERFECT' if g['perfect'] else 'FIN-B-IMPERFECT'
    if eid=='FIN-C' and cause!='HUMANITY_EXTINCT':campaign.fact(game,'PRE_SIGNED_TERMINATION_COMMITTED',{'cause':cause,'finale_id':r['id']})
    campaign.fact(game,eid,{'cause':cause,'finale_id':r['id'] if r else None})
    f['ending']={'ending_id':eid,'route_id':'FIN-B' if eid.startswith('FIN-B') else eid,'cause':cause,
                 'finale_id':r['id'] if r else None,'grade':g,'facts':deepcopy(s['campaign']['facts']),
                 'battle_ids':[b['battle_id'] for b in r['reports']] if r else [],
                 'safe_disconnect':eid.startswith('FIN-B'),'life_support_preserved':eid!='FIN-C'}
    f['ending']['sha256']=digest(f['ending']);s['ending']=eid;s['phase']='FIN_C' if eid=='FIN-C' else 'FINISHED'
    if r:r['stage']='FINISHED'
    game.log('finale_ended',ending_id=eid,cause=cause)
    return ending_text(game)


def ending_text(game):
    e=game.s['finale']['ending']
    if not e:return ''
    title,text=ENDINGS[e['ending_id']]
    if e['cause']=='PROFIT_ASSIMILATION':text='你主动交还独立人格，知识与权柄归合并后的魔王。收益保留下来了，你不再单独存在。没有进行魔王战或管理员战。\n'+text
    elif e['cause']:
        reports=(game.s['finale'].get('run') or {}).get('reports',[])
        last=reports[-1] if reports else {}
        stage=last.get('finale',{}).get('stage')
        reason={'HUMANITY_EXTINCT':'整份人类名册已永久损失，已无可恢复的队员',
                'FORMATTING_FAILED':'管理员格式化倒计时结束，未能在期限内完成终战目标',
                'BATTLE_DEFEAT':{'DEMON':('魔王战后已无可继续作战的人类' if last.get('result')=='VICTORY' else '魔王战败，上场人类全部失能'),
                                 'ADMIN':'管理员战败，上场人类全部失能'}.get(stage,'终战失败，已无可继续作战的幸存者')}.get(e['cause'],e['cause'])
        text='终止原因：'+reason+'。没有把失败解释为背叛或趋利。\n'+text
    if e['ending_id']=='FIN-B-IMPERFECT':
        g=e['grade'];reasons=[]
        if not g.get('hidden_thread_ready'):reasons.append('最后一封回信尚未取得')
        if g['unfinished']:
            known=[game.cat.events[eid]['name'] for eid in g['unfinished']
                   if cases.get(game.s,eid).get('encountered')]
            reasons.append('尚未办完的接洽：'+'、'.join(known) if known else '仍有未闭合的交接记录')
        if g['exploited']:reasons.append('存在已经实际交割且无法撤销的委托')
        if g['lost']:reasons.append('仍有同行者永久缺席')
        if g['captives']:reasons.append('仍有同行者未能救回')
        text+='\n本次未能完整回接的原因：'+'；'.join(reasons)+'。保留生命支持，不把未回接写成死亡或已获救。'
    return e['ending_id']+' '+title+'\n'+text+'\n本轮已结束；可回看或另建新周目，不能修改已提交结局。'


def _hp_warning(game):
    short=[m['instance_id'] for m in game.s['party'] if 0<m['hp']<m['stats']['hp']]
    return ('\n注意：当前HP未回填（'+'、'.join(short)+'）；升级只补本次新增上限，换装与旧缺口仍保留。'
            '可在下一次安全归城后补满，或使用现有恢复手段。') if short else ''


def describe(game):
    if not campaign.active(game):return '终战需要自然开局的真实章节事实。'
    f=game.s['finale'];r=f['run']
    if f['ending']:return ending_text(game)
    if r:
        if r['stage']=='IDENTITY':
            visible=[]
            for eid,row in r['grade']['events'].items():
                if row['state']=='PROTECTED':visible.append(game.cat.events[eid]['name']+'：已实际保全，回执'+row['receipt']['id'])
                elif row['redeemed_trade']:visible.append(game.cat.events[eid]['name']+'：已交割，实际所得'+str(row['redeemed_trade']))
            return ('ST-401：你是魔王为研究上代回头而建立的独立分身，一直借用旧指挥官的脑体。\n'
                    'ST-402：上代最后的回头来自固定档案，不被当作你的经历。本轮可核对的已交割记录：'+('；'.join(visible) if visible else '无，不编造救援或罪行')+'。\n'
                    'finale choice ASK_TERMS / KEEP_SELF / ACCEPT_MERGER；归并须另行确认，不按财富或事件选择推断。'
                    + ('\n'+game.cat.rules['finale']['identity_choice_contract']['confirmation_text']+' 使用 finale merge CONFIRM；finale cancel 取消。' if r['merger_pending'] else ''))
        if r['stage']=='REGROUP':
            fatigue=r.get('reserve_fatigue') or {}
            detail=('；魔王战后后备损耗：'+'、'.join(f"{mid} {row['before']}→{row['after']}" for mid,row in sorted(fatigue.items()))) if fatigue else ''
            return ('魔王已败，同源竞争权柄已继承；管理员不能直接注销你。仅原随队幸存者可重布阵：'
                    'finale deploy ID on/off；finale place ID q r；finale fight CONFIRM。生命、次数和逻辑时钟保留'+detail+'。')
        return finale_battle.describe(game.s['battle'])
    letter=hidden_thread.public(game)
    letter_text=('尚无已发现的来信线索。' if not letter['discovered'] else
                 '已取得最后回信“让他们自己回答”。' if letter['complete'] else
                 letter['text']+' 可用thread status回看已发现的来信。')
    if 'ST-303' not in game.s['unlocked_facts']:return '先完成研究交付ST-303，再筹备终战。\n'+letter_text+_hp_warning(game)
    g=grade(game)
    budget=next(b for b in game.cat.rules['command_budgets'] if b['milestone']=='FINALE_READY')
    return (RISK+f"\n预选路线{'B（携Agla，须接入）' if carried(game) else 'A（虚拟域继任，肉身仍沉睡）'}。"
            +'\n回信记录：'+letter_text
            +'\n最后回信不替代Agla、实际终战目标与同行者去向；终局按真实结果重新核对。'
            +'\nfinale seal → finale seal CONFIRM 封存Agla；finale carry CONFIRM 恢复携带。'
            +'\nfinale prepare CONFIRM 核对合法队伍并认可风险，开放'+f"{budget['expedition']}/{budget['battle']}"+'；finale enter CONFIRM 单向进入。'
            +'\nB执行者：finale executor 队员完整ID；未指定时选稳定ID的上场人类。'+_hp_warning(game))


def view(game):
    s=game.s;out=[s['version']+' | '+s['phase'],describe(game)]
    if s['finale']['ending']:return '\n'.join(out)
    out.append('预算'+str(s['budget'])+'；操作：finale status / finale moves；战中step / run 120。')
    if s['battle']:
        b=s['battle'];out.append('连续逻辑钟：'+str(b['tick']))
        for a in b['actors']:
            out.append(f"{a['id']} {a['side']} {a['kind']} HP{a['hp']}/{a['stats']['hp']} 格{a['pos']} 剩余次数{ {m['move_id']:('无限' if m.get('cast_limit') is None else m['cast_limit']-a['move_uses'].get(m['move_id'],0)) for m in a['moves']} }")
            if a['pending']:out.append(f"预警 {a['pending']['move_id']} → {a['pending']['cells']} 第{a['pending']['due']}拍释放")
        out.append(bosses.describe(b));out.extend(str(x) for x in b['events'][-5:])
    else:
        out.extend(f"{m['instance_id']} {m['unit_id']} {'上阵' if m['deployed'] else '预备'} HP{m['hp']} 侵蚀{m['erosion']} 格{m['position']}" for m in s['party'])
    return '\n'.join(out)


def begin_demon(game):
    s=game.s;r=s['finale']['run']
    b=combat.create(game.cat,r['encounter'],BOARD,s['party'],s['seed'],s['plans_equipped'],s['preparations'])
    b['battle_id']=r['id']+':DEMON';b['debug_tainted']=False
    import boss_threats
    boss_threats.initialize(b,entry_tick=b['tick'])
    finale_battle.attach(b,r,'DEMON',game.cat.rules['finale'])
    outfitting.start_battle(game,b);facilities.start_battle(game,b);learning.battle_started(game,b)
    r['reserves']={}
    for m in s['party']:
        if m['deployed']:continue
        copy=deepcopy(m);copy['deployed']=True
        rb=combat.create(game.cat,r['encounter'],BOARD,[copy],s['seed'],[],s['preparations'])
        r['reserves'][m['instance_id']]=next(a for a in rb['actors'] if a['side']=='player')
    r['stage']='DEMON';s['battle']=b;s['phase']='BATTLE'


def begin_admin(game):
    s=game.s;r=s['finale']['run'];legal_party(game)
    previous=r['reports'][0];b=deepcopy(previous)
    enc=game.cat.encounter_for_board('BATTLE-ADMIN',BOARD)
    players={a['id']:a for a in previous['actors'] if a['side']=='player'}|r['reserves']
    b['actors']=[]
    for m in s['party']:
        if not m['deployed']:continue
        a=deepcopy(players[m['instance_id']]);check(a['hp']>0,'不能重新部署失能者。')
        a.update(pos=m['position'][:],anchor=m['position'][:],facing=m['facing'],stance=m['stance'])
        b['actors'].append(a)
    for unit in enc['units']:
        a=combat.enemy_actor(unit);combat.initialize_actor(a)
        # New enemies join the existing clock; their first-eligible windows are relative to entry.
        a['next_attack']=b['tick']+1
        for card in a['moves']:card['first_eligible_tick']+=b['tick']
        b['actors'].append(a)
    b.update(result=None,encounter_id='BATTLE-ADMIN',battle_id=r['id']+':ADMIN',events=[],no_change=0,
             closed_edge=None,edge_reservation=None,command_mark=None,before=deepcopy(s['party']),adaptation=None)
    player_ids={a['id'] for a in b['actors'] if a['side']=='player'}
    b['shared_shields']=[p for p in b['shared_shields'] if p['owner'] in player_ids]
    bosses.prepare(b);learning.prepare_battle(game.cat,b,enc)
    import boss_threats
    boss_threats.initialize(b,entry_tick=b['tick'])
    # Fixed expedition defence applies equally to original reserves joining now;
    # assigning the same bonus does not stack or refresh one-use abilities.
    b.pop('outfit_receipt',None);outfitting.start_battle(game,b)
    import battle_enrage
    battle_enrage.initialize(b,entry_tick=b['tick'])
    finale_battle.attach(b,r,'ADMIN',game.cat.rules['finale'])
    campaign.fact(game,'ST-404',{'finale_id':r['id'],'source':'DEMON_PROCESS_ENDED'})
    r['stage']='ADMIN';s['battle']=b;s['phase']='BATTLE'


def fatigue_reserves(game):
    """Apply the 20% continuous-operation cost to non-deployed humans."""
    s=game.s;r=s['finale']['run'];fatigue={}
    for m in s['party']:
        if m['deployed'] or m['hp']<=0 or m['unit_id'].startswith('PET'):continue
        before=m['hp'];amount=min(max(1,m['stats']['hp']//5),max(0,before-1))
        if amount<=0:continue
        m['hp']=before-amount
        fatigue[m['instance_id']]={'before':before,'after':m['hp'],'amount':amount}
        game.log('reserve_fatigue',member=m['instance_id'],before=before,after=m['hp'],
                 amount=before-m['hp'],fraction=.2)
    r['reserve_fatigue']=fatigue
    return fatigue


def finish_battle(game):
    s=game.s;b=s['battle'];r=s['finale']['run']
    check(not s['debug_tainted'] and b.get('finale',{}).get('id')==r['id'],'终战来源不符。')
    for a in b['actors']:
        if a['side']=='player':game.member(a['id'])['hp']=a['hp']
    game.erosion(game.cat.multi['erosion']['per_actual_battle_result'])
    b['after']=deepcopy(s['party']);b['debug_tainted']=False;r['reports'].append(deepcopy(b))
    learning.completed(game,b);facilities.record_battle(game,b)
    if b['result']!='VICTORY':outcome(game,'FIN-C',b['finale']['cause'] or 'BATTLE_DEFEAT');return
    if r['stage']=='DEMON':
        for key in ('DEMON_DEFEATED','ST-403','DEMON_PROCESS_ENDED','CANDIDATE_AUTHORITY_INHERITED'):
            campaign.fact(game,key,{'finale_id':r['id'],'battle_id':b['battle_id']})
        # Continuous-operation pressure also reaches reserves. Leaving someone
        # out of the demon battle no longer means entering the admin projection
        # at untouched full HP.
        fatigue_reserves(game)
        r['stage']='REGROUP';s['battle']=None;s['phase']='FINAL_REGROUP'
        cells=iter(game.cat.boards[BOARD]['player_deploy_cells'])
        for m in s['party']:
            if m['hp']<=0 or m['erosion']>=100:m['deployed']=False
            m['position']=list(next(cells))
        if not any(m['hp']>0 and m['erosion']<100 and not m['unit_id'].startswith('PET') for m in s['party']):outcome(game,'FIN-C','BATTLE_DEFEAT')
    else:
        campaign.fact(game,'ADMIN_DEFEATED',{'finale_id':r['id'],'battle_id':b['battle_id']})
        outcome(game,'FIN-B' if r['route']=='B' else 'FIN-A')


def handle(game,args):
    if args in ([],['status']):return describe(game)
    check(campaign.active(game),'终战仅支持自然开局。')
    s=game.s;f=s['finale'];r=f['run']
    if args==['retry']:
        require_retryable_ending(game)
        path=retry_path(game);check(path.exists(),'没有终战重试检查点；需要先进入过一次终战。')
        return ('将恢复到进入终战前的城镇整备状态（同一周目、同一版本）；当前 FIN-C 会写入 finale.retry_history，'
                '不会删除失败回执的备份。确认：finale retry CONFIRM')
    if args==['retry','CONFIRM']:return retry_checkpoint(game)
    if f['ending']:return ending_text(game)
    if args==['moves']:
        check('ST-303' in s['unlocked_facts'],'研究交付后开放终战预览。')
        lines=[]
        for eid in ('BATTLE-DEMON','BATTLE-ADMIN'):
            enc=game.cat.encounter_for_board(eid,BOARD)
            lines.append(eid+' '+str([(u['enemy_id'],u['position'],u['stats']) for u in enc['units']]))
            lines.extend(str(m) for m in enc['units'][0]['moves'])
        locked=r['encounter'] if r else lock_demon(game)
        lines.append('魔王公开回应：'+str(locked.get('adaptation',{}).get('components',[])))
        lines.append('管理员0适应槽；25%含直接归零启动24拍，B自动前往(3,5)或占格被敌人占据时的相邻格接入两拍，失败不降A。')
        return '\n'.join(lines)
    check(not s['debug_tainted'],'调试污染档不能提交终局。')
    action=args[0]
    if not r:
        check(s['phase']=='TOWN' and not s['campaign']['remembrance'],'请先回城并关闭追忆。')
        check('CH3_COMPLETE' in s['unlocked_facts'],'先完成ST-303研究交付。')
        if args==['seal']:
            check(s['research']['assembly'],'尚未合成Agla。');f['seal_pending']=True
            return '封存后预选A：只接管虚拟世界，肉身继续沉睡，本轮不能事后改为B。再次输入 finale seal CONFIRM 才生效。'
        if args==['seal','CONFIRM']:
            check(f['seal_pending'],'先 finale seal 查看后果。');f.update(sealed=True,seal_pending=False,preparation=None);return describe(game)
        if args==['cancel']:f['seal_pending']=False;return describe(game)
        if args==['carry','CONFIRM']:
            check(s['research']['assembly'],'尚未合成Agla。');f.update(sealed=False,seal_pending=False,preparation=None);return describe(game)
        if len(args)==2 and action=='executor':
            m=game.member(args[1]);check(m in s['party'] and m['deployed'] and m['hp']>0 and not m['unit_id'].startswith('PET'),'执行者须为当前上场人类。')
            f['executor']=m['instance_id'];return '执行者已指定；接入时实际格内人类优先接任。'
        if args==['prepare','CONFIRM']:
            legal_party(game);g=grade(game);research.validate(game)
            proof={'party_ids':[m['instance_id'] for m in s['party']],'risk':RISK}
            for key in ('RISK_ACKNOWLEDGED','LEGAL_PARTY','FINAL_PREPARATION_VALIDATED','FINALE_READY'):campaign.fact(game,key,proof)
            f['preparation']={'route':'B' if carried(game) else 'A','grade':g}
            return '整备合法，预算24/20；仍可在城中调整。\n'+describe(game)
        if args==['enter','CONFIRM']:
            check(f['preparation'] and not f['seal_pending'],'先完成终战整备确认；封存确认必须完成或取消。')
            legal_party(game);research.validate(game);g=grade(game)
            route='B' if carried(game) else 'A';check(f['preparation']['route']==route,'携带选择已变，请重新确认整备。')
            deployed=sorted(m['instance_id'] for m in s['party'] if m['deployed'] and not m['unit_id'].startswith('PET'))
            executor=f.get('executor',deployed[0]);check(executor in deployed,'原执行者已不在上场人类中，请重新指定。')
            enc=lock_demon(game)
            write_retry_checkpoint(game)
            f['run']={'id':uuid.uuid4().hex,'stage':'IDENTITY','route':route,'executor':executor,'merger_pending':False,
                      'party':deepcopy(s['party']),'task_items':deepcopy(s['campaign']['task_items']),
                      'agla_carried':carried(game),'grade':g,'encounter':enc,'reports':[],'reserves':{},
                      'reserve_fatigue':{},'choice':None}
            s['mission']='FINALE';s['phase']='FINAL_CHOICE';s['manifest']=None
            outfitting.depart(game);facilities.depart(game)
            campaign.fact(game,'ST-401',{'finale_id':f['run']['id']})
            return describe(game)
        raise ValueError('finale status / prepare CONFIRM / enter CONFIRM / executor ID / seal / carry CONFIRM')
    if r['stage']=='IDENTITY':
        if args==['choice','ASK_TERMS']:return '归并后你的独立人格终止，收益与权柄归合并后的魔王；不会继续战斗。尚未选择。'
        if args==['choice','ACCEPT_MERGER']:r['merger_pending']=True;return describe(game)
        if args==['cancel']:r['merger_pending']=False;return describe(game)
        if args==['merge','CONFIRM']:
            check(r['merger_pending'],'先选择ACCEPT_MERGER并阅读后果。');r['choice']='ACCEPT_MERGER'
            for key in ('ST-402','PROFIT_ASSIMILATION','INDEPENDENT_PERSONALITY_RELINQUISHED'):campaign.fact(game,key,{'finale_id':r['id'],'choice':r['choice']})
            return outcome(game,'FIN-C','PROFIT_ASSIMILATION')
        if args==['choice','KEEP_SELF']:
            r['choice']='KEEP_SELF';r['merger_pending']=False
            for key in ('ST-402','RESISTANCE_CONFIRMED'):campaign.fact(game,key,{'finale_id':r['id'],'choice':r['choice']})
            begin_demon(game)
            return '你保留独立人格。队员只为自己的生存而战：我不知道你以前是谁，但我不想被它换掉。\n'+describe(game)
        raise ValueError('先明确选择KEEP_SELF、ASK_TERMS或ACCEPT_MERGER；没有默认选项。')
    if r['stage']=='REGROUP':
        if action in ('deploy','place'):
            check(len(args)>=3,'finale deploy ID on/off；finale place ID q r')
            m=game.member(args[1]);check(m in s['party'],'只能调整原随队成员。')
            if action=='deploy':
                check(len(args)==3 and args[2] in ('on','off'),'finale deploy ID on/off')
                check(args[2]=='off' or (m['hp']>0 and m['erosion']<100),'该队员已失能。');m['deployed']=args[2]=='on'
            else:
                check(len(args)==4,'finale place ID q r');pos=list(map(int,args[2:]))
                check(pos in game.cat.boards[BOARD]['player_deploy_cells'],'不属于己方部署格。');m['position']=pos
            return describe(game)
        if args==['fight','CONFIRM']:begin_admin(game);return describe(game)
        raise ValueError('仅可布阵；finale fight CONFIRM 投影管理员并继续战斗。')
    raise ValueError('战斗使用step或run；终战不能返回城镇。')


def validate(game):
    f=game.s['finale'];r=f['run'];e=f['ending'];finale_battle.validate(game.s.get('battle'))
    if not campaign.active(game):check(not r and not e,'试验档不能生成终局。');return
    facts=game.s['campaign']['facts']
    if f['preparation']:check('CH3_COMPLETE' in facts and 'FINALE_READY' in facts,'终战整备缺少前置。')
    if r:
        check('FINALE_READY' in facts and facts['ST-401']['evidence']['finale_id']==r['id'],'终战缺少真实出发回执。')
        check(r['route'] in ('A','B') and r['agla_carried']==(r['route']=='B'),'终战钥匙快照与路线不一致。')
        check([m['instance_id'] for m in game.s['party']]==[m['instance_id'] for m in r['party']],'终战带入城镇新人。')
        if r['route']=='B':check('KEY-AGLA' in r['task_items'] and bool(game.s['research']['assembly']),'B缺少真实Agla。')
        if r['choice']:
            check(facts['ST-402']['evidence']['choice']==r['choice'],'身份选择与回执不符。')
        if r['choice']=='ACCEPT_MERGER':check(not r['reports'] and 'DEMON_DEFEATED' not in facts and e and e['cause']=='PROFIT_ASSIMILATION','归并不能生成战斗胜利。')
        if r['stage'] in ('DEMON','REGROUP','ADMIN'):check(r['choice']=='KEEP_SELF' and 'RESISTANCE_CONFIRMED' in facts,'未经拒绝归并不能战斗。')
        fatigue=r.get('reserve_fatigue',{})
        check(isinstance(fatigue,dict),'后备损耗记录无效。')
        party_ids={m['instance_id'] for m in game.s['party']}
        for mid,row in fatigue.items():
            check(mid in party_ids and isinstance(row.get('amount'),int) and 0<=row['amount']<=max(1,next(m['stats']['hp'] for m in game.s['party'] if m['instance_id']==mid)//5)
                  and row.get('after')==row.get('before')-row['amount'] and row.get('after',0)>=1,'后备损耗记录无效。')
        for b in r['reports']:
            finale_battle.validate(b);bosses.validate(b)
            import battle_enrage
            battle_enrage.validate(b)
            import boss_threats
            boss_threats.validate(b,game.cat)
            check(b['result'] in ('VICTORY','DEFEAT') and b['finale']['id']==r['id'],'终战战报无效。')
        if 'DEMON_PROCESS_ENDED' in facts:check(r['reports'] and r['reports'][0]['result']=='VICTORY','维护窗口没有真实魔王胜利。')
        if 'ADMIN_DEFEATED' in facts:check(len(r['reports'])==2 and r['reports'][-1]['result']=='VICTORY','管理员胜利缺少真实战果。')
    else:check(not ({'ST-401','ST-402','ST-403','ST-404'}&facts.keys()),'终战事实缺少终战实例。')
    if e:
        check(e['sha256']==digest({k:v for k,v in e.items() if k!='sha256'}),'结局回执损坏。')
        check(game.s['ending']==e['ending_id'] and e['ending_id'] in facts,'结局与事实不一致。')
        if e['ending_id']!='FIN-C':check('ADMIN_DEFEATED' in facts,'成功结局缺少管理员胜利。')
        if e['ending_id'].startswith('FIN-B'):
            check(r['route']=='B' and r['reports'][-1]['finale']['channel']['complete'] and
                  (e['ending_id']=='FIN-B-PERFECT')==e['grade']['perfect'],'B目标或评级缺少证据。')
            if e['ending_id']=='FIN-B-PERFECT':
                check(hidden_thread.grade_ready(game) and e['grade'].get('hidden_thread_ready')
                      and e['grade'].get('hidden_thread_proof',{}).get('sha256')
                          ==game.s['hidden_thread']['steps']['answer']['sha256'],
                      '完美回接缺少最后回信的实际完成证明。')
