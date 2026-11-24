"""Independent representative combat fixture, without expedition rewards."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shlex
from data import Catalog
from engine import BASE, VERSION, Game, atomic_json, require
import combat
import commander
import gear_affixes as gear
import skill_books as books
import hero_fixtures
import heroes
import bosses

BOARDS = {'INTRO-EN04':'OPEN', 'INTRO-EN10':'MIRROR_COURT', 'INTRO-EN11':'OPEN', 'EL02-SIDE':'DOUBLE_BRIDGE',
          'RG03-N03':'MIRROR_COURT', 'RG04-N03':'SALT_CROSSING', 'RG02-E01':'DOUBLE_BRIDGE', 'INTRO-EN08':'OPEN', 'INTRO-EN09':'OPEN', 'EL05-SIDE':'MIRROR_COURT',
          'RG03-N01':'MIRROR_COURT', 'RG03-N02':'MIRROR_COURT', 'RG03-E01':'MIRROR_COURT', 'INTRO-EN07':'SALT_CROSSING', 'EL04-SIDE':'SALT_CROSSING', 'EL01-SIDE':'OPEN',
          'RG04-N01':'SALT_CROSSING', 'RG04-E01':'SALT_CROSSING', 'INTRO-EN05':'SALT_CROSSING', 'INTRO-EN16':'OPEN', 'INTRO-EN18':'OPEN',
          'RG05-N02':'FORGE_CROSSING', 'G12-CALIBRATION':'OPEN', 'RG02-N03':'DUAL_FLANK', 'RG02-E02':'DOUBLE_BRIDGE',
          'INTRO-EN13':'OPEN', 'RG05-N01':'FORGE_CROSSING', 'RG05-E02':'FORGE_CROSSING',
          'INTRO-EN14':'OPEN', 'INTRO-EN15':'OPEN', 'EL06-SIDE':'FORGE_CROSSING',
          'RG04-N02':'MIRROR_COURT', 'RG05-N03':'FORGE_CROSSING', 'RG05-N04':'FORGE_CROSSING',
          'FX-RG01-N01':'OPEN', 'FX-RG06-N01':'DUAL_FLANK', 'FX-RG07-N01':'DRY_ISLAND',
          'FX-RG08-N01':'CITADEL_RING', 'FX-RG02-N01':'CITADEL_RING', 'FX-RG03-N01':'MIRROR_COURT',
          'FX-RG04-N01':'SALT_CROSSING', 'FX-RG05-N01':'FORGE_CROSSING'}
BOARDS.update(bosses.ENCOUNTERS)
NOTICE = '独立战斗试验：Lv2/MID，初始Q1满血；可显式开启词条样例库存，换装不回血。技能书按实际8铜采购学习，无准备品；plan可从十二项试验方案中选最多3项。非自然招募或掉落，不发奖励，不计正式平衡。'
HELP = 'memory fixture CONFIRM（显式原物／证词试验条件）| memory evidence/retain/skip 窗口ID | memory recall（胜后追忆） | hero list；hero 01 recall self/pet；hero 01 power on/off | book list/show/buy/learn/equip/queue/auto/claim（book show 01查看适用条件） | status | stance 01 advance/hold/flank/evade | skill 03 counter/damage/off | CMD: skill 01 auto/mark/volley/off | gear list | gear wear 05 装备实例ID | gear remove 05 weapon/armor | craft CO01/CO02 | use CO01 02 | use CO02 01,02 | place 01 q r facing | plan PL01 PL07 PL11（试验库存） | fight | step [拍数] | run [最多拍数] | flee CONFIRM | save | quit'


class Lab:
    def __init__(self, encounter='RG02-N03', team='T03', stance='advance', mode='counter', seed=11, catalog=None, orders='auto', affixes=False):
        require(encounter in BOARDS, '请选择已接入的代表遭遇：'+', '.join(BOARDS))
        require(team in ('T02','T03','CMD')+tuple(hero_fixtures.TEAMS), '请选择T02/T03、CMD或已列出的英雄／同预算试验队。')
        self.game = Game.new(route='R06',team='T02' if team=='CMD' else 'T03' if team in hero_fixtures.TEAMS else team,pack='P0',seed=seed,catalog=catalog)
        if team=='CMD':
            import save_validation
            save_validation.require_new_fixture(self.game)
            commander.install_fixture(self.game)
            save_validation.initialize_enrollment(self.game,commander_fixture=True)
        if team in hero_fixtures.TEAMS:hero_fixtures.install(self.game,team)
        if affixes:gear.initialize_lab(self.game)
        self.encounter=encounter;self.board=BOARDS[encounter];self.battle=None;self.commands=[]
        allowed=self.game.cat.boards[self.board]['player_deploy_cells'];used=[]
        for m in self.game.s['party']:
            if m['deployed']:
                position=m['position'] if m['position'] in allowed and m['position'] not in used else next(p for p in allowed if p not in used)
                m['position']=position[:];used.append(position)
            self.game.execute('stance '+m['instance_id']+' '+stance)
            if m['unit_id']=='M04':self.game.execute('skill '+m['instance_id']+' '+mode)
            if m['unit_id']=='CMD':self.game.execute('skill '+m['instance_id']+' '+orders)
        self.game.validate_deployment(self.board)

    def execute(self, command):
        before=(deepcopy(self.game.s),deepcopy(self.battle))
        try:
            args=shlex.split(command);require(args,'请输入命令。');verb=args[0]
            if verb=='memory':
                if args[1:]==['fixture','CONFIRM']:
                    require(self.battle is None or self.battle['result']=='VICTORY','仅开战前或实际胜后可设置显式证据试验条件。')
                    uid=self.encounter.replace('BATTLE-','');require(uid.startswith('MG') and uid in bosses.IDS,'仅四魔将具有记忆窗口。')
                    self.game.s['boss_evidence']={'items':['OBS-'+uid],'verified_testimonies':[uid],'fixture':True}
                    if self.battle:self.battle['boss_memory'][uid].update(eligible=True,source=deepcopy(self.game.s['boss_evidence']))
                elif args[1:]==['recall']:
                    require(self.battle and self.battle['result']=='VICTORY','仅实际胜利后可追忆，不重开敌阵。')
                    bosses.recall(self.battle)
                else:
                    require(self.battle is not None and len(args)==3,'memory evidence/retain/skip 窗口ID')
                    bosses.dialogue(self.battle,args[1],args[2])
            elif verb=='hero':
                require(self.battle is None or args[1:]==['list'],'开战后锁定英雄策略。')
                result=self.game.execute(command);self.commands.append(command);return result
            elif verb=='book':
                require(self.battle is None or args[1:] in ([],['list']) or (len(args)>1 and args[1]=='show'),'开战后锁定学习、书槽和队列。')
                result=self.game.execute(command);self.commands.append(command);return result
            elif verb in ('craft','use'):
                require(self.battle is None or self.battle['result'],'战斗及暂停中不能制作或使用药品。')
                require(len(args)>1 and args[1] in ('CO01','CO02'),'独立实验只接CO01／CO02恢复品；沿用实际配方扣款和携行袋。')
                self.game.execute(command)
            elif verb=='gear':
                require('affix_inventory' in self.game.s,'用 --affixes 开启显式测试装备库存。')
                if args==['gear','list']:
                    for item in self.game.s['affix_inventory']:print(json.dumps(item,ensure_ascii=False))
                else:
                    require(self.battle is None,'开战后锁定装备实例，暂停也不能换装。')
                    require(len(args)==4 and args[1] in ('wear','remove'),'gear wear 队员 实例ID / gear remove 队员 weapon/armor')
                    member=self.game.member(args[2])
                    if args[1]=='wear':
                        item=next((i for i in self.game.s['affix_inventory'] if i['instance_id']==args[3]),None)
                        require(item is not None,'装备不在库存中。')
                        gear.change(self.game,member,item['slot'],item['instance_id'])
                    else:gear.change(self.game,member,args[3])
            elif verb in ('stance','skill','place'):
                require(self.battle is None,'战斗开始后不能更改配置。')
                if verb=='place':
                    require(len(args)==5,'place ID q r facing')
                    m=self.game.member(args[1]);pos=list(map(int,args[2:4]));facing=int(args[4])
                    require(pos in self.game.cat.boards[self.board]['player_deploy_cells'] and 0<=facing<=5,'部署格或朝向不合法。')
                    m.update(position=pos,facing=facing)
                else:self.game.execute(command)
            elif verb=='plan':
                if args[1:] in ([],['list']):
                    from plan_offers import RULES
                    return '\n'.join(k+' '+self.game.cat.plans[k]['name']+'：'+v for k,v in RULES.items())
                require(self.battle is None,'开战后不能改方案。')
                chosen=[] if args[1:]==['clear'] else [x.upper() for x in args[1:]]
                require(len(chosen)==len(set(chosen))<=3 and set(chosen)<=combat.SUPPORTED_PLANS,'试验最多装备3项有效方案。')
                self.game.s['plans_equipped']=chosen
                self.game.s['plans_owned']=chosen[:]
            elif verb=='fight':
                require(self.battle is None,'本次试验已开战；新建试验才能重新开始。')
                self.game.validate_deployment(self.board)
                self.battle=combat.create(self.game.cat,self.game.cat.encounter_for_board(self.encounter,self.board),self.board,self.game.s['party'],self.game.s['seed'],self.game.s['plans_equipped'],{},boss_context=self.game.s.get('boss_evidence'))
            elif verb in ('step','run','flee'):
                require(self.battle and not self.battle['result'],'没有进行中的战斗。')
                if verb=='flee':
                    require(args==['flee','CONFIRM'],'撤退需 flee CONFIRM；执行一拍追击。')
                    require(not bosses.paused(self.battle),'先回应或跳过记忆窗口。')
                    self.battle['retreat_requested']=True;count=1
                else:count=int(args[1]) if len(args)>1 else (1 if verb=='step' else 600)
                require(1<=count<=600,'单次推进1—600拍。')
                for _ in range(count):
                    combat.step(self.game.cat,self.battle)
                    if self.battle['result'] or bosses.paused(self.battle):break
                if self.battle['result'] and not self.game.s.get('lab_outcome_applied'):
                    actors={a['id']:a for a in self.battle['actors'] if a['side']=='player'}
                    for member in self.game.s['party']:
                        if member['instance_id'] in actors:member['hp']=actors[member['instance_id']]['hp']
                    self.game.s['lab_outcome_applied']=True
            else:raise ValueError('未知指令。'+HELP)
            if self.battle and self.battle['result'] and not self.game.s.get('lab_outcome_applied'):
                actors={a['id']:a for a in self.battle['actors'] if a['side']=='player'}
                for member in self.game.s['party']:
                    if member['instance_id'] in actors:member['hp']=actors[member['instance_id']]['hp']
                self.game.s['lab_outcome_applied']=True
            self.commands.append(command)
        except Exception:
            self.game.s,self.battle=before;raise

    def summary(self):
        b=self.battle
        if not b:return {'result':'NOT_STARTED'}
        players=[a for a in b['actors'] if a['side']=='player'];events=b['events']
        return {'encounter':self.encounter,'board':self.board,'result':b['result'],'ticks':b['tick'],
                'standing':sum(a['hp']>0 for a in players),'hp':sum(a['hp'] for a in players),
                'hp_max':sum(a['stats']['hp'] for a in players),
                'releases':dict(Counter(e['move'] for e in events if e['type']=='release')),
                'delays':sum(e['type']=='cast_delayed' for e in events),
                'evades':sum(e['type']=='evade' for e in events),
                'effective_heal':sum(e['effective'] for e in events if e['type']=='heal'),
                'command_granted':sum(len(e['members']) for e in events if e['type']=='command_grant'),
                'command_responses':sum(e['type']=='command_response' for e in events),
                'command_lost':sum(e['type']=='command_token_lost' for e in events),
                'command_extra_hp_damage':sum(e['hp_damage'] for e in events if e['type']=='hit' and e['action']=='CMD-EXTRA'),
                'criticals':sum(e['type']=='hit' and e.get('critical',False) for e in events),
                'dodges':sum(e['type']=='evaded' for e in events),
                'life_stolen':sum(e['effective'] for e in events if e['type']=='life_steal'),
                'bandage_shield_added':sum(e['added'] for e in events if e['type']=='bandage_shield'),
                'affix_triggers':dict(Counter(e['effect'] for e in events if e['type']=='affix_trigger')),
                'misses':dict(Counter(e['move'] for e in events if e['type']=='skill_miss'))}

    def status(self):
        print(NOTICE);print(self.encounter,self.board);print(books.describe(self.game))
        if self.game.s['team_id']=='CMD':print(self.game.s['fixture_notice'])
        print('部署区：',self.game.cat.boards[self.board]['player_deploy_cells'])
        if self.battle:
            b=self.battle
            print(json.dumps(self.summary(),ensure_ascii=False))
            for a in self.battle['actors']:
                print(a['id'],a['kind'],'HP',a['hp'],'位置',a['pos'],'起手',a['pending'],'历史',a['basic_history'],'号令加攻',a.get('command_attack_bonus',0),'待响应',a.get('command_token'))
                if a.get('gear_instances'):print('装备',a['gear_instances'],'触发次数',a['affix_uses'],'有效双防',[combat.stat(a,k,self.battle['tick']) for k in ('physical_defense','magic_defense')])
            print(bosses.describe(b))
            print('指挥目标：',self.battle.get('command_mark'))
            import necromancy
            if necromancy.describe(b):print(necromancy.describe(b))
            import reinforcements
            if reinforcements.describe(b):print(reinforcements.describe(b))
            import enemy_support
            if enemy_support.describe(b):print(enemy_support.describe(b))
            import spatial_moves
            if spatial_moves.describe(b):print(spatial_moves.describe(b))
            import sweeps
            if sweeps.describe(b):print(sweeps.describe(b))
            import veil
            if veil.describe(b):print(veil.describe(b))
            import action_timing
            if action_timing.describe(b):print(action_timing.describe(b))
            import protection
            if protection.describe(b):print(protection.describe(b))
            import battle_plans
            print(battle_plans.describe(b))
            for e in self.battle['events'][-12:]:print(json.dumps(e,ensure_ascii=False))
            if self.battle['result']:
                print('战后当前生命（恢复品不回写上方战斗结果）：',[(m['instance_id'],m['hp'],m['stats']['hp']) for m in self.game.s['party']])
                print('携行药品',self.game.s['pouch'],'资金',self.game.s['bank'])
        else:
            for m in self.game.s['party']:
                print(m['instance_id'],m['unit_id'],'出战' if m['deployed'] else '预备',m['position'],m['stance'],m.get('skill_mode','auto'))
                if 'gear_instances' in m:print('已穿装备',m['gear_instances'],'HP',m['hp'],'面板上限',m['stats']['hp'])
            print('特殊地形：',[(c['q'],c['r'],c['terrain_id']) for c in self.game.cat.boards[self.board]['cells'] if c['terrain_id']!='GROUND'])
            for enemy in self.game.cat.encounter_for_board(self.encounter,self.board)['units']:
                print('敌方',enemy['instance_id'],enemy.get('name',enemy['enemy_id']),'位置',enemy['position'],'面板',enemy['stats'],'招式',enemy.get('moves',[]))
                if enemy.get('briefing'):print('读招：',enemy['briefing'])
                if enemy.get('phases'):print('阶段：',enemy['phases'],'固定预览正轴：',enemy['facing'])
            for part in self.game.cat.encounter_for_board(self.encounter,self.board).get('board_parts',[]):print('首领部位',part)
            for obj in self.game.cat.encounter_for_board(self.encounter,self.board).get('mechanisms',[]):
                print('机制',obj['instance_id'],obj['name'],'位置',obj['position'],'生命',obj['stats']['hp'],obj['briefing'])

    def save(self,path):
        import save_validation
        save_validation.validate_enrollment(self.game)
        books.validate(self.game)
        heroes.validate(self.game)
        bosses.validate(self.battle)
        gear.validate_lab(self.game)
        atomic_json(path,{'version':VERSION,'source_sha256':self.game.cat.hashes,'runtime_sha256':self.game.cat.runtime_hashes,
                         'scope':NOTICE,'balance_eligible':False,'encounter':self.encounter,'board':self.board,
                         'fixture':self.game.s,'commands':self.commands,'battle':self.battle,'summary':self.summary()})

    @classmethod
    def load(cls,path,catalog=None):
        data=json.loads(Path(path).read_text(encoding='utf8'));cat=catalog or Catalog()
        require(data['version']==VERSION and data['source_sha256']==cat.hashes and data['runtime_sha256']==cat.runtime_hashes,'版本或数据变化，请保留旧记录并新建试验。')
        lab=cls.__new__(cls);lab.game=Game(catalog=cat,state=data['fixture'])
        lab.encounter=data['encounter'];lab.board=data['board'];lab.battle=data['battle'];lab.commands=data['commands']
        import save_validation
        save_validation.validate_enrollment(lab.game)
        gear.validate_lab(lab.game)
        books.validate(lab.game)
        heroes.validate(lab.game)
        bosses.validate(lab.battle)
        return lab


def main():
    parser=argparse.ArgumentParser(description=NOTICE)
    parser.add_argument('--encounter',choices=BOARDS,default='RG02-N03')
    parser.add_argument('--team',choices=['T02','T03','CMD']+list(hero_fixtures.TEAMS),default='T03')
    parser.add_argument('--orders',choices=['auto','mark','volley','off'],default='auto')
    parser.add_argument('--affixes',action='store_true',help='开启明确的测试装备实例库存；不代表自然掉落')
    parser.add_argument('--stance',choices=['advance','hold','flank','evade'],default='advance')
    parser.add_argument('--mode',choices=['counter','damage','off'],default='counter')
    parser.add_argument('--seed',type=int,default=11);parser.add_argument('--auto',action='store_true')
    parser.add_argument('--load',type=Path);parser.add_argument('--output',type=Path,default=BASE/'local/battle_lab.json')
    args=parser.parse_args();lab=Lab.load(args.load) if args.load else Lab(args.encounter,args.team,args.stance,args.mode,args.seed,orders=args.orders,affixes=args.affixes)
    if args.auto:
        if lab.battle is None:lab.execute('fight')
        if not lab.battle['result']:lab.execute('run 600')
        lab.save(args.output);print(json.dumps(lab.summary(),ensure_ascii=False,indent=2));print(args.output);return
    print(HELP);lab.status()
    while True:
        try:
            command=input('battle> ').strip()
            if command in ('quit','exit'):lab.save(args.output);break
            if command in ('help','?'):print(HELP);continue
            if command=='status':lab.status();continue
            if command=='save':lab.save(args.output);print(args.output);continue
            response=lab.execute(command)
            if response:print(response)
            lab.save(args.output);lab.status()
        except (ValueError,IndexError) as e:print('未执行：',e)
        except EOFError:lab.save(args.output);break


if __name__=='__main__':main()
