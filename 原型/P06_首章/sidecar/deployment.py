"""Adapt P06 commands to one P03 save transaction."""

from engine import Game, VERSION, require
import region_space
from expedition_peril import deployable
from slice_view import (FINALE_AGLA_ACTIONS, FINALE_IDENTITY_ACTIONS, LOCAL_PROTECTION_ACTIONS,
                        REGIONAL_SIMPLE_OPTIONS, REGIONAL_SCOUT_EVENTS, finale_retry_town,
                        regional_field_event, scouting_blocker, valid_command)


class IncompatibleSaveVersion(ValueError):
    pass


class DeploymentGame(Game):
    @classmethod
    def from_state(cls, state, catalog=None, path=None):
        version = state.get('version') if isinstance(state, dict) else None
        if isinstance(version, str) and version.startswith('TINDER-GREYBOX-') and version != VERSION:
            raise IncompatibleSaveVersion('Save format does not match the packaged runtime.')
        return super().from_state(state, catalog, path)

    def choose(self, option_id, target='01', plan=None):
        state = self.s
        regional = regional_field_event(self)
        if target in REGIONAL_SIMPLE_OPTIONS:
            args = [option_id, target] + ([plan] if plan is not None else [])
            require(target == regional and valid_command('choose', args),
                    '这项选择只在本趟对应的现场开放。')
            binding = self.manifest_region['events'][state['site']]
            require(option_id in binding['enabled_options'],
                    '本趟远征清单未开放该选项。')
            target, plan = plan or '01', None
        if state['phase'] == 'EXPLORE' and state['mission'] == 'ORDINARY':
            site = state['site']
            event_id = self.manifest_region['events'].get(site, {}).get('event_id')
            if regional or (event_id == 'EV59' and option_id == 'RUSH'):
                # The text client reports success even after a local visit closes.
                require(self.current['events'][site]['state'] not in ('RESOLVED', 'DECLINED'),
                        '本现场已处理，不能再次选择。')
            if regional in REGIONAL_SCOUT_EVENTS.values() and option_id == 'PRIMARY':
                blocker = scouting_blocker(self)
                require(not blocker, blocker)
        return super().choose(option_id, target, plan)

    def dispatch(self, command, args):
        if command == 'event' and tuple(args) in LOCAL_PROTECTION_ACTIONS:
            case = self.s.get('cases', {}).get(args[0])
            # The frozen client describes an old receipt as a successful command.
            require(not case or case['state'] != 'PROTECTED', '原案件已完成，沿用原回执。')
        if command == 'thread':
            action = args[0]
            thread = self.s['hidden_thread']
            require(action not in thread['steps'], '这一封回信已完成，请在回信记录回看。')
            if action == 'commission':
                require(thread['commission'] is None, '后续接应已经登记，不能重新登记。')
            if action == 'deliver':
                signed = any(row['expedition'] == self.s['expedition_no'] and row['delivery']
                             for row in thread['attempts'])
                require(not signed, '本趟凭据已签收，请安全归城。')
        if command == 'finale':
            phase = self.s['phase']
            final = self.s['finale']
            action = tuple(args)
            if action == ('retry', 'CONFIRM'):
                finale_retry_town(self)
            if phase == 'FINAL_REGROUP' and action == ('fight', 'CONFIRM'):
                result = super().dispatch(command, args)
                # The frozen admin setup copies reserve actors from before fatigue.
                fatigue = final['run'].get('reserve_fatigue', {})
                for actor in self.s['battle']['actors']:
                    if actor['side'] == 'player' and actor['id'] in fatigue:
                        actor['hp'] = fatigue[actor['id']]['after']
                return result
            if len(action) == 2 and action[0] == 'executor':
                require(phase == 'TOWN' and not final['run'] and not final['ending'],
                        '执行者只能在城镇终战整备时指定。')
                member = next((row for row in self.s['party'] if row['instance_id'] == action[1]), None)
                require(self._available(member) and member['deployed'] and not member['unit_id'].startswith('PET'),
                        '执行者须为当前可行动的上场人类。')
                require(final.get('executor') != action[1], '该执行者已指定。')
            elif action in FINALE_AGLA_ACTIONS or (action == ('cancel',) and phase == 'TOWN'):
                require(phase == 'TOWN' and not final['run'], 'Agla 的携带或封存只能在城镇整备时变更。')
                if action == ('cancel',):
                    require(final['seal_pending'], '当前没有待确认的封存。')
                elif action == ('seal',):
                    require(not final['sealed'] and not final['seal_pending'], 'Agla 已封存或正在等待确认。')
            elif action in FINALE_IDENTITY_ACTIONS:
                # Prevent another success receipt for a finished or unchanged proposal.
                require(phase == 'FINAL_CHOICE', '当前不在终战身份选择。')
                pending = final['run']['merger_pending']
                if action == ('choice', 'ACCEPT_MERGER'):
                    require(not pending, '归并提议已在等待确认。')
                elif action == ('cancel',):
                    require(pending, '当前没有待确认的归并提议。')
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
