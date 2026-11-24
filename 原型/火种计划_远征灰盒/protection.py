"""Finite protection: actual hostile delay and unique final damage recipients."""
import combat as c


def install(cat):
    text='甲环护卫：守护一名相邻可行动友军，优先生命比例最低者。来自甲环卫正面三方向的直接攻击由其代受，每拍1次、每战2次，不连锁、不额外命中；侧后攻击可绕过。环护主动仍独立消耗。'
    cat.enemy_templates['EN04']['briefing']=text
    for encounter in cat.encounters.values():
        for unit in encounter['units']:
            if unit['enemy_id']=='EN04':unit['briefing']=text


def delayed(actor,source,tick,log):
    """Call only after a real +1 start/release delay, never on mark application."""
    if actor['kind']!='M04' or actor['hp']<=0 or actor.get('steady_used') or not source or source['side']==actor['side']:return
    actor['steady_used']=True
    from balance_v062 import passive_value
    amount=passive_value('M04-P',8)
    actor['timed_shields'].append({'effect':'M04-P','source':actor['id'],'amount':amount,'created':tick,'expires':tick+1})
    log('steady_shield',actor=actor['id'],source=source['id'],amount=amount,expires=tick+1)


def actionable(actor,tick):
    return actor['hp']>0 and not actor.get('mechanism') and not actor.get('boss_part') and tick>=actor.get('active_from',1)


def wards(alive,tick):
    """Freeze one ward per guard after movement and before damage settlement."""
    pairs={}
    for guard in alive:
        guard['guard_ward']=None
        if guard['kind']!='EN04' or not actionable(guard,tick) or guard['guard_uses']>=2:continue
        neighbors=[a for a in alive if a!=guard and a['side']==guard['side'] and actionable(a,tick) and c.distance(a['pos'],guard['pos'])==1]
        if neighbors:
            ward=min(neighbors,key=lambda a:(a['hp']/a['stats']['hp'],a['id']))
            pairs[guard['id']]=ward['id'];guard['guard_ward']=ward['id']
    return pairs


def resolve(hits,alive,tick,front,log):
    """One pass: redirected hits never become input for another guard.

    Area hits remain direct damage. A guard also inside the same attack is one
    final recipient, not two damage packets. No movement or new action occurs.
    """
    pairs=wards(alive,tick);result=[];seen=set()
    for attacker,victim,action,origin in hits:
        original=victim
        direct=action['kind']=='damage' and not action.get('derived',False) and action.get('guard_bypass_target')!=victim['id']
        guards=[g for g in alive if direct and g['side']==victim['side'] and attacker['side']!=g['side']
                and pairs.get(g['id'])==victim['id'] and g['guard_uses']<2 and g['guard_last_tick']!=tick
                and front(g,action.get('projectile_origin',origin))]
        if guards:
            victim=min(guards,key=lambda g:g['id']);victim['guard_uses']+=1;victim['guard_last_tick']=tick
            origin=action.get('projectile_origin',origin)[:]
            log('guard_redirect',actor=victim['id'],ward=original['id'],attacker=attacker['id'],action_id=action['id'],move=action['move_id'],used=victim['guard_uses'])
        key=(attacker['id'],action['id'],victim['id'])
        if key in seen:
            log('guard_hit_merged',actor=attacker['id'],target=victim['id'],original_target=original['id'],action_id=action['id'])
            continue
        seen.add(key);result.append((attacker,victim,action,origin))
    return result


def describe(battle):
    result=[]
    for a in battle['actors']:
        if a['hp']<=0:continue
        if a['kind']=='EN04':result.append('甲环护卫 '+a['id']+'：本拍守护 '+str(a.get('guard_ward'))+'，代受已用 '+str(a['guard_uses'])+'/2')
        if a['kind']=='M04':result.append('稳媒 '+a['id']+'：'+('本场已触发' if a['steady_used'] else '等待首次敌方实际延后'))
    return '\n'.join(result)
