"""Presentation receipts only. All world choices remain in their owning modules."""
from copy import deepcopy


def check(ok, message):
    if not ok: raise ValueError(message)


def initialize(game):
    game.s['narrative'] = {'version': 1, 'enabled': True, 'records': {}, 'order': [], 'active': None}
    if game.s.get('campaign'):
        offer(game, 'opening', '暮汀北门 · 独返', [1, 2, 3, 32])


def close(game, status='ARCHIVED'):
    n=game.s['narrative']
    if n['active']:
        row=n['records'][n['active']]
        if row['status']=='READING':row['status']=status
        n['active']=None



# The authored source remains frozen. These captions describe available facts;
# they never give a pet a voice or attribute another person's experience.
CAPTIONS={
 'TD007':'路上仍有往返的脚印，通向前方。',
 'TD008':'敌人的实际起手已经出现；是否与手势有关，尚无结论。',
 'TD010':'两条旧路均可通行，也可以回访。',
 'TD012':'旧照明座位于路旁；是否点亮以实际交互记录为准。',
 'TD013':'前方有两处动静；可以先查看敌人与部署，再决定开战。',
 'TD017':'远处的轮廓已经淡入阴影，现场没有可确认经过的发言队员。',
 'TD018':'路边留着旧巡路队的箱子，封条仍在；是否领取由实际选择决定。',
 'TD027':'这里可以停留；伤势、携带物品与返程选择以实际状态为准。',
 'TD031':'当前名册与点名结果以实际人员记录为准。',
}
HUMAN_LINES={'TD012':'旧照明座就在这里。要不要点亮，先看清实际情况。',
             'TD013':'前面有两处动静。我们可以先查看敌人与部署。'}


def witnessed(game,member,ref,proof):
    s=game.s;iid=member['instance_id']
    if ref=='TD008':
        b=s.get('battle') or {}
        return b.get('battle_id')==proof.get('battle_id') and any(
            e.get('event_id')==proof.get('event_id') and e.get('type')=='windup'
            and e.get('move')=='EN01-A' for e in b.get('events',[]))
    if ref=='TD017':
        reports=s['battle_reports']
        return any(b.get('battle_id')==proof.get('battle_id') and b.get('result')=='VICTORY'
                   and any(a.get('id')==iid and a.get('side')=='player' and a.get('hp',0)>0
                           for a in b.get('actors',[])) for b in reports)
    return True


def speaker_candidates(game,ref,proof):
    s=game.s
    live={a['id']:a for a in (s.get('battle') or {}).get('actors',[])}
    return [m for m in s['party'] if not m['unit_id'].startswith('PET')
            and m['hp']>0 and m['injury_days']==0
            and (s['phase']=='TOWN' or m.get('deployed'))
            and (s['phase']!='BATTLE' or (m['instance_id'] in live
                 and live[m['instance_id']].get('side')=='player'
                 and live[m['instance_id']]['hp']>0))
            and witnessed(game,m,ref,proof)]

def offer(game, key, title, refs=(), text=None, source='首次远征流程.json', proof=None):
    n=game.s['narrative'];s=game.s
    if key in n['records']:return
    lines=[]
    authored={d['dialogue_id']:d for d in game.cat.tutorial['dialogues']}
    for ref in refs:
        d=authored[f'TD{ref:03}'];speaker=d['speaker_ref'];actor=None
        if speaker=='实际同行队员':
            candidates=speaker_candidates(game,d['dialogue_id'],proof or {})
            actor=candidates[0]['instance_id'] if candidates else None
            speaker=('队员 '+actor) if actor else '现场见闻（无可发言队员）'
        if speaker=='秦姨' and s['phase'] not in ('TOWN','RETURNED','FAILED'):
            speaker='出发前的叮嘱 · 秦姨'
        line_text=d['text']
        if d['speaker_ref']=='实际同行队员':
            line_text=HUMAN_LINES.get(d['dialogue_id'],d['text']) if actor else CAPTIONS[d['dialogue_id']]
        lines.append({'id':d['dialogue_id'],'speaker':speaker,'actor_id':actor,'text':line_text})
    if text:lines.append({'id':'receipt','speaker':'行程记录','actor_id':None,'text':str(text)})
    check(lines,'讲解内容为空。')
    close(game)
    n['records'][key]={'id':key,'title':title,'source':source,'lines':lines,'cursor':0,
                       'status':'READING' if n['enabled'] else 'MUTED',
                       'day':s['day'],'expedition':s['expedition_no'],'region':s['region'],
                       'site':s['site'],'proof':deepcopy(proof or {})}
    n['order'].append(key)
    if n['enabled']:n['active']=key


def windup(game):
    s=game.s;b=s.get('battle')
    if not s.get('campaign') or s['mission']!='TUTORIAL' or not b:return
    actual=next((e for e in reversed(b['events']) if e['type']=='windup' and e.get('move')=='EN01-A'),None)
    if actual:
        offer(game,'first_telegraph','看清敌人的起手',[8,9],
              text='橙色预警标出招式范围。战斗按已部署的位置和策略执行；这段文字不计作调查或学习成果。',
              proof={'battle_id':b['battle_id'],'event_id':actual['event_id'],'tick':actual['tick']})


def sync(game, before, command, result):
    s=game.s
    if not s.get('campaign') or command[0]=='dialogue':return
    n=s['narrative'];facts=s['campaign']['facts'];old=before['campaign']['facts']
    # Never leave an old speaker talking over a different location or outcome.
    context=lambda st:(st['phase'],st['region'],st['site'],st['expedition_no'])
    if context(s)!=context(before):close(game)
    if 'ST-101' in facts and 'ST-101' not in old:
        offer(game,'commission','领取委任 · 整备新队',[4,5,6,31],proof={'fact':'ST-101'})
    if s['mission']=='TUTORIAL':
        trip=s['tutorial_trip'];prefix='trip-'+str(trip['expedition'])+'-'
        if before['phase']=='TOWN' and s['phase']=='EXPLORE':
            offer(game,prefix+'depart','灰栎边道 · 出发',[7],text='沿地面移动，走近地点后交互。走过不等于处理事件；原路可以回访。')
        if s['phase']=='EXPLORE':
            site=s['site'];cleared=game.current['cleared']
            if site=='A':
                if 'A' in cleared:
                    offer(game,prefix+'first_win','前路已清',text='方案候选可在此领取，也可放弃。支路都能回访；下一战前可调整部署。')
                else:offer(game,prefix+'contact','发现敌人',text='敌人和战场已在眼前。检查蓝色部署区与队员位置，再开始战斗；也可退回接敌线外。')
            elif site=='B_SUPPORT':offer(game,prefix+'support','护运站留言',[11])
            elif site=='B_MATERIAL':offer(game,prefix+'materials','旧路材料匣',text='领取材料或留在原处，均可继续。未领取时可在本区域内回来处理。')
            elif site=='C':offer(game,prefix+'rest','旧路歇脚处',[27],text='停留不会自动治疗。检查伤势和携带物品，再决定继续或原路返城。')
            elif site=='D':
                # The teaching observation is an explicit action, not dialogue acknowledgement.
                offer(game,prefix+'observe','远眺巡路',text='依侦路单观察远处巡行，并亲自记录现场。阅读提示不会提交调查。')
            elif site=='G':
                if 'G' in cleared and not s['debug_tainted']:
                    offer(game,prefix+'root_win','根口的远声',[15,16,17,18],
                          text='旧巡路队的箱子仍需自行决定是否领取。前方出口可以安全返城。',
                          proof={'battle_id':s['battle_reports'][-1]['battle_id']})
                elif 'G' not in cleared:offer(game,prefix+'root','根口接敌',[13],text='先查看实际敌人与部署，再决定开战。')
        if s['phase']=='BATTLE' and s['site']=='G' and before['phase']!='BATTLE':
            offer(game,prefix+'root_start','根口交战',[14])
        if trip['observation'] and not (before.get('tutorial_trip') or {}).get('observation'):
            offer(game,prefix+'observation','已记录的现场',text=trip['observation']['observed'],proof=trip['observation'])
        if s['phase'] in ('RETURNED','FAILED','FIN_C') and before['phase'] not in ('RETURNED','FAILED','FIN_C'):
            summary=s['summary'] or {};failed=summary.get('result')=='DEFEAT'
            if failed:
                offer(game,prefix+'return','独自归城',[24,25,26],text='本次去向与期限以搜救所记录为准。阅读或跳过对白不会找回人员。',proof={'result':'DEFEAT'})
            else:
                complete='ST-102' in facts
                # TD028 claims the root was not investigated; don't use it if only the D record is missing.
                refs=[19,20,21] if complete else [19,20]+([28] if 'A' in game.current['cleared'] and 'G' not in game.current['cleared'] else [])
                refs += [22]+([23] if complete else [])+[30]
                offer(game,prefix+'return','归城核对 · '+('调查完成' if complete else '调查未齐'),refs,
                      text=f"实际随队归城 {len(s['party'])} 人。"+('完整侦路报告已入档；旧日志仍需亲自核对。' if complete else '调查未齐；检查两场战斗与D处现场记录，准备好后再出发。'),
                      proof={'result':summary.get('result'),'fact':'ST-102' if complete else None})
    # Existing chapter transactions supply their own already-gated text. Never read future scripts.
    head=command[0];args=command[1:];content=None;key=None;title=None
    if head=='clue' and len(args)>=2 and args[0] in ('record','witness','collect'):
        head='quest';args=[args[1],args[0]]+args[2:]
    if head=='quest' and args:
        if args[0] in ('review','archive','report') and facts!=old:
            key='fact-'+','.join(k for k in facts if k not in old);title='主线交存记录';content=result
        elif len(args)>1 and args[1] in ('record','witness','collect'):
            uid,stage=args[:2];row=s['campaign']['quests'].get(uid,{})
            if stage in row and stage not in before['campaign']['quests'].get(uid,{}):
                key='quest-'+uid+'-'+stage;title='旧物调查 · '+uid
                content=row[stage].get('text') or '已取回：'+row[stage]['name']
    elif head=='summon' and s.get('campaign') and s['campaign']['summons']!=before['campaign']['summons']:
        receipt=max(s['campaign']['summons'].values(),key=lambda r:r['sequence'])
        from roster_content import PERSONAS
        person=PERSONAS[receipt['hero_id']]
        key='hero-acquired-'+receipt['hero_id'];title='应召记录 · '+person['name']
        content=result+'\n关注：'+person['fear']+'\n'+person['role']
    elif head=='research' and s['research']!=before['research']:
        key='research-'+args[0];title='研究记录';content=result
    elif head=='remember' and s['campaign']['remembrance']!=before['campaign']['remembrance'] and result:
        key='remembrance-'+str(s['sequence']);title='追忆记录';content=result
    elif head=='finale' and result and (facts!=old or s['finale']!=before['finale']):
        key='finale-'+str(s['sequence']);title='终局现场记录';content=result
    # Endings can also originate in real combat or ordinary loss, not just a finale command.
    if s['finale']['ending'] and not before['finale']['ending']:
        import finale
        key='ending';title='本轮结局';content=finale.ending_text(game)
    if content:offer(game,key,title,text=content,source='已提交的主线交互正文',proof={'command':' '.join(command)})


def hint(game):
    s=game.s
    if not s.get('campaign'):return ''
    facts=s['campaign']['facts']
    if s['finale']['ending']:return '本轮已结束。可回看已发生的故事；回看不能改写结局。'
    if s['mission']=='FINALE':return '终局选择需在现场明确提交；阅读或跳过对白不代表同意。finale status 查看当前选择。'
    if s['phase']=='TOWN':
        if 'ST-101' not in facts:return '先阅读委任，再自行决定接受：quest commission CONFIRM。'
        if 'ST-102' not in facts:return '检查随行和部署后出发。tutorial recommend CONFIRM 采用建议；tutorial start 开始侦路。'
        if 'ST-103' not in facts:return '与许苇核对带回的调查：quest review CONFIRM。'
        if 'ST-104' not in facts:return '交存核对后的报告：quest archive CONFIRM。'
        return 'quest status 查看已开放委托；clue status 查线索，rescue status 查人员去向。'
    if s['phase']=='BATTLE':return '查看预警、面向与生命。step 推进一拍；run 连续推进。阅读文本不推进战斗。'
    if s['phase']=='EXPLORE' and s['mission']=='TUTORIAL':
        site=s['site'];done=game.current['cleared'];choices=s['tutorial_trip']['choices']
        if site=='A' and 'A' in done and 'plan' not in choices:return '可选方案：tutorial plan PL01 / PL02 / PL05 / PASS；plan PL01 装配已取得方案。'
        if site=='B_SUPPORT' and 'support' not in choices:return 'tutorial support 队员ID 领取护持；tutorial support PASS 放弃。'
        if site=='B_MATERIAL' and 'materials' not in choices:return 'tutorial materials 领取材料；tutorial materials PASS 放弃。'
        if site=='D' and not s['tutorial_trip']['observation']:return 'tutorial observe 记录现场；完成两战后安全返城才交付调查。'
        if site=='G' and 'G' in done and 'cache' not in choices:return 'tutorial cache '+ '/'.join(s['tutorial_trip']['gear_offers'])+' / PASS；然后前往出口。'
        if site=='X' and 'G' in done:return 'return CONFIRM 安全返城并结算。'
        if site in ('A','G') and site not in done:return '检查部署后 fight 开战，或 retreat 退回接敌线外。'
        return '用方向键按钮沿地面移动，走近地点后 interact 地点ID。未完成事件可在本区回访；入口可提前返城。'
    if s['phase'] in ('RETURNED','FAILED'):return '本趟已结算；town 返回城镇整备。人员去向以搜救所实际记录为准。'
    return '走近地点再交互；查看出口与风险后自行决定继续或返回。'


def public(game):
    n=game.s['narrative']
    return {'enabled':n['enabled'],'active':deepcopy(n['records'].get(n['active'])),
            'history':[{'id':k,'title':n['records'][k]['title'],'status':n['records'][k]['status'],
                        'day':n['records'][k]['day']} for k in n['order']], 'hint':hint(game)}


def describe(game):
    n=public(game);row=n['active'];text=n['hint']
    if row:
        line=row['lines'][row['cursor']]
        text+=f"\n【{row['title']} {row['cursor']+1}/{len(row['lines'])}】{line['speaker']}：{line['text']}\ndialogue next / skip；dialogue history 回看目录。"
    return text


def handle(game,args):
    n=game.s['narrative']
    if args in ([],['status']):return describe(game)
    if args==['history']:return '\n'.join(k+' '+n['records'][k]['title'] for k in n['order']) or '尚无已发生的对白。'
    if len(args)==2 and args[0]=='auto':
        check(args[1] in ('on','off'),'dialogue auto on/off')
        n['enabled']=args[1]=='on'
        if not n['enabled']:close(game,'SKIPPED')
        return '自动讲解已'+('开启；不补播历史，历史可自行回看。' if n['enabled'] else '关闭；操作提示和现场风险仍保留。')
    if len(args)==2 and args[0]=='replay':
        check(args[1] in n['records'],'只能回看本周目已经发生的内容。')
        close(game);n['active']=args[1];row=n['records'][args[1]];row['cursor']=0;row['status']='READING'
        return describe(game)
    check(args in (['next'],['skip'],['close']),'dialogue next/skip/close/history/replay 已发生ID/auto on/off')
    if not n['active']:return '当前没有播放中的对白。'
    row=n['records'][n['active']]
    if args==['next'] and row['cursor']+1<len(row['lines']):row['cursor']+=1
    else:close(game,'READ' if args==['next'] else 'SKIPPED')
    return describe(game)


def validate(game):
    n=game.s.get('narrative')
    check(isinstance(n,dict) and n.get('version')==1 and type(n.get('enabled')) is bool,'对白存档格式异常。')
    records=n['records'];order=n['order']
    check(len(order)==len(set(order)) and set(order)==set(records),'对白目录重复或缺失。')
    check(n['active'] is None or n['active'] in records,'对白游标没有对应记录。')
    for key,row in records.items():
        check(row['id']==key and row['lines'] and type(row['cursor']) is int and 0<=row['cursor']<len(row['lines']),'对白阅读位置异常。')
        check(row['status'] in ('READING','READ','SKIPPED','ARCHIVED','MUTED'),'对白状态异常。')
        check((row['status']=='READING')==(n['active']==key),'对白激活状态不一致。')
        check(all(isinstance(line.get('text'),str) and isinstance(line.get('speaker'),str) for line in row['lines']),'对白文字异常。')
