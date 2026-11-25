"""Bind the accepted P03 bundle and install the P06 presentation extension."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import shutil


BASE_SHA = 'cf1d1e0d273a0c0bdeb4a0bcaa8eb58e65e42d4970551bf8ba2404f1a29f069b'
PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT.parents[1] / 'local/p03_sol4_20261105/dist/p03-windows-x64-write-candidate5'

PENDING_QUERY_GUARD = """def request_payload_hash(request):
    payload = {key: request[key] for key in ('protocol_version', 'command', 'args')}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def check_pending_query(path, ledger, request_id, row):
    if path.with_suffix('.json.tmp').exists():
        raise ValueError('pending journal has an interrupted write')
    with path.open('rb') as stream:
        raw = stream.read(MAX_FRAME + 1)
    if len(raw) > MAX_FRAME:
        raise ValueError('pending journal exceeds the frame limit')
    request = validate_request(decode_json(raw))
    if request['op'] != 'execute' or request['request_id'] != request_id:
        raise ValueError('pending journal does not identify the requested operation')
    if row is None:
        if request['expected_version'] != ledger['version']:
            raise ValueError('unrecorded request does not match the current version')
    elif row.get('request') != request or row.get('payload_hash') != request_payload_hash(request):
        raise ValueError('pending journal does not match the ledger entry')


def query_result(root, request_id, pending_path=None):
    ledger = store.recover(root)
    row = ledger['entries'].get(request_id)
    if pending_path is not None:
        try:
            check_pending_query(pending_path, ledger, request_id, row)
        except (OSError, ValueError, RecursionError) as exc:
            print(f'Pending journal verification: {exc}', file=sys.stderr, flush=True)
            return dict(status='UNKNOWN', request_id=request_id, error='PENDING_JOURNAL_UNVERIFIED',
                        next_action='QUERY_AND_STOP')
"""


def digest(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def replace(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f'Unexpected P03 source near {before!r}')
    return text.replace(before, after)


def stage(source, output, release_id=None):
    manifest = source / 'bundle.json'
    if digest(manifest) != BASE_SHA:
        raise ValueError('The P06 runtime requires the accepted P03 candidate')
    files = json.loads(manifest.read_bytes())['files']
    for name, row in files.items():
        file = source / name
        if file.stat().st_size != row['bytes'] or digest(file) != row['sha256']:
            raise ValueError(f'P03 bundle member drift: {name}')
    output.mkdir(parents=True, exist_ok=False)
    for name in files:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    shutil.copyfile(manifest, output / 'p03-bundle.json')
    shutil.copyfile(Path(__file__).with_name('slice_view.py'), output / 'slice_view.py')
    shutil.copyfile(Path(__file__).with_name('deployment.py'), output / 'deployment.py')
    shutil.copyfile(Path(__file__).with_name('launch_runtime.py'), output / 'launch_runtime.py')
    shutil.copyfile(Path(__file__).with_name('recover_save.py'), output / 'recover_save.py')
    service = output / 'protocol_service.py'
    text = service.read_text(encoding='utf-8')
    text = replace(text, 'def main():',
                   'def main():\n'
                   '    from contextlib import ExitStack')
    text = replace(text, "    with save_storage.save_lock(root / 'session'):\n",
                   "    with ExitStack() as session:\n"
                   "        try:\n"
                   "            session.enter_context(save_storage.save_lock(root / 'session'))\n"
                   "        except ValueError as exc:\n"
                   "            if not isinstance(exc.__cause__, OSError):\n"
                   "                raise\n"
                   "            print(f'Session busy: {exc}', file=sys.stderr, flush=True)\n"
                   "            print(json.dumps({'status': 'SESSION_BUSY'}), flush=True)\n"
                   "            return\n")
    text = replace(text, "        if not save.exists() and (ledger['entries'] or (root / 'save.json.bak').exists()):\n"
                   "            raise ValueError('RECOVERY_REQUIRED: missing primary')\n",
                   "        if not save.exists():\n"
                   "            if ledger['entries'] or (root / 'save.json.bak').exists():\n"
                   "                raise ValueError('RECOVERY_REQUIRED: missing primary')\n"
                   "            pending = runs.parent / f'{args.case_id}.pending.json'\n"
                   "            if pending.exists() or pending.with_suffix('.json.tmp').exists():\n"
                   "                raise ValueError('RECOVERY_REQUIRED: request journal without primary')\n")
    text = replace(text, '    from engine import Game', '    from deployment import DeploymentGame as Game')
    start = text.index('COMMANDS = ')
    finish = text.index('\n\n\ndef read_frame', start)
    text = text[:start] + 'from slice_view import COMMANDS, valid_command, make_presentation, ready_contact_model_kinds' + text[finish:]
    text = replace(text, "if request['command'] == 'tutorial' and tuple(request['args']) not in TUTORIAL_ACTIONS:",
                   "if not valid_command(request['command'], request['args']):")
    text = replace(text, "                    result = dict(status='SNAPSHOT', state_version=store.recover(root)['version'], **snapshot(game, root, read_digest))",
                   "                    ledger = store.recover(root)\n"
                   "                    if any(row['status'] == 'PREPARED' for row in ledger['entries'].values()):\n"
                   "                        raise ValueError('RECOVERY_REQUIRED: unresolved command')\n"
                   "                    verified = snapshot(game, root, read_digest)\n"
                   "                    if ledger.get('head') is not None and ledger['head'] != verified:\n"
                   "                        raise ValueError('RECOVERY_REQUIRED: file set mismatch')\n"
                   "                    result = dict(status='SNAPSHOT', state_version=ledger['version'], **verified)")
    start = text.index("                    import narrative", text.index("                if request['op'] == 'snapshot':"))
    finish = text.index("                elif request['op'] == 'query':", start)
    assert "result['presentation']['danger'] = danger" in text[start:finish]
    text = text[:start] + (
        "                    result['presentation'] = make_presentation(game, ledger, result['files']['save.json'])\n"
    ) + text[finish:]
    text = replace(text, "({'expected_epoch'} if op == 'execute' else set())",
                   "({'expected_epoch', 'inline_presentation', 'battle_board'} if op == 'execute' else set())")
    text = replace(text, '    if not fields[op].issubset(request)',
                   "    if op == 'query':\n"
                   "        allowed_fields.add('match_pending')\n"
                   "        if 'match_pending' in request and request['match_pending'] is not True:\n"
                   "            raise ValueError('REQUEST_FIELDS')\n"
                   '    if not fields[op].issubset(request)')
    text = replace(text, '    def pairs(items):\n',
                   '    return decode_json(raw)\n\n\ndef decode_json(raw):\n    def pairs(items):\n')
    text = replace(text, 'def query_result(root, request_id):\n    row = store.lookup(root, request_id)\n',
                   PENDING_QUERY_GUARD)
    text = replace(text, "    payload = {k: request[k] for k in ('protocol_version', 'command', 'args')}\n"
                   "    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()\n",
                   '    digest = request_payload_hash(request)\n')
    text = replace(text, "                    result = query_result(root, request['request_id'])\n",
                   "                    pending_path = runs.parent / f'{args.case_id}.pending.json' if request.get('match_pending') else None\n"
                   "                    result = query_result(root, request['request_id'], pending_path)\n")
    text = replace(text, "    if op == 'execute':\n",
                   "    if op == 'execute':\n"
                   "        if 'inline_presentation' in request and type(request['inline_presentation']) is not bool:\n"
                   "            raise ValueError('REQUEST_FIELDS')\n"
                   "        if 'battle_board' in request and (not request.get('inline_presentation')\n"
                   "                or not isinstance(request['battle_board'], str)\n"
                   "                or not re.fullmatch(r'[A-Za-z0-9:_-]{1,80}', request['battle_board'])):\n"
                   "            raise ValueError('REQUEST_FIELDS')\n")
    text = replace(text, "print(json.dumps(dict(status='READY', connection_epoch=connection_epoch, state_version=ledger['version'], **loaded))",
                   "try:\n"
                   "            hints = ready_contact_model_kinds(game, ledger, loaded)\n"
                   "        except Exception as exc:\n"
                   "            print(f'Contact model hint unavailable: {exc}', file=sys.stderr)\n"
                   "            hints = []\n"
                   "        print(json.dumps(dict(status='READY', connection_epoch=connection_epoch, state_version=ledger['version'], "
                   "inline_presentation=True, battle_board_refs=True, contact_model_kinds=hints, **loaded))")
    text = replace(text, '    store.commit(root, ledger)\n    return response\n',
                   "    store.commit(root, ledger)\n"
                   "    if request.get('inline_presentation'):\n"
                   "        # Keep the committed receipt even if the optional view fails.\n"
                   "        try:\n"
                   "            primary = after['files']['save.json']\n"
                   "            saved_at = ledger['version'] if primary != before['files']['save.json'] else None\n"
                   "            return dict(response, presentation=make_presentation(\n"
                   "                game, ledger, primary, battle_board=request.get('battle_board'),\n"
                   "                committed_save_version=saved_at))\n"
                   "        except Exception as exc:\n"
                   "            print('Inline presentation unavailable: ' + repr(exc), file=sys.stderr, flush=True)\n"
                   "    return response\n")
    text = replace(text, "                    result = execute_request(game, root, request, prior_digest)",
                   "                    result = execute_request(game, root, request, prior_digest)\n"
                   "                    if 'presentation' in result:\n"
                   "                        read_digest = result['state_digest']")
    compile(text, str(service), 'exec')
    service.write_text(text, encoding='utf-8')
    schema_path = output / 'protocol.schema.json'
    schema = json.loads(schema_path.read_bytes())
    view = runpy.run_path(str(Path(__file__).with_name('slice_view.py')))
    commands, tutorial, sites = view['COMMANDS'], view['TUTORIAL'], view['SITES']
    schema['properties']['command']['enum'] = sorted(commands)
    schema['properties']['inline_presentation'] = {'type': 'boolean'}
    schema['properties']['battle_board'] = {'type': 'string', 'pattern': '^[A-Za-z0-9:_-]{1,80}$'}
    schema.setdefault('dependentSchemas', {})['battle_board'] = {
        'properties': {'inline_presentation': {'const': True}}, 'required': ['inline_presentation']}
    variants = [{'enum': sorted(tutorial)}]
    for action, option in [('support', {'type': 'string', 'pattern': '^[A-Za-z0-9_-]{1,80}$'}),
                           ('plan', {'enum': [*view['TUTORIAL_PLANS'], 'PASS']}),
                           ('cache', {'enum': ['EF03', 'EF05', 'EF07', 'PASS']})]:
        variants.append({'type': 'array', 'prefixItems': [{'const': action}, option], 'minItems': 2, 'maxItems': 2})
    constraints = {
        'tutorial': {'anyOf': variants}, 'quest': {'enum': sorted(view['QUEST_ACTIONS'])},
        **{command: {'enum': sorted(variants)} for command, variants in view['FIXED_ACTIONS'].items()},
    }
    coordinate = {'pattern': r'^-?\d{1,3}$'}
    member = {'pattern': '^' + view['MEMBER_ID'] + '$'}
    batch = {'pattern': '^' + view['BATCH_ID'] + '$'}
    constraints['event'] = {'anyOf': [
        {'enum': sorted(view['FIXED_ACTIONS']['event'])},
        {'prefixItems': [{'const': 'EV07'}, {'const': 'escort'}, member, {'const': 'CONFIRM'}],
         'minItems': 4, 'maxItems': 4},
    ]}
    for action, arguments in [('move', [{'enum': sorted(sites)}]), ('interact', [{'enum': sorted(sites)}]),
                              ('walkto', [coordinate, coordinate]), ('place', [{}, coordinate, coordinate, coordinate]),
                              ('deploy', [{}, {'enum': ['on', 'off']}]),
                              ('squad', [member, {'enum': ['on', 'off']}]),
                              ('stance', [member, {'enum': sorted(view['STANCES'])}]),
                              ('heal', [member]), ('level_up', [member]), ('care', [member]),
                              ('summon', [{'pattern': '^' + view['SUMMON_ID'] + '$'}, {'const': 'CONFIRM'}]),
                              ('equip', [{'pattern': '^' + view['MEMBER_ID'] + '$'}, {'pattern': '^' + view['GEAR_ID'] + '$'}])]:
        constraints[action] = {'prefixItems': arguments, 'minItems': len(arguments), 'maxItems': len(arguments)}
    book = {'pattern': '^' + view['BOOK_ID'] + '$'}
    move = {'pattern': '^' + view['MOVE_ID'] + '$'}
    constraints['book'] = {'anyOf': [
        {'enum': [['claim'], ['drop']]},
        {'prefixItems': [{'const': 'choice'}, {'enum': ['ST-104', *view['BOOK_RESEARCH']]}, book, {'const': 'CONFIRM'}],
         'minItems': 4, 'maxItems': 4},
        {'prefixItems': [{'const': 'task'}, {'const': 'accept'}, {'enum': list(view['BOOK_RESEARCH'])}],
         'minItems': 3, 'maxItems': 3},
        {'prefixItems': [{'enum': ['buy', 'learn']}, member, book], 'minItems': 3, 'maxItems': 3},
        {'prefixItems': [{'const': 'target'}, {'anyOf': [book, {'const': 'clear'}]}], 'minItems': 2, 'maxItems': 2},
        {'prefixItems': [{'const': 'equip'}, member, {'const': 'clear'}], 'minItems': 3, 'maxItems': 3},
        {'prefixItems': [{'const': 'equip'}, member, book], 'minItems': 3, 'maxItems': 3},
        {'prefixItems': [{'const': 'equip'}, member, book, book], 'minItems': 4, 'maxItems': 4, 'uniqueItems': True},
        {'prefixItems': [{'const': 'queue'}, member], 'items': move, 'minItems': 3, 'maxItems': 20},
        {'prefixItems': [{'const': 'auto'}, member, move, {'enum': ['on', 'off']}], 'minItems': 4, 'maxItems': 4},
        {'prefixItems': [{'const': 'main'}, member, {'anyOf': [{'enum': ['AUTO', 'BASIC']}, move]}],
         'minItems': 3, 'maxItems': 3},
    ]}
    constraints['unequip'] = {'prefixItems': [member, {'enum': list(view['GEAR_SLOTS'])}],
                              'minItems': 2, 'maxItems': 2}
    constraints['plan'] = {'anyOf': [
        {'enum': [['clear']]},
        {'items': {'type': 'string', 'pattern': '^' + view['PLAN_ID'] + '$'},
         'minItems': 1, 'maxItems': 3, 'uniqueItems': True},
    ]}
    placement_args = [member, coordinate, coordinate, {'enum': list('012345')}, member]
    constraints['deploy_at'] = {'prefixItems': placement_args, 'minItems': 4, 'maxItems': 5}
    constraints['rescue'] = {'anyOf': [
        {'enum': sorted(view['SEARCH_ACTIONS'])},
        {'prefixItems': [batch, {'const': 'CONFIRM'}], 'minItems': 2, 'maxItems': 2},
        {'prefixItems': [{'const': 'investigate'}, {'const': 'start'}, batch, {'const': 'CONFIRM'}],
         'minItems': 4, 'maxItems': 4},
    ]}
    constraints['facility'] = {'anyOf': [
        {'prefixItems': [{'const': 'build'}, {'enum': list(view['BUILDING_EFFECTS'])}, {'const': '1'},
                         {'pattern': '^' + view['BUILD_ORDER_ID'] + '$'}, {'const': 'CONFIRM'}],
         'minItems': 5, 'maxItems': 5},
        {'prefixItems': [{'enum': list(view['CONSTRUCTION_ACTIONS'])}, {'minLength': 1, 'maxLength': 64},
                         {'const': 'CONFIRM'}], 'minItems': 3, 'maxItems': 3},
    ]}
    service_id = {'pattern': '^' + view['SERVICE_ORDER_ID'] + '$'}
    outfit_targets = {'pattern': '^' + view['OUTFIT_TARGETS'] + '$'}
    constraints['service'] = {'prefixItems': [{'const': 'training'}, {'pattern': '^' + view['MEMBER_ID'] + ':1$'},
                                              service_id, {'const': 'CONFIRM'}], 'minItems': 4, 'maxItems': 4}
    constraints['outfit'] = {'anyOf': [
        {'prefixItems': [{'const': 'targets'}, outfit_targets], 'minItems': 2, 'maxItems': 2},
        {'prefixItems': [{'const': 'buy'}, {'const': 'defense'}, outfit_targets, service_id, {'const': 'CONFIRM'}],
         'minItems': 5, 'maxItems': 5},
    ]}
    consumables = view['CONSUMABLE_CODES']
    for command in ('craft', 'stash', 'take', 'discard'):
        allowed = consumables[:-2] if command == 'craft' else consumables
        constraints[command] = {'enum': [[item] for item in allowed]}
    constraints['use'] = {'anyOf': [
        {'enum': [[item] for item in view['PARTY_CONSUMABLES']]},
        {'prefixItems': [{'enum': list(consumables[:-2])},
                         {'pattern': '^' + view['CONSUMABLE_TARGETS'] + '$', 'maxLength': 256}],
         'minItems': 2, 'maxItems': 2},
    ]}
    constraints['supply'] = {'enum': [['commission', key] for key in (*view['MATERIAL_GOALS'], 'off')]}
    schema['allOf'] = [{'if': {'properties': {'command': {'const': command}}},
                         'then': {'properties': {'args': rule}}} for command, rule in constraints.items()]
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if release_id:
        (output / 'release-id.txt').write_text(release_id + '\n', encoding='ascii')
    inventory = {file.relative_to(output).as_posix(): digest(file)
                 for file in sorted(output.rglob('*')) if file.is_file()}
    (output / 'bundle.json').write_text(json.dumps({'p03_base': BASE_SHA, 'files': inventory},
                                                    ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'P06 runtime: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--release-id')
    parser.add_argument('output', type=Path)
    arguments = parser.parse_args()
    stage(arguments.source.resolve(), arguments.output.resolve(), arguments.release_id)
