"""Explicit GEAR-AFFIX samples and battle hooks; no production loot weights."""
from copy import deepcopy

EFFECTS={
 'SEEK':{'name':'觅隙','slot':'weapon','critical_chance':.1,'extra_critical_damage':.5},
 'LEECH':{'name':'汲生','slot':'weapon','life_steal_percent':20},
 'BANDAGE':{'name':'余温包扎','slot':'weapon','shield':4,'duration':2,'limit':2},
 'OVERDRAW':{'name':'透支医护','slot':'weapon','outgoing_heal_percent':40,'paired':'HARDHEAL'},
 'HARDHEAL':{'name':'难愈','slot':'weapon','received_recovery_penalty_percent':30,'paired':'OVERDRAW','negative':True},
 'BREAK':{'name':'击破追击','slot':'weapon','increase':.2,'limit':2},
 'LINING':{'name':'接敌衬层','slot':'armor','reduction':.2,'limit':1},
 'LIGHT':{'name':'轻步护片','slot':'armor','dodge':.2,'duration':2,'limit':1},
 'FURY':{'name':'烈刃','slot':'weapon','increase':.35,'paired':'FRAGILE'},
 'FRAGILE':{'name':'薄护','slot':'weapon','defense_penalty':8,'paired':'FURY','negative':True},
 'HEAVY':{'name':'重铠','slot':'armor','reduction':.25,'paired':'SLOW'},
 'SLOW':{'name':'迟行','slot':'armor','pause_ticks':1,'paired':'HEAVY','negative':True},
 'BASTION':{'name':'困守','slot':'armor','hp_threshold_percent':50,'reduction':.15},
 'RECUP':{'name':'易愈','slot':'armor','received_recovery_percent':40,'paired':'EXPOSED'},
 'EXPOSED':{'name':'易伤','slot':'armor','incoming_damage_percent':20,'paired':'RECUP','negative':True},
 'TECHNIQUE':{'name':'技击','slot':'weapon','increase':.5,'paired':'BLUNT'},
 'BLUNT':{'name':'钝刃','slot':'weapon','basic_damage_penalty_percent':25,'paired':'TECHNIQUE','negative':True},
 'TRIAGE':{'name':'急救','slot':'weapon','outgoing_heal_percent':100,'limit':1,'paired':'FATIGUE'},
 'FATIGUE':{'name':'药力衰减','slot':'weapon','outgoing_heal_penalty_percent':25,'paired':'TRIAGE','negative':True},
 'CHANNEL':{'name':'术式增幅','slot':'weapon','increase':.15},
}
PHYSICAL={'EF01','EF02','EF03','EF06'}


def make(catalog, iid, template, effects, source='explicit_lab_fixture'):
    base=catalog.gear[template];quality=base['quality_id'];slot='weapon' if base['slot']=='war_gear' else 'armor'
    if len(effects)!=len(set(effects)) or any(e not in EFFECTS for e in effects):raise ValueError('词条重复或不存在。')
    if quality=='Q1' and effects:raise ValueError('Q1只有面板。')
    if quality=='Q2' and (len(effects)!=1 or 'paired' in EFFECTS[effects[0]]):raise ValueError('Q2须一条常规词条。')
    if quality=='Q3' and len(effects)!=2:raise ValueError('Q3须两条兼容常规或一组强效／负面。')
    for eid in effects:
        effect=EFFECTS[eid]
        if effect['slot']!=slot:raise ValueError('词条槽位不适配。')
        if effect.get('paired') and effect['paired'] not in effects:raise ValueError('强效和负面必须成对。')
        if eid in ('BREAK','FURY','FRAGILE','TECHNIQUE','BLUNT') and base['family_id'] not in PHYSICAL:raise ValueError('需要物理输出底型。')
        if eid in ('BANDAGE','OVERDRAW','HARDHEAL','TRIAGE','FATIGUE') and base['family_id']!='EF05':raise ValueError('需要医护工具底型EF05。')
        if eid=='CHANNEL' and base['family_id']!='EF04':raise ValueError('需要导雾底型EF04。')
    return {'instance_id':iid,'template_id':template,'panel_version':'TINDER-1.7','slot':slot,
            'effects':[{'effect_id':eid,**deepcopy(EFFECTS[eid])} for eid in effects],
            'source':{'kind':source,'randomized':False}}


def validate(catalog,item):
    if item.get('content_mode')=='legacy_panel':
        from equipment import panel
        expected=panel(catalog,item['instance_id'],item['template_id'],item['source'])
    else:
        expected=make(catalog,item['instance_id'],item['template_id'],[e['effect_id'] for e in item['effects']])
    if item['effects']!=expected['effects'] or item['slot']!=expected['slot'] or item['panel_version']!=expected['panel_version']:
        raise ValueError('装备实例与本版词条／面板规格不一致。')


def initialize_lab(game):
    state=game.s;state['affix_inventory']=[]
    from equipment import register
    for family in ('EF01','EF02','EF03','EF04','EF06'):
        specs=[('Q2',['SEEK']),('Q2',['LEECH']),('Q3',['SEEK','LEECH'])]
        if family in PHYSICAL:specs += [('Q2',['BREAK']),('Q3',['SEEK','BREAK']),('Q3',['FURY','FRAGILE']),('Q3',['TECHNIQUE','BLUNT'])]
        if family=='EF04':specs += [('Q2',['CHANNEL']),('Q3',['SEEK','CHANNEL']),('Q3',['LEECH','CHANNEL'])]
        for quality,ids in specs:
            iid='LAB-'+family+'-'+quality+'-'+'-'.join(ids)
            state['affix_inventory'].append(make(game.cat,iid,family+'-'+quality,ids))
    for family in ('EF07','EF08'):
        for quality,ids in [('Q2',['LINING']),('Q2',['LIGHT']),('Q2',['BASTION']),('Q3',['LINING','LIGHT']),('Q3',['LINING','BASTION']),('Q3',['LIGHT','BASTION']),('Q3',['HEAVY','SLOW']),('Q3',['RECUP','EXPOSED'])]:
            iid='LAB-'+family+'-'+quality+'-'+'-'.join(ids)
            state['affix_inventory'].append(make(game.cat,iid,family+'-'+quality,ids))
    for quality,ids in [('Q2',['BANDAGE']),('Q3',['BANDAGE','LEECH']),('Q3',['BANDAGE','SEEK']),('Q3',['OVERDRAW','HARDHEAL']),('Q3',['TRIAGE','FATIGUE'])]:
        iid='LAB-EF05-'+quality+'-'+'-'.join(ids)
        state['affix_inventory'].append(make(game.cat,iid,'EF05-'+quality,ids))
    for item in state['affix_inventory']:register(game,item)


def validate_party(catalog,party):
    seen=set()
    for member in party:
        items=member.get('gear_instances')
        if items is None:continue  # Legacy panel-only campaign data stays panel-only.
        slots=[]
        if [i['template_id'] for i in items]!=member['gear']:raise ValueError('装备实例与面板列表不同步。')
        for item in items:
            validate(catalog,item);base=catalog.gear[item['template_id']]
            kind='H01' if member['unit_id']=='CMD' else member['unit_id']
            if kind not in base['allowed_unit_ids']:raise ValueError('装备与职业不适配。')
            if item['instance_id'] in seen:raise ValueError('同一装备实例不能穿在两人身上。')
            seen.add(item['instance_id']);slots.append(item['slot'])
        if len(slots)!=len(set(slots)) or len(slots)>2:raise ValueError('固定武器／防具两槽，禁止重复槽。')


def validate_lab(game):
    from equipment import validate as validate_custody
    validate_custody(game)
    if 'affix_inventory' not in game.s:return
    validate_party(game.cat,game.s['party'])
    items=game.s['affix_inventory']+[i for m in game.s['party'] for i in m['gear_instances']]
    ids=[i['instance_id'] for i in items]
    if len(ids)!=len(set(ids)):raise ValueError('装备实例存在重复归属。')
    for item in items:validate(game.cat,item)


def change(game,member,slot,item_id=None):
    from equipment import swap
    validate_lab(game)
    inventory=game.s['affix_inventory']
    item=next((i for i in inventory if i['instance_id']==item_id),None) if item_id else None
    if item_id and item is None:raise ValueError('装备不在可用库存中。')
    swap(game,member,inventory,slot,item)
    validate_lab(game)


def active(actor,eid):
    for item in sorted(actor.get('gear_instances',[]),key=lambda i:i['instance_id']):
        for effect in item['effects']:
            if effect['effect_id']==eid:return item,effect
    return None


def use(actor,eid,tick,log):
    found=active(actor,eid)
    if not found:return None
    item,effect=found;key=item['instance_id']+':'+eid
    used=actor['affix_uses'].get(key,0)
    if used>=effect.get('limit',10**9):return None
    actor['affix_uses'][key]=used+1
    log('affix_trigger',actor=actor['id'],gear=item['instance_id'],effect=eid,use=used+1)
    return effect


def moved(actor,tick,log):
    if active(actor,'SLOW'):
        actor['move_pause_until']=max(actor['move_pause_until'],tick+1)
        log('gear_move_pause',actor=actor['id'],until=tick+1)
    effect=use(actor,'LIGHT',tick,log)
    if effect:actor['gear_dodge']={'amount':effect['dodge'],'valid_from':tick+1,'expires':tick+2}


def dodge(actor,tick):
    buff=actor.get('gear_dodge')
    return min(.5,buff['amount']) if buff and buff['valid_from']<=tick<=buff['expires'] else 0


def defense_penalty(actor):
    effect=active(actor,'FRAGILE')
    return effect[1]['defense_penalty'] if effect else 0


def critical(actor):
    effect=active(actor,'SEEK')
    return (effect[1]['critical_chance'],effect[1]['extra_critical_damage']) if effect else (0,0)


def increase(actor,action,victim_cast,tick,conditional,log):
    fury=active(actor,'FURY') if action['damage_type']=='physical' else None
    if action['move_id']=='BASIC' and victim_cast and victim_cast['due']>tick:
        effect=use(actor,'BREAK',tick,log)
        if effect:conditional=max(conditional,effect['increase'])
    special=active(actor,'TECHNIQUE' if action['damage_type']=='physical' else 'CHANNEL') if active_skill(action) else None
    return min(1,conditional+(fury[1]['increase'] if fury else 0)+(special[1]['increase'] if special else 0))


def active_skill(action):
    return not action.get('derived') and action['move_id'] not in ('BASIC','CMD-EXTRA','EN06-A','EL03-A')


def damage_factors(actor,victim,action):
    blunt=active(actor,'BLUNT') if action['move_id']=='BASIC' and action['damage_type']=='physical' else None
    exposed=active(victim,'EXPOSED')
    return (1-blunt[1]['basic_damage_penalty_percent']/100 if blunt else 1,
            1+exposed[1]['incoming_damage_percent']/100 if exposed else 1)


def reduction(actor,tick,base,log):
    heavy=active(actor,'HEAVY');lining=use(actor,'LINING',tick,log)
    bastion=active(actor,'BASTION')
    # HP is still the tick-start value: heals and hits settle only after this batch.
    low=bastion and actor['hp']*100<=actor['stats']['hp']*bastion[1]['hp_threshold_percent']
    return min(.75,base+(heavy[1]['reduction'] if heavy else 0)+(lining['reduction'] if lining else 0)+(bastion[1]['reduction'] if low else 0))


def leech_credit(actor,action,actual_hp_damage,credits):
    if actual_hp_damage<=0 or action['move_id'] in ('CMD-EXTRA','EN06-A','EL03-A') or action.get('derived'):return
    innate=actor.get('innate_life_steal') if actor.get('side')=='enemy' else None
    effect=active(actor,'LEECH')
    if innate:
        if action['move_id'] not in innate['eligible_moves']:return
        source={'gear':None,'source':innate['source_id'],'percent':innate['percent']}
    elif effect:
        item,rule=effect
        source={'gear':item['instance_id'],'percent':rule['life_steal_percent']}
    else:return
    key=(actor['id'],action['id'])
    if key not in credits:
        credits[key]={'actor':actor,'action_id':action['id'],**source,'damage':0}
    credits[key]['damage']+=actual_hp_damage


def settle_leech(credits,log):
    """Derived recovery after direct settlement; cannot revive or produce resources."""
    for row in credits.values():
        actor=row['actor'];requested=row['damage']*row['percent']//100
        after_received=received_recovery(actor,requested)
        effective=min(after_received,max(0,actor['stats']['hp']-actor['hp'])) if actor['hp']>0 else 0
        actor['hp']+=effective
        origin={'source':row['source']} if 'source' in row else {}
        log('life_steal',actor=actor['id'],action_id=row['action_id'],gear=row['gear'],**origin,
            eligible_damage=row['damage'],requested=requested,after_received=after_received,effective=effective,blocked_by_down=actor['hp']<=0)


def outgoing_heal(actor,amount):
    effect=active(actor,'OVERDRAW')
    triage=active(actor,'TRIAGE')
    if triage:
        used=actor.get('affix_uses',{}).get(triage[0]['instance_id']+':TRIAGE',0)
        fatigue=active(actor,'FATIGUE')
        percent=-fatigue[1]['outgoing_heal_penalty_percent'] if used else triage[1]['outgoing_heal_percent']
        return amount*(100+percent)//100
    return amount*(100+effect[1]['outgoing_heal_percent'])//100 if effect else amount


def active_heal_settled(actor,effective,tick,log):
    if effective>0 and active(actor,'TRIAGE'):use(actor,'TRIAGE',tick,log)


def received_recovery(recipient,amount):
    """Active heals, finite items and life steal share incoming modifiers."""
    effect=active(recipient,'HARDHEAL')
    recup=active(recipient,'RECUP')
    percent=(recup[1]['received_recovery_percent'] if recup else 0)-(effect[1]['received_recovery_penalty_percent'] if effect else 0)
    return amount*(100+percent)//100


def queue_bandage(actor,target,effective,tick,action_id,queue,log):
    found=active(actor,'BANDAGE')
    if effective<=0 or not found:return
    item,effect=found;key=item['instance_id']+':BANDAGE'
    if actor['affix_last_tick'].get(key)==tick:return
    effect=use(actor,'BANDAGE',tick,log)
    if not effect:return
    actor['affix_last_tick'][key]=tick
    queue.append({'actor':actor['id'],'target':target,'gear':item['instance_id'],'action_id':action_id,
                  'amount':effect['shield'],'expires':tick+effect['duration']})


def settle_bandages(queue,tick,log):
    """End-of-tick resource production, never fed back into healing or this tick's hits."""
    for row in queue:
        target=row['target'];added=0;expires=None
        if target['hp']>0:
            pools=target['timed_shields']
            pools[:]=[p for p in pools if p['effect']!='BANDAGE' or (p['expires']>tick and p['amount']>0)]
            old=next((p for p in pools if p['effect']=='BANDAGE'),None)
            if old:
                added=max(0,row['amount']-old['amount']);old['amount']+=added;expires=old['expires']
            else:
                added=row['amount'];expires=row['expires']
                pools.append({'effect':'BANDAGE','source':row['actor'],'gear':row['gear'],'amount':added,
                              'created':tick,'valid_from':tick+1,'expires':expires})
        log('bandage_shield',actor=row['actor'],target=target['id'],gear=row['gear'],action_id=row['action_id'],
            added=added,valid_from=tick+1,expires=expires,blocked_by_down=target['hp']<=0)
