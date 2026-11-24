"""Bind the accepted P03 bundle and install the P05 presentation-only extension."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import shutil


BASE_SHA = 'cf1d1e0d273a0c0bdeb4a0bcaa8eb58e65e42d4970551bf8ba2404f1a29f069b'
PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT.parents[1] / 'local/p03_sol4_20261105/dist/p03-windows-x64-write-candidate5'


def digest(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def replace(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f'Unexpected P03 source near {before!r}')
    return text.replace(before, after)


def stage(source, output):
    manifest = source / 'bundle.json'
    if digest(manifest) != BASE_SHA:
        raise ValueError('The P05 runtime requires the accepted P03 candidate')
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
    service = output / 'protocol_service.py'
    text = service.read_text(encoding='utf-8')
    start = text.index('COMMANDS = ')
    finish = text.index('\n\n\ndef read_frame', start)
    text = text[:start] + 'from slice_view import COMMANDS, valid_command, make_view' + text[finish:]
    text = replace(text, "if request['command'] == 'tutorial' and tuple(request['args']) not in TUTORIAL_ACTIONS:",
                   "if not valid_command(request['command'], request['args']):")
    text = replace(text, "                    result = dict(status='SNAPSHOT', state_version=store.recover(root)['version'], **snapshot(game, root, read_digest))",
                   "                    ledger = store.recover(root)\n"
                   "                    result = dict(status='SNAPSHOT', state_version=ledger['version'], **snapshot(game, root, read_digest))")
    text = replace(text, "                    result['presentation']['danger'] = danger",
                   "                    result['presentation']['danger'] = danger\n"
                   "                    result['presentation']['slice'] = make_view(game, ledger, result['files']['save.json'])")
    compile(text, str(service), 'exec')
    service.write_text(text, encoding='utf-8')
    schema_path = output / 'protocol.schema.json'
    schema = json.loads(schema_path.read_bytes())
    view = runpy.run_path(str(Path(__file__).with_name('slice_view.py')))
    commands, tutorial, sites = view['COMMANDS'], view['TUTORIAL'], view['SITES']
    schema['properties']['command']['enum'] = sorted(commands)
    variants = [{'enum': sorted(tutorial)}]
    for action, option in [('support', {'type': 'string', 'pattern': '^[A-Za-z0-9_-]{1,80}$'}),
                           ('plan', {'enum': ['PL01', 'PL02', 'PL05', 'PASS']}),
                           ('cache', {'enum': ['EF03', 'EF05', 'EF07', 'PASS']})]:
        variants.append({'type': 'array', 'prefixItems': [{'const': action}, option], 'minItems': 2, 'maxItems': 2})
    constraints = {
        'tutorial': {'anyOf': variants}, 'quest': {'const': ['commission', 'CONFIRM']},
        'return': {'const': ['CONFIRM']}, 'flee': {'const': ['CONFIRM']},
        'fight': {'const': []}, 'step': {'const': []}, 'retreat': {'const': []},
    }
    coordinate = {'pattern': r'^-?\d{1,3}$'}
    for action, arguments in [('move', [{'enum': sorted(sites)}]), ('interact', [{'enum': sorted(sites)}]),
                              ('walkto', [coordinate, coordinate]), ('place', [{}, coordinate, coordinate, coordinate]),
                              ('deploy', [{}, {'enum': ['on', 'off']}])]:
        constraints[action] = {'prefixItems': arguments, 'minItems': len(arguments), 'maxItems': len(arguments)}
    schema['allOf'] = [{'if': {'properties': {'command': {'const': command}}},
                         'then': {'properties': {'args': rule}}} for command, rule in constraints.items()]
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    inventory = {file.relative_to(output).as_posix(): digest(file)
                 for file in sorted(output.rglob('*')) if file.is_file()}
    (output / 'bundle.json').write_text(json.dumps({'p03_base': BASE_SHA, 'files': inventory},
                                                    ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'P05 runtime: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('output', type=Path)
    arguments = parser.parse_args()
    stage(arguments.source.resolve(), arguments.output.resolve())
