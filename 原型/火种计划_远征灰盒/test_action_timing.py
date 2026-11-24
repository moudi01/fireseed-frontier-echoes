"""Future active starts, release exposure and finite alternating lanes."""
from copy import deepcopy
from contextlib import redirect_stdout
from unittest.mock import patch
import io
import json
import unittest
from data import Catalog
from engine import Game
from battle_lab import Lab
import combat as c
import battle_skills
import action_timing as t


class TimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cat=Catalog()

    def fixture(self,kind='EN11',start=3):
        party=deepcopy(Game.new(catalog=self.cat).s['party'][:1]);party[0].update(deployed=True,position=[3,2])
        u=deepcopy(self.cat.enemy_templates[kind]);u.update(instance_id='enemy',position=[3,3],facing='D4')
        b=c.create(self.cat,{'encounter_id':'timing-contract','units':[u]},'OPEN',party,11,[],{})
        p,n=b['actors']
        for a in (p,n):a.update(root_until=999,range=0,next_attack=999,hp=10000);a['stats']['hp']=10000
        p.update(kind='M01',moves=battle_skills.core_cards('M01'),skill_mode='auto');p['moves'][0]['first_eligible_tick']=start
        if kind!='EN11':p.update(kind='TEST',moves=[])
        if kind=='EL02':n['root_until']=0
        return b,p,n

    def step(self,b,n=1):
        for _ in range(n):c.step(self.cat,b)

    def events(self,b,kind):return [e for e in b['events'] if e['type']==kind]

    def clone(self,b,a,identity,pos):
        other=deepcopy(a);other.update(id=identity,pos=pos,pending=None,move_uses={},action_sequence=0);b['actors'].append(other);return other

    def shot(self,p,n,tick,dtype='physical',attack=100):
        p['stats'][dtype+'_attack']=attack
        p['pending']={'id':'controlled-hit','move_id':'BASIC','kind':'damage','due':tick,'target':n['id'],'range':20,'medium':'near',
                      'max_targets':1,'coefficient':1,'damage_type':dtype,'origin':p['pos'][:],'cells':[]}

    def test_delay_defers_start_without_precharging_or_creating_pending(self):
        b,p,n=self.fixture();self.step(b,3)
        self.assertIsNone(p['pending']);self.assertFalse(p['move_uses']);self.assertEqual(p['action_sequence'],0)
        self.assertEqual(p['deferred_start']['until'],4);self.assertEqual(p['trigger_delay_seen'],1);self.assertFalse(p['trigger_delay'])
        self.step(b);self.assertEqual(p['pending']['due'],5);self.assertEqual(p['move_uses']['M01-A'],1)
        self.assertTrue(p['pending']['delayed']);self.assertEqual(p['pending']['start_delay']['until'],4)
        self.step(b);self.assertEqual(p['move_ready']['M01-A'],8)

    def test_ordinary_attack_still_occurs_on_deferred_start_tick(self):
        b,p,n=self.fixture();p.update(range=1,next_attack=3);self.step(b,3)
        self.assertTrue(any(e['actor']==p['id'] and e['action']=='BASIC' and e['tick']==3 for e in self.events(b,'hit')))
        self.assertFalse(p['pending']);self.assertFalse(p['move_uses'])

    def test_marks_do_not_block_movement_or_retreat(self):
        b,p,n=self.fixture(start=20);self.step(b,3);p.update(root_until=0,pos=[3,0],range=1);self.step(b)
        self.assertEqual(p['pos'],[3,1]);self.assertTrue(p['trigger_delay'])
        b,p,n=self.fixture();self.step(b,2);b['retreat_requested']=True;self.step(b)
        self.assertEqual(b['result'],'RETREAT');self.assertFalse(self.events(b,'active_start_deferred'))

    def test_no_valid_start_for_three_ticks_expires_without_consuming_skill(self):
        b,p,n=self.fixture(start=20);self.step(b,3);self.assertEqual(p['trigger_delay']['expires'],5)
        self.step(b,3);self.assertIsNone(p['trigger_delay']);self.assertFalse(p['move_uses']);self.assertFalse(self.events(b,'active_start_deferred'))
        self.step(b,15);self.assertEqual(p['move_uses']['M01-A'],1);self.assertEqual(p['trigger_delay_seen'],1)
        self.assertEqual(n['move_uses']['EN11-A'],1)

    def test_last_active_tick_can_defer_but_following_tick_cannot(self):
        for start,expected in [(5,True),(6,False)]:
            b,p,n=self.fixture(start=start);self.step(b,6)
            self.assertEqual(bool(self.events(b,'active_start_deferred')),expected)

    def test_disabled_exhausted_passive_only_and_already_casting_not_chosen(self):
        for mode in ('off','exhausted','passive','casting'):
            b,p,n=self.fixture(start=1)
            if mode=='off':p['skill_mode']='off'
            elif mode=='exhausted':p['move_uses']['M01-A']=2
            elif mode=='passive':p.update(kind='S01',moves=[])
            else:p['moves'][0]['windup']=10
            self.step(b,3);self.assertFalse(n['move_uses'],mode)

    def test_already_started_during_windup_is_not_modified_at_release(self):
        # Both IDs must yield the same failed mark, despite loop order.
        for identity in ('a-player','z-player'):
            b,p,n=self.fixture(start=2);p['id']=identity;self.step(b,2);due=p['pending']['due'];self.step(b)
            self.assertEqual(due,3);self.assertEqual(p['trigger_delay_seen'],0)
            self.assertEqual(len(self.events(b,'trigger_delay_failed')),1);self.assertFalse(self.events(b,'active_start_deferred'))

    def test_release_out_of_range_wall_dead_or_off_does_not_retarget(self):
        for mode in ('range','wall','dead','off'):
            b,p,n=self.fixture(start=20)
            reserve=self.clone(b,p,'passive-reserve',[1,1]);reserve.update(kind='S01',moves=[])
            self.step(b,2);board=c.cells(self.cat,b)
            if mode=='range':p['pos']=[7,7]
            elif mode=='wall':p['pos']=[3,1];board[(3,2)]='HIGH_OBSTACLE'
            elif mode=='dead':p['hp']=0
            else:p['skill_mode']='off'
            with patch.object(c,'cells',return_value=board):self.step(b)
            self.assertEqual(p['trigger_delay_seen'],0);self.assertEqual(n['move_uses']['EN11-A'],1)
            self.assertEqual(n['move_ready']['EN11-A'],8);self.assertEqual(len(self.events(b,'trigger_delay_failed')),1)

    def test_multiple_casters_reserve_different_targets_and_never_rearm_same_target(self):
        b,p,n=self.fixture(start=20);q=self.clone(b,p,'z-player',[4,2]);other=self.clone(b,n,'z-caster',[4,3])
        self.step(b,2);self.assertEqual({n['pending']['target'],other['pending']['target']},{p['id'],q['id']})
        self.step(b,15);self.assertEqual(p['trigger_delay_seen'],1);self.assertEqual(q['trigger_delay_seen'],1)
        self.assertEqual(n['move_uses']['EN11-A'],1);self.assertEqual(other['move_uses']['EN11-A'],1)

    def test_two_cast_cap_and_cooldown_choose_second_unmarked_target(self):
        b,p,n=self.fixture(start=20);q=self.clone(b,p,'z-player',[4,2]);self.step(b,18)
        self.assertEqual(n['move_uses']['EN11-A'],2)
        self.assertEqual([e['tick'] for e in self.events(b,'trigger_delay_ready')],[3,9])
        self.assertEqual([p['trigger_delay_seen'],q['trigger_delay_seen']],[1,1])

    def test_same_tick_source_death_keeps_applied_mark_but_prior_death_cancels(self):
        for same in (False,True):
            b,p,n=self.fixture(start=20);other=self.clone(b,n,'other',[4,3]);other['moves']=[];self.step(b,2)
            if same:
                # A second attacker avoids making the marked target already casting.
                ally=self.clone(b,p,'ally',[3,1]);ally['moves']=[];self.shot(ally,n,3,attack=100000)
            else:n['hp']=0
            self.step(b);self.assertEqual(bool(p['trigger_delay']),same);self.assertEqual(n['hp'],0)

    def test_delayed_attempt_revalidates_target_and_does_not_force_a_cast(self):
        b,p,n=self.fixture();self.step(b,3);n['pos']=[7,7];self.step(b)
        self.assertFalse(p['pending']);self.assertFalse(p['move_uses'])
        n['pos']=[3,3];self.step(b);self.assertEqual(p['pending']['due'],6);self.assertEqual(p['move_uses']['M01-A'],1)

    def test_innate_soldier_active_uses_same_defer_hook(self):
        b,p,n=self.fixture(start=20);p.update(kind='S03',moves=[],skill_used=1);self.step(b,1)
        # Restore the one-shot before target selection, but keep it out of range
        # until the mark has started. No artificial active is appended.
        p['skill_used']=0;p['pos']=[3,0];n['pos']=[3,3]
        # S03 would start at range4 this tick, so use an explicit ready mark to
        # isolate its shared start hook from the independent application tests.
        p['trigger_delay']={'source':n['id'],'action_id':'mark','starts':2,'expires':4,'delay':1};p['trigger_delay_seen']=1
        self.step(b);self.assertEqual(p['skill_used'],0);self.assertFalse(p['move_uses']);self.assertIsNone(p['pending'])
        self.step(b);self.assertEqual(p['skill_used'],1);self.assertEqual(p['move_uses']['S03-A'],1)

    def test_deferred_edge_start_does_not_reserve_or_spend_scene_slot(self):
        b,p,n=self.fixture();p.update(kind='EN18',moves=deepcopy(self.cat.enemy_templates['EN18']['moves']),facing=1)
        p['moves'][0]['first_eligible_tick']=3;self.step(b,3)
        self.assertIsNone(b['edge_reservation']);self.assertFalse(p['move_uses']);self.assertIsNone(p['pending'])
        self.step(b);self.assertEqual(b['edge_reservation']['owner'],p['id']);self.assertEqual(p['move_uses']['EN18-A'],1)

    def test_no_one_tick_reactive_fog_counter_to_hush_and_no_second_delay_on_same_cast(self):
        b,p,n=self.fixture();p.update(kind='M04',moves=battle_skills.core_cards('M04'),skill_mode='counter');self.step(b,4)
        self.assertFalse(self.events(b,'cast_delayed'))
        b,p,n=self.fixture();self.step(b,4);self.assertTrue(p['pending']['delayed'])
        counter=self.clone(b,n,'fogger',[4,2]);counter.update(kind='M04',moves=battle_skills.core_cards('M04'),skill_mode='counter')
        self.step(b);self.assertFalse(counter['move_uses'])

    def test_petal_locks_adjacent_pair_physical_two_hits_no_tracking(self):
        b,p,n=self.fixture('EN10');q=self.clone(b,p,'second',[4,2]);self.step(b,2)
        self.assertEqual(n['pending']['cells'],[[3,2],[4,2]]);self.assertEqual(n['pending']['due'],4)
        p['pos']=[5,3];self.step(b,2);self.assertEqual([e['target'] for e in self.events(b,'hit')],['second'])
        self.assertEqual(n['petal_exposure'],{'starts':5,'expires':5,'modifier':-6});self.assertEqual(n['move_ready']['EN10-A'],10)

    def test_petal_physical_window_next_tick_any_direction_not_magic_or_permanent(self):
        for tick,dtype,pos,modifier in [(4,'physical',[3,2],0),(5,'physical',[3,2],-6),(5,'physical',[4,3],-6),(5,'magic',[4,3],0),(6,'physical',[3,2],0)]:
            b,p,n=self.fixture('EN10');base_defense=n['stats']['physical_defense'];self.step(b,tick-1);p['pos']=pos;self.shot(p,n,tick,dtype);self.step(b)
            hit=next(e for e in self.events(b,'hit') if e['actor']==p['id']);self.assertEqual(hit['petal_defense_modifier'],modifier)
            self.assertEqual(hit['raw'],int(10000/(100+max(0,n['stats'][dtype+'_defense']+modifier))))
            self.assertEqual(n['stats']['physical_defense'],base_defense)

    def test_petal_miss_still_exposes_and_two_cast_limit(self):
        b,p,n=self.fixture('EN10');self.step(b,2);p['pos']=[5,3];self.step(b,2)
        self.assertTrue(n['petal_exposure']);self.assertFalse(self.events(b,'hit'));p['pos']=[3,2];self.step(b,25)
        self.assertEqual(n['move_uses']['EN10-A'],2);self.assertEqual([e['tick'] for e in self.events(b,'petal_exposure')],[4,12])

    def test_petal_no_legal_pair_waits_and_does_not_create_terrain(self):
        b,p,n=self.fixture('EN10');board={(3,3):'GROUND',(3,2):'GROUND'};before=deepcopy(board)
        with patch.object(c,'cells',return_value=board):self.step(b,5)
        self.assertFalse(n['move_uses']);self.assertEqual(board,before)

    def test_root_two_sequential_lanes_use_fixed_base_and_do_not_reaim(self):
        b,p,n=self.fixture('EL02');self.step(b,2);first=deepcopy(n['pending']);self.step(b)
        self.assertEqual(first['cells'],[[3,2],[3,1]]);self.assertEqual(n['root_axis_base'],4);self.assertEqual(n['root_until'],4)
        p['pos']=[4,3];self.step(b,5);second=n['pending'];self.assertEqual(second['cells'],[[4,2],[5,1]])
        self.assertEqual(second['axis_offset'],1);self.assertEqual(second['axis_base'],4);self.step(b,20)
        self.assertEqual(n['move_uses']['EL02-A'],2);self.assertEqual([e['tick'] for e in self.events(b,'release')],[3,9])

    def test_root_hits_only_one_and_only_roots_self(self):
        b,p,n=self.fixture('EL02');q=self.clone(b,p,'second',[3,1]);p['root_until']=0;q['root_until']=0;self.step(b,3)
        self.assertEqual([e['target'] for e in self.events(b,'hit')],[p['id']]);self.assertEqual(n['root_until'],4)
        self.assertEqual(p['root_until'],0);self.assertEqual(q['root_until'],0)

    def test_root_exposes_side_physical_only_for_two_release_ticks(self):
        for tick,dtype,pos,weak in [(3,'physical',[4,3],True),(4,'physical',[4,3],True),(5,'physical',[4,3],False),(4,'physical',[3,2],False)]:
            b,p,n=self.fixture('EL02');self.step(b,tick-1);p['pos']=pos;self.shot(p,n,tick,dtype);self.step(b)
            hit=next(e for e in self.events(b,'hit') if e['actor']==p['id']);self.assertEqual(hit['weak_point'],weak)
            self.assertEqual(hit['raw'],int(10000/(100+max(0,n['stats'][dtype+'_defense']-(4 if weak else 0)))))

    def test_invalid_second_root_lane_waits_without_turning_back(self):
        b,p,n=self.fixture('EL02');self.step(b,3);board=c.cells(self.cat,b);board[(5,1)]='HIGH_OBSTACLE'
        with patch.object(c,'cells',return_value=board):self.step(b,20)
        self.assertEqual(n['move_uses']['EL02-A'],1);self.assertEqual(n['root_axis_base'],4)

    def test_root_base_is_not_committed_when_start_is_deferred(self):
        b,p,n=self.fixture('EL02');n['trigger_delay']={'source':'fixture','action_id':'mark','starts':2,'expires':4,'delay':1};n['trigger_delay_seen']=1
        self.step(b,2);self.assertIsNone(n['root_axis_base']);self.assertFalse(n['move_uses']);self.step(b)
        self.assertEqual(n['root_axis_base'],4);self.assertEqual(n['pending']['axis_offset'],0)

    def test_state_serialization_mark_deferred_start_exposure_and_between_lanes(self):
        for kind,start,tick in [('EN11',20,3),('EN11',3,3),('EN11',3,4),('EN10',3,4),('EN10',3,5),('EL02',3,4),('EL02',3,8)]:
            b,p,n=self.fixture(kind,start);self.step(b,tick);restored=json.loads(json.dumps(b));self.step(b,25);self.step(restored,25);self.assertEqual(restored,b)

    def test_lab_status_for_each_public_window(self):
        for eid,expected in [('INTRO-EN11','主动起手延后'),('INTRO-EN10','落蕊物防窗口'),('EL02-SIDE','双囊轴线')]:
            lab=Lab(encounter=eid,catalog=self.cat);lab.execute('fight')
            for _ in range(10):
                lab.execute('step')
                if expected in t.describe(lab.battle):break
            out=io.StringIO()
            with redirect_stdout(out):lab.status()
            self.assertIn(expected,out.getvalue())


if __name__=='__main__':unittest.main()
