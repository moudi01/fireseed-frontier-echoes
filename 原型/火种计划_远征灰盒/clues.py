"""Separate clue book: quest provenance, investigation and protected originals.

This is a view over the authoritative campaign/research ledgers, not a second
inventory. Legacy quest commands remain aliases for town investigation.
"""
import campaign
import research
import recovery

FIELD_SOURCES={
    'MG01':'修钟匠按寄存单标出断誓堡垒旧岗亭的寄存柜；裂口铜哨仍在原编号格内。',
    'MG02':'秦姨按旧衣认领单标出回声林海的旧织坊寄存间；缝补红围巾尚未取回。',
    'MG03':'医舍保管人按捐赠条目标出沉息湖区的旧药站；缺页药簿仍留在原药箱夹层。',
    'MG04':'工具保管人按归还单标出脉炉工场的停用工具柜；刻名扳手尚未取回。',
}


def field_source(uid):return {'scene_id':'Q-OBS-'+uid+'-FIELD','statement':FIELD_SOURCES[uid]}


def describe(game):
    if not campaign.active(game):return '线索册需要自然开局；不共用装备、材料或消耗品背包。'
    c=game.s['campaign'];lines=['线索册（独立任务记录，不占携行容量；已收录线索不会因普通败战丢失）']
    for uid,q in campaign.QUESTS.items():
        if q['gate'] not in c['facts']:
            lines.append(f"{uid} 待开放：{q['gate']}");continue
        row=c['quests'].get(uid,{});target=recovery.state(game)['targets'].get(uid)
        status='已收录' if 'collect' in row else '现场待取回' if target else '证词已核实' if 'witness' in row else '已查阅登记' if 'record' in row else '待查阅'
        lines.append(f"{uid} {q['item']}：{status}；原委托费用{q['cost']}")
        if target:lines.append('  固定地点：'+target['anchor']['region']+'/'+target['anchor']['site']+'；'+target['source']['statement'])
    for iid in research.FRAGMENTS:
        if iid in c['task_items']:lines.append(research.name(game,iid)+'：已收录；来源 '+c['task_items'][iid]['source'])
    if 'KEY-AGLA' in c['task_items']:lines.append('Agla：已装配，独立任务载体；携带状态用 agla status 查看。')
    lines.append('clue record/witness/collect MG01；collect需追加CONFIRM。核实后可 clue locate MG01 CONFIRM 选择现场自取，再 recover quote/start MG01。城内代领与现场自取二选一，不重复发原物；现场额外消耗专线日与补给，不增加奖励。')
    return '\n'.join(lines)


def handle(game,args):
    if not args or args==['status']:return describe(game)
    campaign.check(campaign.active(game),'请使用自然开局线索册。')
    campaign.check(len(args)>=2 and args[1] in campaign.QUESTS,'clue record/witness/collect/locate MG01..MG04')
    action,uid=args[:2]
    if action=='show':
        campaign.check(args==['show',uid],'clue show MG01..MG04')
        q=campaign.QUESTS[uid];c=game.s['campaign']
        campaign.check(q['gate'] in c['facts'],'线索尚未开放：'+q['gate'])
        row=c['quests'].get(uid,{})
        text=f"{q['item']}；记录：{row or '尚未调查'}"
        if 'witness' in row and 'collect' not in row:
            text+='\n现场线索：'+FIELD_SOURCES[uid]+f"\n现场自取先支付原委托费用{q['cost']}，再走1战/1日调查专线；基础1补给，可按搜救所减免。也可继续原城内代领；选定现场后不能重复代领。"
        return text
    if action=='locate':
        campaign.check(args==['locate',uid,'CONFIRM'],'定位现场自取会支付原委托费用，并锁定固定地点；clue locate MG01 CONFIRM')
        target=recovery.register_original(game,uid,field_source(uid))
        return '已选择现场自取，原委托费用仅付一次；失败可重试同一地点，不重付原委托费。\n'+str(target)+'\n'+recovery.describe(game)
    campaign.check(action in ('record','witness','collect'),'clue record/witness/collect/locate MG01..MG04')
    return campaign.handle(game,'quest',[uid,action]+args[2:])
