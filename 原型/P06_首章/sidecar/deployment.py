"""Apply a mouse deployment as one P03 save transaction."""

from engine import Game, require
import region_space
from expedition_peril import deployable


class DeploymentGame(Game):
    def dispatch(self, command, args):
        if command != 'deploy_at':
            return super().dispatch(command, args)
        state = self.s
        require(len(args) in (4, 5), '部署需要队员、格位和朝向，可指定交换队员。')
        require(state['phase'] in ('TOWN', 'EXPLORE'), '当前不能调整部署。')
        board_id = 'OPEN'
        if state['phase'] == 'EXPLORE':
            contact = region_space.current(self).get('contact') if region_space.active(self) else None
            require(contact and contact['site'] == state['site'] and state['site'] not in self.current['cleared'],
                    '需要在接敌部署时调整阵位。')
            board_id = self.manifest_region['encounters'][state['site']]['board_id']
        member = next((row for row in state['party'] if row['instance_id'] == args[0]), None)
        require(self._available(member), '这名队员当前无法上阵。')
        position = [int(args[1]), int(args[2])]
        occupants = [row for row in state['party'] if row is not member and row['deployed'] and row['position'] == position]
        if len(args) == 4:
            require(not occupants, '该格已有队员。')
        else:
            require(len(occupants) == 1 and occupants[0]['instance_id'] == args[4], '交换对象已变化，请重新布阵。')
            require(member['deployed'] and self._available(occupants[0]), '只有可上阵的已部署队员才能交换。')
        board = self.cat.boards[board_id]
        require(self._walkable(board, position), '这里无法部署。')
        if occupants:
            origin = member['position']
            require(origin != position and self._walkable(board, origin)
                    and not any(row is not member and row['deployed'] and row['position'] == origin
                                for row in state['party']), '原阵位无法交换。')
            other = occupants[0]
            super().dispatch('place', [other['instance_id'], *map(str, origin), str(other['facing'])])
        super().dispatch('place', args[:4])
        if not member['deployed']:
            super().dispatch('deploy', [args[0], 'on'])
        outcome = '已交换至' if occupants else '已部署至'
        return f'{outcome} {position[0]},{position[1]}。'

    @staticmethod
    def _available(member):
        return (member is not None and deployable(member) and member['hp'] > 0
                and member['injury_days'] == 0 and member['erosion'] < 100)

    def _walkable(self, board, position):
        if position not in board['player_deploy_cells']:
            return False
        terrain = next((row['terrain_id'] for row in board['cells'] if [row['q'], row['r']] == position), None)
        return terrain is not None and self.cat.terrain[terrain]['walkable']
