"""Hash-pinned, byte-preserving staging. No runtime imports or gameplay."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parent


def verify_inputs(manifest, base):
    base = Path(base).resolve()
    for row in manifest['files']:
        path = (base / row['path']).resolve()
        if not path.is_relative_to(base):
            raise ValueError('Input outside root')
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Input drift: ' + row['path'])


def write_manifest(manifest):
    with (ROOT / 'input_manifest.json').open('x', encoding='utf-8') as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)


def copy_runtime_closure(manifest, source):
    verify_inputs(manifest, source)
    target = ROOT / 'vendor'
    if target.exists():
        raise ValueError('Refuse existing vendor directory')
    target.mkdir()
    for row in manifest['files']:
        # Repeat immediately before copying and verify the resulting bytes.
        origin = Path(source) / row['path']
        if hashlib.sha256(origin.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Input drift: ' + row['path'])
        dest = target / row['path']
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, dest)
    verify_inputs(manifest, target)
