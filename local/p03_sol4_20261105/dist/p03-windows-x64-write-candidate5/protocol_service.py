"""Internal bounded JSONL prototype. Start only with a validated case ID.

Performance collection is deliberately absent. UNKNOWN stops all new commands.
"""
from pathlib import Path
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
import shlex
import sys
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parent))
import transaction_store as store
from stage_runtime import verify_inputs

ROOT = Path(__file__).resolve().parent
MAX_FRAME = 65536
COMMANDS = {'quest', 'recruit', 'book', 'craft', 'rescue', 'finale', 'status', 'help',
            'depart', 'move', 'visit', 'choose', 'return', 'step', 'run', 'formation',
            'level_up', 'stance', 'place', 'fight', 'challenge', 'tutorial', 'town'}
TUTORIAL_ACTIONS = {('recommend', 'CONFIRM'), ('start',), ('materials',), ('observe',)}


def read_frame(stream):
    raw = stream.readline(MAX_FRAME + 1)
    if not raw:
        return None
    if len(raw) > MAX_FRAME or not raw.endswith(b'\n'):
        raise ValueError('FRAME_LIMIT')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('DUPLICATE_KEY')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('NONFINITE')))


def validate_request(request):
    if not isinstance(request, dict) or type(request.get('protocol_version')) is not int or request['protocol_version'] != 1:
        raise ValueError('PROTOCOL_VERSION')
    op = request.get('op')
    if not isinstance(op, str) or op not in ('snapshot', 'query', 'execute'):
        raise ValueError('UNKNOWN_OPERATION')
    fields = {
        'snapshot': {'protocol_version', 'op'},
        'query': {'protocol_version', 'op', 'request_id'},
        'execute': {'protocol_version', 'op', 'request_id', 'expected_version', 'command', 'args'},
    }
    allowed_fields = fields[op] | ({'expected_epoch'} if op == 'execute' else set())
    if not fields[op].issubset(request) or not set(request).issubset(allowed_fields):
        raise ValueError('REQUEST_FIELDS')
    if op in ('query', 'execute') and (not isinstance(request.get('request_id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', request['request_id'])):
        raise ValueError('REQUEST_ID')
    if op == 'execute':
        if 'expected_epoch' in request and (not isinstance(request['expected_epoch'], str) or not re.fullmatch(r'[0-9a-f]{32}', request['expected_epoch'])):
            raise ValueError('SESSION_EPOCH')
        if not isinstance(request['command'], str) or request['command'] not in COMMANDS:
            raise ValueError('COMMAND_NOT_ALLOWED')
        if not isinstance(request['args'], list) or any(not isinstance(v, str) or len(v) > 256 for v in request['args']) or len(request['args']) > 20:
            raise ValueError('ARGS')
        if request['command'] == 'tutorial' and tuple(request['args']) not in TUTORIAL_ACTIONS:
            raise ValueError('COMMAND_NOT_ALLOWED')
        if request['command'] == 'town' and request['args']:
            raise ValueError('ARGS')
        if type(request['expected_version']) is not int or request['expected_version'] < 0:
            raise ValueError('STATE_VERSION')
    return request


def snapshot(game, root, known_digest=None):
    if known_digest is None and len(game.s['completed_history']) >= 24:
        from archive_cache import digest
        with ThreadPoolExecutor(max_workers=1) as worker:
            pending = worker.submit(digest, game.s, sort_keys=True)
            files = snapshot_files(root)
            known_digest = pending.result()
    else:
        files = snapshot_files(root)
        if known_digest is None:
            from archive_cache import digest
            known_digest = digest(game.s, sort_keys=True)
    return dict(state_digest=known_digest, files=files,
                game_id=game.s['id'], domain_sequence=game.s['sequence'])


def snapshot_files(root):
    # Own the whole experimental session lock before calling. File names are
    # fixed; no client-supplied file path or state payload reaches the runtime.
    files = {}
    for suffix in ('', '.bak', '.finale_retry.json'):
        path = Path(root) / ('save.json' + suffix)
        if path.exists():
            with path.open('rb') as stream:
                files[path.name] = hashlib.file_digest(stream, 'sha256').hexdigest()
        else:
            files[path.name] = None
    return files


def query_result(root, request_id):
    row = store.lookup(root, request_id)
    if row is None:
        return dict(status='NOT_FOUND', request_id=request_id)
    if row['status'] == 'PREPARED':
        return dict(status='UNKNOWN', request_id=request_id, error='RECOVERY_REQUIRED',
                    next_action='QUERY_AND_STOP')
    return row['response']


def execute_request(game, root, request, known_digest=None):
    validate_request(request)
    ledger = store.recover(root)
    payload = {k: request[k] for k in ('protocol_version', 'command', 'args')}
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    prior = ledger['entries'].get(request['request_id'])
    if prior:
        if prior['payload_hash'] != digest:
            raise ValueError('ID_PAYLOAD_CONFLICT')
        return query_result(root, request['request_id'])
    if any(row['status'] == 'PREPARED' for row in ledger['entries'].values()):
        raise ValueError('RECOVERY_REQUIRED: unresolved command')
    before = snapshot(game, root, known_digest)
    if ledger.get('head') is not None and ledger['head'] != before:
        raise ValueError('RECOVERY_REQUIRED: file set mismatch')
    if request['expected_version'] != ledger['version']:
        raise ValueError('STALE_VERSION')
    ledger = store.prepare(root, request, digest, before)
    try:
        result = game.execute(shlex.join([request['command']] + request['args']))
    except Exception as exc:
        print('Domain failure: ' + str(exc), file=sys.stderr, flush=True)
        # A validation exception can finalize as rejected only when the domain
        # state and its whole file set still match the pre-command snapshot.
        if type(exc) is ValueError and not any(root.glob('*.tmp')) and snapshot(game, root) == before:
            response = dict(status='REJECTED', request_id=request['request_id'],
                            error='DOMAIN_REJECTED', next_action='REFRESH_SNAPSHOT',
                            state_version=ledger['version'], **before)
            ledger['head'] = before
            ledger['entries'][request['request_id']].update(status='REJECTED', response=response)
            store.commit(root, ledger)
            return response
        raise ValueError('UNKNOWN: command failed after prepare; RECOVERY_REQUIRED')
    after = snapshot(game, root)
    ledger['version'] += 1
    response = dict(status='COMMITTED', request_id=request['request_id'],
                    before_version=request['expected_version'], state_version=ledger['version'],
                    result=result, **after)
    # Emitted only after store.commit succeeds below; this acknowledges the
    # recorded file set, not power-loss durability or a separate UI save action.
    response['persistence_ack'] = dict(
        request_id=request['request_id'], state_version=ledger['version'],
        state_digest=after['state_digest'], files=after['files'],
        basis='COMMITTED_RESULT_LEDGER', power_loss_verified=False)
    ledger['head'] = after
    ledger['entries'][request['request_id']].update(status='COMMITTED', response=response)
    store.commit(root, ledger)
    return response


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--runs-dir', type=Path, default=ROOT / 'runs',
                        help='Trusted launcher data directory, outside the package if supplied.')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', args.case_id):
        raise ValueError('CASE_ID')
    manifest = json.loads((ROOT / 'input_manifest.json').read_text(encoding='utf-8'))
    verify_inputs(manifest, ROOT / 'vendor')
    sys.path.insert(0, str(ROOT / 'vendor/原型/火种计划_远征灰盒'))
    from engine import Game
    import save_storage
    runs = args.runs_dir.resolve()
    case = runs / args.case_id
    if case.resolve() != case:
        raise ValueError('CASE_PATH')
    root = store.open_session(case)
    with save_storage.save_lock(root / 'session'):
        ledger = store.recover(root)
        save = root / 'save.json'
        if not save.exists() and (ledger['entries'] or (root / 'save.json.bak').exists()):
            raise ValueError('RECOVERY_REQUIRED: missing primary')
        game = Game.load(save) if save.exists() else Game.new_campaign(seed=11, save_path=save)
        connection_epoch = uuid.uuid4().hex
        loaded = snapshot(game, root)
        read_digest = loaded['state_digest']
        print(json.dumps(dict(status='READY', connection_epoch=connection_epoch, state_version=ledger['version'], **loaded)), flush=True)
        while True:
            try:
                request = read_frame(sys.stdin.buffer)
                if request is None:
                    return
                validate_request(request)
                if request['op'] == 'snapshot':
                    result = dict(status='SNAPSHOT', state_version=store.recover(root)['version'], **snapshot(game, root, read_digest))
                    read_digest = result['state_digest']
                    import narrative
                    public = narrative.public(game)
                    active = public['active']
                    result['presentation'] = dict(
                        narrative_enabled=public['enabled'], hint=public['hint'],
                        history=public['history'],
                        active=None if active is None else dict(
                            id=active['id'], title=active['title'], status=active['status'],
                            cursor=active['cursor'], line_count=len(active['lines']),
                            line={key: active['lines'][active['cursor']][key]
                                  for key in ('speaker', 'text')}))
                    import region_space
                    map_public = region_space.public(game)
                    map_fields = ('version', 'position', 'facing', 'steps', 'cells',
                                  'objects', 'contact', 'deploy_cells', 'battle_cells', 'summary')
                    result['presentation']['map'] = (None if map_public is None else
                        {key: map_public[key] for key in map_fields})
                    # Current-state warnings only: no hooks, simulated resolution or
                    # historical events. Locked cells are not universal impact areas.
                    battle = game.s.get('battle')
                    danger = None
                    if battle is not None and battle.get('result') is None:
                        actions = []
                        for actor in battle['actors']:
                            pending = actor.get('pending')
                            if actor['hp'] <= 0 or not pending:
                                continue
                            actions.append(dict(
                                actor_id=actor['id'], side=actor['side'],
                                action_id=pending['id'],
                                **{key: pending.get(key) for key in
                                   ('move_id', 'kind', 'target', 'origin', 'facing', 'due')},
                                locked_cells=pending.get('cells', []),
                                geometry_complete=False))
                        import boss_threats
                        laws = []
                        for row in boss_threats.public(battle)['bosses']:
                            law = row['law']
                            if law and law['status'] == 'ACTIVE':
                                laws.append({key: law[key] for key in
                                    ('id', 'boss', 'target', 'started', 'due',
                                     'progress', 'threshold', 'status')})
                        danger = dict(battle_id=battle['battle_id'], tick=battle['tick'],
                                      actions=actions, laws=laws,
                                      coverage='PERSISTED_PENDING_AND_ACTIVE_LAWS',
                                      exhaustive=False)
                    result['presentation']['danger'] = danger
                elif request['op'] == 'query':
                    result = query_result(root, request['request_id'])
                else:
                    if 'expected_epoch' in request and request['expected_epoch'] != connection_epoch:
                        raise ValueError('STALE_EPOCH')
                    prior_digest, read_digest = read_digest, None
                    result = execute_request(game, root, request, prior_digest)
            except Exception as exc:
                # Closed wire errors; diagnostics stay on the engineering stream.
                detail = str(exc)
                invalid = {'PROTOCOL_VERSION', 'UNKNOWN_OPERATION', 'REQUEST_FIELDS',
                           'REQUEST_ID', 'COMMAND_NOT_ALLOWED', 'ARGS', 'STATE_VERSION',
                           'FRAME_LIMIT', 'DUPLICATE_KEY', 'NONFINITE', 'SESSION_EPOCH'}
                if detail in invalid:
                    code, action = detail, 'CORRECT_REQUEST'
                elif detail in ('STALE_VERSION', 'STALE_EPOCH'):
                    code, action = detail, 'REFRESH_SNAPSHOT'
                elif detail == 'ID_PAYLOAD_CONFLICT':
                    code, action = detail, 'QUERY_ORIGINAL_REQUEST'
                elif detail.startswith(('RECOVERY_REQUIRED', 'UNKNOWN:')):
                    code, action = 'RECOVERY_REQUIRED', 'QUERY_AND_STOP'
                elif isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError)):
                    code, action = 'INVALID_JSON', 'CORRECT_REQUEST'
                else:
                    code, action = 'INTERNAL_ERROR', 'QUERY_AND_STOP'
                print('Protocol rejection: ' + repr(exc), file=sys.stderr, flush=True)
                result = dict(status='REJECTED', error=code, next_action=action)
                if str(exc) == 'FRAME_LIMIT':
                    print(json.dumps(dict(result, connection_epoch=connection_epoch)), flush=True)
                    return
            print(json.dumps(dict(result, connection_epoch=connection_epoch), ensure_ascii=False, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
