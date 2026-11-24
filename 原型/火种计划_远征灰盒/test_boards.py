from copy import deepcopy
import unittest
from board_geometry import DIRS, DEFAULT_FORMATION
from data import Catalog
from engine import Game
import combat


def connected(points):
    seen=set();todo=[next(iter(points))] if points else []
    while todo:
        q,r=todo.pop()
        if (q,r) in seen:continue
        seen.add((q,r))
        todo.extend((q+dq,r+dr) for dq,dr in DIRS if (q+dq,r+dr) in points and (q+dq,r+dr) not in seen)
    return len(seen)==len(points)


class BoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cat=Catalog()

    def test_actual_masks_have_multiple_shapes_and_no_missing_cells(self):
        self.assertEqual({b['shape'] for b in self.cat.boards.values()},
                         {'RECTANGLE','LONG_RECTANGLE','REGULAR_HEXAGON','WIDE_RECTANGLE','NEAR_SQUARE'})
        expected={'OPEN':64,'DOUBLE_BRIDGE':60,'DRY_ISLAND':61,'DUAL_FLANK':61,
                  'SALT_CROSSING':72,'MIRROR_COURT':72,'FORGE_CROSSING':72,'CITADEL_RING':72}
        for bid,b in self.cat.boards.items():
            points={(c['q'],c['r']) for c in b['cells']}
            self.assertEqual(len(points),expected[bid]+18);self.assertEqual(len(b['cells']),len(points))
            self.assertGreaterEqual(len(b['player_deploy_cells']),20)
            base_points={p for p in points if p[1]>=0}
            self.assertTrue(connected(points))
            if b['shape']=='REGULAR_HEXAGON':
                relative={(q-3,r-4) for q,r in base_points}
                self.assertEqual(relative,{(-r,q+r) for q,r in relative})  # 60-degree rotational symmetry.
                self.assertTrue(all(sum((q+dq,r+dr) in base_points for dq,dr in DIRS)>=3 for q,r in base_points))
            else:
                self.assertEqual({sum(r==row for q,r in points) for row in range(b['rows'])},{b['columns']})

    def test_all_terrain_connected_without_single_cell_articulation(self):
        for bid,b in self.cat.boards.items():
            with self.subTest(board=bid):
                walk={(c['q'],c['r']) for c in b['cells'] if self.cat.terrain[c['terrain_id']]['walkable']}
                self.assertTrue(connected(walk))
                for cell in walk:self.assertTrue(connected(walk-{cell}),f'{bid} single cell cut {cell}')

    def test_every_encounter_can_deploy_on_every_board(self):
        for bid,b in self.cat.boards.items():
            allowed={tuple(p) for p in b['enemy_deploy_cells']}
            self.assertTrue(set(DEFAULT_FORMATION)<=set(map(tuple,b['player_deploy_cells'])))
            for eid,source in self.cat.encounters.items():
                adapted=self.cat.encounter_for_board(eid,bid)
                positions=[tuple(u['position']) for u in adapted['units']]
                self.assertEqual(len(positions),len(set(positions)),(eid,bid))
                self.assertTrue(set(positions)<=allowed,(eid,bid,positions))
                for a,original in zip(adapted['units'],source['units']):
                    from balance_v062 import enemy_for
                    from late_pressure import fixed_encounter
                    rebased=fixed_encounter(enemy_for(self.cat,source))
                    self.assertEqual(a['stats'],next(u['stats'] for u in rebased['units'] if u['instance_id']==original['instance_id']))
                    for adapted_move,original_move in zip(a['moves'],original['moves']):
                        self.assertEqual({k:v for k,v in adapted_move.items() if k not in ('position_candidates','locked_anchor_cells')},
                                         {k:v for k,v in original_move.items() if k not in ('position_candidates','locked_anchor_cells')})
                        if 'position_candidates' in adapted_move:
                            self.assertTrue(set(map(tuple,adapted_move['position_candidates']))<=allowed,(eid,bid))

    def test_void_cells_are_rejected_and_deployment_uses_selected_board(self):
        g=Game.new(catalog=self.cat);g.s['party'][0]['position']=[0,0]
        with self.assertRaises(ValueError):g.validate_deployment('DUAL_FLANK')
        g.s['party'][0]['position']=[1,0]
        g.validate_deployment('OPEN')
        with self.assertRaises(ValueError):g.validate_deployment('DUAL_FLANK')
        party=deepcopy(g.s['party']);party[0]['position']=[100,100]
        with self.assertRaises(ValueError):combat.create(self.cat,self.cat.encounter_for_board('RG01-N01','OPEN'),'OPEN',party,11,[],{})

    def test_real_battles_on_all_shapes_respect_mask_and_finish(self):
        for bid in self.cat.boards:
            for stance in ('advance','evade'):
                g=Game.new(catalog=self.cat)
                for m in g.s['party']:m['stance']=stance
                b=combat.create(self.cat,self.cat.encounter_for_board('RG01-N01',bid),bid,g.s['party'],11,[],{})
                walk={p for p,t in combat.cells(self.cat,b).items() if self.cat.terrain[t]['walkable']}
                for _ in range(600):
                    combat.step(self.cat,b)
                    positions=[tuple(a['pos']) for a in b['actors'] if a['hp']>0]
                    self.assertEqual(len(positions),len(set(positions)))
                    self.assertTrue(set(positions)<=walk)
                    if b['result']:break
                self.assertIsNotNone(b['result'],(bid,stance))


if __name__=='__main__':unittest.main(verbosity=2)
