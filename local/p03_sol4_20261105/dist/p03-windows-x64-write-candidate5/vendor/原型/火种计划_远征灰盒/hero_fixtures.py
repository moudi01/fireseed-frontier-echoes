"""Explicit Lv2/MID/Q1, six-person, Cost9/12 comparison teams; not recruitment."""
from copy import deepcopy
import equipment
import roster_content

TEAMS={h:([h,'M02','S01','S02','S03','S03'],9) for h in ('H01','H02','H03','H04','H05','H06')}
TEAMS.update({'H04-PET':(['H04','M02','S01','S02','S03','PET-H04'],9),
 'PAIR':(['H01','H03','M02','M03','S01','S03'],12),
 'PAIR-MOVE':(['H04','H05','M02','M03','S01','S03'],12),
 'BASE9':(['M01','M02','M03','S01','S02','S03'],9),
 'BASE9-SPELL':(['M04','M02','M03','S01','S02','S03'],9),
 'BASE12':(['M01','M02','M03','M04','M01','M03'],12)})
TEAMS.update({h:([h,'M02','S01','S02','S03','S03'],9) for h in ('H07',*roster_content.HEROES)})
TEAMS.update({m:([m,'M02','M03','S01','S02','S03'],9) for m in roster_content.MERCENARIES})
TEAMS.update({h:([h,'M02','S01','S02','S03','S03'],10) for h in ('H11','H12')})
TEAMS={key:(units,sum(4 if uid.startswith('H') else 2 if uid.startswith('M') else 1 for uid in units)) for key,(units,_) in TEAMS.items()}
PROFILES={'H02':'S03','H04':'S03','H05':'M01','H06':'M04'}


def install(game,key):
    import save_validation
    save_validation.require_new_fixture(game)
    cat=game.cat;units,budget=TEAMS[key]
    for m in game.s['party']:game.s['gear_storage'].extend(m['gear_instances'])
    bases={x['id']:x for x in cat.rules['units'].values()};bases.update(cat.rules['mercenaries']);bases.update(cat.rules['hero_templates']);bases['PET-H04']=cat.rules['companion_template']
    party=[]
    for i,uid in enumerate(units):
        base=bases[uid];birth=deepcopy(base['stats']) if 'stats' in base else {k:sum(v)//2 for k,v in base['ranges'].items()}
        stats={k:v+base['growth'][k] for k,v in birth.items()}
        templates=cat.config['equipment_profiles']['Q1_CONTROL'].get(PROFILES.get(uid,uid),[])
        if not templates and (uid in roster_content.GEAR_FAMILIES or uid=='H07'):
            families=roster_content.GEAR_FAMILIES.get(uid,('EF02','EF07'))
            templates=[next(f for f in families if cat.gear[f+'-Q1']['slot']=='war_gear')+'-Q1','EF07-Q1']
        for gid in templates:
            from balance_v062 import gear_modifiers
            for k,v in gear_modifiers(cat,gid,uid).items():stats[k]+=v
        m=dict(instance_id=f'HT-{i+1:02}',unit_id=uid,stats=stats,birth_stats=birth,hp=stats['hp'],erosion=0,xp=0,level=2,injury_days=0,
               deployed=True,gear=list(templates),gear_instances=[],cost=4 if uid.startswith('H') else 2 if uid.startswith('M') else 1,
               attack_type=base['attack_type'],range=base['range'],interval=base['interval'],position=list(cat.formation[i]),stance='advance',facing=1)
        m.update({k:base[k] for k in ('basic_medium','locomotion') if k in base})
        for template in templates:equipment.issue(game,template,m['gear_instances'],{'kind':'hero_cost_fixture','member':m['instance_id'],'randomized':False})
        party.append(m)
    game.s.update(party=party,team_id=key,budget={**game.s['budget'],'battle':budget,'expedition':budget+4})
    game.s['fixture_notice']+=' 人员模块显式同预算试验队：Lv2/MID/Q1，六人，Cost'+str(budget)+'；通用武器防具不冒充专属武器或自然招募／应召。'
    assert sum(m['cost'] for m in party)==budget
    save_validation.initialize_enrollment(game,hero_fixture=True)
    game.persist()
