"""An unsigned correspondence, grounded in completed case receipts.

Discovery only observes delivery. Four town actions must still be performed;
neither reading nor the internal humanity factor completes the correspondence.
"""
from copy import deepcopy
import hashlib
import json

import cases

VERSION = 'UNSIGNED-LETTERS-0.83'
AUTHOR_SCOPE = 'CONTROLLED_SCENARIO_NOT_NATURAL_ACQUISITION'
CATEGORIES = {
    'EV03': 'ESCORT', 'EV07': 'ESCORT', 'EV28': 'ESCORT',
    'EV05': 'RETURN', 'EV19': 'RETURN', 'EV09': 'CARGO',
    'EV12': 'LOCAL', 'EV16': 'LOCAL', 'EV22': 'LOCAL', 'EV25': 'LOCAL',
}
LETTERS = {
    'EV03': '搬运工的安置回信', 'EV05': '伤工与工单的回信',
    'EV07': '旧驿站两名逃工的回信', 'EV09': '安置街收水住户的回信',
    'EV12': '商队簿主的回信', 'EV16': '原契继承人的回信',
    'EV19': '医舍药箱接收人的回信', 'EV22': '工人代表的回信',
    'EV25': '行李认领人的回信', 'EV28': '码头家属们的回信',
}
CATEGORY_NAMES = dict(ESCORT='护送交接', RETURN='返城交付', CARGO='装载转运', LOCAL='现场处置')
ORDER = ('inquire', 'assemble', 'follow', 'answer')
TEXT = {
    'discovery': '一张没署名的纸从接收处送来：“人已经到了。这里有人记得，你把话说到了最后。若想问后续，回城后找当班收信员。”',
    'inquire': '收信员没有替任何人评价你：“挑三份不同的回执，至少有两种不同的交接经过。让来信彼此对照，别让一句好听的话替别人作证。”',
    'assemble': '几封信上的人名与接收处对上了。纸角另添了一行：“还有别处的人等着回音。等更多不同接应关系真正有了收据，再来跟进。”',
    'follow': '后续回信到了：“档案归档以后，别替我们填写最后一页。等每一处已经托付的事情有了交代，让我们自己回答。”',
    'answer': '最后一封回信附着各处接收人的签名。你把名册递回，没有替他们回答。信的题头终于写明：“让他们自己回答。”',
}


def check(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def initialize(game):
    game.s.setdefault('hidden_thread', dict(version=VERSION, stage=0,
        discovery=None, proofs={}, steps={}, commission=None, attempts=[], errand_completion=None))


def state(game):
    check('hidden_thread' in game.s, '本档未初始化回信记录。')
    return game.s['hidden_thread']


def _trip(game, expedition):
    if expedition == game.s['expedition_no'] and game.s.get('manifest') is not None:
        return game.s
    return next((h for h in game.s.get('completed_history', [])
                 if h['expedition_no'] == expedition), None)


def _safe_summary(trip):
    summary = trip.get('summary') or {}
    check(summary.get('result') not in (None, 'DEFEAT')
          and bool(summary.get('settlement_id')), '交付缺少实际安全归城结算。')
    return {key: deepcopy(summary.get(key)) for key in ('result', 'settlement_id', 'day')}


def _scene(game, eid, receipt):
    expedition = receipt.get('expedition_no')
    check(type(expedition) is int and 1 <= expedition <= game.s['expedition_no'], '接收回执缺少真实趟次。')
    trip = _trip(game, expedition)
    check(trip is not None and trip.get('manifest'), '接收回执缺少当前或已归档现场。')
    matches = []
    for rid, region in trip.get('regions', {}).items():
        definition = trip['manifest'].get('regions', {}).get(rid, {})
        for site, current in region.get('events', {}).items():
            binding = definition.get('events', {}).get(site, {})
            actual = current.get('receipt') or {}
            if (binding.get('event_id') == eid and current.get('state') == 'RESOLVED'
                    and actual.get('option') == 'PROTECTED'):
                matches.append((rid, site, binding, actual))
    check(len(matches) == 1, '接收回执必须对应唯一已完成的保全现场。')
    rid, site, binding, actual = matches[0]
    check('HUMANITY' in binding.get('enabled_options', []), '原现场没有对应的保全服务。')
    return trip, dict(expedition=expedition, region=rid, site=site,
                      mission=trip.get('mission'), event=eid,
                      scene_receipt=deepcopy(actual)), binding


def _ever_sold(game, eid, row):
    if row['state'] == 'EXPLOITED' or row.get('trade_credit'):
        return True
    return any(r.get('event_id') == eid
               and (r.get('receipt') or {}).get('option') == 'EXPLOITED'
               for r in game.s.get('event_memory', {}).values())


def _proof(game, eid):
    row = cases.get(game.s, eid)
    if row['state'] != 'PROTECTED':
        return None
    receipt = row.get('receipt') or {}
    check(row.get('enabled') and receipt.get('id') == game.cat.events[eid]['protection_receipt_id']
          and game.s['private_case_factors'].get(eid) == 10 and not _ever_sold(game, eid, row),
          '保全回信与原案件回执不一致：'+eid)
    result = dict(event=eid, category=CATEGORIES[eid], name=LETTERS[eid],
                  receipt_id=receipt['id'], receipt=deepcopy(receipt))
    if receipt.get('scope') == AUTHOR_SCOPE:
        # Legacy author scenarios remain usable as declared fixtures, never as
        # evidence that the natural acquisition/delivery was played through.
        result.update(kind='LEGACY_AUTHOR_FIXTURE', source=None)
    else:
        check(row.get('encountered'), '尚未接洽的对象不能签发回信。')
        trip, source, binding = _scene(game, eid, receipt)
        category = CATEGORIES[eid]
        if category == 'LOCAL':
            cfg = cases.CONFIG[eid]
            check(all(receipt.get(key) == value for key, value in cases.service(eid).items())
                  and binding.get('case_service') == cases.service(eid)
                  and receipt.get('action') == cfg['action']
                  and receipt.get('witnessed') is True and receipt.get('action_completed') is True,
                  '现场回信缺少原物件、接收人或实际完成见证。')
            expected = dict(destroy='DESTROYED', release='CLAIM_STUB_DESTROYED_PAY_STUB_RETURNED',
                            receive='ACCEPTED')[cfg['action']]
            check(receipt.get('object_state') == expected
                  and receipt.get('accepted') == (cfg['action'] != 'destroy'), '现场接收结果无效。')
        elif category == 'ESCORT':
            import refugee
            cfg = refugee.profile(eid)
            check(receipt.get('person_id') == row['person_id']
                  and receipt.get('person_ids') == cfg['object_ids']
                  and receipt.get('whole_group_received') is True
                  and receipt.get('destination') == cfg['receiver']
                  and receipt.get('receiver') == cfg['receiver'] and bool(receipt.get('path')),
                  '护送回信不是原人实际完成接收的回执。')
            if receipt.get('mode') == 'ESCORT':
                escort_rows = [r for r in trip.get('escort_receipts', [])
                               if r.get('purpose') == eid
                               and r.get('status') in ('SAFE_EXIT_LOCKED', 'SETTLED')]
                check(len(escort_rows) == 1, '只有在途承诺，尚无实际接收站交接。')
                source['escort'] = {key: deepcopy(escort_rows[0][key]) for key in
                                    ('id', 'leader', 'member_ids', 'purpose')}
            else:
                check(receipt.get('mode') == 'RETURN', '护送接收方式无效。')
                source['settlement'] = _safe_summary(trip)
        elif category == 'RETURN':
            import medicine
            destination = cases.CONFIG[eid]['receiver'] if eid in cases.CONFIG else medicine.DESTINATION
            check(receipt.get('box_id') == row['box_id']
                  and receipt.get('object_id') == row['box_id']
                  and receipt.get('destination') == destination and bool(receipt.get('path')),
                  '返城回信不是原对象送达的回执。')
            source['settlement'] = _safe_summary(trip)
            summary = trip['summary']
            delivered = summary.get('case_deliveries', {}).get(eid)
            if eid == 'EV19':
                delivered = delivered or summary.get('medicine_delivery')
            check(delivered == receipt and receipt.get('settlement_id') == summary['settlement_id'],
                  '送医／药箱回信缺少实际归城交付记录。')
        else:
            import water
            check(receipt.get('cargo_id') == row['cargo_id']
                  and receipt.get('destination') == water.DESTINATION
                  and any(r.get('success') is True and r.get('expedition_no') == receipt['expedition_no']
                          and r.get('cargo_id') == row['cargo_id']
                          and r.get('visited_regions') == receipt.get('visited_regions')
                          for r in row['transport_history']), '运水回信缺少成功转运记录。')
            source['settlement'] = _safe_summary(trip)
        result.update(kind='RUNTIME_RECEIPT', source=source)
    result['sha256'] = digest(result)
    return result


def _collect(game):
    return {eid: proof for eid in sorted(CATEGORIES)
            if (proof := _proof(game, eid)) is not None}


def _seal(body):
    result = deepcopy(body); result['sha256'] = digest(body)
    return result


def _sources(proofs, ids):
    return {eid: proofs[eid]['sha256'] for eid in sorted(ids)}


ERRAND_MODES = {
    'SUPPLY': dict(name='随队补给', supply=2, site='S'),
    'TRACE': dict(name='现场取证', supply=0, site='X'),
}


def _target_region(game, eid):
    proof = state(game)['proofs'][eid]
    # Only declared legacy author inputs lack an actual scene. Never turn
    # their fallback target into a claim of natural acquisition.
    return (proof.get('source') or {}).get('region') or game.cat.events[eid]['trigger']['region_ids'][0]


def _commission(game, args):
    data = state(game)
    check(game.s['phase'] == 'TOWN' and 'assemble' in data['steps'], '先在城镇完成三份回信对证，再选择后续委托。')
    check(len(args) == 4 and args[-1] == 'CONFIRM', 'thread commission SUPPLY/TRACE EVxx CONFIRM')
    mode, eid = args[1].upper(), args[2].upper()
    check(mode in ERRAND_MODES and eid in data['steps']['assemble']['sources'], '请选择补给或取证，以及三份对证回信中的一份。')
    previous = data['commission']
    if previous:
        check((mode,eid) == (previous['mode'],previous['event']), '已约定接应方式和对象，不能重选或刷新。')
        return '这份委托已经登记；thread status 查看实际进度。'
    body = dict(id='UNSIGNED-ERRAND', mode=mode, event=eid,
        target_region=_target_region(game,eid), supply=ERRAND_MODES[mode]['supply'],
        assemble_sha256=data['steps']['assemble']['sha256'], day=game.s['day'],
        expedition=game.s['expedition_no'], seq=game.s['sequence']+1)
    data['commission'] = _seal(body)
    game.log('hidden_errand_commissioned', commission=deepcopy(data['commission']))
    return '委托已登记；后续普通远征到指定接应点交接，再把凭据安全带回。'


def depart(game):
    """After the ordinary manifest and base departure cost, in its transaction."""
    data = state(game); plan = data['commission']; s = game.s
    if not plan or data['errand_completion'] or s.get('mission') != 'ORDINARY':
        return
    if plan['target_region'] not in s['manifest']['regions']:
        return
    check(not any(a['expedition']==s['expedition_no'] for a in data['attempts']), '本趟委托已经绑定，不能重复出发扣款。')
    cost = plan['supply']
    check(s['bank']['supply'] >= cost, '本路线还需预留委托补给2；出发和委托费用一并结算。')
    before = s['bank']['supply']; s['bank']['supply'] -= cost
    attempt = dict(id=plan['sha256']+':'+str(s['expedition_no']),
        expedition=s['expedition_no'], commission_sha256=plan['sha256'],
        manifest_sha256=s['manifest']['manifest_sha256'], supply=cost,
        supply_before=before, supply_after=s['bank']['supply'],
        departure_seq=s['sequence']+1, status='ACTIVE', delivery=None, settlement=None)
    data['attempts'].append(attempt)
    game.log('hidden_errand_departed', attempt_id=attempt['id'],
        manifest_sha256=attempt['manifest_sha256'], supply=cost, supply_before=before,
        supply_after=attempt['supply_after'], commission_sha256=plan['sha256'])


def _gate_report(trip, rid):
    binding = trip.get('manifest',{}).get('regions',{}).get(rid,{}).get('encounters',{}).get('G',{})
    reports = [b for b in trip.get('battle_reports', [])
        if b.get('result')=='VICTORY' and b.get('debug_tainted') is False and
        b.get('encounter_id')==binding.get('encounter_id') and b.get('board_id')==binding.get('board_id') and
        (b.get('journey_conditions') or {}).get('context',{}).get('region')==rid and
        (b.get('journey_conditions') or {}).get('context',{}).get('site')=='G']
    check('G' in trip.get('regions',{}).get(rid,{}).get('cleared',[]) and len(reports)==1,
        '现场取证需要本趟真实打赢目标地区门战，才能到出口接收。')
    return reports[0]['battle_id']


def _deliver(game, args):
    check(args == ['deliver','CONFIRM'], 'thread deliver CONFIRM')
    data = state(game); plan = data['commission']; s = game.s
    check(s['phase']=='EXPLORE' and s.get('mission')=='ORDINARY', '委托需要在普通远征的实际接应点交接。')
    check(not s.get('debug_tainted'), '使用强制战果的试验不能签发正式接应凭据。')
    check(plan and not data['errand_completion'], '没有待交接的委托。')
    attempt = next((a for a in data['attempts'] if a['expedition']==s['expedition_no']),None)
    check(attempt and attempt['manifest_sha256']==s['manifest']['manifest_sha256'], '本趟没有在出发时绑定这份委托。')
    check(s['region']==plan['target_region'] and s['site']==ERRAND_MODES[plan['mode']]['site'],
        '尚未到委托指定接应点；thread status 查看地区和节点。')
    if attempt['delivery']:
        return '凭据已交接，仍需同趟安全归城。'
    gate = _gate_report(s,s['region']) if plan['mode']=='TRACE' else None
    receipt = _seal(dict(id='UNSIGNED-ERRAND-DELIVERY', commission_sha256=plan['sha256'],
        attempt_id=attempt['id'], mode=plan['mode'], event=plan['event'],
        expedition=s['expedition_no'], region=s['region'], site=s['site'],
        manifest_sha256=attempt['manifest_sha256'], gate_battle_id=gate,
        day=s['day'], seq=s['sequence']+1))
    attempt.update(delivery=receipt,status='SIGNED')
    game.log('hidden_errand_delivered', attempt_id=attempt['id'], receipt=deepcopy(receipt))
    return '实际交接完成；凭据须同趟安全带回，才能跟进下一封回信。'


def _errand_settlement(attempt, summary):
    return _seal(dict(id='UNSIGNED-ERRAND-RETURN', expedition=attempt['expedition'],
        manifest_sha256=attempt['manifest_sha256'], settlement_id=summary['settlement_id'],
        result=summary['result'], day=summary['day'],
        delivery_sha256=attempt['delivery']['sha256'] if attempt['delivery'] else None))


def _errand_completion(plan, attempt):
    return _seal(dict(id='UNSIGNED-ERRAND-COMPLETE', commission_sha256=plan['sha256'],
        attempt_id=attempt['id'], delivery_sha256=attempt['delivery']['sha256'],
        settlement_sha256=attempt['settlement']['sha256']))


def _errand_status(summary, delivery):
    return 'FAILED' if summary['result']=='DEFEAT' or summary.get('debug_tainted') else 'COMPLETE' if delivery else 'INCOMPLETE'


def _sync_errand(game):
    data = state(game)
    for attempt in data['attempts']:
        if attempt['status'] not in ('ACTIVE','SIGNED'):
            continue
        trip = _trip(game,attempt['expedition']); summary = (trip or {}).get('summary') or {}
        if not summary.get('settlement_id') or not summary.get('result'):
            continue
        attempt['settlement'] = _errand_settlement(attempt,summary)
        status = _errand_status(summary,attempt['delivery'])
        attempt['status'] = status
        if status=='COMPLETE':
            data['errand_completion'] = _errand_completion(data['commission'],attempt)
        game.log('hidden_errand_returned', attempt_id=attempt['id'], status=status,
            settlement_sha256=attempt['settlement']['sha256'])


def _validate_errand(game):
    data = state(game); plan = data.get('commission'); attempts = data.get('attempts')
    check(isinstance(attempts,list) and 'errand_completion' in data, '回信委托容器无效。')
    if plan is None:
        check(not attempts and data['errand_completion'] is None, '没有委托却出现行动或完成凭据。')
        return
    assembled = data['steps'].get('assemble')
    check(assembled and plan.get('mode') in ERRAND_MODES and plan.get('event') in assembled['sources'], '委托没有对证来源。')
    check(plan.get('sha256')==digest({k:v for k,v in plan.items() if k!='sha256'})
        and plan.get('id')=='UNSIGNED-ERRAND' and plan.get('assemble_sha256')==assembled['sha256']
        and plan.get('target_region')==_target_region(game,plan['event'])
        and plan.get('supply')==ERRAND_MODES[plan['mode']]['supply']
        and type(plan.get('day')) is int and assembled['day']<=plan['day']<=game.s['day']
        and type(plan.get('expedition')) is int and assembled['expedition']<=plan['expedition']<=game.s['expedition_no']
        and type(plan.get('seq')) is int, '委托对象、费用或对证链无效。')
    journal = {row['seq']:row for row in game.s['journal']}
    accepted = journal.get(plan['seq'],{})
    check(accepted.get('type')=='hidden_errand_commissioned' and accepted.get('commission')==plan,
        '委托缺少实际登记记录。')
    check(len({a.get('expedition') for a in attempts})==len(attempts), '同趟委托重复。')
    completed = []
    for attempt in attempts:
        n = attempt.get('expedition'); trip = _trip(game,n)
        check(type(n) is int and plan['expedition']<=n<=game.s['expedition_no']
            and trip and trip.get('mission')=='ORDINARY' and trip.get('manifest'), '委托缺少普通远征来源。')
        check(attempt.get('id')==plan['sha256']+':'+str(n)
            and attempt.get('commission_sha256')==plan['sha256']
            and attempt.get('manifest_sha256')==trip['manifest']['manifest_sha256']
            and plan['target_region'] in trip['manifest']['regions']
            and attempt.get('supply')==plan['supply']
            and type(attempt.get('supply_before')) is int
            and attempt.get('supply_after')==attempt['supply_before']-plan['supply']
            and attempt['supply_after']>=0, '委托路线绑定或实付补给不符。')
        departed = journal.get(attempt.get('departure_seq'),{})
        check(type(attempt.get('departure_seq')) is int and attempt['departure_seq']>plan['seq']
            and departed.get('type')=='hidden_errand_departed'
            and all(departed.get(k)==attempt[k] for k in ('manifest_sha256','supply','supply_before','supply_after','commission_sha256'))
            and departed.get('attempt_id')==attempt['id'] and departed.get('expedition_no')==n,
            '委托缺少实际出发与扣款记录。')
        delivery = attempt.get('delivery')
        if delivery:
            site = ERRAND_MODES[plan['mode']]['site']
            gate = _gate_report(trip,plan['target_region']) if plan['mode']=='TRACE' else None
            check(delivery.get('sha256')==digest({k:v for k,v in delivery.items() if k!='sha256'})
                and delivery.get('id')=='UNSIGNED-ERRAND-DELIVERY'
                and delivery.get('commission_sha256')==plan['sha256'] and delivery.get('attempt_id')==attempt['id']
                and delivery.get('mode')==plan['mode'] and delivery.get('event')==plan['event']
                and delivery.get('expedition')==n and delivery.get('region')==plan['target_region']
                and delivery.get('site')==site and delivery.get('manifest_sha256')==attempt['manifest_sha256']
                and delivery.get('gate_battle_id')==gate
                and site in trip.get('regions',{}).get(plan['target_region'],{}).get('seen',[])
                and type(delivery.get('day')) is int and plan['day']<=delivery['day']<=game.s['day']
                and type(delivery.get('seq')) is int and delivery['seq']>attempt['departure_seq'],
                '委托交接缺少实际接应点、门战或签收来源。')
            delivered = journal.get(delivery['seq'],{})
            check(delivered.get('type')=='hidden_errand_delivered' and delivered.get('receipt')==delivery
                and delivered.get('region')==plan['target_region'] and delivered.get('site')==site
                and delivered.get('expedition_no')==n, '委托签收与现场记录不符。')
        summary = trip.get('summary') or {}
        if summary.get('settlement_id') and summary.get('result'):
            expected = _errand_status(summary,delivery)
            check(attempt.get('settlement')==_errand_settlement(attempt,summary)
                and attempt.get('status')==expected, '委托没有对应同趟实际归城结果。')
            if expected=='COMPLETE':completed.append(attempt)
        else:
            check(attempt.get('settlement') is None and attempt.get('status')==('SIGNED' if delivery else 'ACTIVE'),
                '未实际归城却提前完成委托。')
    check(len(completed)<=1 and data['errand_completion']==(_errand_completion(plan,completed[0]) if completed else None),
        '委托完成证明没有真实安全交接。')


def sync(game):
    data = state(game); proofs = _collect(game)
    for eid, proof in proofs.items():
        if eid in data['proofs']:
            check(data['proofs'][eid] == proof, '已经收到的回信来源被改写。')
        else:
            data['proofs'][eid] = deepcopy(proof)
    if proofs and data['discovery'] is None:
        first = min(proofs, key=lambda eid: (proofs[eid]['receipt'].get('expedition_no', 0),
                                            proofs[eid]['receipt'].get('day', 0), eid))
        data['discovery'] = _seal(dict(id='UNSIGNED-FIRST-LETTER', day=game.s['day'],
            expedition=game.s['expedition_no'], sources=_sources(proofs, [first]), text=TEXT['discovery']))
        data['stage'] = 1
        game.log('hidden_letter_received', source=first, proof=proofs[first]['sha256'])
    _sync_errand(game)


def _story_proof(game):
    if 'ST-303' not in game.s.get('unlocked_facts', []):
        return None
    fact = (game.s.get('campaign') or {}).get('facts', {}).get('ST-303')
    if not fact:
        return None
    evidence = fact.get('evidence')
    delivery = game.s.get('research', {}).get('delivery')
    if delivery and evidence == delivery:
        return dict(kind='RESEARCH_DELIVERY', evidence_sha256=digest(evidence))
    if isinstance(evidence, dict) and evidence.get('scope') == AUTHOR_SCOPE:
        return dict(kind='LEGACY_AUTHOR_FIXTURE', evidence_sha256=digest(evidence))
    return None


def _commit(game, action, ids, story=None):
    data = state(game); index = ORDER.index(action)
    previous = data['discovery'] if index == 0 else data['steps'][ORDER[index-1]]
    body = dict(id='UNSIGNED-'+action.upper(), action=action, sequence=index+1,
        day=game.s['day'], expedition=game.s['expedition_no'],
        sources=_sources(data['proofs'], ids), previous_sha256=previous['sha256'], text=TEXT[action])
    if story is not None:
        body['story'] = deepcopy(story)
    if action == 'follow':
        body['errand_sha256'] = data['errand_completion']['sha256']
    data['steps'][action] = _seal(body)
    data['stage'] = 1 if action == 'inquire' else index+1
    game.log('hidden_thread_step', action=action, proof=data['steps'][action]['sha256'])
    return TEXT[action]


def handle(game, args):
    if not args or args in (['status'], ['read']):
        return describe(game)
    if args[0] == 'read':
        check(len(args) == 2 and args[1] in ORDER, 'thread read inquire/assemble/follow/answer')
        row = state(game)['steps'].get(args[1])
        check(row is not None, '这封回信尚未收到。')
        return row['text']
    if args[0] == 'commission':
        return _commission(game,args)
    if args[0] == 'deliver':
        return _deliver(game,args)
    check(game.s['phase'] == 'TOWN', '回信跟进需要在城镇与收信员交谈。')
    data = state(game)
    check(data['discovery'] is not None, '还没有收到可以追问的来信。')
    action = args[0]
    check(action in ORDER, 'thread inquire/assemble/follow/answer CONFIRM；thread read 回看。')
    if action == 'assemble':
        check(len(args) == 3 and args[2] == 'CONFIRM', 'thread assemble EVxx,EVyy,EVzz CONFIRM')
        ids = args[1].upper().split(',')
        check(len(ids) == len(set(ids)) == 3, '请选择三份不同的真实回执。')
    else:
        check(args == [action, 'CONFIRM'], 'thread '+action+' CONFIRM')
        ids = []
    if action in data['steps']:
        if action == 'assemble':
            check(set(ids) == set(data['steps'][action]['sources']), '这次对证已经完成，不能重选或刷新。')
        return data['steps'][action]['text']
    index = ORDER.index(action)
    check(set(data['steps']) == set(ORDER[:index]), '请先完成上一封回信的实际跟进。')
    proofs = _collect(game)
    check(all(eid in data['proofs'] and data['proofs'][eid] == proof
              for eid, proof in proofs.items()), '新接收回信尚未同步。')
    if action == 'inquire':
        return _commit(game, action, list(data['discovery']['sources']))
    if action == 'assemble':
        check(set(ids) <= set(proofs) and len({proofs[eid]['category'] for eid in ids}) >= 2,
              '对证需要真实完成的三份回执，且至少有两种不同交接方式。')
        return _commit(game, action, ids)
    if action == 'follow':
        check(data['errand_completion'] is not None, '先完成后续远征委托并把凭据安全带回；thread status 查看两种接应方式。')
        check(len(proofs) >= 7 and len({p['category'] for p in proofs.values()}) >= 3,
              '更多不同接应关系的回信还未齐，尚不能跟进后续回信。')
        return _commit(game, action, list(proofs))
    story = _story_proof(game)
    check(story is not None, '研究档案尚未正式交付，最后一封回信还不能寄出。')
    check(set(proofs) == set(CATEGORIES)
          and not any(_ever_sold(game, eid, cases.get(game.s, eid)) for eid in CATEGORIES),
          '回信仍有未闭合的交接，或已有不可撤销的交割；不能替对方签名。')
    return _commit(game, action, list(proofs), story)


def validate(game):
    data = state(game)
    check(data.get('version') == VERSION and isinstance(data.get('proofs'), dict)
          and isinstance(data.get('steps'), dict), '回信版本或记录无效。')
    proofs = _collect(game)
    check(set(data['proofs']) <= set(proofs)
          and all(p == proofs[eid] for eid, p in data['proofs'].items()), '回信来源缺失或被改写。')
    discovery = data.get('discovery'); steps = data['steps']
    check(bool(data['proofs']) == bool(discovery), '首封来信与真实来源不符。')
    check(set(steps) == set(ORDER[:len(steps)]), '回信步骤被跳过或插入。')
    expected_stage = 0 if not discovery else max(1, len(steps))
    check(type(data.get('stage')) is int and data['stage'] == expected_stage, '回信阶段与步骤不符。')
    _validate_errand(game)
    if discovery is None:
        check(not steps, '没有首封来信却完成了跟进。')
        return
    check(discovery.get('id') == 'UNSIGNED-FIRST-LETTER' and discovery.get('text') == TEXT['discovery']
          and len(discovery.get('sources', {})) == 1, '首封来信无效。')
    previous = None
    for index, row in enumerate([discovery]+[steps[a] for a in ORDER if a in steps]):
        check(row.get('sha256') == digest({k:v for k,v in row.items() if k != 'sha256'}), '回信证明损坏。')
        check(type(row.get('day')) is int and 0 <= row['day'] <= game.s['day']
              and type(row.get('expedition')) is int
              and 1 <= row['expedition'] <= game.s['expedition_no'], '回信时间或趟次无效。')
        sources = row.get('sources', {})
        check(bool(sources) and set(sources) <= set(data['proofs'])
              and all(value == data['proofs'][eid]['sha256'] for eid,value in sources.items()),
              '回信使用了未实际取得的接收证明。')
        if index:
            action = ORDER[index-1]
            check(row.get('id') == 'UNSIGNED-'+action.upper() and row.get('action') == action
                  and row.get('sequence') == index and row.get('text') == TEXT[action]
                  and row.get('previous_sha256') == previous['sha256']
                  and row['day'] >= previous['day'] and row['expedition'] >= previous['expedition'],
                  '回信链条缺少顺序实际跟进。')
            categories = {data['proofs'][eid]['category'] for eid in sources}
            if action == 'inquire':
                check(sources == discovery['sources'], '询问没有沿首封来信进行。')
            elif action == 'assemble':
                check(len(sources) == 3 and len(categories) >= 2, '三份回执对证无效。')
            elif action == 'follow':
                check(len(sources) >= 7 and len(categories) >= 3, '后续回信缺少不同接应关系。')
                check(data['errand_completion'] is not None and row.get('errand_sha256')==data['errand_completion']['sha256'],
                    '后续回信缺少实际远征交接与安全归城。')
            else:
                check(set(sources) == set(CATEGORIES) and row.get('story') == _story_proof(game)
                      and row.get('story') is not None, '最终回信缺少全部原回执或研究交付。')
        previous = row


def grade_ready(game):
    if not game.s.get('hidden_thread', {}).get('steps', {}).get('answer'):
        return False
    validate(game)
    return set(_collect(game)) == set(CATEGORIES)


def _author_fixture(data):
    return (any(p['kind'] == 'LEGACY_AUTHOR_FIXTURE' for p in data['proofs'].values())
            or any(row.get('story', {}).get('kind') == 'LEGACY_AUTHOR_FIXTURE'
                   for row in data['steps'].values()))


def public(game):
    data = state(game)
    if data['discovery'] is None:
        return dict(discovered=False)
    steps = data['steps']; proofs = data['proofs']; actions = []
    if 'inquire' not in steps:
        actions = ['inquire']
    elif 'assemble' not in steps:
        actions = ['assemble']
    elif 'follow' not in steps:
        if data['errand_completion'] and len(proofs) >= 7 and len({p['category'] for p in proofs.values()}) >= 3:
            actions = ['follow']
    elif 'answer' not in steps and set(proofs) == set(CATEGORIES) and _story_proof(game):
        actions = ['answer']
    letters = [dict(id=eid, name=proof['name'], kind=CATEGORY_NAMES[proof['category']],
                    receipt_id=proof['receipt_id']) for eid,proof in sorted(proofs.items())]
    targets = [dict(event=eid, region=(rid:=_target_region(game,eid)), region_name=game.cat.regions[rid]['name'])
        for eid in sorted(steps['assemble']['sources'])] if 'assemble' in steps and data['commission'] is None else []
    latest = steps[ORDER[len(steps)-1]]['text'] if steps else data['discovery']['text']
    return dict(discovered=True, complete='answer' in steps, stage=data['stage'],
                letters=letters, actions=actions if game.s['phase'] == 'TOWN' else [], text=latest,
                commission=deepcopy(data['commission']), attempts=deepcopy(data['attempts']),
                commission_targets=targets,
                errand_complete=data['errand_completion'] is not None,
                author_fixture=_author_fixture(data))


def describe(game):
    view = public(game)
    if not view['discovered']:
        return '还没有收到可回看的来信。'
    lines = ['未署名的回信：'+('已收到最后回信。' if view['complete'] else '还有来往未结束。'), view['text']]
    if view['letters']:
        lines.append('已收到：'+'；'.join(x['id']+' '+x['name'] for x in view['letters']))
    if view['actions']:
        for action in view['actions']:
            lines.append('thread assemble EVxx,EVyy,EVzz CONFIRM' if action == 'assemble'
                         else 'thread '+action+' CONFIRM')
    if 'assemble' in state(game)['steps']:
        plan = view['commission']
        if plan is None:
            lines.append('后续接应：从对证的三份回信选择对象；SUPPLY在可达目标的普通路线出发时支付2补给，到该区S交接，改走别支或早返不退；TRACE不额外付补给，但须打赢该区G后到X取证。均需安全归城。')
            lines.append('thread commission SUPPLY/TRACE EVxx CONFIRM；可选对象：'+','.join(sorted(state(game)['steps']['assemble']['sources'])))
            lines.append('接应地区：'+'；'.join(x['event']+'→'+x['region']+' '+x['region_name'] for x in view['commission_targets']))
        else:
            spec = ERRAND_MODES[plan['mode']]
            lines.append(f"接应：{plan['event']}／{spec['name']}，目标{plan['target_region']}-{spec['site']}；"+
                ('已安全带回凭据。' if view['errand_complete'] else 'thread deliver CONFIRM 实际交接，再同趟安全归城。'))
            if not view['errand_complete']:
                lines.append('可达目标的路线出发额外补给：'+str(plan['supply'])+'；改走别支、早返或败战不退，重试重新支付；未交接或败战不完成。')
    lines.append('thread read 回看；阅读不支付、不推进步骤。')
    if view.get('author_fixture'):
        lines.append('本档含显式作者夹具来源，不作为自然获取证明。')
    return '\n'.join(lines)
