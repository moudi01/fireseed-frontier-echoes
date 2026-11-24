"""Conservative durable request ledger for new experimental sessions only.

An interrupted PREPARED entry is UNKNOWN, never permission to repeat a command.
No production state schema changes. A committed ledger signs the complete
primary/backup/retry file set; mismatches stop the session.
"""
from pathlib import Path
import hashlib
import json
import os


def open_session(root):
    root = Path(root).resolve()
    if root.is_symlink():
        raise ValueError('Symlink session refused')
    root.mkdir(parents=True, exist_ok=True)
    return root


def prepare(root, request, payload_hash, before):
    ledger = recover(root)
    row = dict(status='PREPARED', request=request, payload_hash=payload_hash,
               before=before, version=ledger['version'])
    ledger['entries'][request['request_id']] = row
    commit(root, ledger)
    return ledger


def commit(root, ledger):
    path = Path(root) / 'ledger.json'
    tmp = Path(root) / 'ledger.next'
    raw = json.dumps(ledger, ensure_ascii=False, sort_keys=True,
                     separators=(',', ':'), allow_nan=False).encode('utf-8')
    with tmp.open('wb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def recover(root):
    # A killed retry-sidecar writer can leave its complete or partial temporary
    # file. Preserve it and stop before loading or executing the session.
    if (Path(root) / 'save.json.finale_retry.json.tmp').exists():
        raise ValueError('RECOVERY_REQUIRED: interrupted retry replacement')
    path = Path(root) / 'ledger.json'
    if (Path(root) / 'ledger.next').exists():
        raise ValueError('RECOVERY_REQUIRED: interrupted ledger replacement')
    if path.exists():
        ledger = json.loads(path.read_text(encoding='utf-8'))
        if ledger.get('format') != 'P03-LEDGER-1':
            raise ValueError('RECOVERY_REQUIRED: unknown ledger')
        return ledger
    return dict(format='P03-LEDGER-1', version=0, entries={})


def lookup(root, request_id):
    return recover(root)['entries'].get(request_id)
